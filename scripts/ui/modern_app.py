#!/usr/bin/env python3
"""
ModernApp - Interface Gráfica Moderna e Universal do RPG Maker Save Editor

Construída em CustomTkinter com Dark/Light Mode, Drag & Drop nativo,
descoberta automática de banco de dados (Armors.json, Items.json, System.json, etc.),
abas especializadas (Visão Geral, Personagens, Inventário, Switches & Variáveis, Árvore Avançada)
e barra de pesquisa global em tempo real.
"""

from __future__ import annotations
import sys
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from typing import Any, Dict, List, Optional

import customtkinter as ctk

# Adiciona diretórios ao sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SCRIPTS_DIR.parent
for d in (str(SCRIPTS_DIR), str(ROOT_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

from core.database_manager import GameDatabaseManager, GLOBAL_DB
from core.detector import detect_and_create_adapter
from core.base_adapter import BaseSaveAdapter
from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, SUCCESS_COLOR, SUCCESS_HOVER,
    DANGER_COLOR, DANGER_HOVER, WARNING_COLOR, WARNING_HOVER,
    BG_CARD, BG_SUB, TEXT_MUTED, TEXT_MAIN, BORDER_COLOR
)

try:
    import tkinterdnd2
    from tkinterdnd2 import DND_FILES
    _DND_AVAILABLE = True
except Exception:
    tkinterdnd2 = None
    DND_FILES = None
    _DND_AVAILABLE = False


# Classe base com suporte opcional a Drag & Drop
if _DND_AVAILABLE:
    class CtkDndApp(ctk.CTk, tkinterdnd2.TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = tkinterdnd2.TkinterDnD._require(self)
else:
    class CtkDndApp(ctk.CTk):
        pass


class ModernSaveEditorApp(CtkDndApp):
    """Aplicação Principal Moderna para Edição de Saves de RPG Maker."""

    def __init__(self):
        super().__init__()

        # Configurações de Janela
        self.title("RPG Maker Save Editor — Universal Edition")
        self.geometry("1180x760")
        self.minsize(960, 620)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Estado da Aplicação
        self.db = GLOBAL_DB
        self.adapter: Optional[BaseSaveAdapter] = None
        self.current_file: Optional[Path] = None
        self.gui_queue = queue.Queue()
        self.selected_actor_id: Optional[Any] = None
        self.current_inv_kind: str = "items"
        self.current_system_tab: str = "switches"

        # Performance, Cache e Ordenação
        self.tabs_need_refresh = {
            "overview": True,
            "actors": True,
            "inventory": True,
            "switches": True,
            "advanced": True
        }
        self._search_debounce_job = None
        self._inv_sort_col: str = "id"
        self._inv_sort_desc: bool = False
        self._selected_inv_id: Optional[str] = None
        self._system_sort_col: str = "id"
        self._system_sort_desc: bool = False
        self._selected_sys_id: Optional[int] = None
        self._tree_node_has_children: Dict[str, Any] = {}

        # Configura estilos de tabela Treeview para Dark/Light mode
        self._setup_treeview_styles("dark")

        # Widgets e Interface
        self._create_header_bar()
        self._create_search_bar()
        self._create_tabview()
        self._create_status_bar()

        # Drag and drop se disponível
        if _DND_AVAILABLE:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop_file)
            except Exception:
                pass

        # Loop de mensagens de UI thread-safe
        self._check_gui_queue()

    def _check_gui_queue(self):
        try:
            while True:
                fn, args, kwargs = self.gui_queue.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception as e:
                    print(f"[GUI Queue Error] {e}")
        except queue.Empty:
            pass
        finally:
            self.after(100, self._check_gui_queue)

    def queue_ui(self, fn, *args, **kwargs):
        self.gui_queue.put((fn, args, kwargs))

    def _setup_treeview_styles(self, mode: str = "dark"):
        """Configura tema visual das tabelas Treeview para integração perfeita com CustomTkinter."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        is_dark = str(mode).lower() == "dark"
        bg_card = "#1E293B" if is_dark else "#FFFFFF"
        fg_text = "#F8FAFC" if is_dark else "#0F172A"
        bg_header = "#0F172A" if is_dark else "#E2E8F0"
        fg_header = "#94A3B8" if is_dark else "#475569"
        bg_select = "#2563EB"
        fg_select = "#FFFFFF"

        style.configure(
            "Modern.Treeview",
            background=bg_card,
            foreground=fg_text,
            fieldbackground=bg_card,
            rowheight=30,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.configure(
            "Modern.Treeview.Heading",
            background=bg_header,
            foreground=fg_header,
            font=("Segoe UI", 10, "bold"),
            relief="flat"
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", bg_select)],
            foreground=[("selected", fg_select)]
        )
        style.map(
            "Modern.Treeview.Heading",
            background=[("active", "#1E3A8A" if is_dark else "#CBD5E1")]
        )

    # --- Construção da Interface ---

    def _create_header_bar(self):
        """Barra de topo com ações principais, status e controle de tema."""
        self.header_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10, height=56)
        self.header_frame.pack(fill="x", padx=12, pady=(10, 6))

        # Ações de Arquivo
        btn_open = ctk.CTkButton(
            self.header_frame, text="📂 Abrir Save", width=110,
            command=self.open_file_dialog, font=ctk.CTkFont(weight="bold")
        )
        btn_open.pack(side="left", padx=(10, 6), pady=10)

        self.btn_save = ctk.CTkButton(
            self.header_frame, text="💾 Salvar", width=95,
            fg_color=SUCCESS_COLOR, hover_color=SUCCESS_HOVER,
            command=self.save_current_file, font=ctk.CTkFont(weight="bold")
        )
        self.btn_save.pack(side="left", padx=4, pady=10)

        self.btn_save_as = ctk.CTkButton(
            self.header_frame, text="Salvar Como...", width=110,
            fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER,
            command=self.save_as_dialog
        )
        self.btn_save_as.pack(side="left", padx=4, pady=10)

        btn_export_json = ctk.CTkButton(
            self.header_frame, text="Exportar JSON", width=110,
            fg_color="transparent", border_width=1, border_color=BORDER_COLOR,
            command=self.export_json_dialog
        )
        btn_export_json.pack(side="left", padx=4, pady=10)

        # Botão Banco de Dados
        self.btn_game_data = ctk.CTkButton(
            self.header_frame, text="📁 Pasta do Jogo", width=120,
            fg_color="transparent", border_width=1, border_color=BORDER_COLOR,
            command=self.select_game_data_dir
        )
        self.btn_game_data.pack(side="left", padx=6, pady=10)

        # Badges no canto direito
        self.theme_switch = ctk.CTkButton(
            self.header_frame, text="🌙 / ☀️", width=50,
            fg_color="transparent", border_width=1, border_color=BORDER_COLOR,
            command=self.toggle_theme
        )
        self.theme_switch.pack(side="right", padx=(6, 10), pady=10)

        self.lbl_dirty_badge = ctk.CTkLabel(
            self.header_frame, text="✓ Salvo", text_color=SUCCESS_COLOR[1],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_dirty_badge.pack(side="right", padx=10)

        self.lbl_engine_badge = ctk.CTkLabel(
            self.header_frame, text="Nenhum save carregado",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)
        )
        self.lbl_engine_badge.pack(side="right", padx=10)

    def _create_search_bar(self):
        """Barra de pesquisa global em tempo real."""
        search_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        search_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_global_search_change())

        self.entry_search = ctk.CTkEntry(
            search_frame, textvariable=self.search_var,
            placeholder_text="🔍 Pesquisar em todo o save (itens, armas, heróis, switches, variáveis)...",
            height=36, corner_radius=8, font=ctk.CTkFont(size=13)
        )
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_clear_search = ctk.CTkButton(
            search_frame, text="✕ Limpar", width=70, height=36,
            fg_color="transparent", border_width=1, border_color=BORDER_COLOR,
            command=lambda: self.search_var.set("")
        )
        btn_clear_search.pack(side="right")

    def _create_tabview(self):
        """Abas principais especializadas."""
        self.tabview = ctk.CTkTabview(self, corner_radius=10, fg_color=BG_CARD, command=self._on_tab_change)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Criação das Abas
        self.tab_overview = self.tabview.add("📊 Visão Geral & Cheats")
        self.tab_actors = self.tabview.add("👥 Personagens & Atributos")
        self.tab_inventory = self.tabview.add("🎒 Inventário")
        self.tab_switches = self.tabview.add("⚙ Switches & Variáveis")
        self.tab_advanced = self.tabview.add("🌲 Modo Avançado / Árvore")

        self._build_overview_tab()
        self._build_actors_tab()
        self._build_inventory_tab()
        self._build_switches_tab()
        self._build_advanced_tab()

    def _create_status_bar(self):
        """Barra inferior de status e logs."""
        status_frame = ctk.CTkFrame(self, fg_color=BG_CARD, height=32, corner_radius=6)
        status_frame.pack(fill="x", padx=12, pady=(0, 8))

        self.lbl_status = ctk.CTkLabel(
            status_frame, text="Pronto. Arraste um save ou clique em 'Abrir Save'.",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=12), anchor="w"
        )
        self.lbl_status.pack(side="left", fill="x", expand=True, padx=10, pady=4)

        self.lbl_db_status = ctk.CTkLabel(
            status_frame, text="⚡ BD: Não conectado",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_db_status.pack(side="right", padx=10, pady=4)

    # --- Construção da Aba: Visão Geral ---

    def _build_overview_tab(self):
        t = self.tab_overview

        # Grid 2 colunas: Esquerda (Ouro & Info), Direita (Cheats Rápidos)
        container = ctk.CTkFrame(t, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        left = ctk.CTkFrame(container, fg_color=BG_SUB, corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        right = ctk.CTkFrame(container, fg_color=BG_SUB, corner_radius=8)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        # Left: Card de Ouro
        ctk.CTkLabel(left, text="💰 Finanças & Ouro", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(14, 6))

        gold_row = ctk.CTkFrame(left, fg_color="transparent")
        gold_row.pack(fill="x", padx=14, pady=4)

        self.entry_gold = ctk.CTkEntry(gold_row, font=ctk.CTkFont(size=20, weight="bold"), height=42)
        self.entry_gold.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_set_gold = ctk.CTkButton(gold_row, text="Aplicar", width=80, height=42, command=self._apply_gold_from_entry)
        btn_set_gold.pack(side="right")

        # Botões rápidos de ouro
        quick_gold_frame = ctk.CTkFrame(left, fg_color="transparent")
        quick_gold_frame.pack(fill="x", padx=14, pady=(6, 14))

        ctk.CTkButton(quick_gold_frame, text="+10.000", width=80, command=lambda: self._add_gold(10000)).pack(side="left", padx=2)
        ctk.CTkButton(quick_gold_frame, text="+100.000", width=85, command=lambda: self._add_gold(100000)).pack(side="left", padx=2)
        ctk.CTkButton(quick_gold_frame, text="+1.000.000", width=95, command=lambda: self._add_gold(1000000)).pack(side="left", padx=2)
        ctk.CTkButton(quick_gold_frame, text="Max (99.9M)", width=95, fg_color=WARNING_COLOR, hover_color=WARNING_HOVER, command=lambda: self._set_gold(99999999)).pack(side="left", padx=2)
        ctk.CTkButton(quick_gold_frame, text="Zerar", width=60, fg_color=DANGER_COLOR, hover_color=DANGER_HOVER, command=lambda: self._set_gold(0)).pack(side="left", padx=2)

        # Info de Jogo
        ctk.CTkLabel(left, text="🎮 Status da Campanha", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(16, 6))

        self.lbl_playtime = ctk.CTkLabel(left, text="Tempo de Jogo: N/A", font=ctk.CTkFont(size=13))
        self.lbl_playtime.pack(anchor="w", padx=14, pady=2)

        self.lbl_steps = ctk.CTkLabel(left, text="Passos Dados: N/A", font=ctk.CTkFont(size=13))
        self.lbl_steps.pack(anchor="w", padx=14, pady=2)

        self.lbl_save_file_info = ctk.CTkLabel(left, text="Arquivo: Nenhum", font=ctk.CTkFont(size=13), text_color=TEXT_MUTED)
        self.lbl_save_file_info.pack(anchor="w", padx=14, pady=2)

        # Right: Cheats Rápidos (Ações em Lote)
        ctk.CTkLabel(right, text="⚡ Ações Rápidas em Lote (1 Clique)", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(14, 10))

        btn_heal = ctk.CTkButton(
            right, text="💖 Curar Todo o Grupo (HP & MP Máximos)", height=40,
            fg_color=SUCCESS_COLOR, hover_color=SUCCESS_HOVER, font=ctk.CTkFont(weight="bold"),
            command=self._quick_heal_all
        )
        btn_heal.pack(fill="x", padx=14, pady=6)

        btn_level = ctk.CTkButton(
            right, text="⭐ Subir Nível de Todos os Heróis (+5 Níveis)", height=40,
            command=self._quick_level_up_all
        )
        btn_level.pack(fill="x", padx=14, pady=6)

        btn_max_all_stats = ctk.CTkButton(
            right, text="💥 Maximizar Status de Todos os Heróis (999)", height=40,
            command=self._quick_max_stats_all
        )
        btn_max_all_stats.pack(fill="x", padx=14, pady=6)

        btn_unlock_items = ctk.CTkButton(
            right, text="🎁 Desbloquear Todos os Itens do Jogo (x99)", height=40,
            command=lambda: self._quick_unlock_all("items")
        )
        btn_unlock_items.pack(fill="x", padx=14, pady=6)

        btn_unlock_weapons = ctk.CTkButton(
            right, text="⚔ Desbloquear Todas as Armas do Jogo (x1)", height=40,
            command=lambda: self._quick_unlock_all("weapons", 1)
        )
        btn_unlock_weapons.pack(fill="x", padx=14, pady=6)

        btn_unlock_armors = ctk.CTkButton(
            right, text="🛡 Desbloquear Todas as Armaduras do Jogo (x1)", height=40,
            command=lambda: self._quick_unlock_all("armors", 1)
        )
        btn_unlock_armors.pack(fill="x", padx=14, pady=6)

    # --- Construção da Aba: Personagens & Atributos ---

    def _build_actors_tab(self):
        t = self.tab_actors

        paned = ctk.CTkFrame(t, fg_color="transparent")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # Lista lateral de atores
        left = ctk.CTkFrame(paned, fg_color=BG_SUB, width=280, corner_radius=8)
        left.pack(side="left", fill="y", padx=(0, 6))

        ctk.CTkLabel(left, text="Heróis & Atores", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 6))

        self.actors_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.actors_scroll.pack(fill="both", expand=True, padx=6, pady=6)

        # Painel direito: Atributos do ator selecionado
        right = ctk.CTkFrame(paned, fg_color=BG_SUB, corner_radius=8)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        self.lbl_selected_actor_name = ctk.CTkLabel(
            right, text="Selecione um personagem ao lado",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.lbl_selected_actor_name.pack(anchor="w", padx=16, pady=(14, 8))

        # Campos de Atributos em Grid
        self.actor_fields_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.actor_fields_frame.pack(fill="both", expand=True, padx=16, pady=4)

        self.actor_entries: Dict[str, ctk.CTkEntry] = {}
        fields = [
            ("level", "Nível:"),
            ("hp", "HP Atual:"),
            ("max_hp", "HP Máximo:"),
            ("mp", "MP Atual:"),
            ("max_mp", "MP Máximo:"),
            ("tp", "TP:"),
            ("atk", "Ataque (ATK):"),
            ("def", "Defesa (DEF):"),
            ("mat", "Ataque Mágico (MAT):"),
            ("mdf", "Defesa Mágica (MDF):"),
            ("agi", "Agilidade (AGI):"),
            ("luk", "Sorte (LUK):"),
        ]

        for i, (key, label) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2

            lbl = ctk.CTkLabel(self.actor_fields_frame, text=label, font=ctk.CTkFont(size=13))
            lbl.grid(row=row, column=col, sticky="w", padx=(6, 6), pady=6)

            ent = ctk.CTkEntry(self.actor_fields_frame, width=140, height=32)
            ent.grid(row=row, column=col+1, sticky="w", padx=(0, 16), pady=6)
            self.actor_entries[key] = ent

        # Botões do Ator
        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(10, 16))

        btn_save_actor = ctk.CTkButton(
            btn_row, text="💾 Aplicar ao Personagem", width=160, height=36,
            command=self._save_current_actor_stats, fg_color=SUCCESS_COLOR, hover_color=SUCCESS_HOVER
        )
        btn_save_actor.pack(side="left", padx=(0, 8))

        btn_max_actor = ctk.CTkButton(
            btn_row, text="⭐ Maximizar Status", width=140, height=36,
            command=self._max_current_actor_stats
        )
        btn_max_actor.pack(side="left", padx=4)

        btn_heal_actor = ctk.CTkButton(
            btn_row, text="💖 Curar Totalmente", width=140, height=36,
            command=self._heal_current_actor
        )
        btn_heal_actor.pack(side="left", padx=4)

    # --- Construção da Aba: Inventário ---

    def _build_inventory_tab(self):
        t = self.tab_inventory

        # Barra superior do inventário
        top_inv = ctk.CTkFrame(t, fg_color="transparent")
        top_inv.pack(fill="x", padx=10, pady=(10, 6))

        self.seg_inv = ctk.CTkSegmentedButton(
            top_inv, values=["Itens Consumíveis", "Armas", "Armaduras"],
            command=self._on_inv_segment_change
        )
        self.seg_inv.set("Itens Consumíveis")
        self.seg_inv.pack(side="left", padx=(0, 10))

        btn_add_item = ctk.CTkButton(
            top_inv, text="➕ Adicionar Item", width=120,
            command=self._add_new_item_dialog
        )
        btn_add_item.pack(side="left", padx=4)

        btn_max_present = ctk.CTkButton(
            top_inv, text="⭐ Max 99 (Existentes)", width=150,
            command=self._max_existing_inventory
        )
        btn_max_present.pack(side="left", padx=4)

        btn_unlock_all = ctk.CTkButton(
            top_inv, text="🌟 Desbloquear Todos (BD)", width=170,
            command=self._unlock_all_current_kind
        )
        btn_unlock_all.pack(side="left", padx=4)

        self.lbl_inv_count = ctk.CTkLabel(top_inv, text="", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12))
        self.lbl_inv_count.pack(side="right", padx=10)

        # Container da Tabela com Bordas
        table_container = ctk.CTkFrame(t, fg_color=BG_CARD, corner_radius=8)
        table_container.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # Tabela Treeview de Alta Performance
        self.tree_inv = ttk.Treeview(
            table_container,
            columns=("id", "name", "qty"),
            show="headings",
            style="Modern.Treeview",
            selectmode="browse"
        )
        self.tree_inv.heading("id", text="# ID  ▲▼", command=lambda: self._sort_inventory("id"))
        self.tree_inv.heading("name", text="Nome do Item / Equipamento  ▲▼", command=lambda: self._sort_inventory("name"))
        self.tree_inv.heading("qty", text="Quantidade  ▲▼", command=lambda: self._sort_inventory("qty"))

        self.tree_inv.column("id", width=80, anchor="center")
        self.tree_inv.column("name", width=520, stretch=True, anchor="w")
        self.tree_inv.column("qty", width=120, anchor="e")

        sb_y = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_inv.yview)
        self.tree_inv.configure(yscrollcommand=sb_y.set)

        self.tree_inv.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb_y.pack(side="right", fill="y", padx=(0, 4), pady=4)

        self.tree_inv.bind("<<TreeviewSelect>>", self._on_inv_select)
        self.tree_inv.bind("<Double-1>", self._on_inv_double_click)
        self.tree_inv.bind("<Return>", lambda e: self.ent_inv_qty.focus_set())
        self.tree_inv.bind("<Delete>", lambda e: self._set_selected_inv_qty(0))

        # Barra Inferior de Edição Rápida
        bottom_bar = ctk.CTkFrame(t, fg_color=BG_CARD, height=44, corner_radius=8)
        bottom_bar.pack(fill="x", padx=10, pady=(0, 10))

        self.lbl_selected_inv = ctk.CTkLabel(
            bottom_bar, text="Selecione um item na lista acima para editar",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        )
        self.lbl_selected_inv.pack(side="left", padx=14, fill="x", expand=True)

        ctk.CTkLabel(bottom_bar, text="Qtd:", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MUTED).pack(side="left", padx=(6, 2))

        self.ent_inv_qty = ctk.CTkEntry(bottom_bar, width=70, height=30)
        self.ent_inv_qty.pack(side="left", padx=4)
        self.ent_inv_qty.bind("<Return>", lambda e: self._apply_inv_qty_from_entry())
        self.ent_inv_qty.bind("<FocusOut>", lambda e: self._apply_inv_qty_from_entry())

        btn_save_qty = ctk.CTkButton(
            bottom_bar, text="Definir", width=65, height=30,
            command=self._apply_inv_qty_from_entry, fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER
        )
        btn_save_qty.pack(side="left", padx=2)

        ctk.CTkButton(bottom_bar, text="-1", width=38, height=30, command=lambda: self._step_inv_qty(-1)).pack(side="left", padx=2)
        ctk.CTkButton(bottom_bar, text="+1", width=38, height=30, command=lambda: self._step_inv_qty(1)).pack(side="left", padx=2)
        ctk.CTkButton(bottom_bar, text="+10", width=44, height=30, command=lambda: self._step_inv_qty(10)).pack(side="left", padx=2)
        ctk.CTkButton(bottom_bar, text="99 (Max)", width=70, height=30, command=lambda: self._set_selected_inv_qty(99)).pack(side="left", padx=2)
        ctk.CTkButton(
            bottom_bar, text="✕ Remover", width=80, height=30,
            fg_color=DANGER_COLOR, hover_color=DANGER_HOVER,
            command=lambda: self._set_selected_inv_qty(0)
        ).pack(side="left", padx=(2, 10))

    # --- Construção da Aba: Switches & Variáveis ---

    def _build_switches_tab(self):
        t = self.tab_switches

        top_sys = ctk.CTkFrame(t, fg_color="transparent")
        top_sys.pack(fill="x", padx=10, pady=(10, 6))

        self.seg_system = ctk.CTkSegmentedButton(
            top_sys, values=["Switches (Interruptores)", "Variáveis de Jogo"],
            command=self._on_system_segment_change
        )
        self.seg_system.set("Switches (Interruptores)")
        self.seg_system.pack(side="left", padx=(0, 10))

        self.lbl_system_count = ctk.CTkLabel(top_sys, text="0 itens encontrados", text_color=TEXT_MUTED)
        self.lbl_system_count.pack(side="left", padx=10)

        # Container da Tabela
        table_container = ctk.CTkFrame(t, fg_color=BG_CARD, corner_radius=8)
        table_container.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self.tree_sys = ttk.Treeview(
            table_container,
            columns=("id", "name", "val"),
            show="headings",
            style="Modern.Treeview",
            selectmode="browse"
        )
        self.tree_sys.heading("id", text="# ID  ▲▼", command=lambda: self._sort_system("id"))
        self.tree_sys.heading("name", text="Nome  ▲▼", command=lambda: self._sort_system("name"))
        self.tree_sys.heading("val", text="Estado (ON / OFF)  ▲▼", command=lambda: self._sort_system("val"))

        self.tree_sys.column("id", width=80, anchor="center")
        self.tree_sys.column("name", width=550, stretch=True, anchor="w")
        self.tree_sys.column("val", width=160, anchor="center")

        sb_sys = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_sys.yview)
        self.tree_sys.configure(yscrollcommand=sb_sys.set)

        self.tree_sys.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb_sys.pack(side="right", fill="y", padx=(0, 4), pady=4)

        self.tree_sys.bind("<<TreeviewSelect>>", self._on_system_select)
        self.tree_sys.bind("<space>", lambda e: self._toggle_selected_switch())
        self.tree_sys.bind("<Double-1>", lambda e: self._on_system_double_click())

        # Tags visuais de destaque
        self.tree_sys.tag_configure("on", foreground="#10B981")
        self.tree_sys.tag_configure("off", foreground="#94A3B8")

        # Barra inferior de Ações Rápidas
        bottom_sys = ctk.CTkFrame(t, fg_color=BG_CARD, height=44, corner_radius=8)
        bottom_sys.pack(fill="x", padx=10, pady=(0, 10))

        self.lbl_selected_sys = ctk.CTkLabel(
            bottom_sys, text="Selecione uma switch ou variável acima",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        )
        self.lbl_selected_sys.pack(side="left", padx=14, fill="x", expand=True)

        # Controles de Switch
        self.btn_toggle_sys = ctk.CTkButton(
            bottom_sys, text="⚡ Alternar Switch (Espaço)", width=190, height=30,
            command=self._toggle_selected_switch, fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER
        )
        self.btn_toggle_sys.pack(side="right", padx=10)

        # Controles de Variável
        self.frame_var_edit = ctk.CTkFrame(bottom_sys, fg_color="transparent")
        ctk.CTkLabel(self.frame_var_edit, text="Novo Valor:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=4)
        self.ent_var_val = ctk.CTkEntry(self.frame_var_edit, width=130, height=30)
        self.ent_var_val.pack(side="left", padx=4)
        self.ent_var_val.bind("<Return>", lambda e: self._save_selected_variable())
        ctk.CTkButton(
            self.frame_var_edit, text="💾 Salvar (Enter)", width=105, height=30,
            command=self._save_selected_variable, fg_color=SUCCESS_COLOR, hover_color=SUCCESS_HOVER
        ).pack(side="left", padx=4)

    # --- Construção da Aba: Avançado (Árvore) ---

    def _build_advanced_tab(self):
        t = self.tab_advanced

        split = ttk.Panedwindow(t, orient="horizontal")
        split.pack(fill="both", expand=True, padx=6, pady=6)

        left = ttk.LabelFrame(split, text="Estrutura Completa de Dados")
        right = ttk.LabelFrame(split, text="Editor Direto")
        split.add(left, weight=3)
        split.add(right, weight=2)

        # Treeview de inspeção com lazy loading de nós
        self.tree = ttk.Treeview(left, columns=("value",), show="tree headings", style="Modern.Treeview")
        self.tree.heading("#0", text="Chave / Caminho")
        self.tree.heading("value", text="Valor")
        self.tree.column("#0", width=380, stretch=True)
        self.tree.column("value", width=220, stretch=True)

        ysb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=ysb.set, xscroll=xsb.set)
        self.tree.pack(fill="both", expand=True, side="left")
        ysb.pack(fill="y", side="right")
        xsb.pack(fill="x", side="bottom")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)

        # Editor de campo na direita
        ed_frame = ttk.Frame(right, padding=10)
        ed_frame.pack(fill="both", expand=True)

        ttk.Label(ed_frame, text="Valor do Campo Selecionado:", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self.entry_tree_val = ttk.Entry(ed_frame)
        self.entry_tree_val.pack(fill="x", pady=4)

        ttk.Button(ed_frame, text="Salvar Valor do Campo", command=self._save_tree_val).pack(fill="x", pady=4)

        self._tree_item_to_path = {}
        self._selected_tree_node = None

    # --- Ações de Arquivo & Carregamento ---

    def open_file_dialog(self):
        p = filedialog.askopenfilename(
            title="Selecione o Save de RPG Maker",
            filetypes=[
                ("Todos os Saves Suportados", "*.rpgsave;*.rmmzsave;*.rvdata2;*.rvdata;*.rxdata;*.lsd;*.json;*.sav;*.dat"),
                ("RPG Maker MV (*.rpgsave)", "*.rpgsave"),
                ("RPG Maker MZ (*.rmmzsave)", "*.rmmzsave"),
                ("RPG Maker VX Ace (*.rvdata2)", "*.rvdata2"),
                ("RPG Maker VX (*.rvdata)", "*.rvdata"),
                ("RPG Maker XP (*.rxdata)", "*.rxdata"),
                ("RPG Maker 2000/2003 (*.lsd)", "*.lsd"),
                ("JSON / Decrypted (*.json)", "*.json"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]
        )
        if p:
            self.load_save_file(p)

    def _on_drop_file(self, event):
        files = self.tk.splitlist(event.data)
        if files:
            self.load_save_file(files[0])

    def load_save_file(self, file_path: str | Path, synchronous: bool = False):
        p = Path(file_path).resolve()
        if not p.is_file():
            return

        def work():
            # 1. Descoberta automática de Banco de Dados
            db_found = self.db.discover_and_load(p)

            # 2. Detecção e criação de adaptador
            adapter = detect_and_create_adapter(p, self.db)
            adapter.load(p)

            self.adapter = adapter
            self.current_file = p
            return db_found

        if synchronous:
            db_found = work()
            self._on_load_success(db_found)
            return

        def task():
            self.queue_ui(self._set_status, f"Carregando {p.name}...", True)
            try:
                db_found = work()
                self.queue_ui(self._on_load_success, db_found)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.queue_ui(self._on_load_error, str(e))

        threading.Thread(target=task, daemon=True).start()

    def _on_load_success(self, db_found: bool):
        if not self.adapter or not self.current_file:
            return

        self.lbl_engine_badge.configure(
            text=f"{self.adapter.engine_name} ({self.adapter.compression})",
            text_color=TEXT_MAIN
        )
        self.lbl_save_file_info.configure(text=f"Arquivo: {self.current_file.name}")

        db_summary = self.db.summary_info()
        if db_found:
            self.lbl_db_status.configure(
                text=f"⚡ BD: Conectado ({db_summary})",
                text_color=SUCCESS_COLOR[1]
            )
        else:
            self.lbl_db_status.configure(
                text="⚡ BD: Não conectado (Use 'Pasta do Jogo')",
                text_color=WARNING_COLOR[1]
            )

        self._refresh_all_views()
        self._update_dirty_indicator()
        self._set_status(f"Save '{self.current_file.name}' carregado com sucesso!")

    def _on_load_error(self, err_msg: str):
        messagebox.showerror("Erro ao abrir save", f"Não foi possível ler o arquivo:\n\n{err_msg}")
        self._set_status("Erro ao carregar arquivo.", False)

    def _on_tab_change(self):
        """Callback acionado ao trocar de aba: atualiza apenas a aba que ficou ativa se estiver pendente."""
        if not self.adapter: return
        curr_tab = self.tabview.get()
        if "Visão Geral" in curr_tab:
            if self.tabs_need_refresh.get("overview"):
                self._refresh_overview()
                self.tabs_need_refresh["overview"] = False
        elif "Personagens" in curr_tab:
            if self.tabs_need_refresh.get("actors"):
                self._refresh_actors()
                self.tabs_need_refresh["actors"] = False
        elif "Inventário" in curr_tab:
            if self.tabs_need_refresh.get("inventory"):
                self._refresh_inventory()
                self.tabs_need_refresh["inventory"] = False
        elif "Switches" in curr_tab:
            if self.tabs_need_refresh.get("switches"):
                self._refresh_switches()
                self.tabs_need_refresh["switches"] = False
        elif "Avançado" in curr_tab:
            if self.tabs_need_refresh.get("advanced"):
                self._populate_tree()
                self.tabs_need_refresh["advanced"] = False

    def _refresh_all_views(self):
        """Atualiza a aba ativa imediatamente e invalida o cache das demais para lazy loading."""
        if not self.adapter:
            return

        for k in self.tabs_need_refresh:
            self.tabs_need_refresh[k] = True

        # Sempre atualiza a visão geral
        self._refresh_overview()
        self.tabs_need_refresh["overview"] = False

        # Se o usuário já estiver navegando em outra aba, atualiza-a agora
        curr_tab = self.tabview.get()
        if "Personagens" in curr_tab:
            self._refresh_actors()
            self.tabs_need_refresh["actors"] = False
        elif "Inventário" in curr_tab:
            self._refresh_inventory()
            self.tabs_need_refresh["inventory"] = False
        elif "Switches" in curr_tab:
            self._refresh_switches()
            self.tabs_need_refresh["switches"] = False
        elif "Avançado" in curr_tab:
            self._populate_tree()
            self.tabs_need_refresh["advanced"] = False

    def _update_dirty_indicator(self):
        if not self.adapter:
            self.lbl_dirty_badge.configure(text="✓ Salvo", text_color=SUCCESS_COLOR[1])
            return

        if self.adapter.dirty:
            cnt = self.adapter.get_pending_changes_count()
            self.lbl_dirty_badge.configure(
                text=f"● {cnt} alterações não salvas",
                text_color=WARNING_COLOR[1]
            )
        else:
            self.lbl_dirty_badge.configure(text="✓ Salvo", text_color=SUCCESS_COLOR[1])

    def _set_status(self, msg: str, busy: bool = False):
        self.lbl_status.configure(text=msg)

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        new_mode = "light" if current == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        self._setup_treeview_styles(new_mode)

    def select_game_data_dir(self):
        """Permite selecionar manualmente a pasta de dados do jogo."""
        d = filedialog.askdirectory(title="Selecione a pasta 'data' do jogo (com Items.json, etc.)")
        if not d:
            return
        if self.db.load_directory(d):
            self.lbl_db_status.configure(
                text=f"⚡ BD: Conectado ({self.db.summary_info()})",
                text_color=SUCCESS_COLOR[1]
            )
            self._refresh_all_views()
            messagebox.showinfo("Banco de Dados", f"Banco de dados carregado com sucesso!\n{self.db.summary_info()}")
        else:
            messagebox.showwarning("Aviso", "Nenhum arquivo de banco de dados válido encontrado na pasta selecionada.")

    # --- Lógica da Aba: Visão Geral ---

    def _refresh_overview(self):
        if not self.adapter: return
        gold = self.adapter.get_gold()
        curr = self.db.get_currency_unit()
        self.entry_gold.delete(0, "end")
        self.entry_gold.insert(0, str(gold))

        playtime, steps = self.adapter.get_playtime_and_steps()
        self.lbl_playtime.configure(text=f"Tempo de Jogo: {playtime}")
        self.lbl_steps.configure(text=f"Passos Dados: {steps:,}")

    def _apply_gold_from_entry(self):
        if not self.adapter: return
        try:
            val = int(self.entry_gold.get().replace(".", "").replace(",", "").strip())
            self.adapter.set_gold(val)
            self._update_dirty_indicator()
            self._set_status(f"Ouro definido para {val:,}")
        except Exception:
            messagebox.showwarning("Valor inválido", "Por favor digite um número válido para o ouro.")

    def _add_gold(self, amount: int):
        if not self.adapter: return
        cur = self.adapter.get_gold()
        new_val = cur + amount
        self.adapter.set_gold(new_val)
        self.entry_gold.delete(0, "end")
        self.entry_gold.insert(0, str(new_val))
        self._update_dirty_indicator()
        self._set_status(f"Adicionado {amount:,} de ouro!")

    def _set_gold(self, val: int):
        if not self.adapter: return
        self.adapter.set_gold(val)
        self.entry_gold.delete(0, "end")
        self.entry_gold.insert(0, str(val))
        self._update_dirty_indicator()
        self._set_status(f"Ouro definido para {val:,}!")

    def _quick_heal_all(self):
        if not self.adapter: return
        actors = self.adapter.get_actors()
        for a in actors:
            max_hp = a.get("max_hp", 9999) or 9999
            max_mp = a.get("max_mp", 999) or 999
            self.adapter.update_actor(a["id"], {"hp": max_hp, "mp": max_mp})
        self.tabs_need_refresh["actors"] = True
        self.tabs_need_refresh["advanced"] = True
        curr_tab = self.tabview.get()
        if "Personagens" in curr_tab:
            self._refresh_actors()
            self.tabs_need_refresh["actors"] = False
        self._update_dirty_indicator()
        self._set_status("💖 Todos os membros do grupo foram totalmente curados!")

    def _quick_level_up_all(self):
        if not self.adapter: return
        actors = self.adapter.get_actors()
        for a in actors:
            new_lvl = min(999, a.get("level", 1) + 5)
            self.adapter.update_actor(a["id"], {"level": new_lvl})
        self.tabs_need_refresh["actors"] = True
        self.tabs_need_refresh["advanced"] = True
        curr_tab = self.tabview.get()
        if "Personagens" in curr_tab:
            self._refresh_actors()
            self.tabs_need_refresh["actors"] = False
        self._update_dirty_indicator()
        self._set_status("⭐ Todos os heróis subiram +5 níveis!")

    def _quick_max_stats_all(self):
        if not self.adapter: return
        actors = self.adapter.get_actors()
        for a in actors:
            self.adapter.update_actor(a["id"], {
                "level": 99,
                "max_hp": 9999,
                "hp": 9999,
                "max_mp": 999,
                "mp": 999,
                "atk": 999,
                "def": 999,
                "mat": 999,
                "mdf": 999,
                "agi": 999,
                "luk": 999
            })
        self.tabs_need_refresh["actors"] = True
        self.tabs_need_refresh["advanced"] = True
        curr_tab = self.tabview.get()
        if "Personagens" in curr_tab:
            self._refresh_actors()
            self.tabs_need_refresh["actors"] = False
        self._update_dirty_indicator()
        self._set_status("💥 Todos os heróis foram maximizados com status supremos!")

    def _quick_unlock_all(self, kind: str, qty: int = 99):
        if not self.adapter: return
        count = self.adapter.unlock_all_items(kind, qty)
        self.tabs_need_refresh["inventory"] = True
        self.tabs_need_refresh["advanced"] = True
        curr_tab = self.tabview.get()
        if "Inventário" in curr_tab:
            self._refresh_inventory()
            self.tabs_need_refresh["inventory"] = False
        self._update_dirty_indicator()
        kind_name = "itens" if kind == "items" else ("armas" if kind == "weapons" else "armaduras")
        self._set_status(f"✔ Desbloqueados {count} {kind_name} (x{qty}) com sucesso!")

    # --- Lógica da Aba: Personagens ---

    def _refresh_actors(self):
        if not self.adapter: return

        for w in self.actors_scroll.winfo_children():
            w.destroy()

        actors = self.adapter.get_actors()
        query = self.search_var.get().strip().lower()

        filtered_actors = []
        for a in actors:
            if query:
                if query not in str(a["name"]).lower() and query not in str(a["id"]):
                    continue
            filtered_actors.append(a)

        if not filtered_actors:
            lbl = ctk.CTkLabel(self.actors_scroll, text="Nenhum herói encontrado", text_color=TEXT_MUTED)
            lbl.pack(pady=10)
            return

        for a in filtered_actors:
            name = a["name"]
            lvl = a["level"]
            aid = a["id"]

            btn = ctk.CTkButton(
                self.actors_scroll,
                text=f"{name}\n(Nível {lvl})",
                fg_color=PRIMARY_COLOR if str(aid) == str(self.selected_actor_id) else "transparent",
                border_width=1, border_color=BORDER_COLOR,
                command=lambda act=a: self._select_actor(act)
            )
            btn.pack(fill="x", pady=3)

        if not self.selected_actor_id and filtered_actors:
            self._select_actor(filtered_actors[0])

    def _select_actor(self, actor_dict: Dict[str, Any]):
        self.selected_actor_id = actor_dict["id"]
        name = actor_dict["name"]
        aid = actor_dict["id"]
        self.lbl_selected_actor_name.configure(text=f"Herói: {name} (ID #{aid})")

        for key, ent in self.actor_entries.items():
            val = actor_dict.get(key, 0)
            ent.delete(0, "end")
            ent.insert(0, str(val))

    def _save_current_actor_stats(self):
        if not self.adapter or not self.selected_actor_id: return
        stats = {}
        for k, ent in self.actor_entries.items():
            txt = ent.get().strip()
            if txt.isdigit():
                stats[k] = int(txt)
        self.adapter.update_actor(self.selected_actor_id, stats)
        self._refresh_actors()
        self._update_dirty_indicator()
        self._set_status(f"Atributos do herói #{self.selected_actor_id} salvos!")

    def _max_current_actor_stats(self):
        if not self.adapter or not self.selected_actor_id: return
        stats = {
            "level": 99,
            "max_hp": 9999, "hp": 9999,
            "max_mp": 999, "mp": 999,
            "atk": 999, "def": 999, "mat": 999, "mdf": 999, "agi": 999, "luk": 999
        }
        for k, v in stats.items():
            if k in self.actor_entries:
                self.actor_entries[k].delete(0, "end")
                self.actor_entries[k].insert(0, str(v))
        self._save_current_actor_stats()

    def _heal_current_actor(self):
        if not self.adapter or not self.selected_actor_id: return
        max_hp = int(self.actor_entries["max_hp"].get() or 999)
        max_mp = int(self.actor_entries["max_mp"].get() or 99)
        self.actor_entries["hp"].delete(0, "end")
        self.actor_entries["hp"].insert(0, str(max_hp))
        self.actor_entries["mp"].delete(0, "end")
        self.actor_entries["mp"].insert(0, str(max_mp))
        self._save_current_actor_stats()

    # --- Lógica da Aba: Inventário (Alta Performance) ---

    def _on_inv_segment_change(self, val):
        mapping = {
            "Itens Consumíveis": "items",
            "Armas": "weapons",
            "Armaduras": "armors"
        }
        self.current_inv_kind = mapping.get(val, "items")
        self._refresh_inventory()

    def _refresh_inventory(self):
        if not self.adapter: return

        self.tree_inv.delete(*self.tree_inv.get_children())
        inv = self.adapter.get_inventory(self.current_inv_kind)
        query = self.search_var.get().strip().lower()

        filtered = []
        for it in inv:
            if query:
                if query not in str(it["name"]).lower() and query not in str(it["id"]):
                    continue
            filtered.append(it)

        # Ordenação
        reverse = self._inv_sort_desc
        if self._inv_sort_col == "id":
            filtered.sort(key=lambda x: int(x["id"]) if str(x["id"]).isdigit() else str(x["id"]), reverse=reverse)
        elif self._inv_sort_col == "name":
            filtered.sort(key=lambda x: str(x["name"]).lower(), reverse=reverse)
        elif self._inv_sort_col == "qty":
            filtered.sort(key=lambda x: int(x.get("quantity", 0)), reverse=reverse)

        for it in filtered:
            i_id_raw = str(it["id"])
            i_id_fmt = f"#{i_id_raw.zfill(3)}" if i_id_raw.isdigit() else f"#{i_id_raw}"
            self.tree_inv.insert("", "end", iid=str(it["id"]), values=(i_id_fmt, it["name"], str(it["quantity"])))

        kind_display = "itens" if self.current_inv_kind == "items" else ("armas" if self.current_inv_kind == "weapons" else "armaduras")
        self.lbl_inv_count.configure(text=f"{len(filtered)} de {len(inv)} {kind_display}")

        # Se havia item selecionado e ainda existe, restaura seleção
        if self._selected_inv_id and self.tree_inv.exists(self._selected_inv_id):
            self.tree_inv.selection_set(self._selected_inv_id)
            self.tree_inv.see(self._selected_inv_id)
        else:
            self._selected_inv_id = None
            self.lbl_selected_inv.configure(text="Selecione um item na lista acima para editar")
            self.ent_inv_qty.delete(0, "end")

    def _sort_inventory(self, col: str):
        if self._inv_sort_col == col:
            self._inv_sort_desc = not self._inv_sort_desc
        else:
            self._inv_sort_col = col
            self._inv_sort_desc = False

        arrow = "▼" if self._inv_sort_desc else "▲"
        self.tree_inv.heading("id", text=f"# ID {' ' + arrow if col == 'id' else ' ▲▼'}")
        self.tree_inv.heading("name", text=f"Nome do Item / Equipamento {' ' + arrow if col == 'name' else ' ▲▼'}")
        self.tree_inv.heading("qty", text=f"Quantidade {' ' + arrow if col == 'qty' else ' ▲▼'}")
        self._refresh_inventory()

    def _on_inv_select(self, event=None):
        sel = self.tree_inv.selection()
        if not sel: return
        item_id = sel[0]
        self._selected_inv_id = item_id
        values = self.tree_inv.item(item_id, "values")
        if values:
            id_fmt, name, qty = values
            self.lbl_selected_inv.configure(text=f"{id_fmt} — {name} (Atual: {qty})")
            self.ent_inv_qty.delete(0, "end")
            self.ent_inv_qty.insert(0, str(qty))

    def _on_inv_double_click(self, event=None):
        self._on_inv_select()
        self.ent_inv_qty.focus_set()
        self.ent_inv_qty.select_range(0, "end")

    def _apply_inv_qty_from_entry(self):
        if not self.adapter or not self._selected_inv_id: return
        txt = self.ent_inv_qty.get().strip()
        if not txt.isdigit():
            return
        new_q = int(txt)
        self._set_selected_inv_qty(new_q)

    def _step_inv_qty(self, delta: int):
        if not self.adapter or not self._selected_inv_id: return
        try:
            curr = int(self.ent_inv_qty.get() or 0)
        except ValueError:
            curr = 0
        new_q = max(0, curr + delta)
        self._set_selected_inv_qty(new_q)

    def _set_selected_inv_qty(self, val: int):
        if not self.adapter or not self._selected_inv_id: return
        self.adapter.set_item_quantity(self.current_inv_kind, self._selected_inv_id, val)
        self._update_dirty_indicator()

        # Atualiza a linha na Treeview instantaneamente (0.0001s)
        if self.tree_inv.exists(self._selected_inv_id):
            if val == 0:
                self.tree_inv.delete(self._selected_inv_id)
                self._selected_inv_id = None
                self.lbl_selected_inv.configure(text="Item removido do inventário.")
                self.ent_inv_qty.delete(0, "end")
            else:
                self.tree_inv.set(self._selected_inv_id, "qty", str(val))
                values = self.tree_inv.item(self._selected_inv_id, "values")
                if values:
                    self.lbl_selected_inv.configure(text=f"{values[0]} — {values[1]} (Atual: {val})")
                self.ent_inv_qty.delete(0, "end")
                self.ent_inv_qty.insert(0, str(val))

    def _add_new_item_dialog(self):
        if not self.adapter: return

        known = []
        if self.current_inv_kind == "items": known = self.db.get_all_known_items()
        elif self.current_inv_kind == "weapons": known = self.db.get_all_known_weapons()
        elif self.current_inv_kind == "armors": known = self.db.get_all_known_armors()

        dlg = ctk.CTkToplevel(self)
        dlg.title("Adicionar Item ao Inventário")
        dlg.geometry("460x420")
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Escolha ou digite o ID do item:", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=16, pady=(16, 6), anchor="w")

        entry_search_item = ctk.CTkEntry(dlg, placeholder_text="Filtrar itens conhecidos...")
        entry_search_item.pack(fill="x", padx=16, pady=4)

        tree_dlg = ttk.Treeview(dlg, columns=("id", "name"), show="headings", style="Modern.Treeview", height=8)
        tree_dlg.heading("id", text="# ID")
        tree_dlg.heading("name", text="Nome do Item")
        tree_dlg.column("id", width=70, anchor="center")
        tree_dlg.column("name", width=330, anchor="w")

        sb_dlg = ttk.Scrollbar(dlg, orient="vertical", command=tree_dlg.yview)
        tree_dlg.configure(yscrollcommand=sb_dlg.set)

        tree_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=16, pady=6)
        tree_dlg.pack(side="left", fill="both", expand=True)
        sb_dlg.pack(side="right", fill="y")

        entry_manual_id = ctk.CTkEntry(dlg, placeholder_text="Ou digite o ID manualmente (ex: 12)")
        entry_manual_id.pack(fill="x", padx=16, pady=4)

        entry_manual_qty = ctk.CTkEntry(dlg, placeholder_text="Quantidade (padrão: 1)")
        entry_manual_qty.insert(0, "1")
        entry_manual_qty.pack(fill="x", padx=16, pady=4)

        def populate_known(filter_q=""):
            tree_dlg.delete(*tree_dlg.get_children())
            fq = filter_q.strip().lower()
            for it in known:
                name = str(it.get("name", ""))
                i_id = str(it.get("id"))
                if fq and (fq not in name.lower() and fq not in i_id):
                    continue
                tree_dlg.insert("", "end", iid=i_id, values=(f"#{i_id.zfill(3)}", name))

        populate_known()
        entry_search_item.bind("<KeyRelease>", lambda e: populate_known(entry_search_item.get()))

        def on_tree_dlg_select(e):
            sel = tree_dlg.selection()
            if sel:
                entry_manual_id.delete(0, "end")
                entry_manual_id.insert(0, sel[0])

        tree_dlg.bind("<<TreeviewSelect>>", on_tree_dlg_select)

        def on_confirm():
            i_id = entry_manual_id.get().strip()
            q_txt = entry_manual_qty.get().strip()
            if not i_id:
                return
            qty = int(q_txt) if q_txt.isdigit() else 1
            self.adapter.set_item_quantity(self.current_inv_kind, i_id, qty)
            dlg.destroy()
            self._selected_inv_id = str(i_id)
            self._refresh_inventory()
            self._update_dirty_indicator()
            self._set_status(f"Item #{i_id} adicionado (x{qty})!")

        btn_confirm = ctk.CTkButton(dlg, text="Adicionar", fg_color=SUCCESS_COLOR, hover_color=SUCCESS_HOVER, command=on_confirm)
        btn_confirm.pack(fill="x", padx=16, pady=(6, 16))

    def _max_existing_inventory(self):
        if not self.adapter: return
        inv = self.adapter.get_inventory(self.current_inv_kind)
        for it in inv:
            self.adapter.set_item_quantity(self.current_inv_kind, it["id"], 99)
        self._refresh_inventory()
        self._update_dirty_indicator()
        self._set_status(f"Todos os {len(inv)} itens desta categoria foram definidos para x99!")

    def _unlock_all_current_kind(self):
        if not self.adapter: return
        count = self.adapter.unlock_all_items(self.current_inv_kind, 99)
        self._refresh_inventory()
        self._update_dirty_indicator()
        kind_name = "itens" if self.current_inv_kind == "items" else ("armas" if self.current_inv_kind == "weapons" else "armaduras")
        self._set_status(f"Desbloqueados todos os {count} {kind_name} do banco de dados (x99)!")

    # --- Lógica da Aba: Switches & Variáveis (Alta Performance) ---

    def _on_system_segment_change(self, val):
        self.current_system_tab = "switches" if "Switches" in val else "variables"
        self._selected_sys_id = None
        self._refresh_switches()

    def _refresh_switches(self):
        if not self.adapter: return

        self.tree_sys.delete(*self.tree_sys.get_children())
        query = self.search_var.get().strip().lower()

        if self.current_system_tab == "switches":
            self.frame_var_edit.pack_forget()
            self.btn_toggle_sys.pack(side="right", padx=10)
            self.tree_sys.heading("val", text="Estado (ON / OFF)  ▲▼")

            switches = self.adapter.get_switches()
            filtered = [s for s in switches if not query or query in s["name"].lower() or query in str(s["id"])]

            reverse = self._system_sort_desc
            if self._system_sort_col == "id":
                filtered.sort(key=lambda x: x["id"], reverse=reverse)
            elif self._system_sort_col == "name":
                filtered.sort(key=lambda x: str(x["name"]).lower(), reverse=reverse)
            elif self._system_sort_col == "val":
                filtered.sort(key=lambda x: int(x["value"]), reverse=reverse)

            for s in filtered:
                s_id = s["id"]
                val_text = "🟢 LIGADO (ON)" if s["value"] else "⚪ DESLIGADO (OFF)"
                tag = "on" if s["value"] else "off"
                self.tree_sys.insert("", "end", iid=str(s_id), values=(f"#{str(s_id).zfill(4)}", s["name"], val_text), tags=(tag,))

            self.lbl_system_count.configure(text=f"{len(filtered)} de {len(switches)} switches")
        else:
            self.btn_toggle_sys.pack_forget()
            self.frame_var_edit.pack(side="right", padx=10)
            self.tree_sys.heading("val", text="Valor Atual  ▲▼")

            variables = self.adapter.get_variables()
            filtered = [v for v in variables if not query or query in v["name"].lower() or query in str(v["id"])]

            reverse = self._system_sort_desc
            if self._system_sort_col == "id":
                filtered.sort(key=lambda x: x["id"], reverse=reverse)
            elif self._system_sort_col == "name":
                filtered.sort(key=lambda x: str(x["name"]).lower(), reverse=reverse)
            elif self._system_sort_col == "val":
                filtered.sort(key=lambda x: str(x["value"]), reverse=reverse)

            for v in filtered:
                v_id = v["id"]
                val_str = str(v["value"]) if v["value"] is not None else ""
                self.tree_sys.insert("", "end", iid=str(v_id), values=(f"#{str(v_id).zfill(4)}", v["name"], val_str))

            self.lbl_system_count.configure(text=f"{len(filtered)} de {len(variables)} variáveis")

        if self._selected_sys_id and self.tree_sys.exists(str(self._selected_sys_id)):
            self.tree_sys.selection_set(str(self._selected_sys_id))
            self.tree_sys.see(str(self._selected_sys_id))
        else:
            self._selected_sys_id = None
            prompt_txt = "Selecione uma switch acima para alternar" if self.current_system_tab == "switches" else "Selecione uma variável para editar seu valor"
            self.lbl_selected_sys.configure(text=prompt_txt)

    def _sort_system(self, col: str):
        if self._system_sort_col == col:
            self._system_sort_desc = not self._system_sort_desc
        else:
            self._system_sort_col = col
            self._system_sort_desc = False
        self._refresh_switches()

    def _on_system_select(self, event=None):
        sel = self.tree_sys.selection()
        if not sel: return
        sid = sel[0]
        self._selected_sys_id = int(sid)
        values = self.tree_sys.item(sid, "values")
        if values:
            id_fmt, name, val_str = values
            if self.current_system_tab == "switches":
                self.lbl_selected_sys.configure(text=f"{id_fmt} — {name} [{val_str}]")
            else:
                self.lbl_selected_sys.configure(text=f"{id_fmt} — {name}")
                self.ent_var_val.delete(0, "end")
                self.ent_var_val.insert(0, val_str)

    def _on_system_double_click(self, event=None):
        if self.current_system_tab == "switches":
            self._toggle_selected_switch()
        else:
            self._on_system_select()
            self.ent_var_val.focus_set()
            self.ent_var_val.select_range(0, "end")

    def _toggle_selected_switch(self):
        if not self.adapter or not self._selected_sys_id or self.current_system_tab != "switches":
            return
        sid_str = str(self._selected_sys_id)
        if not self.tree_sys.exists(sid_str): return

        curr_values = self.tree_sys.item(sid_str, "values")
        is_on = "LIGADO" in curr_values[2]
        new_state = not is_on

        self.adapter.set_switch(self._selected_sys_id, new_state)
        self._update_dirty_indicator()

        new_val_str = "🟢 LIGADO (ON)" if new_state else "⚪ DESLIGADO (OFF)"
        new_tag = "on" if new_state else "off"
        self.tree_sys.set(sid_str, "val", new_val_str)
        self.tree_sys.item(sid_str, tags=(new_tag,))
        self.lbl_selected_sys.configure(text=f"{curr_values[0]} — {curr_values[1]} [{new_val_str}]")

    def _save_selected_variable(self):
        if not self.adapter or not self._selected_sys_id or self.current_system_tab != "variables":
            return
        sid_str = str(self._selected_sys_id)
        if not self.tree_sys.exists(sid_str): return

        new_val = self.ent_var_val.get().strip()
        self.adapter.set_variable(self._selected_sys_id, new_val)
        self._update_dirty_indicator()

        self.tree_sys.set(sid_str, "val", new_val)
        curr_values = self.tree_sys.item(sid_str, "values")
        self._set_status(f"Variável #{self._selected_sys_id} atualizada para: {new_val}")

    # --- Lógica da Aba: Árvore Avançada (Lazy Loading) ---

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        self._tree_item_to_path.clear()
        self._tree_node_has_children.clear()
        if not self.adapter or not self.adapter.raw_data:
            return

        def insert_stub(parent, key, value, path):
            is_container = isinstance(value, (dict, list))
            val_str = "{...}" if isinstance(value, dict) else (" [...]" if isinstance(value, list) else repr(value))
            node = self.tree.insert(parent or "", "end", text=str(key), values=(val_str,))
            self._tree_item_to_path[node] = list(path)
            if is_container:
                self.tree.insert(node, "end", text="...", values=("",))
                self._tree_node_has_children[node] = value

        if isinstance(self.adapter.raw_data, dict):
            for k, v in self.adapter.raw_data.items():
                insert_stub("", k, v, [k])
        elif isinstance(self.adapter.raw_data, list):
            for i, v in enumerate(self.adapter.raw_data):
                insert_stub("", i, v, [i])

    def _on_tree_open(self, event):
        sel = self.tree.focus()
        if not sel or sel not in self._tree_node_has_children:
            return
        container = self._tree_node_has_children.pop(sel)
        for ch in self.tree.get_children(sel):
            self.tree.delete(ch)

        path = self._tree_item_to_path.get(sel, [])

        def insert_child(parent, key, value, p):
            is_container = isinstance(value, (dict, list))
            val_str = "{...}" if isinstance(value, dict) else (" [...]" if isinstance(value, list) else repr(value))
            node = self.tree.insert(parent, "end", text=str(key), values=(val_str,))
            self._tree_item_to_path[node] = list(p)
            if is_container:
                self.tree.insert(node, "end", text="...", values=("",))
                self._tree_node_has_children[node] = value

        if isinstance(container, dict):
            for k, v in list(container.items())[:200]:
                insert_child(sel, k, v, path + [k])
        elif isinstance(container, list):
            for idx, v in enumerate(container[:200]):
                insert_child(sel, idx, v, path + [idx])

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        self._selected_tree_node = sel[0]
        path = self._tree_item_to_path.get(self._selected_tree_node)
        if path:
            val = self.adapter.get_by_path(path)
            self.entry_tree_val.delete(0, "end")
            if not isinstance(val, (dict, list)):
                self.entry_tree_val.insert(0, str(val))
            else:
                self.entry_tree_val.insert(0, f"<{type(val).__name__}>")

    def _save_tree_val(self):
        if not self._selected_tree_node or not self.adapter: return
        path = self._tree_item_to_path.get(self._selected_tree_node)
        if not path: return
        txt = self.entry_tree_val.get().strip()
        import json
        try:
            newval = json.loads(txt)
        except Exception:
            newval = txt

        if self.adapter.set_by_path(path, newval):
            self.tree.set(self._selected_tree_node, "value", repr(newval))
            self._update_dirty_indicator()
            self._set_status(f"Campo {path[-1]} atualizado com sucesso!")

    # --- Busca Global (com Debouncing) ---

    def _on_global_search_change(self):
        """Dispara busca com debouncing de 150ms para manter a interface fluida."""
        if self._search_debounce_job is not None:
            self.after_cancel(self._search_debounce_job)
        self._search_debounce_job = self.after(150, self._apply_search_filter)

    def _apply_search_filter(self):
        self._search_debounce_job = None
        curr_tab = self.tabview.get()
        if "Personagens" in curr_tab:
            self._refresh_actors()
        elif "Inventário" in curr_tab:
            self._refresh_inventory()
        elif "Switches" in curr_tab:
            self._refresh_switches()

    # --- Salvar Arquivo ---

    def save_current_file(self):
        if not self.adapter or not self.current_file:
            messagebox.showwarning("Aviso", "Nenhum save carregado para salvar.")
            return

        def task():
            self.queue_ui(self._set_status, f"Salvando {self.current_file.name}...", True)
            try:
                self.adapter.save(self.current_file, backup=True)
                self.queue_ui(self._on_save_success, str(self.current_file))
            except Exception as e:
                self.queue_ui(self._on_save_error, str(e))

        threading.Thread(target=task, daemon=True).start()

    def save_as_dialog(self):
        if not self.adapter or not self.current_file:
            messagebox.showwarning("Aviso", "Nenhum save carregado para salvar.")
            return

        ext = self.current_file.suffix
        p = filedialog.asksaveasfilename(
            title="Salvar Save Como...",
            defaultextension=ext,
            initialfile=f"{self.current_file.stem}_editado{ext}",
            filetypes=[("Mesmo Formato", f"*{ext}"), ("Todos os Arquivos", "*.*")]
        )
        if not p: return

        def task():
            try:
                self.adapter.save(p, backup=False)
                self.current_file = Path(p)
                self.queue_ui(self._on_save_success, p)
            except Exception as e:
                self.queue_ui(self._on_save_error, str(e))

        threading.Thread(target=task, daemon=True).start()

    def export_json_dialog(self):
        if not self.adapter or not self.current_file:
            messagebox.showwarning("Aviso", "Nenhum save carregado.")
            return

        p = filedialog.asksaveasfilename(
            title="Exportar Save como JSON",
            defaultextension=".json",
            initialfile=f"{self.current_file.stem}.json",
            filetypes=[("Arquivo JSON", "*.json")]
        )
        if not p: return

        try:
            import json
            out = {
                "engine": self.adapter.engine_name,
                "compression": self.adapter.compression,
                "data": self.adapter.raw_data
            }
            Path(p).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            self._set_status(f"Exportado com sucesso para {Path(p).name}!")
            messagebox.showinfo("Exportação Concluída", f"JSON exportado com sucesso em:\n{p}")
        except Exception as e:
            messagebox.showerror("Erro na exportação", f"Erro: {e}")

    def _on_save_success(self, file_path_str: str):
        self._update_dirty_indicator()
        self._set_status(f"Arquivo '{Path(file_path_str).name}' salvo com sucesso! Backup .bak gerado.")
        messagebox.showinfo("Salvo com Sucesso", f"O save foi salvo com sucesso!\nUm backup (.bak) de segurança foi gerado.")

    def _on_save_error(self, err_msg: str):
        messagebox.showerror("Erro ao salvar", f"Ocorreu um erro ao tentar salvar:\n\n{err_msg}")
        self._set_status("Erro ao salvar arquivo.", False)


def main():
    app = ModernSaveEditorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
