# --- src/api/sheets.py ---
import gspread
import os
import re
import copy
from datetime import datetime
from google.oauth2.credentials import Credentials
from src.config import SPREADSHEET_ID, HISTORICO_NAME

# 🔥 DOS FUNCIONES NUEVAS PARA PROTEGER LAS FECHAS AL 100%
def parsear_fecha_flexible(fecha_str):
    fecha_str = str(fecha_str).strip().replace('-', '/')
    partes = fecha_str.split('/')
    if len(partes) == 3 and len(partes[0]) == 4:
        return datetime.strptime(f"{partes[2]}/{partes[1]}/{partes[0]}", "%d/%m/%Y")
    return datetime.strptime(fecha_str, "%d/%m/%Y")

def estandarizar_fecha_str(fecha_str):
    fecha_str = str(fecha_str).strip().replace('-', '/')
    partes = fecha_str.split('/')
    if len(partes) == 3 and len(partes[0]) == 4:
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    return fecha_str
# --------------------------------------------------------

class SheetsClient:
    def __init__(self):
        if not os.path.exists('token.json'):
            raise FileNotFoundError("❌ No existe token.json. Ejecuta primero la autenticación.")
        creds = Credentials.from_authorized_user_file('token.json')
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(SPREADSHEET_ID).worksheet(HISTORICO_NAME)

    def obtener_todas_las_filas(self):
        return self.sheet.get_all_values()

    def obtener_categorias(self):
        """Obtiene las categorías únicas de la columna E."""
        valores = self.sheet.col_values(5) 
        return sorted(list(set([v.strip().upper() for v in valores[1:] if v and "---" not in v])))

    def _limpiar_valor_moneda(self, valor):
        """Extrae solo los números de un string como '$ 15.000'."""
        if not valor: return 0
        # Quitamos todo lo que no sea número
        solo_numeros = re.sub(r'[^0-9]', '', str(valor))
        return int(solo_numeros) if solo_numeros else 0

    def actualizar_fila_exacta(self, fila_index, nombre_t, ean, precio_nuevo, fila_original, fecha_ticket, cant_compra, categoria_nueva=None):
        """Actualiza el producto: Matemática en enteros (30 días) + Protección de Checkboxes."""
        nueva_fila = copy.deepcopy(fila_original)
        
        # Aseguramos que la fila tenga las 16 columnas para no romper el formato
        while len(nueva_fila) < 16: nueva_fila.append("")
        
        fecha_ticket_limpia = estandarizar_fecha_str(fecha_ticket)
        es_ticket_nuevo = True
        
        # Validamos si el ticket que entró es más viejo que el último registrado
        if nueva_fila[9] and nueva_fila[9] != "":
            fecha_excel = parsear_fecha_flexible(nueva_fila[9])
            fecha_actual_ticket = parsear_fecha_flexible(fecha_ticket)
            if fecha_actual_ticket < fecha_excel:
                es_ticket_nuevo = False

        if categoria_nueva:
            nueva_fila[4] = categoria_nueva

        # --- 1. MATEMÁTICA EN ENTEROS (COLUMNAS H e I) ---
        if es_ticket_nuevo:
            try:
                # Convertimos cantidad a entero para evitar decimales como 1.09
                cant_actual = int(float(str(cant_compra).replace(',', '.')))
                
                if nueva_fila[9] and nueva_fila[9] != "":
                    f_ant = parsear_fecha_flexible(nueva_fila[9])
                    f_act = parsear_fecha_flexible(fecha_ticket)
                    dias = (f_act - f_ant).days
                    
                    # Lógica de ventana de 30 días (Sin divisiones por 30.44)
                    if dias <= 30: 
                        # FREC MES (Col I): Sumamos 1 compra al contador real
                        try:
                            frec_ant = int(float(str(nueva_fila[8]).replace(',', '.')))
                        except:
                            frec_ant = 0
                        nueva_fila[8] = frec_ant + 1
                        
                        # CANT MES (Col H): Guardamos la cantidad más alta registrada
                        try:
                            cant_max_ant = int(float(str(nueva_fila[7]).replace(',', '.')))
                        except:
                            cant_max_ant = 0
                        nueva_fila[7] = max(cant_max_ant, cant_actual)
                    else:
                        # Si pasó más de un mes, reiniciamos el ciclo de estadísticas
                        nueva_fila[8] = 1
                        nueva_fila[7] = cant_actual
                else:
                    # Producto sin fecha previa: primer registro del ciclo
                    nueva_fila[8] = 1
                    nueva_fila[7] = cant_actual
            except Exception as e:
                print(f"⚠️ Error en cálculos para {nombre_t}: {e}")
                nueva_fila[8] = 1
                nueva_fila[7] = int(float(cant_compra))

            # Guardamos datos de la última compra
            nueva_fila[9] = fecha_ticket_limpia
            nueva_fila[10] = int(float(cant_compra))

            # Actualización de precios (O y P)
            precio_actual_excel = self._limpiar_valor_moneda(nueva_fila[14])
            if precio_actual_excel != precio_nuevo:
                nueva_fila[15] = precio_actual_excel 
                nueva_fila[14] = int(precio_nuevo)

        # --- 2. PROTECCIÓN DE CHECKBOXES (L, M, N) ---
        # Recuperamos los valores de la fila original para que NO se borren tus selecciones
        nueva_fila[11] = fila_original[11] if len(fila_original) > 11 else "FALSE"
        nueva_fila[12] = fila_original[12] if len(fila_original) > 12 else "FALSE"
        nueva_fila[13] = fila_original[13] if len(fila_original) > 13 else "TRUE"
        
        # Subimos todo con USER_ENTERED para que Google Sheets respete el dibujo del checkbox
        self.sheet.update(f"A{fila_index}:P{fila_index}", [nueva_fila[:16]], value_input_option='USER_ENTERED')
        return True

    def obtener_tiendas_registradas(self):
        """Lee la columna F y devuelve una lista de tiendas únicas."""
        # Columna F es el índice 6 (base 1)
        valores = self.sheet.col_values(6) 
        # Limpiamos, quitamos duplicados y el encabezado
        tiendas = set([v.strip().upper() for v in valores[1:] if v and "---" not in v])
        return list(tiendas)

    def registrar_nuevo(self, nombre_t, ean, precio, tienda, categoria, fecha, cant_compra):
        """Inserta el producto nuevo al final como un usuario real."""
        # Generar CÓDIGO ID (C)
        codigo_id = nombre_t.upper().strip()
        reemplazos = (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("Ñ", "N"))
        for a, b in reemplazos:
            codigo_id = codigo_id.replace(a, b)
        codigo_id = re.sub(r'[^A-Z0-9]+', '_', codigo_id).strip('_')

        # 🔥 Limpiamos la fecha por si acaso antes de guardarla como nuevo registro
        fecha_limpia = estandarizar_fecha_str(fecha)
        cant_entero = int(float(cant_compra))

        nueva_fila = [
            "",                        # A: ID
            str(ean).strip() if ean else "", # B: EAN (Sin comilla manual)
            codigo_id,                 # C: CÓDIGO ID
            nombre_t.upper(),          # D: Nombre
            categoria.upper(),         # E: Categoría
            tienda.upper(),            # F: Tienda
            nombre_t.upper(),          # G: Desc. Ticket
            cant_entero,        # H: CANT MES (Inicia con la cantidad actual)
            1,                         # I: FREC MES (Inicia en 1)
            fecha_limpia,              # J: ÚLT. FECHA
            cant_entero,        # K: ÚLT. CANT (Número real)
            "FALSE",                   # L: SOLO
            "FALSE",                   # M: PAREJA
            "TRUE",                    # N: FAMILIA
            int(precio),               # O: PRECIO ACTUAL (Número sin $)
            ""                         # P: PRECIO ANTERIOR
        ]
        
        # 🚀 SUBIDA AL SHEETS CON USER_ENTERED
        self.sheet.append_row(nueva_fila, value_input_option='USER_ENTERED')
        return True