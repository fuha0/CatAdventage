# -*- coding: utf-8 -*-
class EditorEnhancementsMixin:
    def _open_sunglasses_adjust(self):
        self._ensure_item_selected('sunglasses', '\u5934\u9970')
        return super()._open_sunglasses_adjust()

    def _place_editor_window(self, win):
        owner = getattr(self, '_warehouse_win', None)
        if owner is None:
            owner = getattr(self, '_adventure_win', None)
        if owner is None:
            return
        try:
            win.update_idletasks()
            x = owner.winfo_x() + owner.winfo_width() + 8
            y = owner.winfo_y()
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            x = max(0, min(x, sw - win.winfo_width()))
            y = max(0, min(y, sh - win.winfo_height()))
            win.geometry(f'+{int(x)}+{int(y)}')
        except Exception:
            pass

    def _open_hat_ji_scale(self):
        self._ensure_item_selected('hat_ji', '\u5934\u9970')
        result = super()._open_hat_ji_scale()
        win = getattr(self, '_hat_scale_win', None)
        if win is not None:
            self.root.after(0, lambda w=win: self._place_editor_window(w))
        return result

    def _open_color_palette(self, kind):
        if kind == 'clothes':
            self._select_clothes('normal')
        else:
            mapping = {'earrings': ('gold_earrings', '\u5934\u9970'), 'hat_1': ('hat_1', '\u5934\u9970'), 'hat_ji': ('hat_ji', '\u5934\u9970'), 'hat_2_brown': ('hat_2', '\u5934\u9970'), 'hat_2_cream': ('hat_2', '\u5934\u9970'), 'collar_rope': ('fine_collar', '\u9970\u54c1'), 'collar_deco': ('fine_collar', '\u9970\u54c1')}
            item = mapping.get(kind)
            if item is not None:
                self._ensure_item_selected(item[0], item[1])
        return super()._open_color_palette(kind)
