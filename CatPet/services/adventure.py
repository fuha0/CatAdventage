import random
import re
from .inventory import InventoryService


class AdventureService:
    def __init__(self, items, recommended_levels, quality_names,
                 rng=None, success_levels=None, max_success=0.8):
        self.items = items
        self.recommended_levels = recommended_levels
        self.quality_names = quality_names
        self.rng = rng or random
        self.success_levels = dict(success_levels or {})
        self.max_success = max(0.2, min(0.8, float(max_success)))
        self.success_levels = dict(success_levels or {})
        self.max_success = max(0.2, min(0.8, float(max_success)))
        self.item_by_name = {
            data.get('name'): item_id
            for item_id, data in items.items()
            if data.get('name')
        }

    def success_chance(self, level, difficulty, region_id=1):
        try:
            region_number = int(region_id)
        except (TypeError, ValueError):
            region_number = 1
        required_level = max(1, int(self.success_levels.get(region_number, 30)))
        ratio = max(1, int(level)) / float(required_level)
        return max(0.2, min(self.max_success, ratio))

    @staticmethod
    def personalize_description(text, state):
        name = str(getattr(state, 'cat_name', '') or '猫猫').strip() or '猫猫'
        return str(text).replace('你', name)

    def event_damage(self, state, region_id, severity, difficulty):
        try:
            region_number = int(region_id)
        except (TypeError, ValueError):
            region_number = 1
        difficulty = max(1, int(difficulty))
        severity = max(1, int(severity))
        recommended = self.recommended_levels.get(region_number, 15)
        level = max(1, int(state.level))
        severity_factor = max(0.75, severity / 2.0)
        base = difficulty * self.rng.uniform(6.0, 8.5) * severity_factor
        if level < recommended:
            level_factor = 1.0 + min(0.9, (recommended - level) * 0.08)
        else:
            level_factor = max(0.35, 1.0 - (level - recommended) * 0.04)
        damage = max(1, round(base * level_factor))
        return min(damage, max(1, round(state.max_hp * 0.45)))

    def apply_reward(self, text, state, inventory, treasures,
                     treasure_factory, region_id=1, difficulty=1):
        result = {
            'xp': 0, 'gold_delta': 0, 'hp_delta': 0,
            'parts': [], 'treasures': [], 'inventory_delta': {},
        }
        if not text:
            return result
        text = str(text).strip()
        if not text or text.startswith('无'):
            return result

        for raw in re.split(r'[，,；;、]+', text):
            token = raw.strip()
            if not token:
                continue
            match = re.fullmatch(
                r'(经验|金币|生命|活力)\s*([+＋\-－])\s*(\d+)', token)
            if match:
                kind = match.group(1)
                sign = -1 if match.group(2) in '－-' else 1
                amount = sign * int(match.group(3))
                if kind == '经验':
                    if amount > 0:
                        result['xp'] += amount
                        result['parts'].append(f'经验+{amount}')
                    continue
                if kind == '金币':
                    before = state.gold
                    state.gold = max(0, state.gold + amount)
                    actual = state.gold - before
                    result['gold_delta'] += actual
                    if actual:
                        result['parts'].append(f'金币{actual:+d}')
                    continue
                before = state.hp
                if amount < 0:
                    damage = self.event_damage(
                        state, region_id, abs(amount), difficulty)
                    state.hp = max(0, state.hp - damage)
                else:
                    state.hp = min(state.max_hp, state.hp + amount)
                actual = state.hp - before
                result['hp_delta'] += actual
                if actual:
                    result['parts'].append(f'活力{actual:+d}')
                continue

            match = re.fullmatch(r'(.+?)\s*[×xX*]\s*(\d+)', token)
            if match:
                item_name = match.group(1).strip()
                if item_name == '宝藏':
                    count = int(match.group(2))
                    for _ in range(max(1, count)):
                        treasure = treasure_factory(region_id)
                        if treasure is None:
                            continue
                        treasures.append(treasure)
                        result['treasures'].append(treasure)
                        quality_name = self.quality_names.get(
                            treasure['quality'], '普通')
                        display = treasure['prefix'] + treasure['name']
                        result['parts'].append(
                            f'{display}（{quality_name}，{treasure["value"]}G）')
                    if not result['treasures']:
                        result['parts'].append('宝藏生成失败')
                    continue
                item_id = self.item_by_name.get(item_name)
                if item_id is not None:
                    count = int(match.group(2))
                    info = self.items.get(item_id) or {}
                    max_count = (1 if info.get('category') in (
                        '\u5934\u9970', '\u670d\u88c5', '\u9970\u54c1', '\u4e66\u7c4d') else None)
                    actual = InventoryService.add(
                        inventory, item_id, count, max_count=max_count)
                    if actual:
                        result['inventory_delta'][item_id] = (
                            result['inventory_delta'].get(item_id, 0) + actual)
                        result['parts'].append(f'{item_name}{actual:+d}')
                    continue

            match = re.fullmatch(r'(.+?)\s*([+＋\-－])\s*(\d+)', token)
            if match:
                item_name = match.group(1).strip()
                item_id = self.item_by_name.get(item_name)
                if item_id is not None:
                    sign = -1 if match.group(2) in '－-' else 1
                    delta = sign * int(match.group(3))
                    info = self.items.get(item_id) or {}
                    max_count = (1 if info.get('category') in (
                        '\u5934\u9970', '\u670d\u88c5', '\u9970\u54c1', '\u4e66\u7c4d') else None)
                    actual = InventoryService.change(
                        inventory, item_id, delta, max_count=max_count)
                    if actual:
                        result['inventory_delta'][item_id] = (
                            result['inventory_delta'].get(item_id, 0) + actual)
                        result['parts'].append(f'{item_name}{actual:+d}')
                    continue
            result['parts'].append(f'{token}(未识别)')
        return result

    def resolve(self, events, region_id, minutes, state, inventory,
                treasures, treasure_factory, allow_early_fail=True,
                early_fail_hp=10):
        result = {
            'xp': 0, 'gold_delta': 0, 'hp_delta': 0,
            'inventory_delta': {}, 'treasures': [],
            'failed_early': False, 'lines': [],
            'average_success': 0.0,
        }
        chances = []
        try:
            region_number = int(region_id)
        except (TypeError, ValueError):
            region_number = 1
        pool = [event for event in events
                if region_number in event.get('regions', set())]
        if not pool:
            result['lines'].append('事件簿中没有该地区可用事件')
            return result

        for minute_no in range(1, max(1, int(minutes)) + 1):
            event = self.rng.choice(pool)
            chance = self.success_chance(
                state.level, event['difficulty'], region_number)
            chances.append(chance)
            passed = self.rng.random() < chance
            if passed:
                description = event['success_desc']
                reward_text = event['success_reward']
                state_text = '成功'
            else:
                failure_text = event['failure_desc']
                options = [part.strip()
                           for part in re.split(r'[/／]', failure_text)
                           if part.strip()]
                description = (self.rng.choice(options)
                               if options else failure_text)
                reward_text = event['failure_penalty']
                state_text = '失败'
            description = self.personalize_description(description, state)
            applied = self.apply_reward(
                reward_text, state, inventory, treasures,
                treasure_factory, region_number, event['difficulty'])
            result['xp'] += applied['xp']
            result['gold_delta'] += applied['gold_delta']
            result['hp_delta'] += applied['hp_delta']
            result['treasures'].extend(applied['treasures'])
            for item_id, delta in applied['inventory_delta'].items():
                result['inventory_delta'][item_id] = (
                    result['inventory_delta'].get(item_id, 0) + delta)
            detail = '，'.join(applied['parts'])
            if not detail:
                detail = '无额外奖励' if passed else '无额外惩罚'
            result['lines'].append(
                f'{minute_no}分钟 · {event["name"]}｜{state_text}'
                f'（{chance:.0%}）：{description}；{detail}')
            if allow_early_fail and state.hp <= int(early_fail_hp):
                result['failed_early'] = True
                result['lines'].append(
                    f'活力降至 {int(early_fail_hp)} 及以下，探险提前结束！')
                break
        if chances:
            result['average_success'] = sum(chances) / len(chances)
        return result
