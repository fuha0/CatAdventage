# -*- coding: utf-8 -*-
"""猫猫桌宠 · 源码调试启动器（不打包、直接跑 桌宠/desktop_pet.py）。

为什么要有这个文件，而不是直接在 .bat 里写 python 桌宠\\desktop_pet.py：
  桌宠 目录名是中文，而 .bat 的内容会按控制台代码页解释，很容易变成乱码路径。
  所以 .bat 只负责「找到 Python，然后调用本文件」，中文路径由 Python 处理。

用法（也可以直接双击同目录的 启动猫猫.bat）：
    python run_cat.py                  # 普通启动
    python run_cat.py --fps 60         # 本次启动用 60 帧（不写入存档）
    python run_cat.py --scale 1.2      # 本次启动用 120% 大小
    python run_cat.py --action wave    # 启动后不停重放「招手」方便看效果
    python run_cat.py --action lick --repeat 3
    python run_cat.py --list-actions   # 列出所有动作 id
    python run_cat.py --restart        # 先把上一次启动的实例关掉再开

命令行给的 --fps / --scale 只影响这一次运行，不会覆盖设置面板里的存档值。
"""
import argparse
import ctypes
import os
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
PET_DIR = os.path.join(ROOT, 'CatPet')
ENTRY = os.path.join(PET_DIR, 'desktop_pet.py')
ASSET_DIR = os.path.join(ROOT, 'Materials')

MUTEX_NAME = 'CatAdventage_DesktopPet_SingleInstance'
PID_FILE = os.path.join(tempfile.gettempdir(), 'cat_pet_dev.pid')


def _force_utf8():
    """让中文在这里稳定输出，不受控制台代码页影响。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def _line(text=''):
    print(text, flush=True)


def _banner(title):
    _line('=' * 62)
    _line('  ' + title)
    _line('=' * 62)


# --------------------------------------------------------------- 单实例

def _mutex_alive():
    """另一个实例是否在运行（打包版和源码版用的是同一个互斥体名）。"""
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenMutexW.restype = ctypes.c_void_p
        kernel32.OpenMutexW.argtypes = [ctypes.c_ulong, ctypes.c_bool,
                                        ctypes.c_wchar_p]
        handle = kernel32.OpenMutexW(0x00100000, False, MUTEX_NAME)
        if not handle:
            return False
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return True
    except Exception:
        return False


def _read_pid():
    try:
        with open(PID_FILE, 'r', encoding='utf-8') as handle:
            return int(handle.read().strip() or 0)
    except Exception:
        return 0


def _write_pid(pid):
    try:
        with open(PID_FILE, 'w', encoding='utf-8') as handle:
            handle.write(str(int(pid)))
    except Exception:
        pass


def _clear_pid():
    try:
        os.remove(PID_FILE)
    except Exception:
        pass


def _pid_alive(pid):
    if pid <= 0:
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        code = ctypes.c_ulong()
        alive = bool(kernel32.GetExitCodeProcess(ctypes.c_void_p(handle),
                                                 ctypes.byref(code)))
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return alive and code.value == 259  # STILL_ACTIVE
    except Exception:
        return False


def _kill_previous():
    """关掉上一次由本启动器开的实例，以及打包版 CatPet.exe。"""
    killed = []
    pid = _read_pid()
    if _pid_alive(pid):
        try:
            os.kill(pid, 9)
            killed.append('源码实例 PID %d' % pid)
        except Exception:
            pass
    _clear_pid()
    try:
        result = subprocess.run(
            ['taskkill', '/F', '/IM', 'CatPet.exe'],
            capture_output=True, text=True)
        if result.returncode == 0 and 'CatPet.exe' in (result.stdout or ''):
            killed.append('打包版 CatPet.exe')
    except Exception:
        pass
    if killed:
        _line('  已关闭：' + '、'.join(killed))
        for _ in range(30):
            if not _mutex_alive():
                break
            time.sleep(0.1)
    return killed


# --------------------------------------------------------------- 启动

def _parse_args():
    parser = argparse.ArgumentParser(
        description='猫猫桌宠 · 源码调试启动器',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--fps', type=int, choices=(30, 60),
                        help='本次启动的动画帧率（不写入存档）')
    parser.add_argument('--scale', type=float,
                        help='本次启动的比例，0.5 ~ 1.5')
    parser.add_argument('--action', metavar='ID',
                        help='启动后立刻反复播放指定动作，方便盯着看效果')
    parser.add_argument('--repeat', type=float, default=4.0, metavar='秒',
                        help='配合 --action：每几秒重放一次（默认 4 秒）')
    parser.add_argument('--restart', action='store_true',
                        help='先关闭上一次启动的实例再启动')
    parser.add_argument('--list-actions', action='store_true',
                        help='列出所有动作 id 后退出')
    parser.add_argument('--keep', action='store_true',
                        help='退出后停住控制台，方便看报错（双击启动时默认开启）')
    parser.add_argument('--quiet', action='store_true',
                        help='只打印报错，不打印启动信息')
    return parser.parse_args()


def _print_env(pet, args, dev_mode):
    size = pet._display_size()[0]
    _line()
    _banner('环境')
    _line('  Python      : %s' % sys.version.split()[0])
    _line('  解释器路径  : %s' % sys.executable)
    _line('  运行模式    : %s' % ('源码 / dev（直接读 Materials/*.xlsx）'
                                 if dev_mode else '打包 / release（读 json 缓存））'))
    _line('  入口        : %s' % ENTRY)
    _line('  素材目录    : %s%s' % (ASSET_DIR,
                                   '' if os.path.isdir(ASSET_DIR) else '  ← 不存在！'))
    _line('  帧率        : %s 帧（%d ms/帧）%s'
          % (pet.frame_rate, pet.frame_rate and (16 if int(pet.frame_rate) >= 60 else 33),
             '  ← 命令行指定，仅本次' if args.fps else ''))
    _line('  比例        : %.0f%%  窗口约 %d x %d 像素%s'
          % (pet.scale * 100, size, size,
             '  ← 命令行指定，仅本次' if args.scale else ''))
    _line('  音量        : %s%s' % (getattr(pet, 'sound_volume', '?'), '%'))
    _line()
    _line('  关闭方式    : 右键猫 → 退出，或关掉这个控制台窗口后按 Ctrl+C')


def _list_actions():
    sys.path.insert(0, PET_DIR)
    import action_catalog as catalog
    _banner('所有动作 id（按权重排序）')
    specs = sorted(catalog.ACTION_LIST, key=lambda s: -s.weight)
    for spec in specs:
        if spec.layer in ('system',) and not spec.weight:
            continue
        _line('  %-16s %-8s 权重 %-5s  %s%s'
              % (spec.id, spec.layer, ('%.2f' % spec.weight).rstrip('0').rstrip('.'),
                 spec.name,
                 '  [需 %s]' % spec.requires_book if spec.requires_book else ''))
    _line()
    _line('  用法：python run_cat.py --action <id>')
    return 0


def _install_action_replay(pet, action_id, repeat_s):
    """启动后按固定节奏重放某个动作，方便肉眼比对。"""
    sys.path.insert(0, PET_DIR)
    import action_catalog as catalog
    spec = catalog.get_action(action_id)
    if spec is None:
        _line('  [警告] 没有叫 %r 的动作，用 --list-actions 看有哪些。'
              % action_id)
        return

    def fire():
        try:
            if getattr(pet, 'closing', False):
                return
            if spec.layer == 'overlay':
                pet.motion.finish_overlay(action_id)
                pet.motion.play_overlay(action_id, force=True)
            else:
                if pet.motion.current != 'idle':
                    pet.motion.finish(None, 'idle')
                pet.motion.play(action_id, force=True)
        except Exception as exc:
            _line('  [重放出错] %r' % (exc,))
        pet.root.after(max(800, int(repeat_s * 1000)), fire)

    _line()
    _line('  重放模式：每 %.1f 秒播一次「%s（%s）」，Ctrl+C 或关控制台结束'
          % (repeat_s, action_id, spec.name))
    pet.root.after(1200, fire)


def main():
    _force_utf8()
    args = _parse_args()

    if args.list_actions:
        return _list_actions()

    if not os.path.isfile(ENTRY):
        _line('[错误] 找不到入口文件：%s' % ENTRY)
        return 1

    try:
        import tkinter  # noqa: F401
    except Exception as exc:
        _line()
        _line('[错误] 当前这个 Python 没有 tkinter，桌宠起不来。')
        _line('       解释器：%s' % sys.executable)
        _line('       原因  ：%r' % (exc,))
        _line('       解决  ：换一个带 tkinter 的 Python 3，或用 启动猫猫.bat '
              '（它会自动挑带 tkinter 的那个）。')
        return 1

    if not args.quiet:
        _banner('猫猫桌宠 · 源码调试启动')

    if _mutex_alive():
        if args.restart:
            _kill_previous()
        if _mutex_alive():
            _line()
            _line('  [!] 已经有一个猫猫在运行了（打包版 CatPet.exe 或另一个源码实例）。')
            _line('      先把它关掉，或者改用：python run_cat.py --restart')
            return 1

    sys.path.insert(0, PET_DIR)
    try:
        # 导入 desktop_pet 本身就会把它的全局量注入各动画模块
        # （文件末尾那批 install_*_globals），所以这里不用再手工注入。
        import desktop_pet as dp
    except Exception:
        _line()
        _line('[错误] 导入桌宠模块失败，完整报错见下：')
        traceback.print_exc()
        return 1

    if not dp._acquire_single_instance():
        _line('  [!] 单实例检查没通过，可能是刚才那个实例还没完全退出，稍后再试。')
        return 1

    try:
        pet = dp.DesktopPet()
    except Exception:
        _line()
        _line('[错误] 创建窗口失败，完整报错见下：')
        traceback.print_exc()
        return 1

    if args.fps:
        dp.set_anim_fps(args.fps)
        pet.frame_rate = int(dp.ANIM_FPS)
    if args.scale:
        target = max(dp.SCALE_MIN, min(dp.SCALE_MAX, args.scale))
        pet.set_scale(target)
        if abs(target - args.scale) > 0.001:
            _line('  [提示] 比例已限制到允许范围 %.2f ~ %.2f，本次用 %.2f'
                  % (dp.SCALE_MIN, dp.SCALE_MAX, target))

    dev_mode = not getattr(sys, 'frozen', False)
    if not args.quiet:
        _print_env(pet, args, dev_mode)

    if args.action:
        _install_action_replay(pet, args.action, args.repeat)

    _write_pid(os.getpid())
    try:
        pet.run()
    except KeyboardInterrupt:
        pass
    except Exception:
        _line()
        _line('[错误] 运行中抛出异常：')
        traceback.print_exc()
        return 1
    finally:
        _clear_pid()
        try:
            pet.closing = True
            pet.root.destroy()
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    code = 1
    try:
        code = main()
    except KeyboardInterrupt:
        code = 0
    except Exception:
        _line()
        _line('[错误] 启动器自身出错：')
        traceback.print_exc()
    if code:
        _line()
        _line('  退出码 %d' % code)
    sys.exit(code)
