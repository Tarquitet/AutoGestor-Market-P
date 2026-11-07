import difflib
import re

def limpiar_texto(texto):
    """Quita tildes, comas y deja todo en mayúsculas para comparar limpio."""
    if not texto:
        return ""
    # Mantenemos solo letras, números y espacios
    limpio = re.sub(r'[^\w\s]', '', str(texto).upper().strip())
    return limpio

def calcular_similitud(nombre_ticket, nombre_excel, abrev_excel, ean_ticket, ean_excel):
    """El núcleo del sabueso. Calcula del 0 al 100 qué tan parecidos son."""
    
    # 0. LÓGICA DE PESO VARIABLE (EANs que empiezan por 29 o 20)
    # Si el código empieza por estos números, ignoramos los últimos 5 dígitos (el peso/precio)
    ean_t_short = str(ean_ticket)[:8] if ean_ticket and str(ean_ticket).startswith(('29', '20')) else str(ean_ticket)
    ean_e_short = str(ean_excel)[:8] if ean_excel and str(ean_excel).startswith(('29', '20')) else str(ean_excel)
    
    if ean_t_short == ean_e_short and len(ean_t_short) >= 8:
        return 100

    # 1. MATCH PERFECTO: EAN idéntico (Ignorando ceros a la izquierda)
    ean_t_clean = str(ean_ticket).strip().lstrip('0') if ean_ticket else ""
    ean_e_clean = str(ean_excel).strip().lstrip('0') if ean_excel else ""
    if ean_t_clean and ean_e_clean and ean_t_clean == ean_e_clean:
        return 100
    
    # 2. MATCH PERFECTO: Abreviación de la Columna G
    if abrev_excel and str(nombre_ticket).upper().strip() == str(abrev_excel).upper().strip():
        return 100
        
    # 3. ANÁLISIS DE TEXTO (El motor de búsqueda sucio)
    t_clean = limpiar_texto(nombre_ticket)
    e_clean = limpiar_texto(nombre_excel)
    
    if not t_clean or not e_clean:
        return 0
        
    score = 0
    
    # 3.1. Contenido directo: Si uno está DENTRO del otro (Ej: "CR COLGATE A" en "CR COLGATE A CREMA")
    if t_clean in e_clean or e_clean in t_clean:
        score = max(score, 90)
        
    # 3.2. Coincidencia por palabras (Si tienen las mismas palabras aunque estén en desorden)
    palabras_t = t_clean.split()
    if palabras_t:
        # Solo contamos palabras de más de 2 letras para ignorar "de", "la", "el"
        coincidencias = sum(1 for p in palabras_t if len(p) > 2 and p in e_clean)
        if len(palabras_t) > 0:
            porcentaje_palabras = int((coincidencias / len(palabras_t)) * 100)
            if porcentaje_palabras > 50:
                score = max(score, porcentaje_palabras)
            
    # 3.3. Similitud clásica de caracteres (difflib)
    diff_score = int(difflib.SequenceMatcher(None, t_clean, e_clean).ratio() * 100)
    score = max(score, diff_score)
    
    return score

def buscar_top_coincidencias(item_ticket, filas_excel, top_n=3):
    """
    Recibe un item del JSON y TODA la tabla de Excel. 
    Devuelve los mejores 3 resultados con su % de coincidencia.
    """
    nombre_t = item_ticket.get('nombre_ticket', '')
    ean_t = item_ticket.get('ean', '')
    
    resultados = []
    
    # Iteramos toda la matriz del Excel
    for i, fila in enumerate(filas_excel):
        if i == 0:
            continue # Saltamos el encabezado principal
        
        # Nos aseguramos de que la fila tenga datos y no sea un subtítulo de categoría (Ej: 1.0)
        id_str = str(fila[0]).strip() if len(fila) > 0 else ""
        if not id_str or ".0" in id_str or "ENCABEZADO" in str(fila[2]).upper():
            continue
            
        # Rellenamos columnas vacías por si la fila está incompleta en el Excel
        while len(fila) < 8:
            fila.append("")
            
        ean_e = fila[1]
        nom_c = fila[2] # Código ID (Col C)
        nom_d = fila[3] # Nombre Largo (Col D)
        categoria = fila[4]
        abrev_e = fila[6] if len(fila) > 6 else ""
        
        # Extraer el precio limpio de la Columna H
        p_act_str = "".join(filter(str.isdigit, str(fila[7]))) if len(fila) > 7 else ""
        precio_e = int(p_act_str) if p_act_str else 0
        
        # Calculamos la similitud comparando con el Nombre Largo y el Código ID
        score_nombre_largo = calcular_similitud(nombre_t, nom_d, abrev_e, ean_t, ean_e)
        score_codigo_id = calcular_similitud(nombre_t, nom_c, abrev_e, ean_t, ean_e)
        
        # Nos quedamos con el puntaje más alto de los dos
        mejor_score = max(score_nombre_largo, score_codigo_id)
        
        # Solo guardamos cosas que tengan al menos un 25% de similitud (para no mostrarte basura pura)
        if mejor_score >= 25:
            resultados.append({
                'fila_index': i + 1, # +1 porque en Google Sheets la fila 1 es el índice 0 de la lista
                'score': mejor_score,
                'nombre_excel': nom_d,
                'precio_actual': precio_e,
                'categoria': categoria,
                'ean_excel': ean_e,
                'abrev': abrev_e
            })
            
    # Ordenamos de mayor a menor porcentaje
    resultados.sort(key=lambda x: x['score'], reverse=True)
    
    # Devolvemos solo el Top 3
    return resultados[:top_n]