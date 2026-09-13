# -*- coding: utf-8 -*-
"""动画执行器：动作登记统一放在 action_catalog.py。"""
import random
from action_catalog import DRAG_MODE_IDS, choose_idle_action

# 动作间隔。加了一批新动作之后把间隔缩短了一点：闲置 2.5~6 秒才动一次
# 本来就是「挂机不够生动」的一部分原因，现在 2.2~5 秒。
ACTION_MIN_MS = 2200
ACTION_MAX_MS = 5000
BLINK_CLOSED_MS = 150
EAR_MOVE_MS = 180
EAR_GAP_MS = 120
TAIL_MOVE_MS = 220
TAIL_GAP_MS = 160
# 挠头「抓挠」每一下的帧间隔。原来写 30ms，但系统定时器 tick 约 15.4ms，
# 30ms 会被推到第 3 个 tick（实测 46.4ms，只有 21 帧/秒，看着就是一跳一跳）。
# 取 25ms 正好落在第 2 个 tick 上（实测 30.8ms ≈ 32 帧/秒），也更接近原设计值。
SCRATCH_FRAME_MS = 25
# 落手在 1 个 tick 上（实测 15.4ms），与抬手对称
SCRATCH_TRANSITION_FRAME_MS = 15
SCRATCH_OFFSET = 26

# ------------------------------------------------------------------
# 新增待机动作的参数
# ------------------------------------------------------------------
# 头部转动只用这几个离散角度。head_sway 是合成参数（整组头部绕 (450,380)
# 旋转），每换一个角度就是一张新的显示图（冷合成约 95ms），所以角度集合
# 必须小，并且提前在闲时热好 —— 之后每帧只要换一张缓存好的图。
HEAD_SWAY_STEP_ANGLES = (4.0, 8.0)


def _angles_from(factors, base):
    """把「倍数表」展开成实际角度集合（含 ± 两侧）。"""
    out = set()
    for factor, _ms in factors:
        for value in (base * factor, -base * factor):
            value = round(value, 3)
            out.add(0.0 if value == 0 else value)   # 把 -0.0 归成 0.0
    return out
# 招手/舔手的帧间隔。25ms 会落在第 2 个定时器 tick 上（实测 30.8ms ≈ 32 帧/秒），
# 和挠头的「抓挠」同一档：手部动作 32 帧/秒已经足够顺，CPU 只要 65 帧档的一半。
# 别写 40ms —— 那会被推到第 3 个 tick（46.5ms），一眼就看出卡。
HAND_ACTION_FRAME_MS = 25
WAVE_TOTAL_MS = 1600           # 招手总时长（含抬手那 30%）
LICK_TOTAL_MS = 1500           # 舔手总时长
MEOW_HOLD_MS = 700             # 喵一声：张着嘴多久（表情只停留 0.7s）

# 待机换表情不再硬编码组合，而是复用 _random_click_expression()：
# 那里已经按「表情管理书籍」约束可选素材（例如 eye_2 是「生无可恋」书专属），
# 硬编码会把需要勾选书籍才会出现的表情也塞进待机里。
# 舔手时的表情：眯着眼抿嘴，像在认真舔爪子（这些素材都是默认可选，不涉及书籍）
LICK_EXPRESSION = {'eye': 'eye_close2', 'brow': 'brow', 'mouth': 'mouth_comfy'}
# 喵一声的表情：眯眼张嘴
MEOW_EXPRESSION = {'eye': 'eye_close2', 'brow': 'brow', 'mouth': 'mouth_huya'}

class AnimationMixin:
    def start_animations(self):
        """开始随机动作循环"""
        self._cancel_anim()
        self._schedule_next()

    def _schedule_next(self):
        """睁眼休息随机一段时间后，执行下一个动作"""
        if (self.closing or self.hospitalized or self.dragging
                or self.flinging or self.climbing
                or self.motion.current in (
                    'jump', 'scratch', 'reach', 'fall', 'adventure_wave',
                    'adventure_hop', 'adventure_launch',
                    'hospital', 'closing')):
            return
        delay = random.randint(ACTION_MIN_MS, ACTION_MAX_MS)
        self._anim_job = self.animations.schedule('idle', delay, self._do_action)

    def _do_action(self):
        """随机挑一个动作：抖耳朵 / 挠头 / 摇尾巴 / 眨眼"""
        self._anim_job = None
        if (self.closing or self.hospitalized or self.dragging
                or self.flinging or self.climbing
                or self.motion.current in (
                    'jump', 'scratch', 'reach', 'fall', 'adventure_wave',
                    'adventure_hop', 'adventure_launch',
                    'hospital', 'closing')):
            return
        action = choose_idle_action(
            books_enabled=self.books_enabled)
        self._active_idle_action = action.id
        if action.layer == 'overlay':
            if not self.motion.play_overlay(action.id):
                self._schedule_next()
        elif not self.motion.play(action.id):
            self._schedule_next()

    def _play_blink(self):
        """眨眼：闭眼一下，再睁开；无所谓喵样式下不执行。"""
        if self.closing or self.dragging:
            return
        self._active_idle_action = 'blink'
        if self._current_expression_key() == 'comfy':
            self.motion.finish_overlay('blink')
            self._schedule_next()
            return
        self.show_pose('blink')
        self._anim_job = self.animations.schedule('idle', BLINK_CLOSED_MS, self._finish_action)

    def _play_ear(self, count=0):
        """耳朵动两下：右上角下拉形变 -> 恢复 -> 再下拉 -> 恢复"""
        if self.closing or self.dragging:
            return
        self._active_idle_action = 'ear'
        if count == 0 and not self.motion.is_active('ear'):
            self._schedule_next()
            return
        if count >= 2:  # 已经动完两下
            self.motion.finish_overlay('ear')
            self.show_pose('normal')
            self._schedule_next()
            return
        self.show_pose('ear')
        self._anim_job = self.animations.schedule('idle', EAR_MOVE_MS,
                                         lambda: self._ear_gap(count))

    def _ear_gap(self, count):
        """耳朵两下之间短暂恢复"""
        if self.closing or self.dragging:
            return
        self.show_pose('normal')
        self._anim_job = self.animations.schedule('idle', EAR_GAP_MS,
                                         lambda: self._play_ear(count + 1))

    def _play_tail(self, count=0):
        """尾巴轻摆两下：摆 -> 恢复 -> 摆 -> 恢复"""
        if self.closing or self.dragging:
            return
        self._active_idle_action = 'tail'
        if count == 0 and not self.motion.is_active('tail'):
            self._schedule_next()
            return
        if count >= 2:
            self.motion.finish_overlay('tail')
            self.show_pose('normal')
            self._schedule_next()
            return
        self._tail_tilt = -1.0  # 只往下摇，避免上摇冲突
        self.show_pose('tail')
        self._anim_job = self.animations.schedule('idle', TAIL_MOVE_MS,
                                         lambda: self._tail_gap(count))

    def _tail_gap(self, count):
        """尾巴两下之间短暂恢复"""
        if self.closing or self.dragging:
            return
        self.show_pose('normal')
        self._anim_job = self.animations.schedule('idle', TAIL_GAP_MS,
                                         lambda: self._play_tail(count + 1))

    def _play_scratch(self, step=0):
        """待机挠头：停下走动 → 抬手轨迹 → 挠两下 → 落手轨迹"""
        if self.closing or self.dragging:
            return
        if step == 0:
            if not self.motion.enter('scratch'):
                self._schedule_next()
                return
            self.motion.cancel_overlays()
            # 触发动作时必须停下走动
            if self.walking:
                self._cancel_walk()
                self.walking = False
            self._scratch_wave_style = 'vertical'
            self._scratch_wave_offset = SCRATCH_OFFSET
            self._scratch_side = random.choice(('left', 'right'))
            frames = []
            # 抬起：用更多中间帧让轨迹更清晰。
            # 帧间隔取 _hand_frame_ms()（贴着系统定时器 tick 的 60 帧档）：
            # 以前这里是 5ms，但那时每帧都要重合成整张 1024 图（约 95ms），
            # 名义 200 帧/秒实际只有约 10 帧/秒，看着就是一跳一跳的。
            # 现在每帧只贴两只手（约 1ms），13 帧全程约 0.2 秒且每帧都看得到。
            steps = 12
            lift_ms = self._hand_frame_ms()
            for i in range(steps + 1):
                frames.append((i / steps, 0.0, lift_ms))
            # 挠两下：使用连续位置，避免手部直接跳动
            scratch_curve = (0.0, 0.35, 0.7, 1.0, 0.7, 0.35)
            frames += [(1.0, stage, SCRATCH_FRAME_MS)
                       for stage in scratch_curve]
            frames += [(1.0, stage, SCRATCH_FRAME_MS)
                       for stage in scratch_curve]
            frames.append((1.0, 0.0, SCRATCH_FRAME_MS))
            # 放下：1 → 0
            for i in range(steps, -1, -1):
                frames.append((i / steps, 0.0, SCRATCH_TRANSITION_FRAME_MS))
            self._scratch_frames = frames
        if step >= len(self._scratch_frames):
            self.motion.finish('scratch')
            self._scratch_lift = 0.0
            self._scratch_stage = -1
            self.pose = 'normal'
            self.update_image()
            self._schedule_walk_attempt()
            self._schedule_next()
            return
        frame = self._scratch_frames[step]
        if len(frame) >= 3:
            self._scratch_lift, self._scratch_stage, delay_ms = frame
        else:
            self._scratch_lift, self._scratch_stage = frame
            delay_ms = SCRATCH_FRAME_MS
        self.pose = 'scratch'
        # 只贴手，不重合成整图：抬手/挠动才能真的按上面的节拍走
        self._render_hand_frame(
            'scratch', self._display_size()[0], self._scratch_hand_pastes())
        self._anim_job = self.animations.schedule('idle',
            delay_ms, lambda: self._play_scratch(step + 1))

    # ------------------------------------------------------------------
    # 主体类待机动作：转头环顾 / 晃头 / 招手 / 舔手
    #
    # 这几种都要占住整幅画面（转头要重画整张图、招手要贴手），所以和挠头一样
    # 走 motion.enter（interaction 层），开场先停下走动、清掉耳朵尾巴这些叠层。
    # ------------------------------------------------------------------

    def _prepare_body_action(self):
        """主体类动作的共同开场：停下走动、清叠层、姿势回到站立。

        不这么做的话，叠层（耳朵/尾巴/表情）会画在已经转头或抬起手的画面上，
        而「全过程合成」和「显示尺寸贴图」两条渲染通路的键就不一致了。
        """
        self.motion.cancel_overlays()
        if self.walking:
            self._cancel_walk()
            self.walking = False
        self.pose = 'normal'

    def _finish_body_action(self, action_id):
        """主体类动作收尾：状态复位、重画一张干净的站立帧、安排下一次动作。"""
        self._idle_head_sway = 0.0
        self._idle_hand_action = None
        self._idle_hand_t = 0.0
        self._idle_hand_phase = 0.0
        self._clear_idle_expressions()
        self.motion.finish(action_id)
        self.pose = 'normal'
        # update_image 不带 head_sway，所以这一下也顺手把头转回 0
        self.update_image()
        self._schedule_walk_attempt()
        self._schedule_next()

    def _set_idle_expression(self, owner, expression):
        """把一组表情（dict，可缺 eye/brow/mouth 任一项）压上表情栈并重画。

        用 motion.set_expression 而不是直接改 _forced_expression：表情栈带
        优先级，单击反应（优先级更高）能自然地压过待机表情。缺项由
        renderer 的 .get(..., 默认值) 兜底，所以传部分 dict 也安全。
        """
        self.motion.set_expression(owner, dict(expression))
        self.update_image()

    def _clear_idle_expressions(self):
        """撤掉所有待机表情，避免残留（拖拽/关闭会把动画打断在半路）。"""
        for owner in ('meow', 'lick'):
            self.motion.clear_expression(owner)

    def _hand_action_frames(self, frame_ms, total_ms):
        """把一段手部动作切成 [(t, 帧间隔), ...]，t 从 0 匀速走到 1。

        t 是「动作进度」而不是帧号：抬手、摆动、舔的曲线都按 t 算，
        所以改总时长只改速度，不会改变动作形状。
        """
        count = max(2, int(round(total_ms / float(frame_ms))))
        return [(i / float(count), frame_ms) for i in range(count + 1)]

    def _play_wave(self, step=0):
        """招手：抬起一只手，左右摆几下打招呼。"""
        if self.closing or self.dragging:
            return
        if step == 0:
            if not self.motion.enter('wave'):
                self._schedule_next()
                return
            self._prepare_body_action()
            self._idle_hand_action = 'wave'
            self._idle_hand_side = random.choice(('left', 'right'))
            self._idle_hand_phase = random.choice((-1.0, 1.0))
            self._idle_hand_t = 0.0
            self._wave_frames = self._hand_action_frames(
                HAND_ACTION_FRAME_MS, WAVE_TOTAL_MS)
        if step >= len(self._wave_frames):
            self._finish_body_action('wave')
            return
        t, delay_ms = self._wave_frames[step]
        self._idle_hand_t = t
        self._render_hand_frame(
            'normal', self._display_size()[0], self._wave_hand_pastes())
        self._anim_job = self.animations.schedule(
            'idle', delay_ms, lambda: self._play_wave(step + 1))

    def _play_lick(self, step=0):
        """舔手：抬起一只手到嘴边，上下舔几下（顺手眯起眼睛）。"""
        if self.closing or self.dragging:
            return
        if step == 0:
            if not self.motion.enter('lick'):
                self._schedule_next()
                return
            self._prepare_body_action()
            self._idle_hand_action = 'lick'
            self._idle_hand_side = random.choice(('left', 'right'))
            self._idle_hand_phase = random.choice((-1.0, 1.0))
            self._idle_hand_t = 0.0
            self._lick_frames = self._hand_action_frames(
                HAND_ACTION_FRAME_MS, LICK_TOTAL_MS)
            # 表情要设在第一帧渲染之前：它在显示图的缓存键里，
            # 所以「眯着眼」的那张底图是独立的一张，先设好才不会画错。
            self._set_idle_expression('lick', LICK_EXPRESSION)
        if step >= len(self._lick_frames):
            self._finish_body_action('lick')
            return
        t, delay_ms = self._lick_frames[step]
        self._idle_hand_t = t
        self._render_hand_frame(
            'normal', self._display_size()[0], self._lick_hand_pastes())
        self._anim_job = self.animations.schedule(
            'idle', delay_ms, lambda: self._play_lick(step + 1))

    # ------------------------------------------------------------------
    # 表情类待机动作：喵一声（overlay，只换脸，走路时也能来一下）
    # 「换表情」动作已删除 —— 猫叫本身就带表情了。
    # ------------------------------------------------------------------

    def _play_meow(self, step=0):
        """偶尔喵一声：张着嘴眯着眼叫一下，同时放一声喵。"""
        if self.closing or self.dragging:
            return
        if step == 0:
            self._active_idle_action = 'meow'
            if not self.motion.is_active('meow'):
                self._schedule_next()
                return
            self._set_idle_expression('meow', MEOW_EXPRESSION)
            self._play_meow_sound()
            self._anim_job = self.animations.schedule(
                'idle', MEOW_HOLD_MS, lambda: self._play_meow(1))
            return
        self._clear_idle_expressions()
        self._finish_action()

    def _finish_action(self):
        """动作结束：恢复睁眼，并安排下一次随机动作"""
        self._anim_job = None
        if self.closing or self.dragging:
            return
        self.show_pose('normal')
        self.motion.finish_overlay(getattr(self, '_active_idle_action', None))
        self._schedule_next()

    def _cancel_anim(self):
        """取消已排定的随机动作任务"""
        if self._anim_job is not None:
            try:
                self.animations.cancel('idle')
            except Exception:
                pass
            self._anim_job = None
        cancel_bounce = getattr(self, '_cancel_click_bounce', None)
        if cancel_bounce is not None:
            cancel_bounce()
        self.motion.cancel_overlays()
        if self.motion.current == 'scratch':
            self.motion.finish('scratch')
        # 主体类动作被打断在半路时，手势和表情都会留在原地：
        # 手要放下、表情要撤掉，否则会一直僵着。
        for action_id in ('wave', 'lick'):
            self.motion.finish(action_id)
        self._idle_head_sway = 0.0
        self._idle_hand_action = None
        self._idle_hand_t = 0.0
        self._idle_hand_phase = 0.0
        self._clear_idle_expressions()
        self._active_idle_action = None


def idle_head_sway_angles():
    """待机动作会用到的全部头部角度（含 0），供启动后预热用。

    转头环顾（head_look）已移除，这里保留 0 度（站立底图）与
    HEAD_SWAY_STEP_ANGLES（旧有转头离散角），供仍引用此函数的调用方
    取到一个非空、且含 0 度的集合。
    """
    angles = {0.0}
    angles |= _angles_from(tuple((a, 0) for a in HEAD_SWAY_STEP_ANGLES), 1.0)
    return tuple(sorted(round(a, 3) for a in angles))
