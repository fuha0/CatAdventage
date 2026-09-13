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
    treasures: list = field(default_factory=list)
    logs: list = field(default_factory=list)
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

PlayerState = GameState
