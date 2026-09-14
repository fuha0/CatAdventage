# -*- coding: utf-8 -*-
"""AdventureMixin 独立模块。"""
from services import AdventureService, TreasureService, InventoryService
from services.long_adventure import region_supports_long_adventure
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
            if minutes not in PLAIN_EXPLORE_TIMES:
                return
        elif minutes not in EXPLORE_TIMES:
            return
        if self.hp < HP_LOW_AT:
            self._adventure_notice('活力值不足 20，无法探险。')
            return
        # 等级低于地区最低要求不再拦截：允许硬闯，但成功率固定 10%
        # （由 AdventureService.success_chance 判定）。
        bread_cost = 0
        if not region['fallback']:
            bread_cost = math.ceil(
                minutes / ADVENTURE_BREAD_MINUTES_PER_UNIT)
            bread_count = InventoryService.count(self.inventory, 'bread')
            if bread_count < bread_cost:
                self._adventure_notice(
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
        # 出发记录写进探险日志（不弹窗）：消耗与风险提示都在这里。
        self._log_note(self._departure_lines(region, minutes, bread_cost))
        self._save_satiety()
        self._update_tray_title()
        self._start_adventure_departure()

    def _departure_lines(self, region, minutes, bread_cost):
        """短途出发要写进探险日志的内容（消耗 + 风险提示 + 预计归来）。"""
        lines = [f'【探险出发】{region.get("name", "远方")} · {minutes} 分钟']
        if bread_cost:
            lines.append(
                f'消耗面包 ×{bread_cost}（剩余 '
                f'{InventoryService.count(self.inventory, "bread")} 个）。')
        else:
            lines.append('风和平原不消耗面包。')
        try:
            min_level = int(region.get('min_level', 1) or 1)
            recommended = int(region.get('recommended_level', 1) or 1)
        except (TypeError, ValueError):
            min_level, recommended = 1, 1
        if not region.get('fallback') and self.level < min_level:
            lines.append(f'注意：未达最低等级 {min_level} 级，'
                         '本次探险的事件成功率固定只有 10%。')
        elif self.level < recommended:
            lines.append(f'注意：当前 {self.level} 级，'
                         f'低于推荐的 {recommended} 级。')
        if self.hp < self.max_hp * 0.5:
            lines.append(f'注意：活力偏低（{self.hp}/{self.max_hp}）。')
        lines.append('预计归来：' + time.strftime(
            '%Y-%m-%d %H:%M', time.localtime(time.time() + minutes * 60)))
        return lines


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
        # 长期冒险（>3 天）不挂一个「minutes * 60 * 1000」的定时器：那个
        # 定时器跨不过软件重启。改成先写出计划、再定期对表补齐进度。
        if getattr(self, '_long_adv_total_days', 0) > 0:
            self._begin_long_adventure_watch()
            return
        self._adventure_end_time = time.monotonic() + self._adventure_minutes * 60
        self._adventure_job = self.root.after(
            self._adventure_minutes * 60 * 1000, self._finish_adventure)
        self._adventure_title_job = self.animations.schedule('adventure_title', 
            ADVENTURE_TITLE_UPDATE_MS, self._adventure_title_tick)
        self._update_tray_title()

    # ---------- 长期冒险（大于 3 天） ----------

    def _long_adventure_plan(self):
        """当前存档里的长期冒险计划（不合法或没在进行时返回空字典）。"""
        plan = getattr(self.game, 'adventure', None)
        return plan if isinstance(plan, dict) and plan.get('active') else {}

    def _long_adventure_service(self):
        return LongAdventureService(ITEMS, REGIONS, random)

    def _long_adventure_region(self):
        """长期冒险所在地区（兜底风和平原）。"""
        plan = self._long_adventure_plan()
        region_id = str(plan.get('region', '') or '')
        if region_id not in REGIONS:
            region_id = str(self._adventure_region or '1')
        return region_id if region_id in REGIONS else '1'

    def _long_adventure_apply_reward(self, text, scale=1.0):
        """长期冒险的途中事件结算：不扣活力（hp_scale=0），金币经验按 scale 放大。"""
        service = self._adventure_service(with_success=False)
        return service.apply_reward(
            text, self.game, self.inventory, self.treasures,
            self._generate_treasure, self._long_adventure_region(), 1.0,
            reward_scale=scale, item_scale=1.0, hp_scale=0.0)

    def _long_adventure_send_letter(self, title, body):
        """投递一封冒险来信（内容写进存档，随存档持久化）。"""
        return send_adventure_letter(self.game, title, body)

    def start_long_adventure(self, region_id, days):
        """出发长期冒险：校验 → 扣面包 → 写计划 → 播离场动画。"""
        if self.adventuring or self.closing or self.hospitalized:
            return
        region = REGIONS.get(str(region_id))
        if region is None:
            return
        try:
            days = int(days)
        except (TypeError, ValueError):
            return
        if days not in LONG_EXPLORE_DAYS:
            return
        # 平原不消耗面包，也不适合长住；尚未实装的地区没有日收益口径，同样排除。
        if not region_supports_long_adventure(region):
            self._adventure_notice('这个地区不适合长期冒险，请选择低语森林或灰石谷。')
            return
        if self.level < int(region.get('min_level', 1)):
            self._adventure_notice(
                f"长期冒险需要 {region.get('min_level', 1)} 级，"
                f"当前 {self.level} 级，先练练级吧。")
            return
        if self.hp < HP_LOW_AT:
            self._adventure_notice('活力值不足 20，无法出发长期冒险。')
            return
        service = self._long_adventure_service()
        bread_cost = service.bread_cost(str(region_id), days)
        bread_count = InventoryService.count(self.inventory, 'bread')
        if bread_count < bread_cost:
            self._adventure_notice(
                f'面包不足：{days} 天的补给需要 {bread_cost} 个，'
                f'当前只有 {bread_count} 个。')
            return
        if not self.close_warehouse():
            return
        self.close_adventure()
        if bread_cost:
            InventoryService.remove(self.inventory, 'bread', bread_cost)
            self._save_satiety()
        plan = new_plan(str(region_id), days, time.time())
        plan['bread_cost'] = bread_cost
        self.game.adventure = plan
        self._adventure_region = str(region_id)
        self._adventure_minutes = int(plan['minutes'])
        self._adventure_bread_cost = bread_cost
        self._long_adv_total_days = days
        self._long_adv_last_lines = []
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
        # 出发记录写进探险日志（不弹窗）：用户随时能在日志里回看计划与消耗。
        self._log_note([
            f'【长期冒险出发】{region.get("name", "远方")} · {days} 天',
            f'补给消耗：面包 ×{bread_cost}（剩余 '
            f'{InventoryService.count(self.inventory, "bread")} 个）',
            f'预计归来：{time.strftime("%Y-%m-%d %H:%M", time.localtime(plan["ends_at"]))}',
            '探险期间可以关掉软件，重新打开后会按原计划继续推进。',
        ])
        # 计划先落盘：哪怕离场动画没播完就被关掉，重启后依然能接着走。
        self._save_satiety()
        self._update_tray_title()
        self._start_adventure_departure()

    def _begin_long_adventure_watch(self):
        """离场完成后启动定期检查；错过的天数在这里立刻补结算。"""
        plan = self._long_adventure_plan()
        if not plan:
            return
        self._adventure_departing = False
        self._adventure_end_time = None
        self._settle_long_adventure_progress(plan, time.time())
        self._update_tray_title()
        self._long_adv_job = self.root.after(
            LONG_ADVENTURE_CHECK_MS, self._long_adventure_tick)

    def _restore_long_adventure(self):
        """软件重启后恢复长期冒险：补齐进度、继续计时。"""
        plan = self._long_adventure_plan()
        if not plan:
            return False
        self._adventure_region = str(plan.get('region', '1'))
        self._adventure_minutes = int(plan.get('minutes', 0) or 0)
        self._adventure_bread_cost = int(plan.get('bread_cost', 0) or 0)
        self._long_adv_total_days = int(plan.get('days', 0) or 0)
        self._long_adv_last_lines = []
        self.adventuring = True
        self._adventure_departing = False
        try:
            self.root.withdraw()
        except Exception:
            pass
        if self._regen_job is not None:
            try:
                self.root.after_cancel(self._regen_job)
            except Exception:
                pass
            self._regen_job = None
        self._begin_long_adventure_watch()
        # 回到游戏时如果早该回来了，直接走归来流程。
        plan = self._long_adventure_plan()
        if plan and elapsed_days(plan, time.time()) >= int(plan.get('days', 1)):
            self._finish_long_adventure()
        return True

    def _long_adventure_tick(self):
        """长期冒险进度检查：结算已过完的天数，到点则归来。"""
        self._long_adv_job = None
        if self.closing or not self.adventuring:
            return
        plan = self._long_adventure_plan()
        if not plan:
            return
        now = time.time()
        self._settle_long_adventure_progress(plan, now)
        if elapsed_days(plan, now) >= int(plan.get('days', 1) or 1):
            self._finish_long_adventure()
            return
        self._update_tray_title()
        try:
            self._refresh_adventure_page()
        except Exception:
            pass
        self._long_adv_job = self.root.after(
            LONG_ADVENTURE_CHECK_MS, self._long_adventure_tick)

    def _settle_long_adventure_progress(self, plan, now):
        """把「已经过完但还没结算」的天数逐天结算并写日志。"""
        service = self._long_adventure_service()
        pending = [day for day in service.pending_days(plan)
                   if day <= elapsed_days(plan, now)]
        if not pending:
            return []
        results = service.settle_days(
            plan, pending, self.game, self.inventory, self.treasures,
            self._generate_treasure, self._long_adventure_apply_reward,
            self._long_adventure_send_letter)
        for day_index, detail in results:
            self._apply_long_adventure_day(detail)
        # 途中结算完立刻落盘：退出软件也不会丢已经拿到的收获与来信。
        self._save_satiety()
        return results

    def _apply_long_adventure_day(self, detail):
        """把某一天的结算结果记进日志与属性（金币/物品已在结算时入账）。"""
        region_name = detail.get('region_name', '远方')
        lines = [
            f"【长期冒险 · 第 {detail['day']} 天】{region_name}"
            f"（剩余约 {self._long_adventure_remaining_text()}）",
            f"当日收获：金币 +{detail['gold']}、经验 +{detail['xp']}",
        ]
        for event in detail.get('lines') or ():
            detail_text = '、'.join(event.get('parts') or ()) or '无额外收获'
            lines.append(
                f"途中事件 · {event.get('name', '见闻')}："
                f"{event.get('text', '')}（{detail_text}）")
        drops = []
        for item_id, count in (detail.get('items') or {}).items():
            name = (ITEMS.get(item_id) or {}).get('name', item_id)
            drops.append(f'{name} ×{count}')
        treasure_count = len(detail.get('treasures') or ())
        if treasure_count:
            drops.append(f'宝藏 ×{treasure_count}')
        if drops:
            lines.append('随身带回：' + '、'.join(drops))
        letter = detail.get('letter')
        if letter:
            lines.append(f"来信：{letter.get('title', '探险来信')}（已放进仓库·信件）")
        if detail['xp']:
            self._gain_exp(int(detail['xp']))
            StatsService.record_gold_earned(self.game, int(detail['gold']))
        self._long_adv_last_lines.extend(lines)
        self._pending_long_adv_lines = list(self._long_adv_last_lines)

    def _long_adventure_remaining_text(self):
        plan = self._long_adventure_plan()
        if not plan:
            return '即将归来'
        return remaining_text(plan, time.time())

    def _long_adventure_progress_text(self):
        """「第 X / N 天」进度文本。"""
        plan = self._long_adventure_plan()
        if not plan:
            return ''
        total = int(plan.get('days', 0) or 0)
        done = min(total, elapsed_days(plan, time.time()))
        return f'第 {done} / {total} 天'

    def _finish_long_adventure(self):
        """长期冒险归来：结算日志、解锁地区背景、恢复桌宠。"""
        self.motion.finish('adventure_wave', 'idle')
        self.motion.clear_expression('expression_jump')
        self._adventure_job = None
        self._adventure_departing = False
        self._adventure_end_time = None
        self.animations.cancel_many('adventure_depart', 'adventure_title')
        self._adventure_depart_job = None
        self._adventure_title_job = None
        if self._long_adv_job is not None:
            try:
                self.root.after_cancel(self._long_adv_job)
            except Exception:
                pass
            self._long_adv_job = None
        if self.closing:
            return
        plan = self._long_adventure_plan()
        region_id = str(plan.get('region', '') or self._adventure_region or '1')
        region = REGIONS.get(region_id, REGIONS['1'])
        total_days = int(plan.get('days', 0) or 0) or self._long_adv_total_days
        minutes = int(plan.get('minutes', 0) or 0) or self._adventure_minutes
        bread_cost = int(plan.get('bread_cost', 0) or 0)
        self.adventuring = False
        self.root.deiconify()
        self._play_effect_sound(
            globals().get('ADVENTURE_RETURN_SOUND_PATH', ''), 'ling')

        # 情绪：在外面待了这么多天，多少有点想家。
        before_emotion = self.emotion
        emotion_loss = max(0, int(LONG_ADVENTURE_EMOTION_LOSS_PER_DAY)) * max(
            1, total_days)
        self.emotion = max(0, self.emotion - emotion_loss)
        emotion_loss = before_emotion - self.emotion

        StatsService.record_adventure(self.game, region_id, minutes, False)
        # 来信数优先取计划里累计的值：途中结算过、后来重启过，也不会漏计。
        try:
            letter_count = max(0, int(plan.get('letters_sent', 0) or 0))
        except (TypeError, ValueError):
            letter_count = 0
        if not letter_count:
            letter_count = sum(1 for line in (self._long_adv_last_lines or ())
                               if str(line).startswith('来信：'))
        StatsService.record_long_adventure(self.game, total_days, letter_count)
        background = {'1': 'plain', '2': 'forest', '3': 'valley'}.get(region_id)
        if background:
            self.game.backgrounds.add(background)

        log_lines = [
            f'【长期冒险归来】{region["name"]} · {total_days} 天',
            f'按计划走完了全程，剩余时间 {self._long_adventure_remaining_text()}。',
        ]
        if bread_cost:
            log_lines.append(f'出发消耗：面包 ×{bread_cost}')
        # 途中的逐日记录可能很长（离线 30 天会攒几十条），入库前裁一下。
        detail_lines = list(self._long_adv_last_lines or ['途中一切平安。'])
        if len(detail_lines) > 40:
            detail_lines = (['（途中记录较多，这里只保留最近 40 行）'] +
                            detail_lines[-40:])
        log_lines.extend(detail_lines)
        if emotion_loss:
            log_lines.append(f'情绪 -{emotion_loss}（离家太久）')
        self._log_note(log_lines)

        # 计划结束，清掉存档里的进行状态。
        self.game.adventure = {}
        self._long_adv_total_days = 0
        self._long_adv_last_lines = []
        self._pending_long_adv_lines = []
        self._forced_expression = None
        self._scratch_wave_style = 'vertical'
        self._scratch_wave_offset = SCRATCH_OFFSET
        self._adventure_region = None
        self._adventure_minutes = 0
        self._adventure_bread_cost = 0
        self._adventure_treasure_quality_counts = {}
        self._event_book = None
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
        self._update_tray_title()
        # 归来不弹窗：完整结果已经写进探险日志（见上面的 log_lines）。


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
        """从该地区的可获得物品里随机抽 0~3 件，每件各 1 个。

        抽到的几件**可以是不同物品**（不重复取同一种），返回
        [(item_id, count), ...]；一件都没抽到时返回空列表。
        """
        try:
            region_number = int(region_id)
        except (TypeError, ValueError):
            return []
        candidates = []
        for item_id, info in ITEMS.items():
            try:
                regions = {int(value) for value in info.get('regions', [])}
            except (TypeError, ValueError):
                continue
            if region_number in regions:
                candidates.append(item_id)
        if not candidates:
            return []
        amount = random.randint(0, 3)
        if amount <= 0:
            return []
        picked = random.sample(candidates, min(amount, len(candidates)))
        gained = []
        for item_id in picked:
            if InventoryService.add(self.inventory, item_id, 1) > 0:
                gained.append((item_id, 1))
        return gained


    def _unlock_treasure_bonuses(self):
        if not any('鸡毛偶' in str(t.get('name', ''))
                   for t in self.treasures):
            return False
        if int(self.inventory.get('hat_ji', 0)) <= 0:
            self.inventory['hat_ji'] = 1
            return True
        return False

    def _adventure_service(self, with_success=True):
        """构造探险结算服务，统一注入各地区的最低等级与满成功率等级。

        min_levels 决定「等级不够时成功率固定 10%」这条规则；
        success_levels 决定达到最低等级后成功率爬到 95% 封顶所需的等级。
        """
        min_levels = {int(key): int(region.get('min_level', 1))
                      for key, region in REGIONS.items()}
        kwargs = {'min_levels': min_levels}
        if with_success:
            kwargs['success_levels'] = REGION_SUCCESS_LEVELS
            kwargs['max_success'] = 0.95
        return AdventureService(
            ITEMS, REGION_RECOMMENDED_LEVEL, QUALITY_NAMES, random, **kwargs)

    def _success_chance(self, difficulty, region_id=1):
        """事件成功率：未达地区最低等级固定 10%，否则地区基准 × 事件难度。"""
        service = self._adventure_service()
        return service.success_chance(self.level, difficulty, region_id)

    def _event_damage(self, severity, region_id, difficulty):
        """按惩罚强度、地区和当前等级计算实际扣血（难度已折进惩罚数值）。"""
        service = self._adventure_service(with_success=False)
        return service.event_damage(self.game, region_id, severity, difficulty)

    def _apply_event_reward(self, text, region_id=1, difficulty=1):
        """结算奖励/惩罚；宝藏按地区品质上限生成。"""
        service = self._adventure_service(with_success=False)
        return service.apply_reward(
            text, self.game, self.inventory, self.treasures,
            self._generate_treasure, region_id, difficulty)

    def _resolve_adventure_events(self, region_id, minutes,
                                  allow_early_fail=True):
        """按分钟抽取事件并逐条判定；每 5 分钟 1 个事件。"""
        service = self._adventure_service()
        return service.resolve(
            self._load_event_book(), region_id, minutes, self.game,
            self.inventory, self.treasures, self._generate_treasure,
            allow_early_fail, EARLY_ADVENTURE_FAIL_HP)


    def _finish_adventure(self, simulated=False):
        """探险结束：结算基础收益、逐次事件和日志。"""
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

        inventory_before = {str(k): int(v) for k, v in self.inventory.items()}
        event_result = self._resolve_adventure_events(region_id, minutes)
        failure_count = int(event_result.get('failure_count', 0) or 0)
        base_extra_chance_points = min(
            100, (max(1, int(minutes)) // 5) * 20)
        failure_penalty_points = sum(
            random.randint(5, 10) for _ in range(failure_count))
        extra_treasure_chance_points = max(
            0, base_extra_chance_points - failure_penalty_points)
        extra_treasure_chance = extra_treasure_chance_points / 100.0
        expected_extra_treasures = extra_treasure_chance * 3.0
        extra_treasure_count = max(
            0, min(3, int(expected_extra_treasures + 0.5)))
        extra_treasures = []
        for _ in range(extra_treasure_count):
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
        region_items = []
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
        region_items = self._roll_adventure_region_item(region_id)
        item_drop_totals = {}
        for item_id, after in self.inventory.items():
            delta = int(after) - inventory_before.get(str(item_id), 0)
            if delta > 0:
                item_drop_totals[item_id] = delta
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
        unlocked_hat = self._unlock_treasure_bonuses()
        log_lines = [
            f'【探险归来·{tag}{region["name"]}】{minutes} 分钟 · '
            f'{region["difficulty"]}']
        if simulated:
            log_lines.append('模拟探险：不消耗面包，其余结算与正常探险一致')
        if unlocked_hat:
            log_lines.append('解锁装备：一只小鸡')
        if self._adventure_bread_cost:
            log_lines.append(f'出发消耗：面包 ×{self._adventure_bread_cost}')
        log_lines.append(f'基础收获：金币 +{base_gold}、经验 +{base_xp}')
        log_lines.append(f'事件结算：{minutes // 5}个事件（每5分钟1次）')
        log_lines.extend(event_result['lines'])
        extra_text = ''
        if extra_treasures:
            names = [
                treasure.get('prefix', '') + treasure.get('name', '')
                for treasure in extra_treasures]
            extra_text = '：' + '、'.join(names)
        log_lines.append(
            f'额外宝藏判定：基础 {base_extra_chance_points}% - 失败惩罚 '
            f'{failure_penalty_points}% = {extra_treasure_chance_points}%，'
            f'预计 {expected_extra_treasures:.1f} 件，获得 '
            f'{len(extra_treasures)}/3 件{extra_text}')
        if region_items:
            region_item_text = '、'.join(
                f"{ITEMS.get(item_id, {}).get('name', item_id)} ×{count}"
                for item_id, count in region_items)
        else:
            region_item_text = '无'
        log_lines.append(
            f'地区额外收获：{region_item_text}（抽 0~3 件，可为不同物品）')
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
        drop_parts = []
        for item_id, count in item_drop_totals.items():
            item_name = ITEMS.get(item_id, {}).get('name', item_id)
            drop_parts.append(f'{item_name} ×{count}')
        treasure_count = len(event_result.get('treasures', []))
        if treasure_count:
            drop_parts.append(f'宝藏 ×{treasure_count}')
        drop_text = '、'.join(drop_parts) or '无'
        log_lines.append(f'本次合计：金币 {gained_gold:+d}、经验 +{gained_xp}、掉落物品：{drop_text}')

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
            if region.get('fallback'):
                plain_menu = tk.Menu(adv_menu, tearoff=0)
                adv_menu.add_cascade(
                    label=f'{region["name"]}（推荐 {recommended}级 · 不消耗面包）',
                    menu=plain_menu)
                for t in PLAIN_EXPLORE_TIMES:
                    plain_menu.add_command(
                        label=f'{t} 分钟',
                        command=lambda r=rid, m=t:
                        self._confirm_adventure(r, m))
                continue
            # 未达最低等级不再禁止出发：可以硬闯，但成功率固定只有 10%。
            if self.level < min_level:
                label = (f'{region["name"]}（未达最低等级 {min_level} 级，'
                         f'成功率仅 10%）')
            else:
                label = f'{region["name"]}（推荐 {recommended}级）'
            sub = tk.Menu(adv_menu, tearoff=0)
            adv_menu.add_cascade(label=label, menu=sub)
            for t in EXPLORE_TIMES:
                sub.add_command(
                    label=f'{t}分钟',
                    command=lambda r=rid, m=t:
                    self._confirm_adventure(r, m))
        adv_menu.add_separator()
        adv_menu.add_command(label='探险日志', command=self.show_log)


    def _confirm_adventure(self, region_id, minutes):
        """短途探险出发：直接出发，不弹确认框。

        消耗与风险提示由 start_adventure 写进探险日志（见 _log_departure）。
        """
        region = REGIONS.get(str(region_id))
        if region is None:
            return
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            return
        if region['fallback'] and minutes not in PLAIN_EXPLORE_TIMES:
            return
        self.start_adventure(str(region_id), minutes)


    def _log_note(self, lines):
        """往探险日志里追加一条记录（不落盘，由调用方决定何时保存）。"""
        if isinstance(lines, str):
            lines = [lines]
        lines = [str(line) for line in lines if str(line or '').strip()]
        if not lines:
            return
        self.logs.append({
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'lines': lines,
        })
        self.logs = self.logs[-20:]
        self._refresh_log_window()

    def _refresh_log_window(self):
        """日志窗口开着的话，重新渲染一遍内容。"""
        win = getattr(self, '_log_win', None)
        if win is None:
            return
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return
        try:
            self._close_log()
            self.show_log()
        except Exception:
            pass

    def _adventure_notice(self, text):
        """探险校验不通过时的提示：写进日志 + 页面内联红字，不弹窗。"""
        self._log_note(f'【探险】{text}')
        try:
            self._refresh_adventure_page()
        except Exception:
            pass
        label = getattr(self, '_adventure_unlock_label', None)
        if label is not None:
            try:
                label.config(text=str(text))
            except Exception:
                pass

    def show_log(self):
        """打开探险日志"""
        if (self._log_win is not None
                and self._log_win.winfo_exists()):
            self._log_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title('探险日志')
        win.geometry(f'{dp(520)}x{dp(420)}')
        win.attributes('-toolwindow', True)
        self._hide_from_taskbar(win)
        win.after(80, lambda w=win: self._hide_from_taskbar(w))
        self._log_win = win
        txt = tk.Text(win, wrap='word', font=('Microsoft YaHei UI', 9))
        txt.pack(fill='both', expand=True, padx=6, pady=6)
        if not self.logs:
            txt.insert('end', '（还没有探险记录）\n')
        cat_name = str(getattr(self, 'cat_name', '') or '猫猫').strip() or '猫猫'
        for log in reversed(self.logs):
            txt.insert('end', log['time'] + '\n')
            for line in log['lines']:
                display_line = str(line).replace('你', cat_name)
                txt.insert('end', '  ' + display_line + '\n')
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
        """取消探险并让猫立即回桌面，不结算也不记录统计。"""
        if not self.adventuring:
            return
        # 长期冒险的「进度」在存档里，取消时必须把计划一并清掉，
        # 否则重启又会被恢复成「还在探险」。
        long_plan = self._long_adventure_plan()
        if long_plan:
            region_name = (REGIONS.get(str(long_plan.get('region', ''))) or
                           {}).get('name', '远方')
            total_days = int(long_plan.get('days', 0) or 0)
            settled_days = int(long_plan.get('settled_days', 0) or 0)
            bread_cost = int(long_plan.get('bread_cost', 0) or 0)
            self.game.adventure = {}
            self._long_adv_total_days = 0
            self._long_adv_last_lines = []
            self._pending_long_adv_lines = []
            if self._long_adv_job is not None:
                try:
                    self.root.after_cancel(self._long_adv_job)
                except Exception:
                    pass
                self._long_adv_job = None
            # 取消不弹窗：把中止结果与消耗写进探险日志。
            cancel_lines = [
                f'【长期冒险取消】{region_name} · 计划 {total_days} 天，'
                f'已走 {settled_days} 天',
                '提前中止，这次途中的收获全部作废。',
            ]
            if bread_cost:
                cancel_lines.append(f'出发时的补给不退还（面包 ×{bread_cost}）。')
            self._log_note(cancel_lines)
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
        self._adventure_bread_cost = 0
        self._adventure_treasure_quality_counts = {}
        self._find_cat(reset_scale=False)
        # 取消探险恢复被暂停的分钟计时，不触发结算或累计统计。
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
