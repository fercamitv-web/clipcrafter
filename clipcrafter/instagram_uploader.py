"""Instagram Reels uploader via Meta Graph API.

Publishing uses the two-step container flow:
  1. POST /{ig-user-id}/media       -> create REELS container (video_url must be public)
  2. Poll GET /{ig-container-id}    -> wait until status_code == FINISHED
  3. POST /{ig-user-id}/media_publish -> publish the container

The video_url is served from this GitHub repo's raw URLs, since Meta cURLs the
file from a publicly accessible server.

Requirements (see generate_credentials_guide):
  - Instagram Business account linked to a Facebook Page
  - Meta app with instagram_business_basic + instagram_business_content_publish
  - Long-lived user access token + the Instagram Business account ID
"""
import os, json, time, urllib.parse, urllib.request
from pathlib import Path

TOKEN_DIR = os.path.join(os.path.expanduser("~"), ".clipcrafter")
TOKEN_PATH = os.path.join(TOKEN_DIR, "instagram_token.json")

GRAPH = "https://graph.facebook.com"
API_VERSION = "v25.0"

REPO_OWNER = "fercamitv-web"
REPO_NAME = "clipcrafter"
REPO_BRANCH = "master"

DEFAULT_CAPTION = (
    "Melhores momentos de gameplay! 🎮\n\n"
    "Siga @canalpropra para mais clipes INSANOS!\n\n"
    "#gameplay #clipe #gaming #shorts"
)


def has_credentials() -> bool:
    return os.environ.get("IG_ACCESS_TOKEN") is not None or os.path.exists(TOKEN_PATH)


def _load_token() -> dict:
    tok = os.environ.get("IG_ACCESS_TOKEN")
    uid = os.environ.get("IG_USER_ID")
    if tok and uid:
        return {"access_token": tok, "ig_user_id": uid}
    if os.path.exists(TOKEN_PATH):
        return json.loads(open(TOKEN_PATH, "r").read())
    return {}


def save_token(access_token: str, ig_user_id: str):
    os.makedirs(TOKEN_DIR, exist_ok=True)
    data = {"access_token": access_token, "ig_user_id": ig_user_id}
    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Token salvo em {TOKEN_PATH}")


def _api_call(method: str, path: str, params: dict, data: dict = None,
              timeout: int = 60) -> dict:
    url = f"{GRAPH}/{API_VERSION}/{path}"
    params = {k: v for k, v in params.items() if v is not None}
    if method == "GET" and params:
        url += "?" + urllib.parse.urlencode(params)
    body = None
    if data:
        body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        print(f"API error {e.code}: {raw[:400]}")
        try:
            return json.loads(raw)
        except Exception:
            return {"error": {"message": raw, "code": e.code}}


def _resolve_video_url(clip_file: str) -> str:
    """Return a public URL for the clip. Uses this repo's raw GitHub URLs."""
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{REPO_BRANCH}/clipcrafter/scheduled_uploads/clips/{clip_file}"
    return url


def _build_caption(title: str, description: str = "", tags: list = None) -> str:
    parts = []
    if title:
        parts.append(title[:150])
    if description:
        desc = description.split("\n\n")[0][:500]
        parts.append(desc)
    if tags:
        ht = " ".join(f"#{t.replace(' ', '')}" for t in tags[:8])
        parts.append(ht)
    caption = "\n\n".join(p for p in parts if p)
    if not caption:
        caption = DEFAULT_CAPTION
    return caption[:2200]


def upload_video(video_path: str, title: str = None,
                 description: str = "", tags: list = None,
                 share_to_feed: bool = True, privacy_status: str = "public") -> str:
    """
    Upload a Reel to Instagram.
    video_path is used to derive the public video_url (from this repo's raw URLs).
    Returns the Instagram media ID if successful, None otherwise.
    """
    token = _load_token()
    if not token or "access_token" not in token or "ig_user_id" not in token:
        print("No Instagram credentials. Set IG_ACCESS_TOKEN/IG_USER_ID or run setup_token().")
        return None

    access_token = token["access_token"]
    ig_user_id = token["ig_user_id"]
    clip_file = os.path.basename(video_path)
    video_url = _resolve_video_url(clip_file)
    caption = _build_caption(title, description, tags)

    # Step 1: create the REELS container
    print(f"  Creating container for {clip_file}...", end=" ", flush=True)
    result = _api_call(
        "POST", f"{ig_user_id}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
            "access_token": access_token,
        },
    )
    if "error" in result:
        print(f"FAIL: {result['error'].get('message', result['error'])}")
        return None
    container_id = result.get("id")
    print(f"OK container={container_id}")

    # Step 2: poll until FINISHED
    status = None
    for _ in range(12):  # up to ~2 minutes
        time.sleep(10)
        st = _api_call("GET", f"{container_id}",
                       params={"fields": "status_code", "access_token": access_token})
        status = st.get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            print(f"  Container status: {status}")
            return None
        print(f"  status={status}...", end=" ", flush=True)
    if status != "FINISHED":
        print(f"  FAIL: container did not finish (last status {status})")
        return None

    # Step 3: publish
    print(f"  Publishing...", end=" ", flush=True)
    pub = _api_call(
        "POST", f"{ig_user_id}/media_publish",
        params={"creation_id": container_id, "access_token": access_token},
    )
    if "error" in pub:
        print(f"FAIL: {pub['error'].get('message', pub['error'])}")
        return None
    media_id = pub.get("id")
    print(f"OK media_id={media_id}")
    return media_id


def setup_token():
    """Interactively save the long-lived user access token + IG business user ID."""
    print("Cole o access token de longa duracao:")
    tok = input().strip()
    print("Cole o ID da conta profissional do Instagram (ig-user-id):")
    uid = input().strip()
    if tok and uid:
        save_token(tok, uid)
    else:
        print("Token e/ou ID vazios, nada salvo.")


def generate_credentials_guide() -> str:
    return """COMO CONFIGURAR O INSTAGRAM (META GRAPH API):

PREREQUISITOS OBRIGATORIOS:
  1. Conta Instagram PROFISSIONAL (Business) - a API nao publica em conta pessoal/creator
     - Instagram > Configuracoes > Tipo de conta > Mudar para conta profissional (Business)
  2. Pagina no Facebook conectada a essa conta do Instagram
     - Instagram > Configuracoes > Central de contas > Vincular conta do Facebook
  3. App no Meta for Developers:
     - Acesse https://developers.facebook.com > Meus apps > Criar app (tipo Business)
     - Adicione o produto "Instagram Graph API"

PASSOS:
  4. No app, adicione as permissoes:
     - instagram_business_basic
     - instagram_business_content_publish
     - pages_read_engagement
  5. App Review (obrigatorio para publicar em contas reais):
     - Cada permissao exige submission com screencast (2-4 semanas)
     - Sem aprovacao, so funciona com usuarios de teste
  6. Pegue o token de usuario:
     - Acesse https://developers.facebook.com/tools/explorer
     - Selecione o app e peca as permissoes acima
     - Troque pelo token de longa duracao (60 dias)
  7. Descubra o ig-user-id:
     - GET https://graph.facebook.com/v25.0/me/accounts?access_token=TOKEN
     - Pegue o ID da Page, depois:
       GET https://graph.facebook.com/v25.0/{page_id}?fields=instagram_business_account
  8. Salve:
     python -c "from instagram_uploader import setup_token; setup_token()"

PARA CI (GitHub Actions):
  - Adicione os secrets IG_ACCESS_TOKEN e IG_USER_ID
  - Nota: o video_url usado e o raw do GitHub, que o Meta precisa conseguir acessar
  - Limite: 100 posts/24h por conta, videos Reels 5-90s e 9:16 (seus clipes ja sao)
"""


if __name__ == "__main__":
    setup_token()
