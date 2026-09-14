# -*- coding: utf-8 -*-
"""MarketMixin 独立模块。"""
import random

from services import MarketService, InventoryService
from stats import StatsService
from ui_theme import (
    THEME, FONT_FAMILY, configure_theme, make_button, make_label, make_card)


QUALITY_RANK = {
    '粗劣': 1, '普通': 2, '少见': 3,
    '稀有': 4, '史诗': 5, '传说': 6,
}
MARKET_BANNER_TEXTS = (
    '挑选喜欢的物品吧~',
    '走过路过不要错过！',
    '机不可失！',
    '真是只可爱的小猫咪~',
    '小猫咪，今天要买点什么呢？',
)


class MarketMixin:
    def show_market(self):
        if self._market_win is not None and self._market_win.winfo_exists():
            banner = getattr(self, '_market_banner_label', None)
            if banner is not None:
                banner.config(text=random.choice(MARKET_BANNER_TEXTS))
            self._market_win.lift()
            self._refresh_market()
            return
        win = tk.Toplevel(self.root)
        win.title('集市')
        win.resizable(False, False)
        win.geometry(f'{dp(1120)}x{dp(620)}')
        # 集市是「页面」，留在任务栏里方便切回来（子弹窗仍然隐藏）。
        self._show_in_taskbar(win)
        win.after(80, lambda w=win: self._show_in_taskbar(w))
        configure_theme(win)
        win.configure(bg=THEME['bg'])
        self._market_win = win

        bottom = tk.Frame(win, bg=THEME['bg'])
        bottom.pack(side='bottom', fill='x', padx=18, pady=(0, 14))
        self._market_gold = make_label(bottom, '', bg=THEME['bg'])
        self._market_gold.pack(side='left')
        make_button(bottom, '仓库', self._switch_market_to_warehouse,
                    kind='secondary', width=7).pack(side='left', padx=(10, 0))
        make_button(bottom, '探险', self._switch_market_to_adventure,
                    kind='secondary', width=7).pack(side='left', padx=(6, 0))
        self._market_status = make_label(
            bottom, '', bg=THEME['bg'], fg=THEME['danger'], style='small',
            justify='right', wraplength=460)
        self._market_status.pack(side='right', padx=(10, 0))

        header = tk.Frame(win, bg=THEME['bg'])
        header.pack(side='top', fill='x', padx=18, pady=(12, 0))
        make_label(header, f"{self.cat_name or '猫猫'}的集市", style='title',
                   bg=THEME['bg']).pack(side='left', anchor='center')
        self._market_banner_label = make_label(
            header, random.choice(MARKET_BANNER_TEXTS), bg=THEME['bg'],
            fg=THEME['accent_hover'], font=(FONT_FAMILY, 13, 'bold'))
        self._market_banner_label.pack(
            side='left', anchor='center', padx=(18, 0))

        tabbar = tk.Frame(header, bg=THEME['bg'])
        tabbar.pack(side='right', fill='x', expand=True, anchor='center')
        self._market_tab_buttons = {}
        for page_name in reversed(('杂货铺', '服装店', '书店', '宝藏')):
            btn = make_button(
                tabbar, page_name,
                lambda page=page_name: self._select_market_page(page),
                kind='tab', width=8)
            btn.pack(side='right', padx=3)
            self._market_tab_buttons[page_name] = btn

        body = tk.Frame(win, bg=THEME['bg'])
        body.pack(fill='both', expand=True, padx=18, pady=(6, 6))
        page_host = tk.Frame(body, bg=THEME['bg'])
        page_host.pack(side='left', fill='both', expand=True)
        self._market_detail_card = make_card(body, bg=THEME['card'])
        self._market_detail_card.configure(width=280)
        self._market_detail_card.pack(
            side='right', fill='y', padx=(12, 0))
        self._market_detail_card.pack_propagate(False)
        self._market_detail_content = tk.Frame(
            self._market_detail_card, bg=THEME['card'])
        self._market_detail_content.pack(fill='both', expand=True)
        self._market_detail_job = None
        self._market_detail_hide_job = None
        self._show_market_detail_placeholder()
        self._market_page_frames = {}
        self._market_pages = {}
        for page_name in ('杂货铺', '服装店', '书店'):
            tab = tk.Frame(page_host, bg=THEME['bg'])
            self._market_page_frames[page_name] = tab
            self._market_pages[page_name] = self._make_scrollable_frame(
                tab, THEME['card'], height=430, width=760)

        sell_tab = tk.Frame(page_host, bg=THEME['bg'])
        self._market_page_frames['宝藏'] = sell_tab
        self._market_btns = {}
        self._market_spins = {}
        self._market_have = {}
        self._market_sell_btns = {}
        self._market_sell_spins = {}
        self._market_sell_have = {}
        self._market_rows = {}

        market_items = [
            (iid, info) for iid, info in ITEMS.items()
            if (info.get('can_buy') or info.get('can_sell'))
            and info.get('market_page') in self._market_pages
        ]
        ordered_items = []
        for page_name in ('杂货铺', '服装店', '书店'):
            page_items = [
                pair for pair in market_items
                if pair[1].get('market_page') == page_name
            ]
            if page_name in ('服装店', '书店'):
                page_items.sort(key=lambda pair: (
                    int(self.inventory.get(pair[0], 0)) > 0,
                    -QUALITY_RANK.get(pair[1].get('quality'), 0),
                    pair[1].get('name', ''),
                ))
            ordered_items.extend(page_items)

        for iid, info in ordered_items:
            frame = self._market_pages.get(info.get('market_page'))
            if frame is None:
                continue
            row_bg = THEME['card_alt']
            row = make_card(frame, bg=row_bg)
            row.grid(row=len(self._market_rows), column=0, sticky='ew',
                     padx=6, pady=4)
            self._market_rows[iid] = row
            frame.grid_columnconfigure(0, weight=1)
            quality = self._quality_color(info)
            row.configure(highlightbackground=quality)
            row.bind('<Enter>', lambda e, c=row, b=quality: c.configure(
                highlightbackground=THEME['accent_hover']))
            row.bind('<Leave>', lambda e, c=row, b=quality: c.configure(
                highlightbackground=b))

            make_label(
                row, info['name'], width=18,
                anchor='w', bg=row_bg, fg=self._quality_color(info),
                font=(FONT_FAMILY, 11)).pack(side='left', padx=(10, 5), pady=6)

            can_buy = bool(info.get('can_buy'))
            if can_buy:
                price = int(info.get('buy_price') or info.get('price') or 0)
                make_label(row, f'{price} G', width=7, anchor='e',
                           bg=row_bg).pack(side='left', padx=(4, 2))
                have = make_label(row, '', width=7, anchor='center',
                                  fg=THEME['muted'], bg=row_bg,
                                  style='small')
                have.pack(side='left', padx=(2, 4))
                spin = tk.Spinbox(
                    row, from_=1, to=99, width=3, justify='center',
                    bg=THEME['card'], fg=THEME['text'], relief='flat',
                    highlightthickness=1, highlightbackground=THEME['border'],
                    command=lambda i=iid: self._on_market_quantity_change(i))
                spin.bind('<FocusOut>',
                          lambda e, i=iid: self._on_market_quantity_change(i))
                spin.bind('<Return>',
                          lambda e, i=iid: self._on_market_quantity_change(i))
                spin.pack(side='left', padx=2)
                btn = make_button(
                    row, text='购买', kind='primary', width=5,
                    command=lambda i=iid: self._buy_item(i))
                btn.pack(side='left', padx=(6, 2))
                self._market_btns[iid] = btn
                self._market_spins[iid] = spin
                self._market_have[iid] = have

            if info.get('can_sell'):
                sell_price = int(info.get('sell_price') or 0)
                sell_separator = None
                if can_buy:
                    sell_separator = make_label(
                        row, '｜', bg=row_bg, fg=THEME['border'])
                sell_price_label = make_label(
                    row, f'卖 {sell_price} G', width=7, anchor='e',
                    bg=row_bg)
                sell_have = make_label(
                    row, '', width=7, anchor='center', bg=row_bg,
                    fg=THEME['muted'], style='small')
                sell_spin = tk.Spinbox(
                    row, from_=1, to=99, width=3, justify='center',
                    bg=THEME['card'], fg=THEME['text'], relief='flat',
                    highlightthickness=1, highlightbackground=THEME['border'])
                sell_btn = make_button(
                    row, text='出售', kind='primary', width=5,
                    command=lambda i=iid: self._sell_item(i))
                sell_btn.pack(side='right', padx=(6, 8))
                sell_spin.pack(side='right', padx=2)
                sell_have.pack(side='right', padx=(2, 4))
                sell_price_label.pack(side='right', padx=(2, 4))
                if sell_separator is not None:
                    sell_separator.pack(side='right', padx=2)
                self._market_sell_btns[iid] = sell_btn
                self._market_sell_spins[iid] = sell_spin
                self._market_sell_have[iid] = sell_have
            self._bind_market_detail_frame(row, info)

        sell_header = make_card(sell_tab, bg=THEME['card'])
        sell_header.pack(fill='x', padx=8, pady=(8, 6))
        self._market_treasure_summary = make_label(
            sell_header, '', bg=THEME['card'])
        self._market_treasure_summary.pack(
            side='left', padx=12, pady=9)
        make_button(sell_header, '一键出售', self._show_bulk_sell_dialog,
                    kind='primary', width=8).pack(
                        side='right', padx=10, pady=6)
        self._market_treasure_items = self._make_scrollable_frame(
            sell_tab, THEME['card'], height=390, width=760)
        win.protocol('WM_DELETE_WINDOW', self.close_market)
        self._select_market_page('杂货铺')

    def _select_market_page(self, page_name):
        self._hide_market_detail()
        frame = getattr(self, '_market_page_frames', {}).get(page_name)
        if frame is None:
            return
        for name, page in self._market_page_frames.items():
            if name == page_name:
                page.pack(fill='both', expand=True)
            else:
                page.pack_forget()
        for name, btn in getattr(self, '_market_tab_buttons', {}).items():
            selected = name == page_name
            btn.config(
                bg=THEME['tab_selected'] if selected else THEME['tab_bg'],
                fg=THEME['accent_text'] if selected else THEME['text'])
        self._market_current_page = page_name
        self._refresh_market()

    def _bind_market_detail_frame(self, widget, info):
        def show_detail(event=None):
            self._schedule_market_detail(info)

        def hide_detail(event=None):
            self._schedule_market_detail_hide()

        def bind_tree(item):
            item.bind('<Enter>', show_detail, add='+')
            item.bind('<Leave>', hide_detail, add='+')
            for child in item.winfo_children():
                bind_tree(child)

        bind_tree(widget)

    def _cancel_market_detail_hide(self):
        job = getattr(self, '_market_detail_hide_job', None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._market_detail_hide_job = None

    def _schedule_market_detail(self, info):
        self._cancel_market_detail_hide()
        job = getattr(self, '_market_detail_job', None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        self._market_detail_job = self.root.after(
            20, lambda data=info: self._show_market_detail(data))

    def _schedule_market_detail_hide(self):
        self._cancel_market_detail_hide()
        job = getattr(self, '_market_detail_job', None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._market_detail_job = None
        self._market_detail_hide_job = self.root.after(
            90, self._hide_market_detail)

    def _show_market_detail_placeholder(self):
        content = getattr(self, '_market_detail_content', None)
        if content is None or not content.winfo_exists():
            return
        for child in content.winfo_children():
            child.destroy()
        card = getattr(self, '_market_detail_card', None)
        if card is not None:
            card.configure(
                highlightbackground=THEME['border'],
                highlightcolor=THEME['border'], highlightthickness=1)
        make_label(
            content, '物品详情', bg=THEME['card'], fg=THEME['muted'],
            font=(FONT_FAMILY, 10, 'bold')).pack(
                anchor='w', padx=12, pady=(14, 6))
        make_label(
            content, '将鼠标移入商品框查看详情', bg=THEME['card'],
            fg=THEME['muted'], font=(FONT_FAMILY, 9), justify='left',
            wraplength=240).pack(anchor='w', padx=12)

    def _hide_market_detail(self):
        self._market_detail_job = None
        self._market_detail_hide_job = None
        self._show_market_detail_placeholder()

    def _show_market_detail(self, info):
        self._market_detail_job = None
        self._cancel_market_detail_hide()
        content = getattr(self, '_market_detail_content', None)
        if content is None or not content.winfo_exists():
            return
        for child in content.winfo_children():
            child.destroy()
        quality = info.get('quality', '普通')
        quality_color = self._quality_color(info)
        card = getattr(self, '_market_detail_card', None)
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

    def _get_market_amount(self, item_id, clamp=False):
        spin = getattr(self, '_market_spins', {}).get(item_id)
        info = ITEMS.get(item_id) or {}
        if info.get('category') in ('头饰', '服装', '饰品', '书籍'):
            return 1
        if spin is None:
            return 1
        try:
            amount = max(1, int(spin.get()))
        except Exception:
            amount = 1
        price = int(info.get('buy_price') or info.get('price') or 0)
        if clamp and price > 0:
            max_affordable = min(99, self.gold // price)
            if max_affordable < 1:
                amount = 1
            else:
                amount = min(amount, max_affordable)
        return amount

    def _on_market_quantity_change(self, item_id):
        self._get_market_amount(item_id, clamp=True)
        self._refresh_market()

    def _get_market_sell_amount(self, item_id, clamp=False):
        spin = getattr(self, '_market_sell_spins', {}).get(item_id)
        have_count = max(0, int(self.inventory.get(item_id, 0)))
        if spin is None:
            return 1
        try:
            amount = max(1, int(spin.get()))
        except Exception:
            amount = 1
        if clamp:
            amount = min(amount, max(1, have_count))
        return amount


    def _refresh_market(self):
        if self._market_win is None or not self._market_win.winfo_exists():
            return
        self._market_gold.config(text=f'金币：{self.gold} G')
        for page_name in ('服装店', '书店'):
            page_rows = [
                (iid, row)
                for iid, row in getattr(self, '_market_rows', {}).items()
                if (ITEMS.get(iid) or {}).get('market_page') == page_name
            ]
            page_rows.sort(key=lambda pair: (
                int(self.inventory.get(pair[0], 0)) > 0,
                -QUALITY_RANK.get(
                    (ITEMS.get(pair[0]) or {}).get('quality'), 0),
                (ITEMS.get(pair[0]) or {}).get('name', ''),
            ))
            for row_index, (_, row) in enumerate(page_rows):
                row.grid_configure(row=row_index)
        for iid, row in getattr(self, '_market_rows', {}).items():
            info = ITEMS.get(iid) or {}
            owned = int(self.inventory.get(iid, 0)) > 0
            if info.get('category') == '服装' and owned:
                row.grid_remove()
            else:
                row.grid()
        for iid, btn in getattr(self, '_market_btns', {}).items():
            info = ITEMS.get(iid) or {}
            amount = self._get_market_amount(iid, clamp=True)
            have_count = int(self.inventory.get(iid, 0))
            unique = info.get('category') in ('头饰', '服装', '饰品', '书籍')
            sold_out = unique and have_count >= 1
            have = self._market_have.get(iid)
            if have is not None:
                have.config(text='已售罄' if sold_out else f'已有 {have_count}')
            price = int(info.get('buy_price') or info.get('price') or 0)
            if sold_out:
                btn.config(text='已售罄', state='disabled')
                spin = self._market_spins.get(iid)
                if spin is not None:
                    spin.config(state='disabled')
            else:
                btn.config(text='购买', state='disabled' if self.gold < price * amount else 'normal')
                spin = self._market_spins.get(iid)
                if spin is not None:
                    spin.config(state='normal')
        for iid, btn in getattr(self, '_market_sell_btns', {}).items():
            have_count = max(0, int(self.inventory.get(iid, 0)))
            sell_have = getattr(self, '_market_sell_have', {}).get(iid)
            if sell_have is not None:
                sell_have.config(text=f'已有 {have_count}')
            spin = getattr(self, '_market_sell_spins', {}).get(iid)
            if spin is not None:
                spin.config(to=max(1, have_count))
                if have_count > 0:
                    try:
                        if int(spin.get()) > have_count:
                            spin.delete(0, 'end')
                            spin.insert(0, str(have_count))
                    except Exception:
                        pass
                    spin.config(state='normal')
                else:
                    spin.config(state='disabled')
            btn.config(state='normal' if have_count > 0 else 'disabled')
        self._refresh_market_treasures()

    def _refresh_market_treasures(self):
        """重建宝藏出售列表。"""
        frame = getattr(self, '_market_treasure_items', None)
        if frame is None or not frame.winfo_exists():
            return
        for widget in frame.winfo_children():
            widget.destroy()
        self._market_treasure_spins = {}
        self._market_treasure_groups = {}
        all_groups = self._treasure_groups()
        groups = {key: group for key, group in all_groups.items()
                  if not key[4]}
        sellable = [t for group in groups.values() for t in group]
        total_value = sum(int(t.get('value', 0)) for t in sellable)
        self._market_treasure_summary.config(
            text=f'可出售：{len(sellable)} 件 · 总价值 {total_value} G')
        bg = frame.cget('background')
        if not groups:
            make_label(frame, '（没有可以出售的宝藏）', bg=bg,
                       fg=THEME['muted']).pack(anchor='center', pady=18)
            return

        ordered = sorted(
            groups.items(),
            key=lambda item: (-item[0][2],
                              self._treasure_display_name(item[1][0])))
        for key, group in ordered:
            first = group[0]
            info = self._treasure_info(first)
            row_bg = THEME['card_alt']
            row = make_card(frame, bg=row_bg)
            row.configure(highlightbackground=self._quality_color(info))
            row.pack(fill='x', padx=6, pady=4)
            make_label(row, info['name'], width=28, anchor='w',
                       bg=row_bg, fg=self._quality_color(info),
                       font=(FONT_FAMILY, 11)).pack(
                           side='left', padx=(10, 5), pady=6)
            make_label(row, f"{first.get('value', 0)} G", width=8,
                       anchor='e', bg=row_bg).pack(side='left', padx=(4, 2))
            make_label(row, f'×{len(group)}', width=4, bg=row_bg).pack(
                side='left', padx=(4, 2))
            make_label(row, '卖出', bg=row_bg, fg=THEME['muted']).pack(
                side='left', padx=(4, 2))
            spin = tk.Spinbox(
                row, from_=1, to=len(group), width=3, justify='center',
                bg=THEME['card'], fg=THEME['text'], relief='flat',
                highlightthickness=1, highlightbackground=THEME['border'])
            spin.pack(side='left', padx=2)
            btn = make_button(
                row, text='出售', kind='secondary', width=6,
                command=lambda k=key: self._sell_treasure_group(k))
            btn.pack(side='right', padx=(8, 10))
            self._market_treasure_groups[key] = group
            self._market_treasure_spins[key] = spin
            self._bind_market_detail_frame(row, info)

    def _sell_treasure_group(self, key):
        """按数量出售一组相同宝藏。"""
        group = self._market_treasure_groups.get(key, [])
        spin = self._market_treasure_spins.get(key)
        if not group or spin is None:
            return
        try:
            amount = max(1, min(len(group), int(spin.get())))
        except Exception:
            amount = 1
        result = MarketService.sell_treasures(
            self.game, self.treasures, group[:amount], TREASURE_SELL_EMOTION)
        if not result.ok:
            return
        StatsService.record_gold_earned(self.game, result.gain)
        StatsService.record_treasure_sale(self.game, result.count)
        self._check_achievements()
        self._save_satiety()
        self._market_status.config(
            text=f'已出售 {self._treasure_display_name(self._market_treasure_groups[key][0])} '
                 f'×{result.count}，获得 {result.gain} G'
                 + (f'，情绪 +{result.emotion_gain}'
                    if result.emotion_gain else ''))
        self._refresh_market()
        self._refresh_warehouse()


    def _show_bulk_sell_dialog(self):
        """询问最高品质后，一键出售所有未上锁宝藏。"""
        parent = None
        for attr in ('_market_win', '_warehouse_win'):
            candidate = getattr(self, attr, None)
            try:
                if candidate is not None and candidate.winfo_exists():
                    parent = candidate
                    break
            except Exception:
                continue
        if parent is None:
            return
        win = tk.Toplevel(parent)
        win.title('一键出售')
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        win.after(80, lambda w=win: self._hide_from_taskbar(w))
        configure_theme(win)
        win.configure(bg=THEME['bg'])
        make_label(win, '出售最高品质不超过：', bg=THEME['bg']).pack(
            padx=18, pady=(14, 4))
        quality_names = [QUALITY_NAMES[q] for q in range(1, 7)]
        quality_var = tk.StringVar(value=quality_names[2])
        combo = ttk.Combobox(win, textvariable=quality_var,
                             values=quality_names, state='readonly', width=10)
        combo.pack(padx=18, pady=4)
        preview = make_label(win, '', bg=THEME['bg'], fg=THEME['muted'],
                             style='small')
        preview.pack(padx=18, pady=(4, 2))

        def selected_quality():
            try:
                return quality_names.index(quality_var.get()) + 1
            except ValueError:
                return 1

        def update_preview(*args):
            max_quality = selected_quality()
            targets = [t for t in self.treasures
                       if not t.get('locked', False)
                       and int(t.get('quality', 1)) <= max_quality]
            total = sum(int(t.get('value', 0)) for t in targets)
            preview.config(text=f'将出售 {len(targets)} 件，获得 {total} G')

        def confirm_sell():
            self._bulk_sell_treasures(selected_quality())
            win.destroy()

        combo.bind('<<ComboboxSelected>>', update_preview)
        update_preview()
        bar = tk.Frame(win, bg=THEME['bg'])
        bar.pack(pady=(8, 14))
        make_button(bar, '出售', confirm_sell, kind='primary',
                    width=8).pack(side='left', padx=4)
        make_button(bar, '取消', win.destroy, kind='ghost',
                    width=8).pack(side='left', padx=4)
        win.update_idletasks()
        dialog_w = max(1, win.winfo_reqwidth())
        dialog_h = max(1, win.winfo_reqheight())
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = parent.winfo_rootx() + parent.winfo_width() + 8
        if x + dialog_w > screen_w:
            x = parent.winfo_rootx() - dialog_w - 8
        x = max(0, min(x, screen_w - dialog_w))
        y = parent.winfo_rooty() + 40
        y = max(0, min(y, screen_h - dialog_h - 40))
        win.geometry(f'+{x}+{y}')
        win.protocol('WM_DELETE_WINDOW', win.destroy)

    def _bulk_sell_treasures(self, max_quality):
        """出售所有未上锁且品质不超过 max_quality 的宝藏。"""
        targets = [t for t in self.treasures
                   if not t.get('locked', False)
                   and int(t.get('quality', 1)) <= max_quality]
        if not targets:
            if self._market_status is not None:
                self._market_status.config(text='没有符合条件的未上锁宝藏')
            if getattr(self, '_equip_status', None) is not None:
                self._equip_status.config(text='没有符合条件的未上锁宝藏')
            return
        result = MarketService.sell_treasures(
            self.game, self.treasures, targets, TREASURE_SELL_EMOTION)
        if not result.ok:
            return
        StatsService.record_gold_earned(self.game, result.gain)
        StatsService.record_treasure_sale(self.game, result.count)
        self._check_achievements()
        self._save_satiety()
        quality = QUALITY_NAMES.get(max_quality, '普通')
        status = (
            f'一键出售 {result.count} 件（最高{quality}），获得 {result.gain} G'
            + (f'，情绪 +{result.emotion_gain}' if result.emotion_gain else ''))
        if self._market_status is not None:
            self._market_status.config(text=status)
        if getattr(self, '_equip_status', None) is not None:
            self._equip_status.config(text=status)
        self._refresh_market()
        self._refresh_warehouse()


    def _market_item_equipped(self, item_id):
        info = ITEMS.get(item_id) or {}
        category = info.get('category')
        if category == '服装':
            return CLOTHES_ITEM_IDS.get(self.equipped_clothes) == item_id
        if category in ('头饰', '饰品'):
            return item_id in self._slot_item_ids(self.equipped_slots, category)
        if category == '书籍':
            return item_id in self.books_enabled
        return False

    def _buy_item(self, item_id):
        info = ITEMS.get(item_id)
        if info is None or not info.get('can_buy'):
            return
        unique = info.get('category') in ('头饰', '服装', '饰品', '书籍')
        if unique and int(self.inventory.get(item_id, 0)) >= 1:
            self._market_status.config(text='这件商品已经拥有，显示已售罄')
            self._refresh_market()
            return
        amount = self._get_market_amount(item_id, clamp=True)
        price = int(info.get('buy_price') or info.get('price') or 0)
        result = MarketService.purchase(self.game, self.inventory, item_id, price, amount, max_count=1 if unique else None)
        if not result.ok:
            self._market_status.config(text='金币不足！' if result.reason == 'insufficient_gold' else '已售罄')
            return
        StatsService.record_purchase(self.game, result.amount, item_id)
        self._check_achievements()
        self._save_satiety()
        self._market_status.config(text=f"已购买 {info['name']} {result.amount}（花费 {result.cost} G）")
        spin = self._market_spins.get(item_id)
        if spin is not None:
            try:
                spin.delete(0, 'end')
                spin.insert(0, '1')
            except Exception:
                pass
        self._refresh_market()
        self._refresh_warehouse()

    def _sell_item(self, item_id):
        info = ITEMS.get(item_id) or {}
        if not info.get('can_sell') or int(self.inventory.get(item_id, 0)) <= 0:
            return
        if self._market_item_equipped(item_id):
            self._market_status.config(text='请先在仓库中卸下该物品')
            return
        amount = self._get_market_sell_amount(item_id, clamp=True)
        price = int(info.get('sell_price') or 0)
        result = MarketService.sell_item(
            self.game, self.inventory, item_id, price, amount)
        if not result.ok:
            self._market_status.config(text='没有可以出售的物品')
            return
        StatsService.record_gold_earned(self.game, result.cost)
        self._check_achievements()
        self._save_satiety()
        self._market_status.config(
            text=f"已出售 {info['name']} ×{result.amount}，获得 {result.cost} G")
        spin = getattr(self, '_market_sell_spins', {}).get(item_id)
        if spin is not None:
            try:
                spin.delete(0, 'end')
                spin.insert(0, '1')
            except Exception:
                pass
        self._refresh_market()
        self._refresh_warehouse()

    def _switch_market_to_warehouse(self):
        self.close_market()
        self.show_warehouse()

    def _switch_market_to_adventure(self):
        self.close_market()
        self.show_adventure()

    def close_market(self):
        """关闭集市窗口"""
        for attr in ('_market_detail_job', '_market_detail_hide_job'):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._market_job is not None:
            try:
                self.root.after_cancel(self._market_job)
            except Exception:
                pass
            self._market_job = None
        if self._market_win is not None:
            try:
                self._market_win.destroy()
            except Exception:
                pass
            self._market_win = None


    def _fill_feed_menu(self, feed_menu):
        """喂食二级菜单：只显示有库存且可食用的食物。"""
        foods = [i for i, info in ITEMS.items()
                 if info.get('kind') == '食物'
                 and info.get('exp', 0) > 0
                 and self.inventory.get(i, 0) > 0]
        if not foods:
            feed_menu.add_command(label='（没有可用食物）', state='disabled')
            return
        for iid in foods:
            info = ITEMS[iid]
            count = self.inventory.get(iid, 0)
            gain = info.get('exp', 0)
            sub = tk.Menu(feed_menu, tearoff=0)
            feed_menu.add_cascade(label=f"{info['name']} × {count}", menu=sub)
            for n in range(1, min(count, 10) + 1):
                sub.add_command(
                    label=f'使用 {n} 个（+{n * gain} 经验）',
                    command=lambda i=iid, nn=n: self._use_food(i, nn))
            if count > 10:
                sub.add_separator()
                sub.add_command(
                    label=f'全部使用（{count} 个）',
                    command=lambda i=iid: self._use_food(i, count))


    def _use_food(self, item_id, amount=1):
        """消耗指定数量的食物，获得经验并可升级"""
        info = ITEMS.get(item_id)
        if (info is None or info.get('kind') != '食物'
                or info.get('exp', 0) <= 0):
            return
        amount = max(0, min(amount, self.inventory.get(item_id, 0)))
        if amount <= 0:
            return
        InventoryService.remove(self.inventory, item_id, amount)
        gained = self._gain_exp(info.get('exp', 0) * amount)
        effect = info.get('eat_effect') or {}
        hp_loss = 0
        chance = float(effect.get('hp_loss_chance', 0))
        ratio = float(effect.get('hp_loss_ratio', 0))
        if chance > 0 and ratio > 0:
            loss_per = max(1, round(self.max_hp * ratio))
            for _ in range(amount):
                if random.random() < chance:
                    before = self.hp
                    self.hp = max(0, self.hp - loss_per)
                    hp_loss += before - self.hp
        gain_range = FOOD_EMOTION_GAIN.get(info.get('quality', '普通'), (0, 1))
        emotion_gain = sum(random.randint(gain_range[0], gain_range[1])
                           for _ in range(amount))
        if emotion_gain:
            self.emotion = min(100, self.emotion + emotion_gain)
        if hp_loss:
            self._last_food_status = (
                f'{info["name"]}吃坏了肚子，活力 -{hp_loss}'
                + (f'，情绪 +{emotion_gain}' if emotion_gain else ''))
        else:
            self._last_food_status = (
                f'食用{info["name"]} ×{amount}，经验 +{info.get("exp", 0) * amount}'
                + (f'，情绪 +{emotion_gain}' if emotion_gain else ''))
        StatsService.record_feed(
            self.game, item_id, amount, hp_loss > 0)
        self._check_achievements()
        self._save_satiety()
        self._refresh_panel()
        self._selected_food = None
        self._stop_exp_flash()
        self._refresh_warehouse()
        self._check_hospital_state()
        return gained



def install_runtime_globals(namespace):
    globals().update(namespace)
