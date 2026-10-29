#!/usr/bin/env python3
"""
Switches & Variables View (Tela 04 do Figma).
Visualização e edição com extração de categorias via prefixo [...],
chips de filtro rápido (Todos, ON, Com nome), alternância via Espaço e edição com Enter.
Fiel ao Figma Save Maker.
"""

from typing import Callable, List, Dict, Any, Optional
import re
import tkinter as tk
from tkinter import ttk, simpledialog
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, WARNING_COLOR, DANGER_COLOR,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)

class SwitchesView(ctk.CTkFrame):
    """Visualização de Switches e Variáveis com categorias e atalhos rápidos."""

    def __init__(
        self, master,
        on_segment_change: Callable[[str], None],
        on_filter_change: Callable[[str], None],
        on_filter_chip: Callable[[str], None],
        on_sort: Callable[[str], None],
        on_select: Callable[[int], None],
        on_toggle_switch: Callable[[], None],
        on_save_var: Callable[[int, Any], None],
        on_turn_off_visible: Callable[[], None],
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_segment_change = on_segment_change
        self.on_filter_change = on_filter_change
        self.on_filter_chip = on_filter_chip
        self.on_sort = on_sort
        self.on_select = on_select
        self.on_toggle_switch = on_toggle_switch
        self.on_save_var = on_save_var
        self.on_turn_off_visible = on_turn_off_visible

        self.current_subtab: str = "switches"
        self._selected_id: Optional[int] = None
        self.active_chip: str = "all"

        self._build_ui()

    def _build_ui(self):
        # 1. Barra Superior com Segmentos e Chips
        top_bar = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        top_bar.pack(fill="x", pady=(0, 10))

        pad_top = ctk.CTkFrame(top_bar, fg_color="transparent")
        pad_top.pack(fill="x", padx=16, pady=10)

        # Segments (Switches / Variáveis)
        seg_box = ctk.CTkFrame(pad_top, fg_color="transparent")
        seg_box.pack(side="left")

        self.seg_btn_switches = ctk.CTkButton(
            seg_box, text="Switches (0)", font=get_ui_font(12, "bold"),
            height=32, corner_radius=6, fg_color=BG_ACTIVE,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            command=lambda: self._select_subtab("switches")
        )
        self.seg_btn_switches.pack(side="left", padx=2)

        self.seg_btn_vars = ctk.CTkButton(
            seg_box, text="Variáveis (0)", font=get_ui_font(12, "bold"),
            height=32, corner_radius=6, fg_color="transparent",
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            command=lambda: self._select_subtab("variables")
        )
        self.seg_btn_vars.pack(side="left", padx=2)

        # Chips de Filtro Rápido (Todos / ON / Com nome)
        chips_box = ctk.CTkFrame(pad_top, fg_color="transparent")
        chips_box.pack(side="left", padx=20)

        self.chip_all = self._create_chip(chips_box, "Todos", "all")
        self.chip_on = self._create_chip(chips_box, "ON", "on")
        self.chip_named = self._create_chip(chips_box, "Com nome", "named")
        self._highlight_active_chip("all")

        # Botão Desligar Visíveis
        zap_ico = get_icon("zap", size=(14, 14), tint="#FBBF24")
        self.btn_turn_off = ctk.CTkButton(
            pad_top, text=" Desligar visíveis", image=zap_ico, compound="left",
            width=134, height=32, font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6, command=self.on_turn_off_visible
        )
        self.btn_turn_off.pack(side="right")

        # Campo de Pesquisa
        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", pady=(0, 8))

        self.entry_filter = ctk.CTkEntry(
            search_row, placeholder_text="Filtrar por nome, ID ou categoria…",
            font=get_ui_font(12), height=32, fg_color=BG_CARD,
            border_color=BORDER_SUBTLE, corner_radius=6
        )
        self.entry_filter.pack(fill="x")
        self.entry_filter.bind("<KeyRelease>", lambda e: self.on_filter_change(self.entry_filter.get()))

        # 2. Container da Tabela Treeview
        table_container = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        table_container.pack(fill="both", expand=True, pady=(0, 10))

        cols = ("id", "name", "val")
        self.tree_sys = ttk.Treeview(
            table_container, columns=cols, show="headings",
            selectmode="browse"
        )

        self.tree_sys.heading("id", text="ID", command=lambda: self.on_sort("id"))
        self.tree_sys.heading("name", text="Nome / Categoria", command=lambda: self.on_sort("name"))
        self.tree_sys.heading("val", text="Estado / Valor", command=lambda: self.on_sort("val"))

        self.tree_sys.column("id", width=80, anchor="center")
        self.tree_sys.column("name", width=480, anchor="w")
        self.tree_sys.column("val", width=180, anchor="center")

        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_sys.yview)
        self.tree_sys.configure(yscrollcommand=scrollbar.set)

        self.tree_sys.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=10)

        # Bindings de Teclado e Seleção
        self.tree_sys.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree_sys.bind("<space>", lambda e: self._handle_space_toggle())
        self.tree_sys.bind("<Return>", lambda e: self._handle_enter_edit())
        self.tree_sys.bind("<Double-1>", lambda e: self._handle_double_click())

        # 3. Rodapé com Instruções de Atalho
        bottom_bar = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=8, height=44,
            border_width=1, border_color=BORDER_COLOR
        )
        bottom_bar.pack(fill="x")
        bottom_bar.pack_propagate(False)

        bot_pad = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        bot_pad.pack(fill="both", expand=True, padx=16, pady=8)

        self.lbl_selected_info = ctk.CTkLabel(
            bot_pad, text="Selecione um item acima",
            font=get_ui_font(12), text_color=TEXT_MUTED
        )
        self.lbl_selected_info.pack(side="left")

        # Dicas de Atalho no Teclado
        hints_box = ctk.CTkFrame(bot_pad, fg_color="transparent")
        hints_box.pack(side="right")

        hints = [
            ("Espaço", "alterna"),
            ("↑ ↓", "navega"),
            ("Enter", "edita")
        ]
        for key, act in hints:
            kbd = ctk.CTkFrame(hints_box, fg_color=BG_SUB, corner_radius=4)
            kbd.pack(side="left", padx=3)
            ctk.CTkLabel(kbd, text=key, font=get_mono_font(10), text_color=TEXT_MAIN, padx=4, pady=1).pack()
            ctk.CTkLabel(hints_box, text=act, font=get_ui_font(11), text_color=TEXT_MUTED).pack(side="left", padx=(0, 8))

    def _create_chip(self, parent, text, chip_id) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            parent, text=text, font=get_ui_font(11), height=28,
            corner_radius=14, fg_color=BG_SUB, hover_color=BG_ACTIVE,
            text_color=TEXT_MUTED, border_width=1, border_color=BORDER_SUBTLE,
            command=lambda: self._select_chip(chip_id)
        )
        btn.pack(side="left", padx=3)
        return btn

    def _select_chip(self, chip_id: str):
        self.active_chip = chip_id
        self._highlight_active_chip(chip_id)
        if self.on_filter_chip:
            self.on_filter_chip(chip_id)

    def _highlight_active_chip(self, chip_id: str):
        chips = [("all", self.chip_all), ("on", self.chip_on), ("named", self.chip_named)]
        for cid, btn in chips:
            if cid == chip_id:
                btn.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN, border_color=PRIMARY_COLOR)
            else:
                btn.configure(fg_color=BG_SUB, text_color=TEXT_MUTED, border_color=BORDER_SUBTLE)

    def _select_subtab(self, subtab: str):
        self.current_subtab = subtab
        if subtab == "switches":
            self.seg_btn_switches.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN)
            self.seg_btn_vars.configure(fg_color="transparent", text_color=TEXT_MUTED)
            self.btn_turn_off.configure(state="normal")
            self.chip_on.configure(state="normal")
        else:
            self.seg_btn_switches.configure(fg_color="transparent", text_color=TEXT_MUTED)
            self.seg_btn_vars.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN)
            self.btn_turn_off.configure(state="disabled")
            self.chip_on.configure(state="disabled")

        if self.on_segment_change:
            self.on_segment_change(subtab)

    def update_subtab_counts(self, switches_c: int, vars_c: int, on_c: int = 0, named_c: int = 0):
        self.seg_btn_switches.configure(text=f"Switches ({switches_c})")
        self.seg_btn_vars.configure(text=f"Variáveis ({vars_c})")
        self.chip_on.configure(text=f"ON ({on_c})")
        self.chip_named.configure(text=f"Com nome ({named_c})")

    def _on_tree_select(self, event=None):
        sel = self.tree_sys.selection()
        if not sel: return
        sid_str = sel[0]
        try:
            self._selected_id = int(sid_str)
        except ValueError:
            self._selected_id = None

        vals = self.tree_sys.item(sid_str, "values")
        if vals:
            cat = vals[3] if len(vals) > 3 else "Geral"
            self.lbl_selected_info.configure(text=f"#{vals[0]} [{cat}] {vals[1]}: {vals[2]}")

        if self.on_select and self._selected_id:
            self.on_select(self._selected_id)

    def _handle_space_toggle(self):
        if self.current_subtab == "switches" and self.on_toggle_switch:
            self.on_toggle_switch()
            return "break"

    def _handle_enter_edit(self):
        if self.current_subtab == "variables" and self._selected_id:
            sel = self.tree_sys.selection()
            if not sel: return
            vals = self.tree_sys.item(sel[0], "values")
            cur_val = vals[2] if len(vals) > 2 else "0"
            name = vals[1] if len(vals) > 1 else ""
            new_val = simpledialog.askstring("Editar Variável", f"Novo valor para #{self._selected_id} ({name}):", initialvalue=cur_val)
            if new_val is not None and self.on_save_var:
                self.on_save_var(self._selected_id, new_val)
            return "break"

    def _handle_double_click(self):
        if self.current_subtab == "switches":
            self._handle_space_toggle()
        else:
            self._handle_enter_edit()
