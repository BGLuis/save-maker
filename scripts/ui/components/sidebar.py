#!/usr/bin/env python3
"""
Sidebar component for Save Maker.
Barra lateral fixa com navegação em seções, status do arquivo, status do BD e troca de tema.
Fiel ao Figma Save Maker (nó #5:98).
"""

from typing import Dict, Optional, Callable, Any
from pathlib import Path
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_TEXT, BG_SIDEBAR, BG_CARD, BG_SUB, BG_ACTIVE,
    TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE, BORDER_COLOR,
    SUCCESS_COLOR, WARNING_COLOR, get_ui_font, get_mono_font, get_icon
)

class Sidebar(ctk.CTkFrame):
    """Navegação lateral fixa com hierarquia visual moderna."""

    def __init__(self, master, on_navigate: Callable[[str], None], on_theme_toggle: Callable[[], None], on_select_db_dir: Callable[[], None], **kwargs):
        super().__init__(master, width=250, fg_color=BG_SIDEBAR, corner_radius=0, border_width=1, border_color=BORDER_COLOR, **kwargs)
        self.pack_propagate(False)
        self.on_navigate = on_navigate
        self.on_theme_toggle = on_theme_toggle
        self.on_select_db_dir = on_select_db_dir

        self.current_area: str = "overview"
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}

        self._build_brand()
        self._build_current_file_card()
        self._build_navigation()

        # Espaçador vertical para empurrar o rodapé para baixo
        self.spacer = ctk.CTkFrame(self, fg_color="transparent")
        self.spacer.pack(fill="both", expand=True)

        self._build_footer()

    def _build_brand(self):
        """Cabeçalho com logo e nome do aplicativo."""
        brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        brand_frame.pack(fill="x", padx=16, pady=(18, 14))

        # Logo tile dourado com ícone
        logo_tile = ctk.CTkFrame(
            brand_frame, width=32, height=32, corner_radius=8,
            fg_color=PRIMARY_COLOR
        )
        logo_tile.pack(side="left", padx=(0, 10))
        logo_tile.pack_propagate(False)

        logo_icon = get_icon("sword", size=(16, 16), tint="#0B0C10")
        if logo_icon:
            lbl_logo = ctk.CTkLabel(logo_tile, text="", image=logo_icon)
        else:
            lbl_logo = ctk.CTkLabel(
                logo_tile, text="SM", font=get_ui_font(13, "bold"),
                text_color=PRIMARY_TEXT
            )
        lbl_logo.pack(expand=True)

        # Textos de título
        title_box = ctk.CTkFrame(brand_frame, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        lbl_title = ctk.CTkLabel(
            title_box, text="Save Maker", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            title_box, text="RPG Maker MV / MZ", font=get_ui_font(11),
            text_color=TEXT_MUTED, anchor="w"
        )
        lbl_sub.pack(anchor="w")

    def _build_current_file_card(self):
        """Card exibindo o arquivo atualmente carregado e seus badges."""
        self.file_card = ctk.CTkFrame(
            self, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.file_card.pack(fill="x", padx=14, pady=(0, 14))

        top_row = ctk.CTkFrame(self.file_card, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(8, 4))

        file_icon = get_icon("file", size=(14, 14))
        self.lbl_file_icon = ctk.CTkLabel(
            top_row, text="" if file_icon else "📄", image=file_icon
        )
        self.lbl_file_icon.pack(side="left", padx=(0, 6))

        self.lbl_file_name = ctk.CTkLabel(
            top_row, text="Nenhum save aberto", font=get_mono_font(11, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        )
        self.lbl_file_name.pack(side="left", fill="x", expand=True)

        # Badges (Motor e Compressão)
        self.badges_frame = ctk.CTkFrame(self.file_card, fg_color="transparent")
        self.badges_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.lbl_engine_badge = ctk.CTkLabel(
            self.badges_frame, text="Aguardando", font=get_ui_font(10),
            text_color=TEXT_MUTED, fg_color="transparent",
            corner_radius=4, height=18, padx=6
        )
        self.lbl_engine_badge.pack(side="left", padx=(0, 4))

        self.lbl_compress_badge = ctk.CTkLabel(
            self.badges_frame, text="", font=get_ui_font(10),
            text_color=TEXT_MUTED, fg_color="transparent",
            corner_radius=4, height=18, padx=4
        )
        self.lbl_compress_badge.pack(side="left")

    def _build_navigation(self):
        """Constrói as seções de navegação Início, Editar e Avançado."""
        # Seção Início
        self._add_nav_heading("INÍCIO")
        self._add_nav_item("library", "Biblioteca", "library", "0")

        # Seção Editar
        self._add_nav_heading("EDITAR")
        self._add_nav_item("overview", "Visão geral", "dashboard", "Ctrl 1")
        self._add_nav_item("actors", "Personagens", "users", "Ctrl 2")
        self._add_nav_item("inventory", "Inventário", "package", "Ctrl 3")
        self._add_nav_item("switches", "Switches & variáveis", "toggle", "Ctrl 4")

        # Seção Avançado
        self._add_nav_heading("AVANÇADO")
        self._add_nav_item("advanced", "Árvore JSON", "braces", "Ctrl 5")

    def _add_nav_heading(self, title: str):
        lbl = ctk.CTkLabel(
            self, text=title, font=get_ui_font(10, "bold"),
            text_color=TEXT_SUBTLE, anchor="w"
        )
        lbl.pack(fill="x", padx=16, pady=(10, 4))

    def _add_nav_item(self, area_id: str, label: str, icon_name: str, shortcut: str):
        icon = get_icon(icon_name, size=(16, 16))
        
        btn = ctk.CTkButton(
            self, text=f"   {label}", image=icon, compound="left",
            font=get_ui_font(13), anchor="w", fg_color="transparent",
            hover_color=BG_SUB, text_color=TEXT_MUTED, height=36,
            corner_radius=6, command=lambda: self.select_area(area_id)
        )
        btn.pack(fill="x", padx=10, pady=1)

        self.nav_buttons[area_id] = btn

    def select_area(self, area_id: str, notify: bool = True):
        """Altera a área de navegação selecionada."""
        self.current_area = area_id
        for aid, btn in self.nav_buttons.items():
            if aid == area_id:
                btn.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED)

        if notify and self.on_navigate:
            self.on_navigate(area_id)

    def update_file_status(self, filename: Optional[str], engine: str = "", compression: str = ""):
        """Atualiza o card do arquivo com o nome, motor e compressão."""
        if not filename:
            self.lbl_file_name.configure(text="Nenhum save aberto")
            self.lbl_engine_badge.configure(text="Aguardando", text_color=TEXT_MUTED)
            self.lbl_compress_badge.configure(text="")
            return

        self.lbl_file_name.configure(text=filename)
        self.lbl_engine_badge.configure(
            text=engine or "RPG Maker",
            text_color=SUCCESS_COLOR[1]
        )
        if compression:
            self.lbl_compress_badge.configure(
                text=compression,
                text_color=TEXT_MUTED
            )
        else:
            self.lbl_compress_badge.configure(text="")

    def update_library_count(self, count: int):
        """Atualiza a contagem exibida no botão da biblioteca."""
        if "library" in self.nav_buttons:
            self.nav_buttons["library"].configure(text=f"   Biblioteca ({count})")

    def _build_footer(self):
        """Rodapé da Sidebar com status do banco de dados e controle de tema."""
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(fill="x", padx=12, pady=(0, 14), side="bottom")

        # Card status do banco de dados
        self.db_card = ctk.CTkFrame(
            footer_frame, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.db_card.pack(fill="x", pady=(0, 10))

        db_top = ctk.CTkFrame(self.db_card, fg_color="transparent")
        db_top.pack(fill="x", padx=8, pady=(8, 2))

        db_icon = get_icon("database", size=(14, 14))
        lbl_db_icon = ctk.CTkLabel(db_top, text="" if db_icon else "🗄", image=db_icon)
        lbl_db_icon.pack(side="left", padx=(0, 4))

        self.lbl_db_title = ctk.CTkLabel(
            db_top, text="Banco de dados", font=get_ui_font(11, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        )
        self.lbl_db_title.pack(side="left", fill="x", expand=True)

        self.btn_db_change = ctk.CTkButton(
            db_top, text="Pasta…", width=50, height=20,
            font=get_ui_font(10), fg_color="transparent",
            hover_color=BG_ACTIVE, border_width=1, border_color=BORDER_COLOR,
            command=self.on_select_db_dir
        )
        self.btn_db_change.pack(side="right")

        self.lbl_db_status = ctk.CTkLabel(
            self.db_card, text="Não conectado", font=get_ui_font(10),
            text_color=TEXT_MUTED, anchor="w"
        )
        self.lbl_db_status.pack(fill="x", padx=8, pady=(0, 8))

        # Controle de Tema (Dark / Light)
        theme_row = ctk.CTkFrame(footer_frame, fg_color="transparent")
        theme_row.pack(fill="x", padx=4)

        moon_icon = get_icon("moon", size=(14, 14))
        self.lbl_theme_icon = ctk.CTkLabel(theme_row, text="" if moon_icon else "🌙", image=moon_icon)
        self.lbl_theme_icon.pack(side="left", padx=(0, 6))

        self.lbl_theme_text = ctk.CTkLabel(
            theme_row, text="Tema escuro", font=get_ui_font(12),
            text_color=TEXT_MAIN
        )
        self.lbl_theme_text.pack(side="left")

        self.theme_btn = ctk.CTkButton(
            theme_row, text="Alternar", width=64, height=24,
            font=get_ui_font(10), fg_color=BG_SUB, hover_color=BG_ACTIVE,
            text_color=TEXT_MAIN, border_width=1, border_color=BORDER_COLOR,
            command=self._handle_theme_toggle
        )
        self.theme_btn.pack(side="right")

    def _handle_theme_toggle(self):
        if self.on_theme_toggle:
            self.on_theme_toggle()

    def update_theme_ui(self, appearance_mode: str):
        """Atualiza os textos e ícones do tema conforme o modo ativo."""
        is_dark = appearance_mode.lower() == "dark"
        icon_name = "moon" if is_dark else "sun"
        new_icon = get_icon(icon_name, size=(14, 14))
        if new_icon:
            self.lbl_theme_icon.configure(image=new_icon, text="")
        else:
            self.lbl_theme_icon.configure(text="🌙" if is_dark else "☀️")
        self.lbl_theme_text.configure(text="Tema escuro" if is_dark else "Tema claro")

    def update_database_status(self, is_loaded: bool, summary: str = ""):
        """Atualiza as informações de status da base de dados do jogo."""
        if is_loaded:
            self.lbl_db_title.configure(text="BD Conectado", text_color=SUCCESS_COLOR[1])
            self.lbl_db_status.configure(text=summary or "data/ carregada")
        else:
            self.lbl_db_title.configure(text="BD Desconectado", text_color=TEXT_MUTED)
            self.lbl_db_status.configure(text="Detectado ao abrir save")
