# --- src/core/handler.py ---
import time
import msvcrt
import sys
from src.core.auditor import generar_plan_auditoria, formatear_fila_auditoria
from src.core.maintenance import ejecutar_mantenimiento
from src.api.sheets import SheetsClient

def input_con_timeout(prompt, timeout_sec=15, default='s'):
    """Espera una respuesta del usuario. Si se acaba el tiempo, devuelve la respuesta por defecto."""
    print(prompt, end='', flush=True)
    start_time = time.time()
    respuesta = ""
    
    while (time.time() - start_time) < timeout_sec:
        if msvcrt.kbhit(): # Si el usuario presiona una tecla
            char = msvcrt.getwche() # Lee la tecla y la muestra en pantalla
            
            if char in ('\r', '\n'): # Si presiona Enter
                print()
                return respuesta.strip().lower() if respuesta.strip() else default
            elif char == '\x08': # Si presiona Backspace (Borrar)
                respuesta = respuesta[:-1]
                print(' \x08', end='', flush=True)
            else:
                respuesta += char
                
        time.sleep(0.05) # Pequeña pausa para no saturar la CPU
        
    print(f"\n⏳ Tiempo agotado ({timeout_sec}s). Auto-confirmando: '{default}'")
    return default

def validar_datos_finales(datos):
    """Comprueba que el JSON tenga la estructura correcta antes de enviarlo al Excel."""
    if not datos or "lineas" not in datos or not datos["lineas"]:
        print("⚠️ ERROR: El JSON está vacío o no tiene productos detectados.")
        return False
        
    for linea in datos["lineas"]:
        if "nombre_ticket" not in linea or "precio_unitario" not in linea or "ean" not in linea:
            print(f"⚠️ ERROR: Estructura corrupta en un producto: {linea}")
            return False
            
    return True

def gestionar_auditoria_interactiva(datos_clasificados): 
    # 🛡️ SANITY CHECK: Validamos antes de mostrar la tabla
    if not validar_datos_finales(datos_clasificados):
        print("🛑 Se abortó el registro de este ticket para proteger tu Excel.")
        return False
        
    sheets = SheetsClient()
    tienda, fecha, plan_de_accion = generar_plan_auditoria(datos_clasificados, sheets)
    
    print("\n" + "="*125)
    print(f"📋 RESUMEN DE COMPRA - {tienda} ({fecha})")
    print("-" * 125)
    print(f"ID      | EAN           | NOMBRE PRODUCTO      | CATEGORÍA       | TIENDA | ACTUAL    | ANTERIOR")
    for plan in plan_de_accion:
        print(formatear_fila_auditoria(plan))
    print("="*125)

    # 🔥 AQUI ESTÁ LA MAGIA DEL TIMEOUT (15 Segundos)
    mensaje = "\n¿Proceder con el registro? (s: Sí / n: Saltar / q: Salir) [Auto 's' en 15s]: "
    opcion = input_con_timeout(mensaje, timeout_sec=15, default='s')

    if opcion == 'q':
        return "QUIT"
    if opcion != 's':
        return False

    # Registro 1x1
    for i, plan in enumerate(plan_de_accion, 1):
        cat_final = plan['fila_despues'][4]
        if not plan['es_nuevo']:
            sheets.actualizar_fila_exacta(
                plan['fila_index'], plan['nombre_t'], plan['ean'], 
                plan['precio_u'], plan['fila_antes'], fecha, plan['cant_c'],
                categoria_nueva=cat_final
            )
        else:
            sheets.registrar_nuevo(
                plan['nombre_t'], plan['ean'], plan['precio_u'], 
                tienda, cat_final, fecha, plan['cant_c']
            )

    ejecutar_mantenimiento()
    return True