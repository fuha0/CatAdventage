import random


class ProgressionService:
    @staticmethod
    def xp_to_next(level):
        return int(round(10 * (max(1, int(level)) ** 1.4)))

    @staticmethod
    def calculate_max_hp(level, strength, wisdom, agility):
        return max(
            1,
            100 + (max(1, int(level)) - 1) * 7
            + (int(strength) + int(wisdom) + int(agility)) * 2,
        )

    @staticmethod
    def regen_per_minute(max_hp):
        return max(1, (max(1, int(max_hp)) + 9) // 10)

    @staticmethod
    def recalculate_max_hp(state):
        old_max = max(1, int(state.max_hp))
        missing = max(0, old_max - int(state.hp))
        state.max_hp = ProgressionService.calculate_max_hp(
            state.level, state.strength, state.wisdom, state.agility)
        state.hp = max(0, min(state.max_hp, state.max_hp - missing))
        return state.max_hp

    @staticmethod
    def gain_level(state, rng=None):
        rng = rng or random
        state.level = max(1, int(state.level)) + 1
        attr = rng.choice(('strength', 'wisdom', 'agility'))
        setattr(state, attr, int(getattr(state, attr)) + 1)
        ProgressionService.recalculate_max_hp(state)
        return attr

    @staticmethod
    def gain_exp(state, amount, rng=None):
        amount = int(amount)
        if amount <= 0:
            return []
        state.exp = max(0, int(state.exp)) + amount
        gained = []
        while state.exp >= ProgressionService.xp_to_next(state.level):
            state.exp -= ProgressionService.xp_to_next(state.level)
            gained.append(ProgressionService.gain_level(state, rng))
        return gained
