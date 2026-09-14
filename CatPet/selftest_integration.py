# -*- coding: utf-8 -*-
"""长期冒险的集成自检：直接驱动真实的 DesktopPet（Tk 窗口会短暂出现）。

覆盖 GUI 侧接线：
- start_long_adventure → 计划落盘、面包扣除、adventuring 置位；
- 模拟重启（新建 DesktopPet 读同一份存档）→ 计划恢复、错过的天数补齐；
- 回到游戏后到点自动归来 → 日志写入、信件入库、计划清空、统计累计。
"""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 把存档目录隔离到临时目录（SATIETY_SAVE_PATH 走 expanduser('~')）。
SANDBOX_HOME = tempfile.mkdtemp(prefix='catadv_home_')
os.environ['USERPROFILE'] = SANDBOX_HOME
os.environ['HOME'] = SANDBOX_HOME

import desktop_pet as dp  # noqa: E402
from adventure_page import ADVENTURE_MODES, ADVENTURE_MODE_LONG  # noqa: E402
from services.long_adventure import (  # noqa: E402
    MINUTES_PER_DAY, LONG_EXPLORE_DAYS, elapsed_days)
import letters as L  # noqa: E402

FAILS = []


def check(label, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    if not condition:
        FAILS.append(f'{label}  {detail}')
    print(f'  [{status}] {label}' + (f'  -> {detail}' if detail and not condition else ''))


def make_pet():
    """建一个 DesktopPet，并把窗口藏起来、停掉会干扰测试的定时器。"""
    pet = dp.DesktopPet()
    pet.root.withdraw()
    pet.cat_name = '测试猫'
    pet.game.cat_name = '测试猫'
    # 测试里不需要托盘/随机动作/走动/掉落到任务栏。
    pet._stop_tray()
    pet.start_animations = lambda *a, **k: None
    pet._schedule_walk_attempt = lambda *a, **k: None
    pet._start_fall_check = lambda *a, **k: None
    pet._schedule_idle_exp = lambda *a, **k: None
    pet._schedule_mouse_check = lambda *a, **k: None
    pet._schedule_emotion_change = lambda *a, **k: None
    pet._schedule_online_tick = lambda *a, **k: None
    pet._setup_tray = lambda *a, **k: None
    # 离场动画在测试里直接跳到「完全离开屏幕」这一步。
    pet._start_adventure_departure = pet._finish_adventure_departure
    return pet


def teardown(pet):
    pet.closing = True
    try:
        pet.root.destroy()
    except Exception:
        pass


save_path = os.path.join(SANDBOX_HOME, '.cat_pet_satiety.json')

print('=== 1. 出发长期冒险 ===')
pet = make_pet()

# 真实配置回归：只有实装、且需要补给的地区才能开长期冒险。
from services.long_adventure import region_supports_long_adventure  # noqa: E402
check('真实配置：低语森林可长期冒险',
      region_supports_long_adventure(dp.REGIONS['2']))
check('真实配置：灰石谷可长期冒险',
      region_supports_long_adventure(dp.REGIONS['3']))
check('真实配置：风和平原被排除',
      not region_supports_long_adventure(dp.REGIONS['1']))
check('真实配置：尚未实装的圆心湖被排除',
      not region_supports_long_adventure(dp.REGIONS['4']))

# 给足面包与等级，避免卡在校验上。
pet.game.level = 12
pet.game.inventory['bread'] = 60
pet.game.hp = pet.game.max_hp
pet.game.adventure = {}
plan = None
pet.start_long_adventure('2', 4)
plan = pet.game.adventure
check('计划已写入 game.adventure', bool(plan.get('active')), str(plan))
check('计划地区=低语森林', plan.get('region') == '2', str(plan.get('region')))
check('计划天数=4', plan.get('days') == 4)
check('面包被扣除（4天×2=8）',
      pet.game.inventory.get('bread') == 52, str(pet.game.inventory.get('bread')))
check('adventuring 置位', pet.adventuring is True)
check('长期定时任务已注册 或 等待离场',
      pet._long_adv_job is not None or pet._adventure_departing)
# 固定随机种子：seed=8 在完整体检路径下 4 天里第 1、4 天会寄信，结果可复现。
# 注意必须落盘，否则「重启」读回的还是原来的随机种子。
pet.game.adventure['seed'] = 8
pet._save_satiety()
# 落到「离场完成 → 开计时」这一步
pet._begin_long_adventure_watch()
check('检查定时器已挂上', pet._long_adv_job is not None)
check('第 0 天没有可结算天数', pet.game.adventure.get('settled_days') == 0)

# 托盘提示与进度文本
captured_title = {}
pet._set_tray_title = lambda text: captured_title.__setitem__('title', text)
pet._update_tray_title()
check('托盘提示显示长期冒险进度',
      '长期冒险' in captured_title.get('title', '') and
      '/ 4 天' in captured_title.get('title', ''),
      captured_title.get('title'))
check('进度文本为「第 0 / 4 天」',
      pet._long_adventure_progress_text() == '第 0 / 4 天',
      pet._long_adventure_progress_text())

# 计划真的落盘了吗
saved = json.loads(Path(save_path).read_text(encoding='utf-8'))
check('adventure 已写进存档文件', saved.get('adventure', {}).get('active') is True)
check('存档里的面包数一致', saved['inventory'].get('bread') == 52)
teardown(pet)

print('\n=== 2. 模拟重启：计划恢复 + 补齐错过的天数 ===')
# 手动把出发时间往前挪 3 天，模拟「关掉软件 3 天」。
saved = json.loads(Path(save_path).read_text(encoding='utf-8'))
plan = saved['adventure']
shift = 3 * MINUTES_PER_DAY * 60 + 30
plan['started_at'] -= shift
plan['ends_at'] -= shift
Path(save_path).write_text(
    json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')

pet2 = make_pet()
plan2 = pet2.game.adventure
check('重启后计划被恢复', bool(plan2.get('active')), str(plan2))
check('重启后 adventuring 为真', pet2.adventuring is True)
check('重启后地区恢复', plan2.get('region') == '2')
check('重启后已补齐 3 天', plan2.get('settled_days') == 3,
      str(plan2.get('settled_days')))
check('重启后仍在计时', pet2._long_adv_job is not None)
adv_letters = [x for x in pet2.game.letters if L.is_adventure_letter(x)]
check('补齐的 3 天里收到了来信', len(adv_letters) >= 1,
      f'收到 {len(adv_letters)} 封')
check('来信正文已落盘',
      all(pet2.game.letter_contents.get(x, {}).get('body') for x in adv_letters))
check('来了信也能在仓库渲染',
      all(pet2._letter_info(x) is not None for x in adv_letters))
last_lines = ' | '.join(pet2._long_adv_last_lines)
check('途中结算写进了日志缓存', '第' in last_lines and '天' in last_lines)
teardown(pet2)

print('\n=== 3. 回到游戏：到期自动归来 ===')
saved = json.loads(Path(save_path).read_text(encoding='utf-8'))
plan = saved['adventure']
check('重启补齐后已收到来信（seed=8 的第 1 天）',
      any(L.is_adventure_letter(x) for x in saved.get('letters', [])),
      str(saved.get('letters')))
check('补齐的天数已写回存档', plan.get('settled_days') == 3,
      str(plan.get('settled_days')))
# 把结束时间挪到过去 → 启动时应当直接走「归来」。
shift = int(plan['days'] * MINUTES_PER_DAY * 60) + 600
plan['started_at'] -= shift
plan['ends_at'] -= shift
Path(save_path).write_text(
    json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')

pet3 = make_pet()
check('归来后 adventuring 为假', pet3.adventuring is False)
check('计划已从存档清空', pet3.game.adventure == {}, str(pet3.game.adventure))
check('归来后离场状态复位（可再次出发）',
      not getattr(pet3, '_adventure_departing', False))
check('写入了归来日志', any('长期冒险归来' in str(l)
                            for log in pet3.logs for l in log['lines']),
      str(pet3.logs[-1:]))
stats = pet3.stats
check('统计累计了长冒险次数', stats.get('long_adventure_count') == 1,
      str(stats.get('long_adventure_count')))
check('统计累计了长冒险天数', stats.get('long_adventure_days') == 4,
      str(stats.get('long_adventure_days')))
# seed=8 在完整体检路径下 4 天内会寄出 2 封（第 1、4 天），跨重启也不能漏。
check('统计累计了来信数（跨重启不漏）',
      stats.get('long_adventure_letter_count', 0) >= 2,
      str(stats.get('long_adventure_letter_count')))
check('归来日志里提到了来信',
      any('来信：' in str(l) for log in pet3.logs for l in log['lines']))
# 重复启动不应再触发
reloaded = json.loads(Path(save_path).read_text(encoding='utf-8'))
check('存档里 adventure 已清空', reloaded.get('adventure') == {},
      str(reloaded.get('adventure')))

print('\n=== 4. 取消长期冒险：计划要一并清掉 ===')
pet4 = pet3
pet4.game.inventory['bread'] = 60
pet4.game.hp = pet4.game.max_hp
pet4.game.adventure = {}
pet4.start_long_adventure('2', 7)
check('第二次出发成功', bool(pet4.game.adventure.get('active')))
pet4._begin_long_adventure_watch()
pet4._cancel_adventure()
check('取消后 adventuring 为假', pet4.adventuring is False)
check('取消后计划被清空（否则重启会复活）', pet4.game.adventure == {},
      str(pet4.game.adventure))
check('取消后定时器已注销', pet4._long_adv_job is None)
pet4._save_satiety()
saved = json.loads(Path(save_path).read_text(encoding='utf-8'))
check('取消后存档里也没有计划', saved.get('adventure') == {},
      str(saved.get('adventure')))

print('\n=== 5. 短途探险未受影响（回归） ===')
pet4.game.hp = pet4.game.max_hp
pet4.game.inventory['bread'] = 60
pet4._adventure_job = None
pet4.start_adventure('2', 30)
check('短途仍走老路径（无长期计划）', pet4.game.adventure == {},
      str(pet4.game.adventure))
check('短途 adventuring 为真', pet4.adventuring is True)
check('短途离场完成后挂的是分钟级定时器',
      pet4._adventure_job is not None and pet4._long_adv_job is None,
      f'job={pet4._adventure_job}, long={pet4._long_adv_job}')
check('短途剩余时间可读', pet4._adventure_remaining_minutes() >= 25,
      str(pet4._adventure_remaining_minutes()))
teardown(pet4)

# ---------- 6. 探险全程不弹窗 ----------
print('\n=== 6. 探险全程不弹窗（校验/出发/归来都只写日志） ===')
import tkinter.messagebox as mb  # noqa: E402

popup_calls = []
_orig_askyesno, _orig_showinfo = mb.askyesno, mb.showinfo


def _spy(name, default):
    def _inner(*args, **kwargs):
        popup_calls.append((name, args[:1]))
        return default
    return _inner


mb.askyesno = _spy('askyesno', False)
mb.showinfo = _spy('showinfo', None)

pet5 = make_pet()
pet5.game.level = 12
pet5.game.hp = pet5.game.max_hp
pet5.game.adventure = {}
pet5.logs = []

# 面包不足：应当只写日志，不弹窗、不出发
pet5.game.inventory['bread'] = 0
pet5.start_long_adventure('2', 4)
check('面包不足：没有弹窗', not popup_calls, str(popup_calls))
check('面包不足：没有出发', pet5.adventuring is False)
check('面包不足：写进了探险日志',
      any('面包不足' in str(l) for log in pet5.logs for l in log['lines']),
      str(pet5.logs[-1:]))

# 等级不足
pet5.logs = []
pet5.game.level = 1
pet5.game.inventory['bread'] = 60
pet5.start_long_adventure('3', 4)
check('等级不足：没有弹窗', not popup_calls, str(popup_calls))
check('等级不足：没有出发', pet5.adventuring is False)
check('等级不足：写进了探险日志',
      any('练练级' in str(l) for log in pet5.logs for l in log['lines']),
      str(pet5.logs[-1:]))

# 不支持的地区（平原 / 尚未实装）
pet5.logs = []
pet5.game.level = 12
pet5.start_long_adventure('1', 4)
check('平原长冒险：没有弹窗', not popup_calls, str(popup_calls))
check('平原长冒险：没有出发', pet5.adventuring is False)
check('平原长冒险：写进了探险日志',
      any('不适合长期冒险' in str(l) for log in pet5.logs for l in log['lines']),
      str(pet5.logs[-1:]))

# 正常出发：也只写日志
pet5.logs = []
pet5.start_long_adventure('2', 4)
check('正常出发：没有弹窗', not popup_calls, str(popup_calls))
check('正常出发：已出发', pet5.adventuring is True)
check('正常出发：日志里有「长期冒险出发」',
      any('长期冒险出发' in str(l) for log in pet5.logs for l in log['lines']),
      str(pet5.logs[-1:]))
check('正常出发：日志里有预计归来时间',
      any('预计归来' in str(l) for log in pet5.logs for l in log['lines']))

# 取消：同样只写日志，并把面包不退还写清楚
pet5._begin_long_adventure_watch()
pet5.logs = []
pet5._cancel_adventure()
check('取消：没有弹窗', not popup_calls, str(popup_calls))
check('取消：写进了探险日志',
      any('长期冒险取消' in str(l) for log in pet5.logs for l in log['lines']),
      str(pet5.logs[-1:]))

# 页面：切到长期模式，提示写的是「长期冒险」而非短途口径；点开始不弹窗
pet5.logs = []
pet5.game.adventure = {}
pet5.game.inventory['bread'] = 8
pet5.adventuring = False
pet5.show_adventure()
long_label = [text for key, text in
              ADVENTURE_MODES if key == ADVENTURE_MODE_LONG][0]
try:
    # 默认地区是风和平原，长期模式下应当提示不适合。
    pet5._adventure_mode_var.set(long_label)
    pet5._adventure_mode_changed()
    check('长期模式 + 平原：提示不适合长期冒险',
          '不适合长期冒险' in pet5._adventure_unlock_label.cget('text'),
          pet5._adventure_unlock_label.cget('text'))

    # 换到低语森林：提示应当说明补给消耗与来信机制。
    pet5._adventure_region_var.set(dp.REGIONS['2']['name'])
    pet5._adventure_region_changed()
    hint_text = pet5._adventure_unlock_label.cget('text')
    check('长期模式 + 低语森林：提示提到补给与来信',
          '面包' in hint_text and '寄信' in hint_text, hint_text)
    check('长期模式：按钮文案变成「开始长期冒险」',
          pet5._adventure_start_button.cget('text') == '开始长期冒险')
    check('长期模式：显示「天」档、隐藏「分钟」档',
          bool(pet5._adventure_long_row.grid_info()) and
          not pet5._adventure_short_row.grid_info())
    check('长期模式：只有 4/7/14/30 天可选',
          [int(x) for x in pet5._adventure_days_combo.cget('values')] ==
          list(LONG_EXPLORE_DAYS))

    # 面包不足时在页面上点出发：只写日志，不弹窗。
    pet5.game.inventory['bread'] = 0
    pet5._adventure_page_start()
    check('页面上点出发：不弹窗', not popup_calls, str(popup_calls))
    check('页面上点出发：日志里写了面包不足',
          any('面包不足' in str(l) for log in pet5.logs for l in log['lines']),
          str(pet5.logs[-1:]))

    # 补给足够时在页面上点出发 → 出发成功，且页面重新打开后显示长期进度。
    pet5.game.inventory['bread'] = 60
    pet5._adventure_page_start()
    check('页面上点出发（补给足够）：不弹窗', not popup_calls, str(popup_calls))
    check('页面上点出发（补给足够）：已出发', pet5.adventuring is True)
    pet5.show_adventure()
    pet5._refresh_adventure_page()
    status = pet5._adventure_status.cget('text')
    check('探险页状态显示长期冒险进度',
          '长期冒险中' in status and '/ 4 天' in status, status)
    pet5.close_adventure()
    pet5._cancel_adventure()

    # 切回短途：提示与按钮文案复原。
    pet5.show_adventure()
    pet5._adventure_mode_var.set(ADVENTURE_MODES[0][1])
    pet5._adventure_mode_changed()
    check('切回短途：按钮文案复原',
          pet5._adventure_start_button.cget('text') == '开始探险')
    check('切回短途：隐藏「天」档、显示「分钟」档',
          bool(pet5._adventure_short_row.grid_info()) and
          not pet5._adventure_long_row.grid_info())
finally:
    pet5.close_adventure()

# 短途：出发与归来也都不弹窗，结果只走日志
pet5.game.adventure = {}
pet5.adventuring = False
pet5.hospitalized = False
pet5.game.hp = pet5.game.max_hp
pet5.game.level = 12
pet5.game.inventory['bread'] = 60
pet5.logs = []
pet5._adventure_job = None
pet5._confirm_adventure('2', 30)
check('短途出发：不弹窗', not popup_calls, str(popup_calls))
check('短途出发：已出发', pet5.adventuring is True)
check('短途出发：日志里有「探险出发」',
      any('【探险出发】' in str(l) for log in pet5.logs for l in log['lines']),
      str(pet5.logs[-1:]))
check('短途出发：日志里写了消耗与预计归来',
      any('消耗面包' in str(l) for log in pet5.logs for l in log['lines']) and
      any('预计归来' in str(l) for log in pet5.logs for l in log['lines']))
pet5.logs = []
pet5._finish_adventure()
check('短途归来：不弹窗', not popup_calls, str(popup_calls))
check('短途归来：日志里有「探险归来」',
      any('【探险归来' in str(l) for log in pet5.logs for l in log['lines']),
      str(pet5.logs[-1:]))

# 活力不足：只写日志
pet5.logs = []
pet5.game.hp = 5
pet5._confirm_adventure('2', 30)
check('活力不足：不弹窗', not popup_calls, str(popup_calls))
check('活力不足：写进了探险日志',
      any('活力值不足' in str(l) for log in pet5.logs for l in log['lines']),
      str(pet5.logs[-1:]))
teardown(pet5)

mb.askyesno, mb.showinfo = _orig_askyesno, _orig_showinfo

print('\n' + '=' * 56)
try:
    shutil.rmtree(SANDBOX_HOME)
except Exception:
    pass
if FAILS:
    print(f'共 {len(FAILS)} 项失败：')
    for line in FAILS:
        print('  - ' + line)
    sys.exit(1)
print('全部通过 ✅')