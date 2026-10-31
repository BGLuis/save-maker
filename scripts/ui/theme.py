#!/usr/bin/env python3
"""
Theme definitions and color palettes for the modern CustomTkinter interface.
Mapeamento 1:1 dos tokens de design extraídos do Figma Save Maker.
"""

from typing import Tuple, Optional, Dict
import os
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import customtkinter as ctk
from PIL import Image

# Acento Primário: Ouro / Dourado (Figma #E9B44C dark / #B7801A light)
PRIMARY_COLOR = ("#B7801A", "#E9B44C")
PRIMARY_HOVER = ("#9A6915", "#D8A23B")
PRIMARY_TEXT = ("#FFFFFF", "#1A1408")

# Semântica de Sucesso (Verde #3FCF8E)
SUCCESS_COLOR = ("#1E9E66", "#3FCF8E")
SUCCESS_HOVER = ("#178253", "#2BB882")
SUCCESS_BG = ("#E8F7F0", "#142D23")

# Semântica de Perigo / HP (Vermelho Coral #F2706B)
DANGER_COLOR = ("#D64545", "#F2706B")
DANGER_HOVER = ("#BF3939", "#EF4444")
DANGER_BG = ("#FCEBEB", "#2D181A")

# Semântica de Aviso / Destaque Dourado
WARNING_COLOR = ("#B7801A", "#E9B44C")
WARNING_HOVER = ("#9A6915", "#D8A23B")
WARNING_BG = ("#FBF3E0", "#2A2418")

# Semântica de Informação / MP (Azul #6E8BFF)
INFO_COLOR = ("#3B5BDB", "#6E8BFF")
INFO_BG = ("#EAEFFD", "#192038")

# Cores dedicadas para Barras de Recursos (HP / MP / TP)
HP_COLOR = ("#D64545", "#F2706B")
MP_COLOR = ("#3B5BDB", "#6E8BFF")
TP_COLOR = ("#1E9E66", "#3FCF8E")

# Backgrounds (Figma Light #F4F2EE / #FAF8F4 / #EFECE6 e Dark #0B0C10 / #14161C / #1B1E26 / #232733)
BG_CANVAS_LIGHT = "#F4F2EE"
BG_CANVAS_DARK = "#0B0C10"
BG_CANVAS = (BG_CANVAS_LIGHT, BG_CANVAS_DARK)

BG_SIDEBAR_LIGHT = "#FAF8F4"
BG_SIDEBAR_DARK = "#14161C"
BG_SIDEBAR = (BG_SIDEBAR_LIGHT, BG_SIDEBAR_DARK)

BG_CARD_LIGHT = "#FFFFFF"
BG_CARD_DARK = "#14161C"
BG_CARD = (BG_CARD_LIGHT, BG_CARD_DARK)

BG_SUB_LIGHT = "#FAF8F4"
BG_SUB_DARK = "#1B1E26"
BG_SUB = (BG_SUB_LIGHT, BG_SUB_DARK)

BG_ACTIVE_LIGHT = "#EFECE6"
BG_ACTIVE_DARK = "#232733"
BG_ACTIVE = (BG_ACTIVE_LIGHT, BG_ACTIVE_DARK)

# Textos
TEXT_MAIN = ("#16171C", "#ECEEF3")
TEXT_MUTED = ("#5B606C", "#9AA0AE")
TEXT_SUBTLE = ("#8A8F99", "#6B7180")

# Bordas
BORDER_COLOR = ("#E4E0D8", "#262A35")
BORDER_SUBTLE = ("#D3CEC4", "#353A48")

# Cache de fontes detectadas
_BEST_UI_FAMILY: Optional[str] = None
_BEST_MONO_FAMILY: Optional[str] = None

def _resolve_font_families():
    global _BEST_UI_FAMILY, _BEST_MONO_FAMILY
    if _BEST_UI_FAMILY and _BEST_MONO_FAMILY:
        return

    try:
        root = tk._default_root
        if root is None:
            # Não inicializar root aqui se não houver; usar fallbacks
            _BEST_UI_FAMILY = "DejaVu Sans"
            _BEST_MONO_FAMILY = "JetBrains Mono"
            return
        available = set(tkfont.families(root))
    except Exception:
        available = set()

    for cand in ("Geist", "Inter", "DejaVu Sans", "Roboto", "Segoe UI", "Helvetica Neue", "Arial"):
        if cand in available:
            _BEST_UI_FAMILY = cand
            break
    if not _BEST_UI_FAMILY:
        _BEST_UI_FAMILY = "DejaVu Sans"

    for cand in ("JetBrains Mono", "Fira Code", "DejaVu Sans Mono", "Consolas", "Courier New"):
        if cand in available:
            _BEST_MONO_FAMILY = cand
            break
    if not _BEST_MONO_FAMILY:
        _BEST_MONO_FAMILY = "JetBrains Mono"

def get_ui_font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    """Retorna a fonte padrão da interface com fallbacks seguros."""
    _resolve_font_families()
    return ctk.CTkFont(family=_BEST_UI_FAMILY, size=size, weight=weight)

def get_mono_font(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    """Retorna a fonte monospace para números, IDs e caminhos."""
    _resolve_font_families()
    return ctk.CTkFont(family=_BEST_MONO_FAMILY, size=size, weight=weight)

def init_draw_engine():
    """
    Configura o motor de desenho do CustomTkinter para garantir cantos lisos
    e livres de artefatos mesmo em ambientes X11/Wayland sem suporte total a fontes.
    """
    try:
        root = tk._default_root
        if root is not None:
            families = set(tkfont.families(root))
            if "CustomTkinter_shapes_font" not in families:
                ctk.DrawEngine.preferred_drawing_method = "circle_shapes"
    except Exception:
        pass


# Cache de ícones carregados por root ativo
_ICON_CACHE: Dict[Tuple[int, str, Tuple[int, int], Optional[str]], ctk.CTkImage] = {}

def _tint_image(img: Image.Image, color_hex: str) -> Image.Image:
    """Aplica uma cor sólida preservando o canal alfa."""
    color_hex = color_hex.lstrip("#")
    if len(color_hex) == 6:
        r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
    else:
        r, g, b = (255, 255, 255)
    
    alpha = img.split()[-1]
    colored = Image.new("RGBA", img.size, (r, g, b, 255))
    colored.putalpha(alpha)
    return colored

def get_icon(name: str, size: Tuple[int, int] = (16, 16), tint: Optional[str] = None) -> Optional[ctk.CTkImage]:
    """
    Retorna uma instância de CTkImage baseada no ícone oficial do Figma.
    Gera automaticamente versões nítidas para modo claro e escuro.
    Isola a instância do cache por intérprete Tk ativo para evitar conflitos de ciclo de vida.
    """
    root_id = id(tk._default_root) if tk._default_root is not None else 0
    cache_key = (root_id, name, size, tint)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icons", f"{name}.png")
    if not os.path.exists(icon_path):
        # Fallback para o diretório icons/ na raiz se assets/icons não for encontrado
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "icons", f"{name}.png")
        if not os.path.exists(icon_path):
            return None

    try:
        base_img = Image.open(icon_path).convert("RGBA")
        
        if tint:
            # Cor fixa para ambos os modos
            tinted = _tint_image(base_img, tint)
            ctk_img = ctk.CTkImage(light_image=tinted, dark_image=tinted, size=size)
        else:
            # Modo padrão: escuro no tema light, claro no tema dark
            light_img = _tint_image(base_img, TEXT_MAIN[0])   # #111318
            dark_img = _tint_image(base_img, TEXT_MAIN[1])    # #F0F2F5
            ctk_img = ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=size)

        _ICON_CACHE[cache_key] = ctk_img
        return ctk_img
    except Exception as e:
        return None


def setup_treeview_styles(mode: str = "dark"):
    """
    Configura a aparência das tabelas ttk.Treeview com base no modo dark/light.
    Garante legibilidade, espaçamento confortável e alinhamento visual com o Figma.
    """
    style = ttk.Style()
    style.theme_use("default")

    if mode == "dark":
        bg_main = BG_CARD_DARK
        fg_main = TEXT_MAIN[1]
        bg_alt = BG_SUB_DARK
        bg_selected = BG_ACTIVE_DARK
        border_col = BORDER_COLOR[1]
        heading_bg = BG_SUB_DARK
        heading_fg = TEXT_MUTED[1]
    else:
        bg_main = BG_CARD_LIGHT
        fg_main = TEXT_MAIN[0]
        bg_alt = BG_SUB_LIGHT
        bg_selected = BG_ACTIVE_LIGHT
        border_col = BORDER_COLOR[0]
        heading_bg = BG_SUB_LIGHT
        heading_fg = TEXT_MUTED[0]

    _resolve_font_families()
    font_body = (_BEST_UI_FAMILY, 10)
    font_head = (_BEST_UI_FAMILY, 10, "bold")

    style.configure(
        "Treeview",
        background=bg_main,
        foreground=fg_main,
        fieldbackground=bg_main,
        borderwidth=0,
        highlightthickness=0,
        rowheight=32,
        font=font_body
    )

    style.map(
        "Treeview",
        background=[("selected", bg_selected)],
        foreground=[("selected", fg_main)]
    )

    style.configure(
        "Treeview.Heading",
        background=heading_bg,
        foreground=heading_fg,
        relief="flat",
        font=font_head,
        padding=(8, 6)
    )

    style.map(
        "Treeview.Heading",
        background=[("active", bg_selected)]
    )
