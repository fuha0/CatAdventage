from dataclasses import dataclass
import random


@dataclass
class TreasureSale:
    targets: list
    gain: int
    emotion_gain: int


class TreasureService:
    @staticmethod
    def generate(definitions, prefixes, next_uid, quality_cap,
                 prefix_grade_by_quality, rng=None,
                 quality_weights=None, quality_counts=None,
                 quality_caps=None):
        rng = rng or random
        weights = quality_weights or {}
        counts = quality_counts or {}
        caps = quality_caps or {}
        choices = []
        for definition in definitions or []:
            allowed = [q for q in definition.get('qualities', [])
                       if int(q) <= int(quality_cap)]
            for quality in allowed:
                quality = int(quality)
                cap = caps.get(quality)
                if cap is not None and counts.get(quality, 0) >= int(cap):
                    continue
                weight = max(0.0, float(weights.get(quality, 1.0)))
                if weight > 0:
                    choices.append((definition, quality, weight))
        if not choices or not prefixes:
            return None, int(next_uid)
        total = sum(choice[2] for choice in choices)
        roll = rng.uniform(0.0, total)
        running = 0.0
        definition, quality = choices[-1][0], choices[-1][1]
        for candidate_definition, candidate_quality, weight in choices:
            running += weight
            if roll <= running:
                definition, quality = candidate_definition, candidate_quality
                break
        grade = prefix_grade_by_quality.get(quality, 'D级')
        grade_prefixes = [p for p in prefixes if p.get('grade') == grade]
        if not grade_prefixes:
            return None, int(next_uid)
        prefix = rng.choice(grade_prefixes)
        value = max(
            1,
            round(int(definition.get('base_value', 1))
                  * float(prefix.get('multiplier', 1.0))),
        )
        uid = int(next_uid) + 1
        treasure = {
            'uid': uid,
            'name': definition.get('name', ''),
            'prefix': prefix.get('name', ''),
            'quality': quality,
            'base_value': int(definition.get('base_value', 1)),
            'value': value,
            'locked': False,
        }
        return treasure, uid

    @staticmethod
    def select_sale(treasures, targets, emotion_by_quality=None):
        emotion_by_quality = emotion_by_quality or {}
        selected = [t for t in targets if not t.get('locked', False)]
        gain = sum(max(0, int(t.get('value', 0))) for t in selected)
        emotion = sum(
            int(emotion_by_quality.get(int(t.get('quality', 1)), 0))
            for t in selected
        )
        return TreasureSale(selected, gain, emotion)
