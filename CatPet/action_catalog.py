# -*- coding: utf-8 -*-
"""动作目录：新增动作只需要登记一次；主体动作用 play，叠加动作用 play_overlay。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ActionSpec:
    id: str
    name: str
    layer: str
    priority: int
    handler: str | None = None
    channels: tuple = ()
    allowed_from: tuple = ()
    interrupts: tuple = ()
    interruptible: bool = True
    weight: float = 0.0
    cooldown_ms: int = 0
    exclusive: bool = True
    requires_book: str | None = None
    expression: str | None = None


DRAG_MODES = {1: 'wing_flap', 2: 'cling_to_mouse', 3: 'punch_mouse'}
DRAG_MODE_IDS = tuple(DRAG_MODES)


ACTION_LIST = (
    ActionSpec('idle', '待机', 'base', 0, None, ('body',),
               (), (), True, 0.0, 0, False),
    ActionSpec('walk', '走动', 'base', 10, 'start_walk',
               ('body', 'position'), ('idle',), ('idle',),
               True),
    ActionSpec('blink', '眨眼', 'overlay', 5, '_play_blink',
               ('eyes',), ('idle', 'walk'),
               (), True, 0.12),
    ActionSpec('ear', '动耳朵', 'overlay', 5, '_play_ear',
               ('ears',), ('idle', 'walk'),
               (), True, 0.34),
    ActionSpec('tail', '摇尾巴', 'overlay', 5, '_play_tail',
               ('tail',), ('idle', 'walk'),
               (), True, 0.26),
    # 喵一声：只换脸，所以是 overlay，走路时也能来一下。
    # 「换表情」动作已删除 —— 猫叫本身就带表情了，再单独换表情是重复。
    ActionSpec('meow', '喵一声', 'overlay', 7, '_play_meow',
               ('face',), ('idle', 'walk'),
               (), True, 0.16, 25000),
    # 主体类动作：要占住画面，所以是 interaction；和挠头一样会先停下走动
    ActionSpec('wave', '招手', 'interaction', 27, '_play_wave',
               ('body', 'hands'), ('idle',), ('idle', 'walk'),
               True, 0.12, 0, True),
    ActionSpec('lick', '舔手', 'interaction', 27, '_play_lick',
               ('body', 'hands', 'face'), ('idle',), ('idle', 'walk'),
               True, 0.12, 0, True),
    ActionSpec('scratch', '挠头', 'interaction', 30, '_play_scratch',
               ('body', 'hands'), ('idle',), ('idle', 'walk'),
               True, 0.12, 0, True),
    ActionSpec('jump', '跳远', 'interaction', 40, '_play_jump',
               ('body', 'hands', 'position'), ('idle',),
               ('idle', 'walk'), True, 0.06, 0, True, 'jump_guide'),
    ActionSpec('reach', '抓鼠标', 'interaction', 45, '_start_reach',
               ('hands', 'cursor'), ('idle',),
               ('idle', 'walk', 'scratch'), True, 0.0, 60000,
               True, 'pat_guide'),
    ActionSpec('drag', '拖动', 'system', 90, None,
               ('body', 'hands', 'position'), (), (), False),
    ActionSpec('climb', '攀爬', 'physics', 75, '_start_taskbar_climb',
               ('body', 'hands', 'position'), ('drag',), ('drag',),
               False),
    ActionSpec('fling', '甩飞', 'physics', 72, '_start_fling',
               ('body', 'hands', 'position'), ('drag',), ('drag',),
               False),
    ActionSpec('fall', '下落', 'physics', 80, '_begin_fall',
               ('body', 'hands', 'position'), ('fling', 'drag'),
               ('fling', 'drag'), False),
    ActionSpec('adventure_wave', '探险告别', 'interaction', 28,
               '_start_adventure_departure', ('body', 'hands'),
               ('idle',), ('idle', 'walk', 'scratch', 'reach'),
               False),
    ActionSpec('adventure_hop', '探险前跳', 'interaction', 29,
               None, ('body', 'hands', 'position'), (), (),
               False),
    ActionSpec('adventure_launch', '探险离场', 'interaction', 30,
               None, ('body', 'hands', 'position'), (), (),
               False),
    ActionSpec('expression_daily', '日常表情', 'expression', 0,
               None, ('face',), (), (), True, 0.0, 0, False,
               expression='daily'),
    ActionSpec('expression_click', '单击表情', 'expression', 30,
               None, ('face',), (), (), True, 0.0, 0, False,
               expression='click'),
    ActionSpec('expression_comfy', '无所谓喵', 'expression', 40,
               None, ('face',), (), (), True, 0.0, 0, False,
               expression='comfy'),
    ActionSpec('expression_jump', '跳跃蓄力表情', 'expression', 50,
               None, ('face',), (), (), True, 0.0, 0, False,
               expression='jump_brow'),
    ActionSpec('hospital', '住院', 'system', 100, '_enter_hospital',
               ('body', 'position'), (), (), False),
    ActionSpec('closing', '关闭程序', 'system', 110, None,
               ('body', 'position'), (), (), False),
)

ACTION_CATALOG = {spec.id: spec for spec in ACTION_LIST}

def get_action(action_id):
    return ACTION_CATALOG.get(action_id)


def choose_idle_action(value=None, books_enabled=None):
    import random
    books = set(books_enabled or ())
    candidates = [spec for spec in ACTION_LIST
                  if spec.weight > 0 and 'idle' in spec.allowed_from
                  and (not spec.requires_book
                       or spec.requires_book in books)]
    total = sum(max(0.0, spec.weight) for spec in candidates)
    if total <= 0:
        return ACTION_CATALOG['blink']
    roll = random.random() if value is None else max(0.0, min(1.0, float(value)))
    cursor = roll * total
    for spec in candidates:
        cursor -= max(0.0, spec.weight)
        if cursor <= 0:
            return spec
    return candidates[-1]
