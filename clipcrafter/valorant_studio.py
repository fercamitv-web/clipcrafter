"""ValorantStudio v3 — multi-game hook/title engine with speech-aware analysis"""
import os, json, random, re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# === VALORANT KNOWLEDGE ===
AGENTS = ["Jett","Reyna","Phoenix","Raze","Neon","Yoru","Iso",
          "Sage","Cypher","Killjoy","Chamber","Deadlock","Vyse",
          "Brimstone","Omen","Astra","Harbor","Clove","Tejo",
          "Sova","Breach","Skye","KAY/O","Fade","Gekko"]
MAPS = ["Ascent","Bind","Haven","Split","Icebox","Breeze",
        "Fracture","Pearl","Lotus","Sunset","Abyss"]
WEAPONS = ["Vandal","Phantom","Operator","Sheriff","Classic",
           "Spectre","Ares","Odin","Guardian","Bulldog",
           "Stinger","Judge","Bucky","Shorty","Marshal",
           "Outlaw","Ghost","Frenzy"]
RANKS = ["Ferro","Bronze","Prata","Ouro","Platina","Diamante",
         "Ascendente","Imortal","Radiante"]

# ============================================================
# PSYCHOLOGICAL TRIGGER HOOKS — multi-game, each targets a specific
# retention principle: curiosity gap, open loop, pattern interrupt,
# loss aversion, social proof, self-relevance, mystery, urgency, contrast.
# ============================================================

HOOK_TEMPLATES = {
    # ---------- VALORANT ----------
    "Valorant_curiosity": [
        "VOCE NUNCA VAI ADIVINHAR O QUE ACONTECEU DEPOIS DISSO",
        "OS PROXIMOS 10 SEGUNDOS VAO TE DEIXAR DE QUEIXO CAIDO",
        "QUANDO ELE ACHOU QUE TINHA VENCIDO, AI QUE TUDO COMECOU",
        "O QUE VEM DEPOIS DESTE MOMENTO MUDA COMPLETAMENTE O JOGO",
        "ISSO QUE ACONTECEU NOS SEGUNDOS SEGUINTES FOI ABSURDO",
        "SE VOCE PISCAR OS OLHOS AGORA VOCE VAI PERDER O MELHOR",
        "NINGUEM — ABSOLUTAMENTE NINGUEM — ESPERAVA O PROXIMO PASSO",
        "VOCE ACHA QUE ACABOU? ASSISTE SO O QUE VEM DEPOIS",
        "A PARTIR DESSE MOMENTO ELE SIMPLESMENTE DESABOU",
    ],
    "Valorant_stakes": [
        "ELE ESTAVA A UM UNICO TIRO DE PERDER TUDO — ERA PRA TER PERDIDO",
        "ULTIMO VIVO. CINCO INIMIGOS. SEM MUNICAO. ERA O FIM.",
        "SE FOSSE VOCE JOGANDO, VOCE TERIA PERDIDO. ASSISTE O QUE ELE FEZ.",
        "1 CONTRA 5. UM ERRO E O JOGO ACABA. ELE NAO ERROU.",
        "ELE QUASE PERDEU — POR UM MILISSEGUNDO A HISTORIA SERIA OUTRA",
        "TODOS CONTRA ELE. ELE SABIA DISSO. ELE VENCEU MESMO ASSIM.",
        "A PRESSAO ERA INSUPORTAVEL. ASSISTE O QUE VEIO DEPOIS.",
        "UM PASSO EM FALSO E TUDO DESMORONAVA. ELE NAO DEU ESSE PASSO.",
        "ISSO ERA PRA DAR ERRADO. NAO TEM COMO TER DADO CERTO.",
    ],
    "Valorant_question": [
        "COMO QUE ELE SOBREVIVEU A ISSO? A CIENCIA NAO EXPLICA.",
        "QUAL A PROBABILIDADE MATEMATICA DE UM {event} IGUAL A ESSE? ZERO.",
        "ISSO FOI REAL MESMO? OU FOI SORTE PURO? ASSISTE E TIRE SUAS CONCLUSAO.",
        "COMO ELE SOBREVIVEU? RESPONDE NOS COMENTARIOS.",
        "QUANTAS TENTATIVAS VOCE ACHA QUE ELE PRECISOU PRA ISSO?",
        "REALMENTE ACONTECEU OU EU TO MALUCO? VOCE DECIDE.",
        "EXISTE EXPLICACAO LOGICA PRA ISSO? {event}.",
        "VOCE CONSEGUE ADIVINHAR O FINAL DESSE {event}? EU APOSTO QUE NAO.",
        "MG? OU HACK? A GALERA DOS COMENTARIOS VAI DECIDIR.",
    ],
    "Valorant_bold_statement": [
        "ESSE FOI O {event} MAIS IMPRESSIONANTE DE TODA A HISTORIA DO CANAL",
        "DEPOIS DESSE {event} ELE SIMPLESMENTE PAROU DE JOGAR POR UM TEMPO",
        "NINGUEM NO SERVIDOR INTEIRO ACREDITOU NESSE {event}",
        "ISSO QUE VOCE VAI VER REDEFINE O SIGNIFICADO DE {event}",
        "O {event} QUE VOCE ESTA PRESTES A VER E HISTORICO",
        "ESSE E O TIPO DE {event} QUE APARECE UMA VEZ NA VIDA",
        "SE VOCE NAO VIU ESSE {event} AO VIVO, VOCE PERDEU ALGO UNICO",
        "O PESSOAL DA PARTIDA INTEIRA PAROU PRA ASSISTIR ESSE {event}",
    ],
    "Valorant_one_liner": [
        "NAO EXISTE PALAVRA QUE DESCREVA ISSO QUE VOCE VAI VER",
        "REACAO DE QUEM VIU AO VIVO FOI MELHOR QUE O PROPRIO CLIPE",
        "VOCE SO VAI ENTENDER QUANDO VER ATE O FINAL — E VAI QUERER VER DE NOVO",
        "ISSO NAO E NORMAL. ISSO NAO E HUMANO. ISSO E OUTRO NIVEL.",
        "O CHAT ENLOUQUECEU. A LIVE CAIU. ELE NAO PAROU.",
        "AGORA EU SEI O QUE SIGNIFICA FICAR SEM REACAO.",
    ],

    # ---------- LEAGUE OF LEGENDS ----------
    "LoL_curiosity": [
        "VOCE NUNCA VAI ADIVINHAR O QUE ACONTECEU NESSA PARTIDA DE LOL",
        "OS PROXIMOS SEGUNDOS DESSE LOL VAO TE SURPREENDER COMPLETAMENTE",
        "NO LOL, ISSO E TÃO RARO QUE POUCOS JOGADORES JA PRESENCIARAM",
        "O QUE ACONTECEU DEPOIS NO LOL FEZ TODO MUNDO PERGUNTAR 'COMO?'",
        "ESSA JOGADA DE LOL E TÃO ABSURDA QUE PARECE CENA DE FILME",
        "ISSO NUNCA TINHA ACONTECIDO EM 10 ANOS DE LOL — ATE AGORA",
        "O INIMIGO ACHOU QUE TINHA GANHO. AI VEIO O PLOT TWIST.",
    ],
    "LoL_stakes": [
        "UM ERRO E A PARTIDA ACABAVA — ELE SIMPLESMENTE NAO ERROU",
        "SOZINHO CONTRA VARIOS NO LOL. SEM VISÃO. SEM AJUDA. SEM MEDO.",
        "SE FOSSE VOCE NAQUELE MOMENTO, VOCE TERIA MORRIDO. ELE NAO.",
        "A VITORIA TAVA PERDIDA. ATE ELE DECIDIR MUDAR O ROTEIRO.",
        "UM MILISSEGUNDO DE ATRASO E TUDO DESMORONAVA. ADIVINHA?",
        "ERA PRA TER DADO ERRADO. O LOL DISSE QUE NAO.",
    ],
    "LoL_question": [
        "QUAL A CHANCE DE ALGO ASSIM ACONTECER EM UMA PARTIDA RANKED DE LOL?",
        "ISSO FOI REAL OU O JOGO SIMPLESMENTE DECIDIU AJUDAR ELE?",
        "COMO ELE SOBREVIVEU A ISSO NO LOL? RESPOSTA: SKILL.",
        "VOCE ACHA QUE ISSO E JOGADA COMUM? ASSISTE DE NOVO.",
        "QUANTAS HORAS DE LOL VOCE ACHA QUE ELE PRECISOU PRA TENTAR ISSO?",
        "O QUE VOCE FARIA SE FOSSE O INIMIGO DEPOIS DESSA JOGADA?",
    ],
    "LoL_bold_statement": [
        "ESSA E SIMPLESMENTE A JOGADA DE LOL MAIS IMPRESSIONANTE DO DIA",
        "DEPOIS DISSO, O INIMIGO SIMPLESMENTE DESISTIU DO LOL",
        "NINGUEM JOGA LOL ASSIM — NEM OS PROFISSIONAIS FAZEM ISSO",
        "ISSO NO LOL E O EQUIVALENTE A UM MILAGRE",
        "QUEM VIU AO VIVO VIU ALGO QUE VAI CONTAR PRA VIDA INTEIRA",
    ],
    "LoL_one_liner": [
        "LOL NUNCA MAIS VAI SER O MESMO DEPOIS DESSA JOGADA",
        "O INIMIGO SO PODE TER FICADO SEM REACAO DEPOIS DISSO",
        "VOCE NAO VAI CONSEGUIR PARAR DE ASSISTIR ESSE CLIPE DE LOL",
        "ELE SIMPLESMENTE DECIDIU QUE IA GANHAR — E GANHOU",
        "EXISTE JOGADOR DE LOL ANTES E DEPOIS DESSE MOMENTO",
    ],

    # ---------- COACHING ----------
    "Coaching_curiosity": [
        "ESSA DICA MUDA COMPLETAMENTE A FORMA COMO VOCE JOGA VALORANT",
        "A MAIORIA DOS JOGADORES NUNCA APRENDE ISSO — E PERDE PARTIDAS POR CAUSA DISSO",
        "SE VOCE SO APRENDER UMA COISA DE VALORANT HOJE, QUE SEJA ISSO",
        "ISSO QUE ELE FEZ NA PARTIDA E O QUE SEPARA INICIANTES DE AVANCADOS",
        "POUCAS PESSOAS SABEM DESSE DETALHE — E FAZ TODA DIFERENCA",
    ],
    "Coaching_stakes": [
        "UM UNICO ERRO E VOCE PERDE O ROUND INTEIRO — APRENDA A NAO COMETER",
        "VOCE TA PERDENDO PARTIDA PORQUE NAO SABE DISSO. HOJE VOCE VAI APRENDER.",
        "ESSE PEQUENO AJUSTE VAI TE FAZER GANHAR ROUNDS QUE VOCE PERDIA ANTES",
    ],
    "Coaching_question": [
        "VOCE SABE O QUE ELE FEZ DE DIFERENTE AQUI? 99% DOS JOGADORES NAO SABEM.",
        "QUANTAS PARTIDAS VOCE PERDEU POR NAO SABER DISSO? DEPOIS DE HOJE, NENHUMA.",
    ],
    "Coaching_bold_statement": [
        "ISSO E O ERRO MAIS COMUM QUE DESTROI SUAS PARTIDAS DE VALORANT",
        "SE VOCE DOMINAR ISSO, VOCE SOBE DE ELO EM UMA SEMANA",
    ],

    # ---------- GAMING (FALLBACK) ----------
    "Gaming_curiosity": [
        "VOCE NUNCA VAI ADIVINHAR O QUE VEIO DEPOIS DESSE MOMENTO",
        "O QUE ACONTECEU NOS SEGUNDOS SEGUINTES FOI COMPLETAMENTE INESPERADO",
        "NINGUEM — REPITO, NINGUEM — ESPERAVA QUE ISSO FOSSE ACONTECER",
        "VOCE ACHA QUE JA VIU TUDO? ESPERA SO ATE O FINAL DESTE CLIPE",
        "O MELHOR MOMENTO DA LIVE INTEIRA ESTA NESTES PROXIMOS SEGUNDOS",
    ],
    "Gaming_stakes": [
        "ERA PRA TER DADO ERRADO. NAO TEM EXPLICACAO. SO ACONTECEU.",
        "SE FOSSE VOCE, VOCE TINHA PERDIDO. ELE NAO PERDEU.",
    ],
}

GENERIC_HOOKS = [
    "VOCE NUNCA VAI ADIVINHAR O QUE VEIO DEPOIS",
    "O QUE ACONTECEU DEPOIS FOI COMPLETAMENTE ABSURDO",
    "ISSO SIMPLESMENTE ACONTECEU NA LIVE — NINGUEM ESPERAVA",
    "MOMENTO QUE PAROU A LIVE E O CHAT ENLOUQUECEU",
    "REACAO NA HORA FOI A MELHOR PARTE DO CLIPE INTEIRO",
    "SO ASSISTINDO ATE O FINAL PRA ENTENDER O QUE REALMENTE ACONTECEU",
    "ISSO NAO E NORMAL — ISSO E OUTRO PATAMAR",
    "NINGUEM ESPERAVA ESSE FINAL — INCLUINDO ELE MESMO",
    "VOCE PRECISA VER ISSO ATE O FIM — PROMETO QUE VALE A PENA",
    "ELE TINHA TUDO PRA PERDER. ELE PERDEU TUDO? DESCUBRA AGORA.",
    "ISSO QUE VOCE VAI VER AGORA E EXTREMAMENTE RARO DE ACONTECER",
    "NAO PULE O VIDEO — O FINAL E SIMPLESMENTE IMPERDIVEL",
    "SE VOCE NAO VIU ISSO AO VIVO, VOCE VAI QUERER TER VISTO",
    "A CRESCENDA DESSE CLIPE E ALGO QUE VOCE NAO TA PREPARADO PRA VER",
    "O QUE PARECIA O FIM ERA NA VERDADE SO O COMECO DO ABSURDO",
]

# ============================================================
# PSYCHOLOGICAL 2-LINE OVERLAYS — first 2s retention hooks
# Each line works as a two-part psychological trigger:
# top = pattern interrupt / command, bottom = payoff / curiosity.
# ============================================================

HOOK_2LINE_VALORANT = [
    "VOCE NUNCA VAI\\nADIVINHAR",
    "O QUE VEM DEPOIS\\nMUDA TUDO",
    "ESPERA SO ATE\\nO FINAL",
    "SE PISCAR\\nPERDEU",
    "ISSO NAO E\\nPOSSIVEL",
    "ELE SIMPLESMENTE\\nDOMINOU",
    "REACAO DELES\\nFOI EPICA",
    "NINGUEM ESPERAVA\\nESSE FINAL",
    "COMO ELE\\nFEZ ISSO?",
    "SO ASSISTINDO\\nPRA ENTENDER",
    "ESSA JOGADA\\nE HISTORICA",
    "ISSO FOI REAL\\nMESMO?",
    "VOCE NAO TA\\nPREPARADO",
    "O MELHOR MOMENTO\\nDA LIVE INTEIRA",
    "ERA PRA TER\\nDADO ERRADO",
    "UM MILISSEGUNDO\\nMUDOU TUDO",
    "ELE NAO\\nERROU NADA",
    "ISSO QUE E\\nSELVAGERIA",
    "CHEGOU NO\\nAPICE",
    "ISSO RARISSIMO\\nDE VER",
    "VOCE SO VAI\\nACREDITAR NO FIM",
    "PARA TUDO\\nE ASSISTE",
]

HOOK_2LINE_VALORANT_ACE = [
    "!! ACE !!\\nMATOU O TIME INTEIRO",
    "1VS5? ELE\\nNAO TINHA DIREITO",
    "!! ACE !!\\nELIMINOU TODOS OS 5",
    "O TIME INIMIGO\\nFOI DESTRUIDO",
    "NINGUEM SOBREVIVEU\\nAO ACE",
    "!! ACE !!\\nMOMENTO PERFEITO",
    "CINCO INIMIGOS\\nUMA JOGADA",
    "ELE SOZINHO\\nCONTRA O MUNDO",
    "!! ACE !!\\nSELVAGERIA PURA",
    "NAO SOBROU\\nNINGUEM",
]

HOOK_2LINE_VALORANT_CLUTCH = [
    "ULTIMO VIVO\\nCONTRA TODOS ELES",
    "SOZINHO. SEM AJUDA.\\nE VENCEU.",
    "UM CONTRA VARIOS\\nELE GANHOU ASSIM",
    "NAO TINHA DIREITO\\nDE GANHAR E GANHOU",
    "CLUTCH PERFEITO\\nSEM ERRAR UM TIRO",
    "SOBROU SO ELE\\nE NAO TREMEU",
    "ERA PRA PERDER\\nMAS ELE VIROU",
    "VIRADA HISTORICA\\nSOZINHO CONTRA TUDO",
    "DEU A VIRADA\\nQUANDO MAIS PRECISAVA",
    "UM PASSO DO FIM\\nELE VOLTOU",
    "A PRESSAO NAO\\nATINGIU ELE",
]

HOOK_2LINE_VALORANT_KILL = [
    "!! 4K !!\\nQUADRA INCRIVEL",
    "MATOU VARIOS\\nSEGUIDOS",
    "3 KILLS\\nEM SEGUIDA",
    "!! 4K !!\\nDESTRUIDOR",
    "TRIPLO\\NIMPOSSIVEL",
    "!! 3K !!\\nMOMENTO ABSURDO",
]

HOOK_2LINE_LOL = [
    "ISSO NO LOL\\nE RARISSIMO",
    "JOGADA DE LOL\\nINACREDITAVEL",
    "NO LOL ELE\\nSIMPLESMENTE VIROU",
    "MOMENTO DE LOL\\nQUE PAROU TUDO",
    "QUE JOGADA\\nNO LOL",
    "1 CONTRA VARIOS\\nNO LOL",
    "LOL INSANO\\NUNCA VI IGUAL",
    "NO LOL ISSO\\nMUDOU O JOGO",
    "ELE DOMINOU\\nO LOL INTEIRO",
]

HOOK_2LINE_GENERIC = [
    "ISSO NAO E\\nNORMAL",
    "QUE JOGADA\\nINACREDITAVEL",
    "MOMENTO\\NUNICO",
    "VOCE PRECISA\\nVER ISSO",
    "ESPERA SO\\nATE O FINAL",
    "ISSO\\nMUDOU TUDO",
    "ELE NAO\\nESPERAVA ISSO",
    "QUE\\nFOI ISSO?",
    "VOCE VAI\\nFICAR CHOCADO",
    "COMO ELE\\nFEZ ISSO?",
    "MELHOR MOMENTO\\nDA LIVE INTEIRA",
]

# ============================================================
# MULTI-GAME TITLE PATTERNS
# ============================================================

TITLE_PATTERNS = {
    "Valorant": [
        "{kc}{event} ABSURDO DE VALORANT",
        "ESSE {event} FOI INACREDITAVEL - Valorant",
        "{kc}{event} QUE NINGUEM ESPERAVA",
        "{event} NA RANKED - Jogando Valorant",
        "MELHOR {event} DO DIA - Valorant #clip",
        "{event} INSANO QUE VOCE PRECISA VER",
        "O {event} MAIS LOUCO DA SEMANA",
        "{kc}{event} - MOMENTO QUE PAROU A LIVE",
        "SELVAGEM: {event} ABSURDO NO VALORANT",
        "{event} PERFEITO - MELHORES MOMENTOS",
        "QUE {event} ABSURDO - VALORANT GAMEPLAY",
        "{event} NA LIVE - CanalPropra",
    ],
    "Valorant_agent": [
        "{kc}{event} DE {agent} QUE NINGUEM ESPERAVA",
        "{agent} {kc}{event} ABSURDO - Melhores Jogadas",
        "JOGADA DE {agent} COM {kc}{event} INACREDITAVEL",
        "{agent} {kc}{event} - MOMENTO DE GENIO",
        "QUE JOGADA DA {agent} - {kc}{event} PERFEITO",
        "{agent} SIMPLESMENTE {kc}{event} - VALORANT",
        "MELHOR {agent} DO DIA - {kc}{event} INSANO",
    ],
    "Valorant_weapon": [
        "{weapon} {kc}{event} QUE VOCE PRECISA VER",
        "{event} DE {weapon} ABSURDO - Valorant Gameplay",
        "{agent} DE {weapon} - {kc}{event} PERFEITO",
        "1VS5 DE {weapon} NO VALORANT - {event}",
        "{kc}{event} COM {weapon} - JOGADA IMPOSSIVEL",
        "{weapon} PERFEITA: {agent} {kc}{event} INSANO",
        "{event} COM {weapon} - SENSACIONAL",
    ],
    "Valorant_map": [
        "{kc}{event} NO MAPA {map} - Valorant Gameplay",
        "{event} INSANO NA {map} - Melhores Jogadas",
        "{kc}{event} NA {map} - Jogada PERFEITA",
        "MELHOR MOMENTO NA {map} - {event} ABSURDO",
        "{agent} DOMINOU A {map} - {kc}{event}",
    ],
    "League of Legends": [
        "MOMENTO ABSURDO NO LOL",
        "JOGADA DE LOL INACREDITAVEL",
        "ISSO NO LOL QUE NINGUEM ESPERAVA",
        "MELHOR MOMENTO DO DIA NO LOL",
        "LOL SELVAGEM - Jogada IMPOSSIVEL",
        "QUE JOGADA NO LOL - Inacreditavel",
        "MOMENTO QUE PAROU A LIVE NO LOL",
    ],
    "Coaching": [
        "DICA DE VALORANT QUE MUDA TUDO",
        "APRENDENDO VALORANT - Melhorando",
        "COACHING VALORANT - Dica ABSURDA",
        "MELHORANDO NO VALORANT - Gameplay",
    ],
    "Gaming": [
        "MOMENTO ABSURDO NA LIVE",
        "ISSO ACONTECEU NA LIVE",
        "MELHOR MOMENTO DA LIVE",
        "MOMENTO QUE PAROU A LIVE",
    ],
}

FALLBACK_TITLES = [
    "MOMENTO ABSURDO NA LIVE - CanalPropra #clip",
    "ISSO ACONTECEU NA LIVE - Gameplay #clip",
    "MELHOR MOMENTO DA LIVE #clip",
    "MOMENTO QUE PAROU A LIVE #clip",
]

# Event detection: expanded with audio-based signals and PT-BR
EVENT_KW = {
    "ACE": ["ace","1v5","five kill","all 5","todos","5k","five k","matou todos","eliminou todos"],
    "CLUTCH": ["clutch","1v","last alive","sozinho","morreu","matei","ultimo","segurou","virou"],
    "ONE TAP": ["one tap","one-tap","one shot","dinked","headshot","tap","hs","cabeca","na cabeca"],
    "MULTI KILL": ["multi","triple","quadra","3k","4k","5k","triplo","quadruplo","matando varios"],
    "ECO WIN": ["eco","eco round","sheriff","classic","pistol","sem arma","eco win"],
    "ABILITY PLAY": ["ability","utility","dash","teleport","smoke","flash","ult","ultimate",
                     "ultimato","habilidade","skill","poder","jett dash","reyna heal"],
    "RETOME": ["retake","retomada","voltar","entrar","limpar","reset"],
    "COLEGA": ["team","time","colegas","companheiro","help","ajuda","save","salvou"],
}

@dataclass
class ClipAnalysis:
    event_type: str = "highlight"
    agent: str = ""
    map_name: str = ""
    weapon: str = ""
    is_clutch: bool = False
    is_ace: bool = False
    is_eco: bool = False
    kill_count: int = 0
    speech_text: str = ""
    duration: float = 0
    energy_score: float = 0.0
    excitement: float = 0.0
    silence_pct: float = 0.0
    has_ability: bool = False
    has_comeback: bool = False

class ValorantStudio:
    def __init__(self):
        self.analysis = ClipAnalysis()
        self.game = "Valorant"  # Default, can be changed via detect_game

    def analyze_transcript(self, transcript: List[str]) -> ClipAnalysis:
        a = ClipAnalysis()
        full = " ".join(transcript).lower()
        a.speech_text = full

        # Event detection — multiple events can overlap, pick most specific
        scores = {}
        for ev, kws in EVENT_KW.items():
            scores[ev] = sum(1 for k in kws if k in full)
        if scores:
            best = max(scores, key=scores.get)
            a.event_type = best if scores[best] > 0 else "highlight"

        a.is_ace = "ACE" in a.event_type
        a.is_clutch = "CLUTCH" in a.event_type
        a.is_eco = "ECO" in a.event_type
        a.has_ability = "ABILITY" in a.event_type

        # Agent / map / weapon detection
        for ag in AGENTS:
            if ag.lower() in full:
                a.agent = ag; break
        for m in MAPS:
            if m.lower() in full:
                a.map_name = m; break
        for w in WEAPONS:
            if w.lower() in full:
                a.weapon = w; break

        # Kill count — more aggressive detection
        kc = sum(1 for _ in re.finditer(r"\b\d+\s*k\b|\b(k|kill|dead|morreu|matei|abate|elimin)\b", full))
        explicit = re.findall(r"(\d+)\s*k", full)
        if explicit:
            kc = max(kc, int(max(explicit)))
        a.kill_count = min(kc, 5)
        if a.kill_count >= 3 and a.event_type == "highlight":
            a.event_type = "MULTI KILL"

        self.analysis = a
        return a

    def generate_seo_title(self, kill_count: int = None, event_type: str = None,
                           agent: str = "", map_name: str = "",
                           weapon: str = "") -> str:
        a = self.analysis
        kc = kill_count if kill_count is not None else a.kill_count
        et = (event_type or a.event_type)
        ag = agent or a.agent
        mp = map_name or a.map_name
        wp = weapon or a.weapon
        kc_str = f"{kc}K" if kc >= 2 else ""

        context = {"kc": kc_str, "event": et, "agent": ag, "weapon": wp, "map": mp}

        # Select game-appropriate patterns
        game = self.game
        if game in ("Valorant", "Valorant Duo"):
            if wp and ag:
                pool = [t.format(**context) for t in TITLE_PATTERNS.get("Valorant_weapon", [])]
            elif wp:
                pool = [t.format(**context) for t in TITLE_PATTERNS.get("Valorant_weapon", [])]
            elif ag:
                pool = [t.format(**context) for t in TITLE_PATTERNS.get("Valorant_agent", [])]
            elif mp:
                pool = [t.format(**context) for t in TITLE_PATTERNS.get("Valorant_map", [])]
            else:
                pool = [t.format(**context) for t in TITLE_PATTERNS.get("Valorant", [])]
        elif game in TITLE_PATTERNS:
            pool = [t.format(**context) for t in TITLE_PATTERNS[game]]
        else:
            pool = FALLBACK_TITLES[:]

        title = random.choice(pool).strip()
        title = re.sub(r'\s+', ' ', title).strip()
        if len(title.split()) < 5:
            if game in ("Valorant", "Valorant Duo"):
                title = f"{et} ABSURDO - Valorant Gameplay"
            elif game == "League of Legends":
                title = f"MOMENTO ABSURDO NO LOL"
            else:
                title = f"MOMENTO ABSURDO NA LIVE"
        title = title.rstrip("#").rstrip()
        if "#clip" not in title and len(title) < 90:
            title = f"{title} #clip"
        return title[:100]

    def generate_hook(self, style: str = "auto") -> str:
        a = self.analysis
        ev_labels = {"ACE":"ACE","CLUTCH":"CLUTCH","ONE TAP":"ONE TAP",
                      "MULTI KILL":"MULTI KILL","ECO WIN":"ECO WIN",
                      "ABILITY PLAY":"CLUTCH","RETOME":"CLUTCH","COLEGA":"JOGADA"}
        event = ev_labels.get(a.event_type, "JOGADA")

        game_prefix = self.game.split()[0]
        if game_prefix == "League":
            game_prefix = "LoL"
        elif self.game == "Coaching":
            game_prefix = "Coaching"
        elif self.game not in ["Valorant", "Valorant Duo", "League of Legends", "Coaching"]:
            game_prefix = "Gaming"

        if style == "auto":
            if a.is_ace and game_prefix == "Valorant":
                style = f"{game_prefix}_question"
            elif a.is_clutch and game_prefix == "Valorant":
                style = f"{game_prefix}_stakes"
            elif a.kill_count >= 3 and game_prefix == "Valorant":
                style = f"{game_prefix}_bold_statement"
            else:
                candidates = [k for k in HOOK_TEMPLATES if k.startswith(game_prefix)]
                style = random.choice(candidates) if candidates else "Valorant_curiosity"

        templates = HOOK_TEMPLATES.get(style, GENERIC_HOOKS)
        if templates and isinstance(templates, list) and templates[0] and "{event}" in templates[0]:
            hook = random.choice(templates).format(event=event)
        else:
            hook = random.choice(templates) if templates else ""
        return hook[:80]

    def generate_hook_overlay(self, style: str = "auto") -> str:
        a = self.analysis
        game = self.game
        if game == "League of Legends":
            return random.choice(HOOK_2LINE_LOL)
        elif game == "Coaching":
            return random.choice(HOOK_2LINE_VALORANT + HOOK_2LINE_GENERIC)
        elif game not in ["Valorant", "Valorant Duo"]:
            return random.choice(HOOK_2LINE_GENERIC)

        if a.is_ace:
            pool = HOOK_2LINE_VALORANT_ACE
        elif a.is_clutch:
            pool = HOOK_2LINE_VALORANT_CLUTCH
        elif a.kill_count >= 4:
            pool = HOOK_2LINE_VALORANT_KILL[:3]
        elif a.kill_count >= 3:
            pool = HOOK_2LINE_VALORANT_KILL[3:]
        else:
            pool = HOOK_2LINE_VALORANT
        return random.choice(pool)

    def get_description_tags(self, game: str = None) -> Tuple[str, List[str]]:
        a = self.analysis
        game = game or self.game
        tags = ["ClipCrafter","CanalPropra","shorts","clipe","fercami"]
        if game == "Valorant" or game == "Valorant Duo":
            tags.extend(["Valorant","ValorantBrasil","jogadas valorant","melhores momentos"])
        elif game == "League of Legends":
            tags.extend(["LeagueOfLegends","LoL","lolzinho","lolbrasil"])
        elif game == "Coaching":
            tags.extend(["Coaching","DicasValorant","melhorar"])
        else:
            tags.extend(["Gameplay","jogando","live"])

        if a.event_type and a.event_type != "highlight":
            tags.append(a.event_type.lower().replace(" ",""))
        if a.agent and game in ("Valorant", "Valorant Duo"):
            tags.extend([a.agent, f"{a.agent}Valorant"])
        if a.map_name:
            tags.append(a.map_name)
        if a.weapon and game in ("Valorant", "Valorant Duo"):
            tags.extend([a.weapon, f"{a.weapon}Valorant"])
        if a.kill_count >= 3:
            tags.append(f"{a.kill_count}k")
        if a.is_ace:
            tags.extend(["ace","1v5"])

        game_tag = game.replace(" ", "") if game != "League of Legends" else "LoL"
        desc = (
            f"Melhores momentos de {game}! Jogadas insanas e muito mais.\n\n"
            f"INSCREVA-SE no CanalPropra para mais momentos INSANOS!\n"
            f"Comenta qual dessas jogadas foi a melhor!\n"
            f"Ative o sininho para nao perder os proximos clipes!\n\n"
            f"#{game_tag} #{a.event_type.replace(' ','')} "
            f"#ClipCrafter #CanalPropra #Shorts\n"
        )
        return desc, tags[:20]

    def suggest_duration(self, energy_score: float = 0.5) -> Tuple[float, float]:
        """Research says 30-60s is optimal, median viral clip is 37s.
        High energy = longer clip, low energy = shorter."""
        base = 37  # median viral clip length from 175-clip study
        if energy_score > 0.7:
            return (30, 55)  # high energy can sustain longer
        elif energy_score > 0.5:
            return (25, 40)
        else:
            return (15, 30)

    def _fallback_title(self) -> str:
        return "CLIPE DE VALORANT - Tentando Evoluir #clip"
