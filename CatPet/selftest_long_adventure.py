# -*- coding: utf-8 -*-
"""长期冒险功能的自检脚本（不启动 GUI，直接跑服务层）。

覆盖：
1. letters：动态冒险来信的生成、序号、内容持久化、排序。
2. save：adventure / letter_contents 的读写往返（模拟重启）。
3. long_adventure：计划、天数推进、途中事件、来信、面包消耗。
4. adventure.apply_reward：缩放参数的语义（长期冒险 hp_scale=0 不扣血）。
"""
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import letters as L
from services.long_adventure import (
    LongAdventureService, LONG_EXPLORE_DAYS, MINUTES_PER_DAY, is_long_adventure,
    region_supports_long_adventure, days_to_minutes, minutes_to_days, new_plan,
    sanitize_plan, elapsed_days, remaining_minutes, remaining_text,
    apply_item_rewards)
from services.adventure import AdventureService
from services.models import GameState
from services.save import SaveService
from services.progression import ProgressionService

FAILS = []


def check(label, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    if not condition:
        FAILS.append(f'{label}  {detail}')
    print(f'  [{status}] {label}' + (f'  -> {detail}' if detail and not condition else ''))


ITEMS = {
    'bread': {'name': '面包', 'category': '物品'},
    'green_herb': {'name': '绿草药', 'category': '物品'},
    'ore': {'name': '矿石', 'category': '物品'},
    'beast_meat': {'name': '兽肉', 'category': '物品'},
    'flint': {'name': '燧石', 'category': '物品'},
    'hat_ji': {'name': '一只小鸡', 'category': '头饰'},
}
REGIONS = {
    '1': {'name': '风和平原', 'fallback': True, 'min_level': 1,
          'xp_per_min_min': 24, 'xp_per_min_max': 28},
    '2': {'name': '低语森林', 'fallback': False, 'min_level': 5,
          'long_xp_per_day': 6200, 'long_gold_per_day': 130,
          'long_bread_per_day': 2, 'xp_per_min_min': 24, 'xp_per_min_max': 28},
    '3': {'name': '灰石谷', 'fallback': False, 'min_level': 15,
          'long_xp_per_day': 9000, 'long_gold_per_day': 200,
          'long_bread_per_day': 3},
    # 尚未实装：没有 long_* 口径，xp_per_min 也是 0（对应主程序里的圆心湖）。
    '4': {'name': '圆心湖', 'fallback': False, 'min_level': 30,
          'xp_per_min_min': 0, 'xp_per_min_max': 0},
}


def fake_treasure(region_id):
    return {'uid': random.randint(1, 10 ** 6), 'name': '小玩意',
            'prefix': '', 'quality': 2, 'base_value': 10, 'value': 20}


def make_service():
    return AdventureService(
        ITEMS, {1: 5, 2: 15, 3: 20}, {1: '粗劣', 2: '普通', 3: '少见',
                                      4: '稀有', 5: '史诗', 6: '传说'})


# ---------- 1. letters ----------
print('\n=== 1. 动态冒险来信 ===')
state = GameState()
state.letters = []
lid = L.send_adventure_letter(state, '低语森林的来信 · 第1天', '正文一')
check('send_adventure_letter 返回键名', lid == 'adv_letter_001', str(lid))
check('信件进入 letters', state.letters == ['adv_letter_001'], str(state.letters))
check('正文写进 letter_contents',
      state.letter_contents.get('adv_letter_001', {}).get('body') == '正文一')
lid2 = L.send_adventure_letter(state, '第二封', '正文二')
check('序号递增', lid2 == 'adv_letter_002', str(lid2))
info = L.get_letter('adv_letter_001', state.letter_contents)
check('get_letter 能取到动态信', info is not None and info['title'] == '低语森林的来信 · 第1天')
check('动态信 presentation=text', info and info.get('presentation') == 'text')
check('get_letter 未知键返回 None（既不是固定信也不是合法来信键）',
      L.get_letter('letter_99', {}) is None)
placeholder = L.get_letter('adv_letter_999', {})
check('内容丢失的来信退化成占位正文，不返回 None',
      placeholder is not None and '字迹' in placeholder['body'],
      str(placeholder))
check('is_adventure_letter', L.is_adventure_letter('adv_letter_003'))
check('固定信不受影响', L.get_letter('letter_2') is not None)

# 排序：固定信在前，动态信按序号在后
state.letters.insert(0, 'letter_2')
state.letters.sort(key=L.letter_number)
check('排序后固定信在前', state.letters[0] == 'letter_2' and
      state.letters[-1] == 'adv_letter_002', str(state.letters))
# 同一封信重复投递被忽略
check('重复投递被忽略', L.send_adventure_letter(state, 'x', 'y') == 'adv_letter_003'
      and L.send_letter(state, 'letter_2') is False)

# 动态信覆盖固定信正文（同一封信内容可变）
state.letter_contents['letter_2'] = {'title': '临时标题', 'body': '临时正文'}
overridden = L.get_letter('letter_2', state.letter_contents)
check('动态正文可覆盖固定信', overridden['body'] == '临时正文' and
      overridden['title'] == '临时标题')

# ---------- 2. 时长判定 ----------
print('\n=== 2. 时长判定与换算 ===')
check('30 分钟不是长期', not is_long_adventure(30))
check('3 天整不是长期（需求是「大于 3 天」）', not is_long_adventure(3 * MINUTES_PER_DAY))
check('3 天 + 1 分钟是长期', is_long_adventure(3 * MINUTES_PER_DAY + 1))
check('4 天是长期', is_long_adventure(4 * MINUTES_PER_DAY))
check('days_to_minutes(7)', days_to_minutes(7) == 7 * MINUTES_PER_DAY)
check('minutes_to_days(4天+1分) 向上取整', minutes_to_days(4 * MINUTES_PER_DAY + 1) == 5)
check('minutes_to_days(4天) 正好 4', minutes_to_days(4 * MINUTES_PER_DAY) == 4)

# 哪些地区能开长期冒险：平原（fallback）与尚未实装的地区都要排除。
check('低语森林支持长期冒险', region_supports_long_adventure(REGIONS['2']))
check('灰石谷支持长期冒险', region_supports_long_adventure(REGIONS['3']))
check('风和平原不支持（fallback）',
      not region_supports_long_adventure(REGIONS['1']))
check('尚未实装的圆心湖不支持（无日收益口径）',
      not region_supports_long_adventure(REGIONS['4']))
check('非法地区数据不支持', not region_supports_long_adventure(None))
check('非字典地区数据不支持', not region_supports_long_adventure('2'))

# ---------- 3. 计划与推进 ----------
print('\n=== 3. 长期冒险计划与逐天推进 ===')
now = 1_700_000_000.0
plan = new_plan('2', 4, now, seed=12345)
check('plan 字段齐全', plan['active'] and plan['days'] == 4 and
      plan['minutes'] == 4 * MINUTES_PER_DAY)
check('ends_at = started_at + 4 天',
      plan['ends_at'] == now + 4 * MINUTES_PER_DAY * 60)
check('elapsed_days 当天为 0', elapsed_days(plan, now) == 0)
check('elapsed_days 一天半后为 1', elapsed_days(plan, now + 1.5 * MINUTES_PER_DAY * 60) == 1)
check('elapsed_days 截到计划天数',
      elapsed_days(plan, now + 99 * MINUTES_PER_DAY * 60) == 4)
check('remaining_minutes 剩 4 天',
      remaining_minutes(plan, now) == 4 * MINUTES_PER_DAY)
check('剩余文本含「天」', '天' in remaining_text(plan, now), remaining_text(plan, now))

# sanitize_plan：非法数据要被拒绝
check('sanitize_plan 拒绝空', sanitize_plan({}, REGIONS) == {})
check('sanitize_plan 拒绝未知地区',
      sanitize_plan({'active': True, 'region': '9', 'days': 4,
                     'started_at': now, 'ends_at': now + 100}, REGIONS) == {})
check('sanitize_plan 拒绝 ends<=started',
      sanitize_plan({'active': True, 'region': '2', 'days': 4,
                     'started_at': now, 'ends_at': now}, REGIONS) == {})
ok_plan = sanitize_plan({'active': True, 'region': '2', 'days': 4,
                         'started_at': now, 'ends_at': now + 4 * MINUTES_PER_DAY * 60,
                         'seed': 7, 'settled_days': 99, 'bread_cost': 8}, REGIONS)
check('sanitize_plan 通过并夹住 settled_days',
      ok_plan and ok_plan['settled_days'] == 4 and ok_plan['bread_cost'] == 8)

# ---------- 4. 服务层：面包消耗 / 日收益 ----------
print('\n=== 4. 长期冒险服务 ===')
service = LongAdventureService(ITEMS, REGIONS, random)
check('4 天森林补给 = 2*4', service.bread_cost('2', 4) == 8)
check('7 天灰石谷补给 = 3*7', service.bread_cost('3', 7) == 21)
xp_day, gold_day = service.daily_base('2', 10)
check('森林日收益取配置', (xp_day, gold_day) == (6200, 130), f'{xp_day},{gold_day}')
xp_day2, _ = service.daily_base('1', 1)
check('平原无配置时兜底为 xp_per_min 口径×8 次', xp_day2 == 26 * 30 * 8, str(xp_day2))

# 地缘可复现：同一天、同 seed 两次结算结果一致
state_a = GameState(level=10, hp=500, max_hp=500)
state_b = GameState(level=10, hp=500, max_hp=500)
adv = make_service()
plan_a = new_plan('2', 4, now, seed=999)
plan_b = new_plan('2', 4, now, seed=999)
inv_a, inv_b = {}, {}
t_a, t_b = [], []
log_a, log_b = [], []
res_a = service.settle_days(
    plan_a, [1], state_a, inv_a, t_a, fake_treasure,
    lambda text, scale: adv.apply_reward(text, state_a, inv_a, t_a,
                                         fake_treasure, 2, 1.0,
                                         reward_scale=scale, hp_scale=0.0),
    lambda title, body: L.send_adventure_letter(state_a, title, body))
res_b = service.settle_days(
    plan_b, [1], state_b, inv_b, t_b, fake_treasure,
    lambda text, scale: adv.apply_reward(text, state_b, inv_b, t_b,
                                         fake_treasure, 2, 1.0,
                                         reward_scale=scale, hp_scale=0.0),
    lambda title, body: L.send_adventure_letter(state_b, title, body))
check('同 seed 第 1 天结算可复现（xp 一致）',
      res_a[0][1]['xp'] == res_b[0][1]['xp'],
      f"{res_a[0][1]['xp']} vs {res_b[0][1]['xp']}")
check('同 seed 第 1 天结算可复现（gold 一致）',
      res_a[0][1]['gold'] == res_b[0][1]['gold'])
check('结算后 settled_days 推进', plan_a['settled_days'] == 1)
check('pending_days 只返回未结算的天',
      service.pending_days(plan_a) == [2, 3, 4], str(service.pending_days(plan_a)))

# hp_scale=0：长期冒险不应扣血
state_c = GameState(level=10, hp=300, max_hp=300)
inv_c, t_c = {}, []
adv.apply_reward('生命-50', state_c, inv_c, t_c, fake_treasure,
                 2, 1.0, reward_scale=1.0, hp_scale=0.0)
check('hp_scale=0 时生命惩罚不扣血', state_c.hp == 300, str(state_c.hp))

# 缩放语义：经验/金币按 reward_scale 放大，物品按 item_scale
state_d = GameState(level=10, gold=0)
inv_d, t_d = {}, []
r = adv.apply_reward('经验+10，金币+5，绿草药×2', state_d, inv_d, t_d,
                     fake_treasure, 2, 1.0, reward_scale=288, item_scale=1.0,
                     hp_scale=0.0)
check('经验按 reward_scale 放大', r['xp'] == 10 * 288, str(r['xp']))
check('金币按 reward_scale 放大', state_d.gold == 5 * 288, str(state_d.gold))
check('物品不按 reward_scale 放大（避免爆仓）',
      inv_d.get('green_herb') == 2, str(inv_d))

# 全 4 天推进 + 天数字段
state_e = GameState(level=12, hp=800, max_hp=800)
inv_e, t_e = {}, []
plan_e = new_plan('2', 4, now, seed=4242)
letters_before = list(state_e.letters)
res_all = service.settle_days(
    plan_e, service.pending_days(plan_e), state_e, inv_e, t_e, fake_treasure,
    lambda text, scale: adv.apply_reward(text, state_e, inv_e, t_e,
                                         fake_treasure, 2, 1.0,
                                         reward_scale=scale, hp_scale=0.0),
    lambda title, body: L.send_adventure_letter(state_e, title, body))
check('4 天全部结算', len(res_all) == 4 and plan_e['settled_days'] == 4)
check('每天结算都有 xp/gold 字段',
      all(d['xp'] >= 0 and d['gold'] >= 0 for _, d in res_all))
check('来信会计入 letters', len(state_e.letters) >= len(letters_before))
letter_ids = [l for l in state_e.letters if L.is_adventure_letter(l)]
check('来信是 adv_letter_ 前缀', all(l.startswith('adv_letter_') for l in letter_ids),
      str(letter_ids))
check('来信正文都落盘',
      all(state_e.letter_contents.get(l, {}).get('body') for l in letter_ids))
check('letters_sent 与来信封数一致（归统计靠它跨重启）',
      plan_e.get('letters_sent') == len(letter_ids),
      f"letters_sent={plan_e.get('letters_sent')}, 实际={len(letter_ids)}")
print(f'    （4 天共收到 {len(letter_ids)} 封来信）')

# apply_item_rewards 名称/键名两种写法
inv_f = {}
granted = apply_item_rewards(ITEMS, inv_f, {'绿草药': 3, 'ore': 1, '不存在': 5})
check('apply_item_rewards 支持中文名与键名',
      granted.get('green_herb') == 3 and granted.get('ore') == 1, str(granted))
check('apply_item_rewards 忽略未知物品', '不存在' not in granted)

# ---------- 5. 存档往返（模拟重启） ----------
print('\n=== 5. 存档往返（模拟软件重启） ===')
tmp_dir = tempfile.mkdtemp(prefix='catadv_test_')
save_path = os.path.join(tmp_dir, 'save.json')
saver = SaveService(save_path, ITEMS, (), 10, (), (), {},
                    region_keys=tuple(REGIONS))
state_s = saver.new_state()
state_s.letters = []
state_s.letter_contents = {}
saved_plan = new_plan('2', 7, now, seed=777)
saved_plan['bread_cost'] = 14
state_s.adventure = saved_plan
L.send_adventure_letter(state_s, '森林来信', '一切平安')
L.send_adventure_letter(state_s, '第二封', '又走了一天')
saver.save(state_s)

# 同一份存档重新读（相当于重启软件）
saver2 = SaveService(save_path, ITEMS, (), 10, (), (), {},
                     region_keys=tuple(REGIONS))
loaded = saver2.load()
check('adventure 计划被持久化', loaded.adventure.get('active') is True)
check('计划地区保留', loaded.adventure.get('region') == '2')
check('计划天数保留', loaded.adventure.get('days') == 7)
check('started_at/ends_at 保留',
      loaded.adventure.get('started_at') == now and
      loaded.adventure.get('ends_at') == saved_plan['ends_at'])
check('seed 保留（重启后可复现同日结算）', loaded.adventure.get('seed') == 777)
check('面包消耗保留', loaded.adventure.get('bread_cost') == 14)
check('letters_sent 默认为 0 且可持久化',
      loaded.adventure.get('letters_sent') == 0,
      str(loaded.adventure.get('letters_sent')))
loaded.adventure['letters_sent'] = 3
saver2.save(loaded)
check('letters_sent 写回存档后仍是 3',
      SaveService(save_path, ITEMS, (), 10, (), (), {},
                  region_keys=tuple(REGIONS)).load().adventure.get(
                      'letters_sent') == 3)
loaded.adventure['letters_sent'] = 0
saver2.save(loaded)
check('letter_contents 持久化',
      loaded.letter_contents.get('adv_letter_001', {}).get('body') == '一切平安')
check('动态来信仍在 letters 里',
      'adv_letter_001' in loaded.letters and 'adv_letter_002' in loaded.letters)
loaded_info = L.get_letter('adv_letter_001', loaded.letter_contents)
check('重启后还能渲染动态信', loaded_info and loaded_info['body'] == '一切平安')

# 重启后按绝对时间继续推进：把 now 推到第 5 天，应能补齐 5 天
later = now + 5 * MINUTES_PER_DAY * 60 + 10
service2 = LongAdventureService(ITEMS, REGIONS, random)
pending = [d for d in service2.pending_days(loaded.adventure)
           if d <= elapsed_days(loaded.adventure, later)]
check('重启 5 天后要补 5 天', pending == [1, 2, 3, 4, 5], str(pending))
check('重启后 elapsed_days 正确', elapsed_days(loaded.adventure, later) == 5)

# 计划结束后清理
loaded.adventure = {}
saver2.save(loaded)
reloaded = SaveService(save_path, ITEMS, (), 10, (), (), {},
                       region_keys=tuple(REGIONS)).load()
check('结束后计划被清空', reloaded.adventure == {})

# ---------- 6. 旧存档兼容 ----------
print('\n=== 6. 旧存档兼容（无 adventure / letter_contents 字段） ===')
old_path = os.path.join(tmp_dir, 'old.json')
import json
with open(old_path, 'w', encoding='utf-8') as fh:
    json.dump({'gold': 5, 'level': 3, 'letters': ['letter_2']}, fh,
              ensure_ascii=False)
old = SaveService(old_path, ITEMS, (), 10, (), (), {},
                  region_keys=tuple(REGIONS)).load()
check('旧存档 adventure 为空字典', old.adventure == {})
check('旧存档 letter_contents 为空字典', old.letter_contents == {})
check('旧存档等级读到', old.level == 3)

# 损坏的 adventure 值不应炸
bad_path = os.path.join(tmp_dir, 'bad.json')
with open(bad_path, 'w', encoding='utf-8') as fh:
    json.dump({'adventure': 'not-a-dict', 'letter_contents': [1, 2]}, fh)
bad = SaveService(bad_path, ITEMS, (), 10, (), (), {},
                  region_keys=tuple(REGIONS)).load()
check('损坏 adventure 被忽略', bad.adventure == {})
check('损坏 letter_contents 被忽略', bad.letter_contents == {})

# ---------- 汇总 ----------
print('\n' + '=' * 56)
if FAILS:
    print(f'共 {len(FAILS)} 项失败：')
    for line in FAILS:
        print('  - ' + line)
    sys.exit(1)
print('全部通过 ✅')