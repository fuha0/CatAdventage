# -*- coding: utf-8 -*-
"""管理员页的存档切换与批量解锁功能。"""
import time


class AdminMixin:
    def _select_admin_tab(self, page_name):
        frame = getattr(self, '_admin_pages', {}).get(page_name)
        if frame is None:
            return
        for name, page in self._admin_pages.items():
            if name == page_name:
                page.pack(fill='both', expand=True)
            else:
                page.pack_forget()
        for name, btn in getattr(self, '_admin_tab_buttons', {}).items():
            selected = name == page_name
            btn.config(
                bg=THEME['tab_selected'] if selected else THEME['tab_bg'],
                fg=THEME['accent_text'] if selected else THEME['text'])
        self._admin_current_tab = page_name
        if page_name == '统计数据':
            self._refresh_admin_hp_label()
            self._refresh_admin_stats()
        elif page_name == '存档':
            self._refresh_admin_save_slots()

    def _refresh_admin_save_slots(self):
        frame = getattr(self, '_admin_save_list', None)
        if frame is None or not frame.winfo_exists():
            return
        for child in frame.winfo_children():
            child.destroy()
        current = int(getattr(self.save_service, 'slot_index', 0))
        for slot in range(3):
            name = self.save_service.slot_name(slot)
            row = make_card(frame, bg=THEME['card_alt'])
            row.pack(fill='x', pady=4)
            make_label(
                row, f'存档 {slot + 1}：{name}', bg=THEME['card_alt'],
                font=(FONT_FAMILY, 11, 'bold')).pack(
                    side='left', padx=12, pady=9)
            if slot == current:
                make_button(
                    row, '当前使用', kind='secondary', width=9,
                    state='disabled').pack(side='right', padx=10, pady=5)
            else:
                make_button(
                    row, '切换',
                    lambda s=slot: self._switch_admin_save_slot(s),
                    kind='primary', width=9).pack(
                        side='right', padx=10, pady=5)

    def _switch_admin_save_slot(self, slot):
        slot = max(0, min(2, int(slot)))
        if slot == int(getattr(self.save_service, 'slot_index', 0)):
            return
        if self.adventuring or self.hospitalized:
            self._alert('切换存档', '探险或住院期间无法切换存档。')
            return
        self._flush_online_time()
        self._save_satiety()
        state = self.save_service.load_slot(slot)
        self._apply_loaded_state(
            state, prompt_name=not bool(state.cat_name))
        self._refresh_admin_save_slots()

    def _apply_loaded_state(self, state, prompt_name=False):
        self.game = state
        try:
            loaded_scale = float(getattr(state, 'cat_scale', 1.0))
        except (TypeError, ValueError):
            loaded_scale = 1.0
        self.set_scale(loaded_scale)
        try:
            self.sound_volume = max(
                0, min(100, int(getattr(state, 'sound_volume', 100))))
        except (TypeError, ValueError):
            self.sound_volume = 100
        click_sound = str(getattr(state, 'click_sound', 'cat1') or 'cat1')
        if click_sound not in CLICK_SOUND_PATHS:
            click_sound = 'cat1'
        self.click_sound = click_sound
        self._active_click_sound_path = CLICK_SOUND_PATHS[click_sound]
        self.game.click_sound = click_sound
        self._click_sound_cache_key = None
        self._click_sound_paths = None
        StatsService.ensure(self.game)
        StatsService.sample_state(self.game)
        AchievementService.sync_unlocks(
            self.game, self.achievement_catalog, ITEMS)
        self._sync_expression_book_unlocks()
        self._online_session_started = time.monotonic()
        self.motion.reset('idle')
        self._treasure_uid = max(
            (int(t.get('uid', 0)) for t in self.treasures), default=0)
        self._pending_slots = {'头饰': [], '服装': None, '饰品': []}
        self._pending_clothes = 'normal'
        self._pending_equip_settings = dict(DEFAULT_EQUIPMENT_SETTINGS)
        self._pending_books_enabled = set()
        self._pending_item_uses = {}
        self._pending_click_sound = self.click_sound
        self._pending_color_changes = set()
        self._collar_color_cache.clear()
        self._earring_color_cache.clear()
        self._hat_color_cache.clear()
        self._click_expression = None
        self._forced_expression = None
        self._selected_food = None
        self._treasure_lock_mode = False
        try:
            self._stop_exp_flash(refresh=False)
        except Exception:
            pass
        self._save_satiety()
        self._refresh_panel()
        self._refresh_warehouse()
        self._refresh_market()
        self._refresh_adventure_page()
        self._refresh_admin_hp_label()
        self._refresh_admin_stats()
        self.update_image()
        if prompt_name and not self.cat_name:
            self.root.after(300, self._prompt_cat_name)

    def _admin_unlock_all_clothes(self):
        count = 0
        for item_id, info in ITEMS.items():
            if info.get('category') != '服装':
                continue
            if int(self.inventory.get(item_id, 0)) <= 0:
                count += 1
            self.inventory[item_id] = max(
                1, int(self.inventory.get(item_id, 0)))
        self._save_satiety()
        self._refresh_warehouse()
        if self._admin_settings_status is not None:
            self._admin_settings_status.config(
                text=f'已获得全部衣服，本次新增 {count} 件。')

    def _admin_unlock_all_books(self):
        count = 0
        for item_id, info in ITEMS.items():
            if info.get('category') != '书籍':
                continue
            if int(self.inventory.get(item_id, 0)) <= 0:
                count += 1
            self.inventory[item_id] = max(
                1, int(self.inventory.get(item_id, 0)))
        self._save_satiety()
        self._refresh_warehouse()
        if self._admin_settings_status is not None:
            self._admin_settings_status.config(
                text=f'已获得全部书籍，本次新增 {count} 本。')

    def _admin_unlock_all_achievements(self):
        catalog = getattr(self, 'achievement_catalog', {})
        old_count = len(self.achievements)
        self.achievements = set(catalog)
        self._sync_expression_book_unlocks()
        if self.selected_achievement not in self.achievements:
            self.selected_achievement = next(iter(catalog), None)
        self._save_satiety()
        self._refresh_warehouse()
        if self._admin_settings_status is not None:
            self._admin_settings_status.config(
                text=(
                    f'已解锁全部成就，本次新增 '
                    f'{len(self.achievements) - old_count} 个。'))


def install_runtime_globals(namespace):
    globals().update(namespace)