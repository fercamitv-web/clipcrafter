import os
import pickle
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_DIR = os.path.join(os.path.expanduser("~"), ".clipcrafter")
TOKEN_PATH = os.path.join(TOKEN_DIR, "youtube_token.pickle")
CREDENTIALS_PATH = os.path.join(TOKEN_DIR, "client_secret.json")


def has_credentials():
    return os.path.exists(CREDENTIALS_PATH)


def get_credentials_path():
    return CREDENTIALS_PATH


def set_credentials_from_path(path: str):
    os.makedirs(TOKEN_DIR, exist_ok=True)
    with open(path, "rb") as f:
        data = f.read()
    with open(CREDENTIALS_PATH, "wb") as f:
        f.write(data)


def authenticate():
    creds = None

    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if creds:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "wb") as f:
                pickle.dump(creds, f)
            return creds
        if not creds.expired:
            return creds

    if not os.path.exists(CREDENTIALS_PATH):
        return None

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=8080, prompt="consent")

    with open(TOKEN_PATH, "wb") as f:
        pickle.dump(creds, f)
    return creds


def upload_video(video_path: str, title: str = None,
                 description: str = "",
                 tags: list = None,
                 privacy_status: str = "public",
                 on_progress=None) -> str:
    """
    Upload a video to YouTube.
    Returns the video ID if successful, None otherwise.
    """
    creds = authenticate()
    if not creds:
        return None

    youtube = build("youtube", "v3", credentials=creds)

    if not title:
        title = Path(video_path).stem

    if tags is None:
        tags = ["ClipCrafter", "CanalPropra", "clipe", "games"]

    # If privacy_status is an ISO datetime, schedule it; else use as privacy
    is_schedule = privacy_status and "T" in privacy_status
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": "20",
        },
        "status": {
            "privacyStatus": "private" if is_schedule else privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    if is_schedule:
        body["status"]["publishAt"] = privacy_status

    media = MediaFileUpload(video_path, chunksize=1024 * 1024, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    last_progress = 0

    while response is None:
        status, response = request.next_chunk()
        if status and on_progress:
            pct = int(status.progress() * 100)
            if pct != last_progress:
                last_progress = pct
                on_progress(pct)

    video_id = response.get("id")
    return video_id


def delete_video(video_id: str) -> bool:
    creds = authenticate()
    if not creds:
        return False
    youtube = build("youtube", "v3", credentials=creds)
    try:
        youtube.videos().delete(id=video_id).execute()
        return True
    except Exception as e:
        print(f"Delete error: {e}")
        return False


def generate_credentials_guide() -> str:
    return """COMO CRIAR SUAS CREDENCIAIS DO YOUTUBE:

1. Acesse https://console.cloud.google.com/
2. Crie um projeto novo (ou selecione existente)
3. Vai em "APIs e Servicos" > "Biblioteca"
4. Pesquise "YouTube Data API v3" e ative
5. Va em "Tela de consentimento OAuth"
   - Tipo: Externo
   - Preencha nome, email, escopo: .../auth/youtube.upload
   - Adicione seu email como usuario de teste
6. Va em "Credenciais" > "Criar Credenciais" > "ID do cliente OAuth"
   - Tipo: Aplicativo de desktop
   - Baixe o JSON
7. Salve o arquivo como client_secret.json em:
   C:\\Users\\ferca\\.clipcrafter\\client_secret.json
"""
