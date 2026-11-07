import json
import os
import re

def extraer_id(texto):
    if not texto or "/" not in str(texto):
        return texto
    match = re.search(r'[-\w]{25,}', str(texto))
    return match.group(0) if match else texto

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(BASE_DIR, 'settings.json')

with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
    conf = json.load(f)

# --- VARIABLES PARA LOS IMPORTS ---
# Esta es la ruta al 'client_secrets.json'
CREDENTIALS_PATH = os.path.join(BASE_DIR, conf['rutas']['credenciales'])
JSON_TEMP_DIR = os.path.join(BASE_DIR, conf['rutas']['json_temp'])

# Drive
ID_FOTOS_PENDIENTES = extraer_id(conf['google_drive_links']['fotos_pendientes'])
ID_FOTOS_PROCESADOS = extraer_id(conf['google_drive_links']['fotos_procesados'])

# Sheets
SPREADSHEET_ID = extraer_id(conf['google_sheets']['spreadsheet_id'])
HISTORICO_NAME = conf['google_sheets']['hoja_historico']

# IA
GEMINI_API_KEY = conf['ia_config']['gemini_api_key']

# Lista de modelos que harán de "OJOS" (Lectura de imágenes)
MODELOS_VISION = [conf['ia_config']['vision']['primario']] + conf['ia_config']['vision']['respaldos']

# Lista de modelos que harán de "CEREBRO" (Clasificación de texto)
MODELOS_TEXTO = [conf['ia_config']['texto']['primario']] + conf['ia_config']['texto']['respaldos']

#IA
#HF_TOKEN = conf['ia_config']['hf_token']
# Creamos una lista combinada: el primario primero, luego los fallbacks
#MODELOS_IA = [conf['ia_config']['model_primary']] + conf['ia_config']['model_fallbacks']