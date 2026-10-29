#!/usr/bin/env python3
"""
Advanced JSON Tree View (Tela 05 do Figma).
Navegação na árvore JSON com paginação sob demanda e painel inspetor
com validação de tipo, interpretação semântica e botões Reverter / Aplicar.
Fiel ao Figma Save Maker.
"""

from typing import Callable, Dict, Any, Optional
import json
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, WARNING_COLOR, DANGER_COLOR,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)

class AdvancedView(ctk.CTkFrame):
    """Árvore JSON raw e Painel Inspetor detalhado."""

    def __init__(
        self, master,
        on_save_value: Callable[[str, Any], None],
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_save_value = on_save_value

        self.selected_node_id: Optional[str] = None
        self.selected_path: Optional[str] = None
        self.original_raw_val: Any = None

        self._build_ui()

    def _build_ui(self):
        paned = ctk.CTkFrame(self, fg_color="transparent")
        paned.pack(fill="both", expand=True)

        # 1. Coluna Esquerda: Árvore Hierárquica
        left = ctk.CTkFrame(
            paned, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        left_header = ctk.CTkFrame(left, fg_color="transparent")
        left_header.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            left_header, text="Árvore JSON", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN
        ).pack(side="left")

        # Container do Treeview
        tree_box = ctk.CTkFrame(left, fg_color="transparent")
        tree_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("value",)
        self.tree = ttk.Treeview(
            tree_box, columns=cols, show="tree headings",
            selectmode="browse"
        )
        self.tree.heading("#0", text="Chave / Caminho")
        self.tree.heading("value", text="Valor")
        self.tree.column("#0", width=340, stretch=True)
        self.tree.column("value", width=220, stretch=True)

        ysb = ttk.Scrollbar(tree_box, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(tree_box, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        xsb.pack(side="bottom", fill="x")

        # 2. Coluna Direita: Painel Inspetor
        self.right = ctk.CTkFrame(
            paned, fg_color=BG_CARD, width=360, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.right.pack(side="right", fill="y")
        self.right.pack_propagate(False)

        right_header = ctk.CTkFrame(self.right, fg_color="transparent")
        right_header.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            right_header, text="Inspetor", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN
        ).pack(anchor="w")

        # Caminho completo
        self.lbl_path = ctk.CTkLabel(
            self.right, text="Selecione um nó ao lado", font=get_mono_font(12, "bold"),
            text_color=PRIMARY_COLOR[1], anchor="w"
        )
        self.lbl_path.pack(fill="x", padx=16, pady=(4, 12))

        # Metadados do nó (Tipo / Valor Original / Interpretação)
        meta_box = ctk.CTkFrame(self.right, fg_color=BG_SUB, corner_radius=6)
        meta_box.pack(fill="x", padx=16, pady=(0, 12))

        p_meta = ctk.CTkFrame(meta_box, fg_color="transparent")
        p_meta.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(p_meta, text="Tipo:", font=get_ui_font(11), text_color=TEXT_MUTED).pack(anchor="w")
        self.lbl_type = ctk.CTkLabel(p_meta, text="—", font=get_mono_font(11, "bold"), text_color=TEXT_MAIN)
        self.lbl_type.pack(anchor="w", pady=(0, 6))

        ctk.CTkLabel(p_meta, text="Valor original:", font=get_ui_font(11), text_color=TEXT_MUTED).pack(anchor="w")
        self.lbl_orig_val = ctk.CTkLabel(p_meta, text="—", font=get_mono_font(11), text_color=TEXT_MAIN)
        self.lbl_orig_val.pack(anchor="w", pady=(0, 6))

        ctk.CTkLabel(p_meta, text="Interpretado como:", font=get_ui_font(11), text_color=TEXT_MUTED).pack(anchor="w")
        self.lbl_semantic = ctk.CTkLabel(p_meta, text="—", font=get_ui_font(11), text_color=TEXT_MAIN)
        self.lbl_semantic.pack(anchor="w")

        # Editor de Valor
        ed_box = ctk.CTkFrame(self.right, fg_color="transparent")
        ed_box.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        ctk.CTkLabel(ed_box, text="Valor:", font=get_ui_font(12, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 4))
        self.entry_val = ctk.CTkEntry(
            ed_box, font=get_mono_font(12), height=34,
            fg_color=BG_SUB, border_color=BORDER_SUBTLE, corner_radius=6
        )
        self.entry_val.pack(fill="x", pady=(0, 10))

        # Alerta de edição direta
        warn_box = ctk.CTkFrame(ed_box, fg_color=BG_SUB, corner_radius=6)
        warn_box.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            warn_box,
            text="⚠️ Edição direta ignora validações das outras telas.\nUse com cuidado — Ctrl Z desfaz.",
            font=get_ui_font(10), text_color=TEXT_MUTED, justify="left", padx=8, pady=8
        ).pack(anchor="w")

        # Botões Reverter / Aplicar
        btn_row = ctk.CTkFrame(ed_box, fg_color="transparent")
        btn_row.pack(fill="x")

        undo_ico = get_icon("undo", size=(14, 14))
        self.btn_revert = ctk.CTkButton(
            btn_row, text=" Reverter", image=undo_ico, compound="left",
            font=get_ui_font(12), height=34, fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE, corner_radius=6,
            command=self._handle_revert
        )
        self.btn_revert.pack(side="left", padx=(0, 6), fill="x", expand=True)

        apply_ico = get_icon("check", size=(14, 14), tint="#0B0C10")
        self.btn_apply = ctk.CTkButton(
            btn_row, text=" Aplicar valor", image=apply_ico, compound="left",
            font=get_ui_font(12, "bold"), height=34,
            fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER,
            text_color=PRIMARY_TEXT, corner_radius=6,
            command=self._handle_apply
        )
        self.btn_apply.pack(side="right", fill="x", expand=True)

    def set_inspector_node(self, path_str: str, raw_val: Any, semantic_label: str = ""):
        self.selected_path = path_str
        self.original_raw_val = raw_val
        self.lbl_path.configure(text=path_str)

        val_type = type(raw_val).__name__
        self.lbl_type.configure(text=val_type)

        val_str = json.dumps(raw_val, ensure_ascii=False) if not isinstance(raw_val, str) else raw_val
        self.lbl_orig_val.configure(text=val_str[:60] + ("..." if len(val_str) > 60 else ""))
        self.lbl_semantic.configure(text=semantic_label or "Chave genérica do save")

        self.entry_val.delete(0, "end")
        self.entry_val.insert(0, val_str)

    def _handle_revert(self):
        if self.original_raw_val is not None:
            val_str = json.dumps(self.original_raw_val, ensure_ascii=False) if not isinstance(self.original_raw_val, str) else self.original_raw_val
            self.entry_val.delete(0, "end")
            self.entry_val.insert(0, val_str)

    def _handle_apply(self):
        if not self.selected_path: return
        raw_input = self.entry_val.get().strip()
        try:
            val = json.loads(raw_input)
        except Exception:
            val = raw_input

        if self.on_save_value:
            self.on_save_value(self.selected_path, val)
