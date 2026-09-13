# -*- coding: utf-8 -*-
"""信件定义与投递。"""

LETTER_ENVELOPE_IMAGE = 'ui/envelop.png'
TUTORIAL_LETTER_ID = 'letter_2'

TUTORIAL_BODY = """游戏教程：

      这是一个主打挂机的桌宠游戏。作者做这个游戏的最初目的是让这只猫娘当个闹钟，它去探险的时候，玩家就做专心自己的事。@_@

      桌宠的玩法：这只猫咪可以左键单击抚摸，而右键可以打开菜单。猫咪可以被拖拽或者甩飞。她也会做一些小动作。许多动作和表情，有趣的功能，需要在后续游玩中解锁。

      猫咪的属性：猫咪的等级会随着挂机和探险提升，随着猫咪的等级提升，猫咪的实力会不断变强。猫咪的活力在挂机时会逐渐恢复，活力足够时才可以出门探索。猫咪的情绪会因食物、事件、探索而升降。

      仓库的玩法：在仓库里，猫咪可以进行换装、调整容貌，学会新的动作或表情（如果你获得对应物品）。同时，仓库还可以查看已有的材料和宝藏，更换猫咪的成就。

      探险的玩法：选择地区和时间，并开始探险。猫咪在探险时会从桌面消失，在规定时间内回来，并带来一些材料和宝藏。新的地区可能需要提升等级或者触发事件才能解锁。
      注意，探险可能会减少猫咪的活力、心情，同时出远门可能会消耗面包。面包可以在集市购买或者猫咪自己制作。不要让猫咪太累哦~

      集市的玩法：买入仓库没有的物品，卖出探险获得的宝藏。宝藏大多是猫咪找回来的稀奇古怪的小玩意，可以卖出不错的价钱~"""

LETTER_DEFINITIONS = {
    'letter_1': {
        'id': 'letter_1',
        'number': 1,
        'title': '写给主人',
        'category': '信件',
        'kind': '信件',
        'quality': '特别',
        'desc': '最开始的信。',
        'presentation': 'envelope',
        'envelope': LETTER_ENVELOPE_IMAGE,
        'content_image': 'ui/word1.png',
        'event_number': 1,
    },
    TUTORIAL_LETTER_ID: {
        'id': TUTORIAL_LETTER_ID,
        'number': 2,
        'title': '游戏教程',
        'category': '信件',
        'kind': '信件',
        'quality': '特别',
        'desc': '开局赠送给主人的游戏教程。',
        'presentation': 'text',
        'body': TUTORIAL_BODY,
        'starting': True,
    },
}
LETTERS = LETTER_DEFINITIONS
STARTING_LETTER_IDS = tuple(
    letter_id for letter_id, info in LETTER_DEFINITIONS.items()
    if info.get('starting'))
LETTER_ORDER = tuple(sorted(
    LETTER_DEFINITIONS, key=lambda letter_id: LETTER_DEFINITIONS[letter_id]['number']))


def get_letter(letter_id):
    """返回信件展示数据的副本。"""
    letter = LETTER_DEFINITIONS.get(str(letter_id))
    if letter is None:
        return None
    result = dict(letter)
    result.setdefault('detail_kind', 'letter')
    return result


def send_letter(game, letter_id):
    """把一封信加入存档，重复投递时忽略。"""
    letter_id = str(letter_id)
    if letter_id not in LETTER_DEFINITIONS:
        return False
    letters = getattr(game, 'letters', None)
    if not isinstance(letters, list):
        letters = list(letters or ())
        game.letters = letters
    if letter_id in letters:
        return False
    letters.append(letter_id)
    letters.sort(key=lambda item: LETTER_DEFINITIONS.get(item, {}).get('number', 9999))
    return True
