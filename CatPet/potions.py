# -*- coding: utf-8 -*-
"""炼药：配方、药水前缀与使用结算。

炼药页右侧的配方负责「合成」，合成出的消耗品会随机带一个前缀；
前缀共 5 档（残次品 / 劣质品 / 普通品 / 精良品 / 珍品），每档 4 个前缀，
决定使用时的情绪、活力与持续时间修正。档位权重先都等于 20%，方便日后调整。

本模块不 import 项目内其它模块，方便被 desktop_pet 导入后经
install_runtime_globals 注入到工作站/仓库模块。
"""
import random

# 药水前缀档位。
# weight         出现概率（先都等于 0.2）。
# prefixes       该档的 4 个前缀（合成时在档内等概率抽一个）。
# emotion        使用后的情绪变化（正为增加）。
# hp_ratio       活力损失范围（占活力上限的比例，使用随机取值；None 为不减活力）。
# duration_scale 有持续时间的药水按此倍率随机缩放持续时间。
# effect_scale   没有持续时间的药水改按此倍率随机缩放效果。
# quality        该档产物的物品品质。
POTION_TIERS = (
    {
        'key': 'flawed', 'label': '残次品', 'weight': 0.20, 'quality': '粗劣',
        'prefixes': ('败坏的', '浑浊的', '变质的', '残淬的'),
        'emotion': -10, 'hp_ratio': (0.05, 0.10),
        'duration_scale': (0.50, 0.80), 'effect_scale': (0.50, 0.80),
    },
    {
        'key': 'poor', 'label': '劣质品', 'weight': 0.20, 'quality': '普通',
        'prefixes': ('粗制的', '稀释的', '不纯的', '劣调的'),
        'emotion': -5, 'hp_ratio': None,
        'duration_scale': (0.80, 0.90), 'effect_scale': (0.80, 0.90),
    },
    {
        'key': 'common', 'label': '普通品', 'weight': 0.20, 'quality': '普通',
        'prefixes': ('寻常的', '调制的', '稳定的', '标准的'),
        'emotion': 0, 'hp_ratio': None,
        'duration_scale': (1.00, 1.00), 'effect_scale': (1.00, 1.00),
    },
    {
        'key': 'fine', 'label': '精良品', 'weight': 0.20, 'quality': '少见',
        'prefixes': ('精制的', '纯净的', '凝练的', '饱满的'),
        'emotion': 2, 'hp_ratio': None,
        'duration_scale': (1.10, 1.20), 'effect_scale': (1.10, 1.20),
    },
    {
        'key': 'exquisite', 'label': '珍品', 'weight': 0.20, 'quality': '稀有',
        'prefixes': ('辉耀的', '精粹的', '圣铸的', '永凝的'),
        'emotion': 5, 'hp_ratio': None,
        'duration_scale': (1.20, 1.50), 'effect_scale': (1.20, 1.50),
    },
)

# 药水蒙版：贴在猫身上的染色图层，用来表现中毒等持续状态。
# color    RGB 目标色；strength 染色强度（0~1）。
POTION_MASKS = {
    'poison_green': {
        'color': (144, 238, 144),   # 淡绿色
        'strength': 0.45,
        'label': '中毒',
    },
}

# 炼药配方。materials 为 (物品键, 数量)；unlock_level 为解锁所需炼金等级；
# effect 描述使用效果（mask 为蒙版键，duration_ms 为持续时间）。
# 注意：配方界面显示的「描述」取自物品簿里那条物品的用途（ITEMS[item]['desc']），
# desc 字段只是物品簿里查不到这条物品时的兜底文案。
ALCHEMY_RECIPES = (
    {
        'key': 'green_potion',
        'item': 'green_potion',
        'name': '淡绿色药水',
        'unlock_level': 2,
        'materials': (('green_herb', 1),),
        'effect': {'mask': 'poison_green', 'duration_ms': 10 * 60 * 1000},
        # 配方界面上刻意不写真实效果（喝下去才知道），留个含糊的提示。
        'effect_text': '未知效果，大概会持续十分钟？',
        'desc': '',
    },
)

# 变体物品键的分隔符：基础键 + '__' + 档位键 + 序号。
VARIANT_SEPARATOR = '__'


def potion_tier(key):
    """按档位键取档位定义，找不到返回 None。"""
    if not key:
        return None
    return next((tier for tier in POTION_TIERS
                 if tier['key'] == str(key)), None)


def potion_tier_by_prefix(prefix):
    """按前缀文字反查档位定义，找不到返回 None。"""
    if not prefix:
        return None
    for tier in POTION_TIERS:
        if prefix in tier['prefixes']:
            return tier
    return None


def rolled_tier_weights(tiers=None):
    """档位权重表（归一化后返回 (档位, 权重) 列表）。"""
    tiers = tiers or POTION_TIERS
    total = sum(max(0.0, float(tier.get('weight', 0) or 0)) for tier in tiers)
    if total <= 0:
        weight = 1.0 / len(tiers) if tiers else 0.0
        return [(tier, weight) for tier in tiers]
    return [(tier, max(0.0, float(tier.get('weight', 0) or 0)) / total)
            for tier in tiers]


def roll_potion_prefix(rng=None):
    """随机一个药水前缀：先按权重抽档位，再在档内等概率抽前缀。

    返回 (档位定义, 该档内的序号, 前缀文字)。
    """
    rng = rng or random
    table = rolled_tier_weights()
    if not table:
        return None, 0, ''
    roll = rng.random()
    accumulated = 0.0
    chosen = table[-1][0]
    for tier, weight in table:
        accumulated += weight
        if roll <= accumulated:
            chosen = tier
            break
    prefixes = tuple(chosen.get('prefixes') or ())
    if not prefixes:
        return chosen, 0, ''
    index = rng.randrange(len(prefixes))
    return chosen, index + 1, prefixes[index]


def variant_key(base_key, tier_key, index):
    """前缀变体的物品键，例如 green_potion__flawed1。"""
    return f'{base_key}{VARIANT_SEPARATOR}{tier_key}{int(index)}'


def variant_items(recipe, desc=None):
    """某个配方对应的全部前缀变体物品定义。

    desc 为已确定的描述（一般取基础物品在物品簿里的用途）；
    传 None 时回落到配方自带的兜底文案。
    """
    base_key = recipe['item']
    effect = dict(recipe.get('effect') or {})
    if desc is None:
        desc = recipe.get('desc', '')
    result = {}
    for tier in POTION_TIERS:
        prefixes = tuple(tier.get('prefixes') or ())
        for index, prefix in enumerate(prefixes, start=1):
            key = variant_key(base_key, tier['key'], index)
            result[key] = {
                'name': f"{prefix}{recipe['name']}",
                'kind': '消耗品',
                'category': '物品',
                'quality': tier.get('quality', '普通'),
                'desc': desc,
                'regions': [],
                'can_buy': False, 'buy_price': None, 'price': None,
                'can_sell': False, 'sell_price': None, 'market_page': '杂货铺',
                'use_effect': dict(effect, tier=tier['key']),
                'potion': {
                    'base': base_key, 'tier': tier['key'],
                    'prefix': prefix, 'label': tier.get('label', ''),
                },
            }
    return result


def register_potion_items(items):
    """把配方的基础药水与全部前缀变体补进物品表。

    基础药水本身不入包（合成只会产出带前缀的变体），这里只补上
    use_effect / recipe 字段，方便仓库与详情栏读取。

    变体的描述跟随基础物品在物品簿里的「用途」，改表即改文案。
    """
    registered = {}
    for recipe in ALCHEMY_RECIPES:
        base_key = recipe['item']
        base = items.get(base_key)
        if base is None:
            # 物品簿里没有这条基础物品：仍然注册变体，免得配方点不动。
            base = {}
        else:
            base = dict(base)
        base.setdefault('name', recipe['name'])
        base.setdefault('kind', '消耗品')
        base.setdefault('category', '物品')
        base['use_effect'] = dict(recipe.get('effect') or {})
        base['recipe'] = recipe['key']
        base['potion_base'] = True
        items[base_key] = base
        for key, info in variant_items(
                recipe, desc=base.get('desc') or recipe.get('desc', '')).items():
            existing = items.get(key) or {}
            merged = dict(existing)
            merged.update(info)
            items[key] = merged
            registered[key] = info['potion']
    return registered


def roll_potion_effect(info, max_hp, rng=None):
    """结算「使用一个药水」的效果，返回各项变化的明细。

    duration_ms > 0 的药水缩放持续时间；否则返回 effect_scale 供调用方
    按比例缩放效果（对应「没有持续时间则是效果减少」）。
    """
    rng = rng or random
    potion = info.get('potion') or {}
    tier = potion_tier(potion.get('tier')) or potion_tier('common')
    effect = info.get('use_effect') or {}
    try:
        duration_ms = max(0, int(effect.get('duration_ms') or 0))
    except (TypeError, ValueError):
        duration_ms = 0
    try:
        max_hp = max(1, int(max_hp))
    except (TypeError, ValueError):
        max_hp = 1
    result = {
        'tier_key': tier['key'],
        'tier_label': tier.get('label', ''),
        'prefix': potion.get('prefix', ''),
        'emotion': int(tier.get('emotion', 0) or 0),
        'hp_loss': 0,
        'duration_ms': duration_ms,
        'effect_scale': 1.0,
        'scale': 1.0,
    }
    hp_ratio = tier.get('hp_ratio')
    if hp_ratio:
        ratio = rng.uniform(float(hp_ratio[0]), float(hp_ratio[1]))
        result['hp_ratio'] = ratio
        result['hp_loss'] = max(1, int(round(max_hp * ratio)))
    if duration_ms > 0:
        low, high = tier.get('duration_scale') or (1.0, 1.0)
        scale = rng.uniform(float(low), float(high))
        result['scale'] = scale
        result['duration_ms'] = max(1000, int(round(duration_ms * scale)))
    else:
        low, high = tier.get('effect_scale') or (1.0, 1.0)
        result['effect_scale'] = rng.uniform(float(low), float(high))
        result['scale'] = result['effect_scale']
    return result


def format_effect_summary(result):
    """把结算结果整理成一句人话，供仓库状态栏显示。"""
    parts = []
    if result.get('emotion'):
        parts.append(f'情绪{result["emotion"]:+d}')
    if result.get('hp_loss'):
        parts.append(f'活力-{result["hp_loss"]}')
    if result.get('duration_ms'):
        minutes = result['duration_ms'] / 60000.0
        parts.append(f'持续{minutes:.1f}分钟')
    if not parts:
        parts.append('无额外副作用')
    return '，'.join(parts)


def recipe_materials_text(recipe, items=None):
    """把配方的材料需求整理成文字。"""
    items = items or {}
    parts = []
    for key, count in recipe.get('materials') or ():
        name = (items.get(key) or {}).get('name', key)
        parts.append(f'{name}×{count}')
    return '、'.join(parts)


def recipe_desc(recipe, items=None):
    """配方要显示的描述：直接用物品簿里那条物品的「用途」。

    物品簿里查不到这条物品时，才回落到配方自带的兜底文案。
    """
    items = items or {}
    info = items.get(recipe.get('item')) or {}
    return info.get('desc') or recipe.get('desc') or ''


def recipe_effect_text(recipe):
    """把配方的使用效果整理成一句短文案。

    配方自带 effect_text 时直接用（例如刻意不写明真实效果的药水），
    否则按 effect 数据自动生成「持续时间 + 蒙版」。
    """
    override = (recipe or {}).get('effect_text')
    if override:
        return override
    effect = recipe.get('effect') or {}
    parts = []
    try:
        minutes = max(0, int(effect.get('duration_ms') or 0)) / 60000.0
    except (TypeError, ValueError):
        minutes = 0.0
    if minutes > 0:
        parts.append(f'持续 {minutes:g} 分钟')
    mask = (POTION_MASKS.get(effect.get('mask')) or {}).get('label')
    if mask:
        parts.append(f'染上{mask}蒙版')
    if not parts:
        return ''
    return '效果：' + '，'.join(parts) + '。'
