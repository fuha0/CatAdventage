# -*- coding: utf-8 -*-
"""工作站窗口：与仓库同构的三栏页面，标签页按特别事件解锁。

布局与仓库一致（左=成就选择+模特预览+数值详情，中=标签内容，右=详情栏），
窗口之间互斥，复用 WarehouseMixin / AchievementMixin 提供的公共构件。
"""
import random
import tkinter as tk

from services import InventoryService
from special_events import has_special_event
from stats import StatsService
from ui_theme import (
    THEME, FONT_FAMILY, configure_theme, make_button, make_label, make_card)

WORKSTATION_WIDTH = 1200
WORKSTATION_HEIGHT = 620
# 右栏（详情/配方栏）宽度：**逻辑像素**，配置时统一走 dp()。
# 炼药页的配方卡片需要更宽的地方放描述，所以比仓库的 280 宽一档，
# 多出来的宽度是从中间的材料栏那里让出来的（中间栏会相应变窄）。
WORKSTATION_DETAIL_WIDTH = 340
WORKSTATION_BANNER_TEXTS = (
    '开工啦！', '研习中…', '配方记下了！', '需要什么材料？')

# 没有任何标签页解锁时，中间栏的提示语。
WORKSTATION_LOCKED_TEXT = '尚未解锁工作站内容哦~'

# 炼药页：炼金等级条的颜色（与活力/情绪/经验条区分开）。
ALCHEMY_BAR_COLOR = '#A06CD5'
# 炼药页布景里椅子的落脚点（预览帧 328×328 内的像素坐标：脚底中心 x、脚底 y）。
# 对应 Alchemy.png 里炼金锅右下角的那张木凳，猫站在凳面上。
ALCHEMY_PREVIEW_ANCHOR = (206, 197)
# 炼药页布景里的凳子比默认站位小，模特相应缩一点，免得整个人盖住炼金锅。
ALCHEMY_PREVIEW_CAT_SIZE = 115
# 解锁炼药页需要的物品：「炼药锅」（「一份契约」信件的附件）。
ALCHEMY_POT_ITEM = 'alchemy_pot'

# 标签页定义。解锁条件二选一（unlock_item 优先）：
#   unlock_item  —— 仓库里拥有该键名的物品（>0）即解锁；
#   unlock_event —— 特别事件编号进入存档 special_events 集合即永久解锁。
# background / preview_anchor 用于把左栏的模特摆进该页专属布景。
WORKSTATION_TABS = (
    {
        'key': 'alchemy',
        'label': '炼药',
        # 解锁条件：拥有「炼药锅」——由「一份契约」信件的附件领取获得。
        'unlock_item': ALCHEMY_POT_ITEM,
        'background': 'alchemy',
        'preview_anchor': ALCHEMY_PREVIEW_ANCHOR,
        'preview_cat_size': ALCHEMY_PREVIEW_CAT_SIZE,
        'detail_hint': '把材料倒进炼金锅，就能积累炼金经验。',
    },
)


def workstation_tab(key):
    """按键取标签定义，找不到返回 None。"""
    return next((tab for tab in WORKSTATION_TABS if tab['key'] == key), None)


class WorkstationMixin:
    def show_workstation(self):
        """工作站：三栏结构，标签页按特别事件解锁。"""
        if self.adventuring or self.hospitalized:
            return
        if (self._workstation_win is not None
                and self._workstation_win.winfo_exists()):
            banner = getattr(self, '_workstation_banner_label', None)
            if banner is not None:
                banner.config(text=random.choice(WORKSTATION_BANNER_TEXTS))
            self._workstation_win.lift()
            self._refresh_workstation()
            return
        # 与仓库/探险互斥：三者共用预览、数值条、成就选择器等构件。
        if not self.close_warehouse():
            return
        close_adventure = getattr(self, 'close_adventure', None)
        if close_adventure is not None:
            close_adventure()

        win = tk.Toplevel(self.root)
        win.title('工作站')
        win.resizable(False, False)
        # 工作站是「页面」，留在任务栏里方便切回来（子弹窗仍然隐藏）。
        self._show_in_taskbar(win)
        win.after(80, lambda w=win: self._show_in_taskbar(w))
        configure_theme(win)
        win.geometry(f'{dp(WORKSTATION_WIDTH)}x{dp(WORKSTATION_HEIGHT)}')
        self._workstation_win = win

        # 预览用「当前实装」而不是仓库的待确认方案。
        self._preview_source = 'live'
        self._preview_pose = 'normal'
        self._preview_tail_tilt = 0.0
        self._preview_bounce_scale = (1.0, 1.0)
        self._preview_bounce_job = None
        self._preview_background_key = None
        self._preview_anchor = None
        self._preview_cat_size = None
        self._background_cache = {}
        self._workstation_tab = None
        self._workstation_tabbar = None
        self._workstation_tab_buttons = {}
        # 炼药页状态：每个材料的待倒数量、上次倒入的结果提示、控件引用。
        self._alchemy_qty = {}
        self._alchemy_status = ''
        self._alchemy_spins = {}
        self._alchemy_canvas = None
        self._alchemy_level_label = None
        self._alchemy_ratio_label = None
        self._alchemy_bar_width = dp(220)

        page_bg = THEME['bg']
        win.configure(bg=page_bg)

        # 底部：金币 + 页面互跳 + 关闭
        bottom = tk.Frame(win, bg=page_bg)
        bottom.pack(side='bottom', fill='x', padx=18, pady=(0, 14))
        self._workstation_text = make_label(bottom, '', bg=page_bg)
        self._workstation_text.pack(side='left')
        make_button(bottom, '仓库', self._switch_workstation_to_warehouse,
                    kind='secondary', width=7).pack(side='left', padx=(10, 0))
        make_button(bottom, '集市', self._switch_workstation_to_market,
                    kind='secondary', width=7).pack(side='left', padx=(6, 0))
        make_button(bottom, '探险', self._switch_workstation_to_adventure,
                    kind='secondary', width=7).pack(side='left', padx=(6, 0))
        make_button(bottom, '总览', self._show_overview, kind='secondary',
                    width=7).pack(side='left', padx=(6, 0))
        make_button(bottom, '关闭', self.close_workstation, kind='primary',
                    width=14, height=2,
                    font=(FONT_FAMILY, 11)).pack(side='right')

        # 顶部：标题 + 标签栏（右对齐，只显示已解锁标签）
        tabbar = tk.Frame(win, bg=page_bg)
        tabbar.pack(side='top', fill='x', padx=18, pady=(14, 0))
        self._workstation_title_label = make_label(
            tabbar, f"{self.cat_name or '猫猫'}的工作站", style='title',
            bg=page_bg)
        self._workstation_title_label.pack(side='left', anchor='center')
        self._workstation_banner_label = make_label(
            tabbar, random.choice(WORKSTATION_BANNER_TEXTS), bg=page_bg,
            fg=THEME['accent_hover'], font=(FONT_FAMILY, 13, 'bold'))
        self._workstation_banner_label.pack(
            side='left', anchor='center', padx=(18, 0))
        self._build_workstation_tabbar(tabbar)

        # 内容：左=模特/数值，中=标签内容，右=详情
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
        self._equip_preview_label.bind(
            '<Motion>', self._equip_preview_motion)
        self._equip_preview_label.bind(
            '<Button-1>', self._preview_click_bounce)
        self._equip_stats_label = make_label(
            left_wrap, '', bg=THEME['card'], fg=THEME['muted'],
            style='small')
        self._equip_stats_label.pack(pady=(10, 0))
        self._build_vitals_widgets(left_wrap, THEME['card'])

        self._warehouse_detail_card = make_card(content, bg=THEME['card'])
        # 走 dp()：Tk 坐标是物理像素，不缩放的话高 DPI 下这一栏会显得极窄。
        self._warehouse_detail_card.configure(
            width=dp(WORKSTATION_DETAIL_WIDTH))
        self._warehouse_detail_card.pack(side='right', fill='y', padx=(12, 0))
        self._warehouse_detail_card.pack_propagate(False)
        self._warehouse_detail_content = tk.Frame(
            self._warehouse_detail_card, bg=THEME['card'])
        self._warehouse_detail_content.pack(fill='both', expand=True)
        self._warehouse_detail_job = None
        self._warehouse_detail_hide_job = None
        self._pinned_warehouse_detail = None

        right_col = make_card(content, bg=THEME['card'])
        right_col.pack(side='right', fill='both', expand=True)
        self._workstation_body = tk.Frame(right_col, bg=THEME['card'])
        self._workstation_body.pack(fill='both', expand=True, padx=14, pady=14)

        win.bind('<Motion>', self._equip_preview_motion)
        win.protocol('WM_DELETE_WINDOW', self.close_workstation)
        self._select_workstation_tab(self._default_workstation_tab())
        self._start_preview_actions()

    # ---------- 标签页 ----------

    def _workstation_unlocked_tabs(self):
        """返回当前已解锁的标签定义列表（按定义顺序）。

        解锁条件：有 unlock_item 就看仓库里有没有这件物品（拥有即解锁），
        否则回落到 unlock_event（特别事件是否触发过）。
        """
        unlocked = []
        for tab in WORKSTATION_TABS:
            item_id = tab.get('unlock_item')
            if item_id:
                if InventoryService.count(self.inventory, item_id) > 0:
                    unlocked.append(tab)
                continue
            if has_special_event(self.game, tab.get('unlock_event')):
                unlocked.append(tab)
        return unlocked

    def _default_workstation_tab(self):
        tabs = self._workstation_unlocked_tabs()
        return tabs[0]['key'] if tabs else None

    def _build_workstation_tabbar(self, tabbar):
        """按解锁状态重建标签按钮（未解锁的直接不显示）。"""
        self._workstation_tabbar = tabbar
        self._workstation_tab_buttons = {}
        for tab in reversed(self._workstation_unlocked_tabs()):
            btn = make_button(
                tabbar, tab['label'],
                lambda k=tab['key']: self._select_workstation_tab(k),
                kind='tab', width=7)
            btn.pack(side='right', padx=3)
            self._workstation_tab_buttons[tab['key']] = btn
        self._sync_workstation_tab_styles()

    def _rebuild_workstation_tabbar(self):
        """解锁状态可能变化（例如开着工作站时凑够了力量），对不上就重建。"""
        tabbar = getattr(self, '_workstation_tabbar', None)
        if tabbar is None or not tabbar.winfo_exists():
            return
        wanted = {tab['key'] for tab in self._workstation_unlocked_tabs()}
        if set(getattr(self, '_workstation_tab_buttons', {})) == wanted:
            return
        for btn in getattr(self, '_workstation_tab_buttons', {}).values():
            try:
                btn.destroy()
            except Exception:
                pass
        self._build_workstation_tabbar(tabbar)
        if getattr(self, '_workstation_tab', None) not in wanted:
            self._workstation_tab = (
                self._default_workstation_tab())
            self._apply_workstation_tab_visuals(self._workstation_tab)

    def _sync_workstation_tab_styles(self):
        selected_key = getattr(self, '_workstation_tab', None)
        for key, btn in getattr(self, '_workstation_tab_buttons', {}).items():
            try:
                selected = key == selected_key
                btn.config(
                    bg=THEME['tab_selected'] if selected else THEME['tab_bg'],
                    fg=THEME['accent_text'] if selected else THEME['text'])
            except Exception:
                pass

    def _apply_workstation_tab_visuals(self, key):
        """按当前标签切换模特布景、站位与显示尺寸（炼药页用炼金间布景）。"""
        tab = workstation_tab(key) or {}
        self._preview_background_key = tab.get('background')
        self._preview_anchor = tab.get('preview_anchor')
        self._preview_cat_size = tab.get('preview_cat_size')

    def _select_workstation_tab(self, key):
        keys = [tab['key'] for tab in self._workstation_unlocked_tabs()]
        if key not in keys:
            key = keys[0] if keys else None
        self._workstation_tab = key
        self._alchemy_status = ''
        self._apply_workstation_tab_visuals(key)
        self._sync_workstation_tab_styles()
        self._refresh_workstation()

    # ---------- 刷新 ----------

    def _refresh_workstation(self):
        """刷新金币、三条数值、模特预览、成就栏与标签内容。"""
        if (getattr(self, '_workstation_win', None) is None
                or not self._workstation_win.winfo_exists()):
            return
        self._rebuild_workstation_tabbar()
        text = f'金币：{self.gold} G'
        if self.adventuring:
            text += '（探险中…）'
        try:
            self._workstation_text.config(text=text)
        except Exception:
            pass
        self._refresh_hp_bar()
        self._refresh_emotion_bar()
        self._refresh_exp_bar()
        self._equip_preview_update()
        self._refresh_achievement_ui()
        self._refresh_workstation_body()
        self._show_workstation_detail_placeholder()

    def _refresh_workstation_body(self):
        """重建中间栏：无解锁标签显示提示语，否则显示标签内容。"""
        body = getattr(self, '_workstation_body', None)
        if body is None or not body.winfo_exists():
            return
        for child in body.winfo_children():
            child.destroy()
        self._alchemy_canvas = None
        self._alchemy_level_label = None
        self._alchemy_ratio_label = None
        self._alchemy_spins = {}
        bg = THEME['card']
        tab = workstation_tab(getattr(self, '_workstation_tab', None))
        if tab is None:
            make_label(body, WORKSTATION_LOCKED_TEXT, bg=bg,
                       fg=THEME['muted'],
                       font=(FONT_FAMILY, 13, 'bold')).pack(expand=True)
            return
        builder = {'alchemy': self._build_alchemy_body}.get(tab['key'])
        if builder is not None:
            builder(body, bg)
            return
        make_label(body, tab['label'], bg=bg, fg=THEME['text'],
                   font=(FONT_FAMILY, 12, 'bold')).pack(anchor='w')
        make_label(body, tab.get('body_text', '功能开发中…'), bg=bg,
                   fg=THEME['text'],
                   font=(FONT_FAMILY, 11)).pack(anchor='w', pady=(10, 0))
        hint = tab.get('body_hint')
        if hint:
            make_label(body, hint, bg=bg, fg=THEME['muted'],
                       font=(FONT_FAMILY, 9), justify='left',
                       wraplength=dp(380)).pack(anchor='w', pady=(8, 0))

    # ---------- 炼药页 ----------

    def _build_alchemy_body(self, body, bg):
        """炼药页：炼金等级条 + 可倒入的材料列表 + 结果提示。"""
        make_label(body, '炼药', bg=bg, fg=THEME['text'],
                   font=(FONT_FAMILY, 12, 'bold')).pack(anchor='w')
        self._build_alchemy_level_bar(body, bg)
        make_label(body, '把材料倒进炼金锅就能积累炼金经验，经验够了自动提升炼金等级，'
                         '升级会解锁右边的配方。',
                   bg=bg, fg=THEME['muted'], font=(FONT_FAMILY, 9),
                   justify='left', wraplength=dp(440)).pack(anchor='w', pady=(4, 8))
        material_box = tk.Frame(body, bg=bg)
        material_box.pack(fill='both', expand=True, anchor='w')
        found = False
        for key, exp in ALCHEMY_MATERIALS:
            info = ITEMS.get(key) or {}
            count = int(self.inventory.get(key, 0) or 0)
            if count <= 0:
                continue
            found = True
            self._build_alchemy_material_row(
                material_box, key, info, count, exp, bg)
        if not found:
            make_label(material_box, '背包里没有可以倒入的材料，先去探险采一些吧。',
                       bg=bg, fg=THEME['muted'],
                       font=(FONT_FAMILY, 10)).pack(anchor='w', pady=(4, 0))
        self._alchemy_status_label = make_label(
            body, getattr(self, '_alchemy_status', ''), bg=bg,
            fg=THEME['accent_hover'], font=(FONT_FAMILY, 10),
            justify='left', wraplength=dp(440), anchor='w')
        self._alchemy_status_label.pack(anchor='w', pady=(10, 0))

    def _build_alchemy_level_bar(self, parent, bg):
        row = tk.Frame(parent, bg=bg)
        row.pack(anchor='w', pady=(6, 0))
        self._alchemy_level_label = make_label(
            row, '', bg=bg, fg=THEME['text'], width=9, anchor='w',
            font=(FONT_FAMILY, 10, 'bold'))
        self._alchemy_level_label.pack(side='left')
        self._alchemy_canvas = tk.Canvas(
            row, width=self._alchemy_bar_width + 2, height=14,
            bg=THEME['card_alt'], highlightthickness=1,
            highlightbackground=THEME['border'])
        self._alchemy_canvas.pack(side='left', padx=(6, 0))
        self._alchemy_ratio_label = make_label(
            row, '', bg=bg, fg=THEME['muted'], font=(FONT_FAMILY, 9))
        self._alchemy_ratio_label.pack(side='left', padx=(8, 0))
        self._refresh_alchemy_bar()

    def _refresh_alchemy_bar(self):
        """刷新炼金等级条：紫底当前经验 + 灰底空槽。"""
        canvas = getattr(self, '_alchemy_canvas', None)
        if canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                return
        except Exception:
            return
        level = max(1, int(getattr(self.game, 'alchemy_level', 1) or 1))
        exp = max(0, int(getattr(self.game, 'alchemy_exp', 0) or 0))
        need = max(1, alchemy_xp_to_next(level))
        ratio = max(0.0, min(1.0, exp / float(need)))
        bar_width = max(40, int(getattr(self, '_alchemy_bar_width', 220)))
        right = bar_width + 1
        width = int(bar_width * ratio)
        canvas.delete('all')
        canvas.create_rectangle(1, 1, right, 13,
                                fill=THEME['card_alt'], outline='')
        if width > 0:
            canvas.create_rectangle(1, 1, 1 + width, 13,
                                    fill=ALCHEMY_BAR_COLOR, outline='')
        canvas.create_rectangle(1, 1, right, 13, outline=THEME['border'])
        if getattr(self, '_alchemy_level_label', None) is not None:
            self._alchemy_level_label.config(text=f'炼金 Lv.{level}')
        if getattr(self, '_alchemy_ratio_label', None) is not None:
            # 只写进度、不带升级提示：这一行越短，中间栏的请求宽度越小，
            # 右栏（配方栏）就能让出更多位置。
            self._alchemy_ratio_label.config(text=f'{exp} / {need} 经验')

    def _build_alchemy_material_row(self, parent, key, info, count, exp, bg):
        row = make_card(parent, bg=bg)
        row.pack(fill='x', pady=2)
        make_label(row, f"{info.get('name', key)} × {count}", bg=bg,
                   fg=self._quality_color(info),
                   font=(FONT_FAMILY, 11)).pack(
                       side='left', padx=(10, 0), pady=5)
        make_label(row, f'炼金经验 +{exp} / 个', bg=bg, fg=THEME['muted'],
                   font=(FONT_FAMILY, 9)).pack(side='left', padx=(12, 0))
        make_button(row, '倒入', lambda k=key: self._pour_alchemy(k),
                    kind='primary', width=5).pack(side='right', padx=(6, 10))
        qty = int(getattr(self, '_alchemy_qty', {}).get(key, 1) or 1)
        qty = max(1, min(count, qty))
        spin = tk.Spinbox(row, from_=1, to=count, width=3, justify='center',
                          command=lambda k=key: self._on_alchemy_qty(k))
        spin.delete(0, 'end')
        spin.insert(0, str(qty))
        spin.pack(side='right', padx=(4, 0))
        self._alchemy_spins[key] = spin

    def _on_alchemy_qty(self, key):
        """记下数量框里的值，重建列表时沿用。"""
        spin = getattr(self, '_alchemy_spins', {}).get(key)
        if spin is None:
            return
        try:
            value = max(1, int(spin.get()))
        except (TypeError, ValueError):
            value = 1
        self._alchemy_qty[key] = value

    def _alchemy_gain_exp(self, amount):
        """累加炼金经验并结算升级，返回本次提升的等级数。"""
        state = self.game
        amount = int(amount)
        if amount <= 0:
            return 0
        state.alchemy_exp = (
            max(0, int(getattr(state, 'alchemy_exp', 0) or 0)) + amount)
        state.alchemy_level = max(
            1, int(getattr(state, 'alchemy_level', 1) or 1))
        levels = 0
        while True:
            need = alchemy_xp_to_next(state.alchemy_level)
            if state.alchemy_exp < need:
                break
            state.alchemy_exp -= need
            state.alchemy_level += 1
            levels += 1
        return levels

    def _pour_alchemy(self, key):
        """把选好数量的材料倒进炼金锅：扣材料、加炼金经验、按需升级。"""
        exp_per = int(ALCHEMY_MATERIAL_EXP.get(key, 0) or 0)
        if exp_per <= 0:
            return
        name = (ITEMS.get(key) or {}).get('name', key)
        spin = getattr(self, '_alchemy_spins', {}).get(key)
        try:
            want = int(spin.get()) if spin is not None else 1
        except (TypeError, ValueError):
            want = 1
        have = int(self.inventory.get(key, 0) or 0)
        if have <= 0:
            self._alchemy_status = f'背包里没有{name}了。'
            self._refresh_workstation()
            return
        count = max(1, min(want, have))
        self.inventory[key] = max(0, have - count)
        levels = self._alchemy_gain_exp(count * exp_per)
        self._alchemy_qty[key] = 1
        status = f'倒入{name} ×{count}，炼金经验 +{count * exp_per}'
        if levels:
            status += f'　炼金等级提升到 Lv.{self.game.alchemy_level}！'
        self._alchemy_status = status
        self._check_achievements()
        self._save_satiety()
        self._refresh_workstation()

    def _show_alchemy_recipes(self):
        """右栏（炼药页右边）：配方列表，按炼金等级解锁，点「合成」炼出药剂。"""
        content = getattr(self, '_warehouse_detail_content', None)
        if content is None or not content.winfo_exists():
            return
        for child in content.winfo_children():
            child.destroy()
        card = getattr(self, '_warehouse_detail_card', None)
        if card is not None:
            try:
                card.configure(
                    highlightbackground=THEME['border'],
                    highlightcolor=THEME['border'], highlightthickness=1)
            except Exception:
                pass
        bg = THEME['card']
        level = max(1, int(getattr(self.game, 'alchemy_level', 1) or 1))
        make_label(content, '配方', bg=bg, fg=THEME['muted'],
                   font=(FONT_FAMILY, 10, 'bold')).pack(
                       anchor='w', padx=12, pady=(14, 4))
        make_label(content, f'炼金 Lv.{level}：合成的消耗品会随机带一个前缀。',
                   bg=bg, fg=THEME['muted'], font=(FONT_FAMILY, 9),
                   justify='left', wraplength=dp(280)).pack(
                       anchor='w', padx=12, pady=(0, 8))
        found = False
        for recipe in ALCHEMY_RECIPES:
            found = True
            self._build_alchemy_recipe_card(content, recipe, level, bg)
        if not found:
            make_label(content, '暂时没有可用的配方。', bg=bg, fg=THEME['muted'],
                       font=(FONT_FAMILY, 9)).pack(anchor='w', padx=12)
        status = getattr(self, '_alchemy_status', '')
        if status:
            make_label(content, status, bg=bg, fg=THEME['accent_hover'],
                       font=(FONT_FAMILY, 9), justify='left', anchor='w',
                       wraplength=dp(280)).pack(
                           anchor='w', padx=12, pady=(6, 0))

    def _build_alchemy_recipe_card(self, parent, recipe, level, bg):
        """单个配方卡片：名称、材料需求与「合成」按钮。"""
        try:
            unlock_level = max(1, int(recipe.get('unlock_level', 1) or 1))
        except (TypeError, ValueError):
            unlock_level = 1
        unlocked = int(level) >= unlock_level
        card = make_card(parent, bg=bg)
        card.pack(fill='x', padx=12, pady=(0, 8))
        make_label(card, recipe.get('name', recipe.get('item', '')),
                   bg=bg, fg=THEME['text'] if unlocked else THEME['muted'],
                   font=(FONT_FAMILY, 11, 'bold')).pack(
                       anchor='w', padx=10, pady=(8, 2))
        if unlocked:
            need_text = '需要：' + recipe_materials_text(recipe, ITEMS)
        else:
            need_text = f'炼金 Lv.{unlock_level} 解锁'
        make_label(card, need_text, bg=bg,
                   fg=THEME['text'] if unlocked else THEME['muted'],
                   font=(FONT_FAMILY, 9)).pack(anchor='w', padx=10)
        # 描述直接取物品簿里这条物品的「用途」，和仓库详情栏里看到的是同一句。
        desc = recipe_desc(recipe, ITEMS)
        if desc:
            make_label(card, desc, bg=bg, fg=THEME['muted'],
                       font=(FONT_FAMILY, 9), justify='left',
                       wraplength=dp(280)).pack(
                           anchor='w', padx=10, pady=(2, 0))
        if not unlocked:
            return
        button = make_button(card, '合成', lambda r=recipe: self._craft_potion(r),
                             kind='primary', width=6)
        button.pack(anchor='w', padx=10, pady=(6, 8))
        if not self._alchemy_recipe_ready(recipe):
            try:
                button.config(state='disabled')
            except Exception:
                pass

    def _alchemy_recipe_ready(self, recipe):
        """材料是否够合成这个配方。"""
        for key, count in recipe.get('materials') or ():
            if int(self.inventory.get(key, 0) or 0) < int(count):
                return False
        return True

    def _craft_potion(self, recipe):
        """按配方合成：扣掉材料，产出一个随机前缀的消耗品。"""
        base_key = recipe.get('item')
        name = recipe.get('name', '药剂')
        if not base_key:
            return
        materials = tuple(recipe.get('materials') or ())
        need_text = '、'.join(
            f'{(ITEMS.get(key) or {}).get("name", key)}×{count}'
            for key, count in materials)
        if not self._alchemy_recipe_ready(recipe):
            self._alchemy_status = f'材料不足：炼制{name}需要{need_text}。'
            self._refresh_workstation()
            return
        for key, count in materials:
            self.inventory[key] = max(
                0, int(self.inventory.get(key, 0) or 0) - int(count))
        tier, index, prefix = roll_potion_prefix()
        if tier is None:
            self._alchemy_status = '暂时没法炼制这个配方。'
            self._refresh_workstation()
            return
        item_key = variant_key(base_key, tier['key'], index)
        info = ITEMS.get(item_key) or {}
        self.inventory[item_key] = int(
            self.inventory.get(item_key, 0) or 0) + 1
        StatsService.record_alchemy_craft(self.game)
        self._alchemy_status = (
            f'炼成{info.get("name", prefix + name)}'
            f'（{tier.get("label", "")}）！')
        self._check_achievements()
        self._save_satiety()
        self._refresh_workstation()

    def _show_workstation_detail_placeholder(self):
        """右栏：炼药页显示配方栏，其余按标签给出相应提示。"""
        tab = workstation_tab(getattr(self, '_workstation_tab', None))
        if tab is not None and tab['key'] == 'alchemy':
            self._show_alchemy_recipes()
            return
        content = getattr(self, '_warehouse_detail_content', None)
        if content is None or not content.winfo_exists():
            return
        for child in content.winfo_children():
            child.destroy()
        card = getattr(self, '_warehouse_detail_card', None)
        if card is not None:
            try:
                card.configure(
                    highlightbackground=THEME['border'],
                    highlightcolor=THEME['border'], highlightthickness=1)
            except Exception:
                pass
        if tab is None:
            title = '详情'
            hint = '解锁工作站内容后，这里会显示详细信息。'
        else:
            title = f"{tab['label']}详情"
            hint = tab.get('detail_hint', '功能开发中，敬请期待。')
        make_label(content, title, bg=THEME['card'], fg=THEME['muted'],
                   font=(FONT_FAMILY, 10, 'bold')).pack(
                       anchor='w', padx=12, pady=(14, 6))
        make_label(content, hint, bg=THEME['card'], fg=THEME['muted'],
                   font=(FONT_FAMILY, 9), justify='left',
                   wraplength=dp(240)).pack(anchor='w', padx=12)

    # ---------- 关闭 / 跳转 ----------

    def close_workstation(self):
        if getattr(self, '_workstation_win', None) is None:
            return True
        for attr in ('_warehouse_detail_job', '_warehouse_detail_hide_job'):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
                setattr(self, attr, None)
        self._stop_preview_actions()
        self._stop_preview_bounce()
        self._destroy_achievement_selector()
        try:
            self._workstation_win.destroy()
        except Exception:
            pass
        self._workstation_win = None
        self._workstation_text = None
        self._workstation_title_label = None
        self._workstation_banner_label = None
        self._workstation_body = None
        self._workstation_tabbar = None
        self._workstation_tab_buttons = {}
        self._workstation_tab = None
        self._preview_background_key = None
        self._preview_anchor = None
        self._preview_cat_size = None
        self._pinned_warehouse_detail = None
        # 炼药页控件引用一并清空，避免指向已销毁控件。
        self._alchemy_spins = {}
        self._alchemy_canvas = None
        self._alchemy_level_label = None
        self._alchemy_ratio_label = None
        self._alchemy_status_label = None
        # 与仓库/探险共用的构件，一并清空引用，避免指向已销毁控件。
        self._equip_preview_label = None
        self._equip_stats_label = None
        self._hp_canvas = None
        self._emotion_canvas = None
        self._exp_canvas = None
        self._exp_level_label = None
        self._warehouse_detail_card = None
        self._warehouse_detail_content = None
        return True

    def _switch_workstation_to_warehouse(self):
        if not self.close_workstation():
            return
        self.show_warehouse()

    def _switch_workstation_to_market(self):
        self.close_workstation()
        self.show_market()

    def _switch_workstation_to_adventure(self):
        self.close_workstation()
        self.show_adventure()


def install_runtime_globals(namespace):
    globals().update(namespace)
