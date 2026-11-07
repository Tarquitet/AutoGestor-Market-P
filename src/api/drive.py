import io
import json
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from src.config import CREDENTIALS_PATH

class GoogleDriveClient:
    def __init__(self):
        # Definimos los permisos: Acceso total a Drive y Sheets
        self.scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        self.creds = self._obtener_credenciales()
        self.service = build('drive', 'v3', credentials=self.creds)

    def crear_carpeta(self, nombre, carpeta_padre_id):
        """Crea una carpeta en Drive y retorna su ID."""
        meta = {
            'name': nombre,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [carpeta_padre_id]
        }
        res = self.service.files().create(body=meta, fields='id').execute()
        return res.get('id')

    def buscar_por_nombre(self, nombre, folder_id):
        """Busca un archivo por nombre exacto en una carpeta."""
        q = f"name = '{nombre}' and '{folder_id}' in parents and trashed = false"
        res = self.service.files().list(q=q, fields="files(id, name)").execute().get('files', [])
        return res[0] if res else None

    def _obtener_credenciales(self):
        creds = None
        # El archivo token.json guarda tu sesión iniciada
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.scopes)
        
        # Si no hay token o expiró, pedimos login
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Usamos la variable que viene del settings.json
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, self.scopes)
                creds = flow.run_local_server(port=0)
            
            # Guardamos el token para la próxima vez
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return creds

    def subir_texto(self, nombre, contenido_texto, folder_id):
        """Sube el texto bruto asegurando que el stream sea válido."""
        import io
        from googleapiclient.http import MediaIoBaseUpload

        file_metadata = {
            'name': nombre,
            'parents': [folder_id],
            'mimeType': 'text/plain'
        }
        
        # Convertimos a bytes explícitamente para evitar problemas de socket
        bio = io.BytesIO(contenido_texto.encode('utf-8'))
        media = MediaIoBaseUpload(bio, mimetype='text/plain', resumable=False)
        
        try:
            return self.service.files().create(
                body=file_metadata, 
                media_body=media, 
                fields='id'
            ).execute()
        except Exception as e:
            print(f"⚠️ Error subiendo texto: {e}. Reintentando...")
            # Un pequeño reintento por si fue un parpadeo de red
            return self.service.files().create(
                body=file_metadata, 
                media_body=media, 
                fields='id'
            ).execute()

    def obtener_o_crear_carpeta(self, nombre, padre_id):
        """Busca una carpeta por nombre. Si no existe, la crea."""
        existente = self.buscar_por_nombre(nombre, padre_id)
        if existente:
            return existente['id']
        return self.crear_carpeta(nombre, padre_id)

    def listar_todo(self, folder_id):
        """Lista archivos y carpetas para el flujo de retorno inteligente."""
        q = f"'{folder_id}' in parents and trashed = false"
        # Pedimos el mimeType para saber qué es carpeta y qué es archivo
        return self.service.files().list(
            q=q, 
            fields="files(id, name, mimeType)"
        ).execute().get('files', [])

    def listar_internos(self, folder_id):
        """Lista el contenido de una subcarpeta específica."""
        return self.listar_todo(folder_id)

    def descargar(self, file_id):
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        return fh

    def subir_json(self, nombre, datos, folder_id):
        file_metadata = {'name': nombre, 'parents': [folder_id], 'mimeType': 'application/json'}
        media = MediaIoBaseUpload(
            io.BytesIO(json.dumps(datos, indent=4, ensure_ascii=False).encode('utf-8')), 
            mimetype='application/json'
        )
        return self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()

    def mover(self, file_id, folder_destino_id):
        file = self.service.files().get(fileId=file_id, fields='parents').execute()
        prev = ",".join(file.get('parents'))
        self.service.files().update(fileId=file_id, addParents=folder_destino_id, removeParents=prev).execute()