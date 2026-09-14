# -*- coding: utf-8 -*-
"""WarehouseMixin 独立模块。"""
import random

from letters import (
    LETTERS, attachment_claimed, claim_letter_attachments, get_letter,
    is_known_letter, letter_contents, letter_number, letter_attachments)
from services import MarketService, InventoryService
from stats import StatsService
from ui_theme import THEME, FONT_FAMILY, FONT_SMALL, configure_theme, make_button, make_label, make_card

ADJUSTABLE_EQUIPMENT = {
    'sunglasses', 'gold_earrings', 'hat_1', 'hat_ji', 'hat_2',
    'fine_collar',
}
PREVIEW_FRAME_SIZE = 328
PREVIEW_CAT_SIZE = 160
PREVIEW_CAT_BOTTOM_MARGIN = 28
WAREHOUSE_WIDTH = 1200
WAREHOUSE_EQUIP_WIDTH = 1120
WAREHOUSE_HEIGHT = 620
WAREHOUSE_DETAIL_WIDTH = 280
WAREHOUSE_LETTER_DETAIL_WIDTH = 520
NEW_ITEM_PAGES = ('物品', '装备')
PREVIEW_BOUNCE_FRAMES = (
    (1.12, 0.82), (0.94, 1.14), (1.05, 0.96),
    (0.98, 1.03), (1.0, 1.0),
)
WAREHOUSE_BANNER_TEXTS = ('日积月累！', '让我找找...', '吃什么好呢？', '猫咪整理中...', '正在翻找小宝贝！')


class WarehouseMixin:
    def show_warehouse(self):
        """仓库：左侧预览/圆槽常驻，右侧列表随标签变化；底部金币/经验/确定。"""
        if self.adventuring or self.hospitalized:
            return
        if (self._warehouse_win is not None
                and self._warehouse_win.winfo_exists()):
            banner = getattr(self, '_warehouse_banner_label', None)
            if banner is not None:
                banner.config(text=random.choice(WAREHOUSE_BANNER_TEXTS))
            self._warehouse_win.lift()
            self._refresh_warehouse()
            return
        # 与工作站互斥：两者共用预览、数值条、成就选择器等构件。
        close_workstation = getattr(self, 'close_workstation', None)
        if close_workstation is not None:
            close_workstation()
        win = tk.Toplevel(self.root)
        win.title('仓库')
        win.resizable(False, False)
        # 仓库是「页面」，留在任务栏里方便切回来（子弹窗仍然隐藏）。
        self._show_in_taskbar(win)
        win.after(80, lambda w=win: self._show_in_taskbar(w))
        configure_theme(win)
        win.geometry(
            f'{dp(WAREHOUSE_WIDTH)}x{dp(WAREHOUSE_HEIGHT)}')
        self._warehouse_win = win
        self._reset_pending_warehouse()
        self._preview_source = 'pending'
        self._warehouse_cat = '宝藏'
        self._food_spins = {}
        self._selected_food = None
        self._item_subpage = '食物'
        self._exp_preview_gain = 0
        self._exp_flash_on = False
        self._exp_flash_job = None
        page_bg = THEME['bg']
        self._preview_background_key = None
        # 可选：把模特钉在布景的指定位置（(脚底中心 x, 脚底 y)，帧内像素）。
        self._preview_anchor = None
        # 可选：覆盖模特的显示尺寸（帧内像素）。
        self._preview_cat_size = None
        win.configure(bg=page_bg)

        # 底部：金币 + 经验条 + 确定（右下角）
        bottom = tk.Frame(win, bg=page_bg)
        bottom.pack(side='bottom', fill='x', padx=18, pady=(0, 14))
        self._warehouse_text = make_label(bottom, '', bg=page_bg)
        self._warehouse_text.pack(side='left')
        make_button(bottom, '集市', self._switch_warehouse_to_market,
                    kind='secondary', width=7).pack(side='left', padx=(10, 0))
        make_button(bottom, '探险', self._switch_warehouse_to_adventure,
                    kind='secondary', width=7).pack(side='left', padx=(6, 0))
        make_button(bottom, '总览', self._show_overview, kind='secondary',
                    width=7).pack(side='left', padx=(6, 0))
        # 工作站索引入口（未解锁时进去会看到解锁提示）。
        workstation_cmd = getattr(self, 'show_workstation', None)
        if workstation_cmd is not None:
            make_button(bottom, '工作站', workstation_cmd, kind='secondary',
                        width=7).pack(side='left', padx=(6, 0))
        exp_row = tk.Frame(bottom, bg=page_bg)
        exp_row.pack(side='left', padx=(12, 0))
        self._exp_level_label = make_label(
            exp_row, f'Lv.{self.level}', bg=page_bg, width=4, anchor='w',
            style='small')
        self._exp_level_label.pack(side='left')
        self._exp_bar_width = 120
        self._exp_canvas = tk.Canvas(
            exp_row, width=self._exp_bar_width + 2, height=14,
            bg=THEME['card_alt'], highlightthickness=1,
            highlightbackground=THEME['border'])
        self._exp_canvas.pack(side='left', padx=(6, 0))
        self._equip_status = make_label(bottom, '', bg=page_bg,
                                        fg=THEME['success'])
        # 确定在最右，取消在它左边，提示文字再往左。
        make_button(bottom, '确定', self._confirm_equipment, kind='primary',
                    width=14, height=2,
                    font=(FONT_FAMILY, 11)).pack(side='right')
        make_button(bottom, '取消', self.close_warehouse, kind='ghost',
                    width=10, height=2).pack(side='right', padx=(0, 8))
        self._equip_status.pack(side='right', padx=10)

        # 顶部右侧：自绘标签栏（右对齐）
        tabbar = tk.Frame(win, bg=page_bg)
        tabbar.pack(side='top', fill='x', padx=18, pady=(14, 0))
        self._warehouse_title_label = make_label(
            tabbar, f"{self.cat_name or '猫猫'}的仓库", style='title', bg=page_bg)
        self._warehouse_title_label.pack(side='left', anchor='center')
        self._warehouse_banner_label = make_label(
            tabbar, random.choice(WAREHOUSE_BANNER_TEXTS), bg=page_bg,
            fg=THEME['accent_hover'], font=(FONT_FAMILY, 13, 'bold'))
        self._warehouse_banner_label.pack(
            side='left', anchor='center', padx=(18, 0))
        self._warehouse_cats = ('物品', '宝藏', '信件', '｜', '装备')
        self._warehouse_buttons = {}
        self._warehouse_tab_badges = {}
        for cat in reversed(self._warehouse_cats):
            holder = tk.Frame(tabbar, bg=page_bg)
            holder.pack(side='right', padx=3)
            if cat == '｜':
                btn = make_button(holder, '｜', kind='ghost', width=2,
                                  state='disabled', cursor='arrow')
                btn.pack()
            else:
                btn = make_button(
                    holder, cat,
                    lambda c=cat: self._select_warehouse_tab(c),
                    kind='tab', width=7)
                btn.pack()
                if cat in NEW_ITEM_PAGES:
                    badge = make_label(
                        holder, '●', bg=THEME['tab_bg'], fg=THEME['danger'],
                        font=(FONT_FAMILY, 9, 'bold'), cursor='hand2')
                    badge.bind(
                        '<Button-1>',
                        lambda e, c=cat: self._select_warehouse_tab(c))
                    badge.place_forget()
                    self._warehouse_tab_badges[cat] = badge
            self._warehouse_buttons[cat] = btn

        # 内容：左=预览方框，中=圆槽，右=动态列表
        content = tk.Frame(win, bg=page_bg)
        content.pack(fill='both', expand=True, padx=18, pady=(10, 6))
        left_card = make_card(content, bg=THEME['card'])
        left_card.pack(side='left', fill='y', padx=(0, 12))
        wrap = tk.Frame(left_card, bg=THEME['card'])
        wrap.pack(fill='both', expand=True, padx=14, pady=14)
        self._build_achievement_selector(wrap, THEME['card'])
        self._background_cache = {}
        preview_row = tk.Frame(wrap, bg=THEME['card'])
        preview_row.pack(pady=(2, 0))
        make_button(preview_row, '', lambda: self._cycle_background(-1),
                    kind='ghost', width=3).pack(side='left', padx=(0, 4))
        box = make_card(preview_row, bg=THEME['preview_bg'])
        box.pack(side='left')
        self._equip_preview_label = make_label(
            box, bg=THEME['preview_bg'], cursor='hand2')
        self._equip_preview_label.pack()
        self._preview_bounce_scale = (1.0, 1.0)
        self._preview_bounce_job = None
        make_button(preview_row, '', lambda: self._cycle_background(1),
                    kind='ghost', width=3).pack(side='left', padx=(4, 0))
        self._equip_preview_label.bind('<Motion>', self._equip_preview_motion)
        self._equip_preview_label.bind('<Button-1>', self._preview_click_bounce)
        self._equip_stats_label = make_label(
            wrap, '', bg=THEME['card'], fg=THEME['muted'], style='small')
        self._equip_stats_label.pack(pady=(10, 0))

        self._build_vitals_widgets(wrap, THEME['card'], include_exp=False)

        self._warehouse_detail_card = make_card(content, bg=THEME['card'])
        self._warehouse_detail_card.configure(width=WAREHOUSE_DETAIL_WIDTH)
        self._warehouse_detail_card.pack(
            side='right', fill='y', padx=(12, 0))
        self._warehouse_detail_card.pack_propagate(False)
        self._warehouse_detail_content = tk.Frame(
            self._warehouse_detail_card, bg=THEME['card'])
        self._warehouse_detail_content.pack(fill='both', expand=True)
        self._warehouse_detail_job = None
        self._warehouse_detail_hide_job = None
        self._pinned_warehouse_detail = None
        self._show_warehouse_detail_placeholder()

        right_col = make_card(content, bg=THEME['card'])
        right_col.pack(side='right', fill='both', expand=True)
        self._equip_subbar = tk.Frame(right_col, bg=THEME['card'])
        self._equip_subbuttons = {}
        list_wrap = tk.Frame(right_col, bg=THEME['card'])
        list_wrap.pack(fill='both', expand=True, padx=14, pady=14)
        self._warehouse_list_wrap = list_wrap
        self._warehouse_list = self._make_scrollable_frame(
            list_wrap, THEME['card'], height=430, width=500)
        self._adjust_wrap, self._adjust_content = self._make_scrollable_frame(
            right_col, THEME['card'], height=430, width=500, detached=True)
        win.bind('<Motion>', self._equip_preview_motion)
        win.protocol('WM_DELETE_WINDOW', self.close_warehouse)
        self._select_warehouse_tab('宝藏')
        self._start_preview_actions()


    def _build_vitals_widgets(self, parent, page_bg, include_exp=True):
        """创建仓库/探险共用的条形属性面板。"""
        vitals = tk.Frame(parent, bg=page_bg)
        vitals.pack(pady=(10, 0))
        hp_row = tk.Frame(vitals, bg=page_bg)
        hp_row.pack(anchor='w')
        make_label(hp_row, '活力', width=4, anchor='w', bg=page_bg,
                   style='small').pack(side='left')
        self._hp_canvas = tk.Canvas(
            hp_row, width=182, height=14, bg=THEME['card_alt'],
            highlightthickness=1, highlightbackground=THEME['border'])
        self._hp_canvas.pack(side='left', padx=(6, 0))

        emotion_row = tk.Frame(vitals, bg=page_bg)
        emotion_row.pack(anchor='w', pady=(6, 0))
        make_label(emotion_row, '情绪', width=4, anchor='w', bg=page_bg,
                   style='small').pack(side='left')
        self._emotion_canvas = tk.Canvas(
            emotion_row, width=182, height=14, bg=THEME['card_alt'],
            highlightthickness=1, highlightbackground=THEME['border'])
        self._emotion_canvas.pack(side='left', padx=(6, 0))

        if include_exp:
            exp_row = tk.Frame(vitals, bg=page_bg)
            exp_row.pack(anchor='w', pady=(6, 0))
            self._exp_level_label = make_label(
                exp_row, f'Lv.{self.level}', bg=page_bg, width=4,
                anchor='w', style='small')
            self._exp_level_label.pack(side='left')
            self._exp_bar_width = 180
            self._exp_canvas = tk.Canvas(
                exp_row, width=self._exp_bar_width + 2, height=14,
                bg=THEME['card_alt'], highlightthickness=1,
                highlightbackground=THEME['border'])
            self._exp_canvas.pack(side='left', padx=(6, 0))
        return vitals

    def _slot_text(self, name):
        if name in ('头饰', '饰品'):
            ids = self._slot_item_ids(self.equipped_slots, name)
            names = [ITEMS.get(iid, {}).get('name', name) for iid in ids]
            return ' / '.join(names) if names else name
        if name == '服装':
            return CLOTHES_NAMES.get(self.equipped_clothes, '普通衣服')
        return name


    def _draw_equip_circles(self):
        """重绘三个圆槽（高亮当前选中的槽）"""
        cv = getattr(self, '_equip_canvas', None)
        if cv is None:
            return
        cv.delete('all')
        for cy, name in self._equip_centers:
            fill = THEME['accent'] if name == self._equip_slot else THEME['card']
            cv.create_oval(10, cy - 30, 70, cy + 30, fill=fill,
                           outline='#999999')
            cv.create_text(40, cy, text=self._slot_text(name), width=56,
                           fill=THEME['text'], font=FONT_SMALL)


    def _on_slot_click(self, event):
        """点击圆形：点亮该槽并显示对应装备列表"""
        if not getattr(self, '_equip_centers', None):
            return
        idx = min(range(len(self._equip_centers)),
                  key=lambda i: abs(event.y - self._equip_centers[i][0]))
        self._equip_slot = self._equip_centers[idx][1]
        self._draw_equip_circles()
        self._select_warehouse_tab('装备')


    def _select_warehouse_tab(self, cat):
        """切换仓库右侧列表分类"""
        self._close_equipment_adjust_panel()
        self._record_obtained_items()
        unseen = getattr(self.game, 'new_item_categories', set())
        if cat in unseen:
            unseen.discard(cat)
            self._save_satiety()
        if cat != '宝藏':
            self._treasure_lock_mode = False
        if cat != getattr(self, '_warehouse_cat', cat):
            self._pinned_warehouse_detail = None
        self._warehouse_cat = cat
        self._fit_warehouse_width(cat)
        self._fit_warehouse_detail_width(cat)
        self._configure_warehouse_subbar(cat)
        for c, btn in self._warehouse_buttons.items():
            try:
                selected = c == cat
                btn.config(bg=THEME['tab_selected'] if selected else THEME['tab_bg'],
                           fg=THEME['accent_text'] if selected else THEME['text'])
            except Exception:
                pass
        self._refresh_warehouse()


    def _refresh_warehouse_tab_indicators(self):
        """更新物品/特殊/装备主页的未读红点。"""
        badges = getattr(self, '_warehouse_tab_badges', {})
        if not badges:
            return
        unseen = getattr(self.game, 'new_item_categories', set())
        for cat, badge in badges.items():
            if cat in unseen:
                selected = cat == getattr(self, '_warehouse_cat', '')
                badge.config(
                    bg=(THEME['tab_selected'] if selected
                        else THEME['tab_bg']))
                badge.place(relx=1.0, x=-2, y=0, anchor='ne')
                badge.lift()
            else:
                badge.place_forget()


    def _fit_warehouse_detail_width(self, cat):
        """信件页放大详情栏，相应缩窄中间选择栏。"""
        card = getattr(self, '_warehouse_detail_card', None)
        if card is None:
            return
        try:
            width = (WAREHOUSE_LETTER_DETAIL_WIDTH
                     if cat == '信件' else WAREHOUSE_DETAIL_WIDTH)
            card.configure(width=width)
        except Exception:
            return


    def _fit_warehouse_width(self, cat):
        """装备子页只保留较紧凑的双列宽度，其它仓库页维持原宽度。"""
        win = getattr(self, '_warehouse_win', None)
        if win is None:
            return
        try:
            if not win.winfo_exists():
                return
            width = (WAREHOUSE_EQUIP_WIDTH
                     if cat == '装备' else WAREHOUSE_WIDTH)
            win.geometry(
                f'{dp(width)}x{dp(WAREHOUSE_HEIGHT)}')
        except Exception:
            return

    def _configure_warehouse_subbar(self, cat):
        """按当前主标签重建右侧子标签。"""
        bar = getattr(self, '_equip_subbar', None)
        if bar is None or not bar.winfo_exists():
            return
        for child in bar.winfo_children():
            child.destroy()
        self._equip_subbuttons = {}
        if cat == '装备':
            # 「特殊」（一次性道具）已并入装备子栏，与服装/饰品等并列。
            slots = ('书籍', '头饰', '服装', '饰品', '特殊')
            selected = getattr(self, '_equip_slot', '头饰')
            command = self._select_equip_subpage
        elif cat == '物品':
            slots = ('材料', '食物', '消耗品', '战利品')
            selected = getattr(self, '_item_subpage', '食物')
            command = self._select_item_subpage
        else:
            bar.pack_forget()
            return
        for name in reversed(slots):
            btn = make_button(
                bar, name, lambda s=name, fn=command: fn(s),
                kind='tab', width=8)
            btn.pack(side='right', padx=2)
            self._equip_subbuttons[name] = btn
            try:
                is_selected = name == selected
                btn.config(
                    bg=THEME['tab_selected'] if is_selected else THEME['tab_bg'],
                    fg=THEME['accent_text'] if is_selected else THEME['text'])
            except Exception:
                pass
        bar.pack(fill='x', pady=(0, 4), before=self._warehouse_list_wrap)


    def _select_equip_subpage(self, slot):
        self._equip_slot = slot
        for name, btn in self._equip_subbuttons.items():
            try:
                selected = name == slot
                btn.config(bg=THEME['tab_selected'] if selected else THEME['tab_bg'],
                           fg=THEME['accent_text'] if selected else THEME['text'])
            except Exception:
                pass
        self._refresh_warehouse_list()


    def _select_item_subpage(self, subpage):
        self._item_subpage = subpage
        for name, btn in self._equip_subbuttons.items():
            try:
                selected = name == subpage
                btn.config(bg=THEME['tab_selected'] if selected else THEME['tab_bg'],
                           fg=THEME['accent_text'] if selected else THEME['text'])
            except Exception:
                pass
        self._refresh_warehouse_list()


    def _refresh_warehouse(self):
        """刷新仓库：金币、经验条、预览、右侧列表"""
        if (self._warehouse_win is None
                or not self._warehouse_win.winfo_exists()):
            # 仓库没开时，若工作站开着就同步刷新（两者共用数值条与预览构件）。
            workstation_win = getattr(self, '_workstation_win', None)
            if (workstation_win is not None
                    and workstation_win.winfo_exists()):
                self._refresh_workstation()
            return
        self._record_obtained_items()
        self._refresh_warehouse_tab_indicators()
        text = f'金币：{self.gold} G'
        if self.adventuring:
            text += '（探险中…）'
        self._warehouse_text.config(text=text)
        self._refresh_hp_bar()
        self._refresh_emotion_bar()
        self._refresh_exp_bar()
        self._equip_preview_update()
        self._refresh_achievement_ui()
        self._sync_expression_book_unlocks()
        self._refresh_warehouse_list()


    def _quality_color(self, info):
        """物品品质对应的字体颜色。"""
        custom = info.get('quality_color')
        if custom:
            return custom
        return QUALITY_COLORS.get(info.get('quality', '普通'),
                                  QUALITY_COLORS['普通'])


    def _bind_tooltip(self, widget, info):
        widget.bind('<Enter>',
                    lambda e, i=info: self._schedule_tooltip(i), add='+')
        widget.bind('<Leave>', lambda e: self._hide_tooltip(), add='+')


    def _schedule_tooltip(self, info):
        self._hide_tooltip()
        self._hover_job = self.root.after(
            500, lambda: self._show_tooltip(info))


    def _show_tooltip(self, info):
        self._hover_job = None
        if (self._warehouse_win is None
                or not self._warehouse_win.winfo_exists()):
            return
        quality = info.get('display_quality') or info.get('quality', '普通')
        quality_color = self._quality_color(info)
        win = tk.Toplevel(self._warehouse_win)
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        card = make_card(
            win, bg=THEME['card'], highlightthickness=2,
            highlightbackground=quality_color)
        card.pack()
        make_label(
            card, info.get('name', '-'), bg=THEME['card'],
            fg=THEME['text'], font=(FONT_FAMILY, 11, 'bold'),
            anchor='w').pack(fill='x', padx=10, pady=(8, 2))
        make_label(
            card, f'品质：{quality}', bg=THEME['card'],
            fg=quality_color, font=(FONT_FAMILY, 9, 'bold'),
            anchor='w').pack(fill='x', padx=10)
        tk.Frame(card, bg=THEME['border'], height=1).pack(
            fill='x', padx=10, pady=(6, 5))

        kind = info.get('kind') or info.get('category')
        if kind:
            make_label(
                card, f'类型：{kind}', bg=THEME['card'],
                fg=THEME['muted'], font=(FONT_FAMILY, 9),
                anchor='w').pack(fill='x', padx=10)
        make_label(
            card, info.get('desc', '（暂无描述）'), bg=THEME['card'],
            fg=THEME['text'], font=(FONT_FAMILY, 9), justify='left',
            anchor='w', wraplength=300).pack(
                fill='x', padx=10, pady=(3, 0))

        effects = []
        if 'exp' in info:
            effects.append(f'效果：增加经验 +{info["exp"]}')
        effect = info.get('eat_effect') or {}
        if effect.get('hp_loss_chance') and effect.get('hp_loss_ratio'):
            effects.append(
                f'额外效果：{effect["hp_loss_chance"]:.0%} 概率'
                f'扣除活力上限 {effect["hp_loss_ratio"]:.0%} 的活力')
        if effects:
            make_label(
                card, '\n'.join(effects), bg=THEME['card'],
                fg=THEME['accent_hover'], font=(FONT_FAMILY, 9, 'bold'),
                justify='left', anchor='w', wraplength=300).pack(
                    fill='x', padx=10, pady=(5, 8))
        else:
            tk.Frame(card, bg=THEME['card'], height=8).pack()

        win.update_idletasks()
        width = max(1, win.winfo_reqwidth())
        height = max(1, win.winfo_reqheight())
        pointer_x = self.root.winfo_pointerx()
        pointer_y = self.root.winfo_pointery()
        x = pointer_x + 16
        y = pointer_y + 16
        if x + width > win.winfo_screenwidth():
            x = pointer_x - width - 16
        if y + height > win.winfo_screenheight():
            y = pointer_y - height - 16
        x = max(0, min(x, win.winfo_screenwidth() - width))
        y = max(0, min(y, win.winfo_screenheight() - height))
        win.geometry(f'+{x}+{y}')
        self._hover_win = win

    def _hide_tooltip(self):
        if getattr(self, '_hover_job', None) is not None:
            try:
                self.root.after_cancel(self._hover_job)
            except Exception:
                pass
            self._hover_job = None
        if getattr(self, '_hover_win', None) is not None:
            try:
                self._hover_win.destroy()
            except Exception:
                pass
            self._hover_win = None


    def _bind_warehouse_detail_frame(self, widget, info):
        def show_detail(event=None):
            self._schedule_warehouse_detail(info)

        def hide_detail(event=None):
            self._schedule_warehouse_detail_hide()

        def bind_tree(item):
            item.bind('<Enter>', show_detail, add='+')
            item.bind('<Leave>', hide_detail, add='+')
            for child in item.winfo_children():
                bind_tree(child)

        bind_tree(widget)

    def _cancel_warehouse_detail_hide(self):
        job = getattr(self, '_warehouse_detail_hide_job', None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._warehouse_detail_hide_job = None

    def _schedule_warehouse_detail(self, info):
        self._cancel_warehouse_detail_hide()
        job = getattr(self, '_warehouse_detail_job', None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        self._warehouse_detail_job = self.root.after(
            20, lambda data=info: self._show_warehouse_detail(data))

    def _schedule_warehouse_detail_hide(self):
        self._cancel_warehouse_detail_hide()
        job = getattr(self, '_warehouse_detail_job', None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._warehouse_detail_job = None
        self._warehouse_detail_hide_job = self.root.after(
            90, self._hide_warehouse_detail)

    def _show_warehouse_detail_placeholder(self):
        content = getattr(self, '_warehouse_detail_content', None)
        if content is None or not content.winfo_exists():
            return
        for child in content.winfo_children():
            child.destroy()
        card = getattr(self, '_warehouse_detail_card', None)
        if card is not None:
            card.configure(
                highlightbackground=THEME['border'],
                highlightcolor=THEME['border'], highlightthickness=1)
        make_label(
            content, '物品详情', bg=THEME['card'], fg=THEME['muted'],
            font=(FONT_FAMILY, 10, 'bold')).pack(
                anchor='w', padx=12, pady=(14, 6))
        make_label(
            content, '将鼠标移入物品框查看详情', bg=THEME['card'],
            fg=THEME['muted'], font=(FONT_FAMILY, 9), justify='left',
            wraplength=240).pack(anchor='w', padx=12)

    def _hide_warehouse_detail(self):
        if getattr(self, '_pinned_warehouse_detail', None) is not None:
            return
        self._warehouse_detail_job = None
        self._warehouse_detail_hide_job = None
        self._show_warehouse_detail_placeholder()

    def _show_warehouse_detail(self, info, pinned=False):
        if pinned:
            self._pinned_warehouse_detail = info
        self._warehouse_detail_job = None
        self._cancel_warehouse_detail_hide()
        content = getattr(self, '_warehouse_detail_content', None)
        if content is None or not content.winfo_exists():
            return
        for child in content.winfo_children():
            child.destroy()
        if info.get('detail_kind') == 'letter':
            card = getattr(self, '_warehouse_detail_card', None)
            if card is not None:
                card.configure(
                    highlightbackground=THEME['border'],
                    highlightcolor=THEME['border'], highlightthickness=1)
            self._render_letter_warehouse_detail(content, info)
            return
        quality = info.get('display_quality') or info.get('quality', '普通')
        quality_color = self._quality_color(info)
        card = getattr(self, '_warehouse_detail_card', None)
        if card is not None:
            card.configure(
                highlightbackground=quality_color,
                highlightcolor=quality_color, highlightthickness=2)
        make_label(
            content, info.get('name', '-'), bg=THEME['card'],
            fg=THEME['text'], font=(FONT_FAMILY, 11, 'bold'),
            anchor='w', justify='left', wraplength=240).pack(
                fill='x', padx=12, pady=(14, 2))
        make_label(
            content, f'品质：{quality}', bg=THEME['card'],
            fg=quality_color, font=(FONT_FAMILY, 9, 'bold'),
            anchor='w').pack(fill='x', padx=12)
        tk.Frame(content, bg=THEME['border'], height=1).pack(
            fill='x', padx=12, pady=(7, 6))
        kind = info.get('kind') or info.get('category')
        if kind:
            make_label(
                content, f'类型：{kind}', bg=THEME['card'],
                fg=THEME['muted'], font=(FONT_FAMILY, 9),
                anchor='w').pack(fill='x', padx=12)
        make_label(
            content, info.get('desc', '（暂无描述）'), bg=THEME['card'],
            fg=THEME['text'], font=(FONT_FAMILY, 9), justify='left',
            anchor='w', wraplength=240).pack(
                fill='x', padx=12, pady=(4, 0))
        effects = []
        if 'exp' in info:
            effects.append(f'效果：增加经验 +{info["exp"]}')
        effect = info.get('eat_effect') or {}
        if effect.get('hp_loss_chance') and effect.get('hp_loss_ratio'):
            effects.append(
                f'额外效果：{effect["hp_loss_chance"]:.0%} 概率'
                f'扣除活力上限 {effect["hp_loss_ratio"]:.0%} 的活力')
        if effects:
            make_label(
                content, '\n'.join(effects), bg=THEME['card'],
                fg=THEME['accent_hover'], font=(FONT_FAMILY, 9, 'bold'),
                justify='left', anchor='w', wraplength=240).pack(
                    fill='x', padx=12, pady=(7, 0))


    def _letter_asset_path(self, relative_path):
        parts = str(relative_path).replace('\\', '/').split('/', 1)
        if len(parts) == 2:
            return _asset_path(parts[1], parts[0])
        return _asset_path(parts[0])


    def _render_letter_text_detail(self, content, info):
        """没有图片的信件直接在详情栏中显示可滚动正文。"""
        make_label(
            content, '信件', bg=THEME['card'],
            fg=THEME['text'], font=(FONT_FAMILY, 11, 'bold'),
            anchor='w', justify='left').pack(fill='x', padx=14, pady=(14, 6))
        body = info.get('body') or info.get('desc', '（暂无内容）')
        body_frame = tk.Frame(content, bg=THEME['card'])
        body_frame.pack(fill='both', expand=True, padx=14, pady=(0, 14))
        scrollbar = tk.Scrollbar(
            body_frame, orient='vertical', width=10, bd=0,
            highlightthickness=0, troughcolor=THEME['card_alt'],
            bg=THEME['border'])
        text = tk.Text(
            body_frame, wrap='word', font=(FONT_FAMILY, 9),
            bg=THEME['card'], fg=THEME['text'], bd=0,
            highlightthickness=0, padx=6, pady=6,
            yscrollcommand=scrollbar.set)
        scrollbar.config(command=text.yview)
        scrollbar.pack(side='right', fill='y')
        text.pack(side='left', fill='both', expand=True)
        text.insert('1.0', str(body))
        text.config(state='disabled')


    def _load_letter_image(self, info):
        image_path = info.get('content_image') or info.get('image')
        if not image_path:
            return None
        with PIL.Image.open(self._letter_asset_path(image_path)) as raw:
            return raw.convert('RGBA')


    def _render_letter_image_detail(self, content, info):
        """在仓库详情栏尽量放大显示信件图片，点击后打开可缩放子页。"""
        make_label(
            content, '信件', bg=THEME['card'],
            fg=THEME['text'], font=(FONT_FAMILY, 11, 'bold'),
            anchor='w', justify='left').pack(
                fill='x', padx=14, pady=(14, 4))
        try:
            image = self._load_letter_image(info)
            if image is None:
                raise ValueError('missing letter image')
            content.update_idletasks()
            available_width = int(content.winfo_width() or 0)
            if available_width < 240:
                available_width = 500
            target_width = max(1, min(image.width, available_width - 22))
            scale = target_width / image.width
            target_height = max(1, round(image.height * scale))
            preview = image.resize(
                (target_width, target_height), PIL.Image.Resampling.LANCZOS)
            photo = PIL.ImageTk.PhotoImage(preview)
            self._letter_detail_photo = photo

            holder = tk.Frame(content, bg=THEME['card'])
            holder.pack(fill='both', expand=True, padx=10, pady=(0, 4))
            canvas = tk.Canvas(
                holder, bg=THEME['card'], highlightthickness=0,
                cursor='hand2')
            scrollbar = tk.Scrollbar(
                holder, orient='vertical', command=canvas.yview,
                width=10, bd=0, highlightthickness=0,
                troughcolor=THEME['card_alt'], bg=THEME['border'])
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')
            canvas.pack(side='left', fill='both', expand=True)
            canvas.create_image(0, 0, image=photo, anchor='nw')
            canvas.configure(
                scrollregion=(0, 0, target_width, target_height))
            canvas.bind(
                '<Button-1>',
                lambda event, data=dict(info): self._open_letter_image_viewer(data))
            canvas.bind(
                '<MouseWheel>',
                lambda event: (
                    canvas.yview_scroll(
                        -3 if event.delta > 0 else 3, 'units'),
                    'break')[1])
            make_label(
                content, '点击查看大图 · 鼠标滚轮浏览', bg=THEME['card'],
                fg=THEME['muted'], font=(FONT_FAMILY, 8)).pack(
                    pady=(0, 10))
        except Exception:
            make_label(
                content, info.get('desc', '信件内容暂时无法显示。'),
                bg=THEME['card'], fg=THEME['text'],
                font=(FONT_FAMILY, 9), justify='left', anchor='w',
                wraplength=440).pack(fill='x', padx=18, pady=18)


    def _render_letter_warehouse_detail(self, content, info):
        """按信件定义选择图片或文字详情。"""
        if info.get('presentation') == 'text' or info.get('body'):
            self._render_letter_text_detail(content, info)
        else:
            self._render_letter_image_detail(content, info)
        self._render_letter_attachment_section(content, info)


    def _pack_before_expanding(self, content, widget):
        """把附件区插到详情栏里「会吃掉剩余空间」的那个控件之前。

        正文 / 图片区是 expand 的，谁后 pack 谁就可能被挤没；
        附件区（含「领取附件」按钮）必须排在它前面才一定看得见。
        """
        anchor = None
        for child in content.winfo_children():
            if child is widget:
                continue
            try:
                info = child.pack_info()
            except Exception:
                continue
            if str(info.get('expand', 0)) in ('1', 'True', 'true'):
                anchor = child
                break
        if anchor is not None:
            widget.pack(fill='x', side='top', before=anchor)
        else:
            widget.pack(fill='x')


    def _render_letter_attachment_section(self, content, info):
        """信件详情栏的附件区：附件要手动点「领取附件」才会入包。"""
        attachments = letter_attachments(info.get('id'))
        if not attachments:
            return
        items = globals().get('ITEMS') or {}
        letter_id = info.get('id')
        claimed = attachment_claimed(self.game, letter_id)
        section = tk.Frame(content, bg=THEME['card'])
        tk.Frame(section, bg=THEME['border'], height=1).pack(
            fill='x', padx=14, pady=(10, 0))
        head = tk.Frame(section, bg=THEME['card'])
        head.pack(fill='x', padx=14, pady=(7, 2))
        make_label(
            head, '附件', bg=THEME['card'], fg=THEME['text'],
            font=(FONT_FAMILY, 10, 'bold')).pack(side='left')
        make_label(
            head, '已领取' if claimed else '等待领取', bg=THEME['card'],
            fg=THEME['success'] if claimed else THEME['danger'],
            font=(FONT_FAMILY, 9, 'bold')).pack(side='right')
        for entry in attachments:
            item_id = entry['item']
            detail = items.get(item_id) or {}
            name = detail.get('name') or item_id
            color = self._quality_color(detail) if detail else THEME['text']
            row = make_card(
                section, bg=THEME['card'], highlightbackground=color,
                highlightcolor=color, highlightthickness=1)
            row.pack(fill='x', padx=14, pady=(2, 2))
            title_row = tk.Frame(row, bg=THEME['card'])
            title_row.pack(fill='x', padx=8, pady=(6, 0))
            make_label(
                title_row, f'{name} × {entry["count"]}', bg=THEME['card'],
                fg=color, font=(FONT_FAMILY, 10, 'bold'),
                anchor='w').pack(side='left')
            quality = detail.get('quality')
            if quality:
                make_label(
                    title_row, f'（{quality}）', bg=THEME['card'], fg=color,
                    font=(FONT_FAMILY, 9)).pack(side='left', padx=(4, 0))
            if not claimed:
                make_button(
                    title_row, '领取附件',
                    lambda i=dict(info): self._claim_letter_attachment(i),
                    kind='primary', width=9).pack(side='right')
            desc = detail.get('desc')
            if desc:
                make_label(
                    row, desc, bg=THEME['card'], fg=THEME['muted'],
                    font=(FONT_FAMILY, 9), justify='left', anchor='w',
                    wraplength=430).pack(fill='x', padx=8, pady=(2, 6))
            else:
                tk.Frame(row, bg=THEME['card'], height=6).pack(fill='x')
        make_label(
            section,
            ('附件已经收进仓库，可在「特殊」页查看。' if claimed
             else '点击「领取附件」后，附件才会收进仓库。'),
            bg=THEME['card'], fg=THEME['muted'], font=(FONT_FAMILY, 8),
            justify='left', anchor='w').pack(
                fill='x', padx=14, pady=(2, 10))
        self._pack_before_expanding(content, section)


    def _claim_letter_attachment(self, info):
        """领取信件附件：入包 + 写存档 + 刷新界面（领过的不会重复发放）。"""
        letter_id = info.get('id')
        granted, error = claim_letter_attachments(
            self.game, self.inventory, letter_id, globals().get('ITEMS') or {})
        if error:
            self._alert('附件', error)
            return
        try:
            self._save_satiety()
        except Exception:
            pass
        self._refresh_warehouse_tab_indicators()
        self._refresh_warehouse_list()
        self._show_warehouse_detail(self._letter_info(letter_id) or info, pinned=True)
        banner = getattr(self, '_warehouse_banner_label', None)
        if banner is not None:
            names = '、'.join(f"{g['name']}×{g['count']}" for g in granted)
            try:
                banner.config(text=f'已收下附件：{names}')
            except Exception:
                pass


    def _open_letter_image_viewer(self, info):
        """打开信件图片子页，默认放大并支持拖动、滚轮缩放。"""
        try:
            source = self._load_letter_image(info)
            if source is None:
                raise ValueError('missing letter image')
        except Exception:
            self._alert('信件', '这封信的图片暂时无法打开。')
            return

        parent = (self._warehouse_win
                  if getattr(self, '_warehouse_win', None) is not None
                  and self._warehouse_win.winfo_exists() else self.root)
        win = tk.Toplevel(parent)
        win.title('信件')
        win.attributes('-toolwindow', True)
        configure_theme(win)
        screen_width = int(win.winfo_screenwidth())
        screen_height = int(win.winfo_screenheight())
        win_width = max(720, min(dp(1080), int(screen_width * 0.88)))
        win_height = max(560, min(dp(960), int(screen_height * 0.90)))
        win_x = max(0, (screen_width - win_width) // 2)
        win_y = max(0, (screen_height - win_height) // 2)
        win.geometry(f'{win_width}x{win_height}+{win_x}+{win_y}')
        try:
            win.transient(parent)
        except Exception:
            pass

        controls = tk.Frame(win, bg=THEME['bg'])
        controls.pack(fill='x', padx=12, pady=(10, 5))
        make_label(
            controls, '信件', bg=THEME['bg'], fg=THEME['text'],
            font=(FONT_FAMILY, 11, 'bold')).pack(side='left')
        make_label(
            controls, '按住鼠标拖动 · 滚轮缩放', bg=THEME['bg'],
            fg=THEME['muted'], font=(FONT_FAMILY, 8)).pack(
                side='left', padx=(10, 0))
        zoom_label = make_label(
            controls, '100%', bg=THEME['bg'], fg=THEME['muted'],
            font=(FONT_FAMILY, 9, 'bold'))
        zoom_label.pack(side='right', padx=(8, 0))
        make_button(
            controls, '重置', lambda: set_scale(initial_scale),
            kind='ghost', width=6).pack(side='right', padx=(6, 0))
        make_button(
            controls, '缩小', lambda: set_scale(state['scale'] / 1.25),
            kind='secondary', width=6).pack(side='right', padx=(6, 0))
        make_button(
            controls, '放大', lambda: set_scale(state['scale'] * 1.25),
            kind='secondary', width=6).pack(side='right', padx=(6, 0))

        body = tk.Frame(win, bg=THEME['card'])
        body.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        canvas = tk.Canvas(
            body, bg=THEME['card_alt'], highlightthickness=0,
            cursor='fleur')
        hbar = tk.Scrollbar(
            body, orient='horizontal', command=canvas.xview,
            width=10, bd=0, highlightthickness=0,
            troughcolor=THEME['card_alt'], bg=THEME['border'])
        vbar = tk.Scrollbar(
            body, orient='vertical', command=canvas.yview,
            width=10, bd=0, highlightthickness=0,
            troughcolor=THEME['card_alt'], bg=THEME['border'])
        canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.pack(side='bottom', fill='x')
        vbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        win.update_idletasks()
        view_width = canvas.winfo_width()
        view_height = canvas.winfo_height()
        if view_width <= 1:
            view_width = max(320, win_width - 36)
        if view_height <= 1:
            view_height = max(260, win_height - dp(96))
        fit_width = max(1, view_width - 40) / source.width
        fit_height = max(1, view_height - 40) / source.height
        initial_scale = min(
            1.0, max(0.60, fit_width, fit_height))
        state = {'scale': initial_scale, 'photo': None, 'item': None}
        padding = 20

        def center_view(image_width, image_height):
            current_width = canvas.winfo_width()
            current_height = canvas.winfo_height()
            view_width = (current_width if current_width > 1
                          else max(320, win_width - 36))
            view_height = (current_height if current_height > 1
                           else max(260, win_height - dp(96)))
            scroll_width = max(view_width, image_width + padding * 2)
            scroll_height = max(view_height, image_height + padding * 2)
            image_x = (padding if image_width + padding * 2 > view_width
                       else (view_width - image_width) / 2)
            image_y = (padding if image_height + padding * 2 > view_height
                       else (view_height - image_height) / 2)
            canvas.coords(state['item'], image_x, image_y)
            canvas.configure(scrollregion=(0, 0, scroll_width, scroll_height))
            if scroll_width > view_width:
                canvas.xview_moveto(
                    max(0.0, (scroll_width - view_width) / (2 * scroll_width)))
            else:
                canvas.xview_moveto(0.0)
            if scroll_height > view_height:
                canvas.yview_moveto(
                    max(0.0, (scroll_height - view_height) / (2 * scroll_height)))
            else:
                canvas.yview_moveto(0.0)

        def render():
            width = max(1, round(source.width * state['scale']))
            height = max(1, round(source.height * state['scale']))
            rendered = source.resize(
                (width, height), PIL.Image.Resampling.LANCZOS)
            photo = PIL.ImageTk.PhotoImage(rendered)
            if state['item'] is None:
                state['item'] = canvas.create_image(
                    padding, padding, image=photo, anchor='nw')
            else:
                canvas.itemconfigure(state['item'], image=photo)
            state['photo'] = photo
            center_view(width, height)
            zoom_label.config(text=f'{state["scale"] * 100:.0f}%')

        def set_scale(value):
            state['scale'] = max(0.2, min(3.0, float(value)))
            render()

        def on_mousewheel(event):
            if event.delta:
                factor = 1.12 if event.delta > 0 else 1 / 1.12
                set_scale(state['scale'] * factor)
            return 'break'

        def start_pan(event):
            canvas.scan_mark(event.x, event.y)
            canvas.configure(cursor='fleur')
            return 'break'

        def drag_pan(event):
            canvas.scan_dragto(event.x, event.y, gain=1)
            return 'break'

        def stop_pan(event):
            canvas.configure(cursor='fleur')

        canvas.bind('<MouseWheel>', on_mousewheel)
        canvas.bind('<ButtonPress-1>', start_pan)
        canvas.bind('<B1-Motion>', drag_pan)
        canvas.bind('<ButtonRelease-1>', stop_pan)
        win.bind('<MouseWheel>', on_mousewheel)
        win.bind('<plus>', lambda event: set_scale(state['scale'] * 1.25))
        win.bind('<equal>', lambda event: set_scale(state['scale'] * 1.25))
        win.bind('<minus>', lambda event: set_scale(state['scale'] / 1.25))
        win.bind('<Escape>', lambda event: win.destroy())
        render()
        win.focus_set()


    def _toggle_book(self, item_id):
        """勾选/取消待生效书籍；四本表情管理书互斥。"""
        pending = self._pending_books_enabled
        if item_id in EXPRESSION_BOOK_ORDER:
            if item_id in pending:
                return
            for key in EXPRESSION_BOOK_ORDER:
                pending.discard(key)
            pending.add(item_id)
        elif item_id in pending:
            pending.discard(item_id)
        else:
            pending.add(item_id)
        self._equip_preview_update()
        self._refresh_warehouse_list()


    def _refresh_warehouse_list(self):
        """按当前标签重建右侧列表"""
        self._hide_tooltip()
        self._hide_warehouse_detail()
        if getattr(self, '_warehouse_list', None) is None:
            return
        for w in self._warehouse_list.winfo_children():
            w.destroy()
        self._food_spins = {}
        bg = self._warehouse_list.cget('background')
        cat = getattr(self, '_warehouse_cat', '装备')
        if cat == '装备':
            self._build_equipment_list(self._warehouse_list, bg)
            return
        if cat == '宝藏':
            self._build_treasure_list(self._warehouse_list, bg)
            return
        if cat == '信件':
            self._build_letter_list(self._warehouse_list, bg)
            return
        # 物品页按类型字段分栏：食物显示所有食物，其余显示材料。
        item_subpage = (getattr(self, '_item_subpage', '食物')
                        if cat == '物品' else '')
        food_subpage = cat == '物品' and item_subpage == '食物'
        found = False
        for iid, info in ITEMS.items():
            if cat == '物品':
                expected_kind = item_subpage or '材料'
                if expected_kind == '消耗品':
                    # 消耗品：类型列写「消耗品」，或整张表就叫「消耗品」都算。
                    if (info.get('kind') != '消耗品'
                            and info.get('category') != '消耗品'):
                        continue
                elif info.get('kind') != expected_kind:
                    continue
            elif info.get('category') != cat:
                continue
            count = self.inventory.get(iid, 0)
            if count <= 0:
                continue
            found = True
            row = make_card(self._warehouse_list, bg=bg)
            row.pack(fill='x', pady=2)
            row._quality_color = self._quality_color(info)
            row._quality_border_thick = False
            row._selected = (
                food_subpage
                and getattr(self, '_selected_food', None) == iid)
            if food_subpage:
                can_eat = (info.get('kind') == '食物'
                           and info.get('exp', 0) > 0)
                lbl = make_label(row, text=f"{info['name']} × {count}",
                               bg=bg, font=('Microsoft YaHei UI', 11),
                               fg=self._quality_color(info), cursor='hand2')
                lbl.pack(side='left')
                if can_eat:
                    lbl.bind('<Button-1>',
                             lambda e, i=iid: self._select_food(i))
                else:
                    lbl.bind('<Button-1>',
                             lambda e, i=iid: self._on_item_click(i))
                if can_eat:
                    spin = tk.Spinbox(row, from_=1, to=count, width=3,
                                      justify='center',
                                      command=lambda i=iid: self._on_food_qty(i))
                    spin.pack(side='left', padx=4)
                    self._food_spins[iid] = spin
                    make_button(
                        row, text='使用',
                        command=lambda i=iid: self._feed_from_warehouse(i)
                    ).pack(side='left')
            else:
                lbl = make_label(row, text=f"{info['name']} × {count}",
                               bg=bg, font=('Microsoft YaHei UI', 11),
                               fg=self._quality_color(info), cursor='hand2')
                lbl.pack(side='left')
                lbl.bind('<Button-1>',
                         lambda e, i=iid: self._on_item_click(i))
                # 消耗品（炼药产出的药水等）带使用效果时给一个「使用」按钮。
                if info.get('use_effect'):
                    make_button(row, text='使用',
                                command=lambda i=iid: self._use_consumable(i)
                                ).pack(side='left', padx=(6, 0))
            self._bind_warehouse_detail_frame(row, info)
        if not found:
            make_label(self._warehouse_list, text='（空）', bg=bg,
                     fg='#999999').pack(anchor='w')
        self._layout_two_columns(self._warehouse_list)


    def _layout_two_columns(self, container):
        children = [w for w in container.winfo_children()
                    if w.winfo_manager() in ('pack', 'grid', 'place')]
        for child in children:
            child.pack_forget()
            child.grid_forget()
        for index, child in enumerate(children):
            quality = getattr(child, '_quality_color', None)
            selected = bool(getattr(child, '_selected', False))
            quality_thick = bool(
                getattr(child, '_quality_border_thick', False)) and bool(quality)
            if quality_thick:
                border = quality
                thickness = 2
            else:
                border = THEME['accent'] if selected else (quality or THEME['border'])
                thickness = 2 if selected else 1
            try:
                child.configure(highlightthickness=thickness,
                                highlightbackground=border,
                                highlightcolor=border)
            except Exception:
                pass
            child.bind('<Enter>', lambda e, c=child, b=border: c.configure(
                highlightbackground=THEME['accent_hover']), add='+')
            child.bind('<Leave>', lambda e, c=child, b=border: c.configure(
                highlightbackground=b), add='+')
            row_index = index // 2
            child.grid(row=row_index, column=index % 2, sticky='nsew',
                       padx=5, pady=4)
            container.grid_rowconfigure(row_index, minsize=42)
        container.grid_columnconfigure(0, weight=1, uniform='item')
        container.grid_columnconfigure(1, weight=1, uniform='item')


    def _treasure_display_name(self, treasure):
        return f"{treasure.get('prefix', '')}{treasure.get('name', '')}"


    def _treasure_groups(self):
        """按前缀、名称、品质和市场价归类已获得的宝藏。"""
        groups = {}
        for treasure in self.treasures:
            key = (treasure.get('prefix', ''), treasure.get('name', ''),
                   treasure.get('quality', 1), treasure.get('value', 0),
                   bool(treasure.get('locked', False)))
            groups.setdefault(key, []).append(treasure)
        return groups


    def _treasure_info(self, treasure):
        display = self._treasure_display_name(treasure)
        quality = QUALITY_NAMES.get(treasure.get('quality', 1), '普通')
        return {
            'name': display,
            'quality': quality,
            'category': '宝藏',
            'desc': (f"前缀：{treasure.get('prefix', '') or '无'}\n"
                     f"基础价值：{treasure.get('base_value', 0)} G\n"
                     f"市场价：{treasure.get('value', 0)} G\n"
                     f"状态：{'已上锁' if treasure.get('locked') else '未上锁'}"),
        }


    def _make_scrollable_frame(self, parent, bg, height=300, width=300,
                               detached=False):
        outer = tk.Frame(parent, bg=bg)
        if not detached:
            outer.pack(fill='both', expand=True)
        canvas = tk.Canvas(outer, bg=bg, width=width, height=height,
                           highlightthickness=0)
        scrollbar = tk.Scrollbar(
            outer, orient='vertical', command=canvas.yview,
            width=10, bd=0, highlightthickness=0,
            troughcolor=THEME['card_alt'], bg=THEME['border'])
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        inner = tk.Frame(canvas, bg=bg)
        window = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>',
                   lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',
                    lambda e: canvas.itemconfigure(window, width=e.width))

        def _wheel(event):
            steps = -1 if event.delta > 0 else 1
            canvas.yview_scroll(steps * 3, 'units')

        outer.bind('<Enter>', lambda e: canvas.bind_all('<MouseWheel>', _wheel))
        outer.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))
        return (outer, inner) if detached else inner


    def _letter_info(self, letter_id):
        """取信件展示数据；长期冒险的动态来信正文存在存档里，要一起传进去。"""
        return get_letter(letter_id, letter_contents(self.game))

    def _available_letter_ids(self):
        result = []
        raw_letters = getattr(self.game, 'letters', [])
        if not isinstance(raw_letters, (list, tuple, set)):
            raw_letters = ()
        for value in raw_letters:
            letter_id = str(value)
            if is_known_letter(letter_id) and letter_id not in result:
                result.append(letter_id)
        result.sort(key=letter_number)
        return result


    def _select_letter(self, letter_id):
        info = self._letter_info(letter_id)
        if info is None:
            return
        self._selected_letter_id = letter_id
        self._pinned_warehouse_detail = None
        self._refresh_warehouse_list()
        self._show_warehouse_detail(info, pinned=True)


    def _build_letter_list(self, container, bg):
        """信件页：列出已经收到的信件，点击后常驻详情栏。"""
        letter_ids = self._available_letter_ids()
        header = tk.Frame(container, bg=bg)
        header.pack(anchor='e', pady=(0, 4))
        make_label(
            header, text=f'信件：{len(letter_ids)} 封', bg=bg,
            fg='#555555', font=('Microsoft YaHei UI', 9)).pack(side='left')
        inner = tk.Frame(container, bg=bg)
        inner.pack(fill='both', expand=True)
        if not letter_ids:
            make_label(
                inner, text='（还没有收到信件）', bg=bg,
                fg='#999999').pack(anchor='w')
            make_label(
                inner, text='冒险途中遇到的人与事，也许会留下书信。',
                bg=bg, fg=THEME['muted'], font=('Microsoft YaHei UI', 9)
            ).pack(anchor='w', pady=(6, 0))
            return
        selected_letter = getattr(self, '_selected_letter_id', None)
        for letter_id in letter_ids:
            info = self._letter_info(letter_id)
            if info is None:
                continue
            selected = letter_id == selected_letter
            border = THEME['accent'] if selected else THEME['border']
            row = make_card(
                inner, bg=bg, highlightbackground=border,
                highlightcolor=border, highlightthickness=2 if selected else 1)
            row.pack(fill='x', pady=3)
            row._quality_color = border
            row._selected = selected
            label = make_label(
                row, text=info['title'],
                bg=bg, fg=THEME['text'], font=(FONT_FAMILY, 10, 'bold'),
                cursor='hand2', anchor='w')
            label.pack(side='left', fill='x', expand=True, padx=10, pady=8)
            select = lambda e, lid=letter_id: self._select_letter(lid)
            if letter_attachments(letter_id):
                claimed = attachment_claimed(self.game, letter_id)
                hint = make_label(
                    row, text=('附件已领取' if claimed else '有附件待领取'),
                    bg=bg, fg=(THEME['muted'] if claimed else THEME['danger']),
                    font=(FONT_FAMILY, 9), cursor='hand2')
                hint.pack(side='right', padx=(0, 10))
                hint.bind('<Button-1>', select, add='+')
            row.bind('<Button-1>', select, add='+')
            label.bind('<Button-1>', select, add='+')
            self._bind_warehouse_detail_frame(row, info)


    def _build_treasure_list(self, container, bg):
        groups = self._treasure_groups()
        total_value = sum(int(t.get('value', 0)) for t in self.treasures)
        header = tk.Frame(container, bg=bg)
        header.pack(anchor='e', pady=(0, 4))
        make_label(
            header,
            text=f'宝藏：{len(self.treasures)} 件 · 总价值 {total_value} G',
            bg=bg, fg='#555555', font=('Microsoft YaHei UI', 9)
        ).pack(side='left')
        treasure_bulk_button = make_button(
            header, '一键出售', self._show_bulk_sell_dialog,
            kind='primary', width=8)
        treasure_bulk_button.pack(side='left', padx=(6, 0))
        self._treasure_lock_button = make_button(
            header, text='🔒', width=3,
            relief='sunken' if self._treasure_lock_mode else 'raised',
            command=self._toggle_treasure_lock_mode)
        self._treasure_lock_button.pack(side='left', padx=(6, 0))
        if not groups:
            treasure_bulk_button.config(state='disabled')
            self._treasure_lock_button.config(state='disabled')
        inner = tk.Frame(container, bg=bg)
        inner.pack(fill='both', expand=True)
        if self._treasure_lock_mode:
            make_label(inner, text='锁模式：点击宝藏上锁/解锁', bg=bg,
                     fg=THEME['danger'], font=('Microsoft YaHei UI', 9)
                     ).pack(anchor='e', pady=(0, 3))
        if not groups:
            make_label(inner, text='（还没有获得宝藏）', bg=bg,
                     fg='#999999').pack(anchor='w')
            self._layout_two_columns(inner)
            return
        ordered = sorted(
            groups.items(),
            key=lambda item: (not bool(item[1][0].get('locked', False)),
                              -item[0][2],
                              self._treasure_display_name(item[1][0])))
        for _, group in ordered:
            first = group[0]
            info = self._treasure_info(first)
            mark = '🔒 ' if first.get('locked', False) else ''
            label = make_label(
                inner,
                text=f"{mark}{info['name']} ×{len(group)}",
                bg=bg, font=('Microsoft YaHei UI', 11),
                fg=self._quality_color(info), cursor='hand2')
            label._quality_color = self._quality_color(info)
            label._selected = bool(first.get('locked', False))
            label.pack(anchor='w', fill='x', pady=1)
            label.bind('<Button-1>',
                       lambda e, t=first: self._on_treasure_click(t))
            self._bind_warehouse_detail_frame(label, info)
        self._layout_two_columns(inner)


    def _toggle_treasure_lock_mode(self):
        self._treasure_lock_mode = not self._treasure_lock_mode
        self._refresh_warehouse_list()


    def _on_treasure_click(self, treasure):
        if not self._treasure_lock_mode:
            self._show_treasure_detail(treasure)
            return
        treasure['locked'] = not bool(treasure.get('locked', False))
        self._save_satiety()
        self._refresh_warehouse_list()
        self._refresh_market()


    def _show_treasure_detail(self, treasure):
        info = self._treasure_info(treasure)
        win = tk.Toplevel(self.root)
        win.title(info['name'])
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        win.after(80, lambda w=win: self._hide_from_taskbar(w))
        body = (
            f"名称：{info['name']}\n"
            f"品质：{info['quality']}\n"
            f"类型：宝藏\n"
            f"前缀：{treasure.get('prefix', '') or '无'}\n"
            f"基础价值：{treasure.get('base_value', 0)} G\n"
            f"市场价：{treasure.get('value', 0)} G\n"
            f"描述：探险中获得的战利品，可以在集市出售。"
        )
        make_label(win, text=body, justify='left',
                 font=('Microsoft YaHei UI', 10)).pack(padx=24, pady=16)
        self._place_popup_right_of_warehouse(win)


    def _place_popup_right_of_warehouse(self, win):
        if (self._warehouse_win is None
                or not self._warehouse_win.winfo_exists()):
            return
        win.update_idletasks()
        width = max(1, win.winfo_reqwidth())
        height = max(1, win.winfo_reqheight())
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = self._warehouse_win.winfo_rootx() + self._warehouse_win.winfo_width() + 8
        if x + width > screen_w:
            x = self._warehouse_win.winfo_rootx() - width - 8
        x = max(0, min(x, screen_w - width))
        y = self._warehouse_win.winfo_rooty() + 46
        y = max(0, min(y, screen_h - height - 40))
        win.geometry(f'+{x}+{y}')


    def _build_book_list(self, container, bg):
        """装备-书籍子页：选择当前生效的书籍。"""
        found = False
        for iid, info in ITEMS.items():
            if info.get('category') != '书籍':
                continue
            count = self.inventory.get(iid, 0)
            if count <= 0:
                continue
            found = True
            row = make_card(container, bg=bg)
            row.pack(fill='x', pady=2)
            row._quality_color = self._quality_color(info)
            row._quality_border_thick = True
            row._selected = iid in self._pending_books_enabled
            mark = '☑ ' if iid in self._pending_books_enabled else '☐ '
            book_text = f"{mark}{info['name']}"
            if count != 1:
                book_text += f' × {count}'
            lbl = make_label(row, text=book_text,
                           bg=bg, font=('Microsoft YaHei UI', 11),
                           fg=self._quality_color(info), cursor='hand2')
            lbl.pack(side='left')
            lbl.bind('<Button-1>', lambda e, i=iid: self._toggle_book(i))
            self._bind_warehouse_detail_frame(row, info)
        if not found:
            make_label(container, text='（空）', bg=bg,
                       fg='#999999').pack(anchor='w')
        self._layout_two_columns(container)


    def _build_special_list(self, container, bg):
        """装备-特殊子页：一次性道具（染发剂/美瞳/理发工具等）。

        点名称即走原来的使用入口（_on_item_click），行为与旧的「特殊」页一致。
        """
        found = False
        for iid, info in ITEMS.items():
            if info.get('category') != '特殊':
                continue
            count = self.inventory.get(iid, 0)
            if count <= 0:
                continue
            found = True
            row = make_card(container, bg=bg)
            row.pack(fill='x', pady=2)
            row._quality_color = self._quality_color(info)
            row._quality_border_thick = False
            row._selected = False
            lbl = make_label(row, text=f"{info['name']} × {count}",
                             bg=bg, font=('Microsoft YaHei UI', 11),
                             fg=self._quality_color(info), cursor='hand2')
            lbl.pack(side='left')
            lbl.bind('<Button-1>', lambda e, i=iid: self._on_item_click(i))
            self._bind_warehouse_detail_frame(row, info)
        if not found:
            make_label(container, text='（空）', bg=bg,
                       fg='#999999').pack(anchor='w')
        self._layout_two_columns(container)


    def _build_equipment_list(self, container, bg):
        """装备标签的右侧可选列表（按当前装备子页过滤）。"""
        if self._equip_slot == '书籍':
            self._build_book_list(container, bg)
            return
        if self._equip_slot == '特殊':
            self._build_special_list(container, bg)
            return
        found = False
        if self._equip_slot == '服装':
            cloth_info = {
                'normal': ('普通衣服', '粗劣', '日常穿着的普通衣服，款式简洁。'),
                'peasant': ('村民衣服', '普通', '朴素耐穿的村民日常服装。'),
                'thief': ('盗贼服', '少见', '轻便隐蔽的盗贼服装，适合潜行与探索。'),
                'knight': ('骑士服', '少见', '带有护甲的骑士服装，庄重而坚固。'),
                'hefu_blue': ('和服·蓝', '稀有', '蓝色的传统和服，款式宽松，袖子较长。'),
                'hefu_green': ('和服·绿', '稀有', '绿色的传统和服，款式宽松，袖子较长。'),
                'hefu_red': ('和服·红', '稀有', '红色的传统和服，款式宽松，袖子较长。'),
                'white_moon': ('白月服饰', '稀有', '兽族贵族宗教服饰，带有白色月纹。'),
                'black_sun': ('黑日服饰', '稀有', '兽族贵族宗教服饰，带有黑色日纹。'),
                'blue_noble': ('蓝色贵族服饰', '少见', '剪裁考究的蓝色贵族服饰。'),
                'clown': ('小丑服饰', '少见', '小丑职业的特色冒险服装，色彩鲜艳。'),
                'north_maid1': ('北境女仆装', '稀有', '来自北境的轻便女仆装。'),
                'north_night': ('北境夜行服', '史诗', '适合夜间行动的北境服装。'),
                'north_windbreaker': ('北境防风衣', '稀有', '能够抵御寒风的北境外套。'),
            }
            style_order = (
                'normal', 'peasant', 'thief', 'knight', 'hefu_blue',
                'hefu_green', 'hefu_red', 'white_moon', 'black_sun',
                'blue_noble', 'clown', 'north_maid1', 'north_night', 'north_windbreaker')
            for style in style_order:
                item_id = CLOTHES_ITEM_IDS.get(style)
                if (item_id is not None
                        and self.inventory.get(item_id, 0) <= 0):
                    continue
                found = True
                mark = '☑ ' if self._pending_clothes == style else '☐ '
                cname2, quality, desc = cloth_info[style]
                qcolor = QUALITY_COLORS.get(quality, THEME['border'])
                row = make_card(container, bg=bg)
                row.pack(fill='x', pady=1)
                row._quality_color = qcolor
                row._quality_border_thick = True
                row._selected = self._pending_clothes == style
                if style == 'normal':
                    make_button(
                        row, text='调节', width=6, padx=6, pady=2,
                        command=lambda: self._open_equipment_adjust('normal')
                    ).pack(side='right', padx=(4, 0))
                lbl = make_label(row, text=f'{mark}{cname2}',
                                 bg=bg, font=('Microsoft YaHei UI', 11),
                                 fg=qcolor, cursor='hand2', anchor='w',
                                 justify='left')
                lbl.pack(side='left', fill='x', expand=True)
                lbl.bind('<Button-1>',
                         lambda e, st=style: self._select_clothes(st))
                self._bind_warehouse_detail_frame(row, {
                    'name': cname2, 'quality': quality,
                    'category': '服装', 'kind': '服装', 'desc': desc})
        want = {'头饰': ('头饰',), '饰品': ('饰品',)}.get(
            self._equip_slot, ())
        selected = self._slot_item_ids(self._pending_slots, self._equip_slot)
        for iid, info in ITEMS.items():
            if info.get('category') not in want:
                continue
            if self.inventory.get(iid, 0) <= 0:
                continue
            found = True
            mark = '☑ ' if iid in selected else '☐ '
            row = make_card(container, bg=bg)
            row.pack(fill='x', pady=1)
            row._quality_color = self._quality_color(info)
            row._quality_border_thick = True
            row._selected = iid in selected
            controls = tk.Frame(row, bg=bg)
            controls.pack(side='right')
            lbl = make_label(row, text=f"{mark}{info['name']}",
                           bg=bg, font=('Microsoft YaHei UI', 11),
                           fg=self._quality_color(info), cursor='hand2')
            lbl.pack(side='left')
            lbl.bind('<Button-1>',
                     lambda e, i=iid, slot=self._equip_slot:
                     self._select_equip_item(i, slot))
            if iid in ADJUSTABLE_EQUIPMENT:
                make_button(
                    controls, text='调节', width=6, padx=6, pady=2,
                    command=lambda i=iid: self._open_equipment_adjust(i)
                ).pack(side='right', padx=(4, 0))
            self._bind_warehouse_detail_frame(row, info)
        if not found:
            make_label(container, text='（暂无装备）', bg=bg,
                     fg='#999999').pack(anchor='w')
        self._layout_two_columns(container)


    def _preview_food_gain(self):
        """当前选中食物按数量可获得的经验"""
        iid = getattr(self, '_selected_food', None)
        if iid is None:
            return 0
        spin = self._food_spins.get(iid)
        try:
            amount = max(1, int(spin.get()))
        except Exception:
            amount = 1
        return ITEMS.get(iid, {}).get('exp', 0) * amount


    def _select_food(self, item_id):
        """点击食物：立即刷新并开始闪烁预览可得经验"""
        self._selected_food = item_id
        self._exp_preview_gain = self._preview_food_gain()
        self._exp_flash_on = True
        self._refresh_exp_bar()
        if self._exp_flash_job is None:
            self._exp_flash_tick()


    def _on_food_qty(self, item_id):
        if getattr(self, '_selected_food', None) == item_id:
            self._exp_preview_gain = self._preview_food_gain()
            self._refresh_exp_bar()


    def _feed_from_warehouse(self, item_id):
        spin = self._food_spins.get(item_id)
        try:
            amount = max(1, int(spin.get()))
        except Exception:
            amount = 1
        self._selected_food = None
        self._stop_exp_flash()
        gained = self._use_food(item_id, amount)
        if getattr(self, '_equip_status', None) is not None:
            if gained:
                status = f'升级！Lv.{self.level}'
                if self._last_food_status and '吃坏' in self._last_food_status:
                    status += f'；{self._last_food_status}'
                self._equip_status.config(text=status)
            elif self._last_food_status:
                self._equip_status.config(text=self._last_food_status)


    def _use_consumable(self, item_id, amount=1):
        """使用消耗品（炼药产出的药水）：结算前缀带来的情绪/活力/持续时间。

        前缀的随机效果在使用时结算：残次品可能同时扣情绪、扣活力，
        档次还会缩放持续时间（药水没有持续时间时改为缩放效果）。
        """
        info = ITEMS.get(item_id)
        if info is None:
            return
        effect = info.get('use_effect') or {}
        if not effect:
            return
        have = int(self.inventory.get(item_id, 0) or 0)
        try:
            count = max(0, min(int(amount or 1), have))
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            self._alert('使用物品', '背包里已经没有这件物品了。')
            return
        InventoryService.remove(self.inventory, item_id, count)
        if (info.get('potion') or {}).get('base') == 'green_potion':
            StatsService.record_green_potion_use(self.game)
        emotion_delta = 0
        hp_loss = 0
        mask_ms = 0
        mask_key = effect.get('mask')
        tier_label = ''
        for _ in range(count):
            result = roll_potion_effect(info, self.max_hp)
            tier_label = result.get('tier_label', '')
            emotion_delta += int(result.get('emotion') or 0)
            hp_loss += int(result.get('hp_loss') or 0)
            if mask_key:
                mask_ms = max(mask_ms, int(result.get('duration_ms') or 0))
        if emotion_delta:
            self.emotion = max(0, min(100, self.emotion + emotion_delta))
        if hp_loss:
            self.hp = max(0, self.hp - hp_loss)
        if mask_key and mask_ms > 0:
            self.start_potion_mask(mask_key, mask_ms)
        name = info.get('name', item_id)
        status = f'使用{name} ×{count}'
        if tier_label:
            status += f'（{tier_label}）'
        status += '：' + format_effect_summary({
            'emotion': emotion_delta, 'hp_loss': hp_loss,
            'duration_ms': mask_ms})
        if getattr(self, '_equip_status', None) is not None:
            try:
                self._equip_status.config(text=status)
            except Exception:
                pass
        self._check_achievements()
        self._save_satiety()
        self._refresh_warehouse()
        self._check_hospital_state()

    def _show_overview(self):
        """总览：仅列出当前启用的内容。"""
        win = tk.Toplevel(self.root)
        win.title('总览')
        win.resizable(False, False)
        # 总览也算「页面」，同样留在任务栏里。
        self._show_in_taskbar(win)
        win.after(80, lambda w=win: self._show_in_taskbar(w))

        warehouse_open = bool(
            getattr(self, '_warehouse_win', None) is not None
            and self._warehouse_win.winfo_exists())
        if warehouse_open:
            slots = self._pending_slots
            books = self._pending_books_enabled
            clothes = self._pending_clothes
            hair_style = self._pending_hair_style
            hair_color = self._pending_hair_color
            eye_color = self._pending_eye_color
        else:
            slots = self.equipped_slots
            books = self.books_enabled
            clothes = self.equipped_clothes
            hair_style = self.hair_style
            hair_color = self.hair_color
            eye_color = self.eye_color

        def item_names(slot):
            ids = self._slot_item_ids(slots, slot)
            return [ITEMS.get(iid, {}).get('name', iid) for iid in ids]

        headwear = item_names('头饰')
        accessories = item_names('饰品')
        clothes_name = CLOTHES_NAMES.get(clothes, '普通衣服')
        hair_names = {
            'hair_1': '发型 1（原版）',
            'hair_1_1': '发型 2',
        }
        lines = ['当前启用内容']
        lines.append('头饰：' + ('、'.join(headwear) if headwear else '无'))
        lines.append(f'服装：{clothes_name}')
        lines.append('饰品：' + ('、'.join(accessories) if accessories else '无'))
        lines.append('发型：' + hair_names.get(hair_style, hair_style))
        enabled_books = [
            ITEMS.get(iid, {}).get('name', iid)
            for iid in EXPRESSION_BOOK_ORDER if iid in books]
        if enabled_books:
            lines.append('书籍：' + '、'.join(enabled_books))
        if hair_color:
            lines.append(f'发色：{hair_color}')
        if eye_color:
            lines.append(f'瞳色：{eye_color}')

        make_label(win, text='\n'.join(lines), justify='left',
                 font=('Microsoft YaHei UI', 10)).pack(padx=18, pady=14)
        make_button(win, text='关闭', width=8,
                  command=win.destroy).pack(pady=(0, 12))


    def _refresh_emotion_bar(self):
        """刷新仓库粉色情绪条。"""
        canvas = getattr(self, '_emotion_canvas', None)
        if canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                return
        except Exception:
            return
        ratio = max(0.0, min(1.0, self.emotion / 100.0))
        width = int(180 * ratio)
        canvas.delete('all')
        canvas.create_rectangle(1, 1, 181, 13, fill=THEME['card_alt'], outline='')
        if width > 0:
            canvas.create_rectangle(1, 1, 1 + width, 13,
                                    fill='#ff69b4', outline='')
        canvas.create_rectangle(1, 1, 181, 13, outline=THEME['border'])


    def _refresh_hp_bar(self):
        """刷新仓库红色活力条。"""
        canvas = getattr(self, '_hp_canvas', None)
        if canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                return
        except Exception:
            return
        ratio = max(0.0, min(1.0, self.hp / max(1, self.max_hp)))
        width = int(180 * ratio)
        canvas.delete('all')
        canvas.create_rectangle(1, 1, 181, 13, fill=THEME['card_alt'], outline='')
        if width > 0:
            canvas.create_rectangle(1, 1, 1 + width, 13,
                                    fill=THEME['danger'], outline='')
        canvas.create_rectangle(1, 1, 181, 13, outline=THEME['border'])


    def _refresh_exp_bar(self):
        """刷新经验条：灰底 + 绿色当前经验 + 闪烁的进食预览段"""
        if getattr(self, '_exp_canvas', None) is None:
            return
        try:
            if not self._exp_canvas.winfo_exists():
                return
        except Exception:
            return
        need = max(1, self._xp_to_next())
        ratio = max(0.0, min(1.0, self.exp / need))
        bar_width = max(40, int(getattr(self, '_exp_bar_width', 180)))
        right = bar_width + 1
        w = int(bar_width * ratio)
        c = self._exp_canvas
        c.delete('all')
        gain = getattr(self, '_exp_preview_gain', 0)
        border = ('#1abc9c' if (gain > 0 and getattr(self, '_exp_flash_on', False))
                  else THEME['border'])
        c.create_rectangle(1, 1, right, 13, fill=THEME['card_alt'], outline='')
        if w > 0:
            c.create_rectangle(1, 1, 1 + w, 13, fill=THEME['success'], outline='')
        if gain > 0 and getattr(self, '_exp_flash_on', False):
            w2 = int(bar_width * min(1.0, (self.exp + gain) / need))
            if w2 > w:
                c.create_rectangle(1 + w, 1, 1 + w2, 13,
                                   fill='#7dff9b', outline='')
        c.create_rectangle(1, 1, right, 13, outline=border, width=2)
        if getattr(self, '_exp_level_label', None) is not None:
            self._exp_level_label.config(text=f'Lv.{self.level}')


    def _exp_flash_tick(self):
        """经验条闪烁（表示进食可获得经验）"""
        self._exp_flash_job = None
        if (self._warehouse_win is None
                or not self._warehouse_win.winfo_exists()
                or getattr(self, '_selected_food', None) is None):
            self._exp_flash_on = False
            return
        self._exp_flash_on = not self._exp_flash_on
        self._exp_preview_gain = self._preview_food_gain()
        self._refresh_exp_bar()
        self._exp_flash_job = self.root.after(260, self._exp_flash_tick)


    def _stop_exp_flash(self, refresh=True):
        if getattr(self, '_exp_flash_job', None) is not None:
            try:
                self.root.after_cancel(self._exp_flash_job)
            except Exception:
                pass
            self._exp_flash_job = None
        self._exp_flash_on = False
        self._exp_preview_gain = 0
        if refresh:
            self._refresh_exp_bar()


    def _equip_stats_update(self):
        label = getattr(self, '_equip_stats_label', None)
        if label is None:
            return
        try:
            if not label.winfo_exists():
                return
        except Exception:
            return
        try:
            label.config(
                text=f'力量 {self.strength}　智慧 {self.wisdom}'
                     f'　敏捷 {self.agility}')
        except Exception:
            pass



    def _preview_window_alive(self):
        for attr in ('_warehouse_win', '_adventure_win', '_workstation_win'):
            win = getattr(self, attr, None)
            if win is not None:
                try:
                    if win.winfo_exists():
                        return True
                except Exception:
                    pass
        return False

    def _start_preview_actions(self):
        """启动仓库/探险页的独立眨眼动画。"""
        self._stop_preview_actions()
        self._schedule_preview_action()


    def _schedule_preview_action(self):
        if not self._preview_window_alive():
            return
        self._preview_anim_job = self.root.after(
            random.randint(1800, 4200), self._do_preview_action)


    def _do_preview_action(self):
        self._preview_anim_job = None
        if not self._preview_window_alive():
            return
        books = (self._pending_books_enabled
                 if getattr(self, '_preview_source', 'pending') == 'pending'
                 else self.books_enabled)
        if 'expression_comfy' in books:
            self._schedule_preview_action()
            return
        frames = [('blink', 160, 0.0), ('normal', 0, 0.0)]
        self._run_preview_frames(frames)


    def _run_preview_frames(self, frames):
        if not self._preview_window_alive():
            return
        if not frames:
            self._schedule_preview_action()
            return
        pose, delay, tilt = frames[0]
        self._preview_pose = pose
        self._preview_tail_tilt = tilt
        self._equip_preview_update()
        self._preview_anim_job = self.root.after(
            max(1, delay), lambda: self._run_preview_frames(frames[1:]))


    def _stop_preview_actions(self):
        self._stop_preview_bounce()
        if getattr(self, '_preview_anim_job', None) is not None:
            try:
                self.root.after_cancel(self._preview_anim_job)
            except Exception:
                pass
            self._preview_anim_job = None


    def _preview_background(self, key=None):
        cache = getattr(self, '_background_cache', None)
        if cache is None:
            cache = {}
            self._background_cache = cache
        override = key is not None
        if not override:
            key = getattr(self.game, 'selected_background', 'market')
            if key not in getattr(self.game, 'backgrounds', {'market'}):
                key = 'market'
        elif key not in BACKGROUND_PATHS:
            key = 'market'
        if key in cache:
            return cache[key].copy()
        path = BACKGROUND_PATHS.get(key) or BACKGROUND_PATHS['market']
        image = PIL.Image.open(path).convert('RGBA')
        image = image.resize(
            (PREVIEW_FRAME_SIZE, PREVIEW_FRAME_SIZE),
            PIL.Image.Resampling.LANCZOS)
        pixels = image.load()
        border = 18
        levels = max(1, border // 3)
        for y in range(PREVIEW_FRAME_SIZE):
            for x in range(PREVIEW_FRAME_SIZE):
                distance = min(
                    x, y,
                    PREVIEW_FRAME_SIZE - 1 - x,
                    PREVIEW_FRAME_SIZE - 1 - y)
                if distance < border:
                    step = distance // 3
                    alpha = int(255 * min(levels, step + 1) / levels)
                    r, g, b, _ = pixels[x, y]
                    pixels[x, y] = (r, g, b, alpha)
        cache[key] = image.copy()
        return image

    def _cycle_background(self, step):
        available = [key for key in BACKGROUND_ORDER
                     if key in getattr(self.game, 'backgrounds', {'market'})]
        if len(available) <= 1:
            return
        current = getattr(self.game, 'selected_background', 'market')
        try:
            index = available.index(current)
        except ValueError:
            index = 0
        self.game.selected_background = available[(index + step) % len(available)]
        self._save_satiety()
        self._equip_preview_update()

    def _equip_preview_update(self):
        self._equip_stats_update()
        label = getattr(self, '_equip_preview_label', None)
        if label is None:
            return
        try:
            if not label.winfo_exists():
                return
        except Exception:
            return
        try:
            img = self._full_for(
                self._preview_pose,
                clothes_style=(self.equipped_clothes if getattr(self, '_preview_source', 'pending') == 'live' else self._pending_clothes),
                tail_tilt=self._preview_tail_tilt,
                hair_color=(self.hair_color if getattr(self, '_preview_source', 'pending') == 'live' else self._pending_hair_color),
                eye_color=(self.eye_color if getattr(self, '_preview_source', 'pending') == 'live' else self._pending_eye_color),
                clothes_color=(self.normal_clothes_color if getattr(self, '_preview_source', 'pending') == 'live' else self._pending_normal_clothes_color),
                equipment_slots=(self.equipped_slots if getattr(self, '_preview_source', 'pending') == 'live' else self._pending_slots),
                equipment_settings=(self.equip_settings if getattr(self, '_preview_source', 'pending') == 'live' else self._pending_equip_settings),
                hair_style=(self.hair_style if getattr(self, '_preview_source', 'pending') == 'live' else self._pending_hair_style),
                expression_books=(self.books_enabled if getattr(self, '_preview_source', 'pending') == 'live' else self._pending_books_enabled),
                preview_mode=True)
            if self._preview_facing:
                img = img.transpose(PIL.Image.FLIP_LEFT_RIGHT)
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
            scale_x, scale_y = getattr(
                self, '_preview_bounce_scale', (1.0, 1.0))
            cat_size = int(getattr(self, '_preview_cat_size', 0)
                           or PREVIEW_CAT_SIZE)
            fit_scale = min(
                cat_size / float(max(1, img.width)),
                cat_size / float(max(1, img.height)))
            target_w = max(1, int(round(img.width * fit_scale * scale_x)))
            target_h = max(1, int(round(img.height * fit_scale * scale_y)))
            cat = img.resize(
                (target_w, target_h), PIL.Image.Resampling.LANCZOS)
            preview = self._preview_background(
                getattr(self, '_preview_background_key', None))
            anchor = getattr(self, '_preview_anchor', None)
            if anchor:
                # 炼药页等固定布景：把模特摆到布景指定的落脚点上。
                anchor_x, anchor_y = anchor
                offset_x = int(round(anchor_x - target_w / 2))
                offset_y = int(round(anchor_y - target_h))
            else:
                offset_x = (PREVIEW_FRAME_SIZE - target_w) // 2
                bottom = PREVIEW_FRAME_SIZE - PREVIEW_CAT_BOTTOM_MARGIN
                offset_y = bottom - target_h
            preview.alpha_composite(cat, (max(0, offset_x), max(0, offset_y)))
            self._equip_preview_photo = PIL.ImageTk.PhotoImage(preview)
            self._equip_preview_label.config(image=self._equip_preview_photo)
        except Exception:
            pass


    def _preview_click_bounce(self, event=None):
        if not self._preview_window_alive():
            return
        self._stop_preview_bounce()
        self._preview_bounce_frames = list(PREVIEW_BOUNCE_FRAMES)
        self._preview_bounce_step()

    def _preview_bounce_step(self):
        self._preview_bounce_job = None
        if not self._preview_window_alive():
            self._preview_bounce_scale = (1.0, 1.0)
            return
        frames = getattr(self, '_preview_bounce_frames', [])
        if not frames:
            self._preview_bounce_scale = (1.0, 1.0)
            self._equip_preview_update()
            return
        self._preview_bounce_scale = frames.pop(0)
        self._equip_preview_update()
        self._preview_bounce_job = self.root.after(
            42, self._preview_bounce_step)

    def _stop_preview_bounce(self):
        job = getattr(self, '_preview_bounce_job', None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._preview_bounce_job = None

    def _equip_preview_motion(self, event):
        """光标在预览框左侧→朝左，右侧→朝右（仓库窗口内移动即生效）"""
        label = getattr(self, '_equip_preview_label', None)
        if label is None:
            return
        try:
            center_x = label.winfo_rootx() + label.winfo_width() / 2
        except Exception:
            return
        face_right = event.x_root >= center_x
        if face_right != self._preview_facing:
            self._preview_facing = face_right
            self._equip_preview_update()


    def _select_clothes(self, style):
        self._pending_clothes = style
        self._equip_preview_update()
        self._refresh_warehouse_list()


    def _select_equip_item(self, item_id, slot):
        """头饰/饰品支持多选，但不同物品不能占用同一隐藏属性。"""
        if slot in ('头饰', '饰品'):
            selected = self._slot_item_ids(self._pending_slots, slot)
            if item_id in selected:
                selected.remove(item_id)
            else:
                new_attr = ITEMS.get(item_id, {}).get('hidden_attribute')
                if new_attr:
                    for other_slot in ('头饰', '饰品'):
                        other_items = self._slot_item_ids(
                            self._pending_slots, other_slot)
                        other_items = [
                            iid for iid in other_items
                            if ITEMS.get(iid, {}).get('hidden_attribute')
                            != new_attr
                        ]
                        self._pending_slots[other_slot] = other_items
                    selected = self._slot_item_ids(self._pending_slots, slot)
                selected.append(item_id)
            self._pending_slots[slot] = selected
        else:
            self._pending_slots[slot] = item_id
        self._equip_preview_update()
        self._refresh_warehouse_list()


    def _set_collar_style(self, style):
        self._pending_equip_settings['collar_style'] = (
            2 if int(style) == 2 else 1)
        self._equip_preview_update()
        self._refresh_warehouse_list()


    def _ensure_item_selected(self, item_id, slot):
        selected = self._slot_item_ids(self._pending_slots, slot)
        if item_id not in selected:
            self._select_equip_item(item_id, slot)

    def _open_item_color(self, item_id, slot, kind):
        self._ensure_item_selected(item_id, slot)
        self._open_color_palette(kind)

    def _open_equipment_adjust(self, item_id):
        if item_id == 'normal':
            self._pending_clothes = 'normal'
            self._equip_preview_update()
            self._refresh_warehouse_list()
        elif item_id in ('hair_dye', 'lens', 'throat_lozenge'):
            name = ITEMS.get(item_id, {}).get('name', item_id)
            if self.inventory.get(item_id, 0) <= 0:
                self._alert(name, f'没有{name}了，去集市买一个吧。')
                return
        else:
            info = ITEMS.get(item_id) or {}
            slot = info.get('category')
            if slot in ('头饰', '饰品'):
                self._ensure_item_selected(item_id, slot)
        self._adjust_item_id = item_id
        self._show_equipment_adjust_panel(item_id)

    def _show_equipment_adjust_panel(self, item_id):
        outer = getattr(self, '_adjust_wrap', None)
        content = getattr(self, '_adjust_content', None)
        if outer is None or content is None:
            return
        for child in content.winfo_children():
            child.destroy()
        self._equip_subbar.pack_forget()
        self._warehouse_list_wrap.pack_forget()
        outer.pack(fill='both', expand=True, padx=14, pady=14)
        if item_id == 'normal':
            detail_info = {
                'name': '普通衣服', 'quality': '粗劣', 'category': '服装',
                'kind': '服装', 'desc': '日常穿着的普通衣服，款式简洁。'}
        else:
            detail_info = ITEMS.get(item_id, {})
        if item_id == 'throat_lozenge':
            detail_info = CLICK_SOUND_CATALOG.get(
                getattr(self, '_pending_click_sound', self.click_sound),
                CLICK_SOUND_CATALOG['cat1'])
        if detail_info:
            self._show_warehouse_detail(detail_info, pinned=True)
        wrap = content
        titles = {
            'sunglasses': '太阳镜调节', 'gold_earrings': '耳环调节',
            'hat_1': '鸭舌帽调节', 'hat_ji': '小鸡头饰调节',
            'hat_2': '小洋帽调节', 'fine_collar': '项圈调节',
            'normal': '普通衣服调节',
            'hair_dye': '染发剂调节',
            'lens': '美瞳片调节',
            'throat_lozenge': '润喉糖·音效调整',
        }
        header = tk.Frame(wrap, bg=THEME['card'])
        header.pack(fill='x', pady=(0, 10))
        make_button(header, ' 返回', self._return_to_equipment_list,
                    kind='ghost', width=8).pack(side='left')
        make_label(header, '调节', style='title',
                   bg=THEME['card']).pack(side='left', padx=(12, 0))
        if item_id == 'sunglasses':
            self._inline_scale(
                wrap, '垂直位置', 0, 360, 1,
                int(self._pending_equip_settings.get('sunglasses_y_offset', 80)),
                self._preview_sunglasses_offset)
        elif item_id == 'gold_earrings':
            self._inline_color_section(wrap, 'earrings', '耳环颜色')
        elif item_id == 'hat_1':
            self._inline_color_section(wrap, 'hat_1', '帽身颜色')
        elif item_id == 'hat_ji':
            self._inline_scale(
                wrap, '头饰大小', 0.5, 1.5, 0.05,
                float(self._pending_equip_settings.get('hat_ji_scale', 0.8)),
                self._preview_hat_ji_scale)
            self._inline_color_section(wrap, 'hat_ji', '小鸡颜色')
        elif item_id == 'hat_2':
            self._inline_color_section(wrap, 'hat_2_cream', '米白部分')
            self._inline_color_section(wrap, 'hat_2_brown', '棕色部分')
        elif item_id == 'fine_collar':
            make_label(wrap, '项圈款式', bg=THEME['card']).pack(anchor='w', pady=(6, 4))
            style_bar = tk.Frame(wrap, bg=THEME['card'])
            style_bar.pack(anchor='w', pady=(0, 8))
            make_button(style_bar, '款式一', lambda: self._set_collar_style(1),
                        kind='secondary', width=8).pack(side='left', padx=(0, 5))
            make_button(style_bar, '款式二', lambda: self._set_collar_style(2),
                        kind='secondary', width=8).pack(side='left')
            colors_row = tk.Frame(wrap, bg=THEME['card'])
            colors_row.pack(fill='x', pady=(4, 0))
            rope_panel = tk.Frame(colors_row, bg=THEME['card'])
            rope_panel.pack(side='left', anchor='n')
            deco_panel = tk.Frame(colors_row, bg=THEME['card'])
            deco_panel.pack(side='right', anchor='ne')
            self._inline_color_section(
                rope_panel, 'collar_rope', '绳子颜色')
            self._inline_color_section(
                deco_panel, 'collar_deco', '装饰颜色')
        elif item_id == 'normal':
            self._inline_color_section(wrap, 'clothes', '衣服颜色')
        elif item_id == 'hair_dye':
            self._inline_color_section(wrap, 'hair', '发色', HAIR_COLORS)
        elif item_id == 'lens':
            self._inline_color_section(wrap, 'eye', '瞳色', EYE_COLORS)
        elif item_id == 'throat_lozenge':
            self._build_click_sound_selector(wrap)

    def _close_equipment_adjust_panel(self):
        self._pinned_warehouse_detail = None
        wrap = getattr(self, '_adjust_wrap', None)
        if wrap is not None:
            wrap.pack_forget()
        list_wrap = getattr(self, '_warehouse_list_wrap', None)
        if (list_wrap is not None
                and not list_wrap.winfo_manager()):
            list_wrap.pack(fill='both', expand=True, padx=14, pady=14)

    def _return_to_equipment_list(self):
        self._close_equipment_adjust_panel()
        if self._warehouse_cat in ('装备', '物品'):
            self._equip_subbar.pack(
                fill='x', pady=(0, 4), before=self._warehouse_list_wrap)
        else:
            self._equip_subbar.pack_forget()
        self._refresh_warehouse_list()

    def _inline_scale(self, parent, title, from_, to, resolution, value, callback):
        make_label(parent, title, bg=THEME['card']).pack(anchor='w', pady=(4, 2))
        scale = tk.Scale(
            parent, from_=from_, to=to, resolution=resolution,
            orient='horizontal', length=360, bg=THEME['card'],
            fg=THEME['text'], troughcolor=THEME['card_alt'],
            highlightthickness=0, activebackground=THEME['accent'],
            command=callback)
        scale.set(value)
        scale.pack(fill='x', pady=(0, 10))

    def _inline_color_section(self, parent, kind, title, palette=None):
        make_label(parent, title, bg=THEME['card']).pack(anchor='w', pady=(6, 3))
        grid = tk.Frame(parent, bg=THEME['card'])
        grid.pack(anchor='w')
        for index, color in enumerate(palette or HAIR_COLORS):
            make_button(
                grid, '', lambda c=color, k=kind: self._inline_pick_equipment_color(k, c),
                bg=color, width=3, height=1, padx=0, pady=0
            ).grid(row=index // 8, column=index % 8, padx=2, pady=2)
        make_button(parent, '还原默认颜色',
                    lambda k=kind: self._inline_reset_equipment_color(k),
                    kind='ghost', width=12).pack(anchor='w', pady=(5, 2))

    def _build_click_sound_selector(self, parent):
        """润喉糖音效页：试听并选择单击音效。"""
        make_label(
            parent, '选择单击音效', bg=THEME['card'],
            font=(FONT_FAMILY, 11, 'bold')).pack(
                anchor='w', pady=(4, 6))
        current = getattr(self, '_pending_click_sound', self.click_sound)
        for sound_key in CLICK_SOUND_ORDER:
            info = CLICK_SOUND_CATALOG[sound_key]
            selected = sound_key == current
            row = make_card(parent, bg=THEME['card'])
            row.pack(fill='x', pady=3)
            row.configure(
                highlightthickness=2 if selected else 1,
                highlightbackground=(THEME['accent'] if selected
                                     else info['quality_color']),
                highlightcolor=(THEME['accent'] if selected
                                else info['quality_color']))
            controls = tk.Frame(row, bg=THEME['card'])
            controls.pack(side='right', padx=(6, 6), pady=5)
            make_button(
                controls, '试听',
                command=lambda key=sound_key: self._preview_click_sound(key),
                kind='secondary', width=5).pack(side='left', padx=(0, 4))
            make_button(
                controls, '选择',
                command=lambda key=sound_key: self._select_click_sound(key),
                kind='primary' if not selected else 'secondary',
                width=5).pack(side='left')
            mark = '☑ ' if selected else '☐ '
            name_label = make_label(
                row, mark + info['name'], bg=THEME['card'],
                fg=info['quality_color'],
                font=('Microsoft YaHei UI', 11, 'bold'),
                cursor='hand2', anchor='w')
            name_label.pack(side='left', padx=(8, 4), pady=(6, 1))
            quality_label = make_label(
                row, f"品质：{info['quality']}", bg=THEME['card'],
                fg=info['quality_color'], cursor='hand2', anchor='w')
            quality_label.pack(side='left', padx=(0, 8), pady=(6, 1))
            for widget in (row, name_label, quality_label):
                widget.bind(
                    '<Button-1>',
                    lambda e, key=sound_key: self._select_click_sound(key))
            self._bind_warehouse_detail_frame(row, info)
        make_label(
            parent,
            '试听不会消耗润喉糖；选择后点击仓库“确定”才会替换音效。',
            bg=THEME['card'], fg=THEME['muted'],
            style='small', justify='left', wraplength=460).pack(
                anchor='w', pady=(8, 2))


    def _preview_click_sound(self, sound_key):
        """试听指定单击音效，不改变当前选择。"""
        info = CLICK_SOUND_CATALOG.get(sound_key)
        if info is None:
            return
        self._show_warehouse_detail(info, pinned=True)
        self._audition_click_sound(sound_key)


    def _select_click_sound(self, sound_key):
        """暂存润喉糖选择的单击音效。"""
        if sound_key not in CLICK_SOUND_CATALOG:
            return
        self._pending_click_sound = sound_key
        if sound_key == self.click_sound:
            self._pending_item_uses.pop('throat_lozenge', None)
        else:
            self._pending_item_uses['throat_lozenge'] = 1
        if getattr(self, '_equip_status', None) is not None:
            self._equip_status.config(text='音效已选择，点击确定应用')
        self._show_equipment_adjust_panel('throat_lozenge')


    def _sync_color_item_use(self, kind):
        item_id = {'hair': 'hair_dye', 'eye': 'lens'}.get(kind)
        if item_id is None:
            return
        changed = self._palette_current_pending(kind) != getattr(
            self, 'hair_color' if kind == 'hair' else 'eye_color', None)
        if changed:
            self._pending_item_uses[item_id] = 1
        else:
            self._pending_item_uses.pop(item_id, None)

    def _inline_pick_equipment_color(self, kind, color):
        if kind in ('hair', 'eye'):
            item_id = 'hair_dye' if kind == 'hair' else 'lens'
            if (self.inventory.get(item_id, 0) <= 0
                    and item_id not in self._pending_item_uses):
                name = ITEMS.get(item_id, {}).get('name', item_id)
                self._alert(name, f'没有{name}了，去集市买一个吧。')
                return
            self._palette_set_pending(kind, color)
            self._sync_color_item_use(kind)
            self._equip_preview_update()
            if getattr(self, '_equip_status', None) is not None:
                self._equip_status.config(text='颜色已预览，点击确定应用')
            return
        self._palette_set_pending(kind, color)
        self._mark_equipment_color_change(kind)
        self._equip_preview_update()
        dye_have = max(0, int(self.inventory.get('dye', 0)))
        dye_need = len(self._pending_color_changes)
        if dye_need > dye_have:
            self._show_dye_shortage_dialog(dye_need - dye_have, dye_have)
        if getattr(self, '_equip_status', None) is not None:
            self._equip_status.config(text='颜色已预览，点击确定应用')

    def _inline_reset_equipment_color(self, kind):
        self._palette_kind = kind
        self._palette_restore()
        if kind in ('hair', 'eye'):
            self._sync_color_item_use(kind)
        if getattr(self, '_equip_status', None) is not None:
            self._equip_status.config(text='颜色已还原，点击确定应用')

    def _open_normal_clothes_palette(self):
        self._select_clothes('normal')
        self._open_color_palette('clothes')

    def _open_sunglasses_for_item(self):
        self._ensure_item_selected('sunglasses', '头饰')
        self._open_sunglasses_adjust()

    def _open_hat_scale_for_item(self):
        self._ensure_item_selected('hat_ji', '头饰')
        self._open_hat_ji_scale()

    def _open_sunglasses_adjust(self):
        """太阳镜垂直位置调节条。"""
        win = getattr(self, '_sunglasses_adjust_win', None)
        if win is not None and win.winfo_exists():
            win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title('太阳镜位置')
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        self._sunglasses_adjust_win = win
        current = int(self._pending_equip_settings.get(
            'sunglasses_y_offset', 80))
        self._sunglasses_offset_original = current
        make_label(win, text='向下移动太阳镜',
                 font=('Microsoft YaHei UI', 10)).pack(padx=16, pady=(12, 2))
        scale = tk.Scale(
            win, from_=0, to=360, orient='horizontal', length=260,
            resolution=1, command=self._preview_sunglasses_offset)
        scale.set(current)
        scale.pack(padx=16, pady=4)
        bar = tk.Frame(win)
        bar.pack(pady=(4, 12))
        make_button(bar, text='还原', width=7,
                  command=lambda: scale.set(80)).pack(side='left', padx=4)
        make_button(bar, text='确定', width=7,
                  command=self._confirm_sunglasses_adjust).pack(
                      side='left', padx=4)
        make_button(bar, text='取消', width=7,
                  command=self._cancel_sunglasses_adjust).pack(
                      side='left', padx=4)
        win.protocol('WM_DELETE_WINDOW', self._cancel_sunglasses_adjust)
        try:
            win.update_idletasks()
            if (self._warehouse_win is not None
                    and self._warehouse_win.winfo_exists()):
                x = self._warehouse_win.winfo_x() + \
                    self._warehouse_win.winfo_width() + 8
                y = self._warehouse_win.winfo_y()
                sw = win.winfo_screenwidth()
                sh = win.winfo_screenheight()
                x = max(0, min(x, sw - win.winfo_width()))
                y = max(0, min(y, sh - win.winfo_height()))
                win.geometry(f'+{int(x)}+{int(y)}')
        except Exception:
            pass


    def _preview_sunglasses_offset(self, value):
        try:
            offset = max(0, min(360, int(float(value))))
        except (TypeError, ValueError):
            return
        self._pending_equip_settings['sunglasses_y_offset'] = offset
        self._equip_preview_update()


    def _confirm_sunglasses_adjust(self):
        self._equip_preview_update()
        self._destroy_sunglasses_adjust()
        if getattr(self, '_equip_status', None) is not None:
            self._equip_status.config(text='位置已预览，点击确定应用')


    def _cancel_sunglasses_adjust(self):
        self._pending_equip_settings['sunglasses_y_offset'] = int(
            getattr(self, '_sunglasses_offset_original',
                    self.equip_settings.get('sunglasses_y_offset', 80)))
        self._equip_preview_update()
        self._destroy_sunglasses_adjust()


    def _destroy_sunglasses_adjust(self):
        win = getattr(self, '_sunglasses_adjust_win', None)
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass
        self._sunglasses_adjust_win = None


    def _open_hat_ji_scale(self):
        """调整小鸡头饰大小，等待仓库确定。"""
        win = getattr(self, '_hat_scale_win', None)
        if win is not None and win.winfo_exists():
            win.lift()
            return
        try:
            self._hat_ji_scale_original = max(0.8, min(
                1.1, float(self._pending_equip_settings.get(
                    'hat_ji_scale', 0.8))))
        except (TypeError, ValueError):
            self._hat_ji_scale_original = 0.8
        win = tk.Toplevel(self.root)
        win.title('小鸡头饰大小')
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        self._hat_scale_win = win
        make_label(win, text='调整一只小鸡的大小',
                 font=('Microsoft YaHei UI', 10)).pack(padx=16, pady=(12, 2))
        scale = tk.Scale(
            win, from_=0.8, to=1.1, resolution=0.05,
            orient='horizontal', length=250,
            command=self._preview_hat_ji_scale)
        scale.set(self._hat_ji_scale_original)
        scale.pack(padx=16, pady=4)
        bar = tk.Frame(win)
        bar.pack(pady=(4, 12))
        make_button(bar, text='确定', width=8,
                  command=self._confirm_hat_ji_scale).pack(
                      side='left', padx=4)
        make_button(bar, text='取消', width=8,
                  command=self._cancel_hat_ji_scale).pack(
                      side='left', padx=4)
        win.protocol('WM_DELETE_WINDOW', self._cancel_hat_ji_scale)


    def _preview_hat_ji_scale(self, value):
        try:
            value = max(0.8, min(1.1, float(value)))
        except (TypeError, ValueError):
            return
        self._pending_equip_settings['hat_ji_scale'] = value
        self._equip_preview_update()


    def _confirm_hat_ji_scale(self):
        self._equip_preview_update()
        self._destroy_hat_scale()
        if getattr(self, '_equip_status', None) is not None:
            self._equip_status.config(text='大小已预览，点击确定应用')


    def _cancel_hat_ji_scale(self):
        self._pending_equip_settings['hat_ji_scale'] = getattr(
            self, '_hat_ji_scale_original',
            self.equip_settings.get('hat_ji_scale', 0.8))
        self._equip_preview_update()
        self._destroy_hat_scale()


    def _destroy_hat_scale(self):
        win = getattr(self, '_hat_scale_win', None)
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass
        self._hat_scale_win = None


    def _reset_pending_warehouse(self):
        """从当前生效状态重建仓库待确认快照。"""
        self._pending_slots = {
            key: list(value) if isinstance(value, list) else value
            for key, value in self.equipped_slots.items()
        }
        self._pending_equip_settings = dict(self.equip_settings)
        self._pending_clothes = self.equipped_clothes
        self._pending_books_enabled = set(self.books_enabled)
        self._pending_hair_style = self.hair_style
        self._pending_hair_color = self.hair_color
        self._pending_eye_color = self.eye_color
        self._pending_normal_clothes_color = self.normal_clothes_color
        self._pending_item_uses = {}
        self._pending_click_sound = self.click_sound
        self._pending_color_changes = set()


    def _color_change_item_key(self, kind):
        if kind in ('collar_rope', 'collar_deco'):
            return 'fine_collar'
        if kind in ('hat_2_brown', 'hat_2_cream'):
            return 'hat_2'
        return kind


    def _mark_equipment_color_change(self, kind):
        key = self._color_change_item_key(kind)
        if kind == 'clothes':
            changed = (self._pending_normal_clothes_color
                       != self.normal_clothes_color)
        elif kind in ('collar_rope', 'collar_deco'):
            changed = (
                self._pending_equip_settings.get('collar_rope_color')
                != self.equip_settings.get('collar_rope_color')
                or self._pending_equip_settings.get('collar_deco_color')
                != self.equip_settings.get('collar_deco_color'))
        elif kind in ('hat_2_brown', 'hat_2_cream'):
            changed = (
                self._pending_equip_settings.get('hat_2_brown_color')
                != self.equip_settings.get('hat_2_brown_color')
                or self._pending_equip_settings.get('hat_2_cream_color')
                != self.equip_settings.get('hat_2_cream_color'))
        else:
            field = {
                'earrings': 'earrings_color',
                'hat_1': 'hat_1_color',
                'hat_ji': 'hat_ji_color',
            }.get(kind)
            changed = (self._pending_equip_settings.get(field)
                       != self.equip_settings.get(field))
        if changed:
            self._pending_color_changes.add(key)
        else:
            self._pending_color_changes.discard(key)


    def _required_pending_items(self):
        required = dict(self._pending_item_uses)
        if self._pending_color_changes:
            required['dye'] = max(
                required.get('dye', 0), len(self._pending_color_changes))
        return required


    def _has_pending_warehouse_changes(self):
        return (
            self._pending_slots != self.equipped_slots
            or self._pending_clothes != self.equipped_clothes
            or self._pending_equip_settings != self.equip_settings
            or self._pending_books_enabled != self.books_enabled
            or self._pending_hair_style != self.hair_style
            or self._pending_hair_color != self.hair_color
            or self._pending_eye_color != self.eye_color
            or (self._pending_normal_clothes_color
                != self.normal_clothes_color)
            or self._pending_click_sound != self.click_sound
            or bool(self._pending_item_uses)
            or bool(self._pending_color_changes)
        )


    def _discard_transient_editors(self):
        if getattr(self, '_palette_win', None) is not None:
            self._close_palette()
        if getattr(self, '_sunglasses_adjust_win', None) is not None:
            self._cancel_sunglasses_adjust()
        if getattr(self, '_hat_scale_win', None) is not None:
            self._cancel_hat_ji_scale()
        if getattr(self, '_hairstyle_win', None) is not None:
            self._discard_hairstyle_dialog()


    def _confirm_equipment(self):
        """应用仓库全部待确认变更，并在此刻消耗道具。"""
        self._discard_transient_editors()
        if not self._has_pending_warehouse_changes():
            if getattr(self, '_equip_status', None) is not None:
                self._equip_status.config(text='没有需要确定的变更')
            return True
        required = self._required_pending_items()
        missing = {}
        for iid, amount in required.items():
            have = max(0, int(self.inventory.get(iid, 0)))
            if have < amount:
                missing[iid] = (f"{ITEMS.get(iid, {}).get('name', iid)} "
                                f"需要 {amount} 个，当前 {have} 个")
        if missing:
            dye_amount = int(required.get('dye', 0))
            dye_have = max(0, int(self.inventory.get('dye', 0)))
            if dye_amount > dye_have:
                other_missing = [
                    text for iid, text in missing.items()
                    if iid != 'dye'
                ]
                self._show_dye_shortage_dialog(
                    dye_amount - dye_have, dye_have, other_missing)
            else:
                self._alert('道具不足', '\n'.join(missing.values()))
            return False
        for iid, amount in required.items():
            self.inventory[iid] = max(
                0, int(self.inventory.get(iid, 0)) - amount)
        self.equipped_slots = {
            key: list(value) if isinstance(value, list) else value
            for key, value in self._pending_slots.items()
        }
        self.equip_settings = dict(self._pending_equip_settings)
        self.equipped_clothes = self._pending_clothes
        self.books_enabled = set(self._pending_books_enabled)
        self.hair_style = self._pending_hair_style
        self.hair_color = self._pending_hair_color
        self.eye_color = self._pending_eye_color
        self.normal_clothes_color = self._pending_normal_clothes_color
        if self._pending_click_sound != self.click_sound:
            self.click_sound = self._pending_click_sound
            self._active_click_sound_path = CLICK_SOUND_PATHS[self.click_sound]
            self.game.click_sound = self.click_sound
            self._click_sound_cache_key = None
            self._click_sound_paths = None
        self.facing_right = self._preview_facing
        self._hair_cache.clear()
        self._eye_cache.clear()
        self._clothes_color_cache.clear()
        self._collar_color_cache.clear()
        self._earring_color_cache.clear()
        self._hat_color_cache.clear()
        self._click_expression = None
        self._reset_pending_warehouse()
        self._save_satiety()
        self.update_image()
        self._refresh_warehouse()
        if getattr(self, '_equip_status', None) is not None:
            self._equip_status.config(text='已确定并保存')
        return True


    def _pending_dye_item_names(self):
        names = {
            'clothes': '普通衣服',
            'earrings': '耳环',
            'fine_collar': '细项圈',
            'hat_1': '鸭舌帽',
            'hat_ji': '一只小鸡',
            'hat_2': '小洋帽',
        }
        result = []
        for key in self._pending_color_changes:
            name = names.get(key, ITEMS.get(key, {}).get('name', key))
            if name not in result:
                result.append(name)
        return result

    def _show_dye_shortage_dialog(self, shortfall, have, other_missing=None):
        win = getattr(self, '_dye_shortage_win', None)
        if win is not None and win.winfo_exists():
            try:
                win.destroy()
            except Exception:
                pass
        self._dye_shortage_win = None
        win = tk.Toplevel(self._warehouse_win or self.root)
        win.title('染料不足')
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        configure_theme(win)
        win.configure(bg=THEME['bg'])
        self._dye_shortage_win = win
        card = make_card(win, bg=THEME['card'])
        card.pack(padx=16, pady=16)
        make_label(
            card, '本次染色消耗染料的物品：', bg=THEME['card'],
            font=(FONT_FAMILY, 10, 'bold')).pack(
                anchor='w', padx=14, pady=(12, 4))
        item_names = self._pending_dye_item_names()
        make_label(
            card, '、'.join(item_names) if item_names else '装备',
            bg=THEME['card'], fg=THEME['accent_hover'],
            justify='left', wraplength=300).pack(
                anchor='w', padx=14, pady=(0, 8))
        dye_info = ITEMS.get('dye') or {}
        price = int(dye_info.get('buy_price') or dye_info.get('price') or 0)
        cost = price * max(1, int(shortfall))
        make_label(
            card,
            f'染料：已有 {have} 个，缺少 {shortfall} 个\n'
            f'购买价格：{price} G/个，共需 {cost} G\n'
            f'当前金币：{self.gold} G',
            bg=THEME['card'], justify='left').pack(
                anchor='w', padx=14, pady=(0, 6))
        if other_missing:
            make_label(
                card, '其他不足：' + '；'.join(other_missing),
                bg=THEME['card'], fg=THEME['danger'],
                justify='left', wraplength=300).pack(
                    anchor='w', padx=14, pady=(0, 6))
        bar = tk.Frame(card, bg=THEME['card'])
        bar.pack(fill='x', padx=14, pady=(6, 12))
        make_button(
            bar, f'一键购买并确定（{cost} G）',
            lambda: self._buy_missing_dyes(shortfall),
            kind='primary', width=20).pack(side='left', padx=(0, 6))
        make_button(
            bar, '取消', self._close_dye_shortage_dialog,
            kind='ghost', width=8).pack(side='left')
        win.protocol('WM_DELETE_WINDOW', self._close_dye_shortage_dialog)
        self._place_popup_right_of_warehouse(win)

    def _close_dye_shortage_dialog(self):
        win = getattr(self, '_dye_shortage_win', None)
        self._dye_shortage_win = None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass

    def _buy_missing_dyes(self, amount):
        amount = max(1, int(amount))
        info = ITEMS.get('dye') or {}
        price = int(info.get('buy_price') or info.get('price') or 0)
        result = MarketService.purchase(
            self.game, self.inventory, 'dye', price, amount)
        if not result.ok:
            if result.reason == 'insufficient_gold':
                self._alert(
                    '金币不足',
                    f'购买 {amount} 个染料需要 {result.cost} G，'
                    f'当前只有 {self.gold} G。')
            else:
                self._alert('购买失败', '当前无法购买染料。')
            return
        StatsService.record_purchase(self.game, result.amount, 'dye')
        self._check_achievements()
        self._save_satiety()
        self._refresh_market()
        self._refresh_warehouse()
        self._close_dye_shortage_dialog()
        self._confirm_equipment()

    def close_warehouse(self, force=False):
        """关闭仓库；有待确认变更时询问是否保存并关闭。"""
        try:
            self.root.unbind_all('<MouseWheel>')
        except Exception:
            pass
        if (self._warehouse_win is None
                or not self._warehouse_win.winfo_exists()):
            return True
        self._discard_transient_editors()
        if not force and self._has_pending_warehouse_changes():
            try:
                import tkinter.messagebox as mb
                choice = mb.askyesnocancel(
                    '未确定变更',
                    '存在尚未确定的变更。\n'
                    '是：保存并关闭\n'
                    '否：不保存直接关闭\n'
                    '取消：返回仓库')
            except Exception:
                choice = None
            if choice is None:
                return False
            if choice:
                if not self._confirm_equipment():
                    return False
            else:
                self._reset_pending_warehouse()
        self._stop_exp_flash(refresh=False)
        self._stop_preview_actions()
        self._destroy_achievement_selector()
        self._hide_tooltip()
        for attr in ('_warehouse_detail_job', '_warehouse_detail_hide_job'):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
                setattr(self, attr, None)
        self._close_palette()
        self._destroy_sunglasses_adjust()
        self._destroy_hat_scale()
        self._close_dye_shortage_dialog()
        self._treasure_lock_mode = False
        try:
            self._warehouse_win.destroy()
        except Exception:
            pass
        self._warehouse_win = None
        self._warehouse_detail_card = None
        self._warehouse_detail_content = None
        self._reset_pending_warehouse()
        return True


    def _switch_warehouse_to_market(self):
        if not self.close_warehouse():
            return
        self.show_market()

    def _switch_warehouse_to_adventure(self):
        if not self.close_warehouse():
            return
        self.show_adventure()

    def _on_item_click(self, item_id):
        if item_id == 'hair_dye':
            self._open_equipment_adjust('hair_dye')
        elif item_id == 'lens':
            self._open_equipment_adjust('lens')
        elif item_id == 'hairstyle_tool':
            self._open_hairstyle_dialog()
        elif item_id == 'name_collar':
            self._prompt_cat_name(consume_collar=True, force=True)
        elif item_id == 'throat_lozenge':
            self._open_equipment_adjust('throat_lozenge')


    def _open_hairstyle_dialog(self):
        """使用一次性理发工具切换前层发型，等待仓库确定。"""
        if self.inventory.get('hairstyle_tool', 0) <= 0:
            self._alert('理发工具', '没有理发工具了，去集市买一个吧。')
            return
        win = tk.Toplevel(self.root)
        self._hairstyle_win = win
        self._hairstyle_original = self._pending_hair_style
        win.title('理发工具')
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        win.after(80, lambda w=win: self._hide_from_taskbar(w))
        current = self._pending_hair_style
        original = self._pending_hair_style
        style_var = tk.StringVar(value=current)
        make_label(win, text='选择新的发型',
                 font=('Microsoft YaHei UI', 10)).pack(padx=18, pady=(14, 6))
        for value, label in (('hair_1', '发型 1（原版）'),
                             ('hair_1_1', '发型 2')):
            tk.Radiobutton(win, text=label, variable=style_var,
                           value=value).pack(anchor='w', padx=24, pady=2)
        bar = tk.Frame(win)
        bar.pack(pady=(8, 14))

        def confirm():
            style = style_var.get()
            self._pending_hair_style = style
            if style != self.hair_style:
                self._pending_item_uses['hairstyle_tool'] = 1
            else:
                self._pending_item_uses.pop('hairstyle_tool', None)
            self._equip_preview_update()
            self._hairstyle_win = None
            win.destroy()
            if getattr(self, '_equip_status', None) is not None:
                self._equip_status.config(text='发型已预览，点击确定应用')

        def cancel():
            self._discard_hairstyle_dialog()

        make_button(bar, text='确定', width=8,
                  command=confirm).pack(side='left', padx=4)
        make_button(bar, text='取消', width=8,
                  command=cancel).pack(side='left', padx=4)
        win.protocol('WM_DELETE_WINDOW', cancel)


    def _discard_hairstyle_dialog(self):
        win = getattr(self, '_hairstyle_win', None)
        if win is None:
            return
        self._pending_hair_style = getattr(
            self, '_hairstyle_original', self.hair_style)
        if self._pending_hair_style != self.hair_style:
            self._pending_item_uses['hairstyle_tool'] = 1
        else:
            self._pending_item_uses.pop('hairstyle_tool', None)
        self._hairstyle_win = None
        try:
            self._equip_preview_update()
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass


    def _open_color_palette(self, kind):
        """兼容旧入口，统一转到嵌入式的装备/道具调节页。"""
        target = {
            'hair': 'hair_dye', 'eye': 'lens', 'clothes': 'normal',
            'earrings': 'gold_earrings', 'collar_rope': 'fine_collar',
            'collar_deco': 'fine_collar', 'hat_1': 'hat_1',
            'hat_ji': 'hat_ji', 'hat_2_brown': 'hat_2',
            'hat_2_cream': 'hat_2',
        }.get(kind)
        if target is not None:
            self._open_equipment_adjust(target)
            return
        equipment_kinds = (
            'clothes', 'earrings', 'collar_rope', 'collar_deco',
            'hat_1', 'hat_ji', 'hat_2_brown', 'hat_2_cream')
        if kind in equipment_kinds:
            item_id = None
            name = {
                'clothes': '普通衣服',
                'earrings': '耳环',
                'collar_rope': '细项圈绳子',
                'collar_deco': '细项圈装饰',
                'hat_1': '鸭舌帽',
                'hat_ji': '一只小鸡',
                'hat_2_brown': '小洋帽棕色部分',
                'hat_2_cream': '小洋帽米白部分',
            }.get(kind, '装备')
            color_key = self._color_change_item_key(kind)
            if (self.inventory.get('dye', 0) <= 0
                    and color_key not in self._pending_color_changes):
                self._alert('染料不足', '装备调色需要染料，去集市买一个吧。')
                return
        else:
            item_id = 'hair_dye' if kind == 'hair' else 'lens'
            name = '染发剂' if kind == 'hair' else '美瞳片'
            if self.inventory.get(item_id, 0) <= 0:
                self._alert(name, f'没有{name}了，去集市买一个吧。')
                return
        if (self._palette_win is not None
                and self._palette_win.winfo_exists()):
            self._palette_win.lift()
            return
        self._palette_kind = kind
        self._palette_original_value = self._palette_current_pending(kind)
        win = tk.Toplevel(self.root)
        win.title('调色板')
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        self._palette_win = win
        hint = {
            'hair': '选择新发色',
            'eye': '选择瞳孔颜色',
            'clothes': '选择普通衣服颜色',
            'collar_rope': '选择项圈绳子颜色',
            'collar_deco': '选择项圈装饰颜色',
            'earrings': '选择耳环颜色',
            'hat_1': '选择鸭舌帽颜色',
            'hat_ji': '选择小鸡头饰颜色',
            'hat_2_brown': '选择小洋帽棕色部分',
            'hat_2_cream': '选择小洋帽米白部分',
        }.get(kind, '选择颜色')
        make_label(win, text=hint,
                 font=('Microsoft YaHei UI', 10)).pack(padx=14, pady=(10, 6))
        grid = tk.Frame(win)
        grid.pack(padx=12)
        palette = EYE_COLORS if kind == 'eye' else HAIR_COLORS
        for i, color in enumerate(palette):
            make_button(grid, bg=color, width=3, height=1,
                      command=lambda c=color: self._palette_pick(c)
                      ).grid(row=i // 6, column=i % 6, padx=3, pady=3)
        bar = tk.Frame(win)
        bar.pack(pady=(6, 10))
        make_button(bar, text='还原', width=8,
                  command=self._palette_restore).pack(side='left', padx=4)
        make_button(bar, text='确定', width=8,
                  command=self._palette_confirm).pack(side='left', padx=4)
        make_button(bar, text='取消', width=8,
                  command=self._close_palette).pack(side='left', padx=4)
        win.protocol('WM_DELETE_WINDOW', self._close_palette)
        try:
            if (self._warehouse_win is not None
                    and self._warehouse_win.winfo_exists()):
                win.update_idletasks()
                x = self._warehouse_win.winfo_x() + \
                    self._warehouse_win.winfo_width() + 8
                y = self._warehouse_win.winfo_y()
                sw = win.winfo_screenwidth()
                sh = win.winfo_screenheight()
                x = max(0, min(x, sw - win.winfo_width()))
                y = max(0, min(y, sh - win.winfo_height()))
                win.geometry(f'+{int(x)}+{int(y)}')
        except Exception:
            pass


    def _palette_current_pending(self, kind):
        if kind == 'hair':
            return self._pending_hair_color
        if kind == 'eye':
            return self._pending_eye_color
        if kind == 'clothes':
            return self._pending_normal_clothes_color
        field = {
            'earrings': 'earrings_color',
            'collar_rope': 'collar_rope_color',
            'collar_deco': 'collar_deco_color',
            'hat_1': 'hat_1_color',
            'hat_ji': 'hat_ji_color',
            'hat_2_brown': 'hat_2_brown_color',
            'hat_2_cream': 'hat_2_cream_color',
        }.get(kind)
        return self._pending_equip_settings.get(field)


    def _palette_set_pending(self, kind, color):
        if kind == 'hair':
            self._pending_hair_color = color
        elif kind == 'eye':
            self._pending_eye_color = color
        elif kind == 'clothes':
            self._pending_normal_clothes_color = color
        else:
            field = {
                'earrings': 'earrings_color',
                'collar_rope': 'collar_rope_color',
                'collar_deco': 'collar_deco_color',
                'hat_1': 'hat_1_color',
                'hat_ji': 'hat_ji_color',
                'hat_2_brown': 'hat_2_brown_color',
                'hat_2_cream': 'hat_2_cream_color',
            }.get(kind)
            if field:
                self._pending_equip_settings[field] = color


    def _palette_pick(self, color):
        self._palette_set_pending(self._palette_kind, color)
        self._equip_preview_update()


    def _palette_restore(self):
        if self._palette_kind == 'hair':
            self._palette_set_pending('hair', None)
        elif self._palette_kind == 'eye':
            self._palette_set_pending('eye', None)
        elif self._palette_kind == 'clothes':
            self._palette_set_pending('clothes', None)
        else:
            fields = {
                'earrings': 'earrings_color',
                'collar_rope': 'collar_rope_color',
                'collar_deco': 'collar_deco_color',
                'hat_1': 'hat_1_color',
                'hat_ji': 'hat_ji_color',
                'hat_2_brown': 'hat_2_brown_color',
                'hat_2_cream': 'hat_2_cream_color',
            }
            field = fields.get(self._palette_kind)
            if field:
                self._palette_set_pending(
                    self._palette_kind,
                    DEFAULT_EQUIPMENT_SETTINGS.get(field))
        if self._palette_kind == 'hair':
            if self._pending_hair_color == self.hair_color:
                self._pending_item_uses.pop('hair_dye', None)
        elif self._palette_kind == 'eye':
            if self._pending_eye_color == self.eye_color:
                self._pending_item_uses.pop('lens', None)
        else:
            self._mark_equipment_color_change(self._palette_kind)
        self._equip_preview_update()


    def _palette_confirm(self):
        """颜色进入待确认状态；相关道具在仓库确定时消耗。"""
        kind = self._palette_kind
        if kind == 'hair':
            if self._pending_hair_color != self.hair_color:
                self._pending_item_uses['hair_dye'] = 1
            else:
                self._pending_item_uses.pop('hair_dye', None)
        elif kind == 'eye':
            if self._pending_eye_color != self.eye_color:
                self._pending_item_uses['lens'] = 1
            else:
                self._pending_item_uses.pop('lens', None)
        else:
            self._mark_equipment_color_change(kind)
        self._close_palette(preserve_pending=True)
        if getattr(self, '_equip_status', None) is not None:
            self._equip_status.config(text='颜色已预览，点击确定应用')


    def _close_palette(self, preserve_pending=False):
        if self._palette_win is None:
            return
        if not preserve_pending and getattr(self, '_palette_kind', None):
            self._palette_set_pending(
                self._palette_kind,
                getattr(self, '_palette_original_value', None))
        if self._palette_win is not None:
            try:
                self._palette_win.destroy()
            except Exception:
                pass
            self._palette_win = None
        if not self.closing and (self._warehouse_win is not None
                and self._warehouse_win.winfo_exists()):
            self._equip_preview_update()


    def _alert(self, title, text):
        """弹窗提示（不依赖 Tk 以外模块）"""
        try:
            import tkinter.messagebox as mb
            mb.showinfo(title, text)
        except Exception:
            pass



def install_runtime_globals(namespace):
    globals().update(namespace)
