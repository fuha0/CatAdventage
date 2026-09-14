# -*- coding: utf-8 -*-
"""长期冒险（大于 3 天）的计划、途中事件与来信。

短期探险最长 30 分钟，结算方式是「每 5 分钟一个事件」。长期冒险按天推进，
不可能照搬那套节奏（一天 = 288 个槽位，逐条结算会卡死界面、也会把活力扣光）。
所以这里换一套模型：

- 计划（plan）只记录「什么时候出发、去多久、预计什么时候回来」，
  存进存档的 game.adventure，重启后据此继续推进，不丢进度；
- 推进（settle）以「天」为单位：每过一天结算一次当天的基础收获、
  一次途中随机事件，并按概率寄一封信回家；
- 途中事件的随机数由 plan 里的 seed + 天数派生，所以「同一天」无论当时
  在不在线、有没有重启过，结算结果都一样（可复现，不会靠重启刷收益）。

数值口径：长期冒险是挂机内容，日收益明显低于「手动刷 30 分钟」，
大约是每天 6~8 次短途探险的量，属于用时间换省心的折中。
"""
import random

from .inventory import InventoryService

# 超过这个天数就算「长期冒险」。
LONG_ADVENTURE_THRESHOLD_DAYS = 3
# 可选的长冒险档位（天）。
LONG_EXPLORE_DAYS = (4, 7, 14, 30)
# 一天按 1440 分钟算。
MINUTES_PER_DAY = 24 * 60
# 途中随机事件每天最多触发几次（再多也没意义，一天就一次结算）。
MAX_EVENTS_PER_DAY = 1
# 途中事件触发概率、寄信概率。
DAILY_EVENT_CHANCE = 0.45
DAILY_LETTER_CHANCE = 0.32
# 长期冒险每天的情绪消耗（猫咪在外面久了会想家）。
LONG_ADVENTURE_EMOTION_LOSS_PER_DAY = 2
# 每天基础收获相对地区配置的浮动范围。
DAILY_VARIANCE = (0.85, 1.15)


def is_long_adventure(minutes):
    """给定时长是否属于长期冒险（大于 3 天）。"""
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return False
    return minutes > LONG_ADVENTURE_THRESHOLD_DAYS * MINUTES_PER_DAY


def region_supports_long_adventure(region):
    """该地区是否支持长期冒险。

    不适用的两类：风和平原（不耗面包，长住没意义）和尚未实装的地区
    （没有日收益口径，进去只会空转）。
    """
    if not isinstance(region, dict):
        return False
    if region.get('fallback'):
        return False
    if region.get('long_xp_per_day'):
        return True
    try:
        return int(region.get('xp_per_min_max', 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def days_to_minutes(days):
    """天 → 分钟。"""
    return max(1, int(days)) * MINUTES_PER_DAY


def minutes_to_days(minutes):
    """分钟 → 整天数（向上取整，用于反推档位）。"""
    try:
        minutes = max(0, int(minutes))
    except (TypeError, ValueError):
        return 0
    return int((minutes + MINUTES_PER_DAY - 1) // MINUTES_PER_DAY)


def new_plan(region_id, days, now, seed=None):
    """构造一份长期冒险计划（写入存档 game.adventure 的内容）。

    now 为 epoch 秒。started_at / ends_at 都存绝对时间，重启后直接和当前
    时间比较即可知道「过了几天、还差多久」，不需要额外的计时器状态。
    """
    days = max(1, int(days))
    minutes = days_to_minutes(days)
    now = float(now)
    seed = int(seed if seed is not None else random.randrange(1, 2 ** 31 - 1))
    return {
        'active': True,
        'region': str(region_id),
        'days': days,
        'minutes': minutes,
        'started_at': now,
        'ends_at': now + minutes * 60,
        'seed': seed,
        'bread_cost': 0,
        'settled_days': 0,
        'letters_sent': 0,
        'pending_lines': [],
    }


def elapsed_days(plan, now):
    """计划已完整过去的天数（截到计划天数）。"""
    if not isinstance(plan, dict) or not plan.get('active'):
        return 0
    days = max(1, int(plan.get('days', 1) or 1))
    try:
        started_at = float(plan.get('started_at', 0) or 0)
    except (TypeError, ValueError):
        return 0
    passed = max(0.0, float(now) - started_at)
    return max(0, min(days, int(passed // (MINUTES_PER_DAY * 60))))


def remaining_minutes(plan, now):
    """距离计划结束还剩多少分钟（不足 5 分钟的零头向上取整到 5）。"""
    if not isinstance(plan, dict) or not plan.get('active'):
        return 0
    try:
        ends_at = float(plan.get('ends_at', 0) or 0)
    except (TypeError, ValueError):
        return 0
    remaining = max(0.0, ends_at - float(now))
    return int((remaining / 300.0) + 0.9999) * 5 if remaining > 0 else 0


def remaining_text(plan, now):
    """剩余时间的人类可读文本，例如「2 天 5 小时」「约 40 分钟」。"""
    minutes = remaining_minutes(plan, now)
    if minutes <= 0:
        return '即将归来'
    days, rest = divmod(minutes, MINUTES_PER_DAY)
    hours = rest // 60
    if days:
        return f'{days} 天 {hours} 小时' if hours else f'{days} 天'
    if hours:
        return f'{hours} 小时'
    return f'约 {minutes} 分钟'


def sanitize_plan(raw, region_keys):
    """把存档里读出的计划清洗成可用字典；不合法时返回空字典。"""
    if not isinstance(raw, dict) or not raw.get('active'):
        return {}
    region = str(raw.get('region', '') or '')
    if region not in region_keys:
        return {}
    try:
        days = max(1, int(raw.get('days', 1) or 1))
        started_at = float(raw.get('started_at', 0) or 0)
        ends_at = float(raw.get('ends_at', 0) or 0)
    except (TypeError, ValueError):
        return {}
    if started_at <= 0 or ends_at <= started_at:
        return {}
    try:
        seed = int(raw.get('seed', 0) or 0)
    except (TypeError, ValueError):
        seed = 0
    try:
        settled = max(0, min(days, int(raw.get('settled_days', 0) or 0)))
    except (TypeError, ValueError):
        settled = 0
    try:
        bread_cost = max(0, int(raw.get('bread_cost', 0) or 0))
    except (TypeError, ValueError):
        bread_cost = 0
    try:
        letters_sent = max(0, int(raw.get('letters_sent', 0) or 0))
    except (TypeError, ValueError):
        letters_sent = 0
    pending = raw.get('pending_lines')
    if not isinstance(pending, list):
        pending = []
    return {
        'active': True,
        'region': region,
        'days': days,
        'minutes': days_to_minutes(days),
        'started_at': started_at,
        'ends_at': ends_at,
        'seed': seed,
        'bread_cost': bread_cost,
        'settled_days': settled,
        'letters_sent': letters_sent,
        'pending_lines': [str(line) for line in pending],
    }


# ---------- 途中随机事件 ----------
# 事件写成 reward / penalty 文本，语法与事件簿一致，结算时复用
# AdventureService.apply_reward（见 adventure.py）。
# 长期冒险不按 5 分钟槽位扣血，所以这里出现的「生命」只作叙事用。
LONG_ADVENTURE_EVENTS = (
    {
        'id': 'caravan',
        'name': '顺路的商队',
        'regions': {2, 3},
        'text': '猫咪搭上了一支往南走的商队，帮人看了两天骡子，换来一顿热饭。',
        'reward': '金币+45',
    },
    {
        'id': 'old_ruins',
        'name': '半埋的遗迹',
        'regions': {2, 3},
        'text': '在一段塌掉的石墙下面，猫咪刨出了半只锈掉的箱子。',
        'reward': '宝藏×1',
    },
    {
        'id': 'stray_kitten',
        'name': '同行的小猫',
        'regions': {2, 3},
        'text': '路上捡到一只跟脚的小猫，猫咪把它送到了下一个村子。',
        'reward': '经验+120',
    },
    {
        'id': 'storm',
        'name': '连夜的暴雨',
        'regions': {2, 3},
        'text': '暴雨下了整夜，猫咪缩在树根底下，背包里的干粮受潮了。',
        'penalty': '金币-30',
    },
    {
        'id': 'sprained',
        'name': '崴了的脚',
        'regions': {2, 3},
        'text': '跳过一道石缝的时候崴了一下，猫咪蹲在路边缓了半天。',
        'penalty': '经验-60',
    },
    {
        'id': 'hot_spring',
        'name': '山谷里的温泉',
        'regions': {2, 3},
        'text': '顺着热气找到一潭温泉，猫咪泡到手都皱了才肯出来。',
        'reward': '金币+20，经验+80',
    },
    {
        'id': 'lost_way',
        'name': '绕远的路',
        'regions': {2, 3},
        'text': '照着星星走，结果还是绕了一个大圈，好在路上摘了不少草药。',
        'reward': '绿草药×2',
    },
    {
        'id': 'ore_vein',
        'name': '露头的矿脉',
        'regions': {3},
        'text': '灰石谷的断层里露着一线矿脉，猫咪敲了两块揣进兜里。',
        'reward': '矿石×1，燧石×1',
    },
    {
        'id': 'wind_hunt',
        'name': '乘风狩猎',
        'regions': {2, 3},
        'text': '借着一阵上升气流，猫咪从高处扑到了猎物，回来时尾巴翘得老高。',
        'reward': '兽肉×1，经验+90',
    },
    {
        'id': 'mudslide',
        'name': '塌方的坡',
        'regions': {2, 3},
        'text': '半面山坡滑了下来，猫咪连滚带爬地躲开，丢了些捡来的零碎。',
        'penalty': '金币-40',
    },
)

# ---------- 来信模板 ----------
# 每封信由「问候 + 见闻 + 落款」拼成；见闻会优先引用当天真正发生的事。
LETTER_GREETINGS = (
    '主人，见字如面。',
    '给你的信，我写了两遍。',
    '这边一切都好，真的。',
    '不知道家里下雨了没有。',
    '今天是出门的第 {day} 天啦。',
)
LETTER_SIGNATURES = (
    '——你的猫咪，{name}',
    '——{name}，趴在树杈上写的',
    '——{name}（爪印）',
    '——想你了，{name}',
    '——{name}，于{region}',
)
LETTER_SEEINGS = (
    '这里的白天很长，风也不大，我每天走一小段路，晚上找个背风的地方睡。',
    '路上遇到的人都很好，给了我不少指点的方向，就是干粮吃得比想象中快。',
    '营地旁边有条小溪，水凉得很，我在那儿学会了用石头压鱼。',
    '昨天爬上了一处高坡，回头能看见很远的地方，忽然有点想家里的窗台。',
    '今天没什么特别的事，摘了些草，数了数钱袋，一切照旧。',
    '我遇见一只同路的猫，它教我怎么看云判断明天要不要赶路。',
    '这边的星星比家里的亮，躺着看了一会儿就睡着了。',
)


class LongAdventureService:
    """按天推进长期冒险，产出收获、途中事件与来信。"""

    def __init__(self, items, regions, rng=None):
        self.items = items
        self.regions = regions
        self.rng = rng or random
        self.item_by_name = {
            data.get('name'): item_id
            for item_id, data in items.items()
            if data.get('name')
        }

    # ---------- 数值口径 ----------

    def daily_base(self, region_id, level):
        """当天的基础经验与金币（不含途中事件）。

        地区配置里 `long_xp_per_day` / `long_gold_per_day` 是主口径；
        没配的地区退回「短途 30 分钟的 xp_per_min 口径 × 8 次」。
        """
        region = self.regions.get(str(region_id)) or {}
        try:
            level = max(1, int(level))
        except (TypeError, ValueError):
            level = 1
        xp_per_day = region.get('long_xp_per_day')
        if xp_per_day is None:
            xp_min = int(region.get('xp_per_min_min', 24) or 24)
            xp_max = int(region.get('xp_per_min_max', 28) or 28)
            xp_per_day = ((xp_min + xp_max) // 2) * 30 * 8
        gold_per_day = region.get('long_gold_per_day')
        if gold_per_day is None:
            gold_per_day = 120
        try:
            xp_per_day = max(1, int(xp_per_day))
            gold_per_day = max(0, int(gold_per_day))
        except (TypeError, ValueError):
            xp_per_day, gold_per_day = 6000, 120
        return xp_per_day, gold_per_day

    def bread_cost(self, region_id, days):
        """长冒险的面包消耗：按天算「补给包」，和短途的每 5 分钟 1 个不同。"""
        region = self.regions.get(str(region_id)) or {}
        try:
            per_day = max(0, int(region.get('long_bread_per_day', 2) or 0))
        except (TypeError, ValueError):
            per_day = 2
        return per_day * max(1, int(days))

    def day_rng(self, plan, day_index):
        """派生「第 day_index 天」的随机数发生器（可复现）。"""
        seed = int(plan.get('seed', 0) or 0)
        return random.Random(seed * 131 + int(day_index) * 977 + 17)

    # ---------- 单日结算 ----------

    def settle_day(self, plan, day_index, state, inventory, treasures,
                   treasure_factory, apply_reward, send_letter_fn):
        """结算计划里的第 day_index 天（1 起算）。

        apply_reward(text, scale) 由调用方给出，用于复用事件簿的奖励解析；
        send_letter_fn(title, body) 用于寄信。返回该天的结算详情。
        """
        region_id = str(plan.get('region', '1'))
        region = self.regions.get(region_id) or {}
        rng = self.day_rng(plan, day_index)
        base_xp, base_gold = self.daily_base(region_id, state.level)

        low, high = DAILY_VARIANCE
        xp = max(0, int(round(base_xp * rng.uniform(low, high))))
        gold = max(0, int(round(base_gold * rng.uniform(low, high))))

        detail = {
            'day': int(day_index),
            'region_id': region_id,
            'region_name': region.get('name', '远方'),
            'xp': xp,
            'gold': gold,
            'items': {},
            'treasures': [],
            'lines': [],
            'letter': None,
        }

        # 途中随机事件：每天最多 MAX_EVENTS_PER_DAY 次。
        event = None
        for _ in range(MAX_EVENTS_PER_DAY):
            if rng.random() >= DAILY_EVENT_CHANCE:
                continue
            pool = [item for item in LONG_ADVENTURE_EVENTS
                    if not item.get('regions')
                    or int(region_id) in set(item.get('regions'))]
            if not pool:
                continue
            candidate = rng.choice(pool)
            text = candidate.get('reward') or candidate.get('penalty') or ''
            if not text:
                continue
            reward_text = candidate.get('reward') or ''
            penalty_text = candidate.get('penalty') or ''
            # 奖励与惩罚分别结算：奖励全额，惩罚只按 40% 计（挂机内容惩罚别太重）。
            applied = {
                'xp': 0, 'gold_delta': 0, 'hp_delta': 0,
                'parts': [], 'treasures': [], 'inventory_delta': {},
            }
            for source, scale in ((reward_text, 1.0), (penalty_text, 0.4)):
                if not source:
                    continue
                part = apply_reward(source, scale)
                applied['xp'] += part['xp']
                applied['gold_delta'] += part['gold_delta']
                applied['treasures'].extend(part['treasures'])
                for item_id, count in part['inventory_delta'].items():
                    applied['inventory_delta'][item_id] = (
                        applied['inventory_delta'].get(item_id, 0) + count)
                applied['parts'].extend(part['parts'])
            xp += applied['xp']
            gold += applied['gold_delta']
            detail['treasures'].extend(applied['treasures'])
            for item_id, count in applied['inventory_delta'].items():
                detail['items'][item_id] = (
                    detail['items'].get(item_id, 0) + count)
            event = {
                'name': candidate.get('name', '途中见闻'),
                'text': str(candidate.get('text', '')),
                'parts': list(applied['parts']),
            }
            detail['lines'].append(event)
            break

        detail['xp'] = max(0, xp)
        detail['gold'] = max(0, gold)

        if rng.random() < DAILY_LETTER_CHANCE:
            detail['letter'] = self.build_letter(
                plan, day_index, region, event, send_letter_fn)
            if detail['letter']:
                # 寄出的信数记在计划里：重启后归来时统计才不会漏掉。
                try:
                    plan['letters_sent'] = int(plan.get('letters_sent', 0) or 0) + 1
                except (TypeError, ValueError):
                    plan['letters_sent'] = 1
        return detail

    # ---------- 来信 ----------

    def build_letter(self, plan, day_index, region, event, send_letter_fn):
        """生成并投递一封来信，返回 {'title', 'body'}（投递失败返回 None）。"""
        if send_letter_fn is None:
            return None
        rng = self.day_rng(plan, day_index)
        region_name = region.get('name', '远方')
        title = f'{region_name}的来信 · 第{day_index}天'
        lines = [rng.choice(LETTER_GREETINGS).replace('{day}', str(day_index))]
        if event is not None:
            lines.append('')
            lines.append('「' + str(event.get('text') or '') + '」')
            if event.get('parts'):
                lines.append('（带回来的东西：' + '、'.join(event['parts']) + '）')
        else:
            lines.append('')
            lines.append(rng.choice(LETTER_SEEINGS))
        lines.append('')
        lines.append('别担心我，我知道回家的路。')
        body = '\n'.join(lines)
        letter_id = send_letter_fn(title, body)
        if not letter_id:
            return None
        return {'id': letter_id, 'title': title, 'body': body}

    # ---------- 批量推进 ----------

    def pending_days(self, plan):
        """计划里「已经过完但还没结算」的天数列表。"""
        total = max(1, int(plan.get('days', 1) or 1))
        settled = max(0, int(plan.get('settled_days', 0) or 0))
        return list(range(settled + 1, total + 1))

    def settle_days(self, plan, days, state, inventory, treasures,
                    treasure_factory, apply_reward, send_letter_fn,
                    on_day=None):
        """按顺序结算若干天，返回 [(day_index, detail), ...]。"""
        results = []
        for day_index in days:
            detail = self.settle_day(
                plan, day_index, state, inventory, treasures,
                treasure_factory, apply_reward, send_letter_fn)
            plan['settled_days'] = max(
                int(plan.get('settled_days', 0) or 0), int(day_index))
            results.append((day_index, detail))
            if on_day is not None:
                on_day(day_index, detail)
        return results


def apply_item_rewards(items, inventory, item_counts):
    """把 {物品名: 数量} 或 {物品键: 数量} 落到仓库，返回 {物品键: 实际数量}。"""
    item_by_name = {
        data.get('name'): item_id
        for item_id, data in items.items()
        if data.get('name')
    }
    granted = {}
    for key, count in (item_counts or {}).items():
        item_id = key if key in items else item_by_name.get(key)
        if item_id is None:
            continue
        info = items.get(item_id) or {}
        max_count = (1 if info.get('category') in (
            '\u5934\u9970', '\u670d\u88c5', '\u9970\u54c1', '\u4e66\u7c4d')
            else None)
        actual = InventoryService.add(
            inventory, item_id, max(1, int(count)), max_count=max_count)
        if actual:
            granted[item_id] = granted.get(item_id, 0) + actual
    return granted