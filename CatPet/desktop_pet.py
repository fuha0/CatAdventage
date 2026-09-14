# 桌宠软件 - 使用 tkinter 实现
import tkinter as tk
import tkinter.ttk as ttk
import random
import math
import time
import PIL.Image
import PIL.ImageTk
import os
import sys
import threading
import datetime
import re
from item_catalog import build_code_lookup
from content_repository import ContentRepository
from emoticon_config import load_emoticons
from expression_config import load_click_expression_config
from colors import COLOR_PALETTE
from animation_controller import AnimationController
from animation_state_machine import AnimationStateMachine
from render_cache import RenderCache
from services import GameState, ProgressionService, SaveService
from letters import TUTORIAL_LETTER_ID
from special_events import SpecialEventService
from potions import (
    ALCHEMY_RECIPES, POTION_MASKS, format_effect_summary, potion_tier,
    recipe_desc, recipe_effect_text, recipe_materials_text,
    register_potion_items, roll_potion_effect, roll_potion_prefix,
    variant_key)
from animations import AnimationMixin, DRAG_MODE_IDS
from editor_enhancements import EditorEnhancementsMixin
from renderer import RendererMixin, install_runtime_globals as install_renderer_globals
from interaction_animations import InteractionAnimationMixin, install_runtime_globals as install_interaction_globals
from warehouse_window import WarehouseMixin, install_runtime_globals as install_warehouse_globals
from market_window import MarketMixin, install_runtime_globals as install_market_globals
from adventure_window import AdventureMixin, install_runtime_globals as install_adventure_globals
from adventure_page import AdventurePageMixin, install_runtime_globals as install_adventure_page_globals
from workstation_window import WorkstationMixin, install_runtime_globals as install_workstation_globals
from stats import StatsService
from ui_theme import (
    THEME, FONT_FAMILY, configure_theme, make_button, make_label, make_card)
from achievements import AchievementMixin, AchievementService, install_runtime_globals as install_achievement_globals
from admin_extensions import AdminMixin, install_runtime_globals as install_admin_globals

# 配置

# ---------------------------------------------------------------------------
# 高 DPI 感知：让窗口按「物理像素」渲染，而不是被系统按缩放比例位图拉伸。
# 不声明时 Windows 会把进程当 96 DPI，Tk 拿到的是逻辑坐标（如 1707×1067），
# 窗口却被拉伸到物理分辨率（如 2560×1600），这就是「糊 + 锯齿放大」的根因。
# 声明后 Tk 坐标直接是物理像素，素材按物理尺寸渲染，清晰无拉伸。
# ---------------------------------------------------------------------------
import ctypes as _ctypes


def _declare_dpi_awareness():
    """声明进程 DPI 感知（必须在创建任何 Tk 窗口前调用）。"""
    try:
        # per-monitor V2（多屏不同 DPI 也正确）
        _ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        # system DPI aware（单屏够用）
        _ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        # 最老的回退（Vista/7）
        _ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _physical_dpi_scale():
    """物理缩放因子（物理 DPI / 96）。声明 DPI 感知后 GetDeviceCaps 返回真实 DPI。"""
    try:
        _dc = _ctypes.windll.user32.GetDC(0)
        _dpi = _ctypes.windll.gdi32.GetDeviceCaps(_dc, 88)  # LOGPIXELSX
        _ctypes.windll.user32.ReleaseDC(0, _dc)
        if _dpi and _dpi > 0:
            return float(_dpi) / 96.0
    except Exception:
        pass
    return 1.0


def _declare_app_user_model_id():
    """给进程一个独立身份，任务栏按钮才会用窗口图标（ui/cat.png）。

    Windows 默认按 exe 路径给进程归组，源码调试时那一组就叫 python.exe，
    任务栏按钮会跟着显示 Python 的图标；显式声明 ID 后这一组归本程序，
    再配合 wm iconphoto 就能稳定显示猫的图标。打包成 exe 后同样是这个 ID。
    """
    try:
        _ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            'CatAdventage.CatPet')
    except Exception:
        pass


_declare_dpi_awareness()
_declare_app_user_model_id()
DPI_SCALE = _physical_dpi_scale()


def dp(value):
    """逻辑像素 → 物理像素。所有「窗口几何尺寸 / 像素级 UI 尺寸」都要走它，
    这样在高 DPI 屏上保持和 96 DPI 一样的视觉大小。渲染/桌宠本体用 ICON_SIZE
    （已经按物理尺寸放大），不需要再套 dp。"""
    return int(round(value * DPI_SCALE))


def _asset_dir():
    """返回素材目录：源码使用项目素材，exe 使用打包解压目录。"""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    return os.path.join(base, 'Materials')


def _asset_path(name, category=None):
    """定位素材文件；优先使用分类目录，并兼容旧版顶层结构。"""
    relative = os.path.join(category, name) if category else name
    path = os.path.join(_asset_dir(), relative)
    if os.path.exists(path):
        return path
    legacy_path = os.path.join(_asset_dir(), name)
    if os.path.exists(legacy_path):
        return legacy_path
    return path


CLICK_EXPRESSION_CONFIG_PATH = _asset_path('click_expression_config.json')
CLICK_EXPRESSION_CONFIG = load_click_expression_config(
    CLICK_EXPRESSION_CONFIG_PATH)
CLICK_SOUND_ORDER = ('cat1', 'cat2', 'cat3', 'silent')
CLICK_SOUND_PITCH_RATES = (0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15)
CLICK_SOUND_CATALOG = {
    'cat1': {
        'id': 'cat1', 'name': '猫咪原声',
        'kind': '单击音效', 'category': '音效',
        'quality': '绿色', 'quality_color': '#2ecc71',
        'desc': '猫咪最自然的叫声，平静而熟悉，听起来很安心。',
        'path': _asset_path('cat1.wav', 'voice'),
    },
    'cat2': {
        'id': 'cat2', 'name': '爱傲娇',
        'kind': '单击音效', 'category': '音效',
        'quality': '绿色', 'quality_color': '#2ecc71',
        'desc': '带着一点撒娇和不服气的傲娇叫声，嘴硬心软。',
        'path': _asset_path('cat2.wav', 'voice'),
    },
    'cat3': {
        'id': 'cat3', 'name': '哈气',
        'kind': '单击音效', 'category': '音效',
        'quality': '绿色', 'quality_color': '#2ecc71',
        'desc': '猫咪炸毛时发出的警惕哈气声，别随便惹它哦。',
        'path': _asset_path('cat3.wav', 'voice'),
    },
    'silent': {
        'id': 'silent', 'name': '猫咪闭嘴！',
        'kind': '单击音效', 'category': '音效',
        'quality': '绿色', 'quality_color': '#2ecc71',
        'desc': '选中后猫咪不再发出单击音效，安安静静地闭上嘴。',
        'path': None,
    },
}
CLICK_SOUND_PATHS = {
    key: info['path'] for key, info in CLICK_SOUND_CATALOG.items()
}
CLICK_SOUND_PATH = CLICK_SOUND_PATHS['cat1']
ADVENTURE_RETURN_SOUND_PATH = _asset_path('ling.wav', 'voice')


# 分层素材（同一 1024 画布，同原点叠加）
HEAD_PATH = _asset_path('head.png', 'body')
HAIR1_PATH = _asset_path('hair_1.png', 'body')  # 最前层头发（原版）
HAIR1_1_PATH = _asset_path('hair_1_1.png', 'body')  # 前层发型 2
HAIR2_PATH = _asset_path('hair_2.png', 'body')  # 最底层头发
TAIL_PATH = _asset_path('tail.png', 'body')
EYE_PATH = _asset_path('eye.png', 'body')
EYE_CLOSE1_PATH = _asset_path('eye_close1.png', 'body')
EYE_CLOSE2_PATH = _asset_path('eye_close2.png', 'body')
EYE_CLOSE3_PATH = _asset_path('eye_close3.png', 'body')
EYE_COMFY_PATH = _asset_path('eye_comfy.png', 'body')
EYE1_PATH = _asset_path('eye_1.png', 'body')
EYE2_PATH = _asset_path('eye_2.png', 'body')
BROW_PATH = _asset_path('brow.png', 'body')
BROW1_PATH = _asset_path('brow_1.png', 'body')
MOUTH_HAPPY_PATH = _asset_path('mouth_happy.png', 'body')
MOUTH_HUYA_PATH = _asset_path('mouth_huya.png', 'body')
MOUTH_SAD_PATH = _asset_path('mouth_sad.png', 'body')
MOUTH_COMFY_PATH = _asset_path('mouth_comfy.png', 'body')
EAR_LEFT_PATH = _asset_path('ear_left.png', 'body')
EAR_RIGHT_PATH = _asset_path('ear_right.png', 'body')
CLOTHES_PATH = _asset_path('clothes_normal.png', 'body')
CLOTHES_HEFU_BLUE_PATH = _asset_path('clothes_hefu_blue.png', 'clothes2')
CLOTHES_HEFU_GREEN_PATH = _asset_path('clothes_hefu_green.png', 'clothes2')
CLOTHES_HEFU_RED_PATH = _asset_path('clothes_hefu_red.png', 'clothes2')
CLOTHES_THIEF_PATH = _asset_path('clothes_thief.png', 'clothes2')  # 盗贼服
CLOTHES_KNIGHT_PATH = _asset_path('clothes_knight.png', 'clothes2')  # 骑士服
CLOTHES_PEASANT_PATH = _asset_path('clothes_peasant.png', 'clothes2')  # 村民衣服
CLOTHES_WHITEMOON_PATH = _asset_path('clothes_whitemoon.png', 'clothes2')
CLOTHES_BLACKSUN_PATH = _asset_path('clothes_blacksun.png', 'clothes2')
CLOTHES_NOBLE_BLUE_PATH = _asset_path('clothes_Nobleman_blue.png', 'clothes2')
CLOTHES_CLOWN_PATH = _asset_path('clothes_Clown.png', 'clothes2')
CLOTHES_NORTH_MAID_PATH = _asset_path('north_maid1.png', 'clothes1')
CLOTHES_NORTH_NIGHT_PATH = _asset_path('north_night.png', 'clothes1')
CLOTHES_NORTH_WIND_PATH = _asset_path('north_windbreaker.png', 'clothes1')
BACKGROUND_MARKET_PATH = _asset_path('Market.png', 'background')
BACKGROUND_PLAIN_PATH = _asset_path('Plain.png', 'background')
BACKGROUND_FOREST_PATH = _asset_path('Forest.png', 'background')
BACKGROUND_VALLEY_PATH = _asset_path('Valley.png', 'background')
# 炼金间：只作为工作站「炼药」页的固定布景，不进玩家的背景轮换列表。
BACKGROUND_ALCHEMY_PATH = _asset_path('Alchemy.png', 'background')
BACKGROUND_PATHS = {
    'market': BACKGROUND_MARKET_PATH, 'plain': BACKGROUND_PLAIN_PATH,
    'forest': BACKGROUND_FOREST_PATH, 'valley': BACKGROUND_VALLEY_PATH,
    'alchemy': BACKGROUND_ALCHEMY_PATH,
}
BACKGROUND_ORDER = ('market', 'plain', 'forest', 'valley')
SUNGLASSES_PATH = _asset_path('Sunglasses.png', 'ornament')
HAT1_PATH = _asset_path('hat_1.png', 'ornament')
HAT_JI_PATH = _asset_path('hat_ji.png', 'ornament')
HAT2_PATH = _asset_path('hat_2.png', 'ornament')
GOLD_EARRINGS_PATH = _asset_path('Earrings_gold.png', 'ornament')
FINE_COLLAR1_PATH = _asset_path('Fine collar1.png', 'ornament')
FINE_COLLAR2_PATH = _asset_path('Fine collar2.png', 'ornament')
CLOTHES_NAMES = {
    'normal': '普通衣服', 'peasant': '村民衣服',
    'thief': '盗贼服', 'knight': '骑士服',
    'hefu_blue': '和服·蓝', 'hefu_green': '和服·绿',
    'hefu_red': '和服·红',
    'white_moon': '白月服饰', 'black_sun': '黑日服饰',
    'blue_noble': '蓝色贵族服饰', 'clown': '小丑服饰',
    'north_maid1': '北境女仆装', 'north_night': '北境夜行服',
    'north_windbreaker': '北境防风衣',
}
CLOTHES_ITEM_IDS = {
    'peasant': 'peasant', 'thief': 'thief', 'knight': 'knight',
    'hefu_blue': 'hefu_blue', 'hefu_green': 'hefu_green',
    'hefu_red': 'hefu_red', 'white_moon': 'white_moon',
    'black_sun': 'black_sun', 'blue_noble': 'blue_noble',
    'clown': 'clown', 'north_maid1': 'north_maid1',
    'north_night': 'north_night',
    'north_windbreaker': 'north_windbreaker',
}
STARTING_GIFT_ITEMS = ('expression_happy',)
DEFAULT_EQUIPMENT_SETTINGS = {
    'sunglasses_y_offset': 80,
    'earrings_color': '#ffdf09',
    'hat_1_color': '#f3f0df',
    'hat_ji_color': '#ffffff',
    'hat_ji_scale': 0.8,
    'hat_2_brown_color': '#594926',
    'hat_2_cream_color': '#fbf9ec',
    'collar_style': 1,
    'collar_rope_color': '#c0392b',
    'collar_deco_color': '#f1e8d7',
}
EXPRESSION_PRESETS = {
    'secret': {'brow': 'brow', 'eye': 'eye_2', 'mouth': 'mouth_comfy'},
    'happy': {'brow': 'brow', 'eye': 'eye', 'mouth': 'mouth_happy'},
    'grumpy': {'brow': 'brow_1', 'eye': 'eye_1', 'mouth': 'mouth_sad'},
    'comfy': {'brow': 'brow', 'eye': 'eye_comfy',
              'mouth': 'mouth_comfy'},
}
EXPRESSION_BOOK_ORDER = (
    'expression_secret', 'expression_happy', 'expression_grumpy',
    'expression_comfy')
EXPRESSION_BOOK_TO_PRESET = {
    'expression_secret': 'secret',
    'expression_happy': 'happy',
    'expression_grumpy': 'grumpy',
    'expression_comfy': 'comfy',
}
HAND_PATH = _asset_path('hand.png', 'body')            # 小手（小球）
# 初始大小：逻辑 150px，按物理 DPI 缩放后在高分屏上保持原视觉大小。
# 声明 DPI 感知后 Tk 坐标是物理像素，所以这里直接是物理尺寸（150% 屏 = 225）。
ICON_SIZE = int(150 * DPI_SCALE)
TRANSPARENT_COLOR = "#322828"  # 黑色作为透明色
CAT_FEET_RATIO = 985 / 1024    # 合成后猫脚底在画布中的比例（clothes 底部）
HAND_SIDE_OFFSET = 26          # 两只手向外偏移像素
HAND_UP_OFFSET = 50            # 两只手向上偏移像素（整体再上移一点）
HAND_WALK_AMPLITUDE = 20       # 走路时手上下摆动的幅度（画布像素）
HAND_WALK_PERIOD_MS = 420      # 走路摆手一个来回的周期（毫秒）
SCRATCH_MOVE_MS = 300          # 挠头每一下的时长
# 注意：挠头的帧间隔实际生效的是 animations.py 里那一份（该模块没有注入
# 运行时全局，用的是自己的同名常量）；抬手间隔已改为走 _hand_frame_ms()。
# 这里保留仅为记录原始取值，改这里不会生效。
SCRATCH_FRAME_MS = 30          # 挠头动作帧间隔
SCRATCH_LIFT_FRAME_MS = 5      # 抬手帧间隔（已废弃）
SCRATCH_TRANSITION_FRAME_MS = 15  # 放手帧间隔
SCRATCH_OFFSET = 26            # 挠头时手下探的幅度
SCRATCH_HAND_Y = 205           # 抬起手的位置（画布坐标 y）
SCRATCH_LEFT_X = 150           # 左手抬到头部左侧的 x
SCRATCH_RIGHT_X = 735          # 右手抬到头部右侧的 x

# 待机手部动作（招手 / 舔手）共用：抬手占整段动作前 30%，之后才是摆动/舔
IDLE_HAND_RAISE_T = 0.30

# 招手：手抬到头侧（沿用挠头验证过的位置）再左右摆
WAVE_HAND_Y = 250              # 抬起手的位置（画布坐标 y），比挠头略低一点
WAVE_LEFT_X = 130              # 左手抬到头部左侧的 x（再往外一点，别挡住脸）
WAVE_RIGHT_X = 777             # 右手抬到头部右侧的 x（与左手严格镜像）
WAVE_SWING_X = 50              # 左右摆动幅度（像素）：摆到最外侧刚好擦过脸颊
WAVE_SWING_Y = 16              # 摆动时附带的一点点上下
WAVE_CYCLES = 2.5              # 摆动几个来回

# 舔手：手抬到嘴边上下舔（嘴的中心在画布 (467, 531) 附近）
LICK_HAND_Y = 466              # 抬起手的位置（画布 y），正好落在嘴上
LICK_LEFT_X = 392              # 左手贴到嘴边的 x（偏向自己那一侧，不盖住整张嘴）
LICK_RIGHT_X = 426
LICK_DIP_Y = 36                # 舔的上下幅度
LICK_DIP_X = 12                 # 舔的时候手往回收一点
LICK_CYCLES = 3.0              # 舔几下

# 比例（缩放）参数：滑块范围为 50% ~ 150%
SCALE_MIN = 0.5
SCALE_MAX = 1.5

# 随机动作参数（毫秒）
ACTION_MIN_MS = 2500   # 睁眼休息最短时间（两次随机动作之间）
ACTION_MAX_MS = 6000   # 睁眼休息最长时间
BLINK_CLOSED_MS = 150  # 眨眼时闭眼时间
EAR_MOVE_MS = 180      # 耳朵动一下的持续时间
EAR_GAP_MS = 120       # 耳朵“两下”之间的间隔
HP_LOW_AT = 20         # 活力低于该值，状态条变红/不能探险
EARLY_ADVENTURE_FAIL_HP = 10  # 活力降到该值及以下时提前结束探险
EARLY_ADVENTURE_REWARD_RATE = 0.4  # 提前结束只保留 40% 金币和经验
EAR_WARP_PX = 12       # 右耳右上角下拉像素
TAIL_WAG_ANGLE = 5     # 尾巴轻摆角度（度）
TAIL_MOVE_MS = 220     # 尾巴每下时长
TAIL_GAP_MS = 160      # 尾巴两下间隔
JUMP_FRAME_MS = 33     # 跳跃动画约 30 帧/秒
JUMP_PREP_MS = 150     # 准备动作每帧（蓄力更久）
JUMP_CHARGE_MIN_STEPS = 8   # 最短蓄力帧数
JUMP_CHARGE_MAX_STEPS = 14  # 最长蓄力帧数
JUMP_AIR_MS = 650      # 起跳弧线的名义空中时间
JUMP_SLIDE_MS = 180    # 物理启动失败时的备用落地滑行时间
JUMP_WALL_SPEED = 3    # 撞边下滑速度（像素/帧）
ADVENTURE_FAREWELL_MS = 110   # 探险告别手势每帧
ADVENTURE_HOP_FRAME_MS = 22   # 离场小跳帧间隔（提高水平动力）
ADVENTURE_FALL_FRAME_MS = 33  # 离场下落帧间隔
ADVENTURE_TITLE_UPDATE_MS = 5 * 60 * 1000
IDLE_EXP_PER_MIN = 10  # 挂机奖励：每分钟经验
IDLE_EXP_MS = 60 * 1000
REACH_CHECK_MS = 200       # 鼠标靠近检测间隔
REACH_CHANCE = 0.35        # 每次靠近伸手抓鼠标的几率
REACH_STATIONARY_MS = 1800 # 鼠标静止多久才可能触发（加长）
REACH_RANGE_RATIO = 1.1    # 触发距离（相对猫身长，缩短）
REACH_COOLDOWN_MS = 60 * 1000  # 抓鼠标冷却：约 1 分钟最多一次
REACH_MAX_REACH = 230      # 手伸出幅度（1024 画布像素）
BOUNCE_MS = 260            # 落地回弹时长
BOUNCE_FRAME_MS = 25
BOUNCE_RATIO = 0.12        # 回弹高度（相对身长）
CAT_LEFT_RATIO = 81 / 1024    # 猫内容左边缘比例（用于贴墙）
CAT_RIGHT_RATIO = 932 / 1024  # 猫内容右边缘比例

# 拖动晃动参数
SWAY_AMPLITUDE = 4     # 拖动时身体左右晃动的最大角度（度，调小后晃动更轻微）
SWAY_PERIOD_MS = 800   # 晃动一个完整来回的时间（毫秒）
SWAY_FRAME_MS = 33     # 晃动动画约 30 帧/秒

# 松手甩飞 / 下落共用物理动画：位置约 60 帧/秒，图片约 30 帧/秒
AIRBORNE_REFERENCE_FRAME_MS = 33  # 物理参数的基准帧长
AIRBORNE_FRAME_MS = 16            # 窗口位置更新约 60 帧/秒
AIRBORNE_RENDER_MS = 33           # 身体和手部图片约 30 帧/秒
FLING_FRAME_MS = AIRBORNE_FRAME_MS
FALL_FRAME_MS = AIRBORNE_FRAME_MS
FLING_MIN_SPEED = 700       # 低于该鼠标速度不触发（像素/秒；鼠标坐标也随 DPI 变物理，阈值不变）
FLING_SPEED_SCALE = 0.55    # 鼠标速度转换为基准帧移动距离
FLING_MAX_SPEED = 53 * DPI_SCALE   # 33ms 基准帧下的最大初速度（每帧像素，随 DPI 缩放）
FLING_FRICTION = 0.955      # 33ms 基准帧的空气阻力
FLING_GROUND_FRICTION = 0.9  # 33ms 基准帧的地面摩擦力
FLING_GROUND_STOP_SPEED = 0.75 * DPI_SCALE  # 接地后低于该每帧速度即结束动画
FLING_GRAVITY = 1.13 * DPI_SCALE        # 33ms 基准帧的垂直重力（每帧像素）
FLING_BOUNCE = 0.28         # 撞墙/落地反弹系数
FLING_SECOND_BOUNCE = 0.45  # 高落差落地后的第二次小弹跳
FLING_THIRD_BOUNCE = 0.55   # 高落差连续弹跳的第三次小弹跳
FLING_SECOND_BOUNCE_MIN_IMPACT_SPEED = 10.0 * DPI_SCALE  # 首次落地速度达到该值时启用连续弹跳
FLING_SECOND_BOUNCE_MIN_SPEED = 0.75 * DPI_SCALE  # 后续落地的最低反弹速度
FLING_EDGE_OVERSHOOT_RATIO = 0.05  # 甩飞时允许猫身伸出屏幕的比例
AIRBORNE_FRAME_SCALE = AIRBORNE_FRAME_MS / AIRBORNE_REFERENCE_FRAME_MS
AIRBORNE_MAX_SPEED = FLING_MAX_SPEED * AIRBORNE_FRAME_SCALE
AIRBORNE_FRICTION_STEP = FLING_FRICTION ** AIRBORNE_FRAME_SCALE
AIRBORNE_GROUND_FRICTION_STEP = (
    FLING_GROUND_FRICTION ** AIRBORNE_FRAME_SCALE)
AIRBORNE_GRAVITY_STEP = FLING_GRAVITY * AIRBORNE_FRAME_SCALE ** 2
AIRBORNE_VISUAL_POWER_STEPS = 16  # 手部拖尾视觉量化级别
AIRBORNE_LANDING_REFRESH_FRAMES = 10  # 约 6Hz，减少 EnumWindows 开销

# 动画帧率：设置里可选 30 / 60 帧。只影响「由定时器驱动」的动画节拍
# （拖拽晃动、走动、跳跃、攀爬、空中身体重绘）。
# 甩飞/下落的窗口位置物理固定 16ms 不变——它的物理常量是按 33ms 基准帧
# 推导出来的，改步长需要整套重算，风险太大。
#
# 注意：上面那些 JUMP_FRAME_MS / SWAY_FRAME_MS / CLIMB_FRAME_MS /
# WALK_STEP_MS / AIRBORNE_RENDER_MS = 33 已经**不再被读取**（保留只为
# 记录原始节拍）。所有动画节拍现在一律走 anim_frame_ms()，
# 改帧率时不要再往那些常量里塞值，否则改了不生效。
FRAME_MS_30 = 33
FRAME_MS_60 = 16
ANIM_FPS = 30          # 当前帧率，构造时从存档读入


def anim_frame_ms():
    """当前动画帧间隔（毫秒）：60 帧返回 16，否则 33。"""
    return FRAME_MS_60 if int(ANIM_FPS) >= 60 else FRAME_MS_30


def set_anim_fps(fps):
    """切换动画帧率，返回归一化后的值（30 或 60）。"""
    global ANIM_FPS
    ANIM_FPS = 60 if int(fps) >= 60 else 30
    return ANIM_FPS

# 拖进任务栏区域后的向上攀爬
CLIMB_FRAME_MS = 33
CLIMB_PAUSE_MS = 260
CLIMB_REACH_MS = 360
CLIMB_RISE_MS = 560
CLIMB_RELEASE_MS = 160

# 手部动画（挠头抬手、攀爬）专用帧间隔，固定走快档，不跟随 30/60 帧设置。
#
# 为什么不能直接照抄 60 帧的 16ms：Windows 的窗口定时器 tick 约 15.4ms，
# Tk 的 after(N) 只能落在 tick 边界上。设回调自身耗时 c、请求间隔 d，
# 判定规则是（实测验证，见 diag_tk_tick_with_work.py）：
#     d <= 15.4 - c  ->  命中下一个 tick，间隔 15.4ms（约 65 帧/秒）
#     d  > 15.4 - c  ->  只能等再下一个 tick，间隔 30.8ms（约 32 帧/秒）
# 贴手一帧约 3.6ms，所以可用余量是 15.4 - 3.6 ≈ 11.8ms。
#     请求 16ms -> 30.9ms（32 帧/秒）      请求 14ms -> 30.9ms（32 帧/秒）
#     请求 12ms -> 15.7ms 但只有 82% 命中（15.4/30.8 交替闪烁）
#     请求  8ms -> 15.4ms，100% 命中（65 帧/秒）
# 取 8 而不是 12：12 正好卡在边界上，帧间隔会一半 15.4 一半 30.8，看着是
# 「一卡一顿」。8 留出余量，稳定 65 帧/秒。也不要再往下取（如 1ms）——
# 那会变成空转忙等，实际能跑到 200 帧/秒，既烧 CPU 又会把手部节奏拉快 3 倍。
HAND_FRAME_MS = 8

# 自主走动参数
WALK_IDLE_MIN_MS = 2500      # 空闲多久后可能开始走动（下限，缩短以增加频率）
WALK_IDLE_MAX_MS = 5000      # 空闲多久后可能开始走动（上限）
WALK_CHANCE = 0.85           # 尝试时开始走动的概率（提高）
WALK_STEP_MS = 33            # 走动约 30 帧/秒
# 每帧移动像素。声明高 DPI 后窗口是物理像素（150% 屏 = 225px），
# 位移类常量要同步乘 DPI_SCALE，否则猫的相对移动速度会慢 1/1.5。
WALK_SPEED = 3 * DPI_SCALE
WALK_MIN_MS = 1000           # 一次走动最短时长
WALK_MAX_MS = 2500           # 一次走动最长时长
WALK_EDGE_OVERSHOOT_RATIO = 0.10  # 行走时允许猫身伸出屏幕的比例
WALK_ROCK_AMPLITUDE = 2      # 走动时身体左右轻微摇晃的角度（度）
WALK_ROCK_PERIOD_MS = 420    # 摇晃一个来回的时长（毫秒）

# 待机呼吸感：静止站立时身体极小幅度的垂直起伏，模拟呼吸。
# 独立于眨眼/动耳等叠层动作（那些改的是局部图层，呼吸改的是整图纵向缩放），
# 两者互不冲突。幅度刻意压得很小：150px 窗口下 1% ≈ 1.5 像素，只是「活着」。
BREATH_PERIOD_MS = 2000      # 一次完整呼吸（吸+呼）的时长（缩短让起伏更明显）
BREATH_AMPLITUDE = 0.010     # 纵向缩放幅度（±1%）
BREATH_FRAME_MS = 80         # 呼吸帧间隔（慢动作，不需要 60 帧）
BREATH_LEVELS = 7            # 呼吸离散成几个缩放级别（用于缓存命中）

# 掉落（任务栏）参数
FALL_CHECK_MS = 400          # 检查猫是否越过桌面底部的间隔（毫秒）

# 所有染色功能统一使用 colors.py 中的完整色表。
HAIR_COLORS = COLOR_PALETTE
EYE_COLORS = COLOR_PALETTE

QUALITY_COLORS = {
    '粗劣': '#b0b0b0',  # 浅灰
    '普通': '#555555',  # 深灰
    '少见': '#2ecc71',  # 绿
    '稀有': '#3498db',  # 蓝
    '史诗': '#9b59b6',  # 紫
    '传说': '#f1c40f',  # 金
}
QUALITY_NAMES = {
    1: '粗劣', 2: '普通', 3: '少见', 4: '稀有', 5: '史诗', 6: '传说',
}
PREFIX_GRADE_BY_QUALITY = {
    1: 'D级', 2: 'C级', 3: 'B级', 4: 'A级', 5: 'S级', 6: 'S级',
}
TREASURE_REGION_MAX_QUALITY = {1: 2, 2: 3, 3: 4, 4: 5}
TREASURE_REGION_QUALITY_WEIGHTS = {
    1: {1: 4.0, 2: 1.0},
    2: {1: 2.0, 2: 8.0, 3: 0.4},
    3: {1: 10.0, 2: 35.0, 3: 50.0, 4: 5.0},
    4: {1: 5.0, 2: 20.0, 3: 40.0, 4: 30.0, 5: 5.0},
}
TREASURE_REGION_QUALITY_CAPS = {2: {3: 2}}
TREASURE_SELL_EMOTION = {1: 0, 2: 0, 3: 1, 4: 4, 5: 9, 6: 15}

EMOTION_INITIAL = 50
EMOTION_NATURAL_MIN = 40
EMOTION_NATURAL_MAX = 80
EMOTION_CHANGE_MS = 5 * 60 * 1000
HOSPITAL_MS = 3 * 60 * 1000
# 药水蒙版（炼药产出的药水效果）到期检查间隔。
POTION_MASK_TICK_MS = 1000
EMOTION_FACE_FRAME_MS = 30
CLICK_REACTION_COOLDOWN_MS = 700  # 单击猫咪表情与音效共用的最短间隔
CLICK_EXPRESSION_DURATION_MS = 1000  # 单击后猫咪改变表情的持续时间
EMOTION_FACE_EMERGE_MS = 350
EMOTION_FACE_HOLD_MS = 1000
EMOTION_FACE_FADE_MS = 500
EMOTION_FACE_RISE_PX = 24

# 颜文字从素材/emoticons.json 读取，方便自行扩充。
EMOTICON_CONFIG_PATH = _asset_path('emoticons.json')
EMOTICONS = load_emoticons(EMOTICON_CONFIG_PATH)
FOOD_EMOTION_GAIN = {
    '粗劣': (0, 0), '普通': (0, 1), '少见': (1, 2),
    '稀有': (2, 3), '史诗': (3, 4), '传说': (4, 5),
}

BAR_BG = '#ffffff'        # 悬浮条背景
BAR_FG = '#333333'        # 悬浮条文字
BAR_BORDER = '#cccccc'    # 悬浮条边框

# 状态（属性）参数
HP_MAX = 100                    # 活力值上限
HP_INITIAL = 100                # 活力值初始
STRENGTH_INITIAL = 10           # 力量初始
WISDOM_INITIAL = 10             # 智慧初始
AGILITY_INITIAL = 10            # 敏捷初始
LUCK_INITIAL = 0                # 幸运初始

SATIETY_SAVE_PATH = os.path.join(os.path.expanduser('~'),
                                 '.cat_pet_satiety.json')

# 探险 / 金币参数

ADVENTURE_REWARD_MIN = 0             # 每次探险基础金币下限（G）
ADVENTURE_REWARD_MAX = 20            # 每次探险基础金币上限（G）
EXPLORE_TIMES = (5, 10, 15, 20, 25, 30)  # 低语森林可选时间（5 的倍数，5~30 分钟）
PLAIN_EXPLORE_TIMES = (5, 10, 15)  # plain allowed durations
ADVENTURE_BREAD_MINUTES_PER_UNIT = 5  # 非平原地区每 5 分钟消耗 1 个面包
XP_PLAIN = 50                   # 风和平原基础经验
XP_FOREST_PER_MIN_MIN = 24      # 低语森林每分钟经验下限
XP_FOREST_PER_MIN_MAX = 28      # 低语森林每分钟经验上限
STARTING_BREAD = 10             # 首次进入游戏赠送面包数
STARTING_GOLD = 20              # 新存档初始金币
REGION_RECOMMENDED_LEVEL = {1: 5, 2: 15, 3: 20, 4: 40}
REGION_SUCCESS_LEVELS = {1: 20, 2: 30, 3: 40, 4: 50}

# 炼金参数（工作站「炼药」页）

# 可倒入炼金锅的材料及其炼金经验：物品键 -> 经验。
ALCHEMY_MATERIALS = (
    ('mushroom', 1),      # 蘑菇
    ('slime', 2),         # 粘液
    ('green_herb', 3),    # 绿草药
    ('yellow_herb', 5),   # 黄草药
    ('red_herb', 7),      # 红草药
)
ALCHEMY_MATERIAL_EXP = dict(ALCHEMY_MATERIALS)

# 升到下一级所需炼金经验分档：(等级上限, 该档每级所需经验)。
# 前 10 级每级 10 点，11~20 级每级 30 点，20 级以后每级 50 点。
ALCHEMY_XP_TIERS = ((10, 10), (20, 30), (None, 50))


def alchemy_xp_to_next(level):
    """从 level 升到 level+1 所需的炼金经验。"""
    level = max(1, int(level))
    for cap, need in ALCHEMY_XP_TIERS:
        if cap is None or level <= cap:
            return need
    return ALCHEMY_XP_TIERS[-1][1]

REGIONS = {
    # 地区编号：平原=1（保底，不消耗面包）
    '1': {'fixed_minutes': 5, 'name': '风和平原', 'difficulty': '简单', 'fallback': True,
          'recommended_level': 1, 'min_level': 1,
          'extra_treasure_max': 1,
          'treasure_quality_weights': TREASURE_REGION_QUALITY_WEIGHTS[1],
          'treasure_quality_caps': TREASURE_REGION_QUALITY_CAPS.get(1, {}),
          'description': '风和平原：不消耗面包，探险时间可选5、10或15分钟。等级低于最低要求时成功率固定10%；20级时基准成功率最高95%，实际成功率还会按事件难度（0.7~1.0）打折。',
          'desc': '推荐 1 级 · 可选 5/10/15 分钟' },
    # 低语森林=2（自由时间 5~30 分钟）
    '2': {'name': '低语森林', 'difficulty': '困难', 'fallback': False,
          'recommended_level': 10, 'min_level': 5,
          'extra_treasure_max': 2, 'xp_per_min_min': XP_FOREST_PER_MIN_MIN,
          'xp_per_min_max': XP_FOREST_PER_MIN_MAX,
          'treasure_quality_weights': TREASURE_REGION_QUALITY_WEIGHTS[2],
          'treasure_quality_caps': TREASURE_REGION_QUALITY_CAPS.get(2, {}),
          'description': '低语森林：需要等级至少 5，低于 5 级成功率固定 10%。每 5 分钟消耗 1 个面包，30 级时基准成功率最高 95%（再按事件难度打折），成功结算 3 次后解锁灰石谷。',
          'desc': '推荐 10 级 · 自由 5~30 分钟（5 的倍数）' },
    '3': {'name': '灰石谷', 'difficulty': '极难', 'fallback': False,
          'recommended_level': 20, 'min_level': 15,
          'extra_treasure_max': 3, 'xp_per_min_min': 18,
          'xp_per_min_max': 26,
          'treasure_quality_weights': TREASURE_REGION_QUALITY_WEIGHTS[3],
          'treasure_quality_caps': TREASURE_REGION_QUALITY_CAPS.get(3, {}),
          'description': '灰石谷：需要等级至少 15，并且低语森林成功结算 3 次，低于 15 级成功率固定 10%。每 5 分钟消耗 1 个面包，40 级时基准成功率最高 95%（再按事件难度打折）。',
          'unlock_forest_clears': 3,
          'desc': '推荐 20 级 · 自由 5~30 分钟（5 的倍数）' },
    # 圆心湖=4（推荐30~50级）
    '4': {'name': '圆心湖', 'difficulty': '极难', 'fallback': False,
          'recommended_level': 40, 'min_level': 30,
          'xp_per_min_min': 0, 'xp_per_min_max': 0,
          'extra_treasure_max': 3,
          'treasure_quality_weights': TREASURE_REGION_QUALITY_WEIGHTS[4],
          'treasure_quality_caps': TREASURE_REGION_QUALITY_CAPS.get(4, {}),
          'description': '圆心湖：尚未实装。推荐等级 30~50。',
          'desc': '推荐 40 级 · 自由 5~30 分钟' },
}

# 物品 / 集市参数
ITEMS = {
    # id: 名称/类型/分类/品质/描述/效果/价格（price 为空=集市不可购买）
    # category 仓库分类：物品 / 特殊 / 装备 / 书籍 / 头饰 / 服装 / 饰品
    'bread': {'name': '面包', 'kind': '食物', 'category': '物品',
              'quality': '普通',
              'desc': '探险时消耗的干粮，不能直接食用。除平原外，每探险 5 分钟需要 1 个。',
              'price': 15, 'regions': []},
    'apple': {'name': '树果', 'kind': '食物', 'category': '物品',
              'quality': '普通',
              'desc': '探险时捡到的果子，吃了能获得经验。',
              'exp': 10, 'price': None, 'regions': [1, 2]},
    'poultry': {'name': '禽肉', 'kind': '食物', 'category': '物品',
                'quality': '普通',
                'desc': '从鸟类或鸟型怪兽身上获得的肉，吃了能获得经验。',
                'exp': 15, 'price': None, 'regions': [1, 2]},
    'mushroom': {'name': '蘑菇', 'kind': '食物', 'category': '物品',
                 'quality': '普通',
                 'desc': '森林里采到的蘑菇，吃下后有小概率肠胃不适。',
                 'exp': 10, 'price': None, 'regions': [2],
                 'eat_effect': {'hp_loss_chance': 0.20,
                                'hp_loss_ratio': 0.05}},
    'bird_egg': {'name': '鸟蛋', 'kind': '食物', 'category': '物品',
                 'quality': '普通',
                 'desc': '从鸟巢里发现的鸟蛋，吃了能获得经验。',
                 'exp': 12, 'price': None, 'regions': [1, 2]},
    'beast_meat': {'name': '兽肉', 'kind': '食物', 'category': '物品',
                   'quality': '普通',
                   'desc': '从野兽身上获得的肉，吃了能获得较多经验。',
                   'exp': 20, 'price': None, 'regions': [1, 2]},
    'green_herb': {'name': '绿草药', 'kind': '材料', 'category': '物品',
                   'quality': '普通',
                   'desc': '带有清新草木香气的绿色草药。',
                   'price': None, 'regions': [1, 2]},
    'yellow_herb': {'name': '黄草药', 'kind': '材料', 'category': '物品',
                    'quality': '普通',
                    'desc': '晒干后仍带着温暖香气的黄色草药。',
                    'price': None, 'regions': [2]},
    'red_herb': {'name': '红草药', 'kind': '材料', 'category': '物品',
                 'quality': '普通',
                 'desc': '颜色鲜艳的红色草药。',
                 'price': None, 'regions': [2, 3]},
    'flint': {'name': '燧石', 'kind': '材料', 'category': '物品',
              'quality': '普通',
              'desc': '敲击时能产生火花的坚硬石块。',
              'price': None, 'regions': [1, 3]},
    'ore': {'name': '矿石', 'kind': '材料', 'category': '物品',
            'quality': '普通',
            'desc': '表面带着金属光泽的矿石。',
            'price': None, 'regions': [3]},
    'jump_guide': {'name': '猫咪跳远指南', 'kind': '书籍', 'category': '书籍',
                   'quality': '稀有',
                   'desc': '教猫咪如何立定跳远的小册子，勾选后会让猫咪偶尔练习跳远。',
                   'price': 1000},
    'pat_guide': {'name': '乖，摸摸头', 'kind': '书籍', 'category': '书籍',
                  'quality': '稀有',
                  'desc': '一本教猫咪亲近人的小册子，勾选后猫咪偶尔会伸手抓鼠标。',
                  'price': None},
    'hair_dye': {'name': '染发剂', 'kind': '道具', 'category': '特殊',
                 'quality': '稀有',
                 'desc': '一瓶染发剂，可以改变猫咪头发、耳朵和尾巴的颜色。',
                 'price': 300},
    'lens': {'name': '美瞳片', 'kind': '道具', 'category': '特殊',
             'quality': '稀有',
             'desc': '一次性美瞳，可以改变猫咪眼睛的颜色。',
             'price': 100},
    'dye': {
        'name': '染料', 'kind': '道具', 'category': '特殊',
        'quality': '少见',
        'desc': '为头饰、服装或饰品调色时消耗的染料。',
        'price': 50,
    },
    'sunglasses': {
        'name': '太阳镜', 'kind': '头饰', 'category': '头饰',
        'quality': '少见', 'hidden_attribute': '眼部',
        'desc': '一副适合猫咪尺寸的太阳镜，可以遮住眼睛。',
        'price': None,
    },
    'gold_earrings': {
        'name': '耳环', 'kind': '头饰', 'category': '头饰',
        'quality': '普通', 'hidden_attribute': '耳部',
        'desc': '精致的金色耳环，会随着耳朵一起晃动。',
        'price': None,
    },
    'hat_1': {
        'name': '鸭舌帽', 'kind': '头饰', 'category': '头饰',
        'quality': '少见', 'hidden_attribute': '帽子',
        'desc': '一顶可以调色的鸭舌帽。',
        'price': None,
    },
    'hat_ji': {
        'name': '一只小鸡', 'kind': '头饰', 'category': '头饰',
        'quality': '史诗', 'hidden_attribute': '帽子',
        'desc': '小鸡造型的头饰，可以调色并放大缩小。',
        'price': None,
    },
    'hat_2': {
        'name': '小洋帽', 'kind': '头饰', 'category': '头饰',
        'quality': '稀有', 'hidden_attribute': '帽子',
        'desc': '一顶可分别调整棕色和米白色部分的小洋帽。',
        'price': None,
    },
    'fine_collar': {
        'name': '细项圈', 'kind': '饰品', 'category': '饰品',
        'quality': '普通', 'hidden_attribute': '项链',
        'desc': '款式纤细的项圈，可以选择心形或星形装饰并自由配色。',
        'price': None,
    },
    'white_moon': {
        'name': '白月服饰', 'kind': '服装', 'category': '服装',
        'quality': '稀有', 'clothes_style': 'white_moon',
        'desc': '兽族贵族在宗教仪式中穿着的白色月纹服饰。',
        'price': None,
    },
    'black_sun': {
        'name': '黑日服饰', 'kind': '服装', 'category': '服装',
        'quality': '稀有', 'clothes_style': 'black_sun',
        'desc': '兽族贵族在宗教仪式中穿着的黑色日纹服饰。',
        'price': None,
    },
    'blue_noble': {
        'name': '蓝色贵族服饰', 'kind': '服装', 'category': '服装',
        'quality': '少见', 'clothes_style': 'blue_noble',
        'desc': '剪裁考究的蓝色贵族服饰，低调而正式。',
        'price': None,
    },
    'clown': {
        'name': '小丑服饰', 'kind': '服装', 'category': '服装',
        'quality': '少见', 'clothes_style': 'clown',
        'desc': '冒险者职业“小丑”的特色服装，色彩鲜艳而夸张。',
        'price': None,
    },
    'expression_secret': {
        'name': '表情管理-生无可恋', 'kind': '书籍', 'category': '书籍',
        'quality': '少见', 'price': None,
        'desc': '完成“痛苦猫”成就后解锁。待机时使用生无可恋表情，单击时眼睛只会选择 eye_2 或 eye_close3。',
    },
    'expression_happy': {
        'name': '表情管理-天天开心！', 'kind': '书籍', 'category': '书籍',
        'quality': '少见', 'price': None,
        'desc': '表情管理书：不触发动作时使用原来的开心日常表情。',
    },
    'expression_grumpy': {
        'name': '表情管理-没头脑和不高兴', 'kind': '书籍', 'category': '书籍',
        'quality': '少见', 'price': None,
        'desc': '完成“不耐烦！”成就后解锁。待机时使用不高兴的日常表情，单击时嘴巴固定为 mouth_sad。',
    },
    'expression_comfy': {
        'name': '表情管理-无所谓喵', 'kind': '书籍', 'category': '书籍',
        'quality': '少见', 'price': None,
        'desc': '完成“幸福猫”成就后解锁。待机时使用无所谓喵表情，不再眨眼；单击时眼睛只会选择 eye_close3 或 eye_comfy。',
    },
    'hairstyle_tool': {
        'name': '理发工具', 'kind': '道具', 'category': '特殊',
        'quality': '普通', 'price': 300,
        'desc': '一次性理发工具，在仓库中使用后可以切换猫咪发型。',
    },
    'name_collar': {
        'name': '新项圈', 'kind': '道具', 'category': '特殊',
        'quality': '稀有', 'price': 200,
        'desc': '使用后可以为猫猫重新命名，消耗一个。',
    },
    'throat_lozenge': {
        'name': '润喉糖', 'kind': '道具', 'category': '特殊',
        'quality': '稀有', 'display_quality': '蓝色',
        'quality_color': '#3498db', 'price': None,
        'desc': '一次性润喉糖，使用后可以试听并更换猫咪的单击音效。',
    },
}

# Excel 中的内容会覆盖默认文案/品质；文件缺失时继续使用内置表。
CONTENT_REPOSITORY = ContentRepository(
    _asset_dir(), frozen=getattr(sys, 'frozen', False))
CONTENT_RESULT = CONTENT_REPOSITORY.load(ITEMS)
ITEMS = dict(CONTENT_RESULT.items)
# 炼药产出的消耗品：物品簿里只写基础药水，前缀变体（5 档 × 4 个 = 20 种）
# 在代码里生成后补进物品表，合成时随机抽一个前缀。
POTION_VARIANTS = register_potion_items(ITEMS)
EVENT_BOOK_CONTENT = CONTENT_RESULT.event_book
TREASURE_BOOK_CONTENT = CONTENT_RESULT.treasure_book
TREASURE_PREFIX_CONTENT = CONTENT_RESULT.treasure_prefixes
CONTENT_ERRORS = list(CONTENT_RESULT.errors)
for _region_id, _region_config in CONTENT_RESULT.region_config.items():
    if _region_id not in REGIONS:
        continue
    try:
        _extra_max = max(0, int(_region_config.get('extra_treasure_max', 0)))
    except (TypeError, ValueError):
        continue
    REGIONS[_region_id]['extra_treasure_max'] = _extra_max
    _description = str(_region_config.get('description') or '').strip()
    if _description:
        REGIONS[_region_id]['description'] = _description
    _raw_weights = _region_config.get('quality_weights')
    if isinstance(_raw_weights, dict):
        _weights = {}
        for _quality, _weight in _raw_weights.items():
            try:
                _quality = int(_quality)
                _weight = max(0.0, float(_weight))
            except (TypeError, ValueError):
                continue
            if 1 <= _quality <= 6:
                _weights[_quality] = _weight
        if _weights:
            REGIONS[_region_id]['treasure_quality_weights'] = _weights
ITEM_BY_CODE = build_code_lookup(ITEMS)
CONTENT_REPOSITORY.write_error_log(CONTENT_ERRORS)
if CONTENT_ERRORS:
    print('[content] 内容校验发现问题：', file=sys.stderr)
    for _content_error in CONTENT_ERRORS:
        print('  ' + _content_error, file=sys.stderr)

install_warehouse_globals(globals())
install_market_globals(globals())
install_adventure_globals(globals())
install_adventure_page_globals(globals())
install_workstation_globals(globals())
install_renderer_globals(globals())
install_interaction_globals(globals())
install_achievement_globals(globals())
install_admin_globals(globals())


class DesktopPet(RendererMixin, InteractionAnimationMixin, AnimationMixin, EditorEnhancementsMixin, AdminMixin, AchievementMixin, WarehouseMixin, MarketMixin, AdventureMixin, AdventurePageMixin, WorkstationMixin):
    def _show_content_load_errors(self):
        """在终端和发布版窗口中报告 Excel/JSON 内容问题。"""
        errors = list(CONTENT_ERRORS)
        if not errors:
            return
        text = CONTENT_RESULT.format_errors(20)
        try:
            import tkinter.messagebox as mb
            mb.showwarning(
                '内容数据校验',
                text + '\n\n完整记录：~/.cat_pet_content_errors.log')
        except Exception:
            pass

    def _handle_content_errors(self, errors):
        if not errors:
            return
        CONTENT_REPOSITORY.write_error_log(errors)
        for error in errors:
            print('[content] ' + str(error), file=sys.stderr)

    def _set_comfy_active(self, active):
        self._comfy_active = bool(active)
        if self._comfy_active:
            self.motion.set_expression('expression_comfy', {
                'brow': 'brow', 'eye': 'eye_comfy',
                'mouth': 'mouth_comfy'})
        else:
            self.motion.clear_expression('expression_comfy')

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('桌宠')
        self.root.attributes('-topmost', True)  # 置顶

        # 设置透明色
        self.root.attributes('-transparentcolor', TRANSPARENT_COLOR)

        # 无边框透明窗口
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        if CONTENT_ERRORS:
            self.root.after(200, self._show_content_load_errors)

        # 分层素材加载：head -> tail -> 眼睛 -> 眉毛 -> 嘴 -> 耳朵 -> 衣服
        self.parts = {
            'head': PIL.Image.open(HEAD_PATH).convert('RGBA'),
            'hair_1': PIL.Image.open(HAIR1_PATH).convert('RGBA'),
            'hair_1_1': PIL.Image.open(HAIR1_1_PATH).convert('RGBA'),
            'hair_2': PIL.Image.open(HAIR2_PATH).convert('RGBA'),
            'tail': PIL.Image.open(TAIL_PATH).convert('RGBA'),
            'eye': PIL.Image.open(EYE_PATH).convert('RGBA'),
            'eye_close1': PIL.Image.open(EYE_CLOSE1_PATH).convert('RGBA'),
            'eye_close2': PIL.Image.open(EYE_CLOSE2_PATH).convert('RGBA'),
            'eye_close3': PIL.Image.open(EYE_CLOSE3_PATH).convert('RGBA'),
            'eye_comfy': PIL.Image.open(EYE_COMFY_PATH).convert('RGBA'),
            'eye_1': PIL.Image.open(EYE1_PATH).convert('RGBA'),
            'eye_2': PIL.Image.open(EYE2_PATH).convert('RGBA'),
            'brow': PIL.Image.open(BROW_PATH).convert('RGBA'),
            'brow_1': PIL.Image.open(BROW1_PATH).convert('RGBA'),
            'mouth_happy': PIL.Image.open(MOUTH_HAPPY_PATH).convert('RGBA'),
            'mouth_huya': PIL.Image.open(MOUTH_HUYA_PATH).convert('RGBA'),
            'mouth_sad': PIL.Image.open(MOUTH_SAD_PATH).convert('RGBA'),
            'mouth_comfy': PIL.Image.open(MOUTH_COMFY_PATH).convert('RGBA'),
            'ear_left': PIL.Image.open(EAR_LEFT_PATH).convert('RGBA'),
            'ear_right': PIL.Image.open(EAR_RIGHT_PATH).convert('RGBA'),
            'clothes': PIL.Image.open(CLOTHES_PATH).convert('RGBA'),
            'clothes_hefu_blue': PIL.Image.open(CLOTHES_HEFU_BLUE_PATH).convert('RGBA'),
            'clothes_hefu_green': PIL.Image.open(CLOTHES_HEFU_GREEN_PATH).convert('RGBA'),
            'clothes_hefu_red': PIL.Image.open(CLOTHES_HEFU_RED_PATH).convert('RGBA'),
            'clothes_thief': PIL.Image.open(CLOTHES_THIEF_PATH).convert('RGBA'),
            'clothes_knight': PIL.Image.open(CLOTHES_KNIGHT_PATH).convert('RGBA'),
            'clothes_peasant': PIL.Image.open(CLOTHES_PEASANT_PATH).convert('RGBA'),
            'clothes_whitemoon': PIL.Image.open(CLOTHES_WHITEMOON_PATH).convert('RGBA'),
            'clothes_blacksun': PIL.Image.open(CLOTHES_BLACKSUN_PATH).convert('RGBA'),
            'clothes_noble_blue': PIL.Image.open(CLOTHES_NOBLE_BLUE_PATH).convert('RGBA'),
            'clothes_clown': PIL.Image.open(CLOTHES_CLOWN_PATH).convert('RGBA'),
            'north_maid1': PIL.Image.open(CLOTHES_NORTH_MAID_PATH).convert('RGBA'),
            'north_night': PIL.Image.open(CLOTHES_NORTH_NIGHT_PATH).convert('RGBA'),
            'north_windbreaker': PIL.Image.open(CLOTHES_NORTH_WIND_PATH).convert('RGBA'),
            'sunglasses': PIL.Image.open(SUNGLASSES_PATH).convert('RGBA'),
            'gold_earrings': PIL.Image.open(GOLD_EARRINGS_PATH).convert('RGBA'),
            'hat_1': PIL.Image.open(HAT1_PATH).convert('RGBA'),
            'hat_ji': PIL.Image.open(HAT_JI_PATH).convert('RGBA'),
            'hat_2': PIL.Image.open(HAT2_PATH).convert('RGBA'),
            'fine_collar1': PIL.Image.open(FINE_COLLAR1_PATH).convert('RGBA'),
            'fine_collar2': PIL.Image.open(FINE_COLLAR2_PATH).convert('RGBA'),
            'hand': PIL.Image.open(HAND_PATH).convert('RGBA'),
        }
        for _part_key, _filename in CLICK_EXPRESSION_CONFIG.get(
                'assets', {}).items():
            _path = _asset_path(_filename, 'body')
            if os.path.exists(_path):
                self.parts[_part_key] = PIL.Image.open(_path).convert('RGBA')
        self._click_expression_config = CLICK_EXPRESSION_CONFIG
        self._click_expression_config_path = CLICK_EXPRESSION_CONFIG_PATH
        self.pose = 'normal'   # 当前姿势：normal / blink / drag / ear
        self._tail_tilt = 0.0  # 尾巴摆动方向
        self._tail_sign = 1    # 尾巴左右交替
        self._scratch_side = 'left'   # 挠头用手：left / right
        self._scratch_stage = -1      # 挠头阶段（-1 未进行）
        self._scratch_lift = 0.0      # 手抬起进度 0~1（用于轨迹）
        self._scratch_frames = []     # 挠头动作帧序列
        # 招手/舔手用 _idle_hand_*（t 是动作进度 0~1，两条渲染通路共用）。
        # _idle_head_sway 是旧「转头环顾」留下的字段，动作已移除，仅保留
        # 字段本身供 _breath_tick 等处的 busy 判断与复位沿用（恒为 0）。
        self._idle_head_sway = 0.0    # 当前头部转动角度（度，恒为 0）
        self._idle_hand_action = None  # 'wave' / 'lick' / None
        self._idle_hand_side = 'left'  # 用哪只手
        self._idle_hand_t = 0.0        # 动作进度 0~1
        self._idle_hand_phase = 1.0    # 摆动方向 ±1
        self._wave_frames = []         # 招手的帧序列
        self._lick_frames = []         # 舔手的帧序列
        # 待机呼吸感：静止时的极小幅纵向起伏，独立于其它动作
        self._breath_job = None        # 呼吸循环句柄
        self._breath_t0 = 0.0          # 呼吸周期起点（秒）
        self._breathing = False        # 呼吸循环是否在跑
        self.scale = 1.0
        self.closing = False
        self.animations = AnimationController(
            self.root, lambda: getattr(self, 'closing', False))
        self.motion = AnimationStateMachine(self)
        self.render_cache = RenderCache()
        self.facing_right = False  # 猫是否朝右（向右走时水平翻转），须在首次 update_image 前初始化

        self._forced_expression = None

        self._panel = None               # 面板窗口
        self._panel_text = None          # 面板上的数字标签
        self._panel_bar = None           # 面板上的进度条
        self._panel_job = None           # 面板刷新定时任务
        self._admin_win = None           # 管理员调试窗口
        self._admin_entry = None         # 管理员输入框（旧引用保留）
        self._admin_entries = {}         # 管理员各字段输入框
        self._admin_hp_label = None      # 管理员活力显示

        # 唯一游戏状态：旧 self.hp/self.gold 等属性通过代理指向这里
        self.save_service = SaveService(
            SATIETY_SAVE_PATH, ITEMS, STARTING_GIFT_ITEMS,
            STARTING_BREAD, CLOTHES_NAMES, EXPRESSION_BOOK_ORDER,
            DEFAULT_EQUIPMENT_SETTINGS, hp_initial=HP_INITIAL,
            hp_max_initial=HP_MAX, strength_initial=STRENGTH_INITIAL,
            wisdom_initial=WISDOM_INITIAL, agility_initial=AGILITY_INITIAL,
            luck_initial=LUCK_INITIAL, emotion_initial=EMOTION_INITIAL,
            gold_initial=STARTING_GOLD)
        self.game = self.save_service.load()
        try:
            activated = False
            if self.cat_name:
                activated = bool(SpecialEventService.activate(
                    self.game, 'first_naming')) or activated
            if int(getattr(self.game, 'strength', 0)) >= 13:
                activated = bool(SpecialEventService.activate(
                    self.game, 'strength_13')) or activated
            if activated:
                self.save_service.save(self.game)
        except Exception:
            pass
        try:
            self._loaded_cat_scale = float(
                getattr(self.game, 'cat_scale', 1.0))
        except (TypeError, ValueError):
            self._loaded_cat_scale = 1.0
        try:
            self.sound_volume = max(
                0, min(100, int(getattr(self.game, 'sound_volume', 100))))
        except (TypeError, ValueError):
            self.sound_volume = 100
        self.game.sound_volume = self.sound_volume
        # 帧率同样要在构造时就从存档生效：否则设置了 60 帧、
        # 重启后又悄悄退回 30 帧（动画节拍由 anim_frame_ms() 决定）。
        # 必须早于下面任何 after/schedule 动画的注册。
        try:
            self.frame_rate = set_anim_fps(
                int(getattr(self.game, 'frame_rate', 30)))
        except (TypeError, ValueError):
            self.frame_rate = set_anim_fps(30)
        self.game.frame_rate = self.frame_rate
        click_sound = str(getattr(self.game, 'click_sound', 'cat1') or 'cat1')
        if click_sound not in CLICK_SOUND_PATHS:
            click_sound = 'cat1'
        self.click_sound = click_sound
        self._active_click_sound_path = CLICK_SOUND_PATHS[click_sound]
        self.game.click_sound = click_sound
        StatsService.ensure(self.game)
        self._unlock_treasure_bonuses()
        StatsService.sample_state(self.game)
        self.achievement_catalog = AchievementService.load_catalog(_asset_dir())
        AchievementService.sync_unlocks(
            self.game, self.achievement_catalog, ITEMS)
        self._sync_expression_book_unlocks()
        self._online_session_started = time.monotonic()
        self._online_job = None
        self._treasure_uid = max(
            (int(t.get('uid', 0)) for t in self.treasures), default=0)
        self._event_book = None           # 探险事件簿缓存
        self._treasure_book = None        # 宝藏基础数据缓存
        self._treasure_prefixes = None    # 宝藏前缀缓存
        self._panel_rows = {}        # 状态窗口各行 (文字标签, 进度条)
        self._attr_text = None       # 力量/智慧/幸运 文字标签
        self._skill_text = None      # 等级/经验/技能点文字
        self.adventuring = False             # 是否正在探险
        self._adventure_job = None           # 探险定时任务
        self._adventure_region = None        # 当前探险地区
        self._adventure_minutes = 0          # 当前探险时长
        self._adventure_bread_cost = 0       # 本次探险消耗面包数
        self._adventure_depart_job = None    # 离场动画任务
        self._adventure_title_job = None     # 托盘剩余时间刷新任务
        self._adventure_end_time = None      # 探险结束时间
        self._adventure_departing = False    # 是否正在播放离场动画
        self._log_win = None                 # 探险日志窗口
        self._adventure_win = None           # 探险页面
        self._warehouse_win = None           # 仓库窗口
        self._workstation_win = None         # 工作站窗口
        self._workstation_tab = None         # 工作站当前标签
        self._workstation_tabbar = None      # 工作站标签栏
        self._workstation_tab_buttons = {}
        self._workstation_body = None        # 工作站中间内容栏
        self._workstation_text = None        # 工作站金币文字
        self._workstation_title_label = None
        self._workstation_banner_label = None
        self._warehouse_text = None          # 仓库金币文字
        self._warehouse_items = None         # 仓库物品列表容器
        self._warehouse_job = None           # 仓库刷新定时任务
        self._warehouse_pages = None         # 仓库分类页
        self._warehouse_cat = '宝藏'
        self._food_spins = {}
        self._selected_food = None
        self._last_food_status = ''
        self._exp_preview_gain = 0
        self._exp_flash_on = False
        self._exp_flash_job = None
        self._exp_canvas = None
        self._exp_level_label = None
        self._hp_canvas = None
        self._emotion_canvas = None
        self._preview_pose = 'normal'
        self._preview_tail_tilt = 0.0
        self._preview_anim_job = None
        self._warehouse_list = None
        self._treasure_lock_mode = False
        self._treasure_lock_button = None
        self._click_expression = None
        self._click_expression_job = None
        self._last_click_reaction = 0.0
        self._click_sound_paths = None
        self._click_sound_cache_key = None
        self._hover_job = None
        self._hover_win = None
        self._pending_slots = {
            key: list(value) if isinstance(value, list) else value
            for key, value in self.equipped_slots.items()
        }
        self._pending_equip_settings = dict(self.equip_settings)
        self._collar_color_cache = {}
        self._earring_color_cache = {}
        self._hat_color_cache = {}
        self._sunglasses_adjust_win = None
        self._hat_scale_win = None
        self._hairstyle_win = None
        self._equip_slot = '头饰'
        self._preview_facing = self.facing_right
        self._equip_preview_photo = None
        self._equip_preview_label = None
        self._equip_status = None
        self._equip_stats_label = None
        self._pending_clothes = self.equipped_clothes
        self._pending_hair_color = self.hair_color
        self._hair_cache = {}
        self._pending_normal_clothes_color = self.normal_clothes_color
        self._clothes_color_cache = {}
        self._palette_win = None
        self._palette_kind = 'hair'
        self._pending_eye_color = self.eye_color
        self._eye_cache = {}
        self._pending_books_enabled = set(self.books_enabled)
        self._pending_hair_style = self.hair_style
        self._pending_item_uses = {}
        self._pending_color_changes = set()
        self._market_win = None              # 集市窗口
        self._market_gold = None             # 集市金币标签
        self._market_items = None            # 集市商品容器
        self._market_status = None           # 集市状态提示
        self._market_job = None              # 集市刷新定时任务
        self._regen_job = None               # 回血检查计时（每 1 分钟）
        self._emotion_job = None             # 情绪自然变化计时（每 5 分钟）
        self._emotion_face = None            # 头顶颜文字窗口
        self._emotion_face_job = None
        self._emotion_face_until = 0.0
        self.hospitalized = False            # 是否在住院
        self._hospital_job = None
        # 药水蒙版：当前生效的持续状态（{蒙版键: 到期时间(monotonic)}）。
        # 蒙版键会进渲染缓存键，所以单独缓存一份签名，只在变化时更新。
        self._potion_masks = {}
        self._potion_mask_signature = ()
        self._potion_mask_job = None

        # 系统托盘相关
        self._tray_icon = None           # pystray 托盘图标
        self._tray_quit = False          # 托盘“退出”请求标志
        self._tray_cmd = None            # 托盘发来的指令（由主线程轮询执行）

        # 比例调节悬浮条相关
        self.scale_win = None          # 悬浮条窗口
        self.scale_percent = None      # 滑块当前值（百分比）
        self.scale_value_label = None  # 显示当前百分比的标签
        self.scale_slider = None       # 比例滑块
        self.sound_percent = None      # 整体音效当前值
        self.sound_value_label = None  # 整体音效百分比标签
        self.sound_slider = None       # 整体音效滑块
        self._bar_drag_active = False

        # 创建标签显示图片，并应用保存的猫咪比例。
        self._click_bounce_frames = []
        self._click_bounce_scale = (1.0, 1.0)
        self._last_click_bounce = 0.0
        self.label = tk.Label(self.root, bg=TRANSPARENT_COLOR, cursor='arrow')
        self.label.pack()
        self.set_scale(getattr(self, '_loaded_cat_scale', 1.0))
        self.update_image()

        # 拖拽相关变量
        self.dragging = False
        self.moved = False
        self._drag_mode = 1  # 抓取反抗模式 1/2/3
        self._jump_state = None   # 跳跃状态
        self._jump_hand_mode = ''
        self._jump_job = None
        self._jump_t0 = 0.0
        self._jump_start = (0, 0)
        self._jump_dir = 1
        self._jump_charge_steps = 8
        self._set_comfy_active(False)
        self._idle_exp_job = None
        self._falling_hands = False
        self._bounce_job = None
        self._bounce_t0 = 0.0
        self._bounce_ground = 0
        self._bounce_active = False
        self._bounce_hand_progress = 0.0
        self._hand_lift = 0.0        # 0=身侧 1=头顶
        self._fall_lift_factor = 0.0
        self._reach_facing = False
        self._reach_state = None
        self._reach_hand = 'left'
        self._reach_dir = (0.0, 0.0)
        self._reach_progress = 0.0
        self._reach_job = None
        self._mouse_armed = True
        self._last_mouse = (0, 0)
        self._last_mouse_time = time.monotonic()
        self._last_reach_time = 0.0
        self._mouse_check_job = None
        self.drag_start_x = 0
        self.drag_start_y = 0

        # 拖动晃动相关
        self.swaying = False      # 是否正在晃动
        self._sway_job = None     # 晃动动画定时任务
        self._sway_t0 = 0.0       # 晃动开始时间
        self._sway_angle = 0.0    # 当前晃动角度
        self._sway_pc = None      # 旋转轴在晃动画布中的坐标 (px, py)
        self._sway_size = None    # 晃动画布尺寸 (w, h)
        self._drag_base = None    # 缩放好的拖动图（作为旋转底图）
        self._drag_samples = []   # 松手前短时间内的鼠标轨迹
        self.flinging = False     # 是否正在被甩飞
        self._fling_job = None    # 甩飞动画任务
        self._fling_vx = 0.0      # 当前水平速度（像素/帧）
        self._fling_vy = 0.0      # 当前垂直速度（像素/帧）
        self._fling_anim_counter = 0  # 甩飞画面刷新计数器
        self._fling_landing_y = None  # 坠落目标位置；None 表示动态检测
        self._fling_bounces = 0       # 已经发生的落地弹跳次数
        self.climbing = False         # 是否正在从任务栏下方向上爬
        self._climb_job = None
        self._climb_t0 = 0.0
        self._climb_start_y = 0
        self._climb_target_y = 0
        self._climb_hand_progress = 0.0
        self._climb_hand_mode = 'normal'
        self._climb_edge_y = 0

        # 自主走动 / 掉落相关
        self.walking = False          # 是否正在自主走动
        self.walk_dir = 1             # 行走方向：1 右，-1 左
        self._walk_job = None         # 走动定时任务
        self._walk_t0 = 0.0           # 本次走动开始时间
        self._walk_end = 0.0          # 本次走动结束时间
        self.falling = False          # 是否正在掉落
        self._fall_job = None         # 掉落/检查定时任务
        self._fall_vy = 0.0           # 掉落速度
        self._on_taskbar = False      # 是否已落在任务栏上

        # 随机动作定时任务 id
        self._anim_job = None
        self._meow_job = None

        # 绑定事件
        self.label.bind('<Button-1>', self.on_drag_start)
        self.label.bind('<B1-Motion>', self.on_drag_motion)
        self.label.bind('<ButtonRelease-1>', self.on_drag_stop)
        self.label.bind('<Button-3>', self.show_menu)  # 右键菜单

        # 全局左键监听：悬浮条打开时，点悬浮条以外任意地方就关闭它
        self.root.bind_all('<Button-1>', self._on_global_click)

        # 窗口 / 任务栏图标：素材里的 ui/cat.png（多档尺寸，见 _load_window_icons）
        self._window_icons = self._load_window_icons()
        self._apply_default_window_icon()

        # 初始位置 - 屏幕右下角
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = screen_width - ICON_SIZE - 50
        y = max(0, self._desktop_bottom()
                - int(ICON_SIZE * CAT_FEET_RATIO))  # 初始脚底贴桌面底部
        self.root.geometry(f'{ICON_SIZE}x{ICON_SIZE}+{x}+{y}')

        # 开始随机动作（眨眼 / 耳朵动）
        self.start_animations()

        # 开始自主走动与任务栏掉落检查
        self._schedule_walk_attempt()
        self._start_fall_check()

        # 活力回复计时
        self._schedule_hp_regen()

        # 挂机经验奖励
        self._schedule_idle_exp()

        # 情绪自然变化
        self._schedule_emotion_change()

        # 在线时长统计
        self._schedule_online_tick()

        # 鼠标靠近检测
        self._schedule_mouse_check()

        # 系统托盘后台图标（探险状态也有提示）
        self._setup_tray()
        if not self.cat_name:
            self.root.after(300, self._prompt_cat_name)
        if self.hp <= 0:
            self.root.after(0, self._enter_hospital)

    # ---------- 图片显示 ----------

































    # ---------- 随机动作：眨眼 / 耳朵动两下 ----------































    def _reload_click_expression_config(self):
        """每次单击前重读概率配置，并加载尚未载入的新素材。"""
        path = getattr(self, '_click_expression_config_path', '')
        config = load_click_expression_config(path)
        for key, filename in config.get('assets', {}).items():
            if key in self.parts:
                continue
            asset_path = _asset_path(filename, 'body')
            if not os.path.exists(asset_path):
                continue
            try:
                self.parts[key] = PIL.Image.open(
                    asset_path).convert('RGBA')
            except Exception:
                pass
        self._click_expression_config = config

    def _reload_emoticons(self):
        """单击前重读颜文字配置，编辑 JSON 后无需重启。"""
        global EMOTICONS
        EMOTICONS = load_emoticons(EMOTICON_CONFIG_PATH)

    def show_emotion_face(self):
        """根据当前情绪显示黑边白字，并完成浮出、停留、上浮消失。"""
        self._reload_emoticons()
        self._reload_click_expression_config()
        self._cancel_emotion_face()
        if self.closing or self.hospitalized:
            return
        self._click_expression = self._random_click_expression()
        self.motion.set_expression('expression_click', self._click_expression)
        try:
            self.update_image()
            self._start_click_bounce()
        except Exception:
            pass
        self._click_expression_job = self.animations.schedule(
            'click_expression', CLICK_EXPRESSION_DURATION_MS,
            self._clear_click_expression)
        level = self._emotion_level()
        text_value = random.choice(EMOTICONS[level])
        from tkinter import font as tkfont
        font_obj = tkfont.Font(family='Microsoft YaHei UI', size=14,
                               weight='bold')
        width = font_obj.measure(text_value) + 18
        height = font_obj.metrics('linespace') + 16
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        win.attributes('-toolwindow', True)
        win.attributes('-transparentcolor', TRANSPARENT_COLOR)
        win.configure(bg=TRANSPARENT_COLOR)
        canvas = tk.Canvas(win, width=width, height=height,
                           bg=TRANSPARENT_COLOR, highlightthickness=0)
        canvas.pack()
        cx, cy = width // 2, height // 2
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2),
                       (-2, -2), (-2, 2), (2, -2), (2, 2)):
            canvas.create_text(cx + dx, cy + dy, text=text_value,
                               fill='black', font=font_obj)
        canvas.create_text(cx, cy, text=text_value,
                           fill='white', font=font_obj)
        self._hide_from_taskbar(win)
        win.after(80, lambda w=win: self._hide_from_taskbar(w))
        self._emotion_face = win
        self._emotion_face_label = canvas
        self._emotion_face_t0 = time.monotonic()
        self._position_emotion_face(eye_start=True)
        win.deiconify()
        StatsService.record_cat_click(self.game)
        self._check_achievements()
        self._save_satiety()
        try:
            win.lift()
        except Exception:
            pass
        self._emotion_face_job = self.animations.schedule('emotion_face', 
            EMOTION_FACE_FRAME_MS, self._emotion_face_tick)

    def _emotion_face_points(self):
        size = int(ICON_SIZE * self.scale)
        win = getattr(self, '_emotion_face', None)
        if win is None:
            return 0, 0, 0, 0
        win.update_idletasks()
        x = self.root.winfo_x() + size // 2 - win.winfo_width() // 2
        eye_y = self.root.winfo_y() + int(size * 0.22) - win.winfo_height() // 2
        head_y = self.root.winfo_y() - win.winfo_height() - 12
        return x, eye_y, head_y, win.winfo_width()

    def _position_emotion_face(self, y=None, alpha=1.0, eye_start=False):
        win = getattr(self, '_emotion_face', None)
        if win is None or not win.winfo_exists():
            return
        try:
            x, eye_y, head_y, width = self._emotion_face_points()
            if eye_start:
                y = eye_y
            if y is None:
                y = head_y
            screen_w = self.root.winfo_screenwidth()
            x = max(0, min(x, screen_w - width))
            y = max(0, int(y))
            win.geometry(f'+{int(x)}+{int(y)}')
            win.attributes('-alpha', max(0.0, min(1.0, alpha)))
            win.lift()
        except Exception:
            pass

    def _clear_click_expression(self):
        """提前结束单击表情，继续保留头顶颜文字的消失动画。"""
        self._click_expression_job = None
        had_click_expression = self._click_expression is not None
        self._click_expression = None
        self.motion.clear_expression('expression_click')
        if had_click_expression:
            try:
                self.update_image()
            except Exception:
                pass

    def _cancel_emotion_face(self):
        if self._click_expression_job is not None:
            try:
                self.animations.cancel('click_expression')
            except Exception:
                pass
            self._click_expression_job = None
        self._clear_click_expression()
        if getattr(self, '_emotion_face_job', None) is not None:
            try:
                self.animations.cancel('emotion_face')
            except Exception:
                pass
            self._emotion_face_job = None
        win = getattr(self, '_emotion_face', None)
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass
        self._emotion_face = None

    def _emotion_face_tick(self):
        self._emotion_face_job = None
        win = getattr(self, '_emotion_face', None)
        if win is None or not win.winfo_exists():
            self._emotion_face = None
            return
        elapsed = (time.monotonic() - self._emotion_face_t0) * 1000.0
        _, eye_y, head_y, _ = self._emotion_face_points()
        emerge_end = EMOTION_FACE_EMERGE_MS
        hold_end = emerge_end + EMOTION_FACE_HOLD_MS
        fade_end = hold_end + EMOTION_FACE_FADE_MS
        if elapsed < emerge_end:
            u = max(0.0, min(1.0, elapsed / max(1, emerge_end)))
            u = u * u * (3.0 - 2.0 * u)
            y = eye_y + (head_y - eye_y) * u
            alpha = 1.0
        elif elapsed < hold_end:
            y = head_y
            alpha = 1.0
        elif elapsed < fade_end:
            u = (elapsed - hold_end) / max(1, EMOTION_FACE_FADE_MS)
            y = head_y - EMOTION_FACE_RISE_PX * u
            alpha = 1.0 - u
        else:
            self._cancel_emotion_face()
            return
        self._position_emotion_face(y=y, alpha=alpha)
        self._emotion_face_job = self.animations.schedule('emotion_face', 
            EMOTION_FACE_FRAME_MS, self._emotion_face_tick)

    # ---------- 拖拽 + 以鼠标为轴晃动 ----------





















    # ---------- 自主走动 / 撞墙 / 掉落任务栏 ----------
















    def _record_obtained_items(self):
        """登记首次获得的物品，并标记对应仓库主页未读。"""
        if not hasattr(self.game, 'obtained_items'):
            self.game.obtained_items = set()
            for iid, count in self.inventory.items():
                try:
                    if int(count) > 0:
                        self.game.obtained_items.add(iid)
                except (TypeError, ValueError):
                    continue
            if not hasattr(self.game, 'new_item_categories'):
                self.game.new_item_categories = set()
            return False
        obtained = getattr(self.game, 'obtained_items', set())
        if not isinstance(obtained, set):
            obtained = set(obtained or ())
        unseen = getattr(self.game, 'new_item_categories', set())
        if not isinstance(unseen, set):
            unseen = set(unseen or ())
        changed = False
        for iid, count in self.inventory.items():
            try:
                owned = int(count) > 0
            except (TypeError, ValueError):
                owned = False
            if not owned or iid in obtained:
                continue
            obtained.add(iid)
            changed = True
            category = (ITEMS.get(iid) or {}).get('category')
            if category in ('物品', '装备'):
                unseen.add(category)
            elif category in ('特殊', '书籍', '头饰', '服装', '饰品'):
                # 「特殊」已并入装备页的子栏，红点直接点在装备上。
                unseen.add('装备')
        self.game.obtained_items = obtained
        self.game.new_item_categories = unseen
        return changed

    # ---------- 存档 / 状态面板 ----------
    def _save_satiety(self):
        """通过 SaveService 原子保存唯一 GameState。"""
        recorded = self._record_obtained_items()
        try:
            self.save_service.save(self.game)
            CONTENT_REPOSITORY.write_error_log(CONTENT_ERRORS)
        except Exception as exc:
            print('[save] ' + str(exc), file=sys.stderr)
        self._update_tray_title()
        if recorded and hasattr(self, '_refresh_warehouse_tab_indicators'):
            try:
                self._refresh_warehouse_tab_indicators()
            except Exception:
                pass
        try:
            self.update_image()
        except Exception:
            pass
        try:
            self._refresh_hp_bar()
        except Exception:
            pass
        try:
            self._refresh_emotion_bar()
        except Exception:
            pass













    def _calculate_max_hp(self):
        """根据等级和三维属性计算活力上限。"""
        return ProgressionService.calculate_max_hp(
            self.level, self.strength, self.wisdom, self.agility)

    def _sync_max_hp(self):
        """属性/等级变化后重算上限，并保留当前已损失活力数值。"""
        ProgressionService.recalculate_max_hp(self.game)
        return self.max_hp


    def show_status(self):
        """打开状态窗口：活力值 / 力量 / 智慧 / 敏捷"""
        if self._panel is not None and self._panel.winfo_exists():
            self._panel.lift()
            self._refresh_panel()
            return
        win = tk.Toplevel(self.root)
        win.title('状态')
        win.resizable(False, False)
        win.attributes('-toolwindow', True)  # 不显示在任务栏
        self._hide_from_taskbar(win)
        win.after(80, lambda w=win: self._hide_from_taskbar(w))
        self._panel = win
        # 带进度条的数值行
        self._panel_rows = {}
        for key, cname, cmax in (('hp', '活力值', self.max_hp),):
            row = tk.Frame(win)
            row.pack(padx=18, pady=(12, 2))
            lbl = tk.Label(row, text='', width=18, anchor='w',
                           font=('Microsoft YaHei UI', 10))
            lbl.pack(side='left')
            bar = tk.Canvas(row, width=150, height=12,
                            bg='#eeeeee', highlightthickness=0)
            bar.pack(side='left', padx=8)
            self._panel_rows[key] = (lbl, bar)
        # 纯数字属性
        self._attr_text = tk.Label(win, font=('Microsoft YaHei UI', 10),
                                   fg='#444444')
        self._attr_text.pack(padx=18, pady=(12, 14))
        win.protocol('WM_DELETE_WINDOW', self.close_panel)
        self._refresh_panel()

    def _schedule_hp_regen(self):
        """启动回血计时：每分钟检查一次，活力未满时回复。"""
        if self.closing:
            return
        if self._regen_job is None:
            self._regen_job = self.root.after(
                60 * 1000, self._hp_regen_tick)

    def _hp_regen_tick(self):
        """每分钟回一次活力：无论上限多少，0→满只需 10 分钟。"""
        self._regen_job = None
        if self.closing:
            return
        if self.hospitalized:
            self._regen_job = self.root.after(60 * 1000, self._hp_regen_tick)
            return
        if self.hp < self.max_hp:
            heal = ProgressionService.regen_per_minute(self.max_hp)
            self.hp = min(self.max_hp, self.hp + heal)
            self._save_satiety()
            self._refresh_panel()
        self._regen_job = self.root.after(
            60 * 1000, self._hp_regen_tick)

    def _schedule_emotion_change(self):
        if self.closing or self._emotion_job is not None:
            return
        self._emotion_job = self.root.after(
            EMOTION_CHANGE_MS, self._emotion_change_tick)

    def _emotion_change_tick(self):
        self._emotion_job = None
        if self.closing:
            return
        self.emotion = max(
            EMOTION_NATURAL_MIN,
            min(EMOTION_NATURAL_MAX,
                self.emotion + random.choice((-5, 5))))
        self._save_satiety()
        self._refresh_emotion_bar()
        self._schedule_emotion_change()

    def _check_hospital_state(self):
        if self.hp <= 0 and not self.hospitalized:
            self._enter_hospital()
            return True
        return False

    def _enter_hospital(self):
        if self.hospitalized or self.closing:
            return
        self.hospitalized = True
        self.motion.enter('hospital', force=True)
        self._cancel_anim()
        self._cancel_walk()
        self._cancel_fall()
        self._cancel_fling()
        self._cancel_climb()
        self._cancel_reach()
        self._cancel_jump()
        self._cancel_emotion_face()
        try:
            self.root.withdraw()
        except Exception:
            pass
        self._save_satiety()
        self._hospital_job = self.root.after(
            HOSPITAL_MS, self._leave_hospital)

    def _leave_hospital(self):
        self._hospital_job = None
        if self.closing:
            return
        self.hospitalized = False
        self.motion.finish('hospital', 'idle')
        self.hp = 1
        try:
            self.root.deiconify()
        except Exception:
            pass
        self._save_satiety()
        self.update_image()
        self.start_animations()
        self._schedule_walk_attempt()
        self._start_fall_check()
        self._schedule_hp_regen()
        self._schedule_emotion_change()

    # ---------- 药水蒙版（持续时间状态） ----------

    def refresh_potion_mask_state(self):
        """清掉已到期的蒙版并更新签名，返回签名是否变化。"""
        now = time.monotonic()
        masks = getattr(self, '_potion_masks', None)
        if not isinstance(masks, dict):
            masks = {}
            self._potion_masks = masks
        for key in [k for k, until in masks.items() if until <= now]:
            masks.pop(key, None)
        signature = tuple(sorted(masks))
        changed = signature != getattr(self, '_potion_mask_signature', ())
        self._potion_mask_signature = signature
        return changed

    def active_potion_masks(self):
        """当前生效的蒙版键元组（渲染层按此叠加蒙版）。"""
        return tuple(getattr(self, '_potion_mask_signature', ()) or ())

    def start_potion_mask(self, mask_key, duration_ms):
        """给猫咪叠加一层持续蒙版；同类蒙版取较晚的到期时间。"""
        spec = POTION_MASKS.get(mask_key)
        if spec is None or duration_ms <= 0:
            return False
        until = time.monotonic() + duration_ms / 1000.0
        masks = getattr(self, '_potion_masks', None)
        if not isinstance(masks, dict):
            masks = {}
            self._potion_masks = masks
        masks[mask_key] = max(masks.get(mask_key, 0.0), until)
        self.refresh_potion_mask_state()
        self._schedule_potion_mask_tick()
        self.update_image()
        return True

    def _schedule_potion_mask_tick(self):
        if getattr(self, 'closing', False):
            return
        if self._potion_mask_job is not None:
            return
        if not getattr(self, '_potion_masks', None):
            return
        self._potion_mask_job = self.root.after(
            POTION_MASK_TICK_MS, self._potion_mask_tick)

    def _potion_mask_tick(self):
        self._potion_mask_job = None
        if getattr(self, 'closing', False):
            return
        if self.refresh_potion_mask_state():
            self.update_image()
        self._schedule_potion_mask_tick()

    def _schedule_online_tick(self):
        self._online_job = self.root.after(60000, self._record_online_tick)

    def _record_online_tick(self):
        self._online_job = None
        now = time.monotonic()
        started = getattr(self, '_online_session_started', now)
        StatsService.add_online_seconds(self.game, now - started)
        self._online_session_started = now
        self._check_achievements()
        self._save_satiety()
        if not self.closing:
            self._schedule_online_tick()

    def _flush_online_time(self):
        now = time.monotonic()
        started = getattr(self, '_online_session_started', now)
        StatsService.add_online_seconds(self.game, now - started)
        self._online_session_started = now
        self._check_achievements()

    def _check_achievements(self):
        catalog = getattr(self, 'achievement_catalog', {})
        if not catalog:
            return set()
        StatsService.sample_state(self.game)
        newly = AchievementService.sync_unlocks(self.game, catalog, ITEMS)
        self._sync_expression_book_unlocks()
        if newly:
            try:
                self._refresh_achievement_ui()
            except Exception:
                pass
        if getattr(self, '_admin_stats_labels', None):
            self._refresh_admin_stats()
        return newly

    def _prompt_cat_name(self, consume_collar=False, force=False):
        if not force and self.cat_name:
            return
        if consume_collar and self.inventory.get('name_collar', 0) <= 0:
            self._alert('新项圈', '没有新项圈了，去杂货铺买一个吧。')
            return
        first_naming = not bool(self.cat_name)
        from tkinter import simpledialog
        name = simpledialog.askstring(
            '猫猫命名', '请为你的猫猫命名：',
            initialvalue=self.cat_name or '猫猫', parent=self.root)
        if name is None:
            if consume_collar or self.cat_name:
                return
            name = '猫猫'
        name = str(name).strip()[:12] or '猫猫'
        self.cat_name = name
        if first_naming:
            SpecialEventService.activate(self.game, 'first_naming')
        if consume_collar:
            self.inventory['name_collar'] = max(
                0, int(self.inventory.get('name_collar', 0)) - 1)
        self._save_satiety()
        title = getattr(self, '_warehouse_title_label', None)
        if title is not None:
            try:
                title.config(text=f'{self.cat_name}的仓库')
            except Exception:
                pass
        self._refresh_warehouse()
        self._refresh_admin_save_slots()
        if first_naming:
            self.root.after(0, self._open_tutorial_letter)

    def _open_tutorial_letter(self):
        """首次命名后打开仓库中的游戏教程信件。"""
        self.show_warehouse()
        if (self._warehouse_win is None
                or not self._warehouse_win.winfo_exists()):
            return
        self._select_warehouse_tab('信件')
        self._select_letter(TUTORIAL_LETTER_ID)

    def show_admin(self):
        if self._admin_win is not None and self._admin_win.winfo_exists():
            self._admin_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title('管理员')
        win.resizable(False, False)
        # 管理员也按「页面」处理，留在 Windows 任务栏中方便切回。
        self._show_in_taskbar(win)
        win.after(80, lambda w=win: self._show_in_taskbar(w))
        win.geometry(f'{dp(900)}x{dp(640)}')
        configure_theme(win)
        page_bg = THEME['bg']
        win.configure(bg=page_bg)
        self._admin_win = win
        self._admin_entries = {}
        self._admin_stats_labels = {}
        self._admin_settings_status = None

        tabbar = tk.Frame(win, bg=page_bg)
        tabbar.pack(side='top', fill='x', padx=18, pady=(14, 0))
        make_label(tabbar, '管理员', style='title', bg=page_bg).pack(
            side='left', anchor='center')
        self._admin_tab_buttons = {}
        for page_name in reversed(('统计数据', '数值设置', '存档')):
            btn = make_button(
                tabbar, page_name,
                lambda page=page_name: self._select_admin_tab(page),
                kind='tab', width=10)
            btn.pack(side='right', padx=3, anchor='center')
            self._admin_tab_buttons[page_name] = btn

        page_host = tk.Frame(win, bg=page_bg)
        page_host.pack(fill='both', expand=True, padx=18, pady=(10, 14))
        self._admin_pages = {}
        for page_name in ('统计数据', '数值设置', '存档'):
            self._admin_pages[page_name] = tk.Frame(page_host, bg=page_bg)

        stats_page = self._admin_pages['统计数据']
        stats_card = make_card(stats_page, bg=THEME['card'])
        stats_card.pack(fill='both', expand=True)
        stats_view = self._make_scrollable_frame(
            stats_card, THEME['card'], height=500, width=820)
        self._admin_hp_label = make_label(
            stats_view, '', bg=THEME['card'], fg=THEME['danger'],
            font=(FONT_FAMILY, 11, 'bold'))
        self._admin_hp_label.pack(anchor='w', padx=18, pady=(18, 10))
        sections = (
            ('基础统计', (
                ('level_exp', '等级与当前经验'),
                ('exp_earned', '累计获得经验'),
                ('strength', '力量点数'),
                ('wisdom', '智慧点数'),
                ('agility', '敏捷点数'),
                ('gold_earned', '总共赚了多少钱'),
                ('purchase_count', '总共买过多少次东西'),
                ('cat_click_count', '总共单击过多少次猫咪'),
                ('online_minutes', '猫咪总共在线时长'),
            )),
            ('状态记录', (
                ('gold_zero_seen', '是否经历过金币为0'),
                ('equipment_count', '当前拥有装备数量'),
                ('emotion_max', '历史最高情绪'),
                ('emotion_min', '历史最低情绪'),
                ('emotion_exact10', '是否出现过情绪10'),
                ('hp_min', '历史最低活力'),
                ('fashion_items', '养成道具购买进度'),
            )),
            ('探险记录', (
                ('adventure_early_fail_count', '提前失败结算次数'),
                ('adventure_count', '探险结算次数'),
                ('plain_adventure_count', '平原探险结算次数'),
                ('forest_adventure_count', '森林探险结算次数'),
                ('valley_adventure_count', '灰石谷探险结算次数'),
                ('plain_clear_count', '平原成功结算次数'),
                ('forest_clear_count', '森林成功结算次数'),
                ('valley_clear_count', '灰石谷成功结算次数'),
                ('adventure_minutes', '累计探险时长'),
            )),
            ('炼药记录', (
                ('alchemy_level', '炼药等级'),
                ('alchemy_craft_count', '炼药次数'),
            )),
            ('交易与喂食', (
                ('treasure_sold_count', '累计出售宝藏数量'),
                ('max_feed_amount', '单次最多喂食数量'),
                ('mushroom_damage_count', '蘑菇导致扣血次数'),
            )),
        )
        for section, definitions in sections:
            make_label(
                stats_view, section, bg=THEME['card'],
                font=(FONT_FAMILY, 10, 'bold')).pack(
                    anchor='w', padx=18, pady=(12, 3))
            for key, label in definitions:
                row = tk.Frame(stats_view, bg=THEME['card'])
                row.pack(fill='x', padx=18, pady=3)
                make_label(
                    row, label, width=24, anchor='w', bg=THEME['card'],
                    style='small').pack(side='left')
                value = make_label(
                    row, '0', anchor='e', bg=THEME['card'],
                    font=(FONT_FAMILY, 10, 'bold'))
                value.pack(side='right')
                self._admin_stats_labels[key] = value

        settings_page = self._admin_pages['数值设置']
        settings_card = make_card(settings_page, bg=THEME['card'])
        settings_card.pack(fill='both', expand=True)
        settings_view = tk.Frame(settings_card, bg=THEME['card'])
        settings_view.pack(fill='both', expand=True, padx=18, pady=14)
        configs = (('level', '等级', str(self.level)),
                   ('emotion', '情绪', str(self.emotion)),
                   ('gold', '金币', str(self.gold)),
                   ('luck', '幸运', str(self.luck)))
        for key, label, val in configs:
            row = tk.Frame(settings_view, bg=THEME['card'])
            row.pack(fill='x', pady=4)
            make_label(
                row, label, width=6, anchor='e',
                bg=THEME['card']).pack(side='left')
            ent = tk.Entry(
                row, width=10, justify='center', bg=THEME['card_alt'],
                fg=THEME['text'], relief='flat', highlightthickness=1,
                highlightbackground=THEME['border'])
            ent.insert(0, val)
            ent.pack(side='left', padx=8)
            ent.bind('<Return>', lambda e, k=key: self._apply_admin_value(k))
            make_button(
                row, '设置', lambda k=key: self._apply_admin_value(k),
                kind='secondary', width=6).pack(side='left')
            self._admin_entries[key] = ent

        make_label(
            settings_view, '快速解锁', bg=THEME['card'],
            font=(FONT_FAMILY, 10, 'bold')).pack(
                anchor='w', pady=(14, 5))
        unlock_bar = tk.Frame(settings_view, bg=THEME['card'])
        unlock_bar.pack(fill='x')
        make_button(
            unlock_bar, '一键解锁获得衣服', self._admin_unlock_all_clothes,
            kind='primary', width=18).pack(side='left', padx=(0, 6))
        make_button(
            unlock_bar, '一键获得所有书籍', self._admin_unlock_all_books,
            kind='primary', width=18).pack(side='left', padx=6)
        make_button(
            unlock_bar, '一键获得所有成就', self._admin_unlock_all_achievements,
            kind='primary', width=18).pack(side='left', padx=6)
        self._admin_settings_status = make_label(
            settings_view, '', bg=THEME['card'], fg=THEME['success'],
            style='small')
        self._admin_settings_status.pack(anchor='w', pady=(6, 10))

        make_label(
            settings_view, '模拟事件', bg=THEME['card'],
            font=(FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(6, 4))
        sim_bar = tk.Frame(settings_view, bg=THEME['card'])
        sim_bar.pack(anchor='w', pady=(2, 6))
        make_button(
            sim_bar, '模拟平原事件', lambda: self._simulate_region_events('1'),
            kind='secondary', width=13).pack(side='left', padx=3)
        make_button(
            sim_bar, '模拟森林事件', lambda: self._simulate_region_events('2'),
            kind='secondary', width=13).pack(side='left', padx=3)
        make_button(
            sim_bar, '模拟灰石谷事件', lambda: self._simulate_region_events('3'),
            kind='secondary', width=13).pack(side='left', padx=3)
        make_button(
            settings_view, '随机生成宝藏', self._admin_generate_treasure,
            kind='secondary', width=14).pack(anchor='w', pady=(6, 2))
        make_label(
            settings_view,
            '等级、情绪可调；活力上限由等级和三维属性自动计算。',
            bg=THEME['card'], fg=THEME['muted'], style='small').pack(
                anchor='w', pady=(10, 0))

        save_page = self._admin_pages['存档']
        save_card = make_card(save_page, bg=THEME['card'])
        save_card.pack(fill='both', expand=True)
        make_label(
            save_card, '选择存档', bg=THEME['card'], style='title').pack(
                anchor='w', padx=18, pady=(16, 6))
        make_label(
            save_card, '最多支持 3 个存档，切换后会自动保存当前存档。',
            bg=THEME['card'], fg=THEME['muted'], style='small').pack(
                anchor='w', padx=18, pady=(0, 10))
        self._admin_save_list = tk.Frame(save_card, bg=THEME['card'])
        self._admin_save_list.pack(fill='x', padx=18)
        make_button(
            save_card, '重开一局', self._reset_game, kind='primary',
            width=18).pack(anchor='w', padx=18, pady=(18, 8))
        make_label(
            save_card, '重开一局只影响当前正在使用的存档。',
            bg=THEME['card'], fg=THEME['danger'], style='small').pack(
                anchor='w', padx=18)

        self._refresh_admin_save_slots()
        self._refresh_admin_hp_label()
        self._refresh_admin_stats()
        win.protocol('WM_DELETE_WINDOW', self.close_admin)
        self._select_admin_tab('统计数据')

    def _apply_admin_value(self, key):
        """管理员：设置某项数值并保存"""
        ent = self._admin_entries.get(key)
        if ent is None:
            return
        try:
            value = int(ent.get().strip())
        except ValueError:
            return
        if key == 'level':
            value = max(1, min(999, value))
            self._set_admin_level(value)
        elif key == 'emotion':
            value = max(0, min(100, value))
            self.emotion = value
            self._refresh_emotion_bar()
        elif key == 'gold':
            value = max(0, value)
            self.gold = value
            self._refresh_warehouse()
            self._refresh_market()
        elif key == 'luck':
            self.luck = value  # 幸运可以是负数
            self._refresh_panel()
        else:
            return
        self._save_satiety()
        ent.delete(0, 'end')
        ent.insert(0, str(value))
        self._refresh_admin_hp_label()
        self._refresh_admin_stats()

    def _refresh_admin_stats(self):
        labels = getattr(self, '_admin_stats_labels', {})
        if not labels:
            return
        summary = StatsService.summary(self.game)
        equipment_count = sum(
            1 for item_id, count in self.inventory.items()
            if int(count or 0) > 0
            and (ITEMS.get(item_id) or {}).get('category') in
            ('头饰', '服装', '饰品'))
        purchased = summary.get('purchased_items', {})
        fashion_names = ['理发工具', '染发剂', '美瞳片']
        fashion_done = [name for item_id, name in zip(
            ('hairstyle_tool', 'hair_dye', 'lens'), fashion_names)
            if purchased.get(item_id, 0) > 0]
        try:
            exp_to_next = max(
                1, int(ProgressionService.xp_to_next(self.level)))
        except Exception:
            exp_to_next = 1
        values = {
            'level_exp': f'Lv.{self.level}（{self.exp} / {exp_to_next}）',
            'exp_earned': f"{summary['exp_earned']} 点",
            'strength': f'{self.strength} 点',
            'wisdom': f'{self.wisdom} 点',
            'agility': f'{self.agility} 点',
            'gold_earned': f"{summary['gold_earned']} G",
            'purchase_count': f"{summary['purchase_count']} 次",
            'cat_click_count': f"{summary['cat_click_count']} 次",
            'online_minutes': f"{summary['online_minutes']} 分钟",
            'gold_zero_seen': '是' if summary['gold_zero_seen'] else '否',
            'equipment_count': f'{equipment_count} 件',
            'emotion_max': str(summary['emotion_max']),
            'emotion_min': str(summary['emotion_min']),
            'emotion_exact10': '是' if summary['emotion_exact10'] else '否',
            'hp_min': str(summary['hp_min']),
            'fashion_items': '、'.join(fashion_done) if fashion_done else '未购买',
            'adventure_early_fail_count': f"{summary['adventure_early_fail_count']} 次",
            'adventure_count': f"{summary['adventure_count']} 次",
            'plain_adventure_count': f"{summary['plain_adventure_count']} 次",
            'forest_adventure_count': f"{summary['forest_adventure_count']} 次",
            'valley_adventure_count': f"{summary['valley_adventure_count']} 次",
            'plain_clear_count': f"{summary['plain_clear_count']} 次",
            'forest_clear_count': f"{summary['forest_clear_count']} 次",
            'valley_clear_count': f"{summary['valley_clear_count']} 次",
            'adventure_minutes': f"{summary['adventure_minutes']} 分钟",
            'alchemy_level': (
                f"Lv.{max(1, int(getattr(self.game, 'alchemy_level', 1) or 1))}"),
            'alchemy_craft_count': f"{summary['alchemy_craft_count']} 次",
            'treasure_sold_count': f"{summary['treasure_sold_count']} 件",
            'max_feed_amount': f"{summary['max_feed_amount']} 个",
            'mushroom_damage_count': f"{summary['mushroom_damage_count']} 次",
        }
        for key, label in labels.items():
            try:
                label.config(text=values.get(key, '0'))
            except Exception:
                pass

    def _refresh_admin_hp_label(self):
        label = getattr(self, '_admin_hp_label', None)
        if label is None:
            return
        try:
            if label.winfo_exists():
                summary = StatsService.summary(self.game)
                exp_to_next = max(
                    1, int(ProgressionService.xp_to_next(self.level)))
                label.config(text=(
                    f'等级：Lv.{self.level}　当前经验：{self.exp} / {exp_to_next}'
                    f'　累计获得经验：{summary["exp_earned"]}\n'
                    f'力量：{self.strength}　智慧：{self.wisdom}'
                    f'　敏捷：{self.agility}　活力：{self.hp} / {self.max_hp}'))
        except Exception:
            pass
        emotion_ent = getattr(self, '_admin_entries', {}).get('emotion')
        if emotion_ent is not None:
            try:
                emotion_ent.delete(0, 'end')
                emotion_ent.insert(0, str(self.emotion))
            except Exception:
                pass
        ent = getattr(self, '_admin_entries', {}).get('level')
        if ent is not None:
            try:
                ent.delete(0, 'end')
                ent.insert(0, str(self.level))
            except Exception:
                pass
        for key, value in (('gold', self.gold), ('luck', self.luck)):
            entry = getattr(self, '_admin_entries', {}).get(key)
            if entry is not None:
                try:
                    entry.delete(0, 'end')
                    entry.insert(0, str(value))
                except Exception:
                    pass

    def _set_admin_level(self, new_level):
        """调整等级并同步三项属性点数，保证活力上限对应等级。"""
        new_level = max(1, min(999, int(new_level)))
        old_max = max(1, self.max_hp)
        hp_ratio = max(0.0, min(1.0, self.hp / old_max))
        self.level = new_level
        expected_total = (STRENGTH_INITIAL + WISDOM_INITIAL
                          + AGILITY_INITIAL + (new_level - 1))
        attrs = ('strength', 'wisdom', 'agility')
        current_total = sum(getattr(self, attr) for attr in attrs)
        difference = expected_total - current_total
        if difference > 0:
            for _ in range(difference):
                attr = random.choice(attrs)
                setattr(self, attr, getattr(self, attr) + 1)
        elif difference < 0:
            remaining = -difference
            while remaining > 0:
                candidates = [attr for attr in attrs
                              if getattr(self, attr) > 10]
                if not candidates:
                    break
                attr = random.choice(candidates)
                setattr(self, attr, getattr(self, attr) - 1)
                remaining -= 1
        self.max_hp = self._calculate_max_hp()
        self.hp = max(0, min(self.max_hp, round(self.max_hp * hp_ratio)))
        self._refresh_panel()

    def _simulate_region_events(self, region_id):
        """管理员模拟正常探险结算，并生成一篇探索日志。"""
        from tkinter import simpledialog
        region_id = str(region_id)
        region = REGIONS.get(region_id, {})
        if not region.get('fallback', False):
            count = None
            while True:
                count = simpledialog.askinteger(
                    '模拟探险',
                    f'输入{region.get("name", "地区")}探险分钟数'
                    '（必须是 5 的倍数，范围 5~30）：',
                    parent=self._admin_win or self.root,
                    initialvalue=5, minvalue=5, maxvalue=30)
                if count is None:
                    return
                if count % 5 == 0:
                    break
                self._alert('模拟探险', '模拟时间必须是 5 的倍数。')
        else:
            count = simpledialog.askinteger(
                '模拟探险',
                '输入平原事件模拟次数：',
                parent=self._admin_win or self.root,
                initialvalue=5, minvalue=1, maxvalue=1000)
            if count is None:
                return
        self._adventure_region = region_id
        self._adventure_minutes = count
        self._adventure_treasure_quality_counts = {}
        self._adventure_bread_cost = 0
        self.adventuring = True
        self._finish_adventure(simulated=True)
        self._refresh_admin_hp_label()
        self._refresh_admin_stats()

    def _admin_generate_treasure(self):
        """管理员生成一件全品质随机宝藏并放入宝藏背包。"""
        treasure = self._generate_treasure(max_quality=6)
        if treasure is None:
            return
        self.treasures.append(treasure)
        self._unlock_treasure_bonuses()
        self._save_satiety()
        self._refresh_warehouse()
        self._refresh_market()

    def _reset_game(self):
        """重开一局：金币/等级/仓库等恢复到第一次打开游戏的状态"""
        try:
            import tkinter.messagebox as mb
            slot = int(getattr(self.save_service, 'slot_index', 0)) + 1
            if not mb.askyesno(
                    '重开一局',
                    f'确定要重置存档 {slot} 的全部进度吗？此操作不可撤销。'):
                return
        except Exception:
            pass
        self._flush_online_time()
        self.game = self.save_service.new_state()
        StatsService.ensure(self.game)
        AchievementService.sync_unlocks(self.game, self.achievement_catalog, ITEMS)
        self._online_session_started = time.monotonic()
        self.motion.reset('idle')
        self._treasure_uid = 0
        self.books_enabled = set()
        self.equipped_slots = {'头饰': [], '服装': None, '饰品': []}
        self._pending_slots = {'头饰': [], '服装': None, '饰品': []}
        self.equipped_clothes = 'normal'
        self._pending_clothes = 'normal'
        self.equip_settings = dict(DEFAULT_EQUIPMENT_SETTINGS)
        self._pending_equip_settings = dict(DEFAULT_EQUIPMENT_SETTINGS)
        self._collar_color_cache.clear()
        self._earring_color_cache.clear()
        self._hat_color_cache.clear()
        self.hair_style = 'hair_1'
        self._pending_hair_style = 'hair_1'
        self._pending_books_enabled = set()
        self._pending_item_uses = {}
        self._pending_color_changes = set()
        self._click_expression = None
        self._save_satiety()
        self._refresh_panel()
        self._refresh_warehouse()
        self._refresh_admin_stats()
        self._refresh_admin_save_slots()
        self.update_image()
        self.root.after(300, self._prompt_cat_name)

    def close_admin(self):
        """关闭管理员窗口"""
        if self._admin_win is not None:
            try:
                self._admin_win.destroy()
            except Exception:
                pass
            self._admin_win = None
        self._admin_hp_label = None

    def _refresh_panel(self):
        """刷新状态窗口：活力值条 + 力量/智慧/敏捷"""
        if self._panel is None or not self._panel.winfo_exists():
            return
        names = {'hp': '活力值'}
        for key, (lbl, bar) in self._panel_rows.items():
            value, cmax = self.hp, self.max_hp
            low = value < HP_LOW_AT
            lbl.config(text=f"{names[key]}：{value} / {cmax}")
            ratio = max(0.0, min(1.0, value / cmax))
            bar.delete('all')
            w = max(0, int(146 * ratio))
            color = '#e74c3c' if low else '#2ecc71'
            bar.create_rectangle(1, 1, 1 + w, 11, fill=color, outline='')
        if self._attr_text is not None:
            self._attr_text.config(
                text=(f'力量：{self.strength}　　智慧：{self.wisdom}'
                      f'　　敏捷：{self.agility}'))
        if self._skill_text is not None:
            self._skill_text.config(
                text=f'等级 {self.level} · 经验 {self.exp}'
                     f'/{self._xp_to_next()} · 技能点 {self.skill_points}')
        if hasattr(self, '_skill_btns'):
            state = 'normal' if self.skill_points > 0 else 'disabled'
            for btn in self._skill_btns.values():
                btn.config(state=state)
        self._refresh_admin_hp_label()


    def _schedule_mouse_check(self):
        if self.closing:
            return
        self._mouse_check_job = self.root.after(
            REACH_CHECK_MS, self._mouse_check)

    def _mouse_check(self):
        self._mouse_check_job = None
        if self.closing:
            return
        try:
            mx, my = self.root.winfo_pointerxy()
        except Exception:
            self._schedule_mouse_check()
            return
        size = int(ICON_SIZE * self.scale)
        cx = self.root.winfo_x() + size // 2
        cy = self.root.winfo_y() + size // 2
        dist = math.hypot(mx - cx, my - cy)
        moved = math.hypot(mx - self._last_mouse[0], my - self._last_mouse[1])
        if moved > 4:
            self._last_mouse = (mx, my)
            self._last_mouse_time = time.monotonic()
        stationary = ((time.monotonic() - self._last_mouse_time) * 1000.0
                      >= REACH_STATIONARY_MS)
        # 远离后重新武装，每次靠近只判定一次
        if dist > size * REACH_RANGE_RATIO * 1.6:
            self._mouse_armed = True
        busy = self.motion.current != 'idle'
        cooldown_ok = ((time.monotonic() - self._last_reach_time) * 1000.0
                       >= REACH_COOLDOWN_MS)
        can_pat = 'pat_guide' in self.books_enabled  # 勾选《乖，摸摸头》
        if (self._mouse_armed and stationary and not busy and cooldown_ok
                and can_pat
                and size * 0.6 < dist <= size * REACH_RANGE_RATIO):
            if random.random() < REACH_CHANCE:
                self._mouse_armed = False
                self._last_reach_time = time.monotonic()
                self._start_reach(mx, my)
        self._schedule_mouse_check()

    @staticmethod
    def _lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    def _set_cursor_pos(self, x, y):
        try:
            import ctypes
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = max(0, min(int(x), sw - 1))
            y = max(0, min(int(y), sh - 1))
            ctypes.windll.user32.SetCursorPos(x, y)
        except Exception:
            pass

    def _hand_screen_center(self, pos, size):
        """手在屏幕上的实际中心（考虑左右镜像），并限制在屏幕内"""
        hand = self.parts.get('hand')
        hw = hand.width if hand is not None else 0
        hh = hand.height if hand is not None else 0
        scale = size / 1024.0
        if getattr(self, '_reach_facing', self.facing_right):
            sx = self.root.winfo_x() + (1024 - pos[0] - hw / 2) * scale
        else:
            sx = self.root.winfo_x() + (pos[0] + hw / 2) * scale
        sy = self.root.winfo_y() + (pos[1] + hh / 2) * scale
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        return max(0, min(sx, sw - 1)), max(0, min(sy, sh - 1))

    def _start_reach(self, mx, my):
        """靠近鼠标的手贴住指针，再把指针带到猫头上并摆 comfy"""
        size = int(ICON_SIZE * self.scale)
        rx0, ry0 = self.root.winfo_x(), self.root.winfo_y()
        head_screen = (rx0 + size * 0.44, ry0 + size * 0.34)
        # 指针已经在头上：不用抓，直接结束
        if math.hypot(mx - head_screen[0], my - head_screen[1]) < size * 0.35:
            self._mouse_armed = False
            return
        if not self.motion.enter('reach'):
            return
        self.motion.set_phase('reach', 'reach')
        self._cancel_anim()
        if self.walking:
            self._cancel_walk()
            self.walking = False
        self._reach_state = 'reach'
        self._reach_facing = self.facing_right  # 动作期间保持朝向不变
        cx = rx0 + size // 2
        mouse_on_left = mx < cx
        if self._reach_facing:
            # 镜像后左右相反：画面左侧对应猫的右手
            self._reach_hand = 'right' if mouse_on_left else 'left'
        else:
            self._reach_hand = 'left' if mouse_on_left else 'right'
        base_l, base_r = self._hand_base_positions()
        self._reach_base = base_l if self._reach_hand == 'left' else base_r
        self._reach_hand_pos = self._reach_base
        self._reach_pointer_start = (mx, my)
        scale = 1024.0 / size
        hand = self.parts.get('hand')
        hw = hand.width if hand is not None else 0
        hh = hand.height if hand is not None else 0
        local_x = (mx - rx0) * scale
        local_y = (my - ry0) * scale
        if self._reach_facing:
            gx = 1024 - local_x - hw / 2
        else:
            gx = local_x - hw / 2
        gy = local_y - hh / 2
        gx = max(0.0, min(gx, 1024.0 - hw))
        gy = max(0.0, min(gy, 1024.0 - hh))
        self._reach_grab = (gx, gy)
        self._reach_head = (450 - hw / 2, 380 - hh / 2)
        mid_x = (self._reach_grab[0] + self._reach_head[0]) / 2
        mid_y = (self._reach_grab[1] + self._reach_head[1]) / 2
        if self._reach_facing:  # 镜像时弧线方向也要反过来
            self._reach_control = (mid_x - 140, mid_y - 120)
        else:
            self._reach_control = (mid_x + 140, mid_y - 120)
        frames = [('approach', t, 70) for t in (0.25, 0.5, 0.75, 1.0)]
        frames += [('pull', 0.0, 140)]  # 手先贴住指针停一下
        frames += [('pull', t, 50) for t in (0.16, 0.33, 0.5, 0.66, 0.83, 1.0)]
        frames += [('comfy', 0.0, 900)]
        frames += [('retract', t, 50) for t in (0.25, 0.5, 0.75, 1.0)]
        self._run_reach_frames(frames)

    def _run_reach_frames(self, frames):
        if self.closing:
            return
        if not frames:
            self._finish_reach()
            return
        phase, t, delay = frames[0]
        size = int(ICON_SIZE * self.scale)
        scale = 1024.0 / size
        self.motion.set_phase(phase, 'reach')
        if phase == 'approach':
            self._reach_hand_pos = self._lerp(self._reach_base,
                                              self._reach_grab, t)
            cur = self.root.winfo_pointerxy()
            if math.hypot(cur[0] - self._reach_pointer_start[0],
                          cur[1] - self._reach_pointer_start[1]) > 14:
                self._retract_reach()
                return
        elif phase == 'pull':
            p0, p1, p2 = (self._reach_grab, self._reach_control,
                          self._reach_head)
            pos = (
                (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
                (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1],
            )
            self._reach_hand_pos = pos
            sx, sy = self._hand_screen_center(pos, size)
            self._set_cursor_pos(sx, sy)
            cur = self.root.winfo_pointerxy()
            if math.hypot(cur[0] - sx, cur[1] - sy) > 22:
                self._retract_reach()
                return
        elif phase == 'comfy':
            self._set_comfy_active(True)
        else:  # retract
            self._reach_hand_pos = self._lerp(self._reach_head,
                                              self._reach_base, t)
        self.update_image()
        self._reach_job = self.animations.schedule('reach', 
            max(1, delay), lambda: self._run_reach_frames(frames[1:]))

    def _retract_reach(self):
        """取消抓取：当前手位直接缩回原处"""
        if self._reach_state is None:
            return
        if getattr(self, '_reach_job', None) is not None:
            try:
                self.animations.cancel('reach')
            except Exception:
                pass
            self._reach_job = None
        self._set_comfy_active(False)
        self._reach_head = self._reach_hand_pos
        frames = [('retract', t, 50) for t in (0.25, 0.5, 0.75, 1.0)]
        self._run_reach_frames(frames)

    def _finish_reach(self):
        self.motion.finish('reach', 'idle')
        self._reach_state = None
        self._set_comfy_active(False)
        self._reach_hand_pos = (0, 0)
        self.update_image()
        self._schedule_walk_attempt()

    def _cancel_reach(self):
        self.motion.finish('reach', 'idle')
        self._reach_state = None
        self._set_comfy_active(False)
        if getattr(self, '_reach_job', None) is not None:
            try:
                self.animations.cancel('reach')
            except Exception:
                pass
            self._reach_job = None

    def _schedule_idle_exp(self):
        """挂机奖励：每 1 分钟 +10 经验（探险中也生效）"""
        if self.closing:
            return
        if self._idle_exp_job is None:
            self._idle_exp_job = self.root.after(
                IDLE_EXP_MS, self._idle_exp_tick)

    def _idle_exp_tick(self):
        self._idle_exp_job = None
        if self.closing:
            return
        self._gain_exp(IDLE_EXP_PER_MIN)
        self._save_satiety()
        self._refresh_panel()
        if (self._warehouse_win is not None
                and self._warehouse_win.winfo_exists()):
            self._refresh_exp_bar()
        elif (self._workstation_win is not None
                and self._workstation_win.winfo_exists()):
            self._refresh_exp_bar()
        self._schedule_idle_exp()

    def _xp_to_next(self):
        """升级所需经验：平滑增长曲线。"""
        return ProgressionService.xp_to_next(self.level)

    def _gain_exp(self, amount):
        """获得经验并处理升级；升级时随机提升一项三维属性。"""
        StatsService.record_exp_earned(self.game, amount)
        gained = ProgressionService.gain_exp(self.game, amount, random)
        if gained:
            self._activate_strength_event_if_needed()
            try:
                self._check_achievements()
            except Exception:
                pass
        return gained

    def _gain_level(self):
        """提升一级，并随机提升力量、智慧或敏捷中的一项。"""
        gained = ProgressionService.gain_level(self.game, random)
        self._activate_strength_event_if_needed()
        return gained


    def _activate_strength_event_if_needed(self):
        """力量达到门槛时触发巴顿老爷的特殊事件。"""
        try:
            if int(getattr(self, 'strength', 0)) < 13:
                return False
            activated = SpecialEventService.activate(
                self.game, 'strength_13')
        except Exception:
            return False
        if not activated:
            return False
        self._save_satiety()
        try:
            self._refresh_warehouse()
        except Exception:
            pass
        return True

    def _spend_skill(self, attr):
        """用技能点强化 力量 或 智慧"""
        if self.skill_points <= 0:
            return
        self.skill_points -= 1
        if attr == 'strength':
            self.strength += 1
        elif attr == 'wisdom':
            self.wisdom += 1
        elif attr == 'agility':
            self.agility += 1
        else:
            self.skill_points += 1
            return
        self._sync_max_hp()
        self._save_satiety()
        self._refresh_panel()
        self._activate_strength_event_if_needed()

    def close_panel(self):
        """关闭状态窗口"""
        if self._panel_job is not None:
            try:
                self.root.after_cancel(self._panel_job)
            except Exception:
                pass
            self._panel_job = None
        if self._panel is not None:
            try:
                self._panel.destroy()
            except Exception:
                pass
            self._panel = None

    # ---------- 系统托盘 ----------
    def _setup_tray(self):
        """创建系统托盘图标；没有 pystray 时静默跳过"""
        try:
            import pystray
        except Exception:
            self._tray_icon = None
            return
        try:
            icon_img = self._full_for('normal').resize(
                (64, 64), PIL.Image.Resampling.LANCZOS)
            self._tray_icon = pystray.Icon(
                'cat_pet_tray', icon_img, title='猫咪',
                menu=pystray.Menu(
                    pystray.MenuItem(
                        '仓库', self._on_tray_open_warehouse,
                        enabled=lambda item: (not self.adventuring
                                              and not self.hospitalized)),
                    pystray.MenuItem(
                        '集市', self._on_tray_open_market,
                        enabled=lambda item: not self.adventuring),
                    pystray.MenuItem(
                        '探险', self._on_tray_adventure,
                        enabled=lambda item: (not self.adventuring
                                              and not self.hospitalized)),
                    pystray.MenuItem(
                        '取消探险', self._on_tray_cancel_adventure,
                        enabled=lambda item: self.adventuring),
                    pystray.MenuItem(
                        '寻找猫咪', self._on_tray_find_cat,
                        enabled=lambda item: (not self.adventuring
                                              and not self.hospitalized)),
                    pystray.MenuItem('退出', self._on_tray_quit)))
            threading.Thread(target=self._tray_icon.run,
                             daemon=True).start()
            self._update_tray_title()
            # 主线程轮询托盘发来的指令（Tk 不宜跨线程直接调用）
            self._tray_watch()
        except Exception:
            self._tray_icon = None

    def _tray_watch(self):
        if self.closing:
            return
        if self._tray_cmd == 'warehouse':
            self._tray_cmd = None
            if not self.adventuring and not self.hospitalized:
                self.show_warehouse()
        elif self._tray_cmd == 'market':
            self._tray_cmd = None
            if not self.adventuring:
                self.show_market()
        elif self._tray_cmd == 'adventure':
            self._tray_cmd = None
            if not self.adventuring and not self.hospitalized:
                self._show_tray_adventure_menu()
        elif self._tray_cmd == 'cancel_adventure':
            self._tray_cmd = None
            self._confirm_cancel_adventure()
        elif self._tray_cmd == 'find_cat':
            self._tray_cmd = None
            if not self.adventuring and not self.hospitalized:
                self._find_cat()
        if self._tray_quit:
            self._tray_quit = False
            self.close()
            return
        self.root.after(500, self._tray_watch)

    def _on_tray_open_warehouse(self, icon, item):
        """托盘菜单“仓库”：置指令，由主线程执行。"""
        if not self.adventuring and not self.hospitalized:
            self._tray_cmd = 'warehouse'

    def _on_tray_open_market(self, icon, item):
        """托盘菜单“集市”：探险中不可用。"""
        if not self.adventuring:
            self._tray_cmd = 'market'

    def _on_tray_adventure(self, icon, item):
        """托盘菜单“探险”：空闲状态可用。"""
        if not self.adventuring and not self.hospitalized:
            self._tray_cmd = 'adventure'

    def _on_tray_cancel_adventure(self, icon, item):
        """托盘菜单“取消探险”：转交主线程显示确认框。"""
        if self.adventuring:
            self._tray_cmd = 'cancel_adventure'

    def _confirm_cancel_adventure(self):
        """确认后直接取消本次探险，不进入结算流程。"""
        if not self.adventuring:
            return
        try:
            import tkinter.messagebox as mb
            confirmed = mb.askyesno(
                '取消探险', '中途返程将没有奖励哦!确定返回吗？')
        except Exception:
            return
        if confirmed:
            self._cancel_adventure()

    def _on_tray_find_cat(self, icon, item):
        """托盘菜单“寻找猫咪”：由主线程重新生成桌宠。"""
        if not self.adventuring and not self.hospitalized:
            self._tray_cmd = 'find_cat'

    def _find_cat(self, reset_scale=True):
        """把猫咪恢复到初始生成状态，并传送到屏幕顶部中央。"""
        if self.closing or self.adventuring or self.hospitalized:
            return
        self._cancel_anim()
        self._cancel_walk()
        self._cancel_jump()
        self._cancel_reach()
        self._cancel_fall()
        self._cancel_fling()
        self._cancel_climb()
        self._end_sway()
        self.dragging = False
        self.moved = False
        self.swaying = False
        self.walking = False
        self.falling = False
        self.flinging = False
        self.climbing = False
        self.pose = 'normal'
        if reset_scale:
            self.scale = 1.0
        self._set_comfy_active(False)
        self._falling_hands = False
        self._hand_lift = 0.0
        self._on_taskbar = False
        self.facing_right = False
        try:
            self.label.config(cursor='arrow')
        except Exception:
            pass
        size = int(ICON_SIZE * self.scale)
        x = max(0, (self.root.winfo_screenwidth() - size) // 2)
        y = 0
        self.root.deiconify()
        self.root.geometry(f'{size}x{size}+{int(x)}+{int(y)}')
        self.root.attributes('-topmost', True)
        self.root.lift()
        self.update_image()
        self.start_animations()
        self._schedule_walk_attempt()
        self._start_fall_check()
        self._update_tray_title()

    def _show_tray_adventure_menu(self):
        """旧接口保留：改为打开探险页面。"""
        self.show_adventure()

    def _on_tray_quit(self, icon, item):
        """托盘菜单“退出”：置标志，由主线程执行关闭"""
        self._tray_quit = True

    def _set_tray_title(self, text):
        """更新托盘图标悬停提示文字"""
        if self._tray_icon is not None:
            try:
                self._tray_icon.title = text
            except Exception:
                pass



    def _update_tray_title(self):
        """按状态刷新托盘提示。"""
        if self.hospitalized:
            text = '猫咪（在住院）'
        elif self.adventuring:
            text = ('猫咪（在探险）\n'
                    f'剩余探索时间：约{self._adventure_remaining_minutes()}分钟')
        else:
            text = '猫咪（在闲逛~）'
        self._set_tray_title(text)

    def _stop_tray(self):
        if self._tray_icon is not None:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None

    # ---------- 窗口 / 任务栏图标 ----------

    def _load_window_icons(self):
        """把素材 `ui/cat.png` 缩成几档 PhotoImage，供窗口图标使用。

        返回的列表必须由调用方长期持有，否则被 GC 回收后图标会掉回默认。
        注意：Tk 的 `wm iconphoto` 一次只喂**一张**图——混传多张不同尺寸
        会抛异常，异常被吞掉就会出现「设了图标却没生效」的假象，
        所以多尺寸这件事交给 `ui/cat.ico`（见 _set_win32_icon）。
        """
        path = _asset_path('cat.png', 'ui')
        if not os.path.exists(path):
            return []
        try:
            from PIL import Image, ImageTk
            source = Image.open(path).convert('RGBA')
        except Exception:
            return []
        icons = []
        for size in (256, 128, 64, 32, 16):
            try:
                frame = source.resize(
                    (size, size), Image.Resampling.LANCZOS)
                icons.append(ImageTk.PhotoImage(frame))
            except Exception:
                continue
        return icons

    def _set_win32_icon(self, win):
        """再用 Win32 的 WM_SETICON 直接给窗口挂 HICON（图标设置的双保险）。

        Tk 的 `wm iconphoto` 在某些情况下会静默失效（页面窗口切过
        `-toolwindow` 样式、或喂了多张不同尺寸的图），所以这里再从
        `ui/cat.ico` 取图标直接发给窗口句柄，任务栏与标题栏都能稳。
        """
        icon_file = _asset_path('cat.ico', 'ui')
        if not os.path.exists(icon_file):
            return
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return
        try:
            user32 = ctypes.windll.user32
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            LR_DEFAULTSIZE = 0x0040
            WM_SETICON = 0x0080
            ICON_SMALL, ICON_BIG = 0, 1
            user32.GetParent.restype = wintypes.HWND
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.LoadImageW.restype = ctypes.c_void_p
            user32.LoadImageW.argtypes = [
                wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                ctypes.c_int, ctypes.c_int, wintypes.UINT]
            user32.SendMessageW.restype = ctypes.c_void_p
            user32.SendMessageW.argtypes = [
                wintypes.HWND, wintypes.UINT,
                ctypes.c_void_p, ctypes.c_void_p]
            hwnd = user32.GetParent(int(win.winfo_id()))
            if not hwnd:
                hwnd = int(win.winfo_id())
            if not hwnd:
                return
            small_side = int(user32.GetSystemMetrics(49)) or 16
            big = user32.LoadImageW(
                None, icon_file, IMAGE_ICON, 0, 0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE)
            small = user32.LoadImageW(
                None, icon_file, IMAGE_ICON, small_side, small_side,
                LR_LOADFROMFILE)
            if big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
            if small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
        except Exception:
            pass

    def _apply_default_window_icon(self):
        """给主窗口挂图标，并登记为「之后新建窗口的默认图标」。"""
        self._apply_window_icon(self.root)

    def _apply_window_icon(self, win):
        """给单个窗口设置图标：Tk 层 + Win32 层双保险。"""
        icons = getattr(self, '_window_icons', None)
        if icons:
            try:
                win.iconphoto(True, icons[0])
            except Exception:
                pass
        self._set_win32_icon(win)

    def _hide_from_taskbar(self, win):
        """用 Win32 扩展样式把窗口从任务栏隐藏（去掉 APPWINDOW，加 TOOLWINDOW）"""
        # 子弹窗不进任务栏，但标题栏小图标仍统一成猫。
        self._apply_window_icon(win)
        try:
            import ctypes
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            # Tk 顶层窗口的外层句柄在其父级
            hwnd = user32.GetParent(int(win.winfo_id()))
            if not hwnd:
                hwnd = int(win.winfo_id())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            # 刷新窗口样式
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                0x0001 | 0x0002 | 0x0004 | 0x0020 | 0x0040)
        except Exception:
            pass

    def _show_in_taskbar(self, win):
        """让窗口出现在 Windows 任务栏（与 _hide_from_taskbar 相反）。

        仓库 / 工作站 / 集市 / 探险这类「页面」用它在任务栏留一个按钮，
        方便用任务栏或 Alt+Tab 找回来；颜色面板、一键出售、信件大图这类
        子弹窗仍然走 _hide_from_taskbar。
        """
        try:
            win.attributes('-toolwindow', False)
        except Exception:
            pass
        self._apply_window_icon(win)
        try:
            import ctypes
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            hwnd = user32.GetParent(int(win.winfo_id()))
            if not hwnd:
                hwnd = int(win.winfo_id())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                0x0001 | 0x0002 | 0x0004 | 0x0020 | 0x0040)
        except Exception:
            pass

    # ---------- 集市 / 物品 / 喂食消耗 ----------























    # ---------- 探险 / 仓库 ----------



















































    def _emotion_level(self):
        if self.emotion >= 80:
            return '狂欢'
        if self.emotion >= 60:
            return '开心'
        if self.emotion >= 40:
            return '慵懒'
        if self.emotion >= 20:
            return '悲伤'
        return '绝望'




























    #     # ---------- 右键菜单 ----------
    def show_menu(self, event):
        """显示右键菜单"""
        # 悬浮条/对话框若开着先关掉，避免重叠
        self.close_scale_window()
        self._cancel_emotion_face()
        menu = tk.Menu(self.root, tearoff=0, bg='#ffffff', fg='#000000')
        cat_name = getattr(self, 'cat_name', None) or '猫猫'
        current = self._current_achievement()
        title = (current or {}).get('name') or '暂无称号'
        title_color = str((current or {}).get('text_color') or '#000000').strip()
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', title_color):
            title_color = '#000000'
        menu.add_command(label=f'名字：{cat_name}', foreground='#000000', activeforeground='#000000',
                         command=lambda: None)
        menu.add_command(label=f'等级：{self.level}', foreground='#000000', activeforeground='#000000',
                         command=lambda: None)
        menu.add_command(label=f'称号：{title}', foreground=title_color,
                         activeforeground=title_color, command=lambda: None)
        menu.add_separator()
        menu.add_command(label='仓库', command=self.show_warehouse)
        menu.add_command(label='集市', command=self.show_market)
        menu.add_command(label='探险', command=self.show_adventure)
        menu.add_command(label='工作站', command=self.show_workstation)
        menu.add_command(label='管理员', command=self.show_admin)
        menu.add_separator()
        # 比例：点击后弹出无边框悬浮滑块条，拖动滑块即可改变大小；
        # 没有关闭按钮，点击悬浮条以外的任意位置即可关闭
        menu.add_command(label='设置', command=self.open_settings_window)
        menu.add_separator()
        menu.add_command(label='关闭', command=self.close)
        menu.post(event.x_root, event.y_root)

    # ---------- 无边框悬浮滑块条 ----------
    def open_settings_window(self):
        """打开设置面板：调整猫咪比例、整体音效和动画帧率。"""
        if self.scale_win is not None and self.scale_win.winfo_exists():
            self.scale_win.lift()
            self.scale_win.focus_force()
            return

        page_bg = THEME['bg']
        win = tk.Toplevel(self.root)
        win.title('设置')
        win.resizable(False, False)
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        win.after(80, lambda w=win: self._hide_from_taskbar(w))
        configure_theme(win)
        win.configure(bg=page_bg)

        make_label(win, '设置', style='title', bg=page_bg).pack(
            anchor='w', padx=18, pady=(14, 8))
        make_label(
            win, '调整猫咪比例、整体音效与动画帧率', bg=page_bg,
            fg=THEME['muted'], style='small').pack(
                anchor='w', padx=18, pady=(0, 8))

        scale_row = tk.Frame(win, bg=page_bg)
        scale_row.pack(fill='x', padx=18, pady=(4, 10))
        make_label(
            scale_row, '猫咪比例', bg=page_bg, width=8,
            anchor='w').pack(side='left')
        self.scale_percent = tk.IntVar(value=int(round(self.scale * 100)))
        self.scale_value_label = make_label(
            scale_row, f'{self.scale_percent.get()}%', bg=page_bg,
            width=4, anchor='e')
        self.scale_value_label.pack(side='right', padx=(8, 0))
        self.scale_slider = tk.Scale(
            scale_row, from_=int(SCALE_MIN * 100), to=int(SCALE_MAX * 100),
            orient='horizontal', variable=self.scale_percent,
            showvalue=False, length=260, command=self.on_scale_slider,
            bg=page_bg, fg=THEME['text'], troughcolor=THEME['card_alt'],
            highlightthickness=0, bd=0, activebackground=THEME['accent'])
        self.scale_slider.pack(side='right', fill='x', expand=True)
        self.scale_slider.bind(
            '<ButtonRelease-1>', lambda e: self._save_settings())

        sound_row = tk.Frame(win, bg=page_bg)
        sound_row.pack(fill='x', padx=18, pady=(4, 10))
        make_label(
            sound_row, '整体音效', bg=page_bg, width=8,
            anchor='w').pack(side='left')
        self.sound_percent = tk.IntVar(
            value=max(0, min(100, int(getattr(self, 'sound_volume', 100)))))
        self.sound_value_label = make_label(
            sound_row, f'{self.sound_percent.get()}%', bg=page_bg,
            width=4, anchor='e')
        self.sound_value_label.pack(side='right', padx=(8, 0))
        self.sound_slider = tk.Scale(
            sound_row, from_=0, to=100, orient='horizontal',
            variable=self.sound_percent, showvalue=False, length=260,
            command=self.on_sound_slider, bg=page_bg, fg=THEME['text'],
            troughcolor=THEME['card_alt'], highlightthickness=0, bd=0,
            activebackground=THEME['accent'])
        self.sound_slider.pack(side='right', fill='x', expand=True)
        self.sound_slider.bind(
            '<ButtonRelease-1>', lambda e: self._save_settings())

        fps_row = tk.Frame(win, bg=page_bg)
        fps_row.pack(fill='x', padx=18, pady=(4, 10))
        make_label(
            fps_row, '动画帧率', bg=page_bg, width=8,
            anchor='w').pack(side='left')
        fps_box = tk.Frame(fps_row, bg=page_bg)
        fps_box.pack(side='right')
        self.frame_rate_var = tk.IntVar(
            value=60 if int(getattr(self, 'frame_rate', 30)) >= 60 else 30)
        for _fps, _text in ((30, '30 帧'), (60, '60 帧')):
            tk.Radiobutton(
                fps_box, text=_text, value=_fps,
                variable=self.frame_rate_var,
                command=self.on_frame_rate_change, bg=page_bg,
                fg=THEME['text'], selectcolor=THEME['card_alt'],
                activebackground=page_bg, activeforeground=THEME['text'],
                highlightthickness=0, bd=0).pack(side='left', padx=(0, 6))

        make_button(
            win, '关闭', self.close_scale_window, kind='primary',
            width=10).pack(anchor='e', padx=18, pady=(2, 14))
        win.bind('<Escape>', lambda e: self.close_scale_window())
        win.protocol('WM_DELETE_WINDOW', self.close_scale_window)
        self.scale_win = win

        win.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - win.winfo_reqwidth() // 2
        y = self.root.winfo_y() - win.winfo_reqheight() - 10
        if y < 0:
            y = self.root.winfo_y() + self.root.winfo_height() + 10
        x = max(0, min(x, win.winfo_screenwidth() - win.winfo_reqwidth()))
        y = max(0, min(y, win.winfo_screenheight() - win.winfo_reqheight()))
        win.geometry(f'+{int(x)}+{int(y)}')
        win.lift()
        win.focus_force()
        win.after(80, self._ensure_scale_focus)


    def open_scale_window(self):
        """兼容旧调用。"""
        self.open_settings_window()

    def _ensure_scale_focus(self):
        """确保悬浮条获得焦点（点击别处时才能触发 FocusOut 自动关闭）"""
        if self.scale_win is not None and self.scale_win.winfo_exists():
            self.scale_win.focus_force()

    def _on_global_click(self, event):
        """点击悬浮条以外的位置时关闭悬浮条（仓库不再自动关闭）"""
        if self.scale_win is None or not self.scale_win.winfo_exists():
            return
        if self._widget_is_inside(event.widget, self.scale_win):
            return
        self.close_scale_window()

    @staticmethod
    def _widget_is_inside(widget, top):
        """判断 widget（或其父级）是否属于 top 这个顶层窗口"""
        while widget is not None:
            if widget is top:
                return True
            try:
                widget = widget.master
            except Exception:
                return False
        return False

    def _bar_drag_start(self, event):
        """开始拖动悬浮条（在滑块上按下时不触发）"""
        if self.scale_win is None:
            return
        # 点按在滑块上时，不启动悬浮条拖动，避免冲突
        if event.widget is self.scale_slider:
            self._bar_drag_active = False
            return
        self._bar_drag_active = True
        self._bar_drag_offset_x = event.x_root - self.scale_win.winfo_x()
        self._bar_drag_offset_y = event.y_root - self.scale_win.winfo_y()

    def _bar_drag_motion(self, event):
        """拖动悬浮条移动"""
        if self.scale_win is None or not self._bar_drag_active:
            return
        x = event.x_root - self._bar_drag_offset_x
        y = event.y_root - self._bar_drag_offset_y
        self.scale_win.geometry(f'+{x}+{y}')

    def _bar_drag_stop(self, event):
        """结束拖动悬浮条"""
        self._bar_drag_active = False

    def on_scale_slider(self, value):
        """拖动滑块时实时改变宠物大小。"""
        percent = int(float(value))
        if self.scale_value_label is not None:
            self.scale_value_label.config(text=f'{percent}%')
        self.set_scale(percent / 100.0)
        if hasattr(self, 'game'):
            self.game.cat_scale = float(self.scale)

    def on_sound_slider(self, value):
        """调整整体音效音量，0 为静音，100 为原始音量。"""
        percent = max(0, min(100, int(float(value))))
        self.sound_volume = percent
        if getattr(self, 'sound_value_label', None) is not None:
            self.sound_value_label.config(text=f'{percent}%')
        if hasattr(self, 'game'):
            self.game.sound_volume = percent
        self._click_sound_cache_key = None
        self._click_sound_paths = None

    def _save_settings(self):
        """保存设置面板中的比例、音量和帧率。"""
        if hasattr(self, 'game'):
            self.game.cat_scale = float(self.scale)
            self.game.sound_volume = int(getattr(self, 'sound_volume', 100))
            self.game.frame_rate = int(getattr(self, 'frame_rate', 30))
            try:
                self._save_satiety()
            except Exception:
                pass
            # 比例变了显示图缓存就全失效，这里补一次预热
            self.root.after(60, self._warm_render_cache)

    def on_frame_rate_change(self):
        """切换动画帧率（30 / 60 帧），立即生效并存档。"""
        try:
            fps = int(self.frame_rate_var.get())
        except (TypeError, ValueError):
            fps = 30
        self.frame_rate = set_anim_fps(fps)
        if hasattr(self, 'game'):
            self.game.frame_rate = self.frame_rate
        self._save_settings()

    def close_scale_window(self):
        """关闭设置面板并保存设置。"""
        if self.scale_win is not None and self.scale_win.winfo_exists():
            self._save_settings()
            self.scale_win.destroy()
        self.scale_win = None
        self.scale_slider = None
        self.sound_slider = None
        self.sound_value_label = None
        self._bar_drag_active = False

    # ---------- 关闭 ----------
    def close(self):
        """关闭程序"""
        if not self.close_warehouse():
            return
        self.close_scale_window()
        self.closing = True
        self.motion.enter('closing', force=True)
        self.animations.cancel_all()
        self._stop_tray()
        self._close_palette()
        self._cancel_anim()
        self._cancel_walk()
        self._cancel_jump()
        self._cancel_reach()
        self._cancel_fall()
        self._cancel_fling()
        self._cancel_climb()
        self._cancel_emotion_face()
        if self._emotion_job is not None:
            try:
                self.root.after_cancel(self._emotion_job)
            except Exception:
                pass
            self._emotion_job = None
        if self._hospital_job is not None:
            try:
                self.root.after_cancel(self._hospital_job)
            except Exception:
                pass
            self._hospital_job = None
        if self._mouse_check_job is not None:
            try:
                self.root.after_cancel(self._mouse_check_job)
            except Exception:
                pass
            self._mouse_check_job = None
        if self._idle_exp_job is not None:
            try:
                self.root.after_cancel(self._idle_exp_job)
            except Exception:
                pass
            self._idle_exp_job = None
        self.close_panel()
        self.close_admin()
        self.close_market()
        self.close_adventure()
        self.close_workstation()
        self._close_log()
        self.adventuring = False
        self._adventure_departing = False
        self._adventure_end_time = None
        for attr in ('_adventure_job', '_adventure_depart_job',
                     '_adventure_title_job'):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._online_job is not None:
            try:
                self.root.after_cancel(self._online_job)
            except Exception:
                pass
            self._online_job = None
        self._flush_online_time()
        self._save_satiety()
        if self._regen_job is not None:
            try:
                self.root.after_cancel(self._regen_job)
            except Exception:
                pass
            self._regen_job = None
        self.root.destroy()

    def run(self):
        """运行程序"""
        # 启动后台预热常用姿势图，避免第一次拖拽糊住主线程上百毫秒
        self.root.after(300, self._warm_render_cache)
        # 待机呼吸感：静止时的极小幅纵向起伏，独立循环，忙时自动让路
        self.root.after(500, self._start_breath)
        self.root.mainloop()

    def _warm_render_cache(self):
        """预热常用姿势的显示图（启动后、改比例后调用）。失败不影响运行。

        单张显示图约 95ms，全部一次预热完会让窗口冻结近 1 秒。所以分两段：
        先同步预热「拖拽 / 站立 / 落地」这条交互主链路，走路等闲时姿势
        1.5 秒后再补 —— 启动停顿短，闲时那一下也不影响手感。

        另外，空中（甩飞/下落）时 flinging/_falling_hands 会参与合成，
        显示图的状态键与地面状态不同，这时候预热等于白热：等落地再热。
        """
        try:
            if (getattr(self, 'flinging', False)
                    or getattr(self, 'falling', False)):
                self.root.after(500, self._warm_render_cache)
                return
            self.warm_render_cache()
            self.root.after(1500, self._warm_idle_poses)
        except Exception:
            pass

    def _warm_idle_poses(self):
        """闲时姿势（走路等）的延迟预热。"""
        try:
            if (getattr(self, 'flinging', False)
                    or getattr(self, 'falling', False)):
                self.root.after(500, self._warm_idle_poses)
                return
            self.warm_render_cache(poses=(('walk', True),))
        except Exception:
            pass


# 旧字段代理：实际数据只保存在 DesktopPet.game 中。
def _bind_state_proxy(name, attr=None):
    attr = attr or name

    def getter(self):
        return getattr(self.game, attr)

    def setter(self, value):
        setattr(self.game, attr, value)

    return property(getter, setter)


for _proxy_name, _proxy_attr in (
    ('hp', 'hp'), ('max_hp', 'max_hp'), ('level', 'level'),
    ('exp', 'exp'), ('strength', 'strength'), ('wisdom', 'wisdom'),
    ('agility', 'agility'), ('luck', 'luck'), ('emotion', 'emotion'),
    ('skill_points', 'skill_points'), ('gold', 'gold'),
    ('inventory', 'inventory'), ('treasures', 'treasures'),
    ('logs', 'logs'), ('equipped_slots', 'equipped_slots'),
    ('equip_settings', 'equipment_settings'),
    ('equipped_clothes', 'equipped_clothes'),
    ('books_enabled', 'books_enabled'), ('hair_style', 'hair_style'),
    ('hair_color', 'hair_color'),
    ('normal_clothes_color', 'normal_clothes_color'),
    ('eye_color', 'eye_color'), ('cat_name', 'cat_name'),
    ('stats', 'stats'),
    ('achievements', 'achievements'),
    ('backgrounds', 'backgrounds'),
    ('selected_background', 'selected_background'),
    ('selected_achievement', 'selected_achievement'),
):
    setattr(DesktopPet, _proxy_name, _bind_state_proxy(
        _proxy_name, _proxy_attr))


# ---------- 单实例保护 ----------
_SINGLE_INSTANCE_HANDLE = None


def _acquire_single_instance():
    """确保程序只运行一个实例（Windows 命名互斥体）；第二个实例返回 False"""
    global _SINGLE_INSTANCE_HANDLE
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p,
                                          ctypes.c_bool,
                                          ctypes.c_wchar_p]
        handle = kernel32.CreateMutexW(
            None, False, 'CatAdventage_DesktopPet_SingleInstance')
        if not handle:
            return True  # 创建失败时不阻止运行
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            try:
                import tkinter as tk
                import tkinter.messagebox as mb
                r = tk.Tk()
                r.withdraw()
                mb.showinfo('猫咪桌宠', '程序已经在运行啦~')
                r.destroy()
            except Exception:
                pass
            return False
        _SINGLE_INSTANCE_HANDLE = handle  # 进程存活期间一直持有
        return True
    except Exception:
        return True


if __name__ == '__main__':
    if not _acquire_single_instance():
        raise SystemExit(0)
    pet = DesktopPet()
    pet.run()
