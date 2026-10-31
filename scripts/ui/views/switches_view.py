#!/usr/bin/env python3
"""
Switches & Variables View (Tela 04 do Figma - nó #5:1488 / #6:728).
Visualização e edição com barra superior unificada, coluna dedicada de Categoria (via displaycolumns),
chips de filtro rápido (Todos, ON, Com nome), alternância via Espaço e edição com Enter.
Fiel ao Figma Save Maker.
"""

from typing import Callable, Any, Optional
import re
from tkinter import ttk, simpledialog
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, WARNING_COLOR, DANGER_COLOR,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)


def extract_category_and_clean_name(raw_name: str) -> tuple[str, str]:
    """Extrai prefixos como '[Chefe] Derrotado' -> ('Chefe', 'Derrotado')."""
    if not raw_name:
        return ("—", "")
    m = re.match(r"^\s*\[([^\]]+)\]\s*(.*)$", raw_name)
    if m:
        cat = m.group(1).strip() or "Geral"
        rest = m.group(2).strip() or raw_name
        return (cat, rest)
    if raw_name.startswith("Switch #") or raw_name.startswith("Variável #") or raw_name.startswith("Variable "):
        return ("—", raw_name)
    return ("Geral", raw_name)


class SwitchesView(ctk.CTkFrame):
    """Visualização de Switches e Variáveis com categorias e atalhos rápidos."""

    def __init__(
        self,
        master,
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
        # 1. Barra Superior Unificada (#6:729)
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 12))

        # Segments (Switches / Variáveis) em container pill (#6:730)
        seg_box = ctk.CTkFrame(
            top_bar, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        seg_box.pack(side="left", padx=(0, 10))

        self.seg_btn_switches = ctk.CTkButton(
            seg_box, text="Switches  0", font=get_ui_font(12, "bold"),
            height=28, corner_radius=6, fg_color=BG_ACTIVE,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            command=lambda: self._select_subtab("switches")
        )
        self.seg_btn_switches.pack(side="left", padx=3, pady=3)

        self.seg_btn_vars = ctk.CTkButton(
            seg_box, text="Variáveis  0", font=get_ui_font(12, "bold"),
            height=28, corner_radius=6, fg_color="transparent",
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            command=lambda: self._select_subtab("variables")
        )
        self.seg_btn_vars.pack(side="left", padx=3, pady=3)

        # Campo de Pesquisa com ícone (#6:741)
        search_wrap = ctk.CTkFrame(
            top_bar, height=34, fg_color=BG_SUB, corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE
        )
        search_wrap.pack(side="left", fill="x", expand=True, padx=(0, 10))

        s_ico = get_icon("search", size=(14, 14))
        lbl_s = ctk.CTkLabel(search_wrap, text="" if s_ico else "🔍", image=s_ico)
        lbl_s.pack(side="left", padx=(10, 4))

        self.entry_filter = ctk.CTkEntry(
            search_wrap, placeholder_text="Filtrar por nome, ID ou categoria…",
            font=get_ui_font(12), height=30, fg_color="transparent",
            border_width=0, text_color=TEXT_MAIN
        )
        self.entry_filter.pack(side="left", fill="both", expand=True)
        self.entry_filter.bind("<KeyRelease>", lambda e: self.on_filter_change(self.entry_filter.get()))

        # Chips de Filtro Rápido em container pill (#6:744: Todos / ON / Com nome)
        chips_box = ctk.CTkFrame(
            top_bar, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        chips_box.pack(side="left", padx=(0, 10))

        self.chip_all = self._create_chip(chips_box, "Todos", "all")
        self.chip_on = self._create_chip(chips_box, "ON", "on")
        self.chip_named = self._create_chip(chips_box, "Com nome", "named")
        self._highlight_active_chip("all")

        # Botão Desligar Visíveis (#6:759)
        self.btn_turn_off = ctk.CTkButton(
            top_bar, text="Desligar visíveis",
            width=126, height=34, font=get_ui_font(12, "bold"), fg_color="transparent",
            hover_color=BG_SUB, text_color=TEXT_MUTED,
            corner_radius=6, command=self.on_turn_off_visible
        )
        self.btn_turn_off.pack(side="right")

        # 2. Container da Tabela Treeview (#6:761)
        table_container = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        table_container.pack(fill="both", expand=True)

        # Nota: columns mantém ("id", "name", "val", "cat") para que values[0..2] permaneçam
        # idênticos nos testes, enquanto displaycolumns exibe ("id", "cat", "name", "val") como no Figma (#6:762).
        cols = ("id", "name", "val", "cat")
        self.tree_sys = ttk.Treeview(
            table_container, columns=cols,
            displaycolumns=("id", "cat", "name", "val"),
            show="headings", selectmode="browse"
        )

        self.tree_sys.heading("id", text="ID", command=lambda: self.on_sort("id"))
        self.tree_sys.heading("cat", text="Categoria")
        self.tree_sys.heading("name", text="Nome", command=lambda: self.on_sort("name"))
        self.tree_sys.heading("val", text="Estado", command=lambda: self.on_sort("val"))

        self.tree_sys.column("id", width=76, anchor="center", stretch=False)
        self.tree_sys.column("cat", width=140, anchor="center", stretch=False)
        self.tree_sys.column("name", width=480, anchor="w", stretch=True)
        self.tree_sys.column("val", width=160, anchor="center", stretch=False)

        on_fg = SUCCESS_COLOR[1] if isinstance(SUCCESS_COLOR, (tuple, list)) else SUCCESS_COLOR
        off_fg = TEXT_MUTED[1] if isinstance(TEXT_MUTED, (tuple, list)) else TEXT_MUTED
        self.tree_sys.tag_configure("on", foreground=on_fg)
        self.tree_sys.tag_configure("off", foreground=off_fg)

        tree_frame = ctk.CTkFrame(table_container, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=2, pady=(2, 0))

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_sys.yview)
        self.tree_sys.configure(yscrollcommand=scrollbar.set)

        self.tree_sys.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=6)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=6)

        # Bindings de Teclado e Seleção
        self.tree_sys.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree_sys.bind("<space>", lambda e: self._handle_space_toggle())
        self.tree_sys.bind("<Return>", lambda e: self._handle_enter_edit())
        self.tree_sys.bind("<Double-1>", lambda e: self._handle_double_click())

        ctk.CTkFrame(table_container, height=1, fg_color=BORDER_COLOR).pack(fill="x")

        # 3. Rodapé com Instruções de Atalho e Contagem Virtualizada (#6:893)
        bottom_bar = ctk.CTkFrame(
            table_container, fg_color=BG_SUB, corner_radius=0, height=40
        )
        bottom_bar.pack(fill="x", padx=2, pady=(0, 2))
        bottom_bar.pack_propagate(False)

        bot_pad = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        bot_pad.pack(fill="both", expand=True, padx=16, pady=6)

        # Dicas de Atalho à Esquerda (#6:894)
        hints_box = ctk.CTkFrame(bot_pad, fg_color="transparent")
        hints_box.pack(side="left")

        hints = [
            ("Espaço", "alterna"),
            ("↑ ↓", "navega"),
            ("Enter", "edita")
        ]
        for key, act in hints:
            kbd = ctk.CTkFrame(
                hints_box, fg_color=BG_ACTIVE, corner_radius=4,
                border_width=1, border_color=BORDER_COLOR
            )
            kbd.pack(side="left", padx=(0, 4))
            ctk.CTkLabel(kbd, text=key, font=get_mono_font(10), text_color=TEXT_MUTED, padx=5, pady=1).pack()
            ctk.CTkLabel(hints_box, text=act, font=get_ui_font(11), text_color=TEXT_MUTED).pack(side="left", padx=(0, 12))

        self.lbl_selected_info = ctk.CTkLabel(
            bot_pad, text="",
            font=get_ui_font(11), text_color=TEXT_SUBTLE
        )
        self.lbl_selected_info.pack(side="left", padx=8)

        # Info de virtualização à direita (#6:904)
        self.lbl_virtual_info = ctk.CTkLabel(
            bot_pad, text="Linhas 1–0 de 0 · virtualizado",
            font=get_mono_font(11), text_color=TEXT_SUBTLE
        )
        self.lbl_virtual_info.pack(side="right")

    def _create_chip(self, parent, text, chip_id) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            parent, text=text, font=get_ui_font(11, "bold"), height=28,
            corner_radius=6, fg_color="transparent", hover_color=BG_ACTIVE,
            text_color=TEXT_MUTED,
            command=lambda: self._select_chip(chip_id)
        )
        btn.pack(side="left", padx=2, pady=3)
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
                btn.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED)

    def _select_subtab(self, subtab: str):
        self.current_subtab = subtab
        if subtab == "switches":
            self.seg_btn_switches.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN)
            self.seg_btn_vars.configure(fg_color="transparent", text_color=TEXT_MUTED)
            self.btn_turn_off.configure(state="normal")
            self.chip_on.configure(state="normal")
            self.tree_sys.heading("val", text="Estado")
        else:
            self.seg_btn_switches.configure(fg_color="transparent", text_color=TEXT_MUTED)
            self.seg_btn_vars.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN)
            self.btn_turn_off.configure(state="disabled")
            self.chip_on.configure(state="disabled")
            self.tree_sys.heading("val", text="Valor")

        if self.on_segment_change:
            self.on_segment_change(subtab)

    def update_subtab_counts(self, switches_c: int, vars_c: int, on_c: int = 0, named_c: int = 0):
        self.seg_btn_switches.configure(text=f"Switches  {switches_c}")
        self.seg_btn_vars.configure(text=f"Variáveis  {vars_c}")
        self.chip_on.configure(text=f"ON  {on_c}")
        self.chip_named.configure(text=f"Com nome  {named_c}")
        shown = len(self.tree_sys.get_children())
        tot = switches_c if self.current_subtab == "switches" else vars_c
        self.lbl_virtual_info.configure(
            text=f"Linhas 1–{min(shown, 20)} de {shown} ({tot} total) · virtualizado" if shown else "0 itens"
        )

    def _on_tree_select(self, event=None):
        sel = self.tree_sys.selection()
        if not sel:
            return
        sid_str = sel[0]
        try:
            self._selected_id = int(sid_str)
        except ValueError:
            self._selected_id = None

        vals = self.tree_sys.item(sid_str, "values")
        if vals:
            cat = vals[3] if len(vals) > 3 else "Geral"
            self.lbl_selected_info.configure(text=f"{vals[0]} [{cat}] {vals[1]}")

        if self.on_select and self._selected_id:
            self.on_select(self._selected_id)

    def _handle_space_toggle(self):
        if self.current_subtab == "switches" and self.on_toggle_switch:
            self.on_toggle_switch()
            return "break"

    def _handle_enter_edit(self):
        if self.current_subtab == "variables" and self._selected_id:
            sel = self.tree_sys.selection()
            if not sel:
                return
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
