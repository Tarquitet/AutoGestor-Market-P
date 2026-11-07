import requests
import time
import json
from src.config import GEMINI_API_KEY, MODELOS_VISION, MODELOS_TEXTO
from src.utils.image_utils import obtener_pedazos_base64

class LectorIA:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.headers = {"Content-Type": "application/json"}
        # Cargamos las listas separadas
        self.modelos_vision = MODELOS_VISION 
        self.modelos_texto = MODELOS_TEXTO

    def analizar_archivo(self, stream, nombre):
        """PASO 1 (LOS OJOS): Extraer texto de las imágenes."""
        pedazos = obtener_pedazos_base64(stream, nombre)
        
        prompt = """
        Eres un transcriptor de tickets de compra. Tu única tarea es transcribir EXACTAMENTE el texto que ves en las imágenes, línea por línea.
        Si la imagen está dividida, léela en orden.
        Reglas estrictas:
        1. Si ves el nombre de la tienda, escríbelo así: TIENDA: [Nombre]
        2. Transcribe cada producto exactamente (EAN, Nombre, Precio).
        3. Transcribe líneas de cantidades (ej: 2 UN X 7.990) justo debajo de su producto.
        Devuelve solo texto plano, sin JSON ni comentarios.
        """

        print(f"🤖 IA (Visión): Extrayendo texto del ticket ({len(pedazos)} partes)...")
        
        parts = [{"text": prompt.strip()}]
        for img_b64 in pedazos:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_b64}})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.1}
        }
        
        # Iteramos solo sobre los modelos de Visión
        for modelo in self.modelos_vision:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={self.api_key}"
            print(f"   -> Intentando leer con: {modelo}...")
            
            try:
                res = requests.post(url, headers=self.headers, json=payload, timeout=60)
                if res.status_code == 200:
                    texto = res.json()['candidates'][0]['content']['parts'][0]['text']
                    print(f"✅ Éxito leyendo el ticket con {modelo}.")
                    return texto
                elif res.status_code == 429:
                    print(f"   ⚠️ Cuota agotada en {modelo}. Saltando al respaldo...")
                    continue 
                else:
                    print(f"   ⚠️ Error {res.status_code} en {modelo}. Saltando...")
                    continue
            except Exception as e:
                print(f"   ⚠️ Fallo de conexión con {modelo}: {e}. Saltando...")
                continue
                
        print("❌ Todos los modelos de Visión fallaron.")
        return None

    def clasificar_productos_ia(self, datos_json, categorias_existentes):
        """PASO 2 (EL CEREBRO): Clasificar el JSON creado por Python."""
        print("🧠 IA (Texto): Clasificando productos...")
        
        prompt = f"""
        Eres un experto en inventarios. Añade el campo 'categoria' a cada producto en este JSON: {json.dumps(datos_json)}
        Categorías permitidas: {", ".join(categorias_existentes)}
        Si no encaja, crea una coherente en MAYÚSCULAS. Retorna SOLO el JSON estructurado.
        """

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1}
        }
        
        # Iteramos solo sobre los modelos de Texto
        for modelo in self.modelos_texto:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={self.api_key}"
            print(f"   -> Intentando clasificar con: {modelo}...")
            
            try:
                res = requests.post(url, headers=self.headers, json=payload, timeout=60)
                if res.status_code == 200:
                    raw_text = res.json()['candidates'][0]['content']['parts'][0]['text']
                    json_clean = raw_text.replace('```json', '').replace('```', '').strip()
                    datos_finales = json.loads(json_clean)
                    
                    if any(l.get('categoria') != 'POR DEFINIR' for l in datos_finales.get('lineas', [])):
                        print(f"✅ Clasificación exitosa con {modelo}.")
                        return datos_finales
                elif res.status_code == 429:
                    continue
            except:
                continue

        return datos_json