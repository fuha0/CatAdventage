# -*- coding: utf-8 -*-
"""探险页面：与仓库同尺寸的独立页面。"""
import random
import tkinter as tk
import tkinter.ttk as ttk

from services import InventoryService
from services.long_adventure import region_supports_long_adventure
from ui_theme import (
    THEME, FONT_FAMILY, configure_theme, make_button, make_label, make_card)


ADVENTURE_BANNER_TEXTS = ('整装待发！', '探索新地区！', '脚步不停！')

# 探险方式：short = 短途（5~30 分钟），long = 长期（>3 天，可跨重启）。
ADVENTURE_MODE_SHORT = 'short'
ADVENTURE_MODE_LONG = 'long'
ADVENTURE_MODES = (
    (ADVENTURE_MODE_SHORT, '短途探险（分钟）'),
    (ADVENTURE_MODE_LONG, '长期冒险（天）'),
)


class AdventurePageMixin:
    def show_adventure(self):
        if (self._adventure_win is not None
                and self._adventure_win.winfo_exists()):
            banner = getattr(self, '_adventure_banner_label', None)
            if banner is not None:
                banner.config(text=random.choice(ADVENTURE_BANNER_TEXTS))
            self._adventure_win.lift()
            self._refresh_adventure_page()
            return
        if not self.close_warehouse():
            return
        close_workstation = getattr(self, 'close_workstation', None)
        if close_workstation is not None:
            close_workstation()
        win = tk.Toplevel(self.root)
        win.title('探险')
        win.resizable(False, False)
        # 探险是「页面」，留在任务栏里方便切回来（子弹窗仍然隐藏）。
        self._show_in_taskbar(win)
        win.after(80, lambda w=win: self._show_in_taskbar(w))
        win.geometry(f'{dp(960)}x{dp(620)}')
        configure_theme(win)
        page_bg = THEME['bg']
        win.configure(bg=page_bg)
        self._adventure_win = win
        self._preview_source = 'live'
        self._adventure_region_var = tk.StringVar(
            value=REGIONS['1']['name'])
        self._adventure_time_var = tk.StringVar(value='5')
        # 探险方式：短途（分钟档）或长期（天档，>3 天，重启后继续推进）。
        self._adventure_mode_var = tk.StringVar(value=ADVENTURE_MODE_SHORT)
        self._adventure_days_var = tk.StringVar(
            value=str(LONG_EXPLORE_DAYS[0]))

        bottom = tk.Frame(win, bg=page_bg)
        bottom.pack(side='bottom', fill='x', padx=18, pady=(0, 14))
        self._adventure_gold_label = make_label(
            bottom, f'金币：{self.gold} G', bg=page_bg)
        self._adventure_gold_label.pack(side='left')
        make_button(bottom, '集市', self._switch_adventure_to_market,
                    kind='secondary', width=7).pack(
                        side='left', padx=(10, 0))
        make_button(bottom, '仓库', self._switch_adventure_to_warehouse,
                    kind='secondary', width=7).pack(
                        side='left', padx=(6, 0))
        make_button(bottom, '总览', self._show_overview,
                    kind='secondary', width=7).pack(
                        side='left', padx=(6, 0))
        # 工作站索引入口（未解锁时进去会看到解锁提示）。
        workstation_cmd = getattr(self, 'show_workstation', None)
        if workstation_cmd is not None:
            make_button(bottom, '工作站', workstation_cmd,
                        kind='secondary', width=7).pack(
                            side='left', padx=(6, 0))

        header = tk.Frame(win, bg=page_bg)
        header.pack(side='top', fill='x', padx=18, pady=(14, 0))
        make_label(header, f"{self.cat_name or '猫猫'}的探险", style='title',
                   bg=page_bg).pack(side='left', anchor='center')
        self._adventure_banner_label = make_label(
            header, random.choice(ADVENTURE_BANNER_TEXTS), bg=page_bg,
            fg=THEME['accent_hover'], font=(FONT_FAMILY, 13, 'bold'))
        self._adventure_banner_label.pack(
            side='left', anchor='center', padx=(18, 0))

        content = tk.Frame(win, bg=page_bg)
        content.pack(fill='both', expand=True, padx=18, pady=(10, 6))

        left_card = make_card(content, bg=THEME['card'])
        left_card.pack(side='left', fill='y', padx=(0, 12))
        left_wrap = tk.Frame(left_card, bg=THEME['card'])
        left_wrap.pack(fill='both', expand=True, padx=14, pady=14)
        self._build_achievement_selector(left_wrap, THEME['card'])
        preview_box = make_card(left_wrap, bg=THEME['preview_bg'])
        preview_box.pack(pady=(2, 0))
        self._equip_preview_label = make_label(
            preview_box, bg=THEME['preview_bg'], cursor='hand2')
        self._equip_preview_label.pack()
        self._preview_bounce_scale = (1.0, 1.0)
        self._preview_bounce_job = None
        self._equip_preview_label.bind(
            '<Motion>', self._equip_preview_motion)
        self._equip_preview_label.bind(
            '<Button-1>', self._preview_click_bounce)
        self._equip_stats_label = make_label(
            left_wrap, '', bg=THEME['card'], fg=THEME['muted'],
            style='small')
        self._equip_stats_label.pack(pady=(10, 0))
        self._build_vitals_widgets(left_wrap, THEME['card'])

        right_card = make_card(content, bg=THEME['card'])
        right_card.pack(side='right', fill='both', expand=True)
        right_wrap = tk.Frame(right_card, bg=THEME['card'])
        right_wrap.pack(fill='both', expand=True, padx=14, pady=14)

        self._adventure_status = make_label(
            right_wrap, '', bg=THEME['card'], fg=THEME['success'],
            font=(FONT_FAMILY, 10, 'bold'))
        self._adventure_status.pack(anchor='w', pady=(0, 7))

        make_label(right_wrap, '探险日志', bg=THEME['card'],
                   font=(FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        log_wrap = make_card(right_wrap, bg=THEME['card_alt'])
        log_wrap.pack(fill='both', expand=True, pady=(4, 10))
        self._adventure_log_text = tk.Text(
            log_wrap, width=48, height=10, wrap='word',
            bg=THEME['card_alt'], fg=THEME['text'], relief='flat',
            bd=0, highlightthickness=0,
            font=(FONT_FAMILY, 9), padx=6, pady=6)
        self._adventure_log_text.pack(fill='both', expand=True, padx=5, pady=5)
        self._adventure_log_text.tag_configure(
            'success', foreground=THEME['success'])
        self._adventure_log_text.tag_configure(
            'failure', foreground=THEME['danger'])
        self._adventure_log_text.config(state='disabled')

        controls = make_card(right_wrap, bg=THEME['card_alt'])
        controls.pack(fill='x')
        controls_inner = tk.Frame(controls, bg=THEME['card_alt'])
        controls_inner.pack(fill='x', padx=12, pady=10)
        controls_inner.grid_columnconfigure(1, weight=1)

        make_label(controls_inner, '探险地区', bg=THEME['card_alt'],
                   font=(FONT_FAMILY, 10)).grid(
                       row=0, column=0, sticky='w', padx=(0, 10), pady=3)
        names = self._available_adventure_region_names()
        self._adventure_region_combo = ttk.Combobox(
            controls_inner, textvariable=self._adventure_region_var,
            values=names, state='readonly', width=20)
        self._adventure_region_combo.grid(
            row=0, column=1, sticky='ew', pady=3)
        self._adventure_region_combo.bind(
            '<<ComboboxSelected>>', self._adventure_region_changed)

        make_label(controls_inner, '探险方式', bg=THEME['card_alt'],
                   font=(FONT_FAMILY, 10)).grid(
                       row=1, column=0, sticky='w', padx=(0, 10), pady=3)
        self._adventure_mode_combo = ttk.Combobox(
            controls_inner, textvariable=self._adventure_mode_var,
            values=[label for _, label in ADVENTURE_MODES],
            state='readonly', width=20)
        self._adventure_mode_combo.grid(
            row=1, column=1, sticky='ew', pady=3)
        self._adventure_mode_combo.bind(
            '<<ComboboxSelected>>', self._adventure_mode_changed)

        # 时长：短途按分钟、长期按天，两行共用一格，切换时只显示其中一行。
        duration = tk.Frame(controls_inner, bg=THEME['card_alt'])
        duration.grid(row=2, column=0, columnspan=2, sticky='ew')
        duration.grid_columnconfigure(1, weight=1)
        self._adventure_duration_frame = duration

        self._adventure_short_row = tk.Frame(duration, bg=THEME['card_alt'])
        self._adventure_short_row.grid(
            row=0, column=0, columnspan=2, sticky='ew')
        self._adventure_short_row.grid_columnconfigure(1, weight=1)
        make_label(self._adventure_short_row, '探险时间（分钟）',
                   bg=THEME['card_alt'],
                   font=(FONT_FAMILY, 10)).grid(
                       row=0, column=0, sticky='w', padx=(0, 10), pady=3)
        self._adventure_time_combo = ttk.Combobox(
            self._adventure_short_row, textvariable=self._adventure_time_var,
            values=[str(x) for x in EXPLORE_TIMES],
            state='readonly', width=20)
        self._adventure_time_combo.grid(
            row=0, column=1, sticky='ew', pady=3)
        self._adventure_time_combo.bind(
            '<<ComboboxSelected>>', self._clear_adventure_combo_selection)

        self._adventure_long_row = tk.Frame(duration, bg=THEME['card_alt'])
        self._adventure_long_row.grid(
            row=0, column=0, columnspan=2, sticky='ew')
        self._adventure_long_row.grid_columnconfigure(1, weight=1)
        make_label(self._adventure_long_row, '长期冒险时长（天）',
                   bg=THEME['card_alt'],
                   font=(FONT_FAMILY, 10)).grid(
                       row=0, column=0, sticky='w', padx=(0, 10), pady=3)
        self._adventure_days_combo = ttk.Combobox(
            self._adventure_long_row, textvariable=self._adventure_days_var,
            values=[str(x) for x in LONG_EXPLORE_DAYS],
            state='readonly', width=20)
        self._adventure_days_combo.grid(
            row=0, column=1, sticky='ew', pady=3)
        self._adventure_days_combo.bind(
            '<<ComboboxSelected>>', self._adventure_mode_changed)
        self._adventure_long_row.grid_remove()

        self._adventure_region_desc_label = make_label(
            controls_inner, '', bg=THEME['card_alt'], fg=THEME['muted'],
            style='small', justify='left', wraplength=500)
        self._adventure_region_desc_label.grid(
            row=3, column=0, columnspan=2, sticky='w', pady=(6, 2))
        self._adventure_unlock_label = make_label(
            controls_inner, '', bg=THEME['card_alt'], fg='#8B1E1E',
            style='small', justify='left', wraplength=500)
        self._adventure_unlock_label.grid(
            row=4, column=0, columnspan=2, sticky='w', pady=(9, 0))
        self._adventure_start_button = make_button(
            controls_inner, '开始探险', self._adventure_page_start,
            kind='primary', width=14)
        self._adventure_start_button.grid(
            row=5, column=1, sticky='e', pady=(9, 0))
        make_label(
            right_wrap,
            '高级地区探险会消耗面包；探险可能会影响猫咪的活力或情绪哦！',
            bg=THEME['card'], fg=THEME['muted'], style='small',
            justify='left', wraplength=520).pack(
                anchor='w', pady=(8, 0))

        win.protocol('WM_DELETE_WINDOW', self.close_adventure)
        self._adventure_region_changed()
        self._refresh_adventure_page()
        self._start_preview_actions()

    def _available_adventure_region_keys(self):
        clear_count = int(getattr(self.game, 'stats', {}).get('forest_clear_count', 0))
        keys = []
        for key, region in REGIONS.items():
            required = int(region.get('unlock_forest_clears', 0) or 0)
            if required and clear_count < required:
                continue
            keys.append(key)
        return keys

    def _available_adventure_region_names(self):
        return [REGIONS[key]['name']
                for key in self._available_adventure_region_keys()]

    def _refresh_adventure_region_choices(self):
        combo = getattr(self, '_adventure_region_combo', None)
        if combo is None:
            return
        names = self._available_adventure_region_names()
        combo.config(values=names)
        if self._adventure_region_var.get() not in names:
            self._adventure_region_var.set(
                names[0] if names else REGIONS['1']['name'])
            self._adventure_region_changed()

    def _adventure_mode(self):
        """当前探险方式：short / long。"""
        label = self._adventure_mode_var.get()
        for key, text in ADVENTURE_MODES:
            if text == label:
                return key
        return ADVENTURE_MODE_SHORT

    def _adventure_long_days(self):
        try:
            return int(self._adventure_days_var.get())
        except (TypeError, ValueError):
            return LONG_EXPLORE_DAYS[0]

    def _adventure_mode_changed(self, event=None):
        """切换短途 / 长期：只显示对应的时长行，并刷新提示与按钮文案。"""
        if event is not None:
            self._clear_adventure_combo_selection(event)
        long_mode = self._adventure_mode() == ADVENTURE_MODE_LONG
        try:
            if long_mode:
                self._adventure_short_row.grid_remove()
                self._adventure_long_row.grid()
            else:
                self._adventure_long_row.grid_remove()
                self._adventure_short_row.grid()
        except Exception:
            pass
        try:
            self._adventure_start_button.config(
                text='开始长期冒险' if long_mode else '开始探险')
        except Exception:
            pass
        self._update_adventure_unlock_hint()

    def _region_id_from_name(self, name):
        for key, region in REGIONS.items():
            if region.get('name') == name:
                return key
        return '1'

    def _update_adventure_unlock_hint(self):
        if getattr(self, '_adventure_unlock_label', None) is None:
            return
        region_id = self._region_id_from_name(self._adventure_region_var.get())
        region = REGIONS.get(region_id, {})
        clear_count = int(getattr(self.game, 'stats', {}).get('forest_clear_count', 0))
        clear_required = int(region.get('unlock_forest_clears', 0) or 0)
        long_mode = self._adventure_mode() == ADVENTURE_MODE_LONG
        if long_mode and not region_supports_long_adventure(region):
            # 平原（不耗补给）与尚未实装的地区都开不了长期冒险。
            text = '这个地区不适合长期冒险，请选择低语森林或灰石谷。'
        elif clear_required and clear_count < clear_required:
            text = f'该地区未解锁，需要低语森林成功结算 {clear_required} 次！'
        elif long_mode and self.level < int(region.get('min_level', 1)):
            text = (f"长期冒险需要 {region.get('min_level', 1)} 级，"
                    f"当前 {self.level} 级，先练练级吧。")
        elif (not region.get('fallback', False)
              and self.level < int(region.get('min_level', 1))):
            text = (f"未达最低等级 {region.get('min_level', 1)} 级，"
                    "可以硬闯，但事件成功率仅 10%！")
        else:
            text = ''
        if long_mode and not text:
            days = self._adventure_long_days()
            cost = self._adventure_long_bread_cost(region_id, days)
            bread_count = InventoryService.count(self.inventory, 'bread')
            text = (f'长期冒险 {days} 天，补给需要面包 ×{cost}'
                    f'（现有 {bread_count} 个）；'
                    '途中会随机触发事件并寄信回来，关闭软件后进度不丢。')
        try:
            self._adventure_unlock_label.config(text=text)
            if getattr(self, '_adventure_region_desc_label', None) is not None:
                self._adventure_region_desc_label.config(
                    text=region.get('description', region.get('desc', '')))
        except Exception:
            pass

    def _adventure_long_bread_cost(self, region_id, days):
        """长期冒险的面包消耗（与桌面主进程同一口径）。"""
        region = REGIONS.get(str(region_id), {})
        try:
            per_day = max(0, int(region.get('long_bread_per_day', 2) or 0))
        except (TypeError, ValueError):
            per_day = 2
        return per_day * max(1, int(days))

    def _clear_adventure_combo_selection(self, event=None):
        combo = event.widget if event is not None else None
        if combo is None:
            return
        try:
            combo.selection_clear()
        except Exception:
            pass

    def _adventure_region_changed(self, event=None):
        try:
            self._adventure_region_combo.selection_clear()
        except Exception:
            pass
        region_id = self._region_id_from_name(
            self._adventure_region_var.get())
        self._preview_background_key = {
            '1': 'plain', '2': 'forest', '3': 'valley',
        }.get(region_id, 'market')
        self._equip_preview_update()
        allowed_times = (PLAIN_EXPLORE_TIMES if region_id == '1'
                         else EXPLORE_TIMES)
        try:
            current = int(self._adventure_time_var.get())
        except (TypeError, ValueError):
            current = 5
        if current not in allowed_times:
            self._adventure_time_var.set('5')
        try:
            self._adventure_time_combo.config(
                values=[str(x) for x in allowed_times], state='readonly')
        except Exception:
            pass
        self._update_adventure_unlock_hint()

    def _refresh_adventure_page(self):
        if (self._adventure_win is None
                or not self._adventure_win.winfo_exists()):
            return
        try:
            self._equip_preview_update()
            self._refresh_achievement_ui()
            self._refresh_hp_bar()
            self._refresh_emotion_bar()
            self._refresh_exp_bar()
            self._refresh_adventure_region_choices()
            self._update_adventure_unlock_hint()
            self._adventure_gold_label.config(
                text=f'\u91d1\u5e01\uff1a{self.gold} G')
        except Exception:
            pass
        if self.adventuring:
            plan = self._long_adventure_plan()
            if plan:
                status = (f'长期冒险中 · {self._long_adventure_progress_text()} · '
                          f'剩余约{self._long_adventure_remaining_text()}')
            else:
                status = f'探索中 · 剩余约{self._adventure_remaining_minutes()}分钟'
        else:
            status = '请选择地区和时间：'
        try:
            self._adventure_status.config(
                text=status,
                fg=THEME['accent_hover'] if self.adventuring else THEME['success'])
        except Exception:
            pass
        try:
            self._adventure_log_text.config(state='normal')
            self._adventure_log_text.delete('1.0', 'end')
            if not self.logs:
                self._adventure_log_text.insert('end', '\uff08\u8fd8\u6ca1\u6709\u63a2\u9669\u8bb0\u5f55\uff09\n')
            recent_logs = list(reversed(self.logs[-6:]))
            for index, log in enumerate(recent_logs):
                self._adventure_log_text.insert('end', log['time'] + '\n')
                for line in log['lines']:
                    marker = line.find('｜失败')
                    tag = 'failure'
                    if marker < 0:
                        marker = line.find('｜成功')
                        tag = 'success'
                    if marker >= 0:
                        state_start = marker + 1
                        self._adventure_log_text.insert(
                            'end', '  ' + line[:state_start])
                        self._adventure_log_text.insert(
                            'end', line[state_start:state_start + 2], tag)
                        self._adventure_log_text.insert(
                            'end', line[state_start + 2:] + '\n')
                    else:
                        self._adventure_log_text.insert(
                            'end', '  ' + line + '\n')
                self._adventure_log_text.insert('end', '\n')
                if index < len(recent_logs) - 1:
                    self._adventure_log_text.insert('end', '—' * 20 + '\n')
            self._adventure_log_text.config(state='disabled')
        except Exception:
            pass

    def _adventure_page_start(self):
        region_id = self._region_id_from_name(
            self._adventure_region_var.get())
        if self._adventure_mode() == ADVENTURE_MODE_LONG:
            # 直接出发，不弹确认框：补给消耗与机制已经写在页面提示里，
            # 校验不通过时由 start_long_adventure 写进探险日志。
            self.start_long_adventure(region_id, self._adventure_long_days())
            return
        try:
            minutes = int(self._adventure_time_var.get())
        except (TypeError, ValueError):
            minutes = 5
        self._confirm_adventure(region_id, minutes)

    def _switch_adventure_to_market(self):
        self.close_adventure()
        self.show_market()

    def _switch_adventure_to_warehouse(self):
        self.close_adventure()
        self.show_warehouse()

    def close_adventure(self):
        self._stop_preview_actions()
        self._destroy_achievement_selector()
        if self._adventure_win is not None:
            try:
                self._adventure_win.destroy()
            except Exception:
                pass
        self._adventure_win = None
        self._equip_preview_label = None
        self._equip_stats_label = None
        self._adventure_region_combo = None
        self._adventure_time_combo = None
        self._adventure_status = None
        self._adventure_log_text = None
        self._adventure_gold_label = None
        self._hp_canvas = None
        self._emotion_canvas = None
        self._exp_level_label = None
        self._exp_canvas = None
        self._adventure_banner_label = None
        self._preview_background_key = None
        self._adventure_unlock_label = None
        self._adventure_region_desc_label = None
        self._adventure_start_button = None
        self._adventure_mode_combo = None
        self._adventure_days_combo = None
        self._adventure_short_row = None
        self._adventure_long_row = None
        self._adventure_duration_frame = None


def install_runtime_globals(namespace):
    globals().update(namespace)
