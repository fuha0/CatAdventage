import random
import re
from .inventory import InventoryService


# 等级未达到地区最低要求时，事件成功率固定为这个值（不随等级和事件难度浮动）。
BELOW_MIN_LEVEL_CHANCE = 0.10
# 事件难度的取值区间（0.70~1.00），越接近 1 越难、成功率越低。
DIFFICULTY_MIN = 0.70
DIFFICULTY_MAX = 1.00


class AdventureService:
    def __init__(self, items, recommended_levels, quality_names,
                 rng=None, success_levels=None, max_success=0.95,
                 min_levels=None):
        self.items = items
        self.recommended_levels = recommended_levels
        self.quality_names = quality_names
        self.rng = rng or random
        self.success_levels = dict(success_levels or {})
        self.max_success = max(0.2, min(0.95, float(max_success)))
        # 各地区的最低准入等级：不满足时成功率固定为 BELOW_MIN_LEVEL_CHANCE。
        self.min_levels = dict(min_levels or {})
        self.item_by_name = {
            data.get('name'): item_id
            for item_id, data in items.items()
            if data.get('name')
        }

    @staticmethod
    def difficulty_factor(difficulty):
        """事件难度系数（0.70~1.00），作为成功率的最后一个乘数。"""
        try:
            value = float(difficulty)
        except (TypeError, ValueError):
            return DIFFICULTY_MAX
        return min(DIFFICULTY_MAX, max(0.1, value))

    def success_chance(self, level, difficulty, region_id=1):
        """事件成功率。

        - 等级低于该地区最低等级：固定 10%（不再按 20% 起算）。
        - 达到最低等级后：clamp(等级 / 满成功率等级, 20%, 95%)，再乘事件难度系数。
          事件难度仅在此处参与判定，不参与扣血。
        """
        try:
            region_number = int(region_id)
        except (TypeError, ValueError):
            region_number = 1
        level = max(1, int(level))
        min_level = max(1, int(self.min_levels.get(region_number, 1)))
        if level < min_level:
            return BELOW_MIN_LEVEL_CHANCE
        required_level = max(1, int(self.success_levels.get(region_number, 30)))
        ratio = level / float(required_level)
        base = max(0.2, min(self.max_success, ratio))
        return base * self.difficulty_factor(difficulty)

    @staticmethod
    def personalize_description(text, state):
        name = str(getattr(state, 'cat_name', '') or '猫猫').strip() or '猫猫'
        return str(text).replace('你', name)

    def event_damage(self, state, region_id, severity, difficulty=None):
        """按惩罚强度（severity）、地区和当前等级计算实际扣血。

        事件难度已不再参与扣血：难度原先的「放大伤害」作用已经折算进事件簿
        的「失败惩罚」数值本身（= 旧难度 × 原 severity），因此这里只按 severity
        计算，难度只管成功率。保留 difficulty 参数仅为兼容调用方签名。
        """
        try:
            region_number = int(region_id)
        except (TypeError, ValueError):
            region_number = 1
        try:
            severity = max(0.1, float(severity))
        except (TypeError, ValueError):
            severity = 1.0
        recommended = self.recommended_levels.get(region_number, 15)
        level = max(1, int(state.level))
        severity_factor = max(0.75, severity / 2.0)
        base = self.rng.uniform(6.0, 8.5) * severity_factor
        if level < recommended:
            level_factor = 1.0 + min(0.9, (recommended - level) * 0.08)
        else:
            level_factor = max(0.35, 1.0 - (level - recommended) * 0.04)
        damage = max(1, round(base * level_factor)) * 5
        return min(damage, max(1, int(state.max_hp)))

    def apply_reward(self, text, state, inventory, treasures,
                     treasure_factory, region_id=1, difficulty=1,
                     reward_scale=1.0, item_scale=1.0, hp_scale=1.0):
        """结算一段奖励/惩罚文本。

        reward_scale 用于「一个事件代表多个 5 分钟槽位」的情形（长期冒险按天
        结算）：经验/金币等比放大，物品与宝藏只按 item_scale 放大（避免几百倍
        爆仓），活力按 hp_scale 放大（长期冒险传 0，避免一天 288 次扣血）。
        """
        result = {
            'xp': 0, 'gold_delta': 0, 'hp_delta': 0,
            'parts': [], 'treasures': [], 'inventory_delta': {},
        }
        if not text:
            return result
        text = str(text).strip()
        if not text or text.startswith('无'):
            return result

        try:
            reward_scale = max(0.0, float(reward_scale))
        except (TypeError, ValueError):
            reward_scale = 1.0
        try:
            item_scale = max(0.0, float(item_scale))
        except (TypeError, ValueError):
            item_scale = 1.0
        try:
            hp_scale = max(0.0, float(hp_scale))
        except (TypeError, ValueError):
            hp_scale = 1.0

        for raw in re.split(r'[，,；;、]+', text):
            token = raw.strip()
            if not token:
                continue
            match = re.fullmatch(
                r'(经验|金币|生命|活力)\s*([+＋\-－])\s*(\d+(?:\.\d+)?)',
                token)
            if match:
                kind = match.group(1)
                sign = -1 if match.group(2) in '－-' else 1
                # 生命/活力允许小数（失败惩罚的数值已按旧的事件难度折算过）。
                amount = sign * float(match.group(3))
                if kind == '经验':
                    gained = int(round(amount * reward_scale))
                    if gained > 0:
                        result['xp'] += gained
                        result['parts'].append(f'经验+{gained}')
                    continue
                if kind == '金币':
                    scaled = int(round(amount * reward_scale))
                    before = state.gold
                    state.gold = max(0, state.gold + scaled)
                    actual = state.gold - before
                    result['gold_delta'] += actual
                    if actual:
                        result['parts'].append(f'金币{actual:+d}')
                    continue
                if hp_scale <= 0:
                    continue
                before = state.hp
                if amount < 0:
                    damage = self.event_damage(
                        state, region_id, abs(amount), difficulty)
                    damage = int(round(damage * hp_scale))
                    state.hp = max(0, state.hp - damage)
                else:
                    state.hp = min(
                        state.max_hp, state.hp + int(round(amount * hp_scale)))
                actual = state.hp - before
                result['hp_delta'] += actual
                if actual:
                    result['parts'].append(f'活力{actual:+d}')
                continue

            match = re.fullmatch(r'(.+?)\s*[×xX*]\s*(\d+)', token)
            if match:
                item_name = match.group(1).strip()
                if item_name == '宝藏':
                    count = int(round(int(match.group(2)) * item_scale))
                    for _ in range(max(0, count)):
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
                    continue
                item_id = self.item_by_name.get(item_name)
                if item_id is not None:
                    count = int(round(int(match.group(2)) * item_scale))
                    if count <= 0:
                        continue
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
                    delta = sign * int(round(int(match.group(3)) * item_scale))
                    if delta == 0:
                        continue
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
                early_fail_hp=10, event_count=None, reward_scale=1.0,
                item_scale=1.0, hp_scale=1.0, labeler=None):
        """按槽位抽取事件并逐条判定；默认每 5 分钟 1 个事件。

        event_count 可覆盖槽位数量（长期冒险按「天」结算时传入天数，并把
        reward_scale 设为每天对应的 5 分钟槽位数）；labeler(index) 可覆盖日志
        里的时间标签（长期冒险显示「第 n 天」）。
        """
        result = {
            'xp': 0, 'gold_delta': 0, 'hp_delta': 0,
            'inventory_delta': {}, 'treasures': [],
            'failed_early': False, 'failure_count': 0, 'lines': [],
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

        if event_count is None:
            event_count = max(1, int(minutes) // 5)
        else:
            try:
                event_count = max(1, int(event_count))
            except (TypeError, ValueError):
                event_count = max(1, int(minutes) // 5)
        for event_index in range(1, event_count + 1):
            if labeler is not None:
                slot_label = str(labeler(event_index))
            else:
                slot_label = f'{event_index * 5}分钟'
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
                result['failure_count'] += 1
            description = self.personalize_description(description, state)
            applied = self.apply_reward(
                reward_text, state, inventory, treasures,
                treasure_factory, region_number, event['difficulty'],
                reward_scale, item_scale, hp_scale)
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
                f'{slot_label} · {event["name"]}｜{state_text}'
                f'（{chance:.0%}）：{description}；{detail}')
            if allow_early_fail and state.hp <= int(early_fail_hp):
                result['failed_early'] = True
                result['lines'].append(
                    f'活力降至 {int(early_fail_hp)} 及以下，探险提前结束！')
                break
        if chances:
            result['average_success'] = sum(chances) / len(chances)
        return result
