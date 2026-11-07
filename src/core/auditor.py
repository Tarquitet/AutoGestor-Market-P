# --- src/core/auditor.py ---
import copy
import re
import difflib
from datetime import date
from src.utils.text_utils import limpiar_precio_peso
from src.utils.search_engine import buscar_top_coincidencias

def mapear_tienda_inteligente(tienda_ticket, tiendas_excel):
    """Compara la tienda del ticket con las del Excel y busca la mejor opción."""
    t_ticket = tienda_ticket.upper().strip()
    
    # 1. Búsqueda exacta
    if t_ticket in tiendas_excel:
        return t_ticket
    
    # 2. Búsqueda de palabra contenida (Ej: 'EXITO' dentro de 'ALMACENES EXITO')
    for t_ex in tiendas_excel:
        if t_ex in t_ticket or t_ticket in t_ex:
            return t_ex
            
    # 3. Búsqueda por similitud (Fuzzy)
    coincidencias = difflib.get_close_matches(t_ticket, tiendas_excel, n=1, cutoff=0.6)
    if coincidencias:
        return coincidencias[0]
        
    # 4. Si es totalmente nueva, la usamos tal cual y el sistema la "aprenderá" al guardarla
    return t_ticket

def generar_plan_auditoria(datos_ia, sheets):
    tienda_raw = datos_ia.get('tienda', 'DESCONOCIDA').upper()
    fecha_ticket = datos_ia.get('fecha', date.today().strftime("%d/%m/%Y"))
    tiendas_en_excel = sheets.obtener_tiendas_registradas()
    # El sistema decide si es una tienda vieja conocida o una nueva
    tienda = mapear_tienda_inteligente(tienda_raw, tiendas_en_excel)
    
    filas_excel = sheets.obtener_todas_las_filas()
    plan_de_accion = []

    for item in datos_ia.get('lineas', []):
        nombre_t = item.get('nombre_ticket', '???')
        ean = item.get('ean', '')
        cant = float(item.get('cantidad', 1.0))
        precio_u = int(limpiar_precio_peso(item.get('precio_total_linea') or 0) / cant) if cant > 0 else 0

        res = buscar_top_coincidencias({'nombre_ticket': nombre_t, 'ean': ean}, filas_excel, top_n=1)
        
        if res and res[0]['score'] == 100:
            f_antes = copy.deepcopy(filas_excel[res[0]['fila_index'] - 1])
            f_antes += [""] * (16 - len(f_antes))
            f_desp = copy.deepcopy(f_antes)
            
            # Preparar cambios
            precio_excel = limpiar_precio_peso(f_antes[14])
            cambio_precio = precio_excel != precio_u
            
            if cambio_precio:
                f_desp[15] = f_antes[14] # El actual pasa a anterior
                f_desp[14] = precio_u     # Nuevo precio actual
            
            plan_de_accion.append({
                'nombre_t': nombre_t, 'ean': ean, 'precio_u': precio_u, 'cant_c': cant,
                'fecha': fecha_ticket, 'tienda': tienda, 'es_nuevo': False,
                'cambio_precio': cambio_precio, 'fila_antes': f_antes, 
                'fila_despues': f_desp, 'fila_index': res[0]['fila_index']
            })
        else:
            # 1. Recuperamos la categoría que la IA ya asignó en el JSON
            categoria_ia = item.get('categoria', 'POR DEFINIR').upper()

            # Plan para producto nuevo
            f_nuevo = [""] * 16
            # 2. Usamos la variable categoria_ia en lugar del texto fijo
            f_nuevo[1], f_nuevo[3], f_nuevo[4], f_nuevo[5], f_nuevo[14] = ean, nombre_t.upper(), categoria_ia, tienda, precio_u
            
            plan_de_accion.append({
                'nombre_t': nombre_t, 'ean': ean, 'precio_u': precio_u, 'cant_c': cant,
                'fecha': fecha_ticket, 'tienda': tienda, 'es_nuevo': True,
                'cambio_precio': False, 'fila_antes': [], 'fila_despues': f_nuevo, 'fila_index': -1
            })

    return tienda, fecha_ticket, plan_de_accion

def formatear_fila_auditoria(plan):
    """Formatea la fila limpiando los precios de símbolos antes de convertir a int."""
    f = plan['fila_despues']
    ant = plan['fila_antes'][14] if not plan['es_nuevo'] else "---"
    
    # 🔥 Limpiamos los valores usando tu utilidad limpiar_precio_peso
    p_act_val = limpiar_precio_peso(f[14])
    p_ant_val = limpiar_precio_peso(ant)
    
    # Formateamos con puntos de miles para la vista de tabla
    p_act = f"${int(p_act_val):,}".replace(",", ".") if p_act_val else "$0"
    p_ant = f"${int(p_ant_val):,}".replace(",", ".") if p_ant_val and ant != "---" else "---"
    
    id_show = "[NUEVO]" if plan['es_nuevo'] else f"{f[0]:<7}"
    return f"{id_show} | {str(f[1]):<13} | {str(f[3]):<20} | {str(f[4]):<15} | {str(f[5]):<6} | {p_act:<9} | {p_ant:<9}"