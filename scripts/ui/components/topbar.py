#!/usr/bin/env python3
"""
Topbar component for Save Maker.
Barra superior com hierarquia visual: título da tela, busca global (Ctrl+K),
indicador de alterações pendentes, botão Desfazer (Ctrl+Z), Exportar e Salvar Dourado.
Fiel ao Figma Save Maker.
"""

from typing import Optional, Callable
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    BG_SIDEBAR, BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, SUCCESS_COLOR, WARNING_COLOR,
    get_ui_font, get_mono_font, get_icon
)

class Topbar(ctk.CTkFrame):
    """Barra superior com ações principais e controle de estado do save."""

    def __init__(
        self, master,
        on_save: Callable[[], None],
        on_export_json: Callable[[], None],
        on_undo: Callable[[], None],
        on_search_change: Callable[[str], None],
        **kwargs
    ):
        super().__init__(master, height=58, fg_color=BG_SIDEBAR, corner_radius=0, border_width=1, border_color=BORDER_COLOR, **kwargs)
        self.pack_propagate(False)

        self.on_save = on_save
        self.on_export_json = on_export_json
        self.on_undo = on_undo
        self.on_search_change = on_search_change

        self._build_ui()

    def _build_ui(self):
        # Título da área ativa à esquerda
        self.lbl_title = ctk.CTkLabel(
            self, text="Visão geral", font=get_ui_font(16, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        )
        self.lbl_title.pack(side="left", padx=(16, 12), pady=11)

        # Botões e Ações Principais à Direita (empacotados primeiro para garantir visibilidade em janelas tiled)
        right_container = ctk.CTkFrame(self, fg_color="transparent")
        right_container.pack(side="right", padx=(10, 16), pady=11)

        # Botão Primário Dourado: SALVAR
        save_icon = get_icon("save", size=(15, 15), tint="#0B0C10")
        self.btn_save = ctk.CTkButton(
            right_container, text=" Salvar", image=save_icon, compound="left",
            width=96, height=34, font=get_ui_font(12, "bold"),
            fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER,
            text_color=PRIMARY_TEXT, corner_radius=6, command=self.on_save
        )
        self.btn_save.pack(side="right", padx=(6, 0))

        # Botão Secundário: EXPORTAR JSON
        export_icon = get_icon("download", size=(14, 14))
        self.btn_export = ctk.CTkButton(
            right_container, text=" Exportar", image=export_icon, compound="left",
            width=100, height=34, font=get_ui_font(12),
            fg_color=BG_SUB, hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR,
            corner_radius=6, command=self.on_export_json
        )
        self.btn_export.pack(side="right", padx=6)

        # Botão Secundário: DESFAZER (Ctrl Z)
        undo_icon = get_icon("undo", size=(14, 14))
        self.btn_undo = ctk.CTkButton(
            right_container, text=" Desfazer", image=undo_icon, compound="left",
            width=96, height=34, font=get_ui_font(12),
            fg_color=BG_SUB, hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER_COLOR,
            corner_radius=6, command=self.on_undo, state="disabled"
        )
        self.btn_undo.pack(side="right", padx=6)

        # Indicador de Alterações Pendentes (Dirty badge)
        self.dirty_badge = ctk.CTkFrame(
            right_container, fg_color="transparent", corner_radius=6, height=30
        )
        self.dirty_badge.pack(side="right", padx=(0, 8))

        self.lbl_dirty_dot = ctk.CTkLabel(
            self.dirty_badge, text="●", font=get_ui_font(11),
            text_color=SUCCESS_COLOR[1]
        )
        self.lbl_dirty_dot.pack(side="left", padx=(6, 4))

        self.lbl_dirty_text = ctk.CTkLabel(
            self.dirty_badge, text="Salvo", font=get_ui_font(11, "bold"),
            text_color=SUCCESS_COLOR[1]
        )
        self.lbl_dirty_text.pack(side="left", padx=(0, 6))

        # Campo de Busca Global (meio)
        self.search_container = ctk.CTkFrame(
            self, height=34, fg_color=BG_SUB, corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE
        )
        self.search_container.pack(side="left", padx=10, pady=11)

        search_icon = get_icon("search", size=(14, 14))
        lbl_search_icon = ctk.CTkLabel(
            self.search_container, text="" if search_icon else "🔍", image=search_icon
        )
        lbl_search_icon.pack(side="left", padx=(8, 4))

        self.entry_search = ctk.CTkEntry(
            self.search_container, placeholder_text="Buscar no save…",
            width=160, height=30, font=get_ui_font(12),
            fg_color="transparent", border_width=0, text_color=TEXT_MAIN
        )
        self.entry_search.pack(side="left", fill="both", expand=True)
        self.entry_search.bind("<KeyRelease>", self._handle_search)

        # Kbd indicator "Ctrl K"
        self.kbd_frame = ctk.CTkFrame(
            self.search_container, fg_color=BG_ACTIVE, corner_radius=4,
            height=20
        )
        self.kbd_frame.pack(side="right", padx=(4, 6), pady=5)
        lbl_kbd = ctk.CTkLabel(
            self.kbd_frame, text="Ctrl K", font=get_mono_font(10),
            text_color=TEXT_MUTED, padx=4
        )
        lbl_kbd.pack()

    def set_title(self, title: str):
        self.lbl_title.configure(text=title)

    def set_dirty_status(self, is_dirty: bool, changes_count: int = 0):
        if is_dirty:
            txt = f"{changes_count} alteração pendente" if changes_count == 1 else f"{changes_count} alterações pendentes"
            self.lbl_dirty_dot.configure(text="●", text_color=WARNING_COLOR[1])
            self.lbl_dirty_text.configure(text=txt, text_color=WARNING_COLOR[1])
            self.dirty_badge.configure(fg_color=BG_SUB)
        else:
            self.lbl_dirty_dot.configure(text="✓", text_color=SUCCESS_COLOR[1])
            self.lbl_dirty_text.configure(text="Salvo", text_color=SUCCESS_COLOR[1])
            self.dirty_badge.configure(fg_color="transparent")

    def update_undo_state(self, can_undo: bool, last_action_desc: Optional[str] = None):
        if can_undo:
            self.btn_undo.configure(state="normal", text_color=TEXT_MAIN)
        else:
            self.btn_undo.configure(state="disabled", text_color=TEXT_MUTED)

    def _handle_search(self, event=None):
        if self.on_search_change:
            text = self.entry_search.get()
            self.on_search_change(text)
