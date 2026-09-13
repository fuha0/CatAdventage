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
)

SPECIAL_EVENTS_BY_TRIGGER = {}
for _event in SPECIAL_EVENT_DEFINITIONS:
    SPECIAL_EVENTS_BY_TRIGGER.setdefault(
        _event['trigger'], []).append(_event)


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
            letter_id = event.get('letter_id')
            if letter_id:
                send_letter(game, letter_id)
            events.add(number)
            activated.append(dict(event))
        return activated
