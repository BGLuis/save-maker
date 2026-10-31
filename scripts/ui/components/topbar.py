#!/usr/bin/env python3
"""
Topbar component for Save Maker.
Barra superior com hierarquia visual: título da tela, busca global (Ctrl+K),
indicador de alterações não salvas, botão Desfazer (Ctrl+Z), Exportar JSON e Salvar Dourado.
Fiel ao Figma Save Maker (nó #5:199 e #5:1850).
"""

from typing import Optional, Callable
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    BG_SIDEBAR, BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, SUCCESS_COLOR, WARNING_COLOR, WARNING_BG,
    get_ui_font, get_mono_font, get_icon
)


class Topbar(ctk.CTkFrame):
    """Barra superior com ações principais e controle de estado do save (56px)."""

    def __init__(
        self,
        master,
        on_save: Callable[[], None],
        on_export_json: Callable[[], None],
        on_undo: Callable[[], None],
        on_search_change: Callable[[str], None],
        **kwargs
    ):
        super().__init__(
            master, height=56, fg_color=BG_SIDEBAR, corner_radius=0,
            border_width=1, border_color=BORDER_COLOR, **kwargs
        )
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
        self.lbl_title.pack(side="left", padx=(24, 12), pady=11)

        # Botões e Ações Principais à Direita
        right_container = ctk.CTkFrame(self, fg_color="transparent")
        right_container.pack(side="right", padx=(10, 24), pady=11)

        # Botão Primário Dourado: SALVAR (#5:220)
        save_icon = get_icon("save", size=(15, 15), tint="#1A1408")
        self.btn_save = ctk.CTkButton(
            right_container, text=" Salvar", image=save_icon, compound="left",
            width=96, height=34, font=get_ui_font(13, "bold"),
            fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER,
            text_color=PRIMARY_TEXT, corner_radius=6, command=self.on_save
        )
        self.btn_save.pack(side="right", padx=(8, 0))

        # Botão Secundário: EXPORTAR JSON (#5:216)
        export_icon = get_icon("download", size=(14, 14))
        self.btn_export = ctk.CTkButton(
            right_container, text=" Exportar JSON", image=export_icon, compound="left",
            width=126, height=34, font=get_ui_font(13, "bold"),
            fg_color=BG_SUB, hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR,
            corner_radius=6, command=self.on_export_json
        )
        self.btn_export.pack(side="right", padx=6)

        # Botão Secundário: DESFAZER (Ctrl Z) (#5:212)
        undo_icon = get_icon("undo", size=(14, 14))
        self.btn_undo = ctk.CTkButton(
            right_container, text=" Desfazer", image=undo_icon, compound="left",
            width=98, height=34, font=get_ui_font(13, "bold"),
            fg_color=BG_SUB, hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER_COLOR,
            corner_radius=6, command=self.on_undo, state="disabled"
        )
        self.btn_undo.pack(side="right", padx=6)

        # Indicador de Alterações Não Salvas (Dirty pill badge #5:208)
        self.dirty_badge = ctk.CTkFrame(
            right_container, fg_color="transparent", corner_radius=999, height=24
        )
        self.dirty_badge.pack(side="right", padx=(0, 8))

        self.lbl_dirty_dot = ctk.CTkLabel(
            self.dirty_badge, text="✓", font=get_ui_font(11, "bold"),
            text_color=SUCCESS_COLOR[1]
        )
        self.lbl_dirty_dot.pack(side="left", padx=(8, 4), pady=2)

        self.lbl_dirty_text = ctk.CTkLabel(
            self.dirty_badge, text="Salvo", font=get_ui_font(11, "bold"),
            text_color=SUCCESS_COLOR[1]
        )
        self.lbl_dirty_text.pack(side="left", padx=(0, 8), pady=2)

        # Campo de Busca Global (#5:201)
        self.search_container = ctk.CTkFrame(
            self, height=34, fg_color=BG_SUB, corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE
        )
        self.search_container.pack(side="left", padx=10, pady=11)

        search_icon = get_icon("search", size=(14, 14))
        lbl_search_icon = ctk.CTkLabel(
            self.search_container, text="" if search_icon else "🔍", image=search_icon
        )
        lbl_search_icon.pack(side="left", padx=(10, 4))

        self.entry_search = ctk.CTkEntry(
            self.search_container, placeholder_text="Buscar no save…",
            width=190, height=30, font=get_ui_font(13),
            fg_color="transparent", border_width=0, text_color=TEXT_MAIN
        )
        self.entry_search.pack(side="left", fill="both", expand=True)
        self.entry_search.bind("<KeyRelease>", self._handle_search)

        # Kbd indicator "Ctrl K"
        self.kbd_frame = ctk.CTkFrame(
            self.search_container, fg_color=BG_ACTIVE, corner_radius=4,
            border_width=1, border_color=BORDER_COLOR, height=20
        )
        self.kbd_frame.pack(side="right", padx=(4, 8), pady=5)
        lbl_kbd = ctk.CTkLabel(
            self.kbd_frame, text="Ctrl K", font=get_mono_font(11),
            text_color=TEXT_MUTED, padx=5
        )
        lbl_kbd.pack()

    def set_title(self, title: str):
        self.lbl_title.configure(text=title)

    def focus_search(self):
        """Foca no campo de busca global ao pressionar Ctrl+K."""
        self.entry_search.focus_set()
        try:
            self.entry_search.select_range(0, "end")
        except Exception:
            pass

    def set_save_loaded(self, has_save: bool):
        """Ajusta os controles da barra superior quando há ou não um save carregado."""
        if has_save:
            self.btn_save.configure(state="normal", fg_color=PRIMARY_COLOR, text_color=PRIMARY_TEXT)
            self.btn_export.configure(state="normal")
        else:
            self.btn_save.configure(state="disabled", fg_color=BG_ACTIVE, text_color=TEXT_SUBTLE)
            self.btn_export.configure(state="disabled")
            self.set_dirty_status(False, 0)

    def set_dirty_status(self, is_dirty: bool, changes_count: int = 0):
        if is_dirty:
            txt = (
                f"{changes_count} alteração não salva"
                if changes_count == 1
                else f"{changes_count} alterações não salvas"
            )
            self.lbl_dirty_dot.configure(text="●", text_color=WARNING_COLOR)
            self.lbl_dirty_text.configure(text=txt, text_color=WARNING_COLOR)
            self.dirty_badge.configure(fg_color=WARNING_BG, border_width=1, border_color=WARNING_COLOR)
        else:
            self.lbl_dirty_dot.configure(text="✓", text_color=SUCCESS_COLOR)
            self.lbl_dirty_text.configure(text="Salvo", text_color=SUCCESS_COLOR)
            self.dirty_badge.configure(fg_color="transparent", border_width=0)

    def update_undo_state(self, can_undo: bool, last_action_desc: Optional[str] = None):
        if can_undo:
            self.btn_undo.configure(state="normal", text_color=TEXT_MAIN)
        else:
            self.btn_undo.configure(state="disabled", text_color=TEXT_MUTED)

    def _handle_search(self, event=None):
        if self.on_search_change:
            text = self.entry_search.get()
            self.on_search_change(text)
