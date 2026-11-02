#!/usr/bin/env python3
"""
Advanced JSON Tree View (Tela 05 do Figma - nó #5:1782 / #6:906).
Navegação na árvore JSON com barra de breadcrumb, paginação sob demanda e painel inspetor
com validação de JSON/tipo em tempo real, interpretação semântica e botões Reverter / Aplicar.
Fiel ao Figma Save Maker.
"""

from typing import Callable, Any, Optional
import json
from tkinter import ttk
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, WARNING_COLOR, WARNING_BG, DANGER_COLOR,
    BG_CANVAS, BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)


def infer_semantic_meaning(path_str: str) -> str:
    """Interpreta semanticamente caminhos conhecidos de saves RPG Maker."""
    p = path_str.lower()
    if p.endswith("_gold") or p == "gold":
        return "Ouro do grupo"
    if p.endswith("_steps") or p == "steps":
        return "Passos dados na campanha"
    if "_framesonsave" in p:
        return "Quadros (60 fps) de tempo de jogo"
    if p.startswith("party._items"):
        return "Quantidade de item no inventário"
    if p.startswith("party._weapons"):
        return "Quantidade de arma no inventário"
    if p.startswith("party._armors"):
        return "Quantidade de armadura no inventário"
    if p.startswith("party._actors"):
        return "IDs dos heróis no grupo ativo"
    if p.startswith("actors._data"):
        if p.endswith("_hp"):
            return "HP atual do personagem"
        if p.endswith("_mp"):
            return "MP atual do personagem"
        if p.endswith("_tp"):
            return "TP atual do personagem"
        if p.endswith("_level"):
            return "Nível atual do personagem"
        if p.endswith("_name"):
            return "Nome do personagem"
        if "_paramplus" in p:
            return "Bônus de atributo (MHP/MMP/ATK/DEF/MAT/MDF/AGI/LUK)"
        return "Ficha de dados do personagem"
    if p.startswith("switches"):
        return "Flag booleana de evento (Switch)"
    if p.startswith("variables"):
        return "Variável global de progresso/evento"
    if p.startswith("map"):
        return "Estado do mapa e posição do jogador"
    if p.startswith("system"):
        return "Configurações de sistema do save"
    return "Chave estrutural do save"


class AdvancedView(ctk.CTkFrame):
    """Árvore JSON raw com Breadcrumb e Painel Inspetor detalhado."""

    def __init__(
        self,
        master,
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

        # 1. Coluna Esquerda: Árvore Hierárquica com Breadcrumb (#6:908)
        left = ctk.CTkFrame(
            paned, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 14))

        # Barra de Breadcrumb no topo (#6:909)
        self.breadcrumb_bar = ctk.CTkFrame(
            left, fg_color=BG_SUB, corner_radius=0, height=38
        )
        self.breadcrumb_bar.pack(fill="x", padx=2, pady=(2, 0))
        self.breadcrumb_bar.pack_propagate(False)

        bc_inner = ctk.CTkFrame(self.breadcrumb_bar, fg_color="transparent")
        bc_inner.pack(fill="both", expand=True, padx=14, pady=6)

        braces_ico = get_icon("braces", size=(13, 13))
        if braces_ico:
            ctk.CTkLabel(bc_inner, text="", image=braces_ico).pack(side="left", padx=(0, 8))

        self.lbl_breadcrumb = ctk.CTkLabel(
            bc_inner, text="raiz", font=get_mono_font(12, "bold"),
            text_color=PRIMARY_COLOR, anchor="w"
        )
        self.lbl_breadcrumb.pack(side="left", fill="x", expand=True)

        ctk.CTkFrame(left, height=1, fg_color=BORDER_COLOR).pack(fill="x")

        # Container do Treeview
        tree_box = ctk.CTkFrame(left, fg_color="transparent")
        tree_box.pack(fill="both", expand=True, padx=10, pady=8)

        cols = ("value",)
        self.tree = ttk.Treeview(
            tree_box, columns=cols, show="tree headings",
            selectmode="browse"
        )
        self.tree.heading("#0", text="Chave / Caminho")
        self.tree.heading("value", text="Valor / Resumo")
        self.tree.column("#0", width=340, stretch=True)
        self.tree.column("value", width=240, stretch=True)

        ysb = ttk.Scrollbar(tree_box, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(tree_box, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        tree_box.grid_rowconfigure(0, weight=1)
        tree_box.grid_columnconfigure(0, weight=1)

        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")

        # 2. Coluna Direita: Painel Inspetor (#6:1063, width=380)
        self.right = ctk.CTkFrame(
            paned, fg_color=BG_CARD, width=380, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        self.right.pack(side="right", fill="y")
        self.right.pack_propagate(False)

        right_pad = ctk.CTkFrame(self.right, fg_color="transparent")
        right_pad.pack(fill="both", expand=True, padx=18, pady=18)

        # Cabeçalho Inspetor (#6:1064)
        ctk.CTkLabel(
            right_pad, text="INSPETOR", font=get_ui_font(10, "bold"),
            text_color=TEXT_SUBTLE, anchor="w"
        ).pack(fill="x")

        self.lbl_path = ctk.CTkLabel(
            right_pad, text="Selecione um nó", font=get_mono_font(16, "bold"),
            text_color=PRIMARY_COLOR, anchor="w"
        )
        self.lbl_path.pack(fill="x", pady=(2, 10))

        ctk.CTkFrame(right_pad, height=1, fg_color=BORDER_COLOR).pack(fill="x", pady=(0, 10))

        # 3 Linhas horizontais de metadados (#6:1067–#6:1075)
        self.lbl_type = self._create_meta_row(right_pad, "Tipo", "—", is_mono=True)
        self.lbl_orig_val = self._create_meta_row(right_pad, "Valor original", "—", is_mono=True)
        self.lbl_semantic = self._create_meta_row(right_pad, "Interpretado como", "—", is_mono=False)

        ctk.CTkFrame(right_pad, height=1, fg_color=BORDER_COLOR).pack(fill="x", pady=(10, 12))

        # Editor de Valor (#6:1077)
        ctk.CTkLabel(
            right_pad, text="Valor", font=get_ui_font(11, "bold"),
            text_color=TEXT_MUTED, anchor="w"
        ).pack(fill="x", pady=(0, 6))

        self.code_box = ctk.CTkFrame(
            right_pad, fg_color=BG_CANVAS, corner_radius=8,
            border_width=1, border_color=PRIMARY_COLOR, height=84
        )
        self.code_box.pack(fill="x", pady=(0, 8))
        self.code_box.pack_propagate(False)

        self.entry_val = ctk.CTkEntry(
            self.code_box, font=get_mono_font(14, "bold"), height=36,
            fg_color="transparent", border_width=0, text_color=TEXT_MAIN
        )
        self.entry_val.pack(fill="x", padx=10, pady=8)
        self.entry_val.bind("<KeyRelease>", self._validate_live_input)
        self.entry_val.bind("<Return>", lambda e: self._handle_apply())
        self.entry_val.bind("<FocusOut>", lambda e: self._handle_apply())
        self.code_box.bind("<Button-1>", lambda e: self.entry_val.focus_set())

        # Indicador de validação JSON ao vivo (#6:1080)
        val_row = ctk.CTkFrame(right_pad, fg_color="transparent")
        val_row.pack(fill="x", pady=(0, 12))

        check_ico = get_icon("check", size=(13, 13), tint=SUCCESS_COLOR[1])
        self.lbl_val_icon = ctk.CTkLabel(val_row, text="" if check_ico else "✓", image=check_ico)
        self.lbl_val_icon.pack(side="left", padx=(0, 6))

        self.lbl_validation = ctk.CTkLabel(
            val_row, text="JSON válido · mesmo tipo do original",
            font=get_ui_font(11), text_color=SUCCESS_COLOR, anchor="w"
        )
        self.lbl_validation.pack(side="left")

        # Alerta de edição direta (#6:1085)
        warn_box = ctk.CTkFrame(
            right_pad, fg_color=WARNING_BG, corner_radius=8,
            border_width=1, border_color=PRIMARY_COLOR
        )
        warn_box.pack(fill="x", pady=(0, 14))

        warn_inner = ctk.CTkFrame(warn_box, fg_color="transparent")
        warn_inner.pack(fill="x", padx=10, pady=8)

        alert_ico = get_icon("alert-triangle", size=(14, 14), tint=PRIMARY_COLOR[1])
        ctk.CTkLabel(warn_inner, text="" if alert_ico else "⚠️", image=alert_ico).pack(side="left", anchor="n", padx=(0, 8), pady=2)

        ctk.CTkLabel(
            warn_inner,
            text="Edição direta ignora validações das outras telas.\nUse com cuidado — Ctrl Z desfaz.",
            font=get_ui_font(11), text_color=TEXT_MUTED, justify="left", anchor="w"
        ).pack(side="left", fill="x", expand=True)

        # Botões Reverter / Aplicar (#6:1090)
        btn_row = ctk.CTkFrame(right_pad, fg_color="transparent")
        btn_row.pack(fill="x", side="bottom")

        undo_ico = get_icon("undo", size=(14, 14))
        self.btn_revert = ctk.CTkButton(
            btn_row, text=" Reverter", image=undo_ico, compound="left",
            font=get_ui_font(12, "bold"), height=34, fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR, corner_radius=6,
            command=self._handle_revert
        )
        self.btn_revert.pack(side="left", padx=(0, 6), fill="x", expand=True)

        apply_ico = get_icon("check", size=(14, 14))
        self.btn_apply = ctk.CTkButton(
            btn_row, text=" Aplicar valor", image=apply_ico, compound="left",
            font=get_ui_font(12, "bold"), height=34,
            fg_color=BG_SUB, hover_color=BG_ACTIVE,
            text_color=TEXT_MAIN, border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6, command=self._handle_apply
        )
        self.btn_apply.pack(side="right", fill="x", expand=True)

    def _create_meta_row(self, parent, label: str, initial_val: str, is_mono: bool = True) -> ctk.CTkLabel:
        row = ctk.CTkFrame(parent, fg_color="transparent", height=24)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        ctk.CTkLabel(row, text=label, font=get_ui_font(12), text_color=TEXT_MUTED).pack(side="left")
        lbl_v = ctk.CTkLabel(
            row, text=initial_val,
            font=get_mono_font(12) if is_mono else get_ui_font(12),
            text_color=TEXT_MAIN
        )
        lbl_v.pack(side="right")
        return lbl_v

    def set_inspector_node(self, path_str: str, raw_val: Any, semantic_label: str = ""):
        self.selected_path = path_str
        self.original_raw_val = raw_val
        self.lbl_path.configure(text=path_str or "raiz")

        # Atualiza Breadcrumb (#6:909: raiz › party › _gold)
        parts = ["raiz"] + [p for p in path_str.split(".") if p] if path_str else ["raiz"]
        self.lbl_breadcrumb.configure(text="  ›  ".join(parts))

        # Tipo detalhado como no Figma (#6:1069)
        if isinstance(raw_val, bool):
            val_type = "boolean"
        elif isinstance(raw_val, int):
            val_type = "number (inteiro)"
        elif isinstance(raw_val, float):
            val_type = "number (decimal)"
        elif isinstance(raw_val, str):
            val_type = "string"
        elif isinstance(raw_val, list):
            val_type = f"array ({len(raw_val)} itens)"
        elif isinstance(raw_val, dict):
            val_type = f"object ({len(raw_val)} chaves)"
        else:
            val_type = type(raw_val).__name__
        self.lbl_type.configure(text=val_type)

        val_str = json.dumps(raw_val, ensure_ascii=False) if not isinstance(raw_val, str) else raw_val
        self.lbl_orig_val.configure(text=val_str[:38] + ("…" if len(val_str) > 38 else ""))
        self.lbl_semantic.configure(text=semantic_label or infer_semantic_meaning(path_str))

        self.entry_val.delete(0, "end")
        self.entry_val.insert(0, val_str)
        self._validate_live_input()

    def _validate_live_input(self, event=None):
        raw_input = self.entry_val.get().strip()
        try:
            parsed = json.loads(raw_input)
            same_type = (
                self.original_raw_val is None
                or type(parsed) is type(self.original_raw_val)
                or (isinstance(parsed, (int, float)) and isinstance(self.original_raw_val, (int, float)))
            )
            if same_type:
                self.lbl_validation.configure(
                    text="JSON válido · mesmo tipo do original",
                    text_color=SUCCESS_COLOR
                )
                self.code_box.configure(border_color=PRIMARY_COLOR)
            else:
                self.lbl_validation.configure(
                    text=f"JSON válido · tipo alterado ({type(parsed).__name__})",
                    text_color=WARNING_COLOR
                )
                self.code_box.configure(border_color=WARNING_COLOR)
        except Exception:
            if isinstance(self.original_raw_val, str):
                self.lbl_validation.configure(
                    text="Texto literal (string) · mesmo tipo do original",
                    text_color=SUCCESS_COLOR
                )
                self.code_box.configure(border_color=PRIMARY_COLOR)
            else:
                self.lbl_validation.configure(
                    text="Formato não-JSON · será salvo como texto",
                    text_color=WARNING_COLOR
                )
                self.code_box.configure(border_color=WARNING_COLOR)

    def _handle_revert(self):
        if self.original_raw_val is not None:
            val_str = json.dumps(self.original_raw_val, ensure_ascii=False) if not isinstance(self.original_raw_val, str) else self.original_raw_val
            self.entry_val.delete(0, "end")
            self.entry_val.insert(0, val_str)
            self._validate_live_input()

    def _handle_apply(self):
        if not self.selected_path:
            return
        raw_input = self.entry_val.get().strip()
        try:
            val = json.loads(raw_input)
        except Exception:
            val = raw_input

        if self.on_save_value:
            self.on_save_value(self.selected_path, val)
