# -*- coding: utf-8 -*-
"""信件定义与投递。"""

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
        'presentation': 'image',
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
    'letter_3': {
        'id': 'letter_3',
        'number': 3,
        'title': '巴顿老爷商行的广告',
        'category': '信件',
        'kind': '信件',
        'quality': '特别',
        'desc': '巴顿老爷商行送来的宣传单。',
        'presentation': 'image',
        'content_image': 'ui/word2.png',
        'event_number': 2,
    },
    'letter_4': {
        'id': 'letter_4',
        'number': 4,
        'title': '一份契约',
        'category': '信件',
        'kind': '信件',
        'quality': '特别',
        'desc': '与巴顿老爷有关的契约，随信附来一口锅。',
        'presentation': 'image',
        'content_image': 'ui/word3.png',
        'event_number': 2,
        # 附件：需要在信件详情里点「领取附件」才会进仓库。
        'attachments': ({'item': 'alchemy_pot', 'count': 1},),
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


# ---------- 信件附件 ----------
# 附件定义写在 LETTER_DEFINITIONS 的 attachments 字段里，支持三种写法：
#   ({'item': '炼药锅键名', 'count': 2},)      —— 推荐
#   ('炼药锅键名',)                            —— 数量默认 1
# 附件不会随信件自动入包，必须在信件详情里点「领取附件」，领取记录存在
# game.letter_attachments_claimed 里，重复点击不会二次发放。

def letter_attachments(letter_id):
    """规范化某封信的附件列表：[{'item': 键名, 'count': 数量}, ...]。"""
    letter = LETTER_DEFINITIONS.get(str(letter_id))
    if not letter:
        return []
    raw = letter.get('attachments') or ()
    if isinstance(raw, dict):
        raw = tuple(raw.items())
    result = []
    for entry in raw:
        if isinstance(entry, str):
            item_id, count = entry, 1
        elif isinstance(entry, (list, tuple)) and len(entry) == 2:
            item_id, count = entry
        elif isinstance(entry, dict):
            item_id = entry.get('item') or entry.get('item_id')
            count = entry.get('count', 1)
        else:
            continue
        item_id = str(item_id or '').strip()
        if not item_id:
            continue
        try:
            count = max(1, int(count))
        except (TypeError, ValueError):
            count = 1
        result.append({'item': item_id, 'count': count})
    return result


def has_letter_attachments(letter_id):
    """这封信有没有附件。"""
    return bool(letter_attachments(letter_id))


def attachment_claimed(game, letter_id):
    """附件是否已经领取过。"""
    claimed = getattr(game, 'letter_attachments_claimed', None)
    if not isinstance(claimed, (list, tuple, set)):
        return False
    target = str(letter_id)
    return any(str(value) == target for value in claimed)


def claim_letter_attachments(game, inventory, letter_id, items=None):
    """领取信件附件，返回 (已领取条目列表, 错误信息)。

    领取成功后把信件编号记进 game.letter_attachments_claimed，
    并把物品真正加进 inventory（单件类物品最多 1 个）。
    """
    # 延迟导入：letters 会被 services.save 导入，模块级导入会绕成环。
    from services.inventory import InventoryService

    letter_id = str(letter_id)
    attachments = letter_attachments(letter_id)
    if not attachments:
        return [], '这封信没有附件。'
    if attachment_claimed(game, letter_id):
        return [], '附件已经领取过了。'
    claimed = getattr(game, 'letter_attachments_claimed', None)
    if not isinstance(claimed, list):
        claimed = list(claimed or ())
        game.letter_attachments_claimed = claimed
    items = items or {}
    granted = []
    for entry in attachments:
        item_id = entry['item']
        info = items.get(item_id) or {}
        max_count = (1 if info.get('category') in (
            '\u5934\u9970', '\u670d\u88c5', '\u9970\u54c1', '\u4e66\u7c4d') else None)
        actual = InventoryService.add(
            inventory, item_id, entry['count'], max_count=max_count)
        granted.append({
            'item': item_id,
            'name': info.get('name') or item_id,
            'count': actual or entry['count'],
        })
    claimed.append(letter_id)
    return granted, ''

