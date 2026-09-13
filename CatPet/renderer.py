# -*- coding: utf-8 -*-
"""RendererMixin 独立模块。"""

import time

# with_hands=False 时，合成图里根本没有手：
# _compose_pose 里那一整串 _paste_*_hands 全部只在 `if with_hands` 分支内执行，
# 而这些手部状态（跳跃/甩飞/攀爬/伸手/下落/挠痒）在本文件里也只被那个分支读。
# 因此它们对这张图没有任何影响，用常量占位即可 —— 长度与真实元组保持一致。
# 放进键里会让「拖拽底图」「空中身体图」在每次起飞/落地后被判为失效而重合成
# （一次约 95ms），表现为抓第二下、每次起飞都掉一下帧。
_NO_HANDS_MOTION = (
    None, '', None, None, False, None, None, None,
    None, None, None, False, None, None, None, None,
    None,
)


# 模特预览的 q 弹幅度较明显；桌宠单击只取其中约 38%，避免视觉过重。
CLICK_BOUNCE_STRENGTH = 0.38
CLICK_BOUNCE_FRAME_MS = 42
CLICK_BOUNCE_FRAMES = tuple(
    (round(1.0 + (sx - 1.0) * CLICK_BOUNCE_STRENGTH, 3),
     round(1.0 + (sy - 1.0) * CLICK_BOUNCE_STRENGTH, 3))
    for sx, sy in ((1.12, 0.82), (0.94, 1.14), (1.05, 0.96),
                   (0.98, 1.03), (1.0, 1.0))
)


class RendererMixin:
    def _get_render_cache(self):
        cache = getattr(self, 'render_cache', None)
        if cache is None:
            from render_cache import RenderCache
            cache = RenderCache()
            self.render_cache = cache
        return cache

    @staticmethod
    def _freeze_render_value(value):
        if isinstance(value, dict):
            return tuple(sorted((str(k), RendererMixin._freeze_render_value(v))
                                for k, v in value.items()))
        if isinstance(value, (set, frozenset)):
            return tuple(sorted(RendererMixin._freeze_render_value(v)
                                for v in value))
        if isinstance(value, (list, tuple)):
            return tuple(RendererMixin._freeze_render_value(v) for v in value)
        try:
            hash(value)
            return value
        except TypeError:
            return repr(value)

    def _render_state_key(self, pose, with_hands=True, clothes_style=None,
                          head_sway=0.0, tail_tilt=None, hair_color=None,
                          eye_color=None, clothes_color=None,
                          equipment_slots=None, equipment_settings=None,
                          hair_style=None, expression_books=None,
                          preview_mode=False):
        slots = (self.equipped_slots if equipment_slots is None
                 else equipment_slots)
        settings = (self.equip_settings if equipment_settings is None
                    else equipment_settings)
        books = (self.books_enabled if expression_books is None
                 else expression_books)
        style = clothes_style or self.equipped_clothes
        h_style = hair_style or getattr(self, 'hair_style', 'hair_1')
        h_color = self.hair_color if hair_color is None else hair_color
        e_color = self.eye_color if eye_color is None else eye_color
        c_color = (self.normal_clothes_color if clothes_color is None
                   else clothes_color)
        tilt_key = (getattr(self, '_tail_tilt', 0.0)
                    if tail_tilt is None else tail_tilt)
        if preview_mode:
            motion = ('preview',)
        else:
            if with_hands:
                hand_state = (
                    getattr(self, '_jump_state', None),
                    getattr(self, '_jump_hand_mode', ''),
                    bool(getattr(self, 'flinging', False)),
                    self._airborne_render_signature(
                        bool(getattr(self, 'falling', False))),
                    bool(getattr(self, 'climbing', False)),
                    getattr(self, '_climb_hand_mode', 'normal'),
                    round(float(getattr(self, '_climb_hand_progress', 0.0)), 3),
                    getattr(self, '_climb_edge_y', 0),
                    getattr(self, '_reach_state', None),
                    getattr(self, '_reach_hand', ''),
                    self._freeze_render_value(
                        getattr(self, '_reach_hand_pos', None)),
                    bool(getattr(self, '_falling_hands', False)),
                    round(float(getattr(self, '_hand_lift', 0.0)), 3),
                    getattr(self, '_scratch_stage', -1),
                    getattr(self, '_scratch_side', 'left'),
                    round(float(getattr(self, '_scratch_lift', 1.0)), 3),
                    # 待机手部动作（招手/舔手）：不在跑的时候恒为 None，
                    # 免得 t 的残留值把「站立/拖拽」这些常用图整批刷掉。
                    self._idle_hand_state_key(),
                )
            else:
                # 不贴手时手部状态与图像无关，见 _NO_HANDS_MOTION 的注释
                hand_state = _NO_HANDS_MOTION
            motion = hand_state + (
                self._freeze_render_value(getattr(self, '_click_expression', None)),
                self._freeze_render_value(getattr(self, '_forced_expression', None)),
                self._freeze_render_value(getattr(getattr(self, 'motion', None), 'expression', None)),
                # 注意：拖拽的三项（_drag_mode / drag_start_x / drag_start_y）**不**在这里。
                # 本文件从不读它们，它们只影响合成之后的 _paste_drag_hands，
                # 而那一刻拖拽底图已经取出来了。放进键里会让同一个底图每次抓取都
                # 重合成一遍（实测一次 100~130ms），拖拽一上手就卡住。
                bool(getattr(self, '_comfy_active', False)),
                int(getattr(self, 'hp', 100)),
                bool(getattr(self, 'facing_right', False)),
            )
        return self._freeze_render_value((
            str(pose), bool(with_hands), round(float(head_sway), 3),
            round(float(tilt_key), 3),
            h_style, h_color, e_color, style, c_color,
            slots, settings, books, motion,
        ))

    def _airborne_render_signature(self, falling=False):
        """空中姿态的量化签名 —— 只作缓存键用，不参与图像合成。

        不在空中时返回 None：落地摩擦/重力会让 _fling_vx/_fling_vy 一直变，
        而这个签名是「站立 / 拖拽 / 走路」这些与空中无关的姿势键的一部分，
        残留速度只要一变，那些图的缓存就整批失效、每帧重新合成一次
        （单次 100ms 以上）。这也是「拖拽一上手就卡」的另一半原因。
        """
        if not (falling or getattr(self, 'flinging', False)):
            return None
        vx = float(getattr(self, '_fling_vx', 0.0))
        vy = float(getattr(self, '_fling_vy', 0.0))
        speed = math.hypot(vx, vy)
        if speed <= 0.01:
            direction = (0, 0)
        else:
            direction = (round(vx / speed, 1), round(vy / speed, 1))
        steps = max(1, int(globals().get(
            'AIRBORNE_VISUAL_POWER_STEPS', 30)))
        max_speed = max(1.0, float(globals().get('AIRBORNE_MAX_SPEED', 25.7)))
        power = int(round(min(1.0, speed / max_speed) * steps))
        return (bool(falling), power, direction)

    def _idle_hand_state_key(self):
        """待机手部动作（招手 / 舔手）的量化签名 —— 只作缓存键用。

        只有这两个动作真的在跑时才返回具体值，其它时候返回 None：
        否则 _idle_hand_t 的残留值会让站立/拖拽这些常用图的缓存整批失效。
        """
        action = getattr(self, '_idle_hand_action', None)
        if action not in ('wave', 'lick'):
            return None
        return (action,
                getattr(self, '_idle_hand_side', 'left'),
                round(float(getattr(self, '_idle_hand_t', 0.0)), 3),
                round(float(getattr(self, '_idle_hand_phase', 0.0)), 2))

    def _display_cache_key(self, pose, new_size, with_hands=True, **kwargs):
        return (self._render_state_key(pose, with_hands, **kwargs),
                tuple(int(v) for v in new_size))

    def _get_display_image(self, pose, new_size, with_hands=True, **kwargs):
        cache = self._get_render_cache()
        key = self._display_cache_key(pose, new_size, with_hands, **kwargs)
        image = cache.get('display', key)
        if image is not None:
            return image
        full = self._compose_pose(pose, with_hands=with_hands, **kwargs)
        image = self._resize_rgba(self._oriented(full), tuple(new_size))
        cache.put('display', key, image)
        return image

    def warm_render_cache(self, poses=None):
        """预热常用姿势的显示图（启动后、改比例后各调一次）。

        姿势合成 + 缩放一次要 100~130ms，而首次拖拽/甩飞必须用到 'drag' 底图。
        不预热的话这一下会整个卡住主线程：窗口不动、跟手消失，看起来就是卡一下。
        这里提前把常用姿势算好，代价只在启动时付一次。

        显示图的缓存键里含 facing_right（朝左、朝右是两张不同的画），
        所以每个姿势都要朝左、朝右各预热一次；否则第一次往另一侧拖
        仍旧是冷启动，依旧要卡 100ms 以上。

        单张约 95ms（合成 ~53ms + 缩放 ~40ms），与姿势无关。默认只预热
        「拖拽 / 站立 / 落地」这条交互主链路，走路等闲时姿势由调用方
        延后一段时间再预热，免得启动停顿太长。

        任何异常都吞掉，预热失败不影响运行。返回成功预热的数量。
        """
        size = (int(ICON_SIZE * self.scale), int(ICON_SIZE * self.scale))
        targets = poses or (('normal', True), ('normal', False),
                            ('drag', False), ('drag', True))
        saved_facing = bool(getattr(self, 'facing_right', False))
        warmed = 0
        try:
            for facing in (False, True):
                self.facing_right = facing
                for name, with_hands in targets:
                    try:
                        self._get_display_image(
                            name, size, with_hands=with_hands)
                        warmed += 1
                    except Exception:
                        continue
        finally:
            self.facing_right = saved_facing
        return warmed

    def _display_size(self):
        """当前显示图片的边长（元组），供各渲染通路统一取用。"""
        size = int(ICON_SIZE * self.scale)
        return (size, size)

    def _apply_click_bounce(self, image):
        """按脚底中心缩放一帧，窗口尺寸保持不变。"""
        scale_x, scale_y = getattr(
            self, '_click_bounce_scale', (1.0, 1.0))
        if abs(scale_x - 1.0) < 0.001 and abs(scale_y - 1.0) < 0.001:
            return image
        width, height = image.size
        target_w = max(1, int(round(width * scale_x)))
        target_h = max(1, int(round(height * scale_y)))
        scaled = self._resize_rgba(image, (target_w, target_h))
        canvas = PIL.Image.new('RGBA', (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(
            scaled, ((width - target_w) // 2, height - target_h))
        return canvas

    def _cancel_click_bounce(self, redraw=False):
        was_active = bool(getattr(self, '_click_bounce_frames', []))
        scale = getattr(self, '_click_bounce_scale', (1.0, 1.0))
        was_active = was_active or abs(scale[0] - 1.0) >= 0.001 or abs(scale[1] - 1.0) >= 0.001
        animations = getattr(self, 'animations', None)
        if animations is not None:
            animations.cancel('click_bounce')
        self._click_bounce_frames = []
        self._click_bounce_scale = (1.0, 1.0)
        if redraw and was_active and not getattr(self, 'closing', False):
            try:
                self.update_image()
            except Exception:
                pass

    def _start_click_bounce(self):
        if getattr(self, 'closing', False):
            return
        cooldown_ms = float(globals().get('CLICK_REACTION_COOLDOWN_MS', 700))
        now = time.monotonic()
        last = float(getattr(self, '_last_click_bounce', 0.0))
        if (now - last) * 1000.0 < cooldown_ms:
            return
        self._last_click_bounce = now
        self._cancel_click_bounce()
        self._click_bounce_frames = list(CLICK_BOUNCE_FRAMES)
        self._click_bounce_tick()

    def _click_bounce_tick(self):
        frames = getattr(self, '_click_bounce_frames', [])
        if not frames:
            self._click_bounce_scale = (1.0, 1.0)
            self.update_image()
            return
        self._click_bounce_scale = frames.pop(0)
        self.update_image()
        self.animations.schedule(
            'click_bounce', CLICK_BOUNCE_FRAME_MS,
            self._click_bounce_tick)

    def _resize_rgba(self, image, new_size):
        """按“预乘 alpha”方式缩放 RGBA 图片，避免透明黑边渗入边缘造成毛边。
        若没有 numpy 则退回普通缩放。

        预乘在 uint16 整数域完成：结果与原 float32 写法逐像素一致
        （rgb*a/255 不可能正好落在 .5 上，四舍五入无歧义；实测 1024² 真实姿势图
        与旧写法输出 0 像素差异），但少了 4 个 1024² 全帧 float32 临时数组，
        单次耗时约从 67ms 降到 45ms。
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
            # 预乘：颜色乘 alpha，再缩放，最后除以新的 alpha（无透明黑渗色）
            prem_img = PIL.Image.fromarray(
                ((rgb * a + 127) // 255).astype(np.uint8), 'RGB')
            a_img = PIL.Image.fromarray(a[..., 0].astype(np.uint8), 'L')
            prem_img = prem_img.resize(new_size,
                                       PIL.Image.Resampling.LANCZOS)
            a_img = a_img.resize(new_size, PIL.Image.Resampling.LANCZOS)
            # 除法只在小图上做（1024² → 127²，工作量差 64 倍）
            prem2 = np.asarray(prem_img, dtype=np.float32) / 255.0
            a2 = np.asarray(a_img, dtype=np.float32) / 255.0
            out_rgb = prem2 / np.maximum(a2[..., None], 1e-4)
            out = np.concatenate([out_rgb, a2[..., None]], axis=-1)
            out = np.clip(out, 0.0, 1.0)
            # 清理外圈毛边：去掉最外围的半透明过渡像素
            # 透明度>=128 的当实体（整为 255），否则直接裁成透明
            a_out = out[..., 3]
            solid = a_out >= 0.5
            out[..., 3] = np.where(solid, 1.0, 0.0)
            return PIL.Image.fromarray((out * 255.0).round().astype(np.uint8),
                                       'RGBA')
        except Exception:
            return image.resize(new_size, PIL.Image.Resampling.LANCZOS)


    def _hair_image(self, key, color=None, preserve_brown=False,
                    darken=1.0):
        """给头发/耳朵上色：保留黑色描边；可整体加深（后发更暗）"""
        color = self.hair_color if color is None else color
        if not color and darken >= 1.0:
            return self.parts[key]
        cache_key = (key, color, preserve_brown, round(darken, 3))
        if cache_key in self._hair_cache:
            return self._hair_cache[cache_key]
        try:
            import numpy as np
            base = self.parts[key].convert('RGBA')
            arr = np.asarray(base, dtype=np.float32)
            rgb = arr[..., :3]
            alpha = arr[..., 3]
            lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
            dark = lum < 60  # 黑色描边保留
            keep = dark
            if preserve_brown:
                r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
                brown = (r > 140) & (g > 100) & (b < 200) & ((r - b) > 25)
                keep = dark | brown  # 棕色内耳也保留
            if color:
                target = np.array([
                    int(color[1:3], 16), int(color[3:5], 16),
                    int(color[5:7], 16)], dtype=np.float32)
                tint = (lum[..., None] / 255.0) * target
                out_rgb = np.where(keep[..., None], rgb, tint)
            else:
                out_rgb = rgb.copy()
            if darken < 1.0:
                # 后发加一层深色蒙版（描边不受影响，本来就接近黑）
                out_rgb = out_rgb * darken
            out = np.dstack([out_rgb, alpha]).clip(0, 255).astype(np.uint8)
            image = PIL.Image.fromarray(out, 'RGBA')
            self._hair_cache[cache_key] = image
            return image
        except Exception:
            return self.parts[key]


    def _eye_image(self, key, color=None):
        """眼睛上色：白色不变；黑色按色板；灰色用浅色蒙版"""
        color = self.eye_color if color is None else color
        if not color:
            return self.parts[key]
        cache_key = (key, color)
        if cache_key in self._eye_cache:
            return self._eye_cache[cache_key]
        try:
            import numpy as np
            base = self.parts[key].convert('RGBA')
            arr = np.asarray(base, dtype=np.float32)
            rgb = arr[..., :3]
            alpha = arr[..., 3]
            lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
            target = np.array([
                int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            ], dtype=np.float32)
            light = target * 0.45 + 255.0 * 0.55  # 浅色蒙版
            black_mask = (lum < 35)[..., None]    # 黑色：不变
            white_mask = (lum > 200)[..., None]   # 白色：不变
            deep_mask = ((lum >= 35) & (lum < 90))[..., None]   # 深灰：色板色
            # 深灰保留一点明暗，整体接近所选颜色
            deep_color = target * (0.85 + 0.15 * (lum[..., None] / 90.0))
            # 浅灰：颜色板颜色 + 浅色蒙版
            light_color = light * (0.6 + 0.4 * (lum[..., None] / 200.0))
            out_rgb = np.where(black_mask, rgb, np.where(
                white_mask, rgb, np.where(deep_mask, deep_color, light_color)))
            out = np.dstack([out_rgb, alpha]).clip(0, 255).astype(np.uint8)
            image = PIL.Image.fromarray(out, 'RGBA')
            self._eye_cache[cache_key] = image
            return image
        except Exception:
            return self.parts[key]


    def _current_expression_key(self, books_enabled=None):
        """返回指定书籍状态的日常表情预设键。"""
        books = (getattr(self, 'books_enabled', set())
                 if books_enabled is None else books_enabled)
        for book_id in EXPRESSION_BOOK_ORDER:
            if book_id in books:
                return EXPRESSION_BOOK_TO_PRESET[book_id]
        return 'happy'


    def _current_expression_preset(self, books_enabled=None):
        return EXPRESSION_PRESETS.get(
            self._current_expression_key(books_enabled),
            EXPRESSION_PRESETS['happy'])


    def _random_click_expression(self):
        """点击时按配置文件分别抽取嘴巴、眼睛和眉毛。"""
        import random
        from expression_config import (
            DEFAULT_CLICK_EXPRESSION_CHOICES, choose_weighted)
        config = getattr(self, '_click_expression_config', {}) or {}
        configured = config.get('choices', {})
        expression = {}
        books = getattr(self, 'books_enabled', set())
        for part in ('mouth', 'eye', 'brow'):
            choices = configured.get(part, {})
            if not isinstance(choices, dict):
                choices = {}
            if part == 'eye' and 'expression_comfy' in books:
                choices = {'eye_close3': 1, 'eye_comfy': 1}
            elif part == 'eye' and 'expression_secret' in books:
                choices = {'eye_2': 1, 'eye_close3': 1}
            elif part == 'eye' and 'expression_happy' in books:
                source = choices or DEFAULT_CLICK_EXPRESSION_CHOICES['eye']
                choices = {key: weight for key, weight in source.items()
                           if key != 'eye_1'}
            elif part == 'mouth' and 'expression_grumpy' in books:
                choices = {'mouth_sad': 1}
            valid = {
                key: weight for key, weight in choices.items()
                if key in self.parts and float(weight) > 0
            }
            if not valid:
                valid = {
                    key: weight
                    for key, weight in DEFAULT_CLICK_EXPRESSION_CHOICES[part].items()
                    if key in self.parts
                }
            selected = choose_weighted(valid, random)
            if selected is not None:
                expression[part] = selected
        return expression


    def _earring_image(self, color=None):
        """耳环染色：金色主体换色，保留黑色描边。"""
        color = color or self.equip_settings.get('earrings_color', '#ffdf09')
        cache_key = color
        if cache_key in self._earring_color_cache:
            return self._earring_color_cache[cache_key]
        base = self.parts.get('gold_earrings')
        if base is None:
            return None
        try:
            import numpy as np
            arr = np.asarray(base.convert('RGBA'), dtype=np.float32)
            rgb = arr[..., :3]
            alpha = arr[..., 3]
            r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            gold = ((r > 70) & (g > 55) & (b < 180)
                    & ((r - b) > 35) & ((g - b) > 25))
            target = np.array([
                int(color[1:3], 16), int(color[3:5], 16),
                int(color[5:7], 16)], dtype=np.float32)
            shade = 0.35 + 0.65 * (lum[..., None] / 255.0)
            out_rgb = np.where(gold[..., None], target * shade, rgb)
            out = np.dstack([out_rgb, alpha]).clip(0, 255).astype(np.uint8)
            image = PIL.Image.fromarray(out, 'RGBA')
            self._earring_color_cache[cache_key] = image
            return image
        except Exception:
            return base


    def _hat_image(self, key, color):
        """鸭舌帽/小鸡帽染色：保留黑色描边。"""
        cache_key = (key, color)
        if cache_key in self._hat_color_cache:
            return self._hat_color_cache[cache_key]
        base = self.parts.get(key)
        if base is None:
            return None
        try:
            import numpy as np
            arr = np.asarray(base.convert('RGBA'), dtype=np.float32)
            rgb = arr[..., :3]
            alpha = arr[..., 3]
            lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
            mask = lum > 55
            target = np.array([
                int(color[1:3], 16), int(color[3:5], 16),
                int(color[5:7], 16)], dtype=np.float32)
            shade = 0.35 + 0.65 * (lum[..., None] / 255.0)
            out_rgb = np.where(mask[..., None], target * shade, rgb)
            out = np.dstack([out_rgb, alpha]).clip(0, 255).astype(np.uint8)
            image = PIL.Image.fromarray(out, 'RGBA')
            self._hat_color_cache[cache_key] = image
            return image
        except Exception:
            return base


    def _hat_ji_image(self, color, scale):
        """小鸡头饰：先染色，再按设置缩放。"""
        layer = self._hat_image('hat_ji', color)
        if layer is None:
            return None
        try:
            scale = max(0.8, min(1.1, float(scale)))
        except (TypeError, ValueError):
            scale = 0.8
        size = (max(1, int(layer.width * scale)),
                max(1, int(layer.height * scale)))
        return layer.resize(size, PIL.Image.Resampling.LANCZOS)


    def _hat2_image(self, brown_color, cream_color):
        """小洋帽：棕色和米白色部分分别染色。"""
        cache_key = ('hat_2', brown_color, cream_color)
        if cache_key in self._hat_color_cache:
            return self._hat_color_cache[cache_key]
        base = self.parts.get('hat_2')
        if base is None:
            return None
        try:
            import numpy as np
            arr = np.asarray(base.convert('RGBA'), dtype=np.float32)
            rgb = arr[..., :3]
            alpha = arr[..., 3]
            r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            brown = ((r - b) > 12) & ((g - b) > 5) & (lum < 190)
            cream = (~brown) & (np.min(rgb, axis=2) > 150)
            out_rgb = rgb.copy()
            for mask, color in ((brown, brown_color), (cream, cream_color)):
                target = np.array([
                    int(color[1:3], 16), int(color[3:5], 16),
                    int(color[5:7], 16)], dtype=np.float32)
                shade = 0.35 + 0.65 * (lum[..., None] / 255.0)
                out_rgb = np.where(mask[..., None], target * shade, out_rgb)
            out = np.dstack([out_rgb, alpha]).clip(0, 255).astype(np.uint8)
            image = PIL.Image.fromarray(out, 'RGBA')
            self._hat_color_cache[cache_key] = image
            return image
        except Exception:
            return base


    def _clothes_image(self, style=None, color=None):
        style = style or self.equipped_clothes
        mapping = {
            'hefu_blue': 'clothes_hefu_blue',
            'hefu_green': 'clothes_hefu_green',
            'hefu_red': 'clothes_hefu_red',
            'thief': 'clothes_thief',
            'knight': 'clothes_knight',
            'peasant': 'clothes_peasant',
            'white_moon': 'clothes_whitemoon',
            'black_sun': 'clothes_blacksun',
            'blue_noble': 'clothes_noble_blue',
            'clown': 'clothes_clown',
            'north_maid1': 'north_maid1',
            'north_night': 'north_night',
            'north_windbreaker': 'north_windbreaker',
        }
        if style != 'normal':
            return self.parts.get(mapping.get(style, 'clothes'),
                                  self.parts.get('clothes'))
        return self._normal_clothes_image(color)


    def _clothes_bbox(self, style=None, color=None):
        """衣服不透明区域的 bbox（带缓存）。

        getbbox() 要扫一遍 1024² 的 alpha（实测 1~2ms），而手部动画
        （挠头、攀爬、甩飞）每一帧都要拿它来定位双手。衣服没换时它是常量，
        所以按 (款式, 颜色) 缓存起来，别每帧重扫。
        """
        key = (style or self.equipped_clothes,
               color if color is not None else self.normal_clothes_color)
        cache = getattr(self, '_clothes_bbox_cache', None)
        if cache is None:
            cache = {}
            self._clothes_bbox_cache = cache
        if key in cache:
            return cache[key]
        clothes = self._clothes_image(style, color)
        bbox = clothes.getchannel('A').getbbox() if clothes is not None else None
        cache[key] = bbox
        return bbox

    def _normal_clothes_image(self, color=None):
        """普通衣服染色：保留黑色描边，其余部分按亮度着色。"""
        color = self.normal_clothes_color if color is None else color
        if not color:
            return self.parts['clothes']
        cache_key = color
        if cache_key in self._clothes_color_cache:
            return self._clothes_color_cache[cache_key]
        try:
            import numpy as np
            base = self.parts['clothes'].convert('RGBA')
            arr = np.asarray(base, dtype=np.float32)
            rgb = arr[..., :3]
            alpha = arr[..., 3]
            lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
            keep = lum < 60
            target = np.array([
                int(color[1:3], 16), int(color[3:5], 16),
                int(color[5:7], 16)], dtype=np.float32)
            tint = (lum[..., None] / 255.0) * target
            out_rgb = np.where(keep[..., None], rgb, tint)
            out = np.dstack([out_rgb, alpha]).clip(0, 255).astype(np.uint8)
            image = PIL.Image.fromarray(out, 'RGBA')
            self._clothes_color_cache[cache_key] = image
            return image
        except Exception:
            return self.parts['clothes']


    def _slot_item_ids(self, slots, slot):
        """读取某个装备槽中的物品 id 列表。"""
        if not isinstance(slots, dict):
            return []
        value = slots.get(slot)
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, (list, tuple)):
            values = value
        else:
            return []
        result = []
        for iid in values:
            if isinstance(iid, str) and iid in ITEMS and iid not in result:
                result.append(iid)
        return result


    def _slice_layer_x(self, image, right=False):
        """按中线切出头饰的左半或右半。"""
        w, h = image.size
        half = w // 2
        box = (half, 0, w, h) if right else (0, 0, half, h)
        crop = image.crop(box)
        out = PIL.Image.new('RGBA', image.size, (0, 0, 0, 0))
        out.paste(crop, (box[0], 0), crop)
        return out


    def _collar_image(self, style=1, rope_color=None, deco_color=None):
        """细项圈双色染色：红绳和浅色装饰分别换色，保留黑边。"""
        rope_color = rope_color or self.equip_settings.get(
            'collar_rope_color', '#c0392b')
        deco_color = deco_color or self.equip_settings.get(
            'collar_deco_color', '#f1e8d7')
        style = 2 if int(style) == 2 else 1
        cache_key = (style, rope_color, deco_color)
        if cache_key in self._collar_color_cache:
            return self._collar_color_cache[cache_key]
        key = 'fine_collar2' if style == 2 else 'fine_collar1'
        base = self.parts.get(key)
        if base is None:
            return base
        try:
            import numpy as np
            arr = np.asarray(base.convert('RGBA'), dtype=np.float32)
            rgb = arr[..., :3]
            alpha = arr[..., 3]
            r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            chroma = np.max(rgb, axis=2) - np.min(rgb, axis=2)
            rope = ((r - np.maximum(g, b)) > 16) & (chroma > 18)
            deco = (~rope) & (np.min(rgb, axis=2) > 135)
            out_rgb = rgb.copy()
            for mask, color in ((rope, rope_color), (deco, deco_color)):
                target = np.array([
                    int(color[1:3], 16), int(color[3:5], 16),
                    int(color[5:7], 16)], dtype=np.float32)
                shade = 0.38 + 0.62 * (lum[..., None] / 255.0)
                out_rgb = np.where(mask[..., None],
                                   target * shade, out_rgb)
            out = np.dstack([out_rgb, alpha]).clip(0, 255).astype(np.uint8)
            image = PIL.Image.fromarray(out, 'RGBA')
            self._collar_color_cache[cache_key] = image
            return image
        except Exception:
            return base


    def _paste_headwear_group(self, group, pose, slots, settings):
        """头饰统一贴在头部组最上方，耳环跟随右耳形变。"""
        items = self._slot_item_ids(slots, '头饰')
        order = [iid for iid in ('gold_earrings', 'sunglasses', 'hat_1', 'hat_2', 'hat_ji')
                 if iid in items]
        order += [iid for iid in items if iid not in order]
        for iid in order:
            layer = self.parts.get(iid)
            if iid == 'gold_earrings':
                layer = self._earring_image(
                    settings.get('earrings_color', '#ffdf09'))
            elif iid == 'hat_1':
                layer = self._hat_image(
                    'hat_1', settings.get('hat_1_color', '#f3f0df'))
            elif iid == 'hat_2':
                layer = self._hat2_image(
                    settings.get('hat_2_brown_color', '#594926'),
                    settings.get('hat_2_cream_color', '#fbf9ec'))
            elif iid == 'hat_ji':
                layer = self._hat_ji_image(
                    settings.get('hat_ji_color', '#ffffff'),
                    settings.get('hat_ji_scale', 0.8))
            if layer is None:
                continue
            if iid == 'gold_earrings' and pose == 'ear':
                left = self._slice_layer_x(layer, right=False)
                right = self._warp_ear_down(
                    self._slice_layer_x(layer, right=True))
                group.paste(left, (0, 0), left)
                group.paste(right, (0, 0), right)
            elif iid == 'sunglasses':
                offset = int(settings.get('sunglasses_y_offset', 80))
                group.paste(layer, (0, offset), layer)
            elif iid == 'hat_ji':
                x = 465 - layer.width // 2
                bottom_y = 215
                y = bottom_y - layer.height
                group.paste(layer, (x, y), layer)
            else:
                group.paste(layer, (0, 0), layer)


    def _paste_accessory_layers(self, canvas, slots, settings):
        """饰品叠在衣服上方、头部下方；目前支持细项圈。"""
        for iid in self._slot_item_ids(slots, '饰品'):
            if iid == 'fine_collar':
                style = settings.get('collar_style', 1)
                rope = settings.get('collar_rope_color', '#c0392b')
                deco = settings.get('collar_deco_color', '#f1e8d7')
                layer = self._collar_image(style, rope, deco)
                if layer is not None:
                    canvas.paste(layer, (0, 0), layer)


    def _compose_pose(self, pose, with_hands=True, clothes_style=None,
                      head_sway=0.0, tail_tilt=None, hair_color=None,
                      eye_color=None, clothes_color=None,
                      equipment_slots=None, equipment_settings=None,
                      hair_style=None, expression_books=None,
                      preview_mode=False):
        cache = self._get_render_cache()
        key = self._render_state_key(
            pose, with_hands, clothes_style, head_sway, tail_tilt,
            hair_color, eye_color, clothes_color, equipment_slots,
            equipment_settings, hair_style, expression_books,
            preview_mode=preview_mode)
        cached = cache.get('compose', key)
        if cached is not None:
            return cached
        image = self._compose_pose_uncached(
            pose, with_hands, clothes_style, head_sway, tail_tilt,
            hair_color, eye_color, clothes_color, equipment_slots,
            equipment_settings, hair_style, expression_books,
            preview_mode=preview_mode)
        cache.put('compose', key, image)
        return image


    def _compose_pose_uncached(self, pose, with_hands=True, clothes_style=None,
                      head_sway=0.0, tail_tilt=None, hair_color=None,
                      eye_color=None, clothes_color=None,
                      equipment_slots=None, equipment_settings=None,
                      hair_style=None, expression_books=None,
                      preview_mode=False):
        """按图层合成：头部组(头/眼/眉/嘴/耳)整体旋转，身体/衣服/手分处理"""
        p = self.parts
        slots = self.equipped_slots if equipment_slots is None else equipment_slots
        settings = (self.equip_settings if equipment_settings is None
                    else equipment_settings)
        expression_books = (self.books_enabled if expression_books is None
                            else expression_books)
        # 后发单独一组，放在衣服下方、头部主体上方之前的层级。
        back_hair_group = PIL.Image.new('RGBA', p['head'].size, (0, 0, 0, 0))
        if p.get('hair_2') is not None:
            hair2 = self._hair_image('hair_2', hair_color, darken=0.72)
            back_hair_group.paste(hair2, (0, 0), hair2)
        # 头部主体及五官/前发组，整体位于衣服上方。
        head_group = PIL.Image.new('RGBA', p['head'].size, (0, 0, 0, 0))
        head_group.paste(p['head'], (0, 0), p['head'])
        hair_key = hair_style or getattr(self, 'hair_style', 'hair_1')
        if p.get(hair_key) is not None:
            hair1 = self._hair_image(hair_key, hair_color)
            head_group.paste(hair1, (0, 0), hair1)
        motion_expression = getattr(getattr(self, 'motion', None), 'expression', None)
        forced_expression = None if preview_mode else (
            motion_expression or getattr(self, '_forced_expression', None))
        if preview_mode:
            expression = self._current_expression_preset(expression_books)
            expression_key = self._current_expression_key(expression_books)
            has_expression_book = any(
                book_id in expression_books
                for book_id in EXPRESSION_BOOK_ORDER)
        elif forced_expression:
            expression = dict(forced_expression)
            expression_key = 'happy'
            has_expression_book = True
        else:
            expression = (getattr(self, '_click_expression', None)
                          or self._current_expression_preset(expression_books))
            expression_key = self._current_expression_key(expression_books)
            has_expression_book = any(
                book_id in expression_books
                for book_id in EXPRESSION_BOOK_ORDER)
        expr_eye = expression.get('eye', 'eye')
        expr_brow = expression.get('brow', 'brow')
        expr_mouth = expression.get('mouth', 'mouth_happy')
        if pose == 'drag':
            eye_key = 'eye_close2'
        elif pose == 'blink':
            eye_key = 'eye_close1'
        elif forced_expression and not preview_mode:
            eye_key = expr_eye
        elif (not preview_mode
              and getattr(self, '_click_expression', None) is not None):
            eye_key = expr_eye
        elif not preview_mode and getattr(self, '_comfy_active', False):
            eye_key = 'eye_comfy'
        else:
            eye_key = expr_eye
        brow_key = expr_brow
        if pose == 'drag':
            mouth_key = 'mouth_sad'
        elif forced_expression and not preview_mode:
            mouth_key = expr_mouth
        elif (not preview_mode
              and getattr(self, '_click_expression', None) is not None):
            mouth_key = expr_mouth
        elif not preview_mode and getattr(self, '_comfy_active', False):
            mouth_key = 'mouth_comfy'
        elif (not preview_mode and self.hp < 50 and expression_key == 'happy'
              and not has_expression_book):
            mouth_key = 'mouth_sad'
        else:
            mouth_key = expr_mouth
        if eye_key in ('eye', 'eye_comfy', 'eye_1'):
            eye_img = self._eye_image(eye_key, eye_color)
        else:
            eye_img = p[eye_key]
        head_group.paste(eye_img, (0, 0), eye_img)
        head_group.paste(p[brow_key], (0, 0), p[brow_key])
        head_group.paste(p[mouth_key], (0, 0), p[mouth_key])
        ear_left = self._hair_image('ear_left', hair_color,
                                    preserve_brown=True)
        head_group.paste(ear_left, (0, 0), ear_left)
        if pose == 'ear':
            ear_r = self._hair_image('ear_right', hair_color,
                                     preserve_brown=True)
            wr = self._warp_ear_down(ear_r)
            head_group.paste(wr, (0, 0), wr)
        else:
            ear_right = self._hair_image('ear_right', hair_color,
                                         preserve_brown=True)
            head_group.paste(ear_right, (0, 0), ear_right)
        self._paste_headwear_group(head_group, pose, slots, settings)
        if head_sway:
            back_hair_group = back_hair_group.rotate(
                head_sway, resample=PIL.Image.Resampling.BICUBIC,
                center=(450, 380), expand=False)
            head_group = head_group.rotate(
                head_sway, resample=PIL.Image.Resampling.BICUBIC,
                center=(450, 380), expand=False)
        # 图层顺序：尾巴 → hair_2 → 衣服 → 头部组 → 小手。
        canvas = PIL.Image.new('RGBA', head_group.size, (0, 0, 0, 0))
        tail_img = self._hair_image('tail', hair_color)
        if pose == 'tail':
            tilt = self._tail_tilt if tail_tilt is None else tail_tilt
            tw = self._warp_tail(tail_img, tilt)
            canvas.paste(tw, (0, 0), tw)
        else:
            canvas.paste(tail_img, (0, 0), tail_img)
        canvas.paste(back_hair_group, (0, 0), back_hair_group)
        style = clothes_style or self.equipped_clothes
        clothes = self._clothes_image(style, clothes_color)
        canvas.paste(clothes, (0, 0), clothes)
        self._paste_accessory_layers(canvas, slots, settings)
        canvas.paste(head_group, (0, 0), head_group)
        # 小手
        hand = p.get('hand')
        if with_hands and hand is not None:
            use_rest_hands = preview_mode
            if not preview_mode and getattr(self, '_jump_state', None):
                self._paste_jump_hands(canvas)
            elif not preview_mode and getattr(self, 'flinging', False):
                self._paste_fling_hands(canvas)
            elif (not preview_mode and getattr(self, 'climbing', False)
                  and getattr(self, '_climb_hand_mode', 'normal') != 'normal'):
                self._paste_climb_hands(canvas)
            elif not preview_mode and getattr(self, '_reach_state', None):
                self._paste_reach_hands(canvas)
            elif not preview_mode and getattr(self, '_falling_hands', False):
                self._paste_fall_hands(canvas)
            elif not preview_mode and getattr(self, '_idle_hand_action', None):
                self._paste_idle_hands(canvas)
            elif not preview_mode and pose == 'scratch':
                self._paste_scratch_hands(canvas)
            else:
                use_rest_hands = True
            if use_rest_hands:
                cb = clothes.getchannel('A').getbbox()
                if cb:
                    hw, hh = hand.size
                    hy = int(cb[1] + (cb[3] - cb[1]) * 0.62) - HAND_UP_OFFSET
                    lx = int(cb[0] + 2) - HAND_SIDE_OFFSET
                    rx = int(cb[2] - hw - 2) + HAND_SIDE_OFFSET
                    canvas.paste(hand, (lx, hy), hand)
                    right_hand = hand.transpose(PIL.Image.FLIP_LEFT_RIGHT)
                    canvas.paste(right_hand, (rx, hy), right_hand)
        return canvas


    def _full_for(self, pose, clothes_style=None, head_sway=0.0,
                  tail_tilt=None, hair_color=None, eye_color=None,
                  clothes_color=None, equipment_slots=None,
                  equipment_settings=None, hair_style=None,
                  expression_books=None, preview_mode=False):
        """返回某姿势的合成图（1024）"""
        return self._compose_pose(
            pose, clothes_style=clothes_style,
            head_sway=head_sway, tail_tilt=tail_tilt,
            hair_color=hair_color, eye_color=eye_color,
            clothes_color=clothes_color,
            equipment_slots=equipment_slots,
            equipment_settings=equipment_settings,
            hair_style=hair_style,
            expression_books=expression_books,
            preview_mode=preview_mode)


    def _current_full(self):
        """返回当前姿势的合成图（1024）"""
        return self._full_for(self.pose)


    def _oriented(self, image):
        """猫朝右时水平翻转"""
        if self.facing_right:
            return image.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        return image


    def _warp_ear_down(self, layer):
        """右耳形变（类 PS 扭曲）：只把右上角轻微下拉"""
        try:
            import numpy as np
            bbox = layer.getchannel('A').getbbox()
            if not bbox:
                return layer
            crop = layer.crop(bbox)
            w, h = crop.size
            arr = np.asarray(crop, dtype=np.uint8)
            amp = float(EAR_WARP_PX)
            Xn = np.arange(w, dtype=np.float32) / max(1, w - 1)
            X = Xn[None, :]
            Yn = np.arange(h, dtype=np.float32) / max(1, h - 1)
            Y = Yn[:, None]
            pull = amp * X * (1.0 - Y)   # 右下角不动，右上角下拉
            sy = Y * (h - 1) - pull
            sy = np.clip(sy, 0, h - 1).astype(int)
            xx = np.broadcast_to(np.arange(w), (h, w))
            out = arr[sy, xx]
            warped = PIL.Image.fromarray(out, 'RGBA')
            full = PIL.Image.new('RGBA', layer.size, (0, 0, 0, 0))
            full.paste(warped, (bbox[0], bbox[1]), warped)
            return full
        except Exception:
            return layer


    def _warp_tail(self, layer, angle):
        """尾巴轻微摆动：绕尾巴根部小幅旋转"""
        try:
            bbox = layer.getchannel('A').getbbox()
            if not bbox:
                return layer
            crop = layer.crop(bbox)
            w, h = crop.size
            rot = crop.rotate(
                angle * TAIL_WAG_ANGLE,
                resample=PIL.Image.Resampling.BICUBIC,
                center=(w * 0.18, h * 0.55), expand=False)
            full = PIL.Image.new('RGBA', layer.size, (0, 0, 0, 0))
            full.paste(rot, (bbox[0], bbox[1]), rot)
            return full
        except Exception:
            return layer


    def update_image(self):
        """按当前姿势合成图层并按比例重新生成显示图片"""
        size = (int(ICON_SIZE * self.scale), int(ICON_SIZE * self.scale))
        key = self._display_cache_key(self.pose, size, True)
        resized = self._get_display_image(self.pose, size)
        scale_x, scale_y = getattr(
            self, '_click_bounce_scale', (1.0, 1.0))
        if abs(scale_x - 1.0) >= 0.001 or abs(scale_y - 1.0) >= 0.001:
            resized = self._apply_click_bounce(resized)
            self.photo = PIL.ImageTk.PhotoImage(resized)
        else:
            cache = self._get_render_cache()
            self.photo = cache.get_or_create(
                'photo', key, lambda: PIL.ImageTk.PhotoImage(resized))
        self.label.config(image=self.photo)


    def show_pose(self, pose):
        """切换到指定姿势的图片"""
        if pose != self.pose:
            self.pose = pose
            self.update_image()


    def set_scale(self, new_scale):
        """设置比例（自动限制在最小/最大范围内）并更新窗口"""
        new_scale = max(SCALE_MIN, min(SCALE_MAX, new_scale))
        if abs(new_scale - self.scale) < 0.001:
            return
        self.scale = new_scale
        self.update_image()
        size = int(ICON_SIZE * self.scale)
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f'{size}x{size}+{x}+{y}')


    def _clean_rgba_edges(self, frame):
        """去除旋转产生的半透明黑边，减少拖动时的毛边。"""
        try:
            import numpy as np
            arr = np.asarray(frame, dtype=np.float32) / 255.0
            alpha = arr[..., 3]
            rgb = arr[..., :3] / np.maximum(alpha[..., None], 1e-4)
            solid = alpha >= 0.5
            out = np.concatenate(
                [np.clip(rgb, 0.0, 1.0),
                 np.where(solid, 1.0, 0.0)[..., None]], axis=-1)
            return PIL.Image.fromarray(
                (out * 255.0).round().astype(np.uint8), 'RGBA')
        except Exception:
            return frame



def install_runtime_globals(namespace):
    globals().update(namespace)
