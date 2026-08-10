"""Content detector — identifies game type and content style from VOD metadata + audio."""
import re

# ============================================================
# GAME DETECTION FROM VOD TITLE
# ============================================================

GAME_PATTERNS = [
    # Valorant variants — match exact game context, avoid common words
    (r"valorant|tentando evoluir.*valorant|void cup|mira bamba|mira cambada", "Valorant"),
    (r"\blol\b|league of legends|lol fercami|yordle", "Valorant"),
    (r"pearl|sunset|ascent|bind|haven|breeze|fracture|icebox|lotus|abyss|duelo|duela|furia.*ouro|amassando|bronze|diamante|ranked|rank up", "Valorant"),
    (r"dupla.*abaixa|doando.*ponto|abaixa.*doando|boost|dupla do", "Valorant Duo"),
    # Roblox / game on Roblox
    (r"roblox|all star|astd|tower defense|anime celestial|chuck e cheese|chuck|protector de fantasm|arsenal|jogo de tiro do roblox|brookhaven|adopt me|piggy|doom|100 k de gemas|atualizado",
     "Roblox"),
    # Minecraft
    (r"minecraft|one block|surviv|craft tower|palworld|palword|mine|na floresta", "Minecraft"),
    # Five Nights at Freddy's
    (r"five nights|fnaf|freddy|fna", "FNAF"),
    # Super Mario
    (r"super mario|mario", "Super Mario"),
    # Demonology / horror co-op
    (r"demonolog|ca.ca.*fantasma|fantasmas|corra do macaco|churrasco|frigid dusk|lost rooms|suitborn", "Horror Co-op"),
    # Marvel
    (r"marvel rivals|marvel|rivals|herois|hero's", "Marvel Rivals"),
    # Squid Game
    (r"round 6|squid game", "Squid Game"),
    (r"ensinando|coach|como.*jogar|propra lives|dica", "Coaching"),
]

# Generic gaming terms to use as flavor (not a specific game)
GENERIC_GAME_WORDS = r"\b(jogo|jogos|game|games|live|lives|partida|momento|clipe|clip)\b"

def detect_game(vod_title: str) -> str:
    vt = vod_title.lower()
    for pattern, game in GAME_PATTERNS:
        if re.search(pattern, vt):
            # Valorant map/lane words collide with common words — only match if
            # not overridden by a more specific game earlier. Keep as-is.
            return game
    # Default fallback for generic gaming titles
    return "Gaming"

def detect_style(vod_title: str) -> str:
    vt = vod_title.lower()
    style = None
    for pattern, s in [
        (r"competitiv|ranked|amassando|destru|classifica", "competitive"),
        (r"relaxando|chill| relax |cozy", "chill"),
        (r"dupla|abaixa|doando.*ponto| duo ", "duo"),
        (r"ensinando|coach|como.*jogar|dicas", "coaching"),
        (r"terror|horror|tenso|assustador|susto", "horror"),
    ]:
        if re.search(pattern, vt):
            style = s
            break
    return style or "gameplay"

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
    "Roblox": "#Roblox #RobloxBrasil",
    "Minecraft": "#Minecraft #MinecraftBrasil",
    "FNAF": "#FNAF #FiveNightsAtFreddys",
    "Super Mario": "#SuperMario #Nintendo",
    "Horror Co-op": "#Horror #JogosDeTerror",
    "Marvel Rivals": "#MarvelRivals #Marvel",
    "Squid Game": "#SquidGame #Round6",
    "Gaming": "#Gameplay",
}

GAME_CATEGORY_IDS = {
    "Valorant": "20",
    "League of Legends": "20",
    "Valorant Duo": "20",
    "Coaching": "20",
    "Roblox": "20",
    "Minecraft": "20",
    "FNAF": "20",
    "Super Mario": "20",
    "Horror Co-op": "20",
    "Marvel Rivals": "20",
    "Squid Game": "20",
    "Gaming": "20",
}

def get_game_tags(game: str) -> list:
    base = ["CanalPropra", "ClipCrafter", "shorts", "clipe", "fercami"]
    game_tags = {
        "Valorant": ["Valorant", "ValorantBrasil", "valorantclips", "jogadasvalorant"],
        "League of Legends": ["LeagueOfLegends", "LoL", "lolzinho", "lolbrasil"],
        "Valorant Duo": ["Valorant", "Duo", "duovalorant", "abaixando"],
        "Coaching": ["Valorant", "Coaching", "dicasvalorant", "melhorar"],
        "Roblox": ["Roblox", "RobloxBrasil", "robloxgameplay", "allstartowerdefense"],
        "Minecraft": ["Minecraft", "MinecraftBrasil", "minecraftgameplay", "oneblock"],
        "FNAF": ["FNAF", "FiveNightsAtFreddys", "fnafbrasil", "horrorgame"],
        "Super Mario": ["SuperMario", "MarioBros", "Nintendo", "mariogameplay"],
        "Horror Co-op": ["JogosDeTerror", "HorrorGame", "terrorcoop"],
        "Marvel Rivals": ["MarvelRivals", "Marvel", "RivalsGameplay"],
        "Squid Game": ["SquidGame", "Round6", "squidgamebrasil"],
        "Gaming": ["Gameplay", "jogando", "live"],
    }
    return base + game_tags.get(game, game_tags["Gaming"])