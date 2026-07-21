"""Content detector — identifies game type and content style from VOD metadata + audio."""
import re

# ============================================================
# GAME DETECTION FROM VOD TITLE
# ============================================================

GAME_PATTERNS = [
    (r"valorant|ranked|tentando evoluir.*valorant", "Valorant"),
    (r"\blol\b|league of legends|lol fercami", "League of Legends"),
    (r"dupla.*abaixa|doando.*ponto|abaixa.*doando|boost", "Valorant Duo"),
    (r"ensinando|coach|como.*jogar|propra lives", "Coaching"),
]

STYLE_PATTERNS = [
    (r"relaxando|chill| relax ", "chill"),
    (r"ranked|tentando evoluir|competitivo", "competitive"),
    (r"dupla|abaixa|doando.*ponto| duo ", "duo"),
    (r"ensinando|coach|como.*jogar|dicas", "coaching"),
    (r"lol.*fercami|fercami.*lol", "casual"),
]

def detect_game(vod_title: str) -> str:
    vt = vod_title.lower()
    for pattern, game in GAME_PATTERNS:
        if re.search(pattern, vt):
            return game
    # Check for "fercami" in title as general gaming
    if "fercami" in vt:
        return "Gaming"
    return "Gaming"

def detect_style(vod_title: str) -> str:
    vt = vod_title.lower()
    for pattern, style in STYLE_PATTERNS:
        if re.search(pattern, vt):
            return style
    return "gameplay"

def get_game_info(vod_title: str) -> dict:
    return {
        "game": detect_game(vod_title),
        "style": detect_style(vod_title),
    }

# ============================================================
# GAME-SPECIFIC CONTENT TEMPLATES
# ============================================================

GAME_HASHTAGS = {
    "Valorant": "#Valorant #ValorantBrasil",
    "League of Legends": "#LeagueOfLegends #LoL",
    "Valorant Duo": "#Valorant #Duo",
    "Coaching": "#Valorant #Coaching #Dicas",
    "Gaming": "#Gameplay",
}

GAME_CATEGORY_IDS = {
    "Valorant": "20",
    "League of Legends": "20",
    "Valorant Duo": "20",
    "Coaching": "20",
    "Gaming": "20",
}

def get_game_tags(game: str) -> list:
    base = ["CanalPropra", "ClipCrafter", "shorts", "clipe", "fercami"]
    game_tags = {
        "Valorant": ["Valorant", "ValorantBrasil", "valorantclips", "jogadasvalorant"],
        "League of Legends": ["LeagueOfLegends", "LoL", "lolzinho", "lolbrasil"],
        "Valorant Duo": ["Valorant", "Duo", "duovalorant", "abaixando"],
        "Coaching": ["Valorant", "Coaching", "dicasvalorant", "melhorar"],
        "Gaming": ["Gameplay", "jogando", "live"],
    }
    return base + game_tags.get(game, game_tags["Gaming"])
