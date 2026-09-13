"""Facebook Page video uploader via Meta Graph API (stdlib only).

Publica o clipe como vídeo na Página do Facebook (mesmo esquema dos outros
uploaders: upload_video(...) -> id ou None).

Requisitos (ver generate_credentials_guide):
  - Página do Facebook (a mesma ligada ao Instagram Business, se houver)
  - Token da PÁGINA (não expira quando gerado de um user token longa duração)
  - App Meta com pages_manage_posts + pages_read_engagement (+ pages_show_list)

Diferente do Instagram (que baixa o vídeo de uma URL pública), aqui o arquivo
sobe direto (multipart), então funciona mesmo sem o mp4 commitado.
"""
import os
import json
import mimetypes
import urllib.parse
import urllib.request
import uuid

TOKEN_DIR = os.path.join(os.path.expanduser("~"), ".clipcrafter")
TOKEN_PATH = os.path.join(TOKEN_DIR, "facebook_token.json")

GRAPH = "https://graph.facebook.com"
API_VERSION = "v25.0"


def has_credentials() -> bool:
    return (os.environ.get("FB_ACCESS_TOKEN") is not None
            or os.path.exists(TOKEN_PATH))


def _load_token() -> dict:
    tok = os.environ.get("FB_ACCESS_TOKEN")
    pid = os.environ.get("FB_PAGE_ID")
    if tok and pid:
        return {"access_token": tok, "page_id": pid}
    if os.path.exists(TOKEN_PATH):
        try:
            return json.loads(open(TOKEN_PATH, "r").read())
        except Exception:
            return {}
    return {}


def save_token(access_token: str, page_id: str):
    os.makedirs(TOKEN_DIR, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        json.dump({"access_token": access_token, "page_id": page_id}, f, indent=2)
    print(f"Token salvo em {TOKEN_PATH}")


def _post_multipart(path: str, fields: dict, file_field: str,
                    file_path: str, access_token: str, timeout: int = 300) -> dict:
    boundary = uuid.uuid4().hex
    chunks = []
    for k, v in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        chunks.append(f"{v}\r\n".encode())
    fname = os.path.basename(file_path)
    ctype = mimetypes.guess_type(fname)[0] or "video/mp4"
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{fname}"\r\n'.encode())
    chunks.append(f"Content-Type: {ctype}\r\n\r\n".encode())
    with open(file_path, "rb") as f:
        chunks.append(f.read())
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    url = f"{GRAPH}/{API_VERSION}/{path}?access_token={urllib.parse.quote(access_token)}"
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        print(f"API error {e.code}: {raw[:300]}")
        try:
            return json.loads(raw)
        except Exception:
            return {"error": {"message": raw, "code": e.code}}


def _build_description(title: str, description: str = "", tags: list = None) -> str:
    parts = []
    if title:
        parts.append(title[:150])
    if description:
        parts.append(description.split("\n\n")[0][:800])
    if tags:
        parts.append(" ".join(f"#{t.replace(' ', '')}" for t in tags[:8]))
    text = "\n\n".join(p for p in parts if p)
    return text[:2000]


def upload_video(video_path: str, title: str = None,
                 description: str = "", tags: list = None,
                 privacy_status: str = "public") -> str:
    """Posta o vídeo na Página do Facebook. Retorna o video ID ou None."""
    token = _load_token()
    if not token or "access_token" not in token or "page_id" not in token:
        print("Sem credenciais Facebook. Set FB_ACCESS_TOKEN/FB_PAGE_ID ou rode setup_token().")
        return None
    if not os.path.exists(video_path):
        print(f"Arquivo não encontrado: {video_path}")
        return None

    desc = _build_description(title or "", description, tags)
    print(f"  Enviando {os.path.basename(video_path)} ({os.path.getsize(video_path)//1024} KB)...",
          end=" ", flush=True)
    result = _post_multipart(
        f"{token['page_id']}/videos",
        fields={"description": desc},
        file_field="file",
        file_path=video_path,
        access_token=token["access_token"],
    )
    if "error" in result:
        err = result["error"]
        print(f"FAIL: {err.get('message', err)}")
        return None
    vid = result.get("id")
    print(f"OK id={vid}")
    return vid


def setup_token():
    """Salva interativamente o Page token + Page ID."""
    print("Cole o PAGE access token (longa duração):")
    tok = input().strip()
    print("Cole o ID da Página (page_id):")
    pid = input().strip()
    if tok and pid:
        save_token(tok, pid)
    else:
        print("Token e/ou ID vazios, nada salvo.")


def generate_credentials_guide() -> str:
    return """COMO CONFIGURAR O FACEBOOK (META GRAPH API):

PRÉ-REQUISITO:
  1. Uma Página do Facebook (pode ser a mesma ligada ao Instagram Business)

PASSOS (token que NÃO expira):
  2. developers.facebook.com > seu app (tipo Business) > Graph API Explorer
  3. Gere um USER token com: pages_manage_posts, pages_read_engagement,
     pages_show_list (+ instagram_* se for usar o IG junto)
  4. Troque por longa duração (60 dias):
     GET /oauth/access_token?grant_type=fb_exchange_token&...
  5. Liste as páginas: GET /me/accounts -> pegue access_token DA PÁGINA
     (page token gerado assim NÃO expira) + o page id
  6. Salve local:  python -c "from facebook_uploader import setup_token; setup_token()"
  7. Para CI: secrets FB_ACCESS_TOKEN (= page token) e FB_PAGE_ID

NOTAS:
  - Vídeo sobe direto do arquivo (não precisa estar commitado)
  - Limite generoso da API para vídeos em Páginas; 9:16 <90s distribui como Reels
"""


if __name__ == "__main__":
    setup_token()
