# -*- coding: utf-8 -*-
"""特别事件定义、编号和触发逻辑。"""
from letters import send_letter

SPECIAL_EVENT_DEFINITIONS = (
    {
        'number': 1,
        'id': 'first_letter',
        'name': '最开始的信',
        'trigger': 'first_naming',
        'letter_id': 'letter_1',
    },
    {
        'number': 2,
        'id': 'barton_pot',
        'name': '巴顿老爷的锅',
        'trigger': 'strength_13',
        'letter_ids': ('letter_3', 'letter_4'),
        'description': '猫咪的力量达到13后，巴顿老爷商行的来信送到了仓库。',
    },
)

SPECIAL_EVENTS_BY_TRIGGER = {}
for _event in SPECIAL_EVENT_DEFINITIONS:
    SPECIAL_EVENTS_BY_TRIGGER.setdefault(
        _event['trigger'], []).append(_event)

SPECIAL_EVENTS_BY_NUMBER = {
    int(_event['number']): _event for _event in SPECIAL_EVENT_DEFINITIONS}

# 便利别名：其它系统按编号判断解锁条件时用它们，避免到处写魔法数字。
# 2 号「巴顿老爷的锅」也是送出「巴顿老爷商行的广告」「一份契约」的信件来源，
# 「一份契约」的附件「炼药锅」才是炼药页的解锁条件（见 workstation_window）。
BARTON_POT_EVENT = 2   # 巴顿老爷的锅（力量达到 13）


def get_special_event(number):
    """按编号取特别事件定义（副本），不存在时返回 None。"""
    try:
        event = SPECIAL_EVENTS_BY_NUMBER.get(int(number))
    except (TypeError, ValueError):
        return None
    return dict(event) if event else None


def has_special_event(game, number):
    """判断某个特别事件是否已经触发过。

    只看编号是否存在于存档的 special_events 集合里，与信件是否读到无关。
    """
    try:
        number = int(number)
    except (TypeError, ValueError):
        return False
    events = getattr(game, 'special_events', None)
    try:
        return number in set(events or ())
    except TypeError:
        return False


class SpecialEventService:
    @staticmethod
    def activate(game, trigger):
        """触发指定条件的特别事件，返回本次激活的事件列表。"""
        events = getattr(game, 'special_events', None)
        if not isinstance(events, set):
            events = set(events or ())
            game.special_events = events
        activated = []
        candidates = sorted(
            SPECIAL_EVENTS_BY_TRIGGER.get(str(trigger), ()),
            key=lambda event: event['number'])
        for event in candidates:
            number = int(event['number'])
            if number in events:
                continue
            letter_ids = list(event.get('letter_ids') or ())
            legacy_letter = event.get('letter_id')
            if legacy_letter and legacy_letter not in letter_ids:
                letter_ids.insert(0, legacy_letter)
            for letter_id in letter_ids:
                send_letter(game, letter_id)
            events.add(number)
            activated.append(dict(event))
        return activated
