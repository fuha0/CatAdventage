# -*- coding: utf-8 -*-
"""InteractionAnimationMixin 独立模块。"""


class InteractionAnimationMixin:
    def _scaled_hand_pair(self, width, height):
        hand = self.parts.get('hand')
        if hand is None:
            return None, None
        width = max(1, int(width))
        height = max(1, int(height))
        cache = self._get_render_cache()
        small = cache.get_or_create(
            'display', ('hand', width, height),
            lambda: self._resize_rgba(hand, (width, height)))
        mirror = cache.get_or_create(
            'display', ('hand-mirror', width, height),
            lambda: small.transpose(PIL.Image.FLIP_LEFT_RIGHT))
        return small, mirror

    def _screen_width(self):
        """缓存屏幕宽度，避免动画每帧调用 Tk。"""
        value = getattr(self, '_screen_width_cache', None)
        if value is None:
            value = int(self.root.winfo_screenwidth())
            self._screen_width_cache = value
        return value

    def _screen_height(self):
        """缓存屏幕高度，避免动画每帧调用 Tk。"""
        value = getattr(self, '_screen_height_cache', None)
        if value is None:
            value = int(self.root.winfo_screenheight())
            self._screen_height_cache = value
        return value

    def _remember_pointer_root(self, event):
        """记下鼠标的屏幕坐标，供 _window_pos 反算窗口位置。"""
        try:
            self._drag_root_x = int(event.x_root)
            self._drag_root_y = int(event.y_root)
        except (TypeError, ValueError):
            self._drag_root_x = None
            self._drag_root_y = None

    def _window_pos(self):
        """返回窗口左上角的屏幕坐标。

        拖拽期间不要读 winfo_x()/winfo_y()：Tk 的 geometry() 只是提交移动请求，
        winfo_* 要等空闲周期才刷新。快速「按下-拖拽-松开」时，最后一次移动和
        松手事件落在同一批里，中间没有空闲周期，读回来的是滞后一整段位移的
        旧坐标，松手时会把猫咪往任务栏方向误判成攀爬。

        拖拽时窗口位置本来就是「鼠标屏幕坐标 - 抓取偏移」算出来的，这里套用
        同一个公式反算，结果必然与刚下发的移动指令一致，且不受 Tk 刷新时机影响。
        """
        if getattr(self, '_drag_pos_valid', False):
            root_x = getattr(self, '_drag_root_x', None)
            root_y = getattr(self, '_drag_root_y', None)
            if root_x is not None and root_y is not None:
                return (root_x - int(self.drag_start_x),
                        root_y - int(self.drag_start_y))
        return int(self.root.winfo_x()), int(self.root.winfo_y())

    def _sync_airborne_window_position(self):
        """仅在真正空中时同步最终坐标，避免单击误用残留值。"""
        if not (getattr(self, 'flinging', False)
                or getattr(self, 'falling', False)):
            return
        if not (hasattr(self, '_airborne_x') and hasattr(self, '_airborne_y')):
            return
        try:
            x, y = int(self._airborne_x), int(self._airborne_y)
            self.root.geometry(f'+{x}+{y}')
        except Exception:
            pass

    def _get_native_window_mover(self):
        """初始化一次 Win32 移动函数，避免每帧重复设置 ctypes。"""
        mover = getattr(self, '_native_window_mover', None)
        if getattr(self, '_native_window_mover_ready', False):
            return mover
        try:
            import ctypes
            user32 = ctypes.windll.user32
            raw = int(self.root.winfo_id())
            user32.GetParent.restype = ctypes.c_void_p
            user32.GetParent.argtypes = [ctypes.c_void_p]
            hwnd = user32.GetParent(ctypes.c_void_p(raw))
            if not hwnd:
                hwnd = ctypes.c_void_p(raw)
            user32.SetWindowPos.restype = ctypes.c_bool
            user32.SetWindowPos.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            flags = 0x0001 | 0x0004 | 0x0010  # NOSIZE | NOZORDER | NOACTIVATE

            def move(px, py):
                return bool(user32.SetWindowPos(hwnd, None, px, py, 0, 0, flags))

            self._native_window_handle = hwnd
            self._native_window_mover = move
            self._native_window_mover_ready = True
            return move
        except Exception:
            self._native_window_mover = None
            self._native_window_mover_ready = True
            return None

    def _move_window_position(self, x, y):
        """优先用 Win32 SetWindowPos 移动顶层窗口，失败时回退 Tk geometry。"""
        x, y = int(x), int(y)
        try:
            mover = self._get_native_window_mover()
            if mover is not None and mover(x, y):
                return
        except Exception:
            pass
        self.root.geometry(f'+{x}+{y}')


    def _climb_hand_pastes(self):
        """攀爬时双手的位置（1024 画布坐标）。返回 [(art, x, y)]，art 取 'left'/'right'。

        单独抽出来是为了让「全过程合成」和「显示尺寸贴手」共用同一份几何，
        避免两条渲染通路的坐标慢慢漂移。
        """
        hand = self.parts.get('hand')
        if hand is None:
            return None
        hw, hh = hand.size
        (lx, ly), (rx, ry) = self._hand_base_positions()
        t = max(0.0, min(1.0, getattr(self, '_climb_hand_progress', 0.0)))
        # t == 0 时即「双手自然垂在身侧」，与 _compose_pose 的静止手位一致
        edge_y = max(0, min(1024 - hh,
                            getattr(self, '_climb_edge_y', 0) - hh // 2))
        target_lx = max(0, lx - int(22 * t))
        target_rx = min(1024 - hw, rx + int(22 * t))
        lx = int(lx + (target_lx - lx) * t)
        rx = int(rx + (target_rx - rx) * t)
        ly = int(ly + (edge_y - ly) * t)
        ry = int(ry + (edge_y - ry) * t)
        return [('left', lx, ly), ('right', rx, ry)]

    def _paste_climb_hands(self, canvas):
        """攀爬任务栏时双手向上抓住边缘，再随身体上移。"""
        hand = self.parts.get('hand')
        pastes = self._climb_hand_pastes()
        if hand is None or pastes is None:
            return
        right_hand = hand.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        for art, x, y in pastes:
            img = hand if art == 'left' else right_hand
            canvas.paste(img, (int(x), int(y)), img)


    def _paste_fling_hands(self, canvas):
        """甩飞时双手向速度相反方向拖尾，速度越大偏移越明显。"""
        hand = self.parts.get('hand')
        if hand is None:
            return
        right_hand = hand.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        (lx, ly), (rx, ry) = self._hand_base_positions()
        speed = math.hypot(self._fling_vx, self._fling_vy)
        if speed > 0.01:
            nx, ny = self._fling_vx / speed, self._fling_vy / speed
            power = min(1.0, speed / AIRBORNE_MAX_SPEED)
            dx = -nx * 155.0 * power
            dy = -ny * 110.0 * power
            if self.facing_right:
                dx = -dx
            lx += dx * 1.30
            rx += dx * 0.70
            ly += dy
            ry += dy
        hw, hh = hand.size
        max_x = max(0, canvas.width - hw)
        max_y = max(0, canvas.height - hh)
        lx = max(0, min(max_x, int(lx)))
        rx = max(0, min(max_x, int(rx)))
        ly = max(0, min(max_y, int(ly)))
        ry = max(0, min(max_y, int(ry)))
        canvas.paste(hand, (lx, ly), hand)
        canvas.paste(right_hand, (rx, ry), right_hand)


    def _paste_fling_hands_scaled(self, frame, size):
        """在已经缩放好的窗口图上贴拖尾手，避免每帧合成 1024 图。"""
        hand = self.parts.get('hand')
        if hand is None:
            return frame
        scale = size / 1024.0
        hw = max(1, int(hand.width * scale))
        hh = max(1, int(hand.height * scale))
        left_hand, right_hand = self._scaled_hand_pair(hw, hh)
        if left_hand is None:
            return frame
        (lx, ly), (rx, ry) = self._hand_base_positions()
        speed = math.hypot(self._fling_vx, self._fling_vy)
        if speed > 0.01:
            nx, ny = self._fling_vx / speed, self._fling_vy / speed
            power = min(1.0, speed / AIRBORNE_MAX_SPEED)
            dx = -nx * 155.0 * power
            dy = -ny * 110.0 * power
            if self.facing_right:
                dx = -dx
            lx += dx * 1.30
            rx += dx * 0.70
            ly += dy
            ry += dy
        if self.facing_right:
            lx = 1024.0 - lx - hand.width
            rx = 1024.0 - rx - hand.width
        lx, rx = int(lx * scale), int(rx * scale)
        ly, ry = int(ly * scale), int(ry * scale)
        max_x = max(0, frame.width - hw)
        max_y = max(0, frame.height - hh)
        lx = max(0, min(max_x, lx))
        rx = max(0, min(max_x, rx))
        ly = max(0, min(max_y, ly))
        ry = max(0, min(max_y, ry))
        frame.paste(left_hand, (lx, ly), left_hand)
        frame.paste(right_hand, (rx, ry), right_hand)
        return frame


    def _render_airborne_frame(self, size, visual_key):
        """用缓存的小尺寸身体图和手部叠加渲染甩飞/下落帧。"""
        base = self._get_display_image(self.pose, (size, size),
                                       with_hands=False)
        frame = base.copy()
        frame = self._paste_fling_hands_scaled(frame, size)
        key = ('airborne', visual_key, size)
        cache = self._get_render_cache()
        self.photo = cache.get_or_create(
            'photo', key, lambda: PIL.ImageTk.PhotoImage(frame))
        self.label.config(image=self.photo)

    def _apply_hand_layer_scaled(self, frame, size, pastes):
        """把 1024 画布坐标的手位贴到「显示尺寸」的帧上。

        frame 来自 _get_display_image(..., with_hands=False)，也就是
        **已经**过 _oriented() 朝右翻转的图；而 pastes 用的是「未翻转画布」
        坐标（和 _compose_pose 里一致）。所以朝右时要再镜像一次：
        位置镜像 + 手图取镜像版，结果等价于 resize(_oriented(整图))。
        """
        hand = self.parts.get('hand')
        if hand is None or not pastes:
            return frame
        sc = size / 1024.0
        hw, hh = hand.size
        sw = max(1, int(hw * sc))
        sh = max(1, int(hh * sc))
        small, mirror = self._scaled_hand_pair(sw, sh)
        if small is None:
            return frame
        flipped = bool(self.facing_right)
        max_x = max(0, frame.width - sw)
        max_y = max(0, frame.height - sh)
        for art, x, y in pastes:
            img = small if art == 'left' else mirror
            if flipped:
                x = 1024 - x - hw
                img = mirror if art == 'left' else small
            px = max(0, min(max_x, int(x * sc)))
            py = max(0, min(max_y, int(y * sc)))
            frame.paste(img, (px, py), img)
        return frame

    def _render_hand_frame(self, pose, size, pastes):
        """用「缓存的身体底图 + 显示尺寸贴手」渲染一帧手部动画。

        为什么必须这样：走全过程合成的话，手位每变一点就要重合成 1024
        （合成 ~53ms + 缩放 ~40ms），于是名义 5ms 一帧的抬手、33ms 一帧的
        攀爬，实际都只有 10 帧/秒 —— 看起来就是一顿一顿的。

        身体底图和手位无关（with_hands=False 时手部状态不进缓存键），
        所以底图只算一次并常驻缓存；每帧只做「拷贝 + 贴两只手」，
        实测约 0.02ms，剩下的开销只有把像素交给 Tk 那一下。
        """
        # 'scratch' 姿势本身不改身体也不改脸（_compose_pose 里只有
        # drag / blink / tail 三个姿势有专门分支），它的身体底图与 'normal'
        # 逐像素相同。直接复用 'normal' 就能命中启动时预热好的那张，
        # 于是第一次挠头也不会先停 90ms 去合成一张完全一样的图。
        # 这个前提由 test_hand_frame_equiv.py 的断言守着。
        body_pose = 'normal' if pose == 'scratch' else pose
        base = self._get_display_image(body_pose, (size, size),
                                       with_hands=False)
        frame = base.copy()
        # 招手/舔手时叠加呼吸：身体底图做纵向极小幅缩放（脚底对齐），
        # 手再按动作手位贴上去 —— 这样「只有手在动」的待机动作也有了
        # 呼吸感，与静止站立呼吸共用同一套周期/幅度参数。
        if getattr(self, '_idle_hand_action', None) in ('wave', 'lick'):
            frame = self._apply_breath_scale(frame, size, time.monotonic())
        self._apply_hand_layer_scaled(frame, size, pastes)
        # 不做 PhotoImage 缓存：每帧像素都不同，缓存下来只会把有用的帧挤出去
        self.photo = PIL.ImageTk.PhotoImage(frame)
        self.label.config(image=self.photo)


    def _paste_fall_hands(self, canvas):
        """下落时双手在头上；回弹过程中逐渐放回身侧"""
        hand = self.parts.get('hand')
        if hand is None:
            return
        right = hand.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        (bl_x, bl_y), (br_x, br_y) = self._hand_base_positions()
        t = max(0.0, min(1.0, getattr(self, '_hand_lift', 0.0)))
        head_l = (195, 140)
        head_r = (675, 140)
        lx = int(bl_x + (head_l[0] - bl_x) * t)
        ly = int(bl_y + (head_l[1] - bl_y) * t)
        rx = int(br_x + (head_r[0] - br_x) * t)
        ry = int(br_y + (head_r[1] - br_y) * t)
        canvas.paste(hand, (lx, ly), hand)
        canvas.paste(right, (rx, ry), right)


    def _hand_base_positions(self):
        """双手在画布中的基准位置 (left, right)。"""
        hand = self.parts.get('hand')
        cb = self._clothes_bbox()
        if hand is None or not cb:
            return (0, 0), (0, 0)
        hw, hh = hand.size
        hy = int(cb[1] + (cb[3] - cb[1]) * 0.62) - HAND_UP_OFFSET
        lx = int(cb[0] + 2) - HAND_SIDE_OFFSET
        rx = int(cb[2] - hw - 2) + HAND_SIDE_OFFSET
        return (lx, hy), (rx, hy)

    def _hand_frame_ms(self):
        """手部动画（挠头抬手 / 攀爬）的帧间隔。

        固定走「快档」而不跟随 30/60 帧设置：这两处的诉求就是看得顺，
        而且单帧只贴两只手（约 1ms），全程不过几百毫秒，开销可以忽略。
        取值见 HAND_FRAME_MS 的注释（要贴着系统定时器 tick 取）。
        """
        return HAND_FRAME_MS


    def _paste_reach_hands(self, canvas):
        """抓鼠标动作：靠近鼠标的那只手移动到当前手位，另一只手留在身侧"""
        hand = self.parts.get('hand')
        if hand is None:
            return
        (lx, ly), (rx, ry) = self._hand_base_positions()
        hx, hy = getattr(self, '_reach_hand_pos', (0, 0))
        if self._reach_hand == 'left':
            lx, ly = hx, hy
        else:
            rx, ry = hx, hy
        canvas.paste(hand, (int(lx), int(ly)), hand)
        right_hand = hand.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        canvas.paste(right_hand, (int(rx), int(ry)), right_hand)


    def _paste_jump_hands(self, canvas):
        """跳远动作中两手的位置（准备摆动/前伸/扒墙）"""
        hand = self.parts.get('hand')
        if hand is None:
            return
        mode = self._jump_hand_mode
        hw, hh = hand.size
        right = hand.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        if mode == 'swing_up':
            pos = ((160, 250), (700, 250))
        elif mode == 'swing_down':
            pos = ((150, 560), (710, 560))
        elif mode == 'wall_up':
            if self._jump_dir < 0:  # 贴左墙
                pos = ((40, 150), (180, 250))
            else:
                pos = ((700, 250), (860, 150))
        else:  # forward 前伸
            pos = ((250, 480), (610, 480))
        if self.facing_right and mode != 'wall_up':
            pos = tuple((1024 - x - hw, y) for x, y in pos)
        canvas.paste(hand, pos[0], hand)
        canvas.paste(right, pos[1], right)


    def _scratch_hand_pastes(self):
        """挠头时双手的位置（1024 画布坐标）。返回 [(art, x, y)]。

        与 _climb_hand_pastes 同理：抽成单一来源，供全过程合成和
        显示尺寸贴手共用。
        """
        hand = self.parts.get('hand')
        cb = self._clothes_bbox()
        if hand is None or not cb:
            return None
        hw, hh = hand.size
        hy = int(cb[1] + (cb[3] - cb[1]) * 0.62) - HAND_UP_OFFSET
        lx = int(cb[0] + 2) - HAND_SIDE_OFFSET
        rx = int(cb[2] - hw - 2) + HAND_SIDE_OFFSET
        stage = max(-1.0, min(1.0, float(getattr(self, '_scratch_stage', 0.0))))
        if self._scratch_side == 'left':
            lift_x = SCRATCH_LEFT_X
        else:
            lift_x = SCRATCH_RIGHT_X
        wave_style = getattr(self, '_scratch_wave_style', 'vertical')
        if wave_style == 'fan':
            wave_x = int(getattr(self, '_scratch_wave_x_offset', 56))
            wave_y = int(getattr(self, '_scratch_wave_y_offset', 14))
            lift_x += int(stage * wave_x)
            target_y = SCRATCH_HAND_Y - int(abs(stage) * wave_y)
        else:
            wave_offset = getattr(self, '_scratch_wave_offset', SCRATCH_OFFSET)
            target_y = SCRATCH_HAND_Y + stage * wave_offset
        # 抬起/落下轨迹：0=身侧位置，1=头部目标位置
        lift = max(0.0, min(1.0, getattr(self, '_scratch_lift', 1.0)))
        lift_y = int(hy + (target_y - hy) * lift)
        if self.facing_right:
            lx, rx = 1024 - lx - hw, 1024 - rx - hw
            lift_x = 1024 - lift_x - hw
        if self._scratch_side == 'left':
            return [('right', rx, hy), ('left', lift_x, lift_y)]
        return [('left', lx, hy), ('right', lift_x, lift_y)]

    def _idle_hand_ease(self, t):
        """抬手/放下的包络：t 走 0→1，前 RAISE_T 段抬手、末 RAISE_T 段放下。

        中间段返回值恒为 1，摆动/舔交给各动作自己算 —— 这样「抬手 /
        保持 / 放下」三段共用同一个 t，两条渲染通路也就不会分叉。
        末段的「放下」让手自然回到身侧，而不是动作一结束就瞬间复位。

        缓动：抬手用 cubic-out（较快起步、接近目标自然减速），放下用
        cubic-in（开始慢、加速落下，有重力感）—— 之前的纯线性抬放太
        「机械匀速」，不像真猫抬手。
        """
        raise_t = max(0.05, float(globals().get('IDLE_HAND_RAISE_T', 0.30)))
        if t <= raise_t:
            e = max(0.0, min(1.0, t / raise_t))
            return 1.0 - (1.0 - e) ** 3          # cubic-out 抬手
        if t >= 1.0 - raise_t:
            e = max(0.0, min(1.0, (1.0 - t) / raise_t))
            return e ** 3                         # cubic-in 放下
        return 1.0

    def _idle_hand_hold_phase(self, t):
        """摆动/舔的相位：只在「保持段」里从 0 走到 1，抬手和放下段恒为 0。

        和 _idle_hand_ease 共用同一个 raise_t，保证两段边界对齐。
        """
        raise_t = max(0.05, float(globals().get('IDLE_HAND_RAISE_T', 0.30)))
        hold_start, hold_end = raise_t, 1.0 - raise_t
        if t <= hold_start or t >= hold_end:
            return 0.0
        return (t - hold_start) / max(1e-6, hold_end - hold_start)

    def _wave_hand_pastes(self):
        """招手时两只手的位置（1024 画布坐标）。返回 [(art, x, y)]。

        一只手留在身侧，另一只手抬到头侧左右摆。摆动只由 _idle_hand_t
        和 _idle_hand_phase 决定，不用随机数 —— 全过程合成与显示尺寸贴手
        必须算出完全一样的坐标，否则两条通路会慢慢漂移。
        """
        hand = self.parts.get('hand')
        if hand is None:
            return None
        (lx, ly), (rx, ry) = self._hand_base_positions()
        t = max(0.0, min(1.0, float(getattr(self, '_idle_hand_t', 0.0))))
        phase = 1.0 if float(getattr(self, '_idle_hand_phase', 1.0)) >= 0 else -1.0
        if getattr(self, '_idle_hand_side', 'left') == 'left':
            # 抬左手：左手从自己的基准位置出发，右手留在身侧
            start_x, start_y = lx, ly
            rest_art, rest_x, rest_y = 'right', rx, ry
            wave_x = int(globals().get('WAVE_LEFT_X', 150))
        else:
            # 抬右手：右手从自己的基准位置出发，左手留在身侧
            start_x, start_y = rx, ry
            rest_art, rest_x, rest_y = 'left', lx, ly
            wave_x = int(globals().get('WAVE_RIGHT_X', 735))
        target_y = int(globals().get('WAVE_HAND_Y', 232))
        ease = self._idle_hand_ease(t)
        x = int(start_x + (wave_x - start_x) * ease)
        y = int(start_y + (target_y - start_y) * ease)
        if ease >= 1.0:
            u = self._idle_hand_hold_phase(t)
            cycles = float(globals().get('WAVE_CYCLES', 2.5))
            swing = math.sin(u * math.tau * cycles) * phase
            x += int(swing * float(globals().get('WAVE_SWING_X', 42)))
            y += int(swing * float(globals().get('WAVE_SWING_Y', 12)))
        return [(rest_art, rest_x, rest_y),
                (getattr(self, '_idle_hand_side', 'left'), x, y)]

    def _lick_hand_pastes(self):
        """舔手时两只手的位置（1024 画布坐标）。

        一只手抬到嘴边（略微偏向自己那一侧，别把嘴整个盖住），上下舔几下。
        """
        hand = self.parts.get('hand')
        if hand is None:
            return None
        hw, hh = hand.size
        (lx, ly), (rx, ry) = self._hand_base_positions()
        t = max(0.0, min(1.0, float(getattr(self, '_idle_hand_t', 0.0))))
        if getattr(self, '_idle_hand_side', 'left') == 'left':
            # 舔左手：左手从自己的基准位置出发，右手留在身侧
            start_x, start_y = lx, ly
            rest_art, rest_x, rest_y = 'right', rx, ry
            lick_x = int(globals().get('LICK_LEFT_X', 392))
        else:
            # 舔右手：右手从自己的基准位置出发，左手留在身侧
            start_x, start_y = rx, ry
            rest_art, rest_x, rest_y = 'left', lx, ly
            lick_x = int(globals().get('LICK_RIGHT_X', 426))
        target_y = int(globals().get('LICK_HAND_Y', 466))
        ease = self._idle_hand_ease(t)
        x = int(start_x + (lick_x - start_x) * ease)
        y = int(start_y + (target_y - start_y) * ease)
        if ease >= 1.0:
            u = self._idle_hand_hold_phase(t)
            cycles = float(globals().get('LICK_CYCLES', 3.0))
            dip = math.sin(u * math.tau * cycles)
            y += int(dip * float(globals().get('LICK_DIP_Y', 20)))
            x -= int(dip * float(globals().get('LICK_DIP_X', 8)))
        max_x = max(0, 1024 - hw)
        return [(rest_art, rest_x, rest_y),
                (getattr(self, '_idle_hand_side', 'left'), max(0, min(max_x, x)), y)]

    def _paste_idle_hands(self, canvas):
        """待机手部动作（招手 / 舔手）的手位。

        与 _render_hand_frame 共用同一份 pastes，保证两条渲染通路一致。
        """
        hand = self.parts.get('hand')
        action = getattr(self, '_idle_hand_action', None)
        if hand is None or action is None:
            return
        if action == 'wave':
            pastes = self._wave_hand_pastes()
        elif action == 'lick':
            pastes = self._lick_hand_pastes()
        else:
            pastes = None
        if not pastes:
            return
        right_hand = hand.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        for art, x, y in pastes:
            img = hand if art == 'left' else right_hand
            canvas.paste(img, (int(x), int(y)), img)

    def _paste_scratch_hands(self, canvas):
        """挠头姿势：一只手抬到头部挠，另一只手放在身侧"""
        hand = self.parts.get('hand')
        pastes = self._scratch_hand_pastes()
        if hand is None or pastes is None:
            return
        right_hand = hand.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        for art, x, y in pastes:
            img = hand if art == 'left' else right_hand
            canvas.paste(img, (int(x), int(y)), img)


    def _cancel_jump(self):
        """取消进行中的跳远动作"""
        self.motion.finish('jump', 'idle')
        self._jump_state = None
        self._forced_expression = None
        self.motion.clear_expression('expression_jump')
        self._jump_hand_mode = ''
        if getattr(self, '_jump_job', None) is not None:
            try:
                self.animations.cancel('jump')
            except Exception:
                pass
            self._jump_job = None


    def _jump_prep_expression(self):
        preset = self._current_expression_preset()
        return {
            'brow': 'brow_1',
            'eye': preset.get('eye', 'eye'),
            'mouth': 'mouth_happy',
        }

    def _play_jump(self):
        """待机跳远：蓄力起跳，最高点后接入甩飞物理下落和滑行。"""
        if self.closing or self.dragging or self.falling:
            return
        if not self.motion.enter('jump'):
            return
        self.motion.cancel_overlays()
        self.motion.set_phase('prep', 'jump')
        if self.walking:
            self._cancel_walk()
            self.walking = False
        self._cancel_reach()
        self._jump_state = 'prep'
        self.pose = 'normal'
        self._forced_expression = self._jump_prep_expression()
        self.motion.set_expression('expression_jump', self._forced_expression)
        # 在缩短后的蓄力区间内随机，蓄得越久，跳得越远
        self._jump_charge_steps = random.randint(
            JUMP_CHARGE_MIN_STEPS, JUMP_CHARGE_MAX_STEPS)
        self._jump_prep_tick(0)


    def _jump_prep_tick(self, step):
        if self.closing or self.dragging:
            return
        if step >= self._jump_charge_steps:
            self._start_jump_air()
            return
        self._forced_expression = self._jump_prep_expression()
        self.motion.set_expression('expression_jump', self._forced_expression)
        self.motion.set_phase('prep', 'jump')
        self._jump_hand_mode = 'swing_up' if step % 2 == 0 else 'swing_down'
        self.pose = 'normal'
        self.update_image()
        self._jump_job = self.animations.schedule('jump', 
            JUMP_PREP_MS, lambda: self._jump_prep_tick(step + 1))


    def _jump_ground_y(self):
        size = int(ICON_SIZE * self.scale)
        feet_h = int(size * CAT_FEET_RATIO)
        return int(self._desktop_bottom() - feet_h)


    def _start_jump_air(self):
        size = int(ICON_SIZE * self.scale)
        self.motion.set_phase('air', 'jump')
        self._jump_state = 'air'
        self._forced_expression = None
        self.motion.clear_expression('expression_jump')
        self._jump_hand_mode = 'forward'
        self.pose = 'drag'
        self._jump_dir = 1 if self.facing_right else -1
        self._jump_start = (self.root.winfo_x(), self.root.winfo_y())
        self._jump_t0 = time.monotonic()
        charge = getattr(self, '_jump_charge_steps', JUMP_CHARGE_MIN_STEPS)
        charge_span = max(1, JUMP_CHARGE_MAX_STEPS - JUMP_CHARGE_MIN_STEPS)
        charge_power = max(
            0.0, min(1.0,
                     (charge - JUMP_CHARGE_MIN_STEPS) / charge_span))
        self._jump_height = int(size * (0.6 + charge_power * 0.6))
        self._jump_dist = int(size * (0.9 + charge_power * 1.6))
        self.update_image()
        self._jump_air_tick()


    def _start_jump_physics(self, t):
        """按当前弧线位置和速度接入共享物理，避免轨迹突变。"""
        frame_ratio = AIRBORNE_FRAME_MS / JUMP_AIR_MS
        vx = self._jump_dir * self._jump_dist * frame_ratio
        vy = -4.0 * self._jump_height * (1.0 - 2.0 * t) * frame_ratio
        return self._start_airborne_motion(vx, vy)


    def _jump_air_tick(self):
        if self._jump_state != 'air':
            return
        t = (time.monotonic() - self._jump_t0) * 1000.0 / JUMP_AIR_MS
        if t >= 0.5:
            if self._start_jump_physics(t):
                return
            self._land_slide()
            return
        size = int(ICON_SIZE * self.scale)
        sx, sy = self._jump_start
        x = int(sx + self._jump_dir * self._jump_dist * t)
        y = int(sy - 4 * self._jump_height * t * (1 - t))
        screen_w = self.root.winfo_screenwidth()
        left_off = int(size * CAT_LEFT_RATIO)
        right_off = int(size * CAT_RIGHT_RATIO)
        if x + left_off <= 0 or x + right_off >= screen_w:  # 猫身碰到边缘
            if self._start_jump_physics(t):
                return
            self._start_wall_slide()
            return
        self.root.geometry(f'{size}x{size}+{x}+{y}')
        self._jump_job = self.animations.schedule('jump', anim_frame_ms(), self._jump_air_tick)


    def _start_wall_slide(self):
        size = int(ICON_SIZE * self.scale)
        self.motion.set_phase('wall', 'jump')
        self._jump_state = 'wall'
        self._jump_hand_mode = 'wall_up'
        self.pose = 'drag'
        screen_w = self.root.winfo_screenwidth()
        left_off = int(size * CAT_LEFT_RATIO)
        right_off = int(size * CAT_RIGHT_RATIO)
        if self._jump_dir < 0:
            x = -left_off          # 猫身左缘贴住屏幕左边缘
        else:
            x = screen_w - right_off  # 猫身右缘贴住屏幕右边缘
        y = self.root.winfo_y()
        self.root.geometry(f'{size}x{size}+{x}+{y}')
        self.update_image()
        self._wall_slide_tick()


    def _wall_slide_tick(self):
        if self._jump_state != 'wall':
            return
        size = int(ICON_SIZE * self.scale)
        x = self.root.winfo_x()
        y = self.root.winfo_y() + JUMP_WALL_SPEED
        ground = self._jump_ground_y()
        if y >= ground:
            self.root.geometry(f'{size}x{size}+{x}+{ground}')
            self._back_hop()
            return
        self.root.geometry(f'{size}x{size}+{x}+{y}')
        self._jump_job = self.animations.schedule('jump', anim_frame_ms(), self._wall_slide_tick)


    def _back_hop(self):
        """滑到地面后先蓄力，再向后小跳离开屏幕边缘"""
        self.motion.set_phase('hop_prep', 'jump')
        self._jump_state = 'hop_prep'
        self._forced_expression = self._jump_prep_expression()
        self.motion.set_expression('expression_jump', self._forced_expression)
        self._back_hop_prep_tick(0)


    def _back_hop_prep_tick(self, step):
        if self._jump_state != 'hop_prep':
            return
        if step >= 3:
            self._do_back_hop()
            return
        self._jump_hand_mode = 'swing_up' if step % 2 == 0 else 'swing_down'
        self.update_image()
        self._jump_job = self.animations.schedule('jump', 
            JUMP_PREP_MS, lambda: self._back_hop_prep_tick(step + 1))


    def _do_back_hop(self):
        size = int(ICON_SIZE * self.scale)
        self.motion.set_phase('hop', 'jump')
        self._jump_state = 'hop'
        self._forced_expression = None
        self._jump_hand_mode = 'forward'
        self._hop_start = (self.root.winfo_x(), self.root.winfo_y())
        self._hop_dir = -self._jump_dir
        self._hop_dist = int(size * 0.6)
        self._hop_height = int(size * 0.35)
        self._hop_t0 = time.monotonic()
        self.update_image()
        self._hop_tick()


    def _hop_tick(self):
        if self._jump_state != 'hop':
            return
        size = int(ICON_SIZE * self.scale)
        t = (time.monotonic() - self._hop_t0) * 1000.0 / 260.0
        if t >= 1.0:
            self._jump_finish()
            return
        sx, sy = self._hop_start
        x = int(sx + self._hop_dir * self._hop_dist * t)
        y = int(sy - 4 * self._hop_height * t * (1 - t))
        left_off = int(size * CAT_LEFT_RATIO)
        right_off = int(size * CAT_RIGHT_RATIO)
        x = max(-left_off, min(x, self.root.winfo_screenwidth() - right_off))
        self.root.geometry(f'{size}x{size}+{x}+{y}')
        self._jump_job = self.animations.schedule('jump', anim_frame_ms(), self._hop_tick)


    def _land_slide(self):
        self.motion.set_phase('slide', 'jump')
        self._jump_state = 'slide'
        self._jump_hand_mode = 'forward'
        self.pose = 'drag'
        size = int(ICON_SIZE * self.scale)
        ground = self._jump_ground_y()
        x = self.root.winfo_x()
        self.root.geometry(f'{size}x{size}+{x}+{ground}')
        self.update_image()
        self._slide_tick(6)


    def _slide_tick(self, step):
        if self._jump_state != 'slide':
            return
        if step <= 0:
            self._jump_finish()
            return
        size = int(ICON_SIZE * self.scale)
        x = self.root.winfo_x() + self._jump_dir * step
        y = self.root.winfo_y()
        self.root.geometry(f'{size}x{size}+{x}+{y}')
        self._jump_job = self.animations.schedule('jump', 
            JUMP_SLIDE_MS // 6, lambda: self._slide_tick(step - 1))


    def _jump_finish(self):
        self.motion.finish('jump', 'idle')
        self._jump_state = None
        self._forced_expression = None
        self.motion.clear_expression('expression_jump')
        self._jump_hand_mode = ''
        self.pose = 'normal'
        self.update_image()
        self._schedule_next()
        self._schedule_walk_attempt()


    def on_drag_start(self, event):
        """开始拖拽：取消随机动作，等真正移动后再切换拖动图"""
        self.motion.enter('drag', force=True)
        self.dragging = True
        self.moved = False
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self._remember_pointer_root(event)
        self._drag_pos_valid = True  # 拖拽期间坐标改由鼠标位置反算
        self._drag_samples = [(time.monotonic(), event.x_root,
                               event.y_root)]
        self._drag_mode = random.choice(DRAG_MODE_IDS)  # 每次抓取随机反抗
        self._cancel_fling()
        self._cancel_climb()
        try:
            self.label.config(cursor='arrow')  # 拖动时用普通鼠标指针
        except Exception:
            pass
        self._cancel_anim()
        self._cancel_walk()
        self._cancel_jump()
        self._cancel_reach()
        self._cancel_fall()
        self._on_taskbar = False


    def on_drag_motion(self, event):
        """拖拽移动：身体以鼠标抓取点为轴轻微左右晃动"""
        if not self.dragging:
            return
        self._record_drag_sample(event)
        self._remember_pointer_root(event)
        delta_x = event.x - self.drag_start_x
        delta_y = event.y - self.drag_start_y
        if not self.moved:
            if delta_x == 0 and delta_y == 0:
                return
            self.moved = True
            self._begin_sway(event)  # 内部会先定位窗口再渲染，避免错位/黑底
        else:
            self._anchor_sway(event)


    def _sound_volume_factor(self):
        """返回 0~1 的整体音效倍率。"""
        try:
            volume = int(getattr(self, 'sound_volume', 100))
        except (TypeError, ValueError):
            volume = 100
        return max(0.0, min(1.0, volume / 100.0))


    def _write_processed_wav(self, source, target, factor, volume=1.0):
        """重采样并调整音量，生成 16 位 PCM WAV。"""
        import array
        import sys
        import wave
        try:
            gain = max(0.0, min(1.0, float(volume)))
            with wave.open(str(source), 'rb') as src:
                channels = src.getnchannels()
                sample_width = src.getsampwidth()
                frame_rate = src.getframerate()
                compression = src.getcomptype()
                frames = src.readframes(src.getnframes())
            if sample_width != 2 or compression != 'NONE' or channels < 1:
                return False
            samples = array.array('h')
            samples.frombytes(frames)
            if sys.byteorder != 'little':
                samples.byteswap()
            source_frames = len(samples) // channels
            if source_frames < 2:
                return False
            output_frames = max(1, int(source_frames / float(factor)))
            output = array.array('h', [0]) * (output_frames * channels)
            for frame_index in range(output_frames):
                position = frame_index * float(factor)
                left_index = min(int(position), source_frames - 1)
                right_index = min(left_index + 1, source_frames - 1)
                fraction = position - int(position)
                for channel in range(channels):
                    left = samples[left_index * channels + channel]
                    right = samples[right_index * channels + channel]
                    value = int(round(
                        (left + (right - left) * fraction) * gain))
                    value = max(-32768, min(32767, value))
                    output[frame_index * channels + channel] = value
            if sys.byteorder != 'little':
                output.byteswap()
            with wave.open(str(target), 'wb') as dst:
                dst.setnchannels(channels)
                dst.setsampwidth(sample_width)
                dst.setframerate(frame_rate)
                dst.writeframes(output.tobytes())
            return True
        except Exception:
            return False


    def _audio_variant_path(self, source, label, factor, volume):
        """返回指定音调和音量对应的 WAV 路径。"""
        import os
        import tempfile
        if not source or not os.path.isfile(source) or volume <= 0:
            return None
        if abs(float(factor) - 1.0) < 0.001 and volume >= 0.999:
            return source
        try:
            output_dir = os.path.join(
                tempfile.gettempdir(), 'cat_pet_audio')
            os.makedirs(output_dir, exist_ok=True)
            stamp = os.stat(source).st_mtime_ns
            stem = os.path.splitext(os.path.basename(source))[0]
            volume_percent = int(round(volume * 100))
            target = os.path.join(
                output_dir,
                f'{stem}_{stamp}_{label}_{factor:.2f}_{volume_percent}.wav')
            if not os.path.isfile(target) or os.path.getsize(target) <= 0:
                self._write_processed_wav(
                    source, target, factor, volume)
            if os.path.isfile(target) and os.path.getsize(target) > 0:
                return target
        except Exception:
            pass
        return None


    def _click_sound_variants(self):
        """返回当前音效的七个随机变调版本路径。"""
        import os
        source = getattr(
            self, '_active_click_sound_path',
            globals().get('CLICK_SOUND_PATH', ''))
        volume = self._sound_volume_factor()
        if (not source or not os.path.isfile(source)
                or volume <= 0):
            self._click_sound_paths = []
            return self._click_sound_paths
        cache_key = (source, os.stat(source).st_mtime_ns, int(round(volume * 100)))
        if (getattr(self, '_click_sound_cache_key', None) == cache_key
                and getattr(self, '_click_sound_paths', None) is not None):
            return self._click_sound_paths
        paths = []
        rates = tuple(globals().get(
            'CLICK_SOUND_PITCH_RATES',
            (0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15)))
        for factor in rates:
            label = f'pitch_{factor:.2f}'
            path = self._audio_variant_path(source, label, factor, volume)
            if path is not None:
                paths.append(path)
        self._click_sound_cache_key = cache_key
        self._click_sound_paths = paths
        return paths


    def _play_wav(self, path):
        """异步播放一个 WAV 文件。"""
        if not path:
            return
        try:
            import winsound
        except Exception:
            return
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC
        flags |= winsound.SND_NODEFAULT
        try:
            winsound.PlaySound(path, flags)
        except Exception:
            pass


    def _play_click_sound(self):
        """单击猫咪时从七个变调版本中随机播放。"""
        import random
        paths = self._click_sound_variants()
        if not paths:
            return
        self._play_wav(random.choice(paths))


    def _audition_click_sound(self, sound_key):
        """试听指定单击音效，随机播放升调或降调版本。"""
        import random
        source = globals().get('CLICK_SOUND_PATHS', {}).get(sound_key)
        if not source:
            return
        volume = self._sound_volume_factor()
        rates = tuple(globals().get(
            'CLICK_SOUND_PITCH_RATES',
            (0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15)))
        factor = random.choice(rates)
        label = f'audition_{factor:.2f}'
        path = self._audio_variant_path(source, label, factor, volume)
        self._play_wav(path)


    def _play_effect_sound(self, source, label='sound'):
        """按整体音效设置播放非变调音效。"""
        volume = self._sound_volume_factor()
        path = self._audio_variant_path(source, label, 1.0, volume)
        self._play_wav(path)


    def _play_meow_sound(self):
        """待机时偶尔喵一声。

        用当前选中的单击猫咪音效（_active_click_sound_path），并从七个
        变调版本里随机挑一个 —— 和单击时听到的是同一套音源，保持一致。
        音量仍然跟随设置面板里的整体音效音量，音量拉到 0 就不响。
        """
        import random
        paths = self._click_sound_variants()
        if not paths:
            return
        self._play_wav(random.choice(paths))

    def _allow_click_reaction(self):
        """限制单击猫咪的反应频率，避免快速连点反复触发。"""
        now = time.monotonic()
        last = getattr(self, '_last_click_reaction', 0.0)
        if (now - last) * 1000.0 < CLICK_REACTION_COOLDOWN_MS:
            return False
        self._last_click_reaction = now
        return True

    def on_drag_stop(self, event):
        """停止拖拽：单击触发对话框；快速松开则把猫咪甩飞。"""
        was_click = not self.moved
        self._record_drag_sample(event)
        self._remember_pointer_root(event)  # 松手点即窗口最终位置
        velocity = self._drag_release_velocity()
        self.dragging = False
        flung = False
        climbed = False
        try:
            if self.moved:
                self._end_sway()
                if self._should_climb_taskbar():
                    climbed = self._start_taskbar_climb()
                else:
                    flung = self._start_fling(*velocity)
            else:
                self.motion.finish('drag', 'idle')
            try:
                self.label.config(cursor='arrow')
            except Exception:
                pass
            if not flung and not climbed:
                self.motion.finish('drag', 'idle')
                self.show_pose('normal')
                self._schedule_next()
                self._schedule_walk_attempt()
                self._start_fall_check()
        finally:
            # 反算坐标只对本次松手有效，异常时也必须复位，
            # 否则后续重力判定会一直用残留的旧位置
            self._drag_pos_valid = False
        self._drag_samples = []
        if (was_click and not self.closing
                and self._allow_click_reaction()):
            self._play_click_sound()
            self.show_emotion_face()


    # 松手速度的采样参数：算速度时最多回看这么久，并保证至少留这么多条样本
    DRAG_SAMPLE_SPAN_S = 0.20
    DRAG_SAMPLE_KEEP = 6

    def _record_drag_sample(self, event):
        now = time.monotonic()
        self._drag_samples.append((now, event.x_root, event.y_root))
        cutoff = now - 0.30
        samples = [s for s in self._drag_samples if s[0] >= cutoff]
        # 关键：快甩时 Tk 会合并 <Motion> 事件，主线程又可能正被一次姿势合成
        # 卡住上百毫秒，时间窗口里可能只剩一两条样本 —— 速度就成了 0，
        # 甩飞直接不触发（实测快速甩动经常完全没反应）。这里兜底保留条数。
        if len(samples) < self.DRAG_SAMPLE_KEEP:
            samples = self._drag_samples[-self.DRAG_SAMPLE_KEEP:]
        self._drag_samples = samples

    def _drag_release_velocity(self):
        """返回鼠标松手前最近一段轨迹的速度（像素/秒）。

        参照点取「距松手不超过 DRAG_SAMPLE_SPAN_S 的最早一条」，跨度最大也最稳；
        样本本身就是鼠标的真实屏幕位置，所以即使 Tk 合并了事件、样本稀疏，
        算出来的方向仍是手势的方向。
        """
        samples = self._drag_samples
        if len(samples) < 2:
            return 0.0, 0.0
        t1, x1, y1 = samples[-1]
        t0, x0, y0 = samples[0]
        for sample in samples[:-1]:
            if t1 - sample[0] <= self.DRAG_SAMPLE_SPAN_S:
                t0, x0, y0 = sample
                break
        dt = max(0.016, t1 - t0)
        return (x1 - x0) / dt, (y1 - y0) / dt


    def _begin_sway(self, event):
        """开始晃动：窗口尺寸保持不变（避免黑底/跳位），
        旋转时按需轻微缩小画面使其不超出窗口边界。"""
        size = int(ICON_SIZE * self.scale)
        # 这里只改姿势状态，不走 show_pose() 的整幅重渲染：那一帧马上会被下面的
        # _render_sway() 覆盖，白等一次姿势合成（实测 100~130ms），
        # 表现为「拖拽一上手就卡一下」。
        self.pose = 'drag'
        self._drag_base = self._get_display_image(
            'drag', (size, size), with_hands=False)

        self.motion.set_phase('sway', 'drag')
        self.swaying = True
        self._sway_t0 = time.monotonic()
        self._sway_angle = 0.0
        # 窗口仍是原尺寸，只是按抓取点对准鼠标移动，不会闪黑边
        self._anchor_sway(event)
        self._render_sway()   # 立刻出第一帧（角度 0），顶替上面省掉的那次渲染
        self._sway_job = self.animations.schedule('sway', anim_frame_ms(), self._sway_tick)


    def _render_sway(self):
        """按当前角度，以抓取点为轴渲染一帧晃动画面（不改变窗口大小）"""
        if self._drag_base is None:
            return
        size = self._drag_base.width
        px, py = self.drag_start_x, self.drag_start_y
        rad = math.radians(self._sway_angle)
        c, s = math.cos(rad), math.sin(rad)

        # 旋转后四个角相对抓取点的范围
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        for sx, sy in ((0, 0), (size, 0), (0, size), (size, size)):
            rx = c * (sx - px) - s * (sy - py)
            ry = s * (sx - px) + c * (sy - py)
            min_x = min(min_x, rx)
            max_x = max(max_x, rx)
            min_y = min(min_y, ry)
            max_y = max(max_y, ry)

        # 计算缩放系数 k，让旋转后的内容仍落在窗口内（避免裁边/黑边）
        k = 1.0
        if min_x < 0:
            k = min(k, px / -min_x)
        if max_x > 0:
            k = min(k, (size - px) / max_x)
        if min_y < 0:
            k = min(k, py / -min_y)
        if max_y > 0:
            k = min(k, (size - py) / max_y)
        k = max(0.05, min(1.0, k))

        # AFFINE 数据把“输出像素”映射回“原图像素”
        ck, sk = c / k, s / k
        data = (ck, sk, px - (ck * px + sk * py),
                -sk, ck, py - (-sk * px + ck * py))
        frame = self._drag_base.transform(
            (size, size), PIL.Image.AFFINE, data,
            resample=PIL.Image.Resampling.BICUBIC,
            fillcolor=(0, 0, 0, 0))
        frame = self._clean_rgba_edges(frame)
        elapsed = (time.monotonic() - self._sway_t0) * 1000.0
        phase = (2.0 * math.pi * elapsed
                 / (SWAY_PERIOD_MS * 1.2))
        frame = self._paste_drag_hands(frame, size, phase)
        key = ('sway-frame', size, round(self._sway_angle, 2),
               round(phase, 3), self._render_state_key('drag', True))
        self.photo = self.render_cache.get_or_create(
            'photo', key, lambda: PIL.ImageTk.PhotoImage(frame))
        self.label.config(image=self.photo)


    def _paste_drag_hands(self, frame, size, phase):
        """拖动反抗：按本次随机模式绘制两只手"""
        hand = self.parts.get('hand')
        if hand is None:
            return frame
        hw = max(1, int(hand.width * size / 1024))
        hh = max(1, int(hand.height * size / 1024))
        small, mirror = self._scaled_hand_pair(hw, hh)
        mode = getattr(self, '_drag_mode', 1)
        px, py = self.drag_start_x, self.drag_start_y
        if mode == 1:
            # 模式1：扇形摆动（像小鸟扇翅膀）
            amp = size * 0.16
            out = size * 0.06
            s = math.sin(phase)
            lx = size * 0.28 - out * abs(s) - hw / 2
            ly = size * 0.52 - amp * s - hh / 2
            rx = size * 0.72 + out * abs(s) - hw / 2
            ry = size * 0.52 + amp * s - hh / 2
        elif mode == 2:
            # 模式2：两只手贴住鼠标，死不松手
            lx = px - hw * 0.95
            ly = py - hh * 0.2
            rx = px - hw * 0.05
            ry = py - hh * 0.2
        else:
            # 模式3：一拳一拳交替打出去（左一拳、右一拳）
            punch = math.sin(phase * 0.6)
            # 出拳时快速打到鼠标（指数<1 让伸展更快），收回稍慢
            left_raw = max(0.0, punch)
            right_raw = max(0.0, -punch)
            left_punch = min(1.0, left_raw * 1.5) ** 0.35
            right_punch = min(1.0, right_raw * 1.5) ** 0.35
            reach = size * 0.30
            lx = size * 0.26 + (px - size * 0.26) * left_punch * 0.75 - hw / 2
            ly = (size * 0.52 + (py - size * 0.52) * left_punch * 0.35
                  - hh / 2)
            rx = size * 0.74 + (px - size * 0.74) * right_punch * 0.75 - hw / 2
            ry = (size * 0.52 + (py - size * 0.52) * right_punch * 0.35
                  - hh / 2)
        frame.paste(small, (int(lx), int(ly)), small)
        frame.paste(mirror, (int(rx), int(ry)), mirror)
        return frame


    def _sway_tick(self):
        """晃动动画的每一帧"""
        self._sway_job = None
        if not (self.swaying and self.dragging and not self.closing):
            return
        elapsed_ms = (time.monotonic() - self._sway_t0) * 1000.0
        self._sway_angle = SWAY_AMPLITUDE * math.sin(
            2.0 * math.pi * elapsed_ms / SWAY_PERIOD_MS)
        self._render_sway()
        self._sway_job = self.animations.schedule('sway', anim_frame_ms(), self._sway_tick)


    def _anchor_sway(self, event):
        """移动窗口（尺寸不变），让抓取点始终对准鼠标。

        走 Win32 SetWindowPos 而不是 root.geometry()：geometry() 只是把移动请求
        排进 Tk 队列，要等空闲周期才真正生效。快速拖动时事件队列一直不空，窗口
        就会落后于鼠标（极端情况下整段拖拽窗口都不动、松手才瞬移过去），
        手感就是「卡」和「跳」。SetWindowPos 立即生效。
        尺寸不变，两种写法视觉一致。
        """
        if not self.swaying:
            return
        x = int(event.x_root) - int(self.drag_start_x)
        y = int(event.y_root) - int(self.drag_start_y)
        self._move_window_position(x, y)


    def _end_sway(self):
        """结束晃动：取消动画即可（窗口一直保持原尺寸）"""
        self.swaying = False
        if self._sway_job is not None:
            try:
                self.animations.cancel('sway')
            except Exception:
                pass
            self._sway_job = None
        self._drag_base = None


    def _start_fling(self, vx, vy):
        """根据松手速度开始甩飞；返回是否成功触发。"""
        speed = math.hypot(vx, vy)
        if speed < FLING_MIN_SPEED:
            return False
        frame_scale = FLING_FRAME_MS / 1000.0 * FLING_SPEED_SCALE
        return self._start_airborne_motion(
            vx * frame_scale, vy * frame_scale)


    def _airborne_limits(self, size):
        """甩飞/下落时窗口左上角允许的横向范围（与 _fling_tick 共用同一套公式）。"""
        screen_w = self._screen_width()
        overshoot = int(size * FLING_EDGE_OVERSHOOT_RATIO)
        left_limit = -int(size * CAT_LEFT_RATIO) - overshoot
        right_limit = screen_w - int(size * CAT_RIGHT_RATIO) + overshoot
        return left_limit, right_limit

    def _start_airborne_motion(self, vx, vy):
        """以每帧速度启动甩飞物理，供甩飞和跳远下落共用。"""
        if self.closing or self.hospitalized:
            return False
        if not self.motion.enter('fling', force=True):
            return False
        size = int(ICON_SIZE * self.scale)
        # 拖拽能到的地方比甩飞边界更靠外（抓取点偏移 + 鼠标能顶到屏幕边），
        # 所以起点可能已经越界。必须在这里就夹回来：否则首帧 _fling_tick 会把
        # 它夹回边界并按“撞墙”把速度反向，表现为「一松手就像撞到东西、
        # 猛地朝反方向飞」。只夹位置，不动速度方向。
        x, y = self._window_pos()
        left_limit, right_limit = self._airborne_limits(size)
        if x < left_limit:
            x = left_limit
        elif x > right_limit:
            x = right_limit
        if y < 0:
            y = 0
        self._airborne_x, self._airborne_y = x, y
        raw_vx = max(-AIRBORNE_MAX_SPEED, min(AIRBORNE_MAX_SPEED, vx))
        self._fling_vx = raw_vx
        self._fling_vy = max(-AIRBORNE_MAX_SPEED,
                             min(AIRBORNE_MAX_SPEED, vy))
        # 松手时若猫已经被压在屏幕边上、而横向速度仍指向墙外，说明这是「往墙里甩」，
        # 横向已经没有可移动空间。此时直接把横向速度吸收掉，让猫贴边下落；
        # 否则紧接着的 _fling_tick 会把它当撞墙反向（×0.28），
        # 表现为「一松手就像撞到什么东西、猛地朝反方向弹开」。上下边界同理。
        if x <= left_limit and self._fling_vx < 0:
            self._fling_vx = 0.0
        elif x >= right_limit and self._fling_vx > 0:
            self._fling_vx = 0.0
        if y <= 0 and self._fling_vy < 0:
            self._fling_vy = 0.0
        self._cancel_climb()
        self.motion.set_phase('air', 'fling')
        self.flinging = True
        self.falling = False
        self._fling_anim_counter = 0
        self._fling_landing_y = None
        self._fling_fixed_landing = False
        self._airborne_last_visual_key = None
        self._fling_bounces = 0
        self._allow_extra_bounces = False
        self._falling_hands = False
        self._hand_lift = 0.0
        self._cancel_walk()
        self._cancel_jump()
        self._cancel_reach()
        self._cancel_fall()
        self._cancel_anim()
        self._on_taskbar = False
        # 朝向按松手瞬间的原始横向速度判断，而不是吸收之后的值，
        # 否则「贴着左墙往左甩」会被吸收成 0 → 误判为朝右。
        self.facing_right = raw_vx >= 0
        self.pose = 'drag'
        initial_key = self._airborne_visual_key()
        self._airborne_last_visual_key = initial_key
        self._airborne_next_render_at = time.monotonic() + anim_frame_ms() / 1000.0
        self._render_airborne_frame(size, initial_key)
        self._fling_tick()
        return True


    def _airborne_visual_key(self):
        """把连续速度量化成少量视觉状态，保持顺滑同时减少重绘。"""
        speed = math.hypot(self._fling_vx, self._fling_vy)
        if speed <= 0.01:
            direction = (0, 0)
        else:
            inv_speed = 1.0 / speed
            direction = (round(self._fling_vx * inv_speed * 4.0),
                         round(self._fling_vy * inv_speed * 4.0))
        power = int(round(min(1.0, speed / AIRBORNE_MAX_SPEED)
                          * AIRBORNE_VISUAL_POWER_STEPS))
        return (
            self.motion.current,
            self.motion.phase,
            self.pose,
            bool(self.facing_right),
            bool(getattr(self, '_falling_hands', False)),
            round(float(getattr(self, '_hand_lift', 0.0)), 2),
            power,
            direction,
        )


    def _fling_tick(self):
        """甩飞动画：惯性、重力、屏幕边缘和地面反弹。"""
        if not self.flinging or self.closing:
            return
        frame_started = time.monotonic()
        size = int(ICON_SIZE * self.scale)
        screen_w = self._screen_width()
        feet_h = int(size * CAT_FEET_RATIO)
        self._fling_anim_counter += 1
        fixed_landing = getattr(self, '_fling_fixed_landing', False)
        refresh_landing = (
            self._fling_landing_y is None
            or (not fixed_landing
                and self._fling_anim_counter
                % AIRBORNE_LANDING_REFRESH_FRAMES == 0))
        if refresh_landing:
            landing = self._compute_landing_y(
                x=self._airborne_x, y=self._airborne_y)
            self._fling_landing_y = (
                int(landing) if landing is not None
                else self._desktop_bottom() - feet_h)
        ground_y = int(self._fling_landing_y)
        x = self._airborne_x + self._fling_vx
        y = self._airborne_y + self._fling_vy
        left_limit, right_limit = self._airborne_limits(size)
        if x <= left_limit:
            x = left_limit
            # 只在真的朝墙飞时才反向；否则会被反复按 0.28 衰减
            if self._fling_vx < 0:
                self._fling_vx = -self._fling_vx * FLING_BOUNCE
        elif x >= right_limit:
            x = right_limit
            if self._fling_vx > 0:
                self._fling_vx = -self._fling_vx * FLING_BOUNCE
        if y <= 0:
            y = 0
            if self._fling_vy < 0:
                self._fling_vy = -self._fling_vy * FLING_BOUNCE
        grounded = y >= ground_y
        if grounded:
            y = ground_y
            impact_speed = self._fling_vy
            if self._fling_bounces == 0 and impact_speed > 0.8:
                self._fling_bounces = 1
                self._allow_extra_bounces = (
                    impact_speed >= FLING_SECOND_BOUNCE_MIN_IMPACT_SPEED)
                self._fling_vy = -abs(impact_speed) * FLING_BOUNCE
            elif (self._fling_bounces == 1
                  and getattr(self, '_allow_extra_bounces', False)
                  and impact_speed > FLING_SECOND_BOUNCE_MIN_SPEED):
                self._fling_bounces = 2
                self._fling_vy = -abs(impact_speed) * FLING_SECOND_BOUNCE
            elif (self._fling_bounces == 2
                  and getattr(self, '_allow_extra_bounces', False)
                  and impact_speed > FLING_SECOND_BOUNCE_MIN_SPEED):
                self._fling_bounces = 3
                self._fling_vy = -abs(impact_speed) * FLING_THIRD_BOUNCE
            else:
                self._fling_bounces = max(1, self._fling_bounces)
                self._fling_vy = 0.0
            if self.pose != 'normal':
                self.pose = 'normal'
        if grounded:
            self._fling_vx *= AIRBORNE_GROUND_FRICTION_STEP
        else:
            self._fling_vx *= AIRBORNE_FRICTION_STEP
        settled = (grounded and self._fling_bounces >= 1
                   and self._fling_vy == 0.0)
        if not settled:
            self._fling_vy += AIRBORNE_GRAVITY_STEP
        self._airborne_x = x
        self._airborne_y = y
        self._move_window_position(x, y)
        visual_key = self._airborne_visual_key()
        now = time.monotonic()
        if (visual_key != getattr(self, '_airborne_last_visual_key', None)
                and now >= getattr(self, '_airborne_next_render_at', 0.0)):
            self._airborne_last_visual_key = visual_key
            self._airborne_next_render_at = now + anim_frame_ms() / 1000.0
            self._render_airborne_frame(size, visual_key)
        if settled and abs(self._fling_vx) < FLING_GROUND_STOP_SPEED:
            self._finish_fling()
            return
        elapsed_ms = (time.monotonic() - frame_started) * 1000.0
        delay_ms = max(1, AIRBORNE_FRAME_MS - int(elapsed_ms))
        self._fling_job = self.animations.schedule(
            'fling', delay_ms, self._fling_tick)


    def _finish_fling(self):
        self._sync_airborne_window_position()
        self.motion.finish('fling', 'idle')
        self.motion.finish('fall', 'idle')
        self._airborne_last_visual_key = None
        self._fling_job = None
        self.flinging = False
        self.falling = False
        self._fling_vx = 0.0
        self._fling_vy = 0.0
        self._falling_hands = False
        self._hand_lift = 0.0
        self.show_pose('normal')
        self._schedule_next()
        self._schedule_walk_attempt()
        if self._fall_job is None:
            self._start_fall_check()


    def _cancel_fling(self):
        self._sync_airborne_window_position()
        self.motion.finish('fling', 'idle')
        self.motion.finish('fall', 'idle')
        self._airborne_last_visual_key = None
        self.flinging = False
        self.falling = False
        self._fling_vx = 0.0
        self._fling_vy = 0.0
        if self._fling_job is not None:
            try:
                self.animations.cancel('fling')
            except Exception:
                pass
            self._fling_job = None


    def _should_climb_taskbar(self):
        """判断猫咪下半身是否已经低于任务栏上沿。"""
        size = int(ICON_SIZE * self.scale)
        feet_h = int(size * CAT_FEET_RATIO)
        top = self._window_pos()[1]
        feet = top + feet_h
        desktop = self._desktop_bottom()
        return feet > desktop + 2 and top > desktop - feet_h + 2


    def _start_taskbar_climb(self):
        """在任务栏下方松手时，从当前位置向上爬回任务栏上沿。"""
        if self.closing or self.hospitalized:
            return False
        size = int(ICON_SIZE * self.scale)
        feet_h = int(size * CAT_FEET_RATIO)
        start_y = self._window_pos()[1]
        target_y = self._desktop_bottom() - feet_h
        if start_y <= target_y + 2:
            return False
        if not self.motion.enter('climb', force=True):
            return False
        self.motion.set_phase('pause', 'climb')
        self.climbing = True
        self.flinging = False
        self.falling = False
        self._climb_t0 = time.monotonic()
        self._climb_start_y = start_y
        self._climb_target_y = target_y
        self._climb_hand_progress = 0.0
        self._climb_hand_mode = 'normal'
        edge_window = max(0, min(size, self._desktop_bottom() - start_y))
        self._climb_edge_y = edge_window * 1024.0 / max(1, size)
        self._cancel_walk()
        self._cancel_jump()
        self._cancel_reach()
        self._cancel_fall()
        self._cancel_anim()
        self._on_taskbar = False
        # 不再走 show_pose('drag') + update_image()：那是两次「整图重合成」
        # （各约 95ms），爬升一开始就要卡两下。姿势先置好，
        # 第一帧由紧随其后的 _climb_tick() 用「缓存底图 + 贴手」画出来。
        self.pose = 'drag'
        self._climb_tick()
        return True


    def _climb_tick(self):
        """攀爬动画：停顿、伸手、上拉、双手收回。"""
        if not self.climbing or self.closing:
            return
        size = int(ICON_SIZE * self.scale)
        elapsed = (time.monotonic() - self._climb_t0) * 1000.0
        p1 = CLIMB_PAUSE_MS
        p2 = p1 + CLIMB_REACH_MS
        p3 = p2 + CLIMB_RISE_MS
        p4 = p3 + CLIMB_RELEASE_MS

        def smooth(t):
            t = max(0.0, min(1.0, t))
            return t * t * (3.0 - 2.0 * t)

        if elapsed < p1:
            y = self._climb_start_y
            self._climb_hand_mode = 'normal'
            self._climb_hand_progress = 0.0
        elif elapsed < p2:
            y = self._climb_start_y
            self._climb_hand_mode = 'reach'
            self._climb_hand_progress = smooth((elapsed - p1) / CLIMB_REACH_MS)
        elif elapsed < p3:
            u = smooth((elapsed - p2) / CLIMB_RISE_MS)
            y = int(self._climb_start_y
                    + (self._climb_target_y - self._climb_start_y) * u)
            self._climb_hand_mode = 'hold'
            self._climb_hand_progress = 1.0
        elif elapsed < p4:
            y = self._climb_target_y
            self._climb_hand_mode = 'release'
            self._climb_hand_progress = 1.0 - smooth(
                (elapsed - p3) / CLIMB_RELEASE_MS)
        else:
            self._finish_climb()
            return

        edge_window = max(0, min(size, self._desktop_bottom() - y))
        self._climb_edge_y = edge_window * 1024.0 / max(1, size)
        x = self.root.winfo_x()
        # 用 SetWindowPos 立即移动：走 Tk geometry 要等空闲周期才生效，
        # 30/60 帧下窗口会落后于手的位置，看起来就是「手在动、身子没跟上」
        self._move_window_position(int(x), int(y))
        # 只贴手，不重合成整图（重合成一次约 95ms，会把 60 帧拖成 10 帧）
        self._render_hand_frame('drag', size, self._climb_hand_pastes())
        self._climb_job = self.animations.schedule('climb',
                                                   self._hand_frame_ms(),
                                                   self._climb_tick)


    def _finish_climb(self):
        self.motion.finish('climb', 'idle')
        self._climb_job = None
        self.climbing = False
        self._climb_hand_mode = 'normal'
        self._climb_hand_progress = 0.0
        size = int(ICON_SIZE * self.scale)
        x = self.root.winfo_x()
        self.root.geometry(f'{size}x{size}+{int(x)}+{int(self._climb_target_y)}')
        self.show_pose('normal')
        self.update_image()
        self._schedule_next()
        self._schedule_walk_attempt()
        if self._fall_job is None:
            self._start_fall_check()


    def _cancel_climb(self):
        self.motion.finish('climb', 'idle')
        self.climbing = False
        self._climb_hand_mode = 'normal'
        self._climb_hand_progress = 0.0
        if self._climb_job is not None:
            try:
                self.animations.cancel('climb')
            except Exception:
                pass
            self._climb_job = None


    def _schedule_walk_attempt(self):
        """隔一段时间随机决定是否开始走动（带自愈，避免卡死）"""
        if self.closing:
            return
        # 自愈：掉落标志卡住但已没有掉落任务在跑时复位
        if self.falling and self._fall_job is None:
            self.falling = False
        if (self.hospitalized or self.walking
                or self.motion.current not in ('idle', 'walk')):
            # 暂时忙（拖动/甩飞/走动/掉落），稍后再试
            self._walk_job = self.animations.schedule('walk', 1500, self._try_walk)
            return
        delay = random.randint(WALK_IDLE_MIN_MS, WALK_IDLE_MAX_MS)
        self._walk_job = self.animations.schedule('walk', delay, self._try_walk)


    def _try_walk(self):
        self._walk_job = None
        if (self.closing or self.walking or self.hospitalized
                or self.motion.current not in ('idle', 'walk')):
            return
        if random.random() >= WALK_CHANCE:
            self._schedule_walk_attempt()
            return
        self.start_walk(random.choice((-1, 1)))


    def start_walk(self, direction):
        """猫开始水平走动，走动时身体轻微摇晃，眨眼/抖耳朵照旧"""
        if (self.closing or self.hospitalized or self.dragging
                or self.falling or self.flinging or self.climbing):
            return
        if not self.motion.enter('walk'):
            return
        # 不强制要求“必须站在支撑上”才能走：只要没在掉落就允许走动，
        # 避免支撑判断出错时猫一直不走路
        self.walking = True
        self.walk_dir = 1 if direction > 0 else -1
        # 向右走时把猫水平翻转（气泡不翻转，仍在猫的左边）
        self.facing_right = (self.walk_dir > 0)
        self._walk_t0 = time.monotonic()
        self._walk_end = (self._walk_t0
                          + random.randint(WALK_MIN_MS, WALK_MAX_MS) / 1000.0)
        self.show_pose('normal')
        self._walk_tick()


    def _walk_tick(self):
        """走动每一帧：移动 + 撞墙掉头 + 轻微摇晃"""
        if not self.walking:
            return
        now = time.monotonic()
        if now >= self._walk_end:
            self.walking = False
            self._cancel_walk_job()
            self.update_image()
            self._schedule_walk_attempt()
            return
        size = int(ICON_SIZE * self.scale)
        x = self.root.winfo_x() + self.walk_dir * WALK_SPEED
        # 在可见内容边界外再放宽一部分，让猫身可以少量伸出屏幕。
        edge_overshoot = int(size * WALK_EDGE_OVERSHOOT_RATIO)
        left_limit = -int(size * CAT_LEFT_RATIO) - edge_overshoot
        right_limit = (self.root.winfo_screenwidth()
                       - int(size * CAT_RIGHT_RATIO)
                       + edge_overshoot)
        if x <= left_limit:
            x = left_limit
            self.walk_dir = 1
            self.facing_right = False
            self.update_image()
        elif x >= right_limit:
            x = right_limit
            self.walk_dir = -1
            self.facing_right = True
            self.update_image()
        y = self.root.winfo_y()
        self.root.geometry(f'{size}x{size}+{int(x)}+{int(y)}')
        # 走动时的轻微摇晃（不影响正在进行的眨眼/抖耳朵）
        self._render_rock(WALK_ROCK_AMPLITUDE, WALK_ROCK_PERIOD_MS, now)
        self._walk_job = self.animations.schedule('walk', anim_frame_ms(), self._walk_tick)


    def _cancel_walk(self):
        """立即停止走动（不重新安排）"""
        self.motion.finish('walk', 'idle')
        self.walking = False
        self._cancel_walk_job()


    def _cancel_walk_job(self):
        if self._walk_job is not None:
            try:
                self.animations.cancel('walk')
            except Exception:
                pass
            self._walk_job = None


    def _render_rock(self, amplitude, period_ms, now):
        """用当前姿势的图做轻微左右摇晃（窗口尺寸不变）"""
        if self.closing:
            return
        size = int(ICON_SIZE * self.scale)
        base = self._get_display_image(
            self.pose, (size, size), with_hands=False)
        angle = amplitude * math.sin(
            2.0 * math.pi * ((now - self._walk_t0) * 1000.0) / period_ms)
        frame = self._rotate_fit(base, (size / 2.0, size / 2.0), angle)
        # 小手不跟随身体旋转，但按周期一上一下交替摆动
        phase = (2.0 * math.pi
                 * (now - self._walk_t0) * 1000.0 / HAND_WALK_PERIOD_MS)
        frame = self._paste_hands(frame, size, phase)
        key = ('walk-frame', self._display_cache_key(self.pose, (size, size)),
               round(angle, 2), round(phase, 3))
        self.photo = self.render_cache.get_or_create(
            'photo', key, lambda: PIL.ImageTk.PhotoImage(frame))
        self.label.config(image=self.photo)


    def _breath_hand_pastes(self):
        """呼吸帧要贴的手位：静止垂手（1024 画布坐标）。

        呼吸循环只在「真正静止」时跑（_breath_tick 里 busy 会排除招手/舔手），
        所以这里贴的永远是自然垂在身侧的两只手 —— 这是之前「站立/单击呼吸
        时手消失」的直接原因，贴回来即可。招手/舔手时的身体呼吸由
        _render_hand_frame 自己叠加，不走这个循环。
        """
        (lx, ly), (rx, ry) = self._hand_base_positions()
        return [('left', lx, ly), ('right', rx, ry)]

    def _resize_breath_rgba(self, image, new_size):
        """纵向缩放一张 RGBA 图，用预乘 alpha 方式避免透明黑边渗入边缘。

        呼吸幅度只有 ±1%，但 BICUBIC 重采样会在剪影边缘造出一圈半透明
        过渡像素（alpha 介于 0~255），这些像素带着底图透明区的黑色。
        这里走和 _resize_rgba 一样的预乘流程：颜色乘 alpha 再缩放、
        除以新 alpha，最后把半透明裁成实心（>=0.5）或全透明。
        """
        try:
            import numpy as np
        except Exception:
            return image.resize(new_size, PIL.Image.Resampling.LANCZOS)
        try:
            source = image if image.mode == 'RGBA' else image.convert('RGBA')
            arr = np.asarray(source, dtype=np.uint16)
            rgb = arr[..., :3]
            a = arr[..., 3:4]
            prem_img = PIL.Image.fromarray(
                ((rgb * a + 127) // 255).astype(np.uint8), 'RGB')
            a_img = PIL.Image.fromarray(a[..., 0].astype(np.uint8), 'L')
            prem_img = prem_img.resize(new_size,
                                       PIL.Image.Resampling.LANCZOS)
            a_img = a_img.resize(new_size, PIL.Image.Resampling.LANCZOS)
            prem2 = np.asarray(prem_img, dtype=np.float32) / 255.0
            a2 = np.asarray(a_img, dtype=np.float32) / 255.0
            out_rgb = prem2 / np.maximum(a2[..., None], 1e-4)
            out = np.concatenate([out_rgb, a2[..., None]], axis=-1)
            out = np.clip(out, 0.0, 1.0)
            solid = out[..., 3] >= 0.5
            out[..., 3] = np.where(solid, 1.0, 0.0)
            return PIL.Image.fromarray(
                (out * 255.0).round().astype(np.uint8), 'RGBA')
        except Exception:
            return image.resize(new_size, PIL.Image.Resampling.LANCZOS)

    def _breath_scale_y(self, now):
        """根据当前时间算呼吸的纵向缩放系数（离散到档，供缓存命中）。

        供 _render_breath（静止呼吸循环）和 _render_hand_frame（招手/舔手
        叠加呼吸）共用同一套周期/幅度/离散逻辑，保证两处呼吸节奏一致。
        """
        levels = max(3, int(globals().get('BREATH_LEVELS', 7)))
        period = max(1, float(globals().get('BREATH_PERIOD_MS', 3200)))
        amplitude = float(globals().get('BREATH_AMPLITUDE', 0.010))
        t0 = getattr(self, '_breath_t0', None)
        if t0 is None:
            t0 = time.monotonic()
            self._breath_t0 = t0
        t = ((now - t0) * 1000.0) % period
        phase = math.sin(2.0 * math.pi * t / period)
        level = round(phase * (levels - 1) / 2.0)
        scale_y = 1.0 + amplitude * (level / float(levels - 1) * 2.0)
        return round(scale_y, 4)

    def _apply_breath_scale(self, base, size, now):
        """把一张显示尺寸的身体底图做「脚底对齐」的纵向呼吸缩放。

        返回新的 size×size RGBA 图（预乘 alpha 缩放，无黑边）。
        手不在这里贴，由调用方决定贴什么手。
        """
        scale_y = self._breath_scale_y(now)
        new_h = max(1, int(size * scale_y))
        frame = self._resize_breath_rgba(base, (size, new_h))
        canvas = PIL.Image.new('RGBA', (size, size), (0, 0, 0, 0))
        canvas.paste(frame, (0, size - new_h), frame)
        return canvas

    def _render_breath(self, now):
        """渲染一帧「呼吸」：身体纵向极小幅缩放，模拟胸腔起伏，手照常贴回。

        与走路晃动不同：呼吸只做纵向缩放（脚底对齐，身体向上起伏），
        幅度只有 ±1% 左右，慢周期，所以看起来是「活着」而不是「在晃」。
        缩放级别离散成 BREATH_LEVELS 档，每档缓存一张图，循环只是切换
        缓存图（约 0.02ms），不会像旋转那样每帧重采样。
        """
        size = int(ICON_SIZE * self.scale)
        base = self._get_display_image(
            self.pose, (size, size), with_hands=False)
        canvas = self._apply_breath_scale(base, size, now)
        # 手不参与纵向缩放（呼吸主要动身体），但必须贴回，否则站立/单击
        # 呼吸时手会「消失」。呼吸循环只在静止时跑，贴的是垂手。
        self._apply_hand_layer_scaled(
            canvas, size, self._breath_hand_pastes())
        key = ('breath-frame',
               self._display_cache_key(self.pose, (size, size)),
               round(self._breath_scale_y(now), 4))
        self.photo = self.render_cache.get_or_create(
            'photo', key, lambda: PIL.ImageTk.PhotoImage(canvas))
        self.label.config(image=self.photo)


    def _breath_tick(self):
        """呼吸循环：只在「真正静止站立」时渲染呼吸帧，其它时刻跳过并自愈。

        静止的定义：motion 在 idle、没有任何 overlay 动作（眨眼/动耳/摇尾巴/
        喵叫）、没有走路/拖拽/甩飞/下落/攀爬、没有待机手部动作（招手/舔手）、
        也没有单击表情在显示。不满足就停一帧再查，呼吸状态不残留到下一次动作里。

        单击/下落期间明确不插呼吸：单击是叠加在静止身上的表情反应，
        下落是空中状态，呼吸在这两种情境下都多余且会覆盖它们各自的帧。

        overlay 动作（眨眼/动耳/摇尾巴/喵叫）也让路：它们都是 <1s 的局部
        动作，期间呼吸的 ±1% 起伏根本看不出来，让呼吸继续跑反而会用整图
        缩放帧去覆盖它们的 pose 帧（摇尾巴是 normal↔tail 切换、眨眼是
        blink 帧），造成闪回。等它们结束呼吸自然续上。
        """
        self._breath_job = None
        if self.closing:
            self._breathing = False
            return
        busy = (self.walking or self.dragging
                or getattr(self, 'flinging', False)
                or getattr(self, 'falling', False)
                or getattr(self, 'climbing', False)
                or getattr(self, '_idle_hand_action', None)
                or getattr(self, '_idle_head_sway', 0.0) != 0.0
                or getattr(self, '_click_expression', None) is not None
                or getattr(self, '_click_expression_job', None) is not None
                or self.motion.overlays
                or self.motion.current not in ('idle',))
        if busy:
            # 忙的时候不画呼吸帧，并把 _breathing 复位：等闲下来重新进入
            # 呼吸时会重置 _breath_t0，从「吸气」重新起，而不是接着走路前
            # 那个陈旧的相位 —— 否则走路停下后相位可能落在正弦过零点，
            # scale_y≈1.0，看起来就是「一动不动也不呼吸」。
            self._breathing = False
            self._breath_job = self.animations.schedule(
                'breath', self._breath_frame_ms(), self._breath_tick)
            return
        if not self._breathing:
            self._breathing = True
            self._breath_t0 = time.monotonic()
        try:
            self._render_breath(time.monotonic())
        except Exception:
            pass
        self._breath_job = self.animations.schedule(
            'breath', self._breath_frame_ms(), self._breath_tick)


    def _breath_frame_ms(self):
        """呼吸帧间隔：慢动作，不需要跟随 30/60 帧设置。"""
        return max(16, int(globals().get('BREATH_FRAME_MS', 80)))


    def _start_breath(self):
        """启动呼吸循环（幂等）。"""
        if self._breath_job is not None or self.closing:
            return
        self._breathing = False
        self._breath_t0 = time.monotonic()
        self._breath_job = self.animations.schedule(
            'breath', self._breath_frame_ms(), self._breath_tick)


    def _stop_breath(self):
        """停止呼吸循环，并复位呼吸状态。"""
        if self._breath_job is not None:
            try:
                self.animations.cancel('breath')
            except Exception:
                pass
            self._breath_job = None
        self._breathing = False



    def _paste_hands(self, frame, size, phase=0.0):
        """把两只小手贴到（已旋转的）身体上；phase 控制一上一下的摆动"""
        hand = self.parts.get('hand')
        clothes = self._clothes_image()
        if hand is None or clothes is None:
            return frame
        cb = clothes.getchannel('A').getbbox()
        if not cb:
            return frame
        scale = size / 1024.0
        hy = cb[1] + (cb[3] - cb[1]) * 0.62 - HAND_UP_OFFSET
        lx = cb[0] + 2 - HAND_SIDE_OFFSET
        rx = cb[2] - hand.width - 2 + HAND_SIDE_OFFSET
        if self.facing_right:
            lx, rx = (1024 - lx - hand.width), (1024 - rx - hand.width)
        hw = max(1, int(hand.width * scale))
        hh = max(1, int(hand.height * scale))
        small, mirror = self._scaled_hand_pair(hw, hh)
        dy = math.sin(phase) * HAND_WALK_AMPLITUDE
        frame.paste(small, (int(lx * scale), int((hy - dy) * scale)), small)
        frame.paste(mirror, (int(rx * scale), int((hy + dy) * scale)), mirror)
        return frame


    def _rotate_fit(self, base, pivot, angle_deg):
        """以 pivot 为轴旋转，并按需轻微缩小保证不超出窗口（不改变窗口尺寸）"""
        size = base.width
        px, py = pivot
        rad = math.radians(angle_deg)
        c, s = math.cos(rad), math.sin(rad)
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        for sx, sy in ((0, 0), (size, 0), (0, size), (size, size)):
            rx = c * (sx - px) - s * (sy - py)
            ry = s * (sx - px) + c * (sy - py)
            min_x = min(min_x, rx)
            max_x = max(max_x, rx)
            min_y = min(min_y, ry)
            max_y = max(max_y, ry)
        k = 1.0
        if min_x < 0:
            k = min(k, px / -min_x)
        if max_x > 0:
            k = min(k, (size - px) / max_x)
        if min_y < 0:
            k = min(k, py / -min_y)
        if max_y > 0:
            k = min(k, (size - py) / max_y)
        k = max(0.05, min(1.0, k))
        ck, sk = c / k, s / k
        data = (ck, sk, px - (ck * px + sk * py),
                -sk, ck, py - (-sk * px + ck * py))
        frame = base.transform(
            (size, size), PIL.Image.AFFINE, data,
            resample=PIL.Image.Resampling.BICUBIC,
            fillcolor=(0, 0, 0, 0))
        # 旋转会让透明黑渗进边缘造成毛边：按预乘还原颜色，并裁掉半透明边
        try:
            import numpy as np
            arr = np.asarray(frame, dtype=np.float32) / 255.0
            a = arr[..., 3]
            rgb = arr[..., :3] / np.maximum(a[..., None], 1e-4)
            rgb = np.clip(rgb, 0.0, 1.0)
            solid = a >= 0.5
            out = np.concatenate(
                [rgb, np.where(solid, 1.0, 0.0)[..., None]], axis=-1)
            out = np.clip(out, 0.0, 1.0)
            return PIL.Image.fromarray(
                (out * 255.0).round().astype(np.uint8), 'RGBA')
        except Exception:
            return frame


    def _desktop_bottom(self):
        """桌面工作区底部（即任务栏上沿）"""
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            ok = ctypes.windll.user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
            if ok:
                return rect.bottom
        except Exception:
            pass
        return self._screen_height()


    def _start_fall_check(self):
        """周期性检查重力：下方悬空就下落，落到窗口/任务栏上沿为止"""
        if self.closing:
            return
        # 自愈：掉落标志卡住但已没有掉落任务在跑时复位
        if self.falling and self._fall_job is None:
            self.falling = False
        self._check_gravity()
        self._fall_job = self.animations.schedule('fall', FALL_CHECK_MS, self._start_fall_check)


    def _check_gravity(self):
        """如果猫下方没有支撑，就开始下落（回弹过程中不重复下落）"""
        if (self.closing or self.hospitalized or self.dragging
                or self.walking or self.falling
                or self.flinging or self.climbing):
            return
        landing = self._compute_landing_y()
        if landing is not None:
            self._begin_fall(landing)


    def _compute_landing_y(self, x=None, y=None):
        """算猫该落到的位置（落下后窗口顶边 y），以“脚底”贴住支撑为准。
        悬空返回目标值，已站稳返回 None。"""
        size = int(ICON_SIZE * self.scale)
        feet_h = int(size * CAT_FEET_RATIO)   # 脚底到窗口顶边的距离
        win_x = win_y = None
        if x is None or y is None:
            win_x, win_y = self._window_pos()
        top = int(y) if y is not None else win_y
        feet = top + feet_h                   # 脚底当前屏幕 y
        x_left = int(x) if x is not None else win_x
        x_right = x_left + size
        desktop = self._desktop_bottom()
        screen_h = self._screen_height()

        TOL = 6  # 判定“已站稳”的容差（px），避免取整误差造成反复下落
        # 1) 脚已进入任务栏区域：落到屏幕底部（脚踩任务栏底）
        if feet > desktop + TOL:
            target = screen_h - feet_h
            return target if abs(target - top) > TOL else None

        # 2) 找横向覆盖猫、上沿在猫脚底下方的“最近”窗口标题栏
        best = None
        for wl, wt, wr in self._other_window_tops():
            if wr <= x_left or wl >= x_right:
                continue
            if wt >= feet - TOL and (best is None or wt < best):
                best = wt
        if best is not None:
            target = best - feet_h
            return target if abs(target - top) > TOL else None

        # 3) 下方没有窗口：落到桌面底部（脚踩任务栏上沿）
        target = desktop - feet_h
        return target if abs(target - top) > TOL else None


    def _other_window_tops(self):
        """返回当前真正可见的顶层窗口标题栏信息。"""
        rects = []
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            dwmapi = ctypes.windll.dwmapi
            my_pid = os.getpid()

            def hwnd_value(handle):
                if not handle:
                    return None
                try:
                    return int(handle)
                except (TypeError, ValueError):
                    try:
                        return ctypes.cast(handle, ctypes.c_void_p).value
                    except Exception:
                        return None

            user32.GetWindow.restype = ctypes.c_void_p
            user32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user32.GetAncestor.restype = ctypes.c_void_p
            user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
            dwmapi.DwmGetWindowAttribute.argtypes = [
                ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
                ctypes.c_uint]

            def is_cloaked(hwnd):
                value = ctypes.c_int(0)
                try:
                    result = dwmapi.DwmGetWindowAttribute(
                        hwnd, 14, ctypes.byref(value), ctypes.sizeof(value))
                    return result == 0 and bool(value.value)
                except Exception:
                    return False

            def covered_at(hwnd, px, py):
                """沿 Z 序检查目标点是否被其他可见窗口遮住。"""
                above = user32.GetWindow(hwnd, 3)  # GW_HWNDPREV
                seen = set()
                while above:
                    value = hwnd_value(above)
                    if value is None or value in seen:
                        break
                    seen.add(value)
                    if (user32.IsWindowVisible(above)
                            and not user32.IsIconic(above)
                            and not is_cloaked(above)):
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(
                            above, ctypes.byref(pid))
                        if pid.value != my_pid:
                            rect = wintypes.RECT()
                            if user32.GetWindowRect(above, ctypes.byref(rect)):
                                if (rect.left <= px < rect.right
                                        and rect.top <= py < rect.bottom):
                                    return True
                    above = user32.GetWindow(above, 3)
                return False

            @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def _enum_cb(hwnd, lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                if user32.IsIconic(hwnd) or is_cloaked(hwnd):
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == my_pid:  # 自己的窗口不当支撑
                    return True

                class_name = ctypes.create_unicode_buffer(128)
                user32.GetClassNameW(hwnd, class_name, 128)
                if class_name.value in {
                        'Progman', 'WorkerW', 'Shell_TrayWnd',
                        'Shell_SecondaryTrayWnd', 'NotifyIconOverflowWindow'}:
                    return True

                rect = wintypes.RECT()
                if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    return True
                if rect.right - rect.left <= 0 or rect.bottom - rect.top <= 0:
                    return True

                # 标题栏中心被其他窗口盖住时，不能作为落脚点。
                center_x = (rect.left + rect.right) // 2
                sample_y = max(0, int(rect.top) + 3)
                if covered_at(hwnd, center_x, sample_y):
                    return True

                rects.append((rect.left, rect.top, rect.right))
                return True

            user32.EnumWindows(_enum_cb, 0)
        except Exception:
            pass
        return rects


    def _begin_fall(self, target_y):
        """高处坠落：使用甩飞物理；落差较大时增加一次小弹跳。"""
        if self.falling or self.closing or self.hospitalized:
            return
        if not self.motion.enter('fall', force=True):
            return
        if self._fall_job is not None:
            try:
                self.animations.cancel('fall')
            except Exception:
                pass
            self._fall_job = None
        size = int(ICON_SIZE * self.scale)
        cur_x, cur_y = self._window_pos()
        self._airborne_x = cur_x
        self._airborne_y = cur_y
        cur = cur_y
        if abs(cur - target_y) <= 2:
            return
        distance = max(1.0, float(target_y) - cur)
        speed = math.sqrt(max(1.0, 2.0 * AIRBORNE_GRAVITY_STEP * distance))
        self._cancel_climb()
        self.falling = True
        self.flinging = True
        self._fling_anim_counter = 0
        self._fling_landing_y = float(target_y)
        self._fling_fixed_landing = True
        self._airborne_last_visual_key = None
        self._fling_bounces = 0
        self._fling_vx = 0.0
        self._fling_vy = min(AIRBORNE_MAX_SPEED, max(1.0, speed))
        self._cancel_walk()
        self._cancel_jump()
        self._cancel_reach()
        self._cancel_anim()
        self._on_taskbar = False
        self._falling_hands = False
        self._hand_lift = 0.0
        self.pose = 'drag'
        initial_key = self._airborne_visual_key()
        self._airborne_last_visual_key = initial_key
        self._airborne_next_render_at = time.monotonic() + anim_frame_ms() / 1000.0
        self._render_airborne_frame(size, initial_key)
        self._fling_tick()


    def _cancel_fall(self):
        """取消重力检测与当前坠落/甩飞任务。"""
        self._sync_airborne_window_position()
        self.motion.finish('fall', 'idle')
        self._airborne_last_visual_key = None
        self.falling = False
        self._fling_landing_y = None
        self._fling_bounces = 0
        self._hand_lift = 0.0
        self._falling_hands = False
        if self._fall_job is not None:
            try:
                self.animations.cancel('fall')
            except Exception:
                pass
            self._fall_job = None



def install_runtime_globals(namespace):
    globals().update(namespace)
