import subprocess
import sys
import os
import re
import importlib.util
import json
import time # 🔥 Importante para las pausas
from datetime import datetime

# --- BLOQUE DE AUTO-INSTALACIÓN ---
def instalar_dependencias():
    dependencias = ["gspread", "googleapiclient", "PIL", "pillow_heif", "pdf2image"]
    faltantes = [pkg for pkg in dependencias if importlib.util.find_spec(pkg) is None]

    if faltantes:
        print(f"🛠️ Faltan librerías ({', '.join(faltantes)}). Instalando...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("✅ Todo instalado. Reiniciando programa...\n")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"❌ Error instalando dependencias: {e}")
            sys.exit(1)

instalar_dependencias()

# --- FUNCIÓN PRINCIPAL ---
def main():
    from src.config import ID_FOTOS_PENDIENTES, ID_FOTOS_PROCESADOS
    from src.api.drive import GoogleDriveClient
    from src.api.vision import LectorIA
    from src.api.sheets import SheetsClient
    from src.core.handler import gestionar_auditoria_interactiva
    from src.utils.text_utils import parsear_ticket_bruto 

    drive = GoogleDriveClient()
    ia = LectorIA()
    
    # 1. LISTAR Y ORDENAR (Marzo antes que Abril)
    items_pendientes = drive.listar_todo(ID_FOTOS_PENDIENTES)
    items_pendientes.sort(key=lambda x: x['name']) # 🔥 Orden cronológico por nombre
    
    for item in items_pendientes:
        # 🛡️ VERIFICACIÓN ANTI-FANTASMAS
        try:
            drive.service.files().get(fileId=item['id']).execute()
        except:
            print(f"👻 Saltando {item['name']}: El archivo ya no existe o fue movido.")
            continue

        # 🛡️ SEGURIDAD: Ignorar carpeta de Procesados
        if item['id'] == ID_FOTOS_PROCESADOS or item['name'].lower() == 'procesados':
            continue

        id_capsula = None
        nombre_base = item['name']
        
        # --- CASO A: IMAGEN SUELTA ---
        if item['mimeType'] != 'application/vnd.google-apps.folder':
            if not any(item['name'].lower().endswith(ex) for ex in ['.jpg', '.jpeg', '.png', '.heic', '.pdf']):
                continue 
            
            print(f"\n📸 NUEVO TICKET DETECTADO: {item['name']}")
            nombre_base = item['name'].rsplit('.', 1)[0]
            id_capsula = drive.crear_carpeta(nombre_base, ID_FOTOS_PENDIENTES)
            drive.mover(item['id'], id_capsula)
        
        # --- CASO B: CARPETA ---
        else:
            print(f"\n📁 INSPECCIONANDO CARPETA: {item['name']}")
            id_capsula = item['id']
            nombre_base = item['name']
        
        # --- PROCESAMIENTO INTERNO ---
        archivos_internos = drive.listar_internos(id_capsula)
        foto_obj = next((f for f in archivos_internos if any(f['name'].lower().endswith(ex) for ex in ['.jpg', '.jpeg', '.png', '.heic', '.pdf'])), None)
        
        if not foto_obj:
            print(f"⚠️ No hay imagen en {nombre_base}. Saltando...")
            continue
            
        # 1. Extracción de Texto (OCR) - CON FRENO DE MANO
        texto_bruto = None
        while True: # 🔥 Bucle para obligar al programa a esperar tu orden
            archivo_txt = next((f for f in archivos_internos if f['name'].endswith('.txt')), None)
            
            if not archivo_txt:
                print(f"🧠 IA: Intentando leer {foto_obj['name']}...")
                texto_bruto = ia.analizar_archivo(drive.descargar(foto_obj['id']), foto_obj['name'])
                
                if texto_bruto:
                    drive.subir_texto(f"{nombre_base}.txt", texto_bruto, id_capsula)
                    print("⏳ Pausa técnica de 8s...")
                    time.sleep(8)
                    break # Éxito: salimos del bucle y seguimos al paso 2
                else:
                    # 🛑 EL FRENO: Si falla la IA, se detiene y pregunta
                    print(f"\n❌ ERROR: La IA no pudo extraer texto de {nombre_base}.")
                    op = input("¿Qué deseas hacer? ([r]eintentar / [s]altar ticket / [q]uit-salir): ").lower()
                    if op == 'r': continue # Vuelve a intentar con la IA
                    if op == 'q': return   # Cierra el programa por completo
                    break # Sale del while, texto_bruto sigue siendo None
            else:
                print("📜 Usando TXT existente...")
                stream_txt = drive.descargar(archivo_txt['id'])
                texto_bruto = stream_txt.read().decode('utf-8')
                break # Tenemos el texto, seguimos adelante

        # Si elegiste 's' (saltar), texto_bruto será None y aquí sí hacemos el continue del for
        if not texto_bruto: 
            continue

        # 2. Generación de JSON Bruto (Con respaldo de fecha)
        datos_brutos = None
        archivo_bruto = next((f for f in archivos_internos if f['name'].endswith('_bruto.json')), None)
        
        if not archivo_bruto:
            print("⚙️ Generando JSON bruto...")
            # 🔥 Pasamos el nombre de la foto para asegurar la fecha correcta
            datos_brutos = parsear_ticket_bruto(texto_bruto, foto_obj['name']) 
            drive.subir_json(f"{nombre_base}_bruto.json", datos_brutos, id_capsula)
            time.sleep(3) # Pausa corta
        else:
            print("📄 Usando JSON bruto existente...")
            stream_bruto = drive.descargar(archivo_bruto['id'])
            datos_brutos = json.loads(stream_bruto.read().decode('utf-8'))

        # 3. Clasificación Local (Python puro y duro)
        datos_finales = None
        archivo_final = next((f for f in archivos_internos if f['name'].endswith('_final.json')), None)
        
        if archivo_final:
            print("📊 Usando clasificación local existente...")
            stream_final = drive.descargar(archivo_final['id'])
            datos_finales = json.loads(stream_final.read().decode('utf-8'))
            
            tiene_categorias = any('categoria' in linea for linea in datos_finales.get('lineas', []))
            if not tiene_categorias:
                print("⚠️ El JSON guardado está incompleto. Forzando a Python a clasificar...")
                archivo_final = None 
        
        if not archivo_final:
            print("🧠 Python: Clasificando productos en milisegundos...")
            sheets = SheetsClient()
            filas_excel = sheets.obtener_todas_las_filas() # Descargamos el historial
            
            from src.utils.clasificador_local import clasificar_json_completo
            datos_finales = clasificar_json_completo(datos_brutos, filas_excel)
            
            if datos_finales:
                drive.subir_json(f"{nombre_base}_final.json", datos_finales, id_capsula)
                print("⏳ Preparando auditoría...")
                time.sleep(2) # Redujimos la pausa de 5s a 2s porque Python no se cansa

        # 4. Verificación de Integridad y Auditoría Interactiva
        print("🔍 Verificando integridad del JSON final...")
        archivo_final_check = next((f for f in drive.listar_internos(id_capsula) if f['name'].endswith('_final.json')), None)
        
        if archivo_final_check:
            stream_final = drive.descargar(archivo_final_check['id'])
            try:
                datos_finales = json.loads(stream_final.read().decode('utf-8'))
            except json.JSONDecodeError:
                print(f"❌ ERROR: El archivo {archivo_final_check['name']} se corrompió en Drive. Saltando ticket...")
                continue
                
        # 🔥 LA LLAMADA AL HANDLER QUE HACE LA AUDITORÍA Y EL TIMEOUT
        resultado = gestionar_auditoria_interactiva(datos_finales)
        
        if resultado == "QUIT":
            print("\n🛑 ABORTANDO PROGRAMA POR ORDEN DEL USUARIO.")
            break
        
        if resultado is True:
            print(f"✅ Registro exitoso. Archivando...")
            # 🔥 Super-parseador de fechas para carpetas de Drive
            fecha_str = datos_finales.get('fecha', datetime.now().strftime("%d/%m/%Y")).replace('-', '/')
            partes = fecha_str.split('/')
            
            # Detecta si el año está al principio (YYYY/MM/DD) o al final (DD/MM/YYYY)
            if len(partes[0]) == 4:
                anio, mes_num = partes[0], partes[1]
            else:
                anio, mes_num = partes[2], partes[1]
                
            meses = ["01-ENERO", "02-FEBRERO", "03-MARZO", "04-ABRIL", "05-MAYO", "06-JUNIO",
                     "07-JULIO", "08-AGOSTO", "09-SEPTIEMBRE", "10-OCTUBRE", "11-NOVIEMBRE", "12-DICIEMBRE"]
            mes_nombre = meses[int(mes_num)-1]

            id_anio = drive.obtener_o_crear_carpeta(anio, ID_FOTOS_PROCESADOS)
            id_mes = drive.obtener_o_crear_carpeta(mes_nombre, id_anio)
            drive.mover(id_capsula, id_mes)
            print(f"📁 Archivando en: {anio} > {mes_nombre} > {nombre_base}")

    print("\n🏁 Proceso terminado.")

if __name__ == "__main__":
    main()