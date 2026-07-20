"""ValorantStudio v2 — redesigned based on 2026 viral clip research"""
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

# Research-backed 2026 hook patterns — curiosity-first, pattern interrupt, zero intro
HOOK_TEMPLATES = {
    "curiosity": [
        "VOCE PRECISA VER ISSO...",
        "O QUE ACONTECEU DEPOIS FOI INACREDITAVEL",
        "NINGUEM ESPERAVA ESSE FINAL",
        "ISSO SIMPLESMENTE ACONTECEU NA LIVE",
    ],
    "stakes": [
        "ULTIMO VIVO CONTRA 5 - ERA PRA PERDER",
        "1VS5? ASSISTE O QUE ELE FEZ",
        "SEM MIRA NENHUMA E AINDA GANHOU",
        "MORRERIA SE FOSSE COM VOCE",
    ],
    "question": [
        "QUAL A CHANCE DISSO ACONTECER? {event}",
        "ISSO FOI REAL? {event} ABSURDO!",
        "COMO ELE SOBREVIVEU? {event} INACREDITAVEL",
        "MG? OU SORTE? {event} PERFEITO",
    ],
    "bold_statement": [
        "ESSE E O MELHOR {event} QUE VOCE VAI VER HOJE",
        "DEPOIS DESSE {event} ELE PAROU DE JOGAR",
        "NINGUEM ACEDITA NESSE {event}",
    ],
    "one_liner": [
        "NAO E POSSIVEL ISSO ACONTECEU",
        "REACAO DELES FOI EPICA",
        "SO ASSISTINDO PRA ACEDITAR",
        "ISSO NAO E NORMAL",
    ],
}

# Titles optimized for search intent + curiosity (2026 best practices)
TITLE_PATTERNS = [
    "{kc}{event} ABSURDO DE VALORANT",
    "ESSE {event} FOI INACREDITAVEL - Valorant",
    "{kc}{event} QUE NINGUEM ESPERAVA",
    "{event} NA RANKED - Jogando Valorant",
    "MELHOR {event} DO DIA - Valorant #clip",
    "{event} INSANO QUE VOCE PRECISA VER",
    "O {event} MAIS LOUCO DA SEMANA",
    "{kc}{event} - MOMENTO QUE PAROU A LIVE",
    "SELVAGEM: {event} ABSURDO NO VALORANT",
    "{kc}{event} - ISSO SIMPLESMENTE ACONTECEU",
    "{event} PERFEITO - MELHORES MOMENTOS",
    "QUE {event} ABSURDO - VALORANT GAMEPLAY",
]
TITLE_PATTERNS_AGENT = [
    "{kc}{event} DE {agent} QUE NINGUEM ESPERAVA",
    "{agent} {kc}{event} ABSURDO - Melhores Jogadas",
    "JOGADA DE {agent} COM {kc}{event} INACREDITAVEL",
    "{agent} {kc}{event} - MOMENTO DE GENIO",
    "QUE JOGADA DA {agent} - {kc}{event} PERFEITO",
    "{agent} SIMPLESMENTE {kc}{event} - VALORANT",
    "MELHOR {agent} DO DIA - {kc}{event} INSANO",
]
TITLE_PATTERNS_WEAPON = [
    "{weapon} {kc}{event} QUE VOCE PRECISA VER",
    "{event} DE {weapon} ABSURDO - Valorant Gameplay",
    "{agent} DE {weapon} - {kc}{event} PERFEITO",
    "1VS5 DE {weapon} NO VALORANT - {event}",
    "{kc}{event} COM {weapon} - JOGADA IMPOSSIVEL",
    "{weapon} PERFEITA: {agent} {kc}{event} INSANO",
    "{event} COM {weapon} - SENSACIONAL",
]
TITLE_PATTERNS_MAP = [
    "{kc}{event} NO MAPA {map} - Valorant Gameplay",
    "{event} INSANO NA {map} - Melhores Jogadas",
    "{kc}{event} NA {map} - Jogada PERFEITA",
    "MELHOR MOMENTO NA {map} - {event} ABSURDO",
    "{agent} DOMINOU A {map} - {kc}{event}",
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

        # Select pattern pool based on available context
        context = {"kc": kc_str, "event": et, "agent": ag, "weapon": wp, "map": mp}
        if wp and ag:
            pool = [t.format(**context) for t in TITLE_PATTERNS_WEAPON]
        elif wp:
            pool = [t.format(**context) for t in TITLE_PATTERNS_WEAPON]
        elif ag:
            pool = [t.format(**context) for t in TITLE_PATTERNS_AGENT]
        elif mp:
            pool = [t.format(**context) for t in TITLE_PATTERNS_MAP]
        else:
            pool = [t.format(**context) for t in TITLE_PATTERNS]

        title = random.choice(pool).strip()
        title = re.sub(r'\s+', ' ', title).strip()
        if len(title.split()) < 5:
            title = f"{et} ABSURDO - Valorant Gameplay"
        # Add #clip if not already present
        title = title.rstrip("#").rstrip()
        if "#clip" not in title and len(title) < 90:
            title = f"{title} #clip"
        return title[:100]

    def generate_hook(self, style: str = "auto") -> str:
        a = self.analysis
        # All hooks use curiosity/drama — no generic "JOGADA"
        ev_labels = {"ACE":"ACE","CLUTCH":"CLUTCH","ONE TAP":"ONE TAP",
                      "MULTI KILL":"MULTI KILL","ECO WIN":"ECO WIN",
                      "ABILITY PLAY":"CLUTCH","RETOME":"CLUTCH","COLEGA":"JOGADA"}
        event = ev_labels.get(a.event_type, "JOGADA")

        if style == "auto":
            if a.is_ace:
                style = "question"
            elif a.is_clutch:
                style = "stakes"
            elif a.is_eco or a.kill_count >= 3:
                style = "bold_statement"
            else:
                style = random.choice(list(HOOK_TEMPLATES.keys()))

        templates = HOOK_TEMPLATES.get(style, HOOK_TEMPLATES["curiosity"])
        hook = random.choice(templates).format(event=event)
        return hook[:80]

    def generate_hook_overlay(self, style: str = "auto") -> str:
        """Short 2-line hook for video overlay (first 2s text card).
        More dramatic, urgent, with ALL CAPS impact.
        Uses literal \\n for ffmpeg drawtext compatibility."""
        a = self.analysis
        hooks_2line = [
            "VOCE PRECISA\\nVER ISSO",
            "ISSO NAO E\\nNORMAL",
            "O QUE ACONTECEU\\nDEPOIS...",
            "REACAO DELES\\nFOI EPICA",
            "1VS5?\\nASSISTE ISSO",
            "NAO VAI\\nACREDITAR",
            "ELE FEZ\\nISSO NA LIVE",
            "MOMENTO\\nDE GENIO",
            "SO ASSISTINDO\\nPRA ENTENDER",
            "ESPERA SO\\nATE O FINAL",
            "ISSO FOI\\nREAL MESMO?",
            "QUE JOGADA\\nMAGNIFICA",
            "NINGUEM FEZ\\nISSO ANTES",
            "MIRA\\nPERFEITA",
        ]
        if a.is_ace:
            hooks_2line = [
                "!! ACE !!\\nINACREDITAVEL",
                "1VS5?\\nELE CONSEGUIU",
                "!! ACE !!\\nMOMENTO DO JOGO",
                "MATOU\\nTODOS OS 5",
                "!! ACE !!\\nPERFEITO",
            ]
        elif a.is_clutch:
            hooks_2line = [
                "ULTIMO VIVO\\nCONTRA TODOS",
                "SOZINHO\\nE VENCEU",
                "1 CONTRA\\nVARIOS",
                "NAO TINHA\\nDIREITO DE GANHAR",
                "CLUTCH\\nPERFEITO",
                "SOBRAMOS\\nSO ELE",
            ]
        elif a.kill_count >= 4:
            hooks_2line = [
                "!! 4K !!\\nMOMENTO ABSURDO",
                "QUADRA\\nIMPRESSIONANTE",
                "4 KILLS\\nSEGUIDAS",
            ]
        elif a.kill_count >= 3:
            hooks_2line = [
                "!! 3K !!\\nMOMENTO ABSURDO",
                "TRIPLO\\nIMPRESSIOANTE",
                "3 KILLS\\nDE UMA SO VEZ",
            ]
        return random.choice(hooks_2line)

    def get_description_tags(self) -> Tuple[str, List[str]]:
        a = self.analysis
        tags = ["ClipCrafter","CanalPropra","Valorant","ValorantBrasil",
                "shorts","clipe","tentando evoluir","fercami gameplay"]
        if a.event_type and a.event_type != "highlight":
            tags.append(a.event_type.lower().replace(" ",""))
        if a.agent:
            tags.extend([a.agent, f"{a.agent}Valorant", f"{a.agent}main"])
        if a.map_name:
            tags.append(a.map_name)
        if a.weapon:
            tags.extend([a.weapon, f"{a.weapon}Valorant"])
        if a.kill_count >= 3:
            tags.append(f"{a.kill_count}k")
        if a.is_ace:
            tags.extend(["ace","acevalorant","1v5"])
        tags.extend(["jogadas valorant","melhores momentos","gameplay"])

        cta = (
            f"INSCREVA-SE no CanalPropra para mais momentos INSANOS de Valorant!\n"
            f"Comenta qual dessas jogadas foi a melhor!\n"
            f"Ative o sininho para nao perder os proximos clipes!\n\n"
        )
        event_tag = f"#{a.event_type.replace(' ','')}" if a.event_type and a.event_type != "highlight" else "#highlight"
        desc = (
            f"Melhores momentos de Valorant! Jogadas insanas, aces, clutches e muito mais.\n"
            f"Gameplay legendado com transcricao real.\n\n"
            f"{cta}"
            f"#Valorant #ValorantBrasil {event_tag} "
            f"#ClipCrafter #CanalPropra #Shorts #Gameplay\n"
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
