# -*- coding: utf-8 -*-
"""仓库及通用界面的第一阶段主题配置。"""
import tkinter as tk
from tkinter import ttk

THEME = {
    "bg": "#F5EFE6",
    "card": "#FFFDF8",
    "card_alt": "#F0E7DA",
    "border": "#D8C8B6",
    "text": "#463B33",
    "muted": "#8A7A6D",
    "accent": "#D89B5A",
    "accent_hover": "#C98745",
    "accent_text": "#FFFFFF",
    "success": "#6FA76F",
    "danger": "#C95D5D",
    "preview_bg": "#E8DDCF",
    "tab_bg": "#E8DDCF",
    "tab_selected": "#D89B5A",
}

FONT_FAMILY = "Microsoft YaHei UI"
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_TITLE = (FONT_FAMILY, 14, "bold")
FONT_BUTTON = (FONT_FAMILY, 10)


def configure_theme(widget):
    style = ttk.Style(widget)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(".", background=THEME["bg"], foreground=THEME["text"], font=FONT_BODY)
    style.configure("TFrame", background=THEME["bg"])
    style.configure("TLabel", background=THEME["bg"], foreground=THEME["text"], font=FONT_BODY)
    style.configure("TButton", font=FONT_BUTTON, padding=(10, 6))
    style.configure(
        "TCombobox", padding=5, fieldbackground=THEME["card"],
        background=THEME["card"], foreground=THEME["text"],
        selectbackground=THEME["card"], selectforeground=THEME["text"],
        arrowcolor=THEME["accent"])
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", THEME["card"]),
                         ("disabled", THEME["card_alt"])],
        background=[("readonly", THEME["card"]),
                    ("disabled", THEME["card_alt"])],
        foreground=[("readonly", THEME["text"]),
                    ("disabled", THEME["muted"])],
        selectbackground=[("readonly", THEME["card"]),
                          ("disabled", THEME["card_alt"])],
        selectforeground=[("readonly", THEME["text"]),
                          ("disabled", THEME["muted"])])
    style.configure("TNotebook", background=THEME["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", font=FONT_BUTTON, padding=(14, 7), background=THEME["tab_bg"], foreground=THEME["muted"])
    style.map("TNotebook.Tab", background=[("selected", THEME["tab_selected"]), ("active", THEME["accent_hover"])], foreground=[("selected", THEME["accent_text"]), ("active", THEME["accent_text"])])


def make_button(parent, text, command=None, kind="secondary", **kwargs):
    palettes = {
        "primary": (THEME["accent"], THEME["accent_text"], THEME["accent_hover"]),
        "secondary": (THEME["card_alt"], THEME["text"], THEME["border"]),
        "ghost": (THEME["bg"], THEME["muted"], THEME["card_alt"]),
        "tab": (THEME["tab_bg"], THEME["text"], THEME["accent_hover"]),
    }
    bg, fg, active = palettes.get(kind, palettes["secondary"])
    options = {
        "font": FONT_BUTTON, "bg": bg, "fg": fg, "activebackground": active,
        "activeforeground": kwargs.pop("activeforeground", fg),
        "relief": "flat", "bd": 0, "highlightthickness": 0,
        "cursor": "hand2", "padx": 10, "pady": 6,
        "disabledforeground": THEME["muted"],
    }
    options.update(kwargs)
    return tk.Button(parent, text=text, command=command, **options)


def make_card(parent, **kwargs):
    options = {"bg": THEME["card"], "bd": 0, "highlightthickness": 1, "highlightbackground": THEME["border"]}
    options.update(kwargs)
    return tk.Frame(parent, **options)


def make_label(parent, text="", style="body", **kwargs):
    font = {"body": FONT_BODY, "small": FONT_SMALL, "title": FONT_TITLE}.get(style, FONT_BODY)
    options = {"bg": THEME["bg"], "fg": THEME["text"], "font": font}
    options.update(kwargs)
    return tk.Label(parent, text=text, **options)


def install_runtime_globals(namespace):
    globals().update(namespace)
