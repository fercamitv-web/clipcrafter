"""Generate GitHub secrets from local YouTube credentials."""
import json, base64, os, sys
from pathlib import Path

CLIP_DIR = Path.home() / ".clipcrafter"
CS_PATH = CLIP_DIR / "client_secret.json"
TK_PATH = CLIP_DIR / "youtube_token.pickle"

def main():
    if not CS_PATH.exists():
        print(f"Missing: {CS_PATH}")
        sys.exit(1)
    if not TK_PATH.exists():
        print(f"Missing: {TK_PATH}")
        sys.exit(1)

    cs_b64 = base64.b64encode(CS_PATH.read_bytes()).decode()
    tk_b64 = base64.b64encode(TK_PATH.read_bytes()).decode()

    print("=" * 60)
    print("  GITHUB SECRETS — execute these commands:")
    print("=" * 60)
    print()
    print(f'gh secret set YT_CLIENT_SECRET --body "{cs_b64}"')
    print()
    print(f'gh secret set YT_TOKEN_PICKLE --body "{tk_b64}"')
    print()
    print("=" * 60)
    print("  Or set manually at:  https://github.com/USER/REPO/settings/secrets/actions")
    print("=" * 60)

if __name__ == "__main__":
    main()
