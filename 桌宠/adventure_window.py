# -*- coding: utf-8 -*-
"""AdventureMixin 独立模块。"""
from services import AdventureService, TreasureService, InventoryService
from stats import StatsService


class AdventureMixin:
    def start_adventure(self, region_id, minutes):
        """校验后播放离场动画，完全离开屏幕才开始探险计时。"""
        if self.adventuring or self.closing or self.hospitalized:
            return
        region = REGIONS.get(region_id)
        if region is None:
            return
        if region['fallback']:
            minutes = region.get('fixed_minutes', 5)
        elif minutes not in EXPLORE_TIMES:
            return
        if self.hp < HP_LOW_AT:
            self._alert('探险', '活力值不足 20，无法探险')
            return
        if not region['fallback'] and self.level < region.get('min_level', 5):
            self._alert('探险', '等级不够哦，请先提升实力吧！')
            return
        bread_cost = 0
        if not region['fallback']:
            bread_cost = math.ceil(
                minutes / ADVENTURE_BREAD_MINUTES_PER_UNIT)
            bread_count = InventoryService.count(self.inventory, 'bread')
            if bread_count < bread_cost:
                self._alert(
                    '探险',
                    f'面包不足：需要 {bread_cost} 个，当前只有 {bread_count} 个。')
                return
        if not self.close_warehouse():
            return
        self.close_adventure()
        self._adventure_bread_cost = bread_cost
        if bread_cost:
            InventoryService.remove(self.inventory, 'bread', bread_cost)
            self._save_satiety()
        self._adventure_region = region_id
        self._adventure_minutes = minutes
        self._adventure_treasure_quality_counts = {}
        self._adventure_end_time = None
        self.adventuring = True
        self._adventure_departing = True
        if self._regen_job is not None:
            try:
                self.root.after_cancel(self._regen_job)
            except Exception:
                pass
            self._regen_job = None
        self._cancel_anim()
        self._cancel_walk()
        self._cancel_fall()
        self._cancel_fling()
        self._cancel_climb()
        self._cancel_reach()
        self._cancel_jump()
        self._cancel_emotion_face()
        self.close_scale_window()
        self._update_tray_title()
        self._start_adventure_departure()


    def _start_adventure_departure(self):
        """先抬手摇晃告别，再前跳并落出屏幕。"""
        self.motion.enter('adventure_wave', force=True)
        self._adventure_depart_phase = 'farewell'
        self._adventure_depart_t0 = time.monotonic()
        self._adventure_farewell_step = 0
        self._adventure_side = random.choice(('left', 'right'))
        self._scratch_side = self._adventure_side
        self._scratch_lift = 1.0
        self._scratch_stage = 0
        self._scratch_wave_style = 'fan'
        self._scratch_wave_x_offset = 56
        self._scratch_wave_y_offset = 14
        self._scratch_wave_offset = 48
        self._forced_expression = None
        self._click_expression = None
        self.motion.clear_expression('expression_click')
        self.motion.clear_expression('expression_comfy')
        self.motion.clear_expression('expression_jump')
        self._comfy_active = False
        self._jump_state = None
        self.pose = 'scratch'
        self.update_image()
        self._adventure_depart_job = self.animations.schedule('adventure_depart', 
            ADVENTURE_FAREWELL_MS, self._adventure_farewell_tick)


    def _adventure_farewell_tick(self):
        self._adventure_depart_job = None
        if not self.adventuring or self.closing:
            return
        step = getattr(self, '_adventure_farewell_step', 0) + 1
        self._adventure_farewell_step = step
        if step < 12:
            self._scratch_stage = 1 if step % 2 else -1
            self.update_image()
            self._adventure_depart_job = self.animations.schedule('adventure_depart', 
                ADVENTURE_FAREWELL_MS, self._adventure_farewell_tick)
            return
        self._start_adventure_hop()


    def _start_adventure_hop(self):
        self.motion.set_phase('hop', 'adventure_wave')
        self._adventure_depart_phase = 'hop'
        self._adventure_hop_step = 0
        self._adventure_hop_start = (
            self.root.winfo_x(), self.root.winfo_y())
        self._adventure_hop_dir = 1 if self.facing_right else -1
        self.pose = 'normal'
        self._scratch_wave_style = 'vertical'
        self._scratch_wave_offset = SCRATCH_OFFSET
        self._forced_expression = None
        self._jump_state = 'adventure'
        self._jump_hand_mode = 'forward'
        self.update_image()
        self._adventure_depart_job = self.animations.schedule('adventure_depart', 
            ADVENTURE_HOP_FRAME_MS, self._adventure_hop_tick)


    def _adventure_hop_tick(self):
        self._adventure_depart_job = None
        if not self.adventuring or self.closing:
            return
        step = getattr(self, '_adventure_hop_step', 0) + 1
        self._adventure_hop_step = step
        size = int(ICON_SIZE * self.scale)
        sx, sy = self._adventure_hop_start
        if step >= 12:
            self._start_adventure_fall()
            return
        x = sx + self._adventure_hop_dir * step * 13
        y = sy - int(12 * math.sin(math.pi * step / 12.0))
        self.root.geometry(f'{size}x{size}+{int(x)}+{int(y)}')
        self._adventure_depart_job = self.animations.schedule('adventure_depart', 
            ADVENTURE_HOP_FRAME_MS, self._adventure_hop_tick)


    def _start_adventure_fall(self):
        self.motion.set_phase('launch', 'adventure_wave')
        self._adventure_depart_phase = 'launch'
        self._forced_expression = None
        self._scratch_wave_style = 'vertical'
        self._scratch_wave_offset = SCRATCH_OFFSET
        self._jump_state = None
        self._jump_hand_mode = ''
        self.pose = 'normal'
        self._falling_hands = True
        self._hand_lift = 1.0
        self._fall_lift_factor = 1.0
        self._adventure_launch_vx = self._adventure_hop_dir * 17.0
        self._adventure_launch_vy = -2.0
        self._adventure_launch_gravity = 0.45
        self.update_image()
        self._adventure_depart_job = self.animations.schedule('adventure_depart', 
            ADVENTURE_FALL_FRAME_MS, self._adventure_fall_tick)


    def _adventure_fall_tick(self):
        self._adventure_depart_job = None
        if not self.adventuring or self.closing:
            return
        size = int(ICON_SIZE * self.scale)
        x = self.root.winfo_x() + int(self._adventure_launch_vx)
        y = self.root.winfo_y() + int(self._adventure_launch_vy)
        self._adventure_launch_vy += self._adventure_launch_gravity
        self._adventure_launch_vx *= 0.997
        self.root.geometry(f'{size}x{size}+{int(x)}+{int(y)}')
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        left_edge = x + int(size * CAT_LEFT_RATIO)
        right_edge = x + int(size * CAT_RIGHT_RATIO)
        if (right_edge < 0 or left_edge > screen_w
                or y > screen_h + size):
            self._finish_adventure_departure()
            return
        self._adventure_depart_job = self.animations.schedule('adventure_depart', 
            ADVENTURE_FALL_FRAME_MS, self._adventure_fall_tick)


    def _finish_adventure_departure(self):
        self._adventure_departing = False
        self._forced_expression = None
        self._scratch_wave_style = 'vertical'
        self._scratch_wave_offset = SCRATCH_OFFSET
        self._falling_hands = False
        self._hand_lift = 0.0
        self._fall_lift_factor = 0.0
        try:
            self.root.withdraw()
        except Exception:
            pass
        self._adventure_end_time = time.monotonic() + self._adventure_minutes * 60
        self._adventure_job = self.root.after(
            self._adventure_minutes * 60 * 1000, self._finish_adventure)
        self._adventure_title_job = self.animations.schedule('adventure_title', 
            ADVENTURE_TITLE_UPDATE_MS, self._adventure_title_tick)
        self._update_tray_title()


    def _load_event_book(self):
        """从统一内容仓库读取探险事件簿。"""
        if self._event_book is not None:
            return self._event_book
        events, errors = CONTENT_REPOSITORY.reload_events()
        self._handle_content_errors(errors)
        if errors:
            events = list(EVENT_BOOK_CONTENT)
        self._event_book = events
        return self._event_book


    def _load_treasure_book(self):
        """从统一内容仓库读取宝藏与前缀。"""
        if self._treasure_book is not None:
            return self._treasure_book
        book, prefixes, errors = CONTENT_REPOSITORY.reload_treasures()
        self._handle_content_errors(errors)
        if errors:
            book = list(TREASURE_BOOK_CONTENT)
            prefixes = list(TREASURE_PREFIX_CONTENT)
        self._treasure_book = book
        self._treasure_prefixes = prefixes
        return self._treasure_book


    def _generate_treasure(self, region_id=None, max_quality=None):
        """按地区筛选宝藏，并按地区权重抽取品质。"""
        region_specified = region_id is not None
        try:
            region_number = int(region_id) if region_specified else 1
        except (TypeError, ValueError):
            region_number = 1
        if max_quality is None:
            cap = TREASURE_REGION_MAX_QUALITY.get(region_number, 2)
        else:
            cap = max(1, min(6, int(max_quality)))
        definitions = list(self._load_treasure_book())
        config = REGIONS.get(str(region_number), {})
        weights = None
        caps = None
        counts = None
        if region_specified:
            definitions = [item for item in definitions
                           if region_number in set(item.get('regions', []))]
            weights = config.get('treasure_quality_weights')
            caps = config.get('treasure_quality_caps')
            counts = getattr(self, '_adventure_treasure_quality_counts', None)
            if counts is None:
                counts = {}
                self._adventure_treasure_quality_counts = counts
        treasure, new_uid = TreasureService.generate(
            definitions, self._treasure_prefixes or [], self._treasure_uid,
            cap, PREFIX_GRADE_BY_QUALITY, random,
            quality_weights=weights, quality_counts=counts,
            quality_caps=caps)
        self._treasure_uid = new_uid
        if treasure is not None and counts is not None:
            quality = int(treasure.get('quality', 1))
            counts[quality] = counts.get(quality, 0) + 1
        return treasure


    def _roll_adventure_region_item(self, region_id):
        """按地区随机抽取一种可获得物品，数量为 0~3。"""
        try:
            region_number = int(region_id)
        except (TypeError, ValueError):
            return None, 0
        candidates = []
        for item_id, info in ITEMS.items():
            try:
                regions = {int(value) for value in info.get('regions', [])}
            except (TypeError, ValueError):
                continue
            if region_number in regions:
                candidates.append(item_id)
        if not candidates:
            return None, 0
        item_id = random.choice(candidates)
        amount = random.randint(0, 3)
        if amount <= 0:
            return item_id, 0
        actual = InventoryService.add(self.inventory, item_id, amount)
        return item_id, actual


    def _unlock_treasure_bonuses(self):
        if not any('鸡毛偶' in str(t.get('name', ''))
                   for t in self.treasures):
            return False
        if int(self.inventory.get('hat_ji', 0)) <= 0:
            self.inventory['hat_ji'] = 1
            return True
        return False

    def _success_chance(self, difficulty, region_id=1):
        """地区成功率：按地区满成功率等级计算，最高 80%。"""
        service = AdventureService(
            ITEMS, REGION_RECOMMENDED_LEVEL, QUALITY_NAMES, random,
            success_levels=REGION_SUCCESS_LEVELS, max_success=0.8)
        return service.success_chance(self.level, difficulty, region_id)


    def _event_damage(self, severity, region_id, difficulty):
        """按事件难度、地区和当前等级计算实际扣血。"""
        service = AdventureService(
            ITEMS, REGION_RECOMMENDED_LEVEL, QUALITY_NAMES, random)
        return service.event_damage(self.game, region_id, severity, difficulty)


    def _apply_event_reward(self, text, region_id=1, difficulty=1):
        """结算奖励/惩罚；宝藏按地区品质上限生成。"""
        service = AdventureService(
            ITEMS, REGION_RECOMMENDED_LEVEL, QUALITY_NAMES, random)
        return service.apply_reward(
            text, self.game, self.inventory, self.treasures,
            self._generate_treasure, region_id, difficulty)


    def _resolve_adventure_events(self, region_id, minutes,
                                  allow_early_fail=True):
        """按分钟抽取事件并逐条判定；每分钟 1 个事件。"""
        service = AdventureService(
            ITEMS, REGION_RECOMMENDED_LEVEL, QUALITY_NAMES, random,
            success_levels=REGION_SUCCESS_LEVELS, max_success=0.8)
        return service.resolve(
            self._load_event_book(), region_id, minutes, self.game,
            self.inventory, self.treasures, self._generate_treasure,
            allow_early_fail, EARLY_ADVENTURE_FAIL_HP)


    def _finish_adventure(self, simulated=False):
        """探险结束：结算基础收益、逐分钟事件和日志。"""
        self.motion.finish('adventure_wave', 'idle')
        self.motion.clear_expression('expression_jump')
        self._adventure_job = None
        self._adventure_departing = False
        self._adventure_end_time = None
        self.animations.cancel_many('adventure_depart', 'adventure_title')
        self._adventure_depart_job = None
        self._adventure_title_job = None
        if self.closing:
            return
        region_id = self._adventure_region or '1'
        region = REGIONS.get(region_id, REGIONS['1'])
        minutes = self._adventure_minutes or region.get('fixed_minutes', 5)
        self.adventuring = False
        self.root.deiconify()
        if not simulated:
            self._play_effect_sound(
                globals().get('ADVENTURE_RETURN_SOUND_PATH', ''), 'ling')

        base_gold = random.randint(ADVENTURE_REWARD_MIN, ADVENTURE_REWARD_MAX)
        self.gold += base_gold
        if region['fallback']:
            base_xp = XP_PLAIN
        else:
            xp_min = int(region.get('xp_per_min_min', XP_FOREST_PER_MIN_MIN))
            xp_max = int(region.get('xp_per_min_max', XP_FOREST_PER_MIN_MAX))
            base_xp = sum(random.randint(xp_min, xp_max)
                          for _ in range(max(1, minutes)))

        event_result = self._resolve_adventure_events(region_id, minutes)
        try:
            extra_max = max(0, int(region.get('extra_treasure_max', 0)))
        except (TypeError, ValueError):
            extra_max = 0
        try:
            average_success = max(
                0.0, min(0.8, float(event_result.get('average_success', 0.0))))
        except (TypeError, ValueError):
            average_success = 0.0
        extra_draw_count = (
            max(0, int(minutes)) // EXTRA_TREASURE_INTERVAL_MINUTES)
        extra_treasure_chance = min(
            1.0, average_success * EXTRA_TREASURE_CHANCE_FACTOR)
        extra_treasures = []
        for _ in range(extra_draw_count):
            if len(extra_treasures) >= extra_max:
                break
            if random.random() >= extra_treasure_chance:
                continue
            treasure = self._generate_treasure(region_id)
            if treasure is None:
                continue
            extra_treasures.append(treasure)
            event_result['treasures'].append(treasure)
            self.treasures.append(treasure)
        gained_xp = base_xp + event_result['xp']
        gained_gold = base_gold + event_result['gold_delta']
        early_fail = event_result.get('failed_early', False)
        loot_loss_lines = []
        region_item_id = None
        region_item_count = 0
        if early_fail:
            raw_xp = max(0, gained_xp)
            gained_xp = int(round(raw_xp * EARLY_ADVENTURE_REWARD_RATE))
            if gained_gold > 0:
                kept_gold = int(round(gained_gold * EARLY_ADVENTURE_REWARD_RATE))
                self.gold = max(0, self.gold - (gained_gold - kept_gold))
                gained_gold = kept_gold
            for item_id, delta in event_result['inventory_delta'].items():
                if delta <= 0:
                    continue
                loss = delta // 2
                if loss <= 0:
                    continue
                self.inventory[item_id] = max(
                    0, int(self.inventory.get(item_id, 0)) - loss)
                loot_loss_lines.append(
                    f"{ITEMS.get(item_id, {}).get('name', item_id)} -{loss}")
            gained_treasures = event_result.get('treasures', [])
            treasure_loss = len(gained_treasures) // 2
            if treasure_loss:
                lost_ids = {t.get('uid') for t in gained_treasures[-treasure_loss:]}
                self.treasures = [
                    t for t in self.treasures
                    if t.get('uid') not in lost_ids]
                loot_loss_lines.append(f'宝藏 -{treasure_loss}')
        region_item_id, region_item_count = self._roll_adventure_region_item(
            region_id)
        if not simulated:
            StatsService.record_gold_earned(self.game, max(0, gained_gold))
            StatsService.record_adventure(
                self.game, region_id, minutes, early_fail)
            background = {'1': 'plain', '2': 'forest', '3': 'valley'}.get(
                str(region_id))
            if background and (background != 'valley' or not early_fail):
                self.game.backgrounds.add(background)
        level_attrs = self._gain_exp(gained_xp)
        if not simulated:
            self._check_achievements()
        level_ups = len(level_attrs)
        emotion_loss = (max(1, minutes) // 5) * 2
        before_emotion = self.emotion
        self.emotion = max(0, self.emotion - emotion_loss)
        emotion_loss = before_emotion - self.emotion

        tag = '模拟·' if simulated else ''
        log_lines = [f'【{tag}{region["name"]}】{minutes} 分钟 · {region["difficulty"]}']
        if simulated:
            log_lines.append('模拟探险：不消耗面包，其余结算与正常探险一致')
        if unlocked_hat:
            log_lines.append('解锁装备：一只小鸡')
        if self._adventure_bread_cost:
            log_lines.append(f'出发消耗：面包 ×{self._adventure_bread_cost}')
        log_lines.append(f'基础收获：金币 +{base_gold}、经验 +{base_xp}')
        log_lines.append(f'事件结算：{minutes} 个事件')
        log_lines.extend(event_result['lines'])
        extra_text = ''
        if extra_treasures:
            names = [
                treasure.get('prefix', '') + treasure.get('name', '')
                for treasure in extra_treasures]
            extra_text = '：' + '、'.join(names)
        log_lines.append(
            f'额外宝藏判定：每 {EXTRA_TREASURE_INTERVAL_MINUTES} 分钟抽取 1 次，'
            f'共 {extra_draw_count} 次；平均成功率 {average_success:.0%} × '
            f'{EXTRA_TREASURE_CHANCE_FACTOR:.0%} = '
            f'{extra_treasure_chance:.0%}，获得 '
            f'{len(extra_treasures)}/{extra_max} 件{extra_text}')
        region_item_name = ITEMS.get(region_item_id, {}).get(
            'name', '无') if region_item_id else '无'
        log_lines.append(
            f'地区额外收获：{region_item_name} ×{region_item_count}（0~3）')
        if early_fail:
            log_lines.append('提前结束惩罚：金币/经验仅保留 40%')
            log_lines.append('物品损失：' + ('、'.join(loot_loss_lines)
                                             if loot_loss_lines else '无'))
        if level_ups:
            names = {'strength': '力量', 'wisdom': '智慧', 'agility': '敏捷'}
            gains_text = '、'.join(names.get(a, a) + ' +1' for a in level_attrs)
            log_lines.append(f'升级！达到 Lv.{self.level}（{gains_text}）')
        if emotion_loss:
            log_lines.append(f'情绪 -{emotion_loss}')
        log_lines.append(f'本次合计：金币 {gained_gold:+d}、经验 +{gained_xp}')

        unlocked_hat = self._unlock_treasure_bonuses()
        self.logs.append({'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                          'lines': log_lines})
        self.logs = self.logs[-20:]
        self._forced_expression = None
        self._scratch_wave_style = 'vertical'
        self._scratch_wave_offset = SCRATCH_OFFSET
        self._adventure_region = None
        self._adventure_minutes = 0
        self._adventure_bread_cost = 0
        self._event_book = None  # 下次探险重新读取，方便编辑事件簿后直接生效
        self._treasure_book = None
        self._treasure_prefixes = None
        self._save_satiety()
        self._refresh_warehouse()
        self._refresh_market()
        self._refresh_panel()
        try:
            self._refresh_adventure_page()
        except Exception:
            pass
        if self._check_hospital_state():
            return
        self.show_pose('normal')
        self.start_animations()
        self._schedule_walk_attempt()
        self._start_fall_check()
        self._schedule_hp_regen()


    def _fill_adventure_menu(self, adv_menu):
        """探险菜单：地区→时间 + 探险日志。"""
        if self.adventuring:
            adv_menu.add_command(label='（探险中…）', state='disabled')
            return
        for rid, region in REGIONS.items():
            recommended = region.get('recommended_level', 1)
            min_level = region.get('min_level', 1)
            if region['fallback']:
                adv_menu.add_command(
                    label=(f"{region['name']}（推荐 {recommended} 级 · "
                           f"{region.get('fixed_minutes', 5)} 分钟）"),
                    command=lambda r=rid, m=region.get('fixed_minutes', 5):
                    self._confirm_adventure(r, m))
            else:
                if self.level < min_level:
                    adv_menu.add_command(
                        label=f'{region["name"]}（等级不够哦，请先提升实力吧！）',
                        state='disabled')
                    continue
                sub = tk.Menu(adv_menu, tearoff=0)
                adv_menu.add_cascade(
                    label=f"{region['name']}（推荐 {recommended} 级）",
                    menu=sub)
                for t in EXPLORE_TIMES:
                    sub.add_command(
                        label=f'{t} 分钟',
                        command=lambda r=rid, m=t:
                        self._confirm_adventure(r, m))
        adv_menu.add_separator()
        adv_menu.add_command(label='探险日志', command=self.show_log)


    def _confirm_adventure(self, region_id, minutes):
        """探险出发确认，并显示面包消耗和状态警告。"""
        region = REGIONS.get(str(region_id))
        if region is None:
            return
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            return
        if region['fallback']:
            minutes = region.get('fixed_minutes', 5)
        bread_cost = 0
        if not region['fallback']:
            bread_cost = math.ceil(
                minutes / ADVENTURE_BREAD_MINUTES_PER_UNIT)
        lines = ['确定要探险吗？']
        if bread_cost:
            lines.append(f'探险会消耗 {bread_cost} 个面包。')
        else:
            lines.append('风和平原不消耗面包。')
        if self.level < region.get('recommended_level', 1):
            lines.append('警告：等级小于推荐等级')
        if self.hp < self.max_hp * 0.5:
            lines.append('警告：猫咪的活力不足')
        try:
            import tkinter.messagebox as mb
            if not mb.askyesno('探险确认', '\n'.join(lines)):
                return
        except Exception:
            return
        self.start_adventure(str(region_id), minutes)


    def show_log(self):
        """打开探险日志"""
        if (self._log_win is not None
                and self._log_win.winfo_exists()):
            self._log_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title('探险日志')
        win.geometry('520x420')
        win.attributes('-topmost', True)
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        win.after(80, lambda w=win: self._hide_from_taskbar(w))
        self._log_win = win
        txt = tk.Text(win, wrap='word', font=('Microsoft YaHei UI', 9))
        txt.pack(fill='both', expand=True, padx=6, pady=6)
        if not self.logs:
            txt.insert('end', '（还没有探险记录）\n')
        for log in reversed(self.logs):
            txt.insert('end', log['time'] + '\n')
            for line in log['lines']:
                txt.insert('end', '  ' + line + '\n')
            txt.insert('end', '\n')
        txt.config(state='disabled')
        win.protocol('WM_DELETE_WINDOW', self._close_log)


    def _close_log(self):
        if self._log_win is not None:
            try:
                self._log_win.destroy()
            except Exception:
                pass
            self._log_win = None


    def _cancel_adventure(self):
        """取消探险并让猫立即回来（不结算）"""
        self.adventuring = False
        self.motion.finish('adventure_wave', 'idle')
        self._forced_expression = None
        self._scratch_wave_style = 'vertical'
        self._scratch_wave_offset = SCRATCH_OFFSET
        self._adventure_departing = False
        self._adventure_end_time = None
        if self._adventure_job is not None:
            try:
                self.root.after_cancel(self._adventure_job)
            except Exception:
                pass
            self._adventure_job = None
        self.animations.cancel_many('adventure_depart', 'adventure_title')
        self._adventure_depart_job = None
        self._adventure_title_job = None
        self._adventure_minutes = 0
        self._adventure_region = None
        self._update_tray_title()
        try:
            self.root.deiconify()
        except Exception:
            pass
        # 取消探险也恢复被暂停的分钟计时
        self._schedule_hp_regen()


    def _adventure_remaining_minutes(self):
        if self._adventure_end_time is None:
            return max(0, int(self._adventure_minutes))
        remaining = max(0.0, self._adventure_end_time - time.monotonic())
        units = int(math.floor(remaining / 300.0 + 0.5))
        return max(0, units * 5)


    def _adventure_title_tick(self):
        self._adventure_title_job = None
        if self.closing or not self.adventuring:
            return
        self._update_tray_title()
        try:
            self._refresh_adventure_page()
        except Exception:
            pass
        self._adventure_title_job = self.animations.schedule('adventure_title', 
            ADVENTURE_TITLE_UPDATE_MS, self._adventure_title_tick)



def install_runtime_globals(namespace):
    globals().update(namespace)
