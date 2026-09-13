# -*- coding: utf-8 -*-
"""动画状态机：管理主体状态、叠加动作、阶段和表情覆盖。"""
import time

from action_catalog import ACTION_CATALOG, get_action


class AnimationStateMachine:
    def __init__(self, owner):
        self.owner = owner
        self.current = 'idle'
        self.phase = None
        self.overlays = {}
        self._last_started = {}
        self._expressions = []

    def spec(self, action_id=None):
        return get_action(action_id or self.current)

    def is_active(self, action_id):
        return self.current == action_id or action_id in self.overlays

    def can_start(self, action_id, force=False, ignore_cooldown=False):
        spec = get_action(action_id)
        if spec is None:
            return False
        if getattr(self.owner, 'closing', False) and action_id != 'closing':
            return False
        if force or action_id == self.current:
            return True
        if spec.requires_book:
            books = getattr(self.owner, 'books_enabled', set())
            if spec.requires_book not in books:
                return False
        if not ignore_cooldown and spec.cooldown_ms > 0:
            last = self._last_started.get(action_id, 0.0)
            if (time.monotonic() - last) * 1000.0 < spec.cooldown_ms:
                return False
        current_spec = get_action(self.current) or get_action('idle')
        if current_spec is None:
            return True
        if spec.allowed_from and self.current not in spec.allowed_from:
            if self.current not in spec.interrupts:
                return False
        if current_spec.priority > spec.priority:
            return current_spec.interruptible and (
                self.current in spec.interrupts or not spec.allowed_from)
        if current_spec.priority == spec.priority and current_spec.id != spec.id:
            return current_spec.interruptible and self.current in spec.interrupts
        return True

    def enter(self, action_id, phase=None, force=False,
              ignore_cooldown=False):
        if not self.can_start(action_id, force, ignore_cooldown):
            return False
        self.current = action_id
        self.phase = phase
        self._last_started[action_id] = time.monotonic()
        self._prune_overlays(action_id)
        return True

    transition = enter

    def finish(self, action_id=None, next_action='idle'):
        if action_id is not None and self.current != action_id:
            return False
        self.current = next_action
        self.phase = None
        self._prune_overlays(next_action)
        return True

    def set_phase(self, phase, action_id=None):
        if action_id is not None and self.current != action_id:
            return False
        self.phase = phase
        return True

    def enter_overlay(self, action_id, force=False):
        spec = get_action(action_id)
        if spec is None or not spec.layer == 'overlay':
            return False
        if not force and spec.allowed_from and self.current not in spec.allowed_from:
            return False
        if not force and spec.requires_book:
            books = getattr(self.owner, 'books_enabled', set())
            if spec.requires_book not in books:
                return False
        if not force and spec.cooldown_ms > 0:
            last = self._last_started.get(action_id, 0.0)
            if (time.monotonic() - last) * 1000.0 < spec.cooldown_ms:
                return False
        if action_id in self.overlays:
            return False
        channels = set(spec.channels)
        for other_id in self.overlays:
            other = get_action(other_id)
            if other and channels.intersection(other.channels):
                return False
        self.overlays[action_id] = {'started': time.monotonic()}
        self._last_started[action_id] = time.monotonic()
        return True

    def play_overlay(self, action_id, force=False, **kwargs):
        if not self.enter_overlay(action_id, force=force):
            return False
        handler_name = get_action(action_id).handler
        if handler_name:
            handler = getattr(self.owner, handler_name, None)
            if callable(handler):
                handler(**kwargs)
        return True

    def finish_overlay(self, action_id=None):
        if action_id is None:
            self.overlays.clear()
            return
        self.overlays.pop(action_id, None)

    def _prune_overlays(self, state_id):
        for action_id in tuple(self.overlays):
            spec = get_action(action_id)
            if spec and spec.allowed_from and state_id not in spec.allowed_from:
                self.overlays.pop(action_id, None)

    def cancel_overlays(self, allowed=()):
        allowed = set(allowed)
        for action_id in tuple(self.overlays):
            if action_id not in allowed:
                self.overlays.pop(action_id, None)

    def set_expression(self, owner, expression, priority=None):
        self._expressions = [
            item for item in self._expressions if item[0] != owner]
        if expression is not None:
            spec = get_action(owner)
            value = spec.priority if spec and priority is None else int(priority or 0)
            self._expressions.append((owner, expression, value))
            self._expressions.sort(key=lambda item: item[2])

    def clear_expression(self, owner):
        self._expressions = [
            item for item in self._expressions if item[0] != owner]

    @property
    def expression(self):
        return self._expressions[-1][1] if self._expressions else None

    def snapshot(self):
        return {
            'current': self.current,
            'phase': self.phase,
            'overlays': tuple(self.overlays),
            'expression': self.expression,
        }

    def reset(self, state='idle'):
        self.current = state
        self.phase = None
        self.overlays.clear()
        self._expressions.clear()

    def play(self, action_id, phase=None, force=False, **kwargs):
        if not self.enter(action_id, phase=phase, force=force):
            return False
        handler_name = get_action(action_id).handler
        if handler_name:
            handler = getattr(self.owner, handler_name, None)
            if callable(handler):
                handler(**kwargs)
        return True
