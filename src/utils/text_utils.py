import re
import json
import datetime

def limpiar_precio_peso(valor):
    """Quita todo lo que no sea número (puntos, comas, letras)."""
    if not valor:
        return 0
    numeros = re.sub(r'[^0-9]', '', str(valor))
    return int(numeros) if numeros else 0

def extraer_json_salvavidas(texto):
    """Busca los corchetes { } en el texto de la IA para sacar el JSON puro."""
    if not texto:
        return None
    texto = texto.replace('```json', '').replace('```', '').strip()
    try:
        inicio = texto.find('{')
        fin = texto.rfind('}') + 1
        if inicio != -1:
            return json.loads(texto[inicio:fin])
        return json.loads(texto)
    except:
        return None

def limpiar_nombre_comparacion(txt):
    """Normaliza nombres para comparar productos sin importar guiones o mayúsculas."""
    if not txt:
        return ""
    txt = str(txt).replace('_', ' ').strip().lower()
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
    for original, limpio in reemplazos.items():
        txt = txt.replace(original, limpio)
    return txt

def extraer_fecha(texto_bruto, nombre_archivo=""):
    """
    Intenta sacar la fecha del texto del ticket. 
    Si falla, intenta sacarla del nombre del archivo (ej: 20260318).
    """
    # 1. Buscar en el texto (Formatos DD/MM/YYYY o YYYY/MM/DD)
    match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})|(\d{4}[/-]\d{2}[/-]\d{2})', texto_bruto)
    if match:
        # 🔥 CORRECCIÓN AQUÍ: Obligamos a que siempre salga como DD/MM/YYYY
        fecha_str = match.group(0).replace('-', '/')
        partes = fecha_str.split('/')
        if len(partes[0]) == 4: # Si viene como YYYY/MM/DD
            return f"{partes[2]}/{partes[1]}/{partes[0]}"
        return fecha_str
    
    # 2. Buscar en el nombre del archivo (Formato YYYYMMDD como tus fotos)
    match_nombre = re.search(r'(\d{4})(\d{2})(\d{2})', nombre_archivo)
    if match_nombre:
        a, m, d = match_nombre.groups()
        return f"{d}/{m}/{a}"
        
    # 3. Si todo falla, usa la fecha actual
    return datetime.date.today().strftime("%d/%m/%Y")

def parsear_ticket_bruto(texto_ia, nombre_archivo=""):
    """Convierte el texto de la IA en un JSON inicial con detección mejorada, filtro anti-basura y lectura inteligente."""
    lineas = texto_ia.strip().split('\n')
    
    # 1. DETECCIÓN DE TIENDA
    tienda = "DESCONOCIDA"
    for l in lineas:
        if "TIENDA:" in l:
            tienda = l.replace("TIENDA:", "").strip().upper()
            break
            
    if tienda == "DESCONOCIDA" and lineas:
        for l in lineas:
            if re.search(r'[A-Z]', l):
                tienda = l.strip().upper()
                break
                
    fecha = extraer_fecha(texto_ia, nombre_archivo)
    datos = {"tienda": tienda, "fecha": fecha, "lineas": []}
    
    item_actual = None
    
    for linea in lineas:
        linea = linea.strip().upper()
        
        # --- 1. FILTRO ANTI-BASURA ---
        if not linea: 
            continue
            
        palabras_basura = [
            "TOTAL", "DESCUENTO", "CAMBIO", "VUELTO", "TARJETA", "EFECTIVO", 
            "IVA", "ATENDIDO", "TRACK", "DOCUMENTO", "SUB TOTAL", "PESO NETO", 
            "IMPUESTO", "RECIBIDO", "GRACIAS", "SITRICPOS", "TIENDA:", "BOGOTA",
            "NIT", "DIAN", "HABILITADA", "CLIENTE", "GRAVADOS", "VIGENCIA", 
            "FACT", "COMPROBANTE", "ENTREGA"
        ]
        if any(p in linea for p in palabras_basura):
            continue
            
        # Bloquea fechas (YYYY-MM-DD), horas (HH:MM) y códigos de TrackID
        if re.search(r'\d{4}-\d{2}-\d{2}', linea) or re.search(r'\d{2}:\d{2}', linea) or "TRACKID" in linea:
            continue

        # --- 2. ¿ES UNA LÍNEA DE CANTIDAD HUÉRFANA? (Ej: "2 UN X 9.880") ---
        match_cantidad = re.search(r'^([\d\.,]+)\s*([A-Z]*)\s*X\s*([\d\.,]+)', linea)
        if match_cantidad and item_actual:
            cant_str, unidad, precio_u_str = match_cantidad.groups()
            try:
                item_actual["cantidad"] = float(cant_str.replace(',', '.'))
            except ValueError:
                pass
            item_actual["precio_unitario"] = limpiar_precio_peso(precio_u_str)
            continue

        # --- 3. ES UN NUEVO PRODUCTO: Leemos de derecha a izquierda ---
        match_producto = re.search(r'^(.*?)\s+([\d\.,]+(?:\s+\d{3})*)\s*([A-Z0-9]{0,2})?$', linea)
        
        if match_producto:
            texto_izq, precio_str, basura = match_producto.groups()
            precio_total = limpiar_precio_peso(precio_str)
            
            ean = "00000"
            cantidad = 1.0
            precio_unitario = precio_total
            
            # A. Buscar EAN ignorando basura al inicio (Ej: "1 770...")
            match_ean = re.search(r'(?:^\d+\s+)?(\d{5,})\s+(.*)', texto_izq)
            if match_ean:
                ean = match_ean.group(1)
                nombre_bruto = match_ean.group(2)
            else:
                # B. Sin EAN (Fruver). Limpiamos letras de viñeta inicial
                nombre_bruto = re.sub(r'^(?:[A-Z]\s+|\d+\s+)', '', texto_izq)

            # C. Detectar si la cantidad está incrustada en la misma línea (Fruver)
            match_incrustado = re.search(r'(.*?)\s+([\d\.,]+)\s*([A-Z]+)\s+([\d\.,]+)$', nombre_bruto)
            if match_incrustado:
                nombre_bruto = match_incrustado.group(1)
                try:
                    cantidad = float(match_incrustado.group(2).replace(',', '.'))
                except ValueError:
                    pass
                precio_unitario = limpiar_precio_peso(match_incrustado.group(4))

            item_actual = {
                "nombre_ticket": nombre_bruto.strip(),
                "precio_total_linea": precio_total,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "ean": ean
            }
            datos["lineas"].append(item_actual)
            
    return datos