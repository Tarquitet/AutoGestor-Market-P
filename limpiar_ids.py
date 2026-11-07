from src.api.sheets import SheetsClient
import re

def generar_codigo_id(nombre):
    """Convierte 'Avena Entera de la Cuesta' en 'AVENA_ENTERA_DE_LA_CUESTA'"""
    codigo = str(nombre).upper().strip()
    reemplazos = (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("Ñ", "N"))
    for a, b in reemplazos:
        codigo = codigo.replace(a, b)
    return re.sub(r'[^A-Z0-9]+', '_', codigo).strip('_')

print("⏳ Conectando a Google Sheets para la purga de IDs...")
sheets = SheetsClient()
filas = sheets.sheet.get_all_values()

actualizaciones = []

for i, fila in enumerate(filas):
    # Asegurarnos de que la fila tenga datos
    if len(fila) < 4:
        continue
    
    codigo_actual = str(fila[2]).strip()
    nombre_producto = str(fila[3]).strip()
    
    # Si detecta el virus "GENERAR_ID"
    if codigo_actual == "GENERAR_ID" and nombre_producto and nombre_producto != "---":
        nuevo_id = generar_codigo_id(nombre_producto)
        fila_excel = i + 1 # +1 porque Google Sheets empieza en la fila 1
        
        # Guardamos la celda exacta y el nuevo valor
        actualizaciones.append({
            'range': f'C{fila_excel}',
            'values': [[nuevo_id]]
        })
        print(f"✅ Fila {fila_excel}: {nombre_producto} -> {nuevo_id}")

# Subimos todas las correcciones de un solo golpe para no gastar cuota de API
if actualizaciones:
    print(f"\n🚀 Subiendo {len(actualizaciones)} correcciones a tu Excel...")
    sheets.sheet.batch_update(actualizaciones)
    print("✨ ¡Purga completada! Tu Excel está inmaculado.")
else:
    print("👍 No se encontraron 'GENERAR_ID'. Todo está limpio.")