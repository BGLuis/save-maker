#!/usr/bin/env python3
"""
ModernSaveEditorApp — Interface Gráfica Principal do Save Maker.
Implementação completa do redesign concebido no Figma:
Sidebar fixa, Topbar com ação primária de salvar dourada, Design Tokens (Dark & Light),
Edição inline e badges de alteração, Sistema de Desfazer (Ctrl+Z), Atalhos globais e
Biblioteca de Jogos.
"""

import os
import sys
import json
import queue
import time
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from typing import Any, Dict, List, Optional

import customtkinter as ctk

# Garante caminhos no sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SCRIPTS_DIR.parent
for d in (str(SCRIPTS_DIR), str(ROOT_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

from core.database_manager import GameDatabaseManager, GLOBAL_DB
from core.detector import detect_and_create_adapter
from core.base_adapter import BaseSaveAdapter
from core.undo_manager import UndoManager
from core.library_manager import LibraryManager

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, SUCCESS_HOVER, DANGER_COLOR, DANGER_HOVER,
    WARNING_COLOR, WARNING_HOVER, BG_CANVAS, BG_CARD, BG_SUB, BG_ACTIVE,
    TEXT_MUTED, TEXT_MAIN, TEXT_SUBTLE, BORDER_COLOR, BORDER_SUBTLE,
    get_ui_font, get_mono_font, setup_treeview_styles, init_draw_engine
)

from ui.components.sidebar import Sidebar
from ui.components.topbar import Topbar
from ui.views.empty_view import EmptyView
from ui.views.overview_view import OverviewView
from ui.views.actors_view import ActorsView
from ui.views.inventory_view import InventoryView
from ui.views.switches_view import SwitchesView
from ui.views.advanced_view import AdvancedView
from ui.views.library_view import LibraryView

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


class CompatibilityWidgetProxy:
    """Proxy para métodos configure() de widgets antigos para não quebrar testes legados."""

    def __init__(self, target_fn=None):
        self.target_fn = target_fn

    def configure(self, **kwargs):
        if self.target_fn:
            self.target_fn(**kwargs)

    def config(self, **kwargs):
        self.configure(**kwargs)


class LegacyTabViewShim:
    """Shim para emular app.tabview com os métodos get() e set() usados em testes."""

    def __init__(self, app: "ModernSaveEditorApp"):
        self.app = app
        self._current_tab_name = "📊 Visão Geral"

    def get(self) -> str:
        return self._current_tab_name

    def set(self, name: str):
        self._current_tab_name = name
        area_map = {
            "Visão": "overview",
            "overview": "overview",
            "Personagens": "actors",
            "actor": "actors",
            "Inventário": "inventory",
            "inventory": "inventory",
            "Switches": "switches",
            "sys": "switches",
            "Avançado": "advanced",
            "Árvore": "advanced",
            "advanced": "advanced",
            "Biblioteca": "library",
            "library": "library"
        }
        for k, area_id in area_map.items():
            if k in name or k.lower() in name.lower():
                self.app.select_nav_area(area_id, from_shim=True)
                return
        self.app.select_nav_area("overview", from_shim=True)


class ModernSaveEditorApp(CtkDndApp):
    """Aplicação Principal Moderna para Edição de Saves de RPG Maker."""

    def __init__(self):
        super().__init__()
        init_draw_engine()

        # Configurações de Janela
        self.title("Save Maker — Universal RPG Maker Editor")
        self.geometry("1240x800")
        self.minsize(980, 640)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=BG_CANVAS)
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)

        # Estado da Aplicação e Gerenciadores
        self.db = GLOBAL_DB
        self.adapter: Optional[BaseSaveAdapter] = None
        self.current_file: Optional[Path] = None
        self.gui_queue = queue.Queue()
        self.undo_mgr = UndoManager()
        self.lib_mgr = LibraryManager()

        self.selected_actor_id: Optional[Any] = None
        self.current_inv_kind: str = "items"
        self.current_system_tab: str = "switches"
        self.tree_page_size: int = 200

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
        self._tree_item_to_path: Dict[str, Any] = {}
        self._selected_tree_node: Optional[str] = None

        self.search_var = tk.StringVar(value="")

        # Configura estilos de tabela Treeview para Dark/Light mode
        self._setup_treeview_styles("dark")

        # Shims de compatibilidade para testes
        self.tabview = LegacyTabViewShim(self)
        self._setup_compatibility_proxies()

        # Constrói a Estrutura Principal da Janela
        self._build_main_layout()

        # Drag and Drop se disponível
        if _DND_AVAILABLE:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop_file)
            except Exception:
                pass

        # Atalhos de Teclado Globais (Figma: Ctrl 1–5, Ctrl S, Ctrl Z, Ctrl K)
        self._setup_keyboard_shortcuts()

        # Observador do UndoManager
        self.undo_mgr.add_listener(self._on_undo_history_changed)

        # Loop de mensagens de UI thread-safe
        self._check_gui_queue()

    # --- Propriedades de Compatibilidade com Testes Legados ---

    @property
    def selected_inv_item_id(self) -> Optional[str]:
        return self._selected_inv_id

    @selected_inv_item_id.setter
    def selected_inv_item_id(self, val: Optional[str]):
        self._selected_inv_id = val

    @property
    def entry_inv_qty(self) -> Optional[ctk.CTkEntry]:
        return getattr(self.view_inventory, "ent_inv_qty", None)

    @entry_inv_qty.setter
    def entry_inv_qty(self, val: ctk.CTkEntry):
        self.view_inventory.ent_inv_qty = val

    @property
    def adv_tree(self) -> Optional[ttk.Treeview]:
        return getattr(self.view_advanced, "tree", None)

    @adv_tree.setter
    def adv_tree(self, val: ttk.Treeview):
        self.view_advanced.tree = val

    @property
    def tree(self) -> Optional[ttk.Treeview]:
        return self.adv_tree

    @tree.setter
    def tree(self, val: ttk.Treeview):
        self.adv_tree = val

    @property
    def tree_paths(self) -> Dict[str, Any]:
        return self._tree_item_to_path

    @tree_paths.setter
    def tree_paths(self, val: Dict[str, Any]):
        self._tree_item_to_path = val

    @property
    def tree_inv(self) -> ttk.Treeview:
        return self.view_inventory.tree_inv

    @property
    def tree_sys(self) -> ttk.Treeview:
        return self.view_switches.tree_sys

    @property
    def actor_buttons(self) -> Dict[str, ctk.CTkButton]:
        return self.view_actors.actor_buttons

    @actor_buttons.setter
    def actor_buttons(self, val: Dict[str, ctk.CTkButton]):
        self.view_actors.actor_buttons = val

    @property
    def actor_entries(self) -> Dict[str, ctk.CTkEntry]:
        return self.view_actors.actor_entries

    @actor_entries.setter
    def actor_entries(self, val: Dict[str, ctk.CTkEntry]):
        self.view_actors.actor_entries = val

    @property
    def actors_scroll(self) -> ctk.CTkScrollableFrame:
        return self.view_actors.actors_scroll

    @property
    def entry_gold(self) -> ctk.CTkEntry:
        return self.view_overview.entry_gold

    @property
    def entry_tree_val(self) -> ctk.CTkEntry:
        return self.view_advanced.entry_val

    # --- Construção da UI ---

    def _build_main_layout(self):
        # 1. Sidebar Fixa à Esquerda
        self.sidebar = Sidebar(
            self,
            on_navigate=self.select_nav_area,
            on_theme_toggle=self.toggle_theme,
            on_select_db_dir=self.select_game_data_dir
        )
        self.sidebar.pack(side="left", fill="y")

        # 2. Container da Direita (Topbar + Área de Conteúdo)
        self.right_container = ctk.CTkFrame(self, fg_color="transparent")
        self.right_container.pack(side="right", fill="both", expand=True)

        # Topbar Fixa no Topo
        self.topbar = Topbar(
            self.right_container,
            on_save=self.save_current_file,
            on_export_json=self.export_json_dialog,
            on_undo=self.undo_last_action,
            on_search_change=self._on_global_search_change
        )
        self.topbar.pack(side="top", fill="x")

        # Container onde as telas (Views) serão alternadas
        self.views_container = ctk.CTkFrame(self.right_container, fg_color="transparent")
        self.views_container.pack(side="top", fill="both", expand=True, padx=14, pady=(10, 14))

        # Inicializa todas as Views
        self._init_views()

        # Inicia no Estado Vazio ou Biblioteca se não houver arquivo aberto
        self.select_nav_area("empty")

    def _init_views(self):
        # View 06: Estado Vazio
        self.view_empty = EmptyView(
            self.views_container,
            on_choose_file=self.open_file_dialog,
            on_choose_game_dir=self.select_game_data_dir,
            on_open_recent=lambda p: self.load_save_file(p),
            get_recent_files=self.lib_mgr.get_recent_files
        )

        # View 01: Visão Geral
        self.view_overview = OverviewView(
            self.views_container,
            on_apply_gold=self._set_gold,
            on_add_gold=self._add_gold,
            on_set_gold=self._set_gold,
            on_quick_heal_all=self._quick_heal_all,
            on_quick_level_up=self._quick_level_up_all,
            on_quick_max_stats=self._quick_max_stats_all,
            on_unlock_items=lambda: self._quick_unlock_all("items", 99),
            on_unlock_weapons=lambda: self._quick_unlock_all("weapons", 1),
            on_unlock_armors=lambda: self._quick_unlock_all("armors", 1),
            on_navigate_to_actors=lambda: self.select_nav_area("actors")
        )

        # View 02: Personagens
        self.view_actors = ActorsView(
            self.views_container,
            on_select_actor=self._select_actor,
            on_save_stats=self._save_current_actor_stats,
            on_max_stats=self._max_current_actor_stats,
            on_heal_actor=self._heal_current_actor
        )

        # View 03: Inventário
        self.view_inventory = InventoryView(
            self.views_container,
            on_kind_change=self._on_inv_segment_change,
            on_filter_change=lambda q: self._on_inv_filter_change(q),
            on_sort=self._sort_inventory,
            on_select_item=self._on_inv_select,
            on_set_qty=self._set_selected_inv_qty,
            on_step_qty=self._step_inv_qty,
            on_complete_db=self._complete_inventory_from_db,
            on_add_new_item=self._add_new_item_dialog,
            on_filter_chip=lambda c: self._on_inv_chip_change(c)
        )

        # View 04: Switches & Variáveis
        self.view_switches = SwitchesView(
            self.views_container,
            on_segment_change=self._on_system_segment_change,
            on_filter_change=lambda q: self._on_system_filter_change(q),
            on_filter_chip=lambda c: self._on_system_chip_change(c),
            on_sort=self._sort_system,
            on_select=lambda sid: self._on_system_select(sid),
            on_toggle_switch=self._toggle_selected_switch,
            on_save_var=self._save_selected_variable,
            on_turn_off_visible=self._turn_off_visible_switches
        )

        # View 05: Árvore JSON
        self.view_advanced = AdvancedView(
            self.views_container,
            on_save_value=self._save_tree_val
        )
        self.view_advanced.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.view_advanced.tree.bind("<<TreeviewOpen>>", self._on_tree_open)

        # View 09 / 10: Biblioteca de Jogos
        self.view_library = LibraryView(
            self.views_container,
            library_manager=self.lib_mgr,
            on_open_save_file=lambda p: self.load_save_file(p),
            get_current_file_path=lambda: self.current_file,
            is_current_dirty=lambda: bool(self.adapter and getattr(self.adapter, "dirty", False)),
            on_ask_save_dirty=self._confirm_save_before_switch
        )

        self.all_views = {
            "empty": (self.view_empty, "Save Maker"),
            "overview": (self.view_overview, "Visão geral"),
            "actors": (self.view_actors, "Personagens"),
            "inventory": (self.view_inventory, "Inventário"),
            "switches": (self.view_switches, "Switches & variáveis"),
            "advanced": (self.view_advanced, "Árvore JSON"),
            "library": (self.view_library, "Biblioteca de Jogos")
        }

    def _setup_compatibility_proxies(self):
        """Cria referências compatíveis para atributos acessados por testes antigos."""
        self.lbl_dirty_badge = CompatibilityWidgetProxy(
            lambda **kw: self.topbar.set_dirty_status(bool(self.adapter and self.adapter.dirty), getattr(self.adapter, "changes_count", 0) if self.adapter else 0)
        )
        self.lbl_status = CompatibilityWidgetProxy(
            lambda text="", **kw: None
        )
        self.lbl_engine_badge = CompatibilityWidgetProxy(
            lambda text="", **kw: None
        )
        self.lbl_save_file_info = CompatibilityWidgetProxy(
            lambda text="", **kw: None
        )
        self.lbl_db_status = CompatibilityWidgetProxy(
            lambda text="", **kw: None
        )
        self.lbl_inv_count = CompatibilityWidgetProxy()
        self.lbl_system_count = CompatibilityWidgetProxy()
        self.lbl_selected_sys = CompatibilityWidgetProxy()

    def _setup_keyboard_shortcuts(self):
        """Registra os atalhos de teclado globais Ctrl 1–5, Ctrl S, Ctrl Z, Ctrl K."""
        self.bind("<Control-KeyPress-1>", lambda e: self.select_nav_area("overview"))
        self.bind("<Control-KeyPress-2>", lambda e: self.select_nav_area("actors"))
        self.bind("<Control-KeyPress-3>", lambda e: self.select_nav_area("inventory"))
        self.bind("<Control-KeyPress-4>", lambda e: self.select_nav_area("switches"))
        self.bind("<Control-KeyPress-5>", lambda e: self.select_nav_area("advanced"))

        self.bind("<Control-s>", lambda e: self._shortcut_save())
        self.bind("<Control-S>", lambda e: self._shortcut_save())
        self.bind("<Control-z>", lambda e: self.undo_last_action())
        self.bind("<Control-Z>", lambda e: self.undo_last_action())
        self.bind("<Control-k>", lambda e: self._shortcut_search())
        self.bind("<Control-K>", lambda e: self._shortcut_search())

    def _shortcut_save(self):
        self.save_current_file()
        return "break"

    def _shortcut_search(self):
        self.topbar.focus_search()
        return "break"

    # --- Navegação e Alternância de Telas ---

    def select_nav_area(self, area_id: str, from_shim: bool = False):
        """Alterna a tela ativa exibida no container principal."""
        if area_id not in self.all_views:
            area_id = "overview"

        # Esconde todas as views
        for vid, (view_widget, _) in self.all_views.items():
            view_widget.pack_forget()

        # Exibe a view selecionada
        active_widget, title = self.all_views[area_id]
        active_widget.pack(fill="both", expand=True)

        self.topbar.set_title(title)

        if not from_shim and area_id != "empty":
            self.sidebar.select_area(area_id, notify=False)

        # Mapeamento para o shim de tabview
        tab_names_map = {
            "overview": "📊 Visão Geral",
            "actors": "👥 Personagens & Atributos",
            "inventory": "🎒 Inventário",
            "switches": "⚙ Switches & Variáveis",
            "advanced": "🌲 Modo Avançado / Árvore",
            "library": "📚 Biblioteca",
            "empty": "Save Maker"
        }
        self.tabview._current_tab_name = tab_names_map.get(area_id, "📊 Visão Geral")

        if not from_shim and self.adapter:
            self._on_tab_change()

    def _on_tab_change(self):
        """Atualiza a tela ativa se ela estiver com a flag de refresh pendente."""
        if not self.adapter: return

        curr_tab = self.tabview.get()
        if "Visão Geral" in curr_tab:
            if self.tabs_need_refresh.get("overview", True):
                self._refresh_overview()
                self.tabs_need_refresh["overview"] = False
        elif "Personagens" in curr_tab:
            if self.tabs_need_refresh.get("actors", True):
                self._refresh_actors()
                self.tabs_need_refresh["actors"] = False
        elif "Inventário" in curr_tab:
            if self.tabs_need_refresh.get("inventory", True):
                self._refresh_inventory()
                self.tabs_need_refresh["inventory"] = False
        elif "Switches" in curr_tab:
            if self.tabs_need_refresh.get("switches", True):
                self._refresh_switches()
                self.tabs_need_refresh["switches"] = False
        elif "Avançado" in curr_tab or "Árvore" in curr_tab:
            if self.tabs_need_refresh.get("advanced", True):
                self._populate_tree()
                self.tabs_need_refresh["advanced"] = False

    def _refresh_all_views(self):
        """Atualiza a tela ativa imediatamente e invalida o cache das demais para lazy loading."""
        if not self.adapter: return

        for k in self.tabs_need_refresh:
            self.tabs_need_refresh[k] = True

        self._refresh_overview()
        self.tabs_need_refresh["overview"] = False

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
        elif "Avançado" in curr_tab or "Árvore" in curr_tab:
            self._populate_tree()
            self.tabs_need_refresh["advanced"] = False

    def _setup_treeview_styles(self, mode: str = "dark"):
        setup_treeview_styles(mode)

    # --- Carregamento e Gravação de Saves ---

    def open_file_dialog(self):
        ft = [
            ("Saves RPG Maker / JSON", "*.rpgsave *.rmmzsave *.rvdata2 *.rvdata *.rxdata *.lsd *.sav *.json *.dat *.txt"),
            ("Todos os Arquivos", "*.*")
        ]
        p = filedialog.askopenfilename(title="Abrir Save de RPG Maker", filetypes=ft)
        if p:
            self.load_save_file(p)

    def _on_drop_file(self, event):
        path_str = event.data
        if path_str.startswith("{") and path_str.endswith("}"):
            path_str = path_str[1:-1]
        p = Path(path_str)
        if p.is_file():
            self.load_save_file(p)

    def load_save_file(self, file_path: str | Path, synchronous: bool = False):
        p = Path(file_path).resolve()
        if not p.is_file():
            return

        def work():
            db_found = self.db.discover_and_load(p)
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

        # Limpa o histórico de undo para o novo arquivo
        self.undo_mgr.clear()

        # Atualiza a Sidebar com informações do save
        self.sidebar.update_file_status(
            filename=self.current_file.name,
            engine=self.adapter.engine_name,
            compression=getattr(self.adapter, "compression", "")
        )

        db_summary = self.db.summary_info()
        self.sidebar.update_database_status(db_found, db_summary)

        # Registra no LibraryManager com resolução inteligente de título
        raw_db_title = getattr(self.db, "game_title", "")
        self.lib_mgr.register_game(
            self.current_file,
            engine=self.adapter.engine_name,
            title=raw_db_title
        )
        self.lib_mgr.add_recent_file(
            self.current_file,
            engine=self.adapter.engine_name,
            title=raw_db_title
        )
        self.sidebar.update_library_count(len(self.lib_mgr.get_games()))

        # Alterna para a visão geral
        self.select_nav_area("overview")
        self._refresh_all_views()
        self._update_dirty_indicator()

    def _on_load_error(self, err_msg: str):
        messagebox.showerror("Erro ao abrir save", f"Não foi possível ler o arquivo:\n\n{err_msg}")

    def save_current_file(self):
        if not self.adapter or not self.current_file:
            return
        try:
            self.adapter.save(self.current_file, backup=True)
            self._on_save_success(self.current_file)
        except Exception as e:
            self._on_save_error(str(e))

    def save_as_dialog(self):
        if not self.adapter: return
        ext = self.current_file.suffix if self.current_file else ".rpgsave"
        p = filedialog.asksaveasfilename(
            title="Salvar Como",
            defaultextension=ext,
            initialfile=self.current_file.name if self.current_file else f"save{ext}"
        )
        if not p: return
        try:
            dest = Path(p)
            self.adapter.save(dest, backup=True)
            self.current_file = dest
            self._on_save_success(dest)
        except Exception as e:
            self._on_save_error(str(e))

    def export_json_dialog(self):
        if not self.adapter:
            messagebox.showinfo("Exportar JSON", "Nenhum save carregado para exportar.")
            return
        initial = f"{self.current_file.stem}.json" if self.current_file else "save.json"
        p = filedialog.asksaveasfilename(
            title="Exportar Save para JSON Legível",
            defaultextension=".json",
            initialfile=initial
        )
        if not p: return
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.adapter.raw_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Exportação Concluída", f"Arquivo JSON exportado com sucesso:\n{p}")
        except Exception as e:
            messagebox.showerror("Erro na Exportação", f"Falha ao exportar JSON:\n{e}")

    def _on_save_success(self, path: Path):
        self._update_dirty_indicator()
        messagebox.showinfo("Save Gravado", f"O arquivo foi salvo com sucesso com backup (.bak):\n{path.name}")

    def _on_save_error(self, err: str):
        messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo:\n\n{err}")

    def _update_dirty_indicator(self):
        is_dirty = bool(self.adapter and getattr(self.adapter, "dirty", False))
        cnt = getattr(self.adapter, "changes_count", 0) if is_dirty else 0
        if is_dirty and hasattr(self.adapter, "get_pending_changes_count"):
            cnt = self.adapter.get_pending_changes_count()
        self.topbar.set_dirty_status(is_dirty, cnt)

    def _set_status(self, msg: str, busy: bool = False):
        pass

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        new_mode = "light" if current.lower() == "dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        self.sidebar.update_theme_ui(new_mode)
        self._setup_treeview_styles(new_mode)

    def select_game_data_dir(self):
        d = filedialog.askdirectory(title="Selecione a pasta 'data' do jogo (com Items.json, System.json, etc.)")
        if not d: return
        if self.db.load_directory(d):
            self.sidebar.update_database_status(True, self.db.summary_info())
            self._refresh_all_views()
            messagebox.showinfo("Banco de Dados", f"Banco de dados carregado com sucesso!\n{self.db.summary_info()}")
        else:
            messagebox.showwarning("Banco de Dados", "Pasta inválida ou arquivos de dados não encontrados.")

    def _confirm_save_before_switch(self) -> Optional[bool]:
        """Pergunta ao usuário se deseja salvar alterações antes de trocar de save."""
        cnt = getattr(self.adapter, "changes_count", 1) if self.adapter else 1
        ans = messagebox.askyesnocancel(
            "Alterações Não Salvas",
            f"Existem alterações não salvas no arquivo atual.\nDeseja salvar antes de trocar de save?"
        )
        if ans is True:
            self.save_current_file()
        return ans

    # --- Desfazer e Refazer (Undo/Redo) ---

    def undo_last_action(self):
        if self.undo_mgr.can_undo():
            desc = self.undo_mgr.undo()
            self._refresh_all_views()
            self._update_dirty_indicator()

    def redo_last_action(self):
        if self.undo_mgr.can_redo():
            desc = self.undo_mgr.redo()
            self._refresh_all_views()
            self._update_dirty_indicator()

    def _on_undo_history_changed(self, mgr: UndoManager):
        can_u = mgr.can_undo()
        last_desc = mgr.get_last_undo_description()
        self.topbar.update_undo_state(can_u, last_desc)

    # --- Lógica de Visão Geral (Ouro, Cheats e Heróis) ---

    def _refresh_overview(self):
        if not self.adapter: return

        # Atualiza Ouro
        gold = self.adapter.get_gold()
        self.view_overview.update_gold(gold)

        # Estatísticas de Campanha
        playtime = "0h 00m 00s"
        steps = 0
        if hasattr(self.adapter, "get_playtime_and_steps"):
            playtime, steps = self.adapter.get_playtime_and_steps()

        actors = self.adapter.get_actors() if hasattr(self.adapter, "get_actors") else []
        party = []
        if hasattr(self.adapter, "get_party_members"):
            party = self.adapter.get_party_members()
        elif hasattr(self.adapter, "get_party_dict"):
            party_dict = self.adapter.get_party_dict()
            party_ids = party_dict.get("_actors", []) if isinstance(party_dict, dict) else []
            party = [a for a in actors if a.get("id") in party_ids or str(a.get("id")) in [str(x) for x in party_ids]]
        if not party:
            party = actors[:4]

        saved_date = time.strftime("%d/%m/%Y · %H:%M", time.localtime(self.current_file.stat().st_mtime)) if self.current_file else "—"

        self.view_overview.update_campaign_stats(
            playtime_str=playtime,
            steps=steps,
            party_count=len(party),
            total_actors=len(actors),
            saved_date=saved_date
        )

        # Heróis do grupo
        self.view_overview.update_party_preview(party)

    def _set_gold(self, val: int):
        if not self.adapter: return
        old_val = self.adapter.get_gold()
        if old_val == val: return

        def undo():
            self.adapter.set_gold(old_val)
            self._refresh_overview()
            self._update_dirty_indicator()

        def redo():
            self.adapter.set_gold(val)
            self._refresh_overview()
            self._update_dirty_indicator()

        self.adapter.set_gold(val)
        self.undo_mgr.record(f"Definir ouro para {val:,}", undo, redo)
        self._refresh_overview()
        self._update_dirty_indicator()

    def _add_gold(self, amount: int):
        if not self.adapter: return
        cur = self.adapter.get_gold()
        self._set_gold(cur + amount)

    def _apply_gold_from_entry(self):
        val_str = self.view_overview.entry_gold.get().strip().replace(".", "").replace(",", "")
        try:
            val = int(val_str)
            self._set_gold(max(0, val))
        except ValueError:
            pass

    def _quick_heal_all(self):
        if not self.adapter: return
        actors = self.adapter.get_actors()
        old_states = {a["id"]: {"hp": a.get("hp", 0), "mp": a.get("mp", 0)} for a in actors}

        def undo():
            for aid, st in old_states.items():
                self.adapter.update_actor(aid, st)
            self._refresh_all_views()
            self._update_dirty_indicator()

        def redo():
            for a in actors:
                m_hp = a.get("max_hp", 9999) or 9999
                m_mp = a.get("max_mp", 999) or 999
                self.adapter.update_actor(a["id"], {"hp": m_hp, "mp": m_mp})
            self._refresh_all_views()
            self._update_dirty_indicator()

        redo()
        self.undo_mgr.record("Curar todo o grupo", undo, redo)

    def _quick_level_up_all(self):
        if not self.adapter: return
        actors = self.adapter.get_actors()
        old_levels = {a["id"]: a.get("level", 1) for a in actors}

        def undo():
            for aid, lvl in old_levels.items():
                self.adapter.update_actor(aid, {"level": lvl})
            self._refresh_all_views()
            self._update_dirty_indicator()

        def redo():
            for a in actors:
                new_lvl = min(99, a.get("level", 1) + 5)
                self.adapter.update_actor(a["id"], {"level": new_lvl})
            self._refresh_all_views()
            self._update_dirty_indicator()

        redo()
        self.undo_mgr.record("Subir 5 níveis do grupo", undo, redo)

    def _quick_max_stats_all(self):
        if not self.adapter: return
        actors = self.adapter.get_actors()
        old_attrs = {
            a["id"]: {
                k: a.get(k, 0)
                for k in ("max_hp", "max_mp", "atk", "def", "mat", "mdf", "agi", "luk")
            }
            for a in actors
        }

        def undo():
            for aid, attrs in old_attrs.items():
                self.adapter.update_actor(aid, attrs)
            self._refresh_all_views()
            self._update_dirty_indicator()

        def redo():
            for a in actors:
                self.adapter.update_actor(a["id"], {
                    "max_hp": 9999,
                    "max_mp": 999,
                    "atk": 999,
                    "def": 999,
                    "mat": 999,
                    "mdf": 999,
                    "agi": 999,
                    "luk": 999
                })
            self._refresh_all_views()
            self._update_dirty_indicator()

        redo()
        self.undo_mgr.record("Maximizar atributos de todos os heróis", undo, redo)

    def _quick_unlock_all(self, kind: str, qty: int = 99):
        if not self.adapter: return
        count = self.adapter.unlock_all_items(kind, qty)
        self.tabs_need_refresh["inventory"] = True
        self.tabs_need_refresh["advanced"] = True
        if "Inventário" in self.tabview.get():
            self._refresh_inventory()
            self.tabs_need_refresh["inventory"] = False
        self._update_dirty_indicator()

    # --- Lógica de Personagens (Actors) ---

    def _refresh_actors(self):
        if not self.adapter: return
        actors = self.adapter.get_actors() if hasattr(self.adapter, "get_actors") else []
        party_members = []
        if hasattr(self.adapter, "get_party_members"):
            party_members = self.adapter.get_party_members()
        elif hasattr(self.adapter, "get_party_dict"):
            party_dict = self.adapter.get_party_dict()
            p_ids = party_dict.get("_actors", []) if isinstance(party_dict, dict) else []
            party_members = [a for a in actors if a.get("id") in p_ids or str(a.get("id")) in [str(x) for x in p_ids]]
        if not party_members:
            party_members = actors[:4]
        party_ids = [p["id"] for p in party_members]

        if not self.selected_actor_id and actors:
            self.selected_actor_id = actors[0]["id"]

        self.view_actors.populate_actor_list(actors, party_ids, self.selected_actor_id)

        # Exibe os dados do herói selecionado
        sel_actor = next((a for a in actors if str(a["id"]) == str(self.selected_actor_id)), None)
        if sel_actor:
            self.view_actors.set_selected_actor_data(sel_actor)

    def _select_actor(self, actor_data_or_id: Any):
        if isinstance(actor_data_or_id, dict):
            aid = actor_data_or_id.get("id")
        else:
            aid = actor_data_or_id
        self.selected_actor_id = aid

        actors = self.adapter.get_actors() if self.adapter else []
        sel_actor = next((a for a in actors if str(a["id"]) == str(aid)), None)
        if sel_actor:
            self.view_actors.set_selected_actor_data(sel_actor)

    def _save_current_actor_stats(self):
        if not self.adapter or not self.selected_actor_id: return
        stats = {}
        for k, ent in self.actor_entries.items():
            txt = ent.get().strip()
            try:
                val = int(txt)
                if val < 0 and k in ("level", "hp", "mp", "tp"):
                    raise ValueError("Negative value not allowed")
            except ValueError:
                ent.configure(border_color=DANGER_COLOR[1])
                messagebox.showwarning(
                    "Valor Inválido",
                    f"O valor '{txt}' no campo '{k.upper()}' não é um número inteiro válido."
                )
                return
            ent.configure(border_color=BORDER_SUBTLE[1])
            stats[k] = val

        self.adapter.update_actor(self.selected_actor_id, stats)

        # Atualiza apenas o botão do ator modificado sem recriar widgets
        actors = self.adapter.get_actors() if hasattr(self.adapter, "get_actors") else []
        updated_actor = next((a for a in actors if str(a.get("id")) == str(self.selected_actor_id)), None)
        if updated_actor:
            aid_str = str(self.selected_actor_id)
            if aid_str in self.actor_buttons:
                name = updated_actor.get("name", "")
                lvl = updated_actor.get("level", 1)
                self.actor_buttons[aid_str].configure(text=f"{name}\n(Nível {lvl})")

        self.tabs_need_refresh["overview"] = True
        self.tabs_need_refresh["advanced"] = True
        self._update_dirty_indicator()

    def _max_current_actor_stats(self):
        if not self.adapter or not self.selected_actor_id: return
        self.adapter.update_actor(self.selected_actor_id, {
            "max_hp": 9999, "max_mp": 999,
            "atk": 999, "def": 999, "mat": 999, "mdf": 999, "agi": 999, "luk": 999
        })
        self._refresh_actors()
        self._update_dirty_indicator()

    def _heal_current_actor(self):
        if not self.adapter or not self.selected_actor_id: return
        actors = self.adapter.get_actors()
        act = next((a for a in actors if str(a["id"]) == str(self.selected_actor_id)), None)
        if act:
            m_hp = act.get("max_hp", 9999) or 9999
            m_mp = act.get("max_mp", 999) or 999
            self.adapter.update_actor(self.selected_actor_id, {"hp": m_hp, "mp": m_mp})
            self._refresh_actors()
            self._update_dirty_indicator()

    # --- Lógica de Inventário ---

    def _on_inv_segment_change(self, kind: str):
        self.current_inv_kind = kind
        self._refresh_inventory()

    def _on_inv_chip_change(self, chip: str):
        self._refresh_inventory()

    def _refresh_inventory(self):
        if not self.adapter: return

        self.tree_inv.delete(*self.tree_inv.get_children())
        inv = self.adapter.get_inventory(self.current_inv_kind, include_all_db=True)
        query = self.search_var.get().strip().lower()

        # Contagens para os chips de filtro
        all_c = len(inv)
        owned_c = sum(1 for it in inv if it.get("quantity", 0) > 0)
        unowned_c = all_c - owned_c
        if hasattr(self.view_inventory, "update_chip_counts"):
            self.view_inventory.update_chip_counts(all_c, owned_c, unowned_c)

        active_chip = getattr(self.view_inventory, "active_chip", "all")
        filtered = []
        for it in inv:
            qty = it.get("quantity", 0)
            if active_chip == "owned" and qty <= 0:
                continue
            if active_chip == "unowned" and qty > 0:
                continue

            if query:
                if query not in str(it["name"]).lower() and query not in str(it["id"]):
                    continue
            filtered.append(it)

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
            tag = "normal_qty" if it.get("quantity", 0) > 0 else "zero_qty"
            self.tree_inv.insert("", "end", iid=str(it["id"]), values=(i_id_fmt, it["name"], str(it["quantity"])), tags=(tag,))

        # Atualiza contadores dos segmentos (possuídos / total do catálogo)
        self._update_inventory_counts_only()

        if self._selected_inv_id and self.tree_inv.exists(self._selected_inv_id):
            self.tree_inv.selection_set(self._selected_inv_id)

    def _update_inventory_counts_only(self):
        if not self.adapter: return
        items_all = self.adapter.get_inventory("items", include_all_db=True)
        items_owned = sum(1 for x in items_all if x.get("quantity", 0) > 0)

        weaps_all = self.adapter.get_inventory("weapons", include_all_db=True)
        weaps_owned = sum(1 for x in weaps_all if x.get("quantity", 0) > 0)

        arms_all = self.adapter.get_inventory("armors", include_all_db=True)
        arms_owned = sum(1 for x in arms_all if x.get("quantity", 0) > 0)

        self.view_inventory.update_segment_counts(
            items_owned, weaps_owned, arms_owned,
            len(items_all), len(weaps_all), len(arms_all)
        )

    def _sort_inventory(self, col: str):
        if self._inv_sort_col == col:
            self._inv_sort_desc = not self._inv_sort_desc
        else:
            self._inv_sort_col = col
            self._inv_sort_desc = False
        self._refresh_inventory()

    def _on_inv_select(self, item_id: str):
        self._selected_inv_id = item_id

    def _apply_inv_qty_from_entry(self):
        item_id = self.selected_inv_item_id or self._selected_inv_id
        if not self.adapter or not item_id:
            return
        entry = self.entry_inv_qty if hasattr(self, "entry_inv_qty") and self.entry_inv_qty is not None else getattr(self.view_inventory, "ent_inv_qty", None)
        if not entry:
            return
        txt = entry.get().strip()
        try:
            qty = int(txt)
            if qty < 0:
                raise ValueError("Negative quantity not allowed")
        except ValueError:
            if hasattr(entry, "configure"):
                entry.configure(border_color=DANGER_COLOR[1] if isinstance(DANGER_COLOR, (tuple, list)) else DANGER_COLOR)
            messagebox.showwarning("Valor Inválido", "Digite uma quantidade inteira válida (>= 0).")
            return

        if hasattr(entry, "configure"):
            entry.configure(border_color=BORDER_COLOR[1] if isinstance(BORDER_COLOR, (tuple, list)) else BORDER_COLOR)
        self._set_selected_inv_qty(qty)

    def _step_inv_qty(self, delta: int):
        if not self.adapter or not self._selected_inv_id: return
        try:
            curr = int(self.entry_inv_qty.get() or 0)
        except ValueError:
            curr = 0
        self._set_selected_inv_qty(max(0, curr + delta))

    def _set_selected_inv_qty(self, val: int):
        if not self.adapter or not self._selected_inv_id: return
        self.adapter.set_item_quantity(self.current_inv_kind, self._selected_inv_id, val)
        self._update_dirty_indicator()

        if self.tree_inv.exists(self._selected_inv_id):
            active_chip = getattr(self.view_inventory, "active_chip", "all")
            if val == 0 and active_chip == "owned":
                self.tree_inv.delete(self._selected_inv_id)
                self._selected_inv_id = None
            elif val > 0 and active_chip == "unowned":
                self.tree_inv.delete(self._selected_inv_id)
                self._selected_inv_id = None
            else:
                curr_values = list(self.tree_inv.item(self._selected_inv_id, "values"))
                curr_values[2] = str(val)
                tag = "normal_qty" if val > 0 else "zero_qty"
                self.tree_inv.item(self._selected_inv_id, values=tuple(curr_values), tags=(tag,))

        self._update_inventory_counts_only()

    def _add_new_item_dialog(self):
        if not self.adapter: return
        item_id = simpledialog.askstring("Novo Item", "Digite o ID do item a adicionar:")
        if not item_id: return
        qty = simpledialog.askinteger("Quantidade", f"Quantidade para o item #{item_id}:", initialvalue=1, minvalue=1)
        if qty is None: return
        self._selected_inv_id = str(item_id)
        self._set_selected_inv_qty(qty)
        self._refresh_inventory()

    def _complete_inventory_from_db(self):
        if not self.adapter: return
        if not self.db or not self.db.is_loaded():
            messagebox.showinfo(
                "Banco de Dados",
                "O banco de dados do jogo não foi encontrado.\nAbra a pasta do jogo onde estão os arquivos de dados para completar o catálogo."
            )
            return

        kind_labels = {"items": "itens", "weapons": "armas", "armors": "armaduras"}
        kind_name = kind_labels.get(self.current_inv_kind, "itens")
        all_items = self.adapter.get_inventory(self.current_inv_kind, include_all_db=True)
        missing_count = sum(1 for it in all_items if it.get("quantity", 0) <= 0)

        if missing_count == 0:
            resp = messagebox.askyesno(
                "Completar com BD",
                f"Todos os {len(all_items)} {kind_name} do catálogo já estão no save.\n\nDeseja maximizar a quantidade de todos para 99?"
            )
            if resp:
                self.adapter.unlock_all_items(self.current_inv_kind, 99)
                self._refresh_inventory()
                self._update_dirty_indicator()
            return

        qty = simpledialog.askinteger(
            "Completar com BD",
            f"Foram encontrados {len(all_items)} {kind_name} no catálogo do jogo ({missing_count} ainda não obtidos no save).\n\n"
            f"Digite a quantidade para preencher todos os {len(all_items)} {kind_name}:",
            initialvalue=99, minvalue=1, maxvalue=9999
        )
        if qty is not None:
            count = self.adapter.unlock_all_items(self.current_inv_kind, qty)
            self._refresh_inventory()
            self._update_dirty_indicator()
            messagebox.showinfo("Sucesso", f"{count} {kind_name} foram atualizados para x{qty}!")

    def _max_existing_inventory(self):
        if not self.adapter: return
        inv = self.adapter.get_inventory(self.current_inv_kind)
        for it in inv:
            self.adapter.set_item_quantity(self.current_inv_kind, str(it["id"]), 99)
        self._refresh_inventory()
        self._update_dirty_indicator()

    def _unlock_all_current_kind(self):
        self._quick_unlock_all(self.current_inv_kind, 99)

    def _on_inv_filter_change(self, query: str):
        self.search_var.set(query)
        self._refresh_inventory()

    # --- Lógica de Switches e Variáveis ---

    def _on_system_segment_change(self, subtab: str):
        self.current_system_tab = subtab
        self._refresh_switches()

    def _refresh_switches(self):
        if not self.adapter: return

        self.tree_sys.delete(*self.tree_sys.get_children())
        query = self.search_var.get().strip().lower()

        if self.current_system_tab == "switches":
            switches = self.adapter.get_switches()
            filtered = []
            on_count = 0
            named_count = 0

            for s in switches:
                is_on = bool(s.get("value"))
                has_name = bool(s.get("name") and not s["name"].startswith("Switch "))
                if is_on: on_count += 1
                if has_name: named_count += 1

                chip = getattr(self.view_switches, "active_chip", "all")
                if chip == "on" and not is_on: continue
                if chip == "named" and not has_name: continue

                if query and query not in s["name"].lower() and query not in str(s["id"]):
                    continue
                filtered.append(s)

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

            all_vars = self.adapter.get_variables()
            self.view_switches.update_subtab_counts(len(switches), len(all_vars), on_count, named_count)
        else:
            variables = self.adapter.get_variables()
            filtered = []
            named_count = 0

            for v in variables:
                has_name = bool(v.get("name") and not v["name"].startswith("Variable "))
                if has_name: named_count += 1

                chip = getattr(self.view_switches, "active_chip", "all")
                if chip == "named" and not has_name: continue

                if query and query not in v["name"].lower() and query not in str(v["id"]):
                    continue
                filtered.append(v)

            reverse = self._system_sort_desc
            if self._system_sort_col == "id":
                filtered.sort(key=lambda x: x["id"], reverse=reverse)
            elif self._system_sort_col == "name":
                filtered.sort(key=lambda x: str(x["name"]).lower(), reverse=reverse)
            elif self._system_sort_col == "val":
                filtered.sort(key=lambda x: str(x["value"]), reverse=reverse)

            for v in filtered:
                v_id = v["id"]
                self.tree_sys.insert("", "end", iid=str(v_id), values=(f"#{str(v_id).zfill(4)}", v["name"], str(v["value"])))

            all_sw = self.adapter.get_switches()
            self.view_switches.update_subtab_counts(len(all_sw), len(variables), 0, named_count)

        if self._selected_sys_id and self.tree_sys.exists(str(self._selected_sys_id)):
            self.tree_sys.selection_set(str(self._selected_sys_id))

    def _sort_system(self, col: str):
        if self._system_sort_col == col:
            self._system_sort_desc = not self._system_sort_desc
        else:
            self._system_sort_col = col
            self._system_sort_desc = False
        self._refresh_switches()

    def _on_system_select(self, sid: int):
        self._selected_sys_id = sid

    def _on_system_double_click(self, event=None):
        if self.current_system_tab == "switches":
            self._toggle_selected_switch()
        else:
            self._save_selected_variable()

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

    def _save_selected_variable(self, sid: Optional[int] = None, val: Any = None):
        target_id = sid or self._selected_sys_id
        if not self.adapter or not target_id or self.current_system_tab != "variables":
            return
        if val is None:
            sel = self.tree_sys.selection()
            if not sel: return
            cur_val = self.tree_sys.item(sel[0], "values")[2]
            val = simpledialog.askstring("Editar Variável", f"Novo valor para #{target_id}:", initialvalue=cur_val)
            if val is None: return

        # Converte para int se possível
        try:
            val = int(val)
        except (ValueError, TypeError):
            pass

        self.adapter.set_variable(target_id, val)
        self._update_dirty_indicator()
        if self.tree_sys.exists(str(target_id)):
            self.tree_sys.set(str(target_id), "val", str(val))

    def _turn_off_visible_switches(self):
        if not self.adapter or self.current_system_tab != "switches": return
        for item in self.tree_sys.get_children():
            try:
                sid = int(item)
                self.adapter.set_switch(sid, False)
                self.tree_sys.set(item, "val", "⚪ DESLIGADO (OFF)")
                self.tree_sys.item(item, tags=("off",))
            except ValueError:
                pass
        self._update_dirty_indicator()

    def _on_system_filter_change(self, query: str):
        self.search_var.set(query)
        self._refresh_switches()

    def _on_system_chip_change(self, chip: str):
        self._refresh_switches()

    # --- Lógica da Árvore JSON Raw (Advanced Tree) ---

    def _get_container_by_path(self, path: List[Any]) -> Any:
        if not path:
            return self.adapter.raw_data if self.adapter else None
        return self.adapter.get_by_path(path) if self.adapter else None

    def _populate_tree_node(self, parent_node: str, container: Any, path: List[Any], start_offset: int = 0):
        if isinstance(container, dict):
            all_items = list(container.items())
        elif isinstance(container, list):
            all_items = list(enumerate(container))
        elif hasattr(container, "attributes") and isinstance(container.attributes, dict):
            all_items = list(container.attributes.items())
        else:
            all_items = []

        page_size = getattr(self, "tree_page_size", 200)
        items_slice = all_items[start_offset : start_offset + page_size]

        for key, value in items_slice:
            is_container = isinstance(value, (dict, list)) or hasattr(value, "attributes")
            val_str = "{...}" if isinstance(value, dict) else (" [...]" if isinstance(value, list) else repr(value))
            node = self.adv_tree.insert(parent_node, "end", text=str(key), values=(val_str,))
            child_path = path + [key]
            self.tree_paths[node] = child_path
            if is_container:
                self.adv_tree.insert(node, "end", text="...", values=("",))
                self._tree_node_has_children[node] = value

        if start_offset + len(items_slice) < len(all_items):
            next_offset = start_offset + len(items_slice)
            remaining = len(all_items) - next_offset
            more_node = self.adv_tree.insert(
                parent_node, "end",
                text=f"… mais {remaining} itens",
                values=("...", f"Carregar mais ({remaining} restantes)")
            )
            self.adv_tree.insert(more_node, "end", text="Carregando...")
            self.tree_paths[more_node] = {
                "_is_more": True,
                "parent_node": parent_node,
                "path": path,
                "next_offset": next_offset
            }

    def _populate_tree(self):
        self.adv_tree.delete(*self.adv_tree.get_children())
        self.tree_paths.clear()
        self._tree_node_has_children.clear()
        if not self.adapter or self.adapter.raw_data is None:
            return

        self._populate_tree_node("", self.adapter.raw_data, [], start_offset=0)

    def _on_tree_open(self, event=None):
        sel = self.adv_tree.focus()
        if not sel:
            selection = self.adv_tree.selection()
            if selection:
                sel = selection[0]
        if not sel: return

        meta = self.tree_paths.get(sel)
        if isinstance(meta, dict) and meta.get("_is_more"):
            self.adv_tree.delete(sel)
            if sel in self.tree_paths:
                del self.tree_paths[sel]
            container = self._get_container_by_path(meta["path"])
            self._populate_tree_node(meta["parent_node"], container, meta["path"], start_offset=meta["next_offset"])
            return

        if sel not in self._tree_node_has_children:
            return
        container = self._tree_node_has_children.pop(sel)
        for ch in self.adv_tree.get_children(sel):
            self.adv_tree.delete(ch)

        path = self.tree_paths.get(sel, [])
        self._populate_tree_node(sel, container, path, start_offset=0)

    def _on_tree_select(self, event=None):
        sel = self.adv_tree.selection()
        if not sel: return
        self._selected_tree_node = sel[0]
        meta = self.tree_paths.get(self._selected_tree_node)
        if isinstance(meta, dict) and meta.get("_is_more"):
            self.view_advanced.set_inspector_node("Paginador", "...")
            return

        path = meta
        if isinstance(path, list):
            val = self.adapter.get_by_path(path)
            path_str = ".".join(str(p) for p in path)
            self.view_advanced.set_inspector_node(path_str, val)

    def _save_tree_val(self, path_str: Optional[str] = None, newval: Any = None):
        if not self._selected_tree_node or not self.adapter: return
        meta = self.tree_paths.get(self._selected_tree_node)
        if isinstance(meta, dict) and meta.get("_is_more"): return
        path = meta
        if not path or not isinstance(path, list): return

        if newval is None:
            txt = self.view_advanced.entry_val.get().strip()
            try:
                newval = json.loads(txt)
            except Exception:
                newval = txt

        if self.adapter.set_by_path(path, newval):
            self.adv_tree.set(self._selected_tree_node, "value", repr(newval))
            self._update_dirty_indicator()

    # --- Busca Global (Debounced) ---

    def _on_global_search_change(self, query: str):
        if self._search_debounce_job:
            self.after_cancel(self._search_debounce_job)
        self._search_debounce_job = self.after(250, lambda: self._apply_search_filter(query))

    def _apply_search_filter(self, query: str = ""):
        self.search_var.set(query)
        curr_tab = self.tabview.get()
        if "Personagens" in curr_tab:
            self._refresh_actors()
        elif "Inventário" in curr_tab:
            self._refresh_inventory()
        elif "Switches" in curr_tab:
            self._refresh_switches()

    # --- Fechamento de Janela Seguro ---

    def _on_close_window(self):
        if self.adapter and getattr(self.adapter, "dirty", False):
            changes = getattr(self.adapter, "changes_count", None)
            if changes is None and hasattr(self.adapter, "get_pending_changes_count"):
                changes = self.adapter.get_pending_changes_count()
            if changes is None:
                changes = 0
            ans = messagebox.askyesnocancel(
                "Alterações Não Salvas",
                f"Existem {changes} alteração(ões) não salva(s).\nDeseja salvar antes de sair?"
            )
            if ans is None:
                return
            if ans is True:
                if self.current_file:
                    try:
                        self.adapter.save(self.current_file, backup=True)
                    except Exception as e:
                        messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar:\n{e}")
                        return
                else:
                    self.save_as_dialog()
                    if getattr(self.adapter, "dirty", False):
                        return
        self.destroy()

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


def run_gui():
    app = ModernSaveEditorApp()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
