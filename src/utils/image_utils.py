import base64
import io
from PIL import Image
import pillow_heif
from pdf2image import convert_from_bytes

def obtener_pedazos_base64(archivo_stream, nombre_archivo, max_alto_pieza=800):
    """Convierte PDF, HEIC o JPG a pedazos legibles para la IA."""
    ext = nombre_archivo.lower().split('.')[-1]
    archivo_stream.seek(0)
    archivo_bytes = archivo_stream.read()
    
    imagenes_pil = []
    try:
        if ext == 'pdf':
            imagenes_pil = convert_from_bytes(archivo_bytes)
        elif ext == 'heic':
            heif = pillow_heif.read_heif(io.BytesIO(archivo_bytes))
            imagenes_pil = [Image.frombytes(heif.mode, heif.size, heif.data, "raw")]
        else:
            imagenes_pil = [Image.open(io.BytesIO(archivo_bytes))]

        pedazos_finales = []
        for img in imagenes_pil:
            img = img.convert('RGB')
            ancho, alto = img.size
            
            # 🔥 LÓGICA DE CORTE VERTICAL
            # Si la imagen es más alta que nuestro límite, la picamos en trozos
            for y in range(0, alto, max_alto_pieza):
                # Definimos el cuadro de corte (izquierda, arriba, derecha, abajo)
                caja = (0, y, ancho, min(y + max_alto_pieza, alto))
                trozo = img.crop(caja)
                
                # Si el trozo sigue siendo muy ancho, lo ajustamos proporcionalmente
                if trozo.width > 800:
                    ratio = 800 / float(trozo.width)
                    nuevo_alto = int(float(trozo.height) * ratio)
                    trozo = trozo.resize((800, nuevo_alto), Image.Resampling.LANCZOS)
                
                # Convertimos el trozo a Base64
                buf = io.BytesIO()
                trozo.save(buf, format="JPEG", quality=85)
                pedazos_finales.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
                
        return pedazos_finales
    except Exception as e:
        print(f"❌ Error al picar la imagen: {e}")
        return []