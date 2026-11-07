import difflib
from src.utils.search_engine import buscar_top_coincidencias, limpiar_texto

# 📘 NIVEL 2: Tu diccionario personal
DICCIONARIO_CATEGORIAS = {
    "LÁCTEOS Y HUEVOS": ["LECHE", "LCH", "QUESO", "YOGURT", "YOG", "HUEVO", "MANTEQUILLA", "MARGAR", "CUAJADA", "CREMA", "KUMIS", "YOG"],
    "PROTEÍNAS Y ENLATADOS": ["JAM", "POLLO", "CARNE", "CERDO", "PESCADO", "ATUN", "JAMON", "JAM", "SALCHICHA", "CHORIZO", "NUGGET", "ALITA", "MUSLO"],
    "DULCES, SNACKS Y PANADERÍA": ["CALADOS", "PAN ", "GALLETA", "BOCADILLO", "CHOCOLATE", "WAFER", "TURRON", "MOGOLLA", "CALADOS", "HOJUELAS"],"BEBIDAS": ["JUGO", "GASEOSA", "CERVEZA", "VINO", "TE ", "CAFE", "BEBIDA", "NECTAR", "MATE", "AGUA"],
    "ASEO Y HOGAR": ["JABON", "DETERGENTE", "SUAVIZANTE", "BLANQUEADOR", "ESCOBA", "TRAPERO", "CREMA DENTAL", "COLGATE", "PAPEL HIGIENICO", "SHAMPOO", "DESODORANTE", "TOALLA", "LIMPIADOR", "LAVALOZA", "AGUA ROSAS"],
    "FRUTAS Y VERDURAS": ["MANZANA", "PERA", "BANANO", "TOMATE", "CEBOLLA", "AJO", "PAPA", "ZANAHORIA", "LECHUGA", "LIMON", "NARANJA", "MANDARINA", "FRESA", "MORA", "PLATANO", "CILANTRO", "YUCA", "MEZCLA VEG", "CIRUE", "CRIO", "R12"],
    "GRANOS Y PASTAS": ["HOJUELAS","ARROZ", "FRIJOL", "LENTEJA", "GARBANZO", "PASTA", "ESPAGUETI", "FIDEOS", "HARINA", "AVENA", "SEMILLA", "CHIA"],
    "SALSAS Y CONDIMENTOS": ["SALSA", "MAYONESA", "MOSTAZA", "KETCHUP", "SAL ", "PIMIENTA", "COLOR", "CALDO", "ACEITE", "VINAGRE", "CONDIMENTO"]
}

def clasificar_json_completo(datos_brutos, filas_excel):
    """Clasifica el JSON usando historial, keywords exactas y búsqueda difusa para errores tipográficos."""
    datos_finales = datos_brutos.copy()
    
    for item in datos_finales.get("lineas", []):
        nombre = item.get("nombre_ticket", "")
        ean = item.get("ean", "")
        
        # 🧠 NIVEL 1: Memoria Histórica
        coincidencias = buscar_top_coincidencias({'nombre_ticket': nombre, 'ean': ean}, filas_excel, top_n=1)
        if coincidencias and coincidencias[0]['score'] >= 85:
            categoria_excel = coincidencias[0]['categoria'].strip().upper()
            if categoria_excel and categoria_excel != "POR DEFINIR":
                item["categoria"] = categoria_excel
                continue
        
        nombre_limpio = limpiar_texto(nombre).replace('_', '')
        palabras_ticket = nombre_limpio.split()
        categoria_encontrada = False
        
        # 📚 NIVEL 2.1: Búsqueda Exacta
        for cat, keywords in DICCIONARIO_CATEGORIAS.items():
            for kw in keywords:
                if kw in nombre_limpio:
                    item["categoria"] = cat
                    categoria_encontrada = True
                    break
            if categoria_encontrada: break
                
        if categoria_encontrada: continue

        # 🕵️ NIVEL 2.2: Búsqueda Difusa
        for cat, keywords in DICCIONARIO_CATEGORIAS.items():
            for palabra in palabras_ticket:
                if len(palabra) >= 5: 
                    similares = difflib.get_close_matches(palabra, keywords, n=1, cutoff=0.70)
                    if similares:
                        item["categoria"] = cat
                        categoria_encontrada = True
                        break
            if categoria_encontrada: break

        if categoria_encontrada: continue
            
        # 🃏 NIVEL 3: El Comodín
        item["categoria"] = "POR DEFINIR"
        
    return datos_finales