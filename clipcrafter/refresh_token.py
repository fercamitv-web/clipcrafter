"""Generate new YouTube OAuth token"""
import os, json, base64, pickle
from pathlib import Path

SECRET_FILE = Path(__file__).parent / "client_secret.json"

if not SECRET_FILE.exists():
    print("=" * 60)
    print("PRECISA DO ARQUIVO client_secret.json")
    print("=" * 60)
    print()
    print("1. Acesse https://console.cloud.google.com/apis/credentials")
    print("2. Crie um credential do tipo 'OAuth 2.0 Client IDs'")
    print("3. Em 'Application type', escolha 'Desktop app'")
    print("4. Baixe o JSON e salve como 'client_secret.json'")
    print("   na pasta:", SECRET_FILE.parent)
    print()
    input("Pressione Enter quando tiver salvo o arquivo...")

if not SECRET_FILE.exists():
    print("Arquivo nao encontrado. Abortando.")
    exit(1)

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]

flow = InstalledAppFlow.from_client_secrets_file(str(SECRET_FILE), SCOPES)
creds = flow.run_local_server(port=0, open_browser=True)

token_bytes = pickle.dumps(creds)
token_b64 = base64.b64encode(token_bytes).decode("utf-8")

print("\n" + "=" * 60)
print("NOVO TOKEN GERADO COM SUCESSO!")
print("=" * 60)
print()
print("Copie o valor abaixo e atualize o GitHub Secret YT_TOKEN_PICKLE:")
print()
print(token_b64)
print()

# Also save locally
local_file = Path(__file__).parent / "yt_token_pickle.b64"
local_file.write_text(token_b64)
print(f"(Tambem salvo em: {local_file})")
input("Pressione Enter para sair...")
