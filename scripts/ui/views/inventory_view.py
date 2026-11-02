#!/usr/bin/env python3
"""
Inventory View (Tela 03 do Figma - nó #5:1192 / #5:2488).
Gerenciamento de Itens, Armas e Armaduras com barra unificada (segmentos, busca, chips e botões),
tabela ttk.Treeview com coluna de Descrição (mantendo índice 2 de values como qty para compatibilidade),
e barra inferior de ações em lote e edição rápida.
Fiel ao Figma Save Maker.
"""

from typing import Callable, Dict, Optional
from tkinter import ttk
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, WARNING_COLOR, DANGER_COLOR, DANGER_HOVER, DANGER_BG,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)


class InventoryView(ctk.CTkFrame):
    """Visualização e edição do inventário."""

    def __init__(
        self,
        master,
        on_kind_change: Callable[[str], None],
        on_filter_change: Callable[[str], None],
        on_sort: Callable[[str], None],
        on_select_item: Callable[[str], None],
        on_set_qty: Callable[[int], None],
        on_step_qty: Callable[[int], None],
        on_complete_db: Callable[[], None],
        on_add_new_item: Callable[[], None],
        on_filter_chip: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_kind_change = on_kind_change
        self.on_filter_change = on_filter_change
        self.on_sort = on_sort
        self.on_select_item = on_select_item
        self.on_set_qty = on_set_qty
        self.on_step_qty = on_step_qty
        self.on_complete_db = on_complete_db
        self.on_add_new_item = on_add_new_item
        self.on_filter_chip = on_filter_chip

        self.current_kind: str = "items"
        self.active_chip: str = "all"
        self._selected_item_id: Optional[str] = None
        self._original_quantities: Dict[str, int] = {}
        self._total_shown: int = 0
        self._total_catalog: int = 0

        self._build_ui()

    def _build_ui(self):
        # 1. Barra Superior Unificada (#5:2489)
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 12))

        # Segmented control em container pill (#5:2490)
        seg_box = ctk.CTkFrame(
            top_bar, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        seg_box.pack(side="left", padx=(0, 10))

        self.seg_btn_items = self._create_seg_btn(seg_box, "Itens  0", "items")
        self.seg_btn_weapons = self._create_seg_btn(seg_box, "Armas  0", "weapons")
        self.seg_btn_armors = self._create_seg_btn(seg_box, "Armaduras  0", "armors")
        self._highlight_active_segment("items")

        # Campo de Busca com ícone (#5:2510)
        search_wrap = ctk.CTkFrame(
            top_bar, height=34, fg_color=BG_SUB, corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE
        )
        search_wrap.pack(side="left", fill="x", expand=True, padx=(0, 10))

        s_ico = get_icon("search", size=(14, 14))
        lbl_s = ctk.CTkLabel(search_wrap, text="" if s_ico else "🔍", image=s_ico)
        lbl_s.pack(side="left", padx=(10, 4))

        self.entry_filter = ctk.CTkEntry(
            search_wrap, placeholder_text="Filtrar por nome ou ID…",
            font=get_ui_font(12), height=30, fg_color="transparent",
            border_width=0, text_color=TEXT_MAIN
        )
        self.entry_filter.pack(side="left", fill="both", expand=True)
        self.entry_filter.bind("<KeyRelease>", lambda e: self.on_filter_change(self.entry_filter.get()))

        # Chips de Filtro (Todos / No Save / Não Obtidos)
        chips_box = ctk.CTkFrame(
            top_bar, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        chips_box.pack(side="left", padx=(0, 10))

        self.chip_all = self._create_chip(chips_box, "Todos", "all")
        self.chip_owned = self._create_chip(chips_box, "No Save", "owned")
        self.chip_unowned = self._create_chip(chips_box, "Faltando", "unowned")
        self._highlight_active_chip("all")

        # Botões de Ação à Direita (#5:2513, #5:2519)
        actions_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        actions_box.pack(side="right")

        db_ico = get_icon("database", size=(14, 14))
        self.btn_db_complete = ctk.CTkButton(
            actions_box, text=" Completar com BD", image=db_ico, compound="left",
            width=142, height=34, font=get_ui_font(12, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR,
            corner_radius=6, command=self.on_complete_db
        )
        self.btn_db_complete.pack(side="left", padx=(0, 6))

        plus_ico = get_icon("plus", size=(14, 14))
        self.btn_add_item = ctk.CTkButton(
            actions_box, text=" Adicionar item", image=plus_ico, compound="left",
            width=128, height=34, font=get_ui_font(12, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR,
            corner_radius=6, command=self.on_add_new_item
        )
        self.btn_add_item.pack(side="left")

        # 2. Container da Tabela Treeview (#5:2525)
        table_container = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        table_container.pack(fill="both", expand=True)

        tree_frame = ctk.CTkFrame(table_container, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=2, pady=(2, 0))

        # Nota: columns mantém ("id", "name", "qty", "desc") para preservar values[2] == qty nos testes,
        # enquanto displaycolumns exibe ("id", "name", "desc", "qty") como no Figma (#5:2526).
        cols = ("id", "name", "qty", "desc")
        self.tree_inv = ttk.Treeview(
            tree_frame, columns=cols,
            displaycolumns=("id", "name", "desc", "qty"),
            show="headings", selectmode="extended"
        )

        self.tree_inv.heading("id", text="ID", command=lambda: self.on_sort("id"))
        self.tree_inv.heading("name", text="Nome", command=lambda: self.on_sort("name"))
        self.tree_inv.heading("desc", text="Descrição")
        self.tree_inv.heading("qty", text="Quantidade", command=lambda: self.on_sort("qty"))

        self.tree_inv.column("id", width=76, anchor="center", stretch=False)
        self.tree_inv.column("name", width=300, stretch=True, anchor="w")
        self.tree_inv.column("desc", width=360, stretch=True, anchor="w")
        self.tree_inv.column("qty", width=130, anchor="center", stretch=False)

        # Tags visuais para estilizar itens possuídos, alterados e não obtidos
        text_fg = TEXT_MAIN[1] if isinstance(TEXT_MAIN, (tuple, list)) else TEXT_MAIN
        muted_fg = TEXT_SUBTLE[1] if isinstance(TEXT_SUBTLE, (tuple, list)) else TEXT_SUBTLE
        gold_fg = PRIMARY_COLOR[1] if isinstance(PRIMARY_COLOR, (tuple, list)) else PRIMARY_COLOR
        self.tree_inv.tag_configure("normal_qty", foreground=text_fg)
        self.tree_inv.tag_configure("modified_qty", foreground=gold_fg)
        self.tree_inv.tag_configure("zero_qty", foreground=muted_fg)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_inv.yview)
        self.tree_inv.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=6)
        self.tree_inv.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=6)

        self.tree_inv.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Divisor antes do rodapé da tabela
        ctk.CTkFrame(table_container, height=1, fg_color=BORDER_COLOR).pack(fill="x")

        # 3. Barra Inferior de Seleção e Ações em Lote (#5:2802)
        self.bottom_bar = ctk.CTkFrame(
            table_container, fg_color=BG_SUB, corner_radius=0, height=46
        )
        self.bottom_bar.pack(fill="x", padx=2, pady=(0, 2))
        self.bottom_bar.pack_propagate(False)

        bot_pad = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        bot_pad.pack(fill="both", expand=True, padx=16, pady=8)

        self.lbl_selected_info = ctk.CTkLabel(
            bot_pad, text="0 selecionados · selecione um item acima para editar",
            font=get_ui_font(12), text_color=TEXT_MUTED
        )
        self.lbl_selected_info.pack(side="left")

        # Controles de quantidade e lote à direita (#5:2805)
        self.stepper_box = ctk.CTkFrame(bot_pad, fg_color="transparent")
        self.stepper_box.pack(side="right")

        ctk.CTkButton(
            self.stepper_box, text="−", width=28, height=28,
            font=get_mono_font(13, "bold"), fg_color=BG_CARD,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE, corner_radius=5,
            command=lambda: self.on_step_qty(-1)
        ).pack(side="left", padx=2)

        self.ent_inv_qty = ctk.CTkEntry(
            self.stepper_box, width=60, height=28, font=get_mono_font(12, "bold"),
            fg_color=BG_CARD, border_color=BORDER_SUBTLE, justify="center", corner_radius=5
        )
        self.ent_inv_qty.pack(side="left", padx=2)
        self.ent_inv_qty.bind("<Return>", lambda e: self._handle_qty_entry())

        ctk.CTkButton(
            self.stepper_box, text="+", width=28, height=28,
            font=get_mono_font(13, "bold"), fg_color=BG_CARD,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE, corner_radius=5,
            command=lambda: self.on_step_qty(1)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self.stepper_box, text="+10", width=42, height=28,
            font=get_ui_font(11, "bold"), fg_color=BG_CARD,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR, corner_radius=5,
            command=lambda: self.on_step_qty(10)
        ).pack(side="left", padx=(6, 2))

        ctk.CTkButton(
            self.stepper_box, text="Definir ×99", width=88, height=28,
            font=get_ui_font(11, "bold"), fg_color=BG_CARD,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR, corner_radius=5,
            command=lambda: self.on_set_qty(99)
        ).pack(side="left", padx=2)

        trash_ico = get_icon("trash", size=(12, 12), tint=DANGER_COLOR[1])
        ctk.CTkButton(
            self.stepper_box, text=" Remover", image=trash_ico, compound="left",
            width=84, height=28, font=get_ui_font(11, "bold"), fg_color=DANGER_BG,
            hover_color=DANGER_HOVER, text_color=DANGER_COLOR,
            border_width=1, border_color=DANGER_COLOR, corner_radius=5,
            command=lambda: self.on_set_qty(0)
        ).pack(side="left", padx=(6, 0))

    def _create_seg_btn(self, parent, text, kind) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            parent, text=text, font=get_ui_font(12, "bold"),
            height=28, corner_radius=6, fg_color="transparent",
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            command=lambda: self._select_kind(kind)
        )
        btn.pack(side="left", padx=3, pady=3)
        return btn

    def _select_kind(self, kind: str):
        self.current_kind = kind
        self._highlight_active_segment(kind)
        if self.on_kind_change:
            self.on_kind_change(kind)

    def _highlight_active_segment(self, kind: str):
        btns = [
            ("items", self.seg_btn_items),
            ("weapons", self.seg_btn_weapons),
            ("armors", self.seg_btn_armors)
        ]
        for k, btn in btns:
            if k == kind:
                btn.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED)

    def _create_chip(self, parent, text, chip_id) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            parent, text=text, font=get_ui_font(11, "bold"),
            height=28, width=76, corner_radius=6, fg_color="transparent",
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
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
        chips = [("all", self.chip_all), ("owned", self.chip_owned), ("unowned", self.chip_unowned)]
        for cid, btn in chips:
            if cid == chip_id:
                btn.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED)

    def update_chip_counts(self, all_c: int = 0, owned_c: int = 0, unowned_c: int = 0):
        self._total_catalog = all_c
        self._total_shown = len(self.tree_inv.get_children())
        self.chip_all.configure(text=f"Todos ({all_c})")
        self.chip_owned.configure(text=f"No Save ({owned_c})")
        self.chip_unowned.configure(text=f"Faltando ({unowned_c})")
        self._update_footer_summary()

    def update_segment_counts(
        self,
        items_c: int, weapons_c: int, armors_c: int,
        items_tot: int = 0, weaps_tot: int = 0, arms_tot: int = 0
    ):
        self.seg_btn_items.configure(text=f"Itens  {items_c}")
        self.seg_btn_weapons.configure(text=f"Armas  {weapons_c}")
        self.seg_btn_armors.configure(text=f"Armaduras  {armors_c}")
        self._total_shown = len(self.tree_inv.get_children())
        self._update_footer_summary()

    def _update_footer_summary(self):
        sel = self.tree_inv.selection()
        n_sel = len(sel)
        shown = len(self.tree_inv.get_children())
        tot = self._total_catalog or shown
        if n_sel == 1:
            vals = self.tree_inv.item(sel[0], "values")
            if vals:
                self.lbl_selected_info.configure(
                    text=f"1 selecionado ({vals[0]} {vals[1]}) · mostrando {shown} de {tot}"
                )
                return
        self.lbl_selected_info.configure(
            text=f"{n_sel} selecionados · mostrando {shown} de {tot} itens"
        )

    def _on_tree_select(self, event=None):
        sel = self.tree_inv.selection()
        if not sel:
            self._update_footer_summary()
            return
        item_id = sel[0]
        self._selected_item_id = item_id

        vals = self.tree_inv.item(item_id, "values")
        if vals:
            qty = vals[2] if len(vals) > 2 else "0"
            self.ent_inv_qty.delete(0, "end")
            self.ent_inv_qty.insert(0, str(qty))

        self._update_footer_summary()

        if self.on_select_item:
            self.on_select_item(item_id)

    def _handle_qty_entry(self):
        txt = self.ent_inv_qty.get().strip()
        try:
            val = int(txt)
            if val < 0:
                val = 0
            self.on_set_qty(val)
        except ValueError:
            pass
