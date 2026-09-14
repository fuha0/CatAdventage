# -*- coding: utf-8 -*-
"""玩家数据统计服务。"""

DEFAULT_STATS = {
    "gold_earned": 0,
    "exp_earned": 0,
    "purchase_count": 0,
    "cat_click_count": 0,
    "online_seconds": 0,
    "gold_zero_seen": 0,
    "emotion_max": 50,
    "emotion_min": 50,
    "emotion_exact10": 0,
    "hp_min": 100,
    "adventure_early_fail_count": 0,
    "treasure_sold_count": 0,
    "adventure_count": 0,
    "forest_adventure_count": 0,
    "plain_adventure_count": 0,
    "valley_adventure_count": 0,
    "plain_clear_count": 0,
    "valley_clear_count": 0,
    "forest_clear_count": 0,
    "adventure_minutes": 0,
    "max_feed_amount": 0,
    "mushroom_damage_count": 0,
    "alchemy_craft_count": 0,
    "green_potion_used": 0,
    "purchased_items": {},
}


class StatsService:
    @staticmethod
    def _minimum_earned_exp(state):
        """旧存档未记录总经验时，用升级曲线估算历史最低获得量。"""
        try:
            level = max(1, int(getattr(state, "level", 1)))
            current = max(0, int(getattr(state, "exp", 0)))
        except (TypeError, ValueError):
            level, current = 1, 0
        return current + sum(
            int(round(10 * (value ** 1.4))) for value in range(1, level))

    @staticmethod
    def ensure(state):
        if not isinstance(getattr(state, "stats", None), dict):
            state.stats = dict(DEFAULT_STATS)
        for key, default in DEFAULT_STATS.items():
            if key == "exp_earned" and key not in state.stats:
                state.stats[key] = StatsService._minimum_earned_exp(state)
                continue
            if key == "purchased_items":
                raw = state.stats.get(key, default)
                if not isinstance(raw, dict):
                    raw = {}
                cleaned = {}
                for item_id, count in raw.items():
                    try:
                        cleaned[str(item_id)] = max(0, int(count))
                    except (TypeError, ValueError):
                        continue
                state.stats[key] = cleaned
                continue
            try:
                state.stats[key] = max(0, int(state.stats.get(key, default)))
            except (TypeError, ValueError):
                state.stats[key] = default
        return state.stats

    @classmethod
    def record_gold_earned(cls, state, amount):
        amount = max(0, int(amount))
        if amount:
            cls.ensure(state)["gold_earned"] += amount

    @classmethod
    def record_exp_earned(cls, state, amount):
        amount = max(0, int(amount))
        if amount:
            cls.ensure(state)["exp_earned"] += amount

    @classmethod
    def record_purchase(cls, state, amount=1, item_id=None):
        amount = max(0, int(amount))
        if amount:
            stats = cls.ensure(state)
            stats["purchase_count"] += amount
            if item_id:
                stats["purchased_items"][str(item_id)] = (
                    stats["purchased_items"].get(str(item_id), 0) + amount)

    @classmethod
    def record_treasure_sale(cls, state, amount=1):
        amount = max(0, int(amount))
        if amount:
            cls.ensure(state)["treasure_sold_count"] += amount

    @classmethod
    def record_adventure(cls, state, region_id, minutes, early_fail=False):
        stats = cls.ensure(state)
        stats["adventure_count"] += 1
        stats["adventure_minutes"] += max(0, int(minutes))
        region_id = str(region_id)
        if region_id == "1":
            stats["plain_adventure_count"] += 1
            if not early_fail:
                stats["plain_clear_count"] += 1
        elif region_id == "2":
            stats["forest_adventure_count"] += 1
            if not early_fail:
                stats["forest_clear_count"] += 1
        elif region_id == "3":
            stats["valley_adventure_count"] += 1
            if not early_fail:
                stats["valley_clear_count"] += 1
        if early_fail:
            stats["adventure_early_fail_count"] += 1

    @classmethod
    def record_alchemy_craft(cls, state, amount=1):
        amount = max(0, int(amount))
        if amount:
            cls.ensure(state)["alchemy_craft_count"] += amount

    @classmethod
    def record_green_potion_use(cls, state):
        cls.ensure(state)["green_potion_used"] += 1

    @classmethod
    def record_feed(cls, state, item_id, amount, mushroom_damage=False):
        stats = cls.ensure(state)
        stats["max_feed_amount"] = max(
            stats["max_feed_amount"], max(0, int(amount)))
        if mushroom_damage:
            stats["mushroom_damage_count"] += 1

    @classmethod
    def sample_state(cls, state):
        stats = cls.ensure(state)
        gold = max(0, int(getattr(state, "gold", 0)))
        emotion = max(0, min(100, int(getattr(state, "emotion", 0))))
        hp = max(0, int(getattr(state, "hp", 0)))
        if gold == 0:
            stats["gold_zero_seen"] = 1
        stats["emotion_max"] = max(stats["emotion_max"], emotion)
        stats["emotion_min"] = min(stats["emotion_min"], emotion)
        if emotion == 10:
            stats["emotion_exact10"] = 1
        stats["hp_min"] = min(stats["hp_min"], hp)

    @classmethod
    def record_cat_click(cls, state, amount=1):
        amount = max(0, int(amount))
        if amount:
            cls.ensure(state)["cat_click_count"] += amount

    @classmethod
    def add_online_seconds(cls, state, seconds):
        seconds = max(0.0, float(seconds))
        if seconds:
            cls.ensure(state)["online_seconds"] += seconds

    @classmethod
    def summary(cls, state):
        stats = cls.ensure(state)
        return {
            "gold_earned": int(stats["gold_earned"]),
            "exp_earned": int(stats["exp_earned"]),
            "purchase_count": int(stats["purchase_count"]),
            "cat_click_count": int(stats["cat_click_count"]),
            "online_minutes": int(stats["online_seconds"] // 60),
            "online_seconds": int(stats["online_seconds"]),
            "gold_zero_seen": int(stats["gold_zero_seen"]),
            "emotion_max": int(stats["emotion_max"]),
            "emotion_min": int(stats["emotion_min"]),
            "emotion_exact10": int(stats["emotion_exact10"]),
            "hp_min": int(stats["hp_min"]),
            "adventure_early_fail_count": int(stats["adventure_early_fail_count"]),
            "treasure_sold_count": int(stats["treasure_sold_count"]),
            "adventure_count": int(stats["adventure_count"]),
            "forest_adventure_count": int(stats["forest_adventure_count"]),
            "plain_adventure_count": int(stats["plain_adventure_count"]),
            "valley_adventure_count": int(stats["valley_adventure_count"]),
            "plain_clear_count": int(stats["plain_clear_count"]),
            "valley_clear_count": int(stats["valley_clear_count"]),
            "forest_clear_count": int(stats["forest_clear_count"]),
            "adventure_minutes": int(stats["adventure_minutes"]),
            "max_feed_amount": int(stats["max_feed_amount"]),
            "mushroom_damage_count": int(stats["mushroom_damage_count"]),
            "alchemy_craft_count": int(stats["alchemy_craft_count"]),
            "green_potion_used": int(stats["green_potion_used"]),
            "purchased_items": dict(stats["purchased_items"]),
        }
