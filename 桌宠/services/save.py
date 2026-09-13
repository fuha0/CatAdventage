# -*- coding: utf-8 -*-
"""GameState 的统一读取、迁移和原子保存。"""
import copy
import json
import os
import re
from pathlib import Path

from .models import GameState
from .progression import ProgressionService
from stats import DEFAULT_STATS


class SaveService:
    def __init__(self, save_path, items, starting_gifts,
                 starting_bread, clothes_names, expression_book_order,
                 default_equipment_settings, hp_initial=100,
                 hp_max_initial=100, strength_initial=10,
                 wisdom_initial=10, agility_initial=10,
                 luck_initial=0, emotion_initial=50,
                 gold_initial=0):
        self.base_save_path = str(save_path)
        self.slot_count = 3
        self.active_slot_file = self.base_save_path + '.active_slot'
        self.slot_index = 0
        self._load_active_slot()
        self.save_path = self.slot_path(self.slot_index)
        self.items = dict(items)
        self.item_ids = tuple(items)
        self.starting_gifts = tuple(starting_gifts)
        self.starting_bread = int(starting_bread)
        self.clothes_names = set(clothes_names)
        self.expression_book_order = tuple(expression_book_order)
        self.default_equipment_settings = copy.deepcopy(default_equipment_settings)
        self.hp_initial = int(hp_initial)
        self.hp_max_initial = int(hp_max_initial)
        self.strength_initial = int(strength_initial)
        self.wisdom_initial = int(wisdom_initial)
        self.agility_initial = int(agility_initial)
        self.luck_initial = int(luck_initial)
        self.emotion_initial = int(emotion_initial)
        self.gold_initial = int(gold_initial)

    def slot_path(self, slot_index):
        slot_index = max(0, min(self.slot_count - 1, int(slot_index)))
        if slot_index == 0:
            return self.base_save_path
        path = Path(self.base_save_path)
        return str(path.with_name(
            f'{path.stem}.slot{slot_index + 1}{path.suffix}'))

    def _load_active_slot(self):
        try:
            value = Path(self.active_slot_file).read_text(encoding='utf-8')
            self.slot_index = max(0, min(self.slot_count - 1, int(value.strip())))
        except Exception:
            self.slot_index = 0

    def set_slot(self, slot_index):
        self.slot_index = max(0, min(self.slot_count - 1, int(slot_index)))
        self.save_path = self.slot_path(self.slot_index)
        try:
            Path(self.active_slot_file).write_text(
                str(self.slot_index), encoding='utf-8')
        except Exception:
            pass

    def slot_name(self, slot_index):
        path = Path(self.slot_path(slot_index))
        if not path.exists():
            return '空存档'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            name = str(data.get('cat_name') or '').strip()
            return name[:12] if name else '未命名'
        except Exception:
            return '损坏存档'

    def load_slot(self, slot_index):
        self.set_slot(slot_index)
        return self.load()

    def new_state(self):
        state = GameState(strength=self.strength_initial,
                          wisdom=self.wisdom_initial,
                          agility=self.agility_initial,
                          luck=self.luck_initial,
                          emotion=self.emotion_initial,
                          gold=self.gold_initial)
        state.max_hp = ProgressionService.calculate_max_hp(
            state.level, state.strength, state.wisdom, state.agility)
        state.hp = state.max_hp
        state.inventory = {iid: 0 for iid in self.item_ids}
        state.inventory['bread'] = self.starting_bread
        for iid in self.starting_gifts:
            state.inventory[iid] = max(1, state.inventory.get(iid, 0))
        state.equipped_slots = self._clean_slots({})
        state.equipment_settings = copy.deepcopy(self.default_equipment_settings)
        state.stats = copy.deepcopy(DEFAULT_STATS)
        state.books_enabled = {'expression_happy'}
        state.achievements = {'dummy'}
        state.selected_achievement = 'dummy'
        return state

    def load(self):
        if not os.path.exists(self.save_path):
            return self.new_state()
        try:
            with open(self.save_path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                return self.new_state()
        except Exception:
            return self.new_state()
        state = GameState()
        state.gold = self._int_value(data, 'gold', 0)
        state.level = max(1, self._int_value(data, 'level', 1))
        state.exp = self._int_value(data, 'exp', 0)
        state.strength = self._int_value(data, 'strength', self.strength_initial)
        state.wisdom = self._int_value(data, 'wisdom', self.wisdom_initial)
        state.agility = self._int_value(data, 'agility', self.agility_initial)
        state.luck = self._int_value(data, 'luck', self.luck_initial, allow_negative=True)
        state.skill_points = self._int_value(data, 'skill_points', 0)
        state.emotion = max(0, min(100, self._int_value(data, 'emotion', self.emotion_initial)))
        raw_hp = self._int_value(data, 'hp', self.hp_initial)
        saved_max = max(1, self._int_value(data, 'max_hp', self.hp_max_initial))
        state.max_hp = ProgressionService.calculate_max_hp(
            state.level, state.strength, state.wisdom, state.agility)
        hp_ratio = max(0.0, min(1.0, raw_hp / saved_max))
        state.hp = max(0, min(state.max_hp, round(state.max_hp * hp_ratio)))
        state.inventory = self._clean_inventory(data.get('inventory', {}), first_time=False)
        state.treasures = self._clean_treasures(data.get('treasures', []))
        state.logs = self._clean_logs(data.get('logs', []))
        state.equipped_slots = self._clean_slots(data.get('equipped_slots', {}))
        state.equipment_settings = self._clean_equipment_settings(data.get('equipment_settings', {}))
        state.equipped_clothes = self._clean_clothes(data.get('clothes'))
        state.books_enabled = self._clean_books(data.get('books_enabled', []))
        state.hair_style = self._clean_hair_style(data.get('hair_style'))
        state.hair_color = self._clean_color(data.get('hair_color'))
        state.normal_clothes_color = self._clean_color(data.get('normal_clothes_color'))
        state.eye_color = self._clean_color(data.get('eye_color'))
        state.cat_name = str(data.get('cat_name') or '').strip()[:12]
        state.stats = self._clean_stats(data.get('stats', {}))
        state.achievements = self._clean_achievements(data.get('achievements', []))
        selected = str(data.get('selected_achievement') or '').strip()
        state.selected_achievement = selected or None
        state.backgrounds = self._clean_backgrounds(data.get('backgrounds'))
        if state.stats.get('forest_adventure_count', 0) > 0:
            state.backgrounds.add('forest')
        if (state.stats.get('adventure_count', 0)
                > state.stats.get('forest_adventure_count', 0)):
            state.backgrounds.add('plain')
        selected_bg = str(data.get('selected_background') or 'market').strip()
        state.selected_background = (selected_bg
                                     if selected_bg in state.backgrounds
                                     else 'market')
        try:
            state.cat_scale = max(
                0.5, min(1.5, float(data.get('cat_scale', 1.0))))
        except (TypeError, ValueError):
            state.cat_scale = 1.0
        state.sound_volume = max(
            0, min(100, self._int_value(data, 'sound_volume', 100)))
        click_sound = str(data.get('click_sound') or 'cat1').strip()
        state.click_sound = click_sound if click_sound in (
            'cat1', 'cat2', 'cat3', 'silent') else 'cat1'
        return state

    def save(self, state):
        if not isinstance(state, GameState):
            raise TypeError('SaveService.save 需要 GameState')
        payload = {
            'gold': int(state.gold), 'inventory': dict(state.inventory),
            'treasures': copy.deepcopy(state.treasures), 'hp': int(state.hp),
            'max_hp': int(state.max_hp), 'strength': int(state.strength),
            'wisdom': int(state.wisdom), 'luck': int(state.luck),
            'agility': int(state.agility), 'level': int(state.level),
            'exp': int(state.exp), 'skill_points': int(state.skill_points),
            'emotion': int(state.emotion), 'logs': copy.deepcopy(state.logs),
            'equipped_slots': copy.deepcopy(state.equipped_slots),
            'equipment_settings': copy.deepcopy(state.equipment_settings),
            'clothes': state.equipped_clothes,
            'books_enabled': sorted(state.books_enabled),
            'hair_style': state.hair_style, 'hair_color': state.hair_color,
            'normal_clothes_color': state.normal_clothes_color,
            'eye_color': state.eye_color, 'cat_name': state.cat_name,
            'stats': copy.deepcopy(state.stats),
            'achievements': sorted(state.achievements),
            'selected_achievement': state.selected_achievement,
            'backgrounds': sorted(state.backgrounds),
            'selected_background': state.selected_background,
            'cat_scale': float(state.cat_scale),
            'sound_volume': int(state.sound_volume),
            'click_sound': str(state.click_sound),
        }
        target = Path(self.save_path)
        temporary = target.with_suffix(target.suffix + '.tmp')
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(temporary, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, target)
        return payload

    def _clean_inventory(self, raw, first_time=False):
        values = raw if isinstance(raw, dict) else {}
        result = {}
        for iid in self.item_ids:
            try:
                result[iid] = max(0, int(values.get(iid, 0)))
            except (TypeError, ValueError):
                result[iid] = 0
        if first_time:
            result['bread'] = self.starting_bread
        for iid in self.item_ids:
            info = self.items.get(iid) or {}
            if info.get('category') in ('\u5934\u9970', '\u670d\u88c5', '\u9970\u54c1', '\u4e66\u7c4d'):
                result[iid] = min(1, result.get(iid, 0))
        for iid in self.starting_gifts:
            result[iid] = max(1, result.get(iid, 0))
        return result

    @staticmethod
    def _clean_backgrounds(raw):
        valid = {'market', 'plain', 'forest', 'valley'}
        if not isinstance(raw, (list, tuple, set)):
            return {'market'}
        result = {str(value).strip() for value in raw
                  if str(value).strip() in valid}
        result.add('market')
        return result

    @staticmethod
    def _clean_stats(raw):
        values = raw if isinstance(raw, dict) else {}
        result = {}
        for key in (
                'gold_earned', 'purchase_count', 'cat_click_count',
                'online_seconds', 'gold_zero_seen', 'emotion_max',
                'emotion_min', 'emotion_exact10', 'hp_min',
                'adventure_early_fail_count', 'treasure_sold_count',
                'adventure_count', 'forest_adventure_count',
                'plain_adventure_count', 'valley_adventure_count',
                'forest_clear_count',
                'adventure_minutes', 'max_feed_amount',
                'mushroom_damage_count'):
            default = 50 if key in ('emotion_max', 'emotion_min') else 0
            try:
                result[key] = max(0, int(values.get(key, default)))
            except (TypeError, ValueError):
                result[key] = default
        purchased = values.get('purchased_items', {})
        result['purchased_items'] = {}
        if isinstance(purchased, dict):
            for item_id, count in purchased.items():
                try:
                    result['purchased_items'][str(item_id)] = max(
                        0, int(count))
                except (TypeError, ValueError):
                    continue
        return result

    @staticmethod
    def _clean_achievements(raw):
        if not isinstance(raw, (list, tuple, set)):
            return set()
        return {str(value).strip() for value in raw if str(value).strip()}

    @staticmethod
    def _int_value(data, key, default, allow_negative=False):
        try:
            value = int(data.get(key, default))
            return value if allow_negative else max(0, value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clean_treasures(raw):
        if not isinstance(raw, list):
            return []
        result = []
        used = set()
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                continue
            name = str(item.get('name', '')).strip()
            prefix = str(item.get('prefix', '')).strip()
            if not name:
                continue
            try:
                quality = max(1, min(6, int(item.get('quality', 1))))
                base_value = max(1, int(item.get('base_value', 1)))
                value = max(1, int(item.get('value', base_value)))
                uid = int(item.get('uid', index))
            except (TypeError, ValueError):
                continue
            if uid <= 0 or uid in used:
                uid = max(used, default=0) + 1
            used.add(uid)
            result.append({'uid': uid, 'name': name, 'prefix': prefix,
                           'quality': quality, 'base_value': base_value,
                           'value': value,
                           'locked': bool(item.get('locked', False))})
        return result

    @staticmethod
    def _clean_logs(raw):
        return raw[-20:] if isinstance(raw, list) else []

    def _clean_slots(self, raw):
        default = {'头饰': [], '服装': None, '饰品': []}
        if not isinstance(raw, dict):
            return default
        slots = dict(raw)
        if '武器' in slots and '头饰' not in slots:
            slots['头饰'] = slots.get('武器')

        def clean_items(value, category):
            if isinstance(value, str):
                values = [value]
            elif isinstance(value, (list, tuple)):
                values = value
            else:
                return []
            result = []
            used_attrs = set()
            for iid in values:
                if not isinstance(iid, str):
                    continue
                info = self.items.get(iid, {})
                if info.get('category') != category or iid in result:
                    continue
                attr = info.get('hidden_attribute')
                if attr and attr in used_attrs:
                    continue
                result.append(iid)
                if attr:
                    used_attrs.add(attr)
            return result

        default['头饰'] = clean_items(slots.get('头饰'), '头饰')
        used_attrs = {self.items.get(iid, {}).get('hidden_attribute')
                      for iid in default['头饰']}
        used_attrs.discard(None)
        accessories = clean_items(slots.get('饰品'), '饰品')
        default['饰品'] = [iid for iid in accessories
                           if self.items.get(iid, {}).get('hidden_attribute')
                           not in used_attrs]
        clothes = slots.get('服装')
        default['服装'] = clothes if isinstance(clothes, str) else None
        return default

    def _clean_clothes(self, value):
        if value == 'hefu':
            value = 'hefu_blue'
        return value if value in self.clothes_names else 'normal'

    def _clean_books(self, raw):
        raw_values = raw if isinstance(raw, (list, tuple, set)) else ()
        result = {str(book) for book in raw_values}
        for iid in self.expression_book_order:
            result.discard(iid)
        chosen = next((iid for iid in self.expression_book_order
                       if iid in raw_values), None)
        result.add(chosen or 'expression_happy')
        return result

    @staticmethod
    def _clean_hair_style(value):
        if value == 'hair1_1':
            value = 'hair_1_1'
        return value if value in ('hair_1', 'hair_1_1') else 'hair_1'

    @staticmethod
    def _clean_color(value):
        if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            return value
        return None

    def _clean_equipment_settings(self, raw):
        settings = copy.deepcopy(self.default_equipment_settings)
        if not isinstance(raw, dict):
            return settings
        try:
            settings['sunglasses_y_offset'] = max(
                0, min(360, int(raw.get('sunglasses_y_offset',
                    settings['sunglasses_y_offset']))))
        except (TypeError, ValueError, KeyError):
            pass
        try:
            settings['collar_style'] = 2 if int(raw.get('collar_style', 1)) == 2 else 1
        except (TypeError, ValueError):
            pass
        try:
            settings['hat_ji_scale'] = max(
                0.25, min(1.5, float(raw.get(
                    'hat_ji_scale', settings.get('hat_ji_scale', 0.65)))))
        except (TypeError, ValueError):
            pass
        for key in ('earrings_color', 'hat_1_color', 'hat_ji_color',
                    'hat_2_brown_color', 'hat_2_cream_color',
                    'collar_rope_color', 'collar_deco_color'):
            value = raw.get(key)
            if isinstance(value, str) and re.fullmatch(
                    r'#[0-9a-fA-F]{6}', value):
                settings[key] = value
        return settings
