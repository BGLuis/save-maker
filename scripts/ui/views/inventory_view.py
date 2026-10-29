#!/usr/bin/env python3
"""
Inventory View (Tela 03 do Figma).
Gerenciamento de Itens, Armas e Armaduras com segmentos modernos,
tabela ttk.Treeview estilizada, stepper de quantidade inline e badges de alteração.
Fiel ao Figma Save Maker.
"""

from typing import Callable, List, Dict, Any, Optional
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, WARNING_COLOR, DANGER_COLOR, DANGER_HOVER,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)

class InventoryView(ctk.CTkFrame):
    """Visualização e edição do inventário."""

    def __init__(
        self, master,
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

        self._build_ui()

    def _build_ui(self):
        # 1. Barra Superior com Segmentos e Filtros
        top_bar = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        top_bar.pack(fill="x", pady=(0, 10))

        pad_top = ctk.CTkFrame(top_bar, fg_color="transparent")
        pad_top.pack(fill="x", padx=16, pady=10)

        # Segments (Itens / Armas / Armaduras)
        seg_box = ctk.CTkFrame(pad_top, fg_color="transparent")
        seg_box.pack(side="left")

        self.seg_btn_items = self._create_seg_btn(seg_box, "Itens (0)", "items")
        self.seg_btn_weapons = self._create_seg_btn(seg_box, "Armas (0)", "weapons")
        self.seg_btn_armors = self._create_seg_btn(seg_box, "Armaduras (0)", "armors")

        self._highlight_active_segment("items")

        # Chips de Filtro (Todos do BD / No Save / Não Obtidos)
        chips_box = ctk.CTkFrame(pad_top, fg_color="transparent")
        chips_box.pack(side="left", padx=16)

        self.chip_all = self._create_chip(chips_box, "Todos do BD", "all")
        self.chip_owned = self._create_chip(chips_box, "No Save", "owned")
        self.chip_unowned = self._create_chip(chips_box, "Não Obtidos", "unowned")
        self._highlight_active_chip("all")

        # Botões de Ação à Direita
        actions_box = ctk.CTkFrame(pad_top, fg_color="transparent")
        actions_box.pack(side="right")

        db_ico = get_icon("database", size=(14, 14))
        self.btn_db_complete = ctk.CTkButton(
            actions_box, text=" Completar com BD", image=db_ico, compound="left",
            width=134, height=32, font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6, command=self.on_complete_db
        )
        self.btn_db_complete.pack(side="left", padx=4)

        plus_ico = get_icon("plus", size=(14, 14), tint="#0B0C10")
        self.btn_add_item = ctk.CTkButton(
            actions_box, text=" Adicionar item", image=plus_ico, compound="left",
            width=124, height=32, font=get_ui_font(11, "bold"), fg_color=PRIMARY_COLOR,
            hover_color=PRIMARY_HOVER, text_color=PRIMARY_TEXT,
            corner_radius=6, command=self.on_add_new_item
        )
        self.btn_add_item.pack(side="left", padx=4)

        # Barra de Pesquisa de Inventário
        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", pady=(0, 8))

        self.entry_filter = ctk.CTkEntry(
            search_row, placeholder_text="Filtrar por nome ou ID…",
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

        cols = ("id", "name", "qty")
        self.tree_inv = ttk.Treeview(
            table_container, columns=cols, show="headings",
            selectmode="browse"
        )

        self.tree_inv.heading("id", text="ID", command=lambda: self.on_sort("id"))
        self.tree_inv.heading("name", text="Nome do Item / Equipamento", command=lambda: self.on_sort("name"))
        self.tree_inv.heading("qty", text="Quantidade", command=lambda: self.on_sort("qty"))

        self.tree_inv.column("id", width=80, anchor="center")
        self.tree_inv.column("name", width=520, stretch=True, anchor="w")
        self.tree_inv.column("qty", width=120, anchor="center")

        # Tags visuais para estilizar itens possuídos vs não obtidos
        text_fg = TEXT_MAIN[1] if isinstance(TEXT_MAIN, (tuple, list)) else TEXT_MAIN
        muted_fg = TEXT_MUTED[1] if isinstance(TEXT_MUTED, (tuple, list)) else TEXT_MUTED
        self.tree_inv.tag_configure("normal_qty", foreground=text_fg)
        self.tree_inv.tag_configure("zero_qty", foreground=muted_fg)

        # Scrollbar vertical
        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_inv.yview)
        self.tree_inv.configure(yscrollcommand=scrollbar.set)

        self.tree_inv.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=10)

        self.tree_inv.bind("<<TreeviewSelect>>", self._on_tree_select)

        # 3. Barra Inferior de Edição Direta / Stepper
        self.bottom_bar = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=8, height=48,
            border_width=1, border_color=BORDER_COLOR
        )
        self.bottom_bar.pack(fill="x")
        self.bottom_bar.pack_propagate(False)

        bot_pad = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        bot_pad.pack(fill="both", expand=True, padx=16, pady=8)

        self.lbl_selected_info = ctk.CTkLabel(
            bot_pad, text="Selecione um item acima para editar",
            font=get_ui_font(12), text_color=TEXT_MUTED
        )
        self.lbl_selected_info.pack(side="left")

        # Stepper à direita
        self.stepper_box = ctk.CTkFrame(bot_pad, fg_color="transparent")
        self.stepper_box.pack(side="right")

        ctk.CTkButton(
            self.stepper_box, text="-1", width=34, height=28,
            font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN, corner_radius=4,
            command=lambda: self.on_step_qty(-1)
        ).pack(side="left", padx=2)

        self.ent_inv_qty = ctk.CTkEntry(
            self.stepper_box, width=64, height=28, font=get_mono_font(12, "bold"),
            fg_color=BG_SUB, border_color=BORDER_SUBTLE, justify="center", corner_radius=4
        )
        self.ent_inv_qty.pack(side="left", padx=2)
        self.ent_inv_qty.bind("<Return>", lambda e: self._handle_qty_entry())

        ctk.CTkButton(
            self.stepper_box, text="+1", width=34, height=28,
            font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN, corner_radius=4,
            command=lambda: self.on_step_qty(1)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self.stepper_box, text="+10", width=42, height=28,
            font=get_ui_font(11), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN, corner_radius=4,
            command=lambda: self.on_step_qty(10)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self.stepper_box, text="+99", width=42, height=28,
            font=get_ui_font(11), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN, corner_radius=4,
            command=lambda: self.on_step_qty(99)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self.stepper_box, text="Zerar", width=50, height=28,
            font=get_ui_font(11, "bold"), fg_color=DANGER_COLOR,
            hover_color=DANGER_HOVER, text_color="#FFFFFF", corner_radius=4,
            command=lambda: self.on_set_qty(0)
        ).pack(side="left", padx=4)

    def _create_seg_btn(self, parent, text, kind) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            parent, text=text, font=get_ui_font(12, "bold"),
            height=32, corner_radius=6, fg_color="transparent",
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            command=lambda: self._select_kind(kind)
        )
        btn.pack(side="left", padx=2)
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
            height=26, corner_radius=13, fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER_SUBTLE,
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
        chips = [("all", self.chip_all), ("owned", self.chip_owned), ("unowned", self.chip_unowned)]
        for cid, btn in chips:
            if cid == chip_id:
                btn.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN, border_color=PRIMARY_COLOR)
            else:
                btn.configure(fg_color=BG_SUB, text_color=TEXT_MUTED, border_color=BORDER_SUBTLE)

    def update_chip_counts(self, all_c: int = 0, owned_c: int = 0, unowned_c: int = 0):
        self.chip_all.configure(text=f"Todos ({all_c})")
        self.chip_owned.configure(text=f"No Save ({owned_c})")
        self.chip_unowned.configure(text=f"Não Obtidos ({unowned_c})")

    def update_segment_counts(self, items_c: int, weapons_c: int, armors_c: int,
                              items_tot: int = 0, weaps_tot: int = 0, arms_tot: int = 0):
        if items_tot and items_tot > items_c:
            self.seg_btn_items.configure(text=f"Itens ({items_c}/{items_tot})")
        else:
            self.seg_btn_items.configure(text=f"Itens ({items_c})")

        if weaps_tot and weaps_tot > weapons_c:
            self.seg_btn_weapons.configure(text=f"Armas ({weapons_c}/{weaps_tot})")
        else:
            self.seg_btn_weapons.configure(text=f"Armas ({weapons_c})")

        if arms_tot and arms_tot > armors_c:
            self.seg_btn_armors.configure(text=f"Armaduras ({armors_c}/{arms_tot})")
        else:
            self.seg_btn_armors.configure(text=f"Armaduras ({armors_c})")

    def _on_tree_select(self, event=None):
        sel = self.tree_inv.selection()
        if not sel: return
        item_id = sel[0]
        self._selected_item_id = item_id

        vals = self.tree_inv.item(item_id, "values")
        if vals:
            self.lbl_selected_info.configure(text=f"#{vals[0]} {vals[1]}")
            qty = vals[2] if len(vals) > 2 else "0"
            self.ent_inv_qty.delete(0, "end")
            self.ent_inv_qty.insert(0, str(qty))

        if self.on_select_item:
            self.on_select_item(item_id)

    def _handle_qty_entry(self):
        txt = self.ent_inv_qty.get().strip()
        try:
            val = int(txt)
            if val < 0: val = 0
            self.on_set_qty(val)
        except ValueError:
            pass
