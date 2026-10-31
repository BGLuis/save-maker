#!/usr/bin/env python3
"""
Sidebar component for Save Maker.
Barra lateral fixa com navegação em seções, status do arquivo, status do BD e troca de tema.
Fiel ao Figma Save Maker (nó #5:98 e #5:1812).
"""

from typing import Dict, Optional, Callable
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_TEXT, BG_SIDEBAR, BG_CARD, BG_SUB, BG_ACTIVE,
    TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE, BORDER_COLOR, BORDER_SUBTLE,
    SUCCESS_COLOR, SUCCESS_BG, WARNING_COLOR, WARNING_BG,
    get_ui_font, get_mono_font, get_icon
)


class Sidebar(ctk.CTkFrame):
    """Navegação lateral fixa com hierarquia visual moderna (272px)."""

    def __init__(
        self,
        master,
        on_navigate: Callable[[str], None],
        on_theme_toggle: Callable[[], None],
        on_select_db_dir: Callable[[], None],
        on_open_file: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(
            master, width=272, fg_color=BG_SIDEBAR, corner_radius=0,
            border_width=1, border_color=BORDER_COLOR, **kwargs
        )
        self.pack_propagate(False)
        self.on_navigate = on_navigate
        self.on_theme_toggle = on_theme_toggle
        self.on_select_db_dir = on_select_db_dir
        self.on_open_file = on_open_file

        self.current_area: str = "overview"
        self.has_save_loaded: bool = False
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        self.nav_shortcuts: Dict[str, ctk.CTkLabel] = {}

        self._build_brand()
        self._build_current_file_card()
        self._build_navigation()

        # Espaçador vertical para empurrar o rodapé para baixo
        self.spacer = ctk.CTkFrame(self, fg_color="transparent")
        self.spacer.pack(fill="both", expand=True)

        self._build_footer()

    def _build_brand(self):
        """Cabeçalho com logo 'S' dourado e nome do aplicativo (#5:100)."""
        brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        brand_frame.pack(fill="x", padx=14, pady=(14, 12))

        # Logo tile dourado 32x32 com letra "S"
        logo_tile = ctk.CTkFrame(
            brand_frame, width=32, height=32, corner_radius=8,
            fg_color=PRIMARY_COLOR
        )
        logo_tile.pack(side="left", padx=(0, 10))
        logo_tile.pack_propagate(False)

        lbl_logo = ctk.CTkLabel(
            logo_tile, text="S", font=get_ui_font(15, "bold"),
            text_color=PRIMARY_TEXT
        )
        lbl_logo.pack(expand=True)

        # Textos de título
        title_box = ctk.CTkFrame(brand_frame, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        lbl_title = ctk.CTkLabel(
            title_box, text="Save Maker", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            title_box, text="Editor de saves", font=get_ui_font(11),
            text_color=TEXT_SUBTLE, anchor="w"
        )
        lbl_sub.pack(anchor="w")

    def _build_current_file_card(self):
        """Card exibindo o arquivo atualmente carregado e seus badges (#5:105)."""
        self.file_card = ctk.CTkFrame(
            self, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.file_card.pack(fill="x", padx=14, pady=(0, 12))

        self.file_top_row = ctk.CTkFrame(self.file_card, fg_color="transparent")
        self.file_top_row.pack(fill="x", padx=10, pady=(8, 8))

        file_icon = get_icon("file", size=(14, 14))
        self.lbl_file_icon = ctk.CTkLabel(
            self.file_top_row, text="" if file_icon else "📄", image=file_icon
        )
        self.lbl_file_icon.pack(side="left", padx=(0, 8))

        self.lbl_file_name = ctk.CTkLabel(
            self.file_top_row, text="Nenhum save aberto", font=get_mono_font(12, "bold"),
            text_color=TEXT_MUTED, anchor="w"
        )
        self.lbl_file_name.pack(side="left", fill="x", expand=True)

        chevron_icon = get_icon("chevron-down", size=(14, 14))
        self.lbl_file_chevron = ctk.CTkLabel(
            self.file_top_row, text="" if chevron_icon else "▾", image=chevron_icon,
            cursor="hand2"
        )
        self.lbl_file_chevron.pack(side="right", padx=(4, 0))

        for w in (self.file_card, self.file_top_row, self.lbl_file_icon, self.lbl_file_name, self.lbl_file_chevron):
            w.bind("<Button-1>", self._handle_file_card_click)

        # Badges (Motor e Compressão) - inicialmente ocultos quando nenhum save aberto
        self.badges_frame = ctk.CTkFrame(self.file_card, fg_color="transparent")

        self.lbl_engine_badge = ctk.CTkLabel(
            self.badges_frame, text="● RPG Maker MV", font=get_ui_font(11, "bold"),
            text_color=PRIMARY_COLOR, fg_color=WARNING_BG,
            corner_radius=999, height=20, padx=8
        )
        self.lbl_engine_badge.pack(side="left", padx=(0, 6))

        self.lbl_compress_badge = ctk.CTkLabel(
            self.badges_frame, text="LZString", font=get_ui_font(11, "bold"),
            text_color=TEXT_MUTED, fg_color=BG_ACTIVE,
            corner_radius=999, height=20, padx=8
        )
        self.lbl_compress_badge.pack(side="left")

    def _handle_file_card_click(self, event=None):
        if self.on_open_file:
            self.on_open_file()

    def _build_navigation(self):
        """Constrói as seções de navegação Início, Editar e Avançado (#5:121)."""
        # Seção Início
        self._add_nav_heading("INÍCIO")
        self._add_nav_item("library", "Biblioteca", "library", "Ctrl 0")

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
        lbl.pack(fill="x", padx=20, pady=(10, 4))

    def _add_nav_item(self, area_id: str, label: str, icon_name: str, shortcut: str):
        icon = get_icon(icon_name, size=(16, 16))

        btn = ctk.CTkButton(
            self, text=f"  {label}", image=icon, compound="left",
            font=get_ui_font(13), anchor="w", fg_color="transparent",
            hover_color=BG_SUB, text_color=TEXT_MUTED, height=34,
            corner_radius=6, command=lambda: self.select_area(area_id)
        )
        btn.pack(fill="x", padx=14, pady=1)

        lbl_sc = ctk.CTkLabel(
            btn, text=shortcut, font=get_mono_font(11),
            text_color=TEXT_SUBTLE, fg_color="transparent", height=20
        )
        lbl_sc.place(relx=1.0, rely=0.5, x=-10, anchor="e")
        lbl_sc.bind("<Button-1>", lambda e: self.select_area(area_id))

        self.nav_buttons[area_id] = btn
        self.nav_shortcuts[area_id] = lbl_sc

    def select_area(self, area_id: str, notify: bool = True):
        """Altera a área de navegação selecionada."""
        self.current_area = area_id
        for aid, btn in self.nav_buttons.items():
            sc_lbl = self.nav_shortcuts.get(aid)
            if aid == area_id:
                btn.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN, font=get_ui_font(13, "bold"))
                if sc_lbl:
                    sc_lbl.configure(fg_color=BG_ACTIVE, text_color=TEXT_MUTED)
            else:
                dimmed = (not self.has_save_loaded) and (aid != "library")
                t_col = TEXT_SUBTLE if dimmed else TEXT_MUTED
                btn.configure(fg_color="transparent", text_color=t_col, font=get_ui_font(13))
                if sc_lbl:
                    sc_lbl.configure(fg_color="transparent", text_color=TEXT_SUBTLE)

        if notify and self.on_navigate:
            self.on_navigate(area_id)

    def update_file_status(self, filename: Optional[str], engine: str = "", compression: str = ""):
        """Atualiza o card do arquivo com o nome, motor e compressão."""
        if not filename:
            self.has_save_loaded = False
            self.lbl_file_name.configure(text="Nenhum save aberto", text_color=TEXT_MUTED)
            self.badges_frame.pack_forget()
            self.file_top_row.pack_configure(pady=(8, 8))
            self.select_area(self.current_area, notify=False)
            return

        self.has_save_loaded = True
        self.file_top_row.pack_configure(pady=(8, 4))
        self.lbl_file_name.configure(text=filename, text_color=TEXT_MAIN)

        eng_label = engine or "RPG Maker"
        self.lbl_engine_badge.configure(
            text=f"● {eng_label}",
            text_color=PRIMARY_COLOR,
            fg_color=WARNING_BG
        )
        if compression:
            comp_display = "LZString" if "lzstring" in compression.lower() else compression
            self.lbl_compress_badge.configure(
                text=comp_display,
                text_color=TEXT_MUTED,
                fg_color=BG_ACTIVE
            )
            self.lbl_compress_badge.pack(side="left")
        else:
            self.lbl_compress_badge.pack_forget()

        self.badges_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.select_area(self.current_area, notify=False)

    def update_library_count(self, count: int):
        """Atualiza a contagem exibida no botão da biblioteca."""
        if "library" in self.nav_buttons:
            self.nav_buttons["library"].configure(text=f"  Biblioteca ({count})" if count > 0 else "  Biblioteca")

    def _build_footer(self):
        """Rodapé da Sidebar com status do banco de dados e controle de tema (#5:182)."""
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(fill="x", padx=14, pady=(0, 14), side="bottom")

        # Card status do banco de dados (#5:183 / #5:1840)
        self.db_card = ctk.CTkFrame(
            footer_frame, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR, cursor="hand2"
        )
        self.db_card.pack(fill="x", pady=(0, 10))

        db_top = ctk.CTkFrame(self.db_card, fg_color="transparent")
        db_top.pack(fill="x", padx=10, pady=(8, 2))

        db_icon = get_icon("database", size=(14, 14))
        self.lbl_db_icon = ctk.CTkLabel(db_top, text="" if db_icon else "🗄", image=db_icon)
        self.lbl_db_icon.pack(side="left", padx=(0, 6))

        self.lbl_db_title = ctk.CTkLabel(
            db_top, text="Banco de dados não conectado", font=get_ui_font(12, "bold"),
            text_color=TEXT_MUTED, anchor="w"
        )
        self.lbl_db_title.pack(side="left", fill="x", expand=True)

        self.lbl_db_status = ctk.CTkLabel(
            self.db_card,
            text="Detectado automaticamente ao abrir um save (data/, www/data/).",
            font=get_ui_font(11),
            text_color=TEXT_SUBTLE, anchor="w", justify="left", wraplength=220
        )
        self.lbl_db_status.pack(fill="x", padx=10, pady=(0, 8))

        for w in (self.db_card, db_top, self.lbl_db_icon, self.lbl_db_title, self.lbl_db_status):
            w.bind("<Button-1>", lambda e: self.on_select_db_dir() if self.on_select_db_dir else None)

        # Controle de Tema (Dark / Light) com Toggle Pill (#5:191)
        theme_row = ctk.CTkFrame(footer_frame, fg_color="transparent")
        theme_row.pack(fill="x", padx=6, pady=(2, 0))

        moon_icon = get_icon("moon", size=(14, 14))
        self.lbl_theme_icon = ctk.CTkLabel(theme_row, text="" if moon_icon else "🌙", image=moon_icon)
        self.lbl_theme_icon.pack(side="left", padx=(0, 8))

        self.lbl_theme_text = ctk.CTkLabel(
            theme_row, text="Tema escuro", font=get_ui_font(12),
            text_color=TEXT_MUTED
        )
        self.lbl_theme_text.pack(side="left")

        # Toggle switch pill (36x20) fiel ao Figma (#5:197)
        self.theme_switch_pill = ctk.CTkFrame(
            theme_row, width=36, height=20, corner_radius=10,
            fg_color=PRIMARY_COLOR, cursor="hand2"
        )
        self.theme_switch_pill.pack(side="right")
        self.theme_switch_pill.pack_propagate(False)

        self.theme_knob = ctk.CTkFrame(
            self.theme_switch_pill, width=16, height=16, corner_radius=8,
            fg_color=PRIMARY_TEXT
        )
        self.theme_knob.place(relx=1.0, rely=0.5, x=-2, anchor="e")

        for w in (theme_row, self.lbl_theme_icon, self.lbl_theme_text, self.theme_switch_pill, self.theme_knob):
            w.bind("<Button-1>", lambda e: self._handle_theme_toggle())

    def _handle_theme_toggle(self):
        if self.on_theme_toggle:
            self.on_theme_toggle()

    def update_theme_ui(self, appearance_mode: str):
        """Atualiza os textos, ícone e o toggle switch do tema conforme o modo ativo."""
        is_dark = appearance_mode.lower() == "dark"
        icon_name = "moon" if is_dark else "sun"
        new_icon = get_icon(icon_name, size=(14, 14))
        if new_icon:
            self.lbl_theme_icon.configure(image=new_icon, text="")
        else:
            self.lbl_theme_icon.configure(text="🌙" if is_dark else "☀️")
        self.lbl_theme_text.configure(text="Tema escuro" if is_dark else "Tema claro")

        if is_dark:
            self.theme_switch_pill.configure(fg_color=PRIMARY_COLOR)
            self.theme_knob.place(relx=1.0, rely=0.5, x=-2, anchor="e")
        else:
            self.theme_switch_pill.configure(fg_color=BORDER_SUBTLE)
            self.theme_knob.place(relx=0.0, rely=0.5, x=2, anchor="w")

    def update_database_status(self, is_loaded: bool, summary: str = ""):
        """Atualiza o card de status da base de dados do jogo (#5:183 vs #5:1840)."""
        if is_loaded:
            self.db_card.configure(fg_color=SUCCESS_BG, border_color=SUCCESS_COLOR)
            db_green = get_icon("database", size=(14, 14), tint=SUCCESS_COLOR[1])
            if db_green:
                self.lbl_db_icon.configure(image=db_green)
            self.lbl_db_title.configure(text="Banco de dados conectado", text_color=SUCCESS_COLOR)
            self.lbl_db_status.configure(
                text=summary or "www/data · carregado",
                text_color=TEXT_MUTED
            )
        else:
            self.db_card.configure(fg_color=BG_SUB, border_color=BORDER_COLOR)
            db_muted = get_icon("database", size=(14, 14))
            if db_muted:
                self.lbl_db_icon.configure(image=db_muted)
            self.lbl_db_title.configure(text="Banco de dados não conectado", text_color=TEXT_MUTED)
            self.lbl_db_status.configure(
                text="Detectado automaticamente ao abrir um save (data/, www/data/).",
                text_color=TEXT_SUBTLE
            )
