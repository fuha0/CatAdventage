# -*- coding: utf-8 -*-
"""动画执行器：动作登记统一放在 action_catalog.py。"""
import random
from action_catalog import DRAG_MODE_IDS, choose_idle_action

ACTION_MIN_MS = 2500
ACTION_MAX_MS = 6000
BLINK_CLOSED_MS = 150
EAR_MOVE_MS = 180
EAR_GAP_MS = 120
TAIL_MOVE_MS = 220
TAIL_GAP_MS = 160
SCRATCH_FRAME_MS = 30
SCRATCH_LIFT_FRAME_MS = 5
SCRATCH_TRANSITION_FRAME_MS = 15
SCRATCH_OFFSET = 26

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
            # 抬起：用更多中间帧让轨迹更清晰
            steps = 12
            for i in range(steps + 1):
                frames.append((i / steps, 0.0, SCRATCH_LIFT_FRAME_MS))
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
        self.update_image()
        self._anim_job = self.animations.schedule('idle', 
            delay_ms, lambda: self._play_scratch(step + 1))

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
        self.motion.cancel_overlays()
        if self.motion.current == 'scratch':
            self.motion.finish('scratch')
        self._active_idle_action = None
