"""Viral optimizer v2 — research-backed parameter suggestions"""
import json, os, math
from typing import Dict, List, Optional, Tuple

OPTIMAL_DURATION = (25, 55)  # 30-60s is sweet spot, median 37s
OPTIMAL_SILENCE = 10  # max % silence before penalty
OPTIMAL_ENERGY_PEAKS = 6  # avg per high-scoring clip
OPTIMAL_SCENE_CUTS = 8  # avg per high-scoring clip

class ViralOptimizer:
    def __init__(self, features_path: str = None, perf_path: str = None):
        self.features_path = features_path or os.path.expanduser(
            "~/.clipcrafter/clip_features.json")
        self.perf_path = perf_path or os.path.expanduser(
            "~/.clipcrafter/clip_performance.json")
        self.features = self._load_json(self.features_path)
        self.performance = self._load_json(self.perf_path)

    def _load_json(self, path: str) -> dict:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def suggest_params(self, clip_features: dict = None) -> dict:
        """Suggest export parameters based on research data + our history."""
        if clip_features:
            dur = clip_features.get("duration", 30)
            silence = clip_features.get("silence_pct", 5)
            excitement = clip_features.get("excitement", 50)
        else:
            dur, silence, excitement = 30, 5, 50

        suggestions = {
            "target_duration": self._suggest_duration(dur, silence),
            "zoom_rate": 0.00012 if excitement > 60 else 0.00018,
            "energy_boost": min(1.0, excitement / 80),
            "hook_style": self._suggest_hook_style(excitement),
            "loop_count": 1,
        }

        # Very short clips (<15s) benefit from looping
        if dur < 15:
            suggestions["loop_count"] = 2
            suggestions["target_duration"] = (dur, dur * 2)

        return suggestions

    def _suggest_duration(self, dur: float, silence: float) -> Tuple[float, float]:
        base_min, base_max = OPTIMAL_DURATION
        if silence > OPTIMAL_SILENCE:
            base_max = min(base_max, 35)  # shorter if too much silence
        if dur < base_min:
            base_min = dur  # don't stretch a short clip
        return (base_min, base_max)

    def _suggest_hook_style(self, excitement: float) -> str:
        if excitement > 75:
            return "stakes"
        elif excitement > 60:
            return "question"
        elif excitement > 45:
            return "action_first"
        return "bold_statement"

    def get_virality_report(self, clip_features: dict) -> str:
        """Generate a human-readable virality assessment."""
        dur = clip_features.get("duration", 30)
        silence = clip_features.get("silence_pct", 0)
        peaks = clip_features.get("energy_peaks", 0)
        scene_cuts = clip_features.get("scene_cuts", 0)
        excitement = clip_features.get("excitement", 0)
        virality = clip_features.get("virality_score", 50)

        issues = []
        if dur < 20:
            issues.append(f"curto ({dur}s, ideal 25-55s)")
        elif dur > 60:
            issues.append(f"longo ({dur}s, ideal 25-55s)")
        if silence > OPTIMAL_SILENCE:
            issues.append(f"muito silencio ({silence}%)")
        if peaks < 3:
            issues.append(f"poucos picos de energia ({peaks})")
        if scene_cuts < 4:
            issues.append(f"poucos cortes ({scene_cuts})")

        report = f"Score de viralidade: {virality}/100\n"
        if issues:
            report += f"Pontos fracos: {', '.join(issues)}\n"
        else:
            report += "Clip bem otimizado!\n"
        report += f"Duracao: {dur}s (ideal 25-55s)\n"
        report += f"Excitement: {excitement}/100\n"
        report += f"Picos de energia: {peaks}\n"
        report += f"Cortes/dinamica: {scene_cuts}"
        return report
