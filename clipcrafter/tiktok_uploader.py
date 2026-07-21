"""TikTok upload via Playwright browser automation."""
import os, json, time, base64
from pathlib import Path

TOKEN_DIR = os.path.join(os.path.expanduser("~"), ".clipcrafter")
COOKIES_PATH = os.path.join(TOKEN_DIR, "tiktok_cookies.json")

def save_cookies(cookies):
    os.makedirs(TOKEN_DIR, exist_ok=True)
    with open(COOKIES_PATH, "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"Cookies salvas: {len(cookies)} cookies -> {COOKIES_PATH}")

def load_cookies():
    if os.path.exists(COOKIES_PATH):
        with open(COOKIES_PATH) as f:
            return json.load(f)
    return None

def login_interactive():
    """Open browser for manual TikTok login, then save cookies."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.goto("https://www.tiktok.com/login")
        print("Faça login no TikTok que abriu no navegador.")
        print("Após logar, volte aqui e aperte ENTER...")
        input()
        cookies = ctx.cookies()
        save_cookies(cookies)
        print("Login salvo! Agora é possível fazer upload automatizado.")
        ctx.close()
        browser.close()

def upload_video(video_path: str, title: str = None,
                 description: str = "", hashtags: list = None,
                 headless: bool = True) -> str:
    cookies = load_cookies()
    if not cookies:
        raise Exception("No TikTok cookies. Execute 'login_interactive()' first.")

    if not title:
        title = Path(video_path).stem
    if hashtags is None:
        hashtags = ["ClipCrafter", "games"]

    # CI: try cookies from env
    ci_cookies_b64 = os.environ.get("TT_COOKIES")
    if ci_cookies_b64:
        cookies = json.loads(base64.b64decode(ci_cookies_b64))

    from playwright.sync_api import sync_playwright

    video_id = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, channel="chrome")
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        try:
            # Navigate to upload page
            page.goto("https://www.tiktok.com/upload/", timeout=30000)
            time.sleep(3)

            # Check if login is still valid
            if page.url.startswith("https://www.tiktok.com/login"):
                raise Exception("Session expired. Run login_interactive() again.")

            # Upload file via hidden input
            file_input = page.locator("input[type=file]")
            file_input.wait_for(timeout=15000)
            file_input.set_input_files(video_path)
            print("  File selected, waiting for processing...")

            # Wait for upload to complete (look for caption textarea)
            caption_field = page.locator("div[contenteditable=true]")
            caption_field.wait_for(timeout=60000)
            print("  Upload processed, filling caption...")

            # Fill caption/description
            hashtag_str = " ".join(f"#{h.replace(' ','')}" for h in hashtags)
            full_caption = f"{title}\n\n{description}\n\n{hashtag_str}"[:2200]
            caption_field.fill(full_caption)
            time.sleep(1)

            # Click Post
            post_btn = page.get_by_role("button", name="Post")
            post_btn.wait_for(timeout=10000)
            post_btn.click()
            print("  Posted!")

            # Wait for success / get video URL
            time.sleep(8)

            # Try to extract video ID from URL
            current_url = page.url
            import re
            m = re.search(r'video/(\d+)', current_url)
            if m:
                video_id = m.group(1)
            else:
                video_id = "posted"

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
        finally:
            ctx.close()
            browser.close()

    return video_id

def generate_credentials_guide():
    return """COMO CONFIGURAR TIKTOK (PLAYWRIGHT):

1. Instale as dependencias:
   pip install playwright
   playwright install chromium

2. Execute o setup de login:
   python -c "from tiktok_uploader import login_interactive; login_interactive()"

3. Faça login manual no navegador que abrir

4. Pronto! O CI vai usar os cookies salvos.

PARA CI (GitHub Actions):
  - Adicione o secret TT_COOKIES com o base64 do arquivo tiktok_cookies.json:
    powershell: [Convert]::ToBase64String([IO.File]::ReadAllBytes(\"$env:USERPROFILE\\.clipcrafter\\tiktok_cookies.json\"))
  - Quando os cookies expirarem, repita o passo 2 e atualize o secret
"""
