from dataclasses import dataclass, field


@dataclass
class GameState:
    hp: int = 100
    max_hp: int = 100
    level: int = 1
    exp: int = 0
    strength: int = 10
    wisdom: int = 10
    agility: int = 10
    luck: int = 0
    emotion: int = 50
    skill_points: int = 0
    gold: int = 0

    inventory: dict = field(default_factory=dict)
    obtained_items: set = field(default_factory=set)
    new_item_categories: set = field(default_factory=set)
    special_events: set = field(default_factory=set)
    letters: list = field(default_factory=list)
    # 动态信件正文表：{信件键: {'title': 标题, 'body': 正文}}。
    # 固定信件不写这里；长期冒险途中寄回的信会写，用于持久化每次不同的内容。
    letter_contents: dict = field(default_factory=dict)
    letter_attachments_claimed: set = field(default_factory=set)
    treasures: list = field(default_factory=list)
    logs: list = field(default_factory=list)
    # 长期冒险（>3 天）的进行状态，用于软件重启后继续按原计划推进：
    #   {'active': True, 'region': '2', 'days': 4, 'minutes': 5760,
    #    'started_at': 起始 epoch 秒, 'ends_at': 预期结束 epoch 秒,
    #    'seed': 随机种子, 'bread_cost': 面包消耗,
    #    'settled_days': 已结算天数, 'letters_sent': 途中已寄出的信数,
    #    'pending_lines': [途中事件描述]}。空闲时为空字典。
    adventure: dict = field(default_factory=dict)
    equipped_slots: dict = field(
        default_factory=lambda: {'头饰': [], '服装': None, '饰品': []})
    equipment_settings: dict = field(default_factory=dict)
    equipped_clothes: str = 'normal'
    books_enabled: set = field(default_factory=set)
    hair_style: str = 'hair_1'
    hair_color: str | None = None
    normal_clothes_color: str | None = None
    eye_color: str | None = None
    cat_name: str = ''
    stats: dict = field(default_factory=dict)
    achievements: set = field(default_factory=set)
    selected_achievement: str | None = None
    backgrounds: set = field(default_factory=lambda: {'market'})
    selected_background: str = 'market'
    cat_scale: float = 1.0
    sound_volume: int = 100
    frame_rate: int = 30          # 动画帧率：30 或 60
    click_sound: str = 'cat1'
    alchemy_level: int = 1        # 炼金等级（工作站「炼药」页）
    alchemy_exp: int = 0          # 当前炼金等级下的炼金经验

PlayerState = GameState
