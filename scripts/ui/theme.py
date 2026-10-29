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

# Acento Primário: Ouro / Dourado
PRIMARY_COLOR = ("#B7801A", "#E2B342")        # Gold dark/light accent
PRIMARY_HOVER = ("#9A6915", "#F0C155")
PRIMARY_TEXT = ("#FFFFFF", "#0B0C10")

# Semântica de Sucesso (Verde)
SUCCESS_COLOR = ("#1E9E66", "#34D399")
SUCCESS_HOVER = ("#178253", "#2BB882")
SUCCESS_BG = ("#E8F7F0", "#132B1E")

# Semântica de Perigo (Vermelho)
DANGER_COLOR = ("#D64545", "#F87171")
DANGER_HOVER = ("#BF3939", "#EF4444")
DANGER_BG = ("#FCEBEB", "#3A181C")

# Semântica de Aviso / Destaque Dourado
WARNING_COLOR = ("#B7801A", "#FBBF24")
WARNING_HOVER = ("#9A6915", "#F59E0B")
WARNING_BG = ("#F9F4E8", "#2E2310")

# Semântica de Informação (Azul)
INFO_COLOR = ("#2563EB", "#60A5FA")
INFO_BG = ("#EFF6FF", "#14253D")

# Backgrounds
BG_CANVAS_LIGHT = "#F6F7F9"
BG_CANVAS_DARK = "#0B0C10"
BG_CANVAS = (BG_CANVAS_LIGHT, BG_CANVAS_DARK)

BG_SIDEBAR_LIGHT = "#FFFFFF"
BG_SIDEBAR_DARK = "#0F1117"
BG_SIDEBAR = (BG_SIDEBAR_LIGHT, BG_SIDEBAR_DARK)

BG_CARD_LIGHT = "#FFFFFF"
BG_CARD_DARK = "#14161C"
BG_CARD = (BG_CARD_LIGHT, BG_CARD_DARK)

BG_SUB_LIGHT = "#F1F3F6"
BG_SUB_DARK = "#1A1D24"
BG_SUB = (BG_SUB_LIGHT, BG_SUB_DARK)

BG_ACTIVE_LIGHT = "#E8ECF2"
BG_ACTIVE_DARK = "#1E222B"
BG_ACTIVE = (BG_ACTIVE_LIGHT, BG_ACTIVE_DARK)

# Textos
TEXT_MAIN = ("#111318", "#F0F2F5")
TEXT_MUTED = ("#636B78", "#8C93A0")
TEXT_SUBTLE = ("#949CA9", "#5A6170")

# Bordas
BORDER_COLOR = ("#E2E5EA", "#232730")
BORDER_SUBTLE = ("#CBD0D8", "#2E333F")

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
