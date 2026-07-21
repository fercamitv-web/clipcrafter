"""Helper: open browser for TikTok login and save session cookies."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiktok_uploader import login_interactive, generate_credentials_guide

if __name__ == "__main__":
    print("=== TikTok Login Setup (Playwright) ===\n")
    try:
        login_interactive()
        print("\nSucesso! Cookies salvos. Agora o CI pode fazer upload automaticamente.")
    except Exception as e:
        print(f"\nErro: {e}")
        print("\nCertifique-se de ter instalado:")
        print("  pip install playwright")
        print("  playwright install chromium")
