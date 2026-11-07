# --- src/core/maintenance.py ---
from src.api.sheets import SheetsClient

def _obtener_llave_orden(fila):
    """Mantiene tu lógica de ordenamiento por categoría e ID."""
    try:
        categoria = str(fila[4]).strip().upper()
        # Procesa el ID (1.12) como tupla numérica para ordenar correctamente
        id_partes = tuple(int(p) for p in str(fila[0]).split('.') if p.isdigit())
        nombre = str(fila[3]).strip().lower()
        return (categoria, id_partes, nombre)
    except:
        return ("ZZZZ", (999, 999), "zzzz")

def ejecutar_mantenimiento():
    print("\n🛠️ Iniciando mantenimiento y limpieza profunda (Modo Seguro)...")
    sc = SheetsClient()
    
    try:
        todo = sc.sheet.get_all_values()
        if len(todo) <= 1:
            print("⚠️ La tabla está vacía.")
            return
            
        encabezado = todo[0]
        
        # 🔥 PURGA DE ZOMBIES: Solo aceptamos filas que tengan NOMBRE (Columna D / Índice 3)
        # Esto elimina automáticamente las 400 filas vacías que tenían IDs basura.
        productos = [
            f for f in todo[1:] 
            if len(f) > 3 and str(f[3]).strip() != "" and ".0" not in str(f[0])
        ]

        # 1. Ordenar usando la lógica de tuplas
        productos.sort(key=_obtener_llave_orden)
        
        # Identificar categorías únicas presentes
        categorias_unicas = []
        for p in productos:
            cat = str(p[4]).strip().upper()
            if cat and cat not in categorias_unicas:
                categorias_unicas.append(cat)

        lista_reorganizada = []
        filas_jefe_indices = []

        # 2. Re-indexación dinámica con 16 columnas obligatorias
        for i, cat_nombre in enumerate(categorias_unicas, 1):
            # Fila Jefe (Azul Petróleo) - AHORA CON 16 CAMPOS PARA NO BORRAR COLUMNAS
            filas_jefe_indices.append(len(lista_reorganizada) + 2) # +2 por header y base 1
            
            fila_jefe = [
                f"{i}.0", "", "ENCABEZADO", f"--- {cat_nombre} ---", cat_nombre, 
                "", "", "", "", "", "", False, False, False, "", ""
            ]
            lista_reorganizada.append(fila_jefe)
            
            # Filtrar productos de esta categoría y re-indexar
            prods_de_esta_cat = [p for p in productos if str(p[4]).strip().upper() == cat_nombre]
            for j, prod in enumerate(prods_de_esta_cat, 1):
                # Aseguramos que el producto mantenga las 16 columnas antes de subirlo
                p_ajustado = prod + [""] * (16 - len(prod))
                p_ajustado[0] = f"{i}.{j}"

                # Forzamos texto que Google Sheets entiende como Checkbox (TRUE/FALSE)
                p_ajustado[11] = str(prod[11]).upper() if len(prod) > 11 else "FALSE"
                p_ajustado[12] = str(prod[12]).upper() if len(prod) > 12 else "FALSE"
                p_ajustado[13] = str(prod[13]).upper() if len(prod) > 13 else "TRUE"

                lista_reorganizada.append(p_ajustado)

        # 3. Sincronización final
        print(f"📤 Sincronizando {len(productos)} productos organizados...")
        sc.sheet.clear()
        sc.sheet.update('A1', [encabezado] + lista_reorganizada)
        
        # 4. Aplicar estilos visuales sin saturar la API
        _aplicar_estilos_batch(sc.sheet, filas_jefe_indices, len(lista_reorganizada) + 1)
        
        print(f"✅ ¡Excel inmaculado! Todo subió a la parte superior.")
        return True

    except Exception as e:
        print(f"❌ Error en el mantenimiento: {e}")
        return False

def _aplicar_estilos_batch(worksheet, indices_jefe, total_filas):
    """Aplica diseño Azul Petróleo y Header Carbono en una sola petición."""
    print("🎨 Aplicando diseño corporativo...")
    
    # Formato general (limpieza de negritas)
    requests = [{
        "repeatCell": {
            "range": {"sheetId": worksheet.id, "startRowIndex": 1, "endRowIndex": total_filas},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": False}, "verticalAlignment": "MIDDLE"}},
            "fields": "userEnteredFormat(textFormat, verticalAlignment)"
        }
    }]

    # Estilo Header (Gris Carbono)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": worksheet.id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": {"red": 0.15, "green": 0.15, "blue": 0.15},
                    "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
                    "horizontalAlignment": "CENTER"
                }
            },
            "fields": "userEnteredFormat(backgroundColor, textFormat, horizontalAlignment)"
        }
    })

    # --- INSERTAR CHECKBOXES REALES (Columnas L, M, N) ---
    # Esto le dice a Google: "Estas celdas son checkboxes, no texto"
    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": worksheet.id, 
                "startRowIndex": 1, 
                "endRowIndex": total_filas, 
                "startColumnIndex": 11, # Columna L
                "endColumnIndex": 14    # Hasta la N
            },
            "rule": {
                "condition": {"type": "BOOLEAN"}, # Esto es lo que crea el checkbox
                "showCustomUi": True
            }
        }
    })

    # Estilo Filas Jefe (Azul Petróleo)
    for idx in indices_jefe:
        requests.append({
            "repeatCell": {
                "range": {"sheetId": worksheet.id, "startRowIndex": idx-1, "endRowIndex": idx},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.0, "green": 0.25, "blue": 0.45},
                        "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True}
                    }
                },
                "fields": "userEnteredFormat(backgroundColor, textFormat)"
            }
        })

    worksheet.spreadsheet.batch_update({"requests": requests})