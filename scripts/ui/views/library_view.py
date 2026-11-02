#!/usr/bin/env python3
"""
Library View (Telas 09 e 10 do Figma - nós #11:1250 e #11:1618).
Gerenciamento da biblioteca de jogos com busca, ordenação (Recentes / Nome / Motor),
cards colapsáveis de jogos com SaveSlot cards ricos, sugestão de jogos vizinhos,
barra de 4 fatos (Saves / Tempo Total / BD / Último Aberto), tabela com coluna Ouro e Pré-visualização completa.
Fiel ao Figma Save Maker.
"""

from typing import Callable, List, Dict, Any, Optional, Set
from pathlib import Path
import subprocess
import shutil
import os
from tkinter import ttk, filedialog, messagebox, simpledialog
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, SUCCESS_BG, WARNING_COLOR, WARNING_BG, DANGER_COLOR, HP_COLOR,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)


class LibraryView(ctk.CTkFrame):
    """Visualização da Biblioteca de Jogos (Telas 09 e 10)."""

    def __init__(
        self,
        master,
        library_manager,
        on_open_save_file: Callable[[str], None],
        get_current_file_path: Callable[[], Optional[Path]],
        is_current_dirty: Callable[[], bool],
        on_ask_save_dirty: Callable[[], Optional[bool]],
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.lib_mgr = library_manager
        self.on_open_save_file = on_open_save_file
        self.get_current_file_path = get_current_file_path
        self.is_current_dirty = is_current_dirty
        self.on_ask_save_dirty = on_ask_save_dirty

        self.current_screen: str = "list"  # "list" ou "game_detail"
        self.selected_game: Optional[Dict[str, Any]] = None
        self.selected_slot: Optional[Dict[str, Any]] = None

        self.filter_query: str = ""
        self.sort_mode: str = "recent"  # "recent", "name", "engine"
        self.collapsed_games: Set[str] = set()
        self.ignored_suggestions: Set[str] = set()
        self._slot_preview_cache: Dict[str, Dict[str, Any]] = {}

        self._build_ui()

    def _build_ui(self):
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.show_games_list()

    def _get_cached_slot_preview(self, slot_path: str, fetch_sync: bool = False) -> Dict[str, Any]:
        if slot_path not in self._slot_preview_cache:
            if fetch_sync and hasattr(self.lib_mgr, "get_slot_preview_details"):
                self._slot_preview_cache[slot_path] = self.lib_mgr.get_slot_preview_details(slot_path)
            else:
                return {}
        return self._slot_preview_cache[slot_path]

    def show_games_list(self):
        """Tela 09 do Figma (#11:1250 / #11:1985): Lista de Jogos da Biblioteca."""
        self.current_screen = "list"
        for w in self.container.winfo_children():
            w.destroy()

        games = self.lib_mgr.get_games()
        cur_file = self.get_current_file_path()
        cur_str = str(cur_file) if cur_file else None

        total_saves = 0
        never_opened_count = 0
        game_slots_map: Dict[str, List[Dict[str, Any]]] = {}
        for g in games:
            g_slots = self.lib_mgr.scan_game_slots(g["path"], current_open_file=cur_str)
            game_slots_map[g["path"]] = g_slots
            total_saves += len(g_slots)
            never_opened_count += sum(1 for s in g_slots if s.get("never_opened", False))

        # 1. Toolbar Unificada (#11:1986)
        toolbar = ctk.CTkFrame(self.container, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 14))

        self.lbl_stats = ctk.CTkLabel(
            toolbar,
            text=f"{len(games)} jogos · {total_saves} saves · {never_opened_count} nunca abertos",
            font=get_ui_font(12), text_color=TEXT_MUTED
        )
        self.lbl_stats.pack(side="left", padx=(0, 12))

        # Campo de busca "Filtrar jogos…" (#11:1988)
        search_wrap = ctk.CTkFrame(
            toolbar, height=34, fg_color=BG_SUB, corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE
        )
        search_wrap.pack(side="left", fill="x", expand=True, padx=(0, 10))

        s_ico = get_icon("search", size=(14, 14))
        ctk.CTkLabel(search_wrap, text="" if s_ico else "🔍", image=s_ico).pack(side="left", padx=(10, 4))

        self.entry_game_filter = ctk.CTkEntry(
            search_wrap, placeholder_text="Filtrar jogos…",
            font=get_ui_font(12), height=30, fg_color="transparent",
            border_width=0, text_color=TEXT_MAIN
        )
        self.entry_game_filter.pack(side="left", fill="both", expand=True)
        if self.filter_query:
            self.entry_game_filter.insert(0, self.filter_query)
        self.entry_game_filter.bind("<KeyRelease>", self._on_game_filter_change)

        # Segmented control de Ordenação (#11:1995: Recentes / Nome / Motor)
        sort_box = ctk.CTkFrame(
            toolbar, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        sort_box.pack(side="left", padx=(0, 10))

        self.sort_btns: Dict[str, ctk.CTkButton] = {}
        for mode_id, mode_lbl in (("recent", "Recentes"), ("name", "Nome"), ("engine", "Motor")):
            is_act = self.sort_mode == mode_id
            btn = ctk.CTkButton(
                sort_box, text=mode_lbl, width=72, height=28,
                font=get_ui_font(11, "bold" if is_act else "normal"),
                fg_color=BG_ACTIVE if is_act else "transparent",
                hover_color=BG_ACTIVE,
                text_color=TEXT_MAIN if is_act else TEXT_MUTED,
                corner_radius=6,
                command=lambda m=mode_id: self._set_sort_mode(m)
            )
            btn.pack(side="left", padx=2, pady=3)
            self.sort_btns[mode_id] = btn

        # Botões Reescanear e + Adicionar pasta de jogo (#11:2010)
        actions_box = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions_box.pack(side="right")

        ref_ico = get_icon("refresh", size=(14, 14))
        ctk.CTkButton(
            actions_box, text=" Reescanear", image=ref_ico, compound="left",
            width=114, height=34, font=get_ui_font(12, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR, corner_radius=6,
            command=self._handle_rescan
        ).pack(side="left", padx=(0, 6))

        plus_ico = get_icon("plus", size=(14, 14))
        ctk.CTkButton(
            actions_box, text=" Adicionar pasta de jogo", image=plus_ico, compound="left",
            width=182, height=34, font=get_ui_font(12, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE, corner_radius=6,
            command=self._handle_add_game_dir
        ).pack(side="left")

        # 2. Lista Scrollável de Jogos
        self.scroll_list = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True)

        self._render_games_cards(games, game_slots_map, cur_file)

    def _handle_rescan(self):
        self._slot_preview_cache.clear()
        self.show_games_list()

    def _on_game_filter_change(self, event=None):
        self.filter_query = self.entry_game_filter.get().strip()
        games = self.lib_mgr.get_games()
        cur_file = self.get_current_file_path()
        cur_str = str(cur_file) if cur_file else None
        game_slots_map = {g["path"]: self.lib_mgr.scan_game_slots(g["path"], current_open_file=cur_str) for g in games}
        self._render_games_cards(games, game_slots_map, cur_file)

    def _set_sort_mode(self, mode: str):
        self.sort_mode = mode
        for m, b in self.sort_btns.items():
            if m == mode:
                b.configure(fg_color=BG_ACTIVE, text_color=TEXT_MAIN, font=get_ui_font(11, "bold"))
            else:
                b.configure(fg_color="transparent", text_color=TEXT_MUTED, font=get_ui_font(11))
        self._on_game_filter_change()

    def _render_games_cards(
        self,
        games: List[Dict[str, Any]],
        game_slots_map: Dict[str, List[Dict[str, Any]]],
        cur_file: Optional[Path]
    ):
        for w in self.scroll_list.winfo_children():
            w.destroy()

        if not games:
            empty_box = ctk.CTkFrame(
                self.scroll_list, fg_color=BG_CARD, corner_radius=12,
                border_width=1, border_color=BORDER_COLOR
            )
            empty_box.pack(fill="x", pady=40, padx=20)
            ctk.CTkLabel(
                empty_box,
                text="Nenhum jogo registrado na biblioteca ainda.\nAbra um save ou clique em '+ Adicionar pasta de jogo' acima.",
                font=get_ui_font(13), text_color=TEXT_MUTED, justify="center"
            ).pack(pady=30)
            return

        filtered = list(games)
        if self.filter_query:
            q = self.filter_query.lower()
            filtered = [
                g for g in filtered
                if q in str(g.get("title", "")).lower()
                or q in str(g.get("engine", "")).lower()
                or q in str(g.get("path", "")).lower()
            ]

        if self.sort_mode == "name":
            filtered.sort(key=lambda g: str(g.get("title", "")).lower())
        elif self.sort_mode == "engine":
            filtered.sort(key=lambda g: str(g.get("engine", "")).lower())
        else:
            filtered.sort(key=lambda g: g.get("last_opened", 0), reverse=True)

        for g in filtered:
            slots = game_slots_map.get(g["path"], [])
            self._create_game_card(self.scroll_list, g, slots, cur_file)

        # Sugestões de jogos vizinhos (#11:2240)
        if games:
            suggestions = [
                s for s in self.lib_mgr.discover_neighboring_games(games[0]["path"])
                if s.get("path") not in self.ignored_suggestions
            ]
            if suggestions:
                self._create_suggestions_card(self.scroll_list, suggestions, games[0].get("title", "seu jogo"))

        try:
            self.scroll_list.update_idletasks()
        except Exception:
            pass

    def _toggle_game_collapse(self, game_path: str):
        if game_path in self.collapsed_games:
            self.collapsed_games.remove(game_path)
        else:
            self.collapsed_games.add(game_path)
        self._on_game_filter_change()

    def _create_game_card(self, parent, game: Dict[str, Any], slots: List[Dict[str, Any]], current_file: Optional[Path]):
        """Card colapsável do jogo com SaveSlot cards ricos (#11:2023)."""
        g_path = game["path"]
        is_collapsed = g_path in self.collapsed_games
        has_active_slot = any(s.get("is_current") for s in slots)

        card = ctk.CTkFrame(
            parent, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=PRIMARY_COLOR if has_active_slot else BORDER_COLOR
        )
        card.pack(fill="x", pady=6, padx=2)

        # Header do Card (#11:2024)
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=14)

        chev_name = "chevron-right" if is_collapsed else "chevron-down"
        chev_ico = get_icon(chev_name, size=(16, 16))
        btn_collapse = ctk.CTkButton(
            header, text="" if chev_ico else ("▸" if is_collapsed else "▾"),
            image=chev_ico, width=26, height=26, fg_color="transparent",
            hover_color=BG_SUB, corner_radius=6,
            command=lambda gp=g_path: self._toggle_game_collapse(gp)
        )
        btn_collapse.pack(side="left", padx=(0, 8))

        # Cover Tile 44x44 (#11:2027)
        cover_tile = ctk.CTkFrame(
            header, width=44, height=44, corner_radius=10,
            fg_color=WARNING_BG, border_width=1, border_color=PRIMARY_COLOR
        )
        cover_tile.pack(side="left", padx=(0, 12))
        cover_tile.pack_propagate(False)

        gp_ico = get_icon("gamepad", size=(20, 20), tint=PRIMARY_COLOR[1])
        ctk.CTkLabel(cover_tile, text="" if gp_ico else "🎮", image=gp_ico).pack(expand=True)

        # Info Box (Título + Badges + Caminho) (#11:2030)
        info_box = ctk.CTkFrame(header, fg_color="transparent")
        info_box.pack(side="left", fill="both", expand=True)

        title_row = ctk.CTkFrame(info_box, fg_color="transparent")
        title_row.pack(anchor="w")

        ctk.CTkLabel(
            title_row, text=game.get("title", "Jogo"),
            font=get_ui_font(15, "bold"), text_color=TEXT_MAIN
        ).pack(side="left", padx=(0, 8))

        eng_txt = game.get("engine", "RPG Maker")
        ctk.CTkLabel(
            title_row, text=f"● {eng_txt}", font=get_ui_font(11, "bold"),
            fg_color=WARNING_BG, text_color=PRIMARY_COLOR,
            corner_radius=999, height=20, padx=8
        ).pack(side="left", padx=(0, 6))

        has_db = bool(game.get("data_dir") or (Path(g_path) / "www" / "data").exists() or (Path(g_path) / "data").exists())
        db_badge_txt = "● BD conectado" if has_db else "BD não encontrado"
        ctk.CTkLabel(
            title_row, text=db_badge_txt, font=get_ui_font(11, "bold"),
            fg_color=SUCCESS_BG if has_db else BG_ACTIVE,
            text_color=SUCCESS_COLOR if has_db else TEXT_MUTED,
            corner_radius=999, height=20, padx=8
        ).pack(side="left")

        ctk.CTkLabel(
            info_box, text=str(game.get("save_dir") or g_path),
            font=get_mono_font(11), text_color=TEXT_SUBTLE, anchor="w"
        ).pack(anchor="w", pady=(2, 0))

        # Ações e Contagem à Direita (#11:2041)
        right_box = ctk.CTkFrame(header, fg_color="transparent")
        right_box.pack(side="right")

        never_c = sum(1 for s in slots if s.get("never_opened", False))
        summary_str = f"{len(slots)} saves · {never_c} nunca abertos" if never_c else f"{len(slots)} saves"
        ctk.CTkLabel(
            right_box, text=summary_str, font=get_mono_font(11),
            text_color=TEXT_MUTED
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            right_box, text="Renomear", width=78, height=28,
            font=get_ui_font(11), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER_COLOR, corner_radius=6,
            command=lambda g=game: self._handle_rename_game(g)
        ).pack(side="left", padx=3)

        folder_ico = get_icon("folder-open", size=(13, 13))
        ctk.CTkButton(
            right_box, text=" Abrir pasta", image=folder_ico, compound="left",
            width=98, height=28, font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR, corner_radius=6,
            command=lambda p=game.get("save_dir", g_path): self._open_dir_in_os(p)
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            right_box, text="Ver slots →", width=88, height=28,
            font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=PRIMARY_COLOR,
            border_width=1, border_color=BORDER_SUBTLE, corner_radius=6,
            command=lambda g=game: self.show_game_details(g)
        ).pack(side="left", padx=(3, 0))

        if is_collapsed or not slots:
            return

        ctk.CTkFrame(card, height=1, fg_color=BORDER_COLOR).pack(fill="x")

        # Body Expandido: Row de SaveSlot Cards Ricos (#11:2051 / #10:1367)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=14)

        slots_row = ctk.CTkFrame(body, fg_color="transparent")
        slots_row.pack(fill="x")

        for s in slots[:4]:
            self._create_rich_slot_card(slots_row, game, s)

        if len(slots) > 4:
            more_count = len(slots) - 4
            more_card = ctk.CTkFrame(
                slots_row, width=100, height=148, corner_radius=10,
                fg_color=BG_SUB, border_width=1, border_color=BORDER_COLOR,
                cursor="hand2"
            )
            more_card.pack(side="left", padx=5, pady=2)
            more_card.pack_propagate(False)

            lbl_m1 = ctk.CTkLabel(
                more_card, text=f"+{more_count}", font=get_mono_font(16, "bold"),
                text_color=TEXT_MUTED
            )
            lbl_m1.pack(expand=True, pady=(32, 0))
            lbl_m2 = ctk.CTkLabel(
                more_card, text="ver todos", font=get_ui_font(11),
                text_color=TEXT_SUBTLE
            )
            lbl_m2.pack(expand=True, pady=(0, 32))

            for w in (more_card, lbl_m1, lbl_m2):
                w.bind("<Button-1>", lambda e, g=game: self.show_game_details(g))

        # Rodapé informativo do card (#11:2134)
        hint_row = ctk.CTkFrame(body, fg_color="transparent")
        hint_row.pack(fill="x", pady=(10, 0))

        sp_ico = get_icon("sparkles", size=(13, 13))
        if sp_ico:
            ctk.CTkLabel(hint_row, text="", image=sp_ico).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            hint_row,
            text="Prévias lidas em segundo plano sem abrir o save · clique em um slot para inspecionar ou abrir no editor",
            font=get_ui_font(11), text_color=TEXT_SUBTLE
        ).pack(side="left")

        btn_all = ctk.CTkButton(
            hint_row, text=f"Ver todos os {len(slots)} slots →",
            height=22, font=get_ui_font(11, "bold"),
            fg_color="transparent", hover_color=BG_SUB,
            text_color=PRIMARY_COLOR,
            command=lambda g=game: self.show_game_details(g)
        )
        btn_all.pack(side="right")

    def _create_rich_slot_card(self, parent, game: Dict[str, Any], slot: Dict[str, Any]):
        """Componente SaveSlot Card rico (#10:1367)."""
        is_cur = slot.get("is_current", False)
        has_bak = slot.get("has_backup", False)
        preview = self._get_cached_slot_preview(slot["path"], fetch_sync=False)

        scard = ctk.CTkFrame(
            parent, width=224, height=148, corner_radius=10,
            fg_color=BG_SUB, border_width=1,
            border_color=PRIMARY_COLOR if is_cur else BORDER_COLOR,
            cursor="hand2"
        )
        scard.pack(side="left", padx=(0, 10), pady=2)
        scard.pack_propagate(False)

        inner = ctk.CTkFrame(scard, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        # Topo: SLOT N + State Badge
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            top, text=str(slot["slot_label"]).upper(),
            font=get_mono_font(10, "bold"), text_color=TEXT_SUBTLE
        ).pack(side="left")

        if is_cur:
            b_txt, b_bg, b_fg = "● Aberto agora", SUCCESS_BG, SUCCESS_COLOR
        elif has_bak:
            b_txt, b_bg, b_fg = "● Editado · .bak", WARNING_BG, PRIMARY_COLOR
        else:
            b_txt, b_bg, b_fg = "Nunca aberto" if slot.get("never_opened") else "Existente", BG_ACTIVE, TEXT_MUTED

        ctk.CTkLabel(
            top, text=b_txt, font=get_ui_font(10, "bold"),
            fg_color=b_bg, text_color=b_fg, corner_radius=999,
            height=18, padx=6
        ).pack(side="right")

        # Playtime grande (20px mono bold)
        pt_str = slot.get("playtime") or preview.get("playtime") or "00h 00m"
        ctk.CTkLabel(
            inner, text=pt_str, font=get_mono_font(19, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        ).pack(fill="x")

        # Nomes do grupo
        p_names = preview.get("party_names") or slot.get("heroes") or "Grupo ativo"
        ctk.CTkLabel(
            inner, text=p_names[:28], font=get_ui_font(11),
            text_color=TEXT_MUTED, anchor="w"
        ).pack(fill="x")

        # Data + Ouro
        meta_row = ctk.CTkFrame(inner, fg_color="transparent")
        meta_row.pack(fill="x", pady=(2, 4))

        ctk.CTkLabel(
            meta_row, text=slot.get("date_str") or "—",
            font=get_mono_font(10), text_color=TEXT_SUBTLE
        ).pack(side="left")

        ctk.CTkLabel(
            meta_row, text=preview.get("gold_str") or "",
            font=get_mono_font(10, "bold"), text_color=PRIMARY_COLOR
        ).pack(side="right")

        ctk.CTkFrame(inner, height=1, fg_color=BORDER_COLOR).pack(fill="x", pady=(2, 4))

        # Rodapé com nome do arquivo
        foot = ctk.CTkFrame(inner, fg_color="transparent")
        foot.pack(fill="x")

        f_ico = get_icon("file", size=(11, 11))
        if f_ico:
            ctk.CTkLabel(foot, text="", image=f_ico).pack(side="left", padx=(0, 4))

        ctk.CTkLabel(
            foot, text=slot["filename"], font=get_mono_font(10),
            text_color=TEXT_SUBTLE
        ).pack(side="left")

        ch_ico = get_icon("chevron-right", size=(12, 12))
        ctk.CTkLabel(foot, text="" if ch_ico else "›", image=ch_ico).pack(side="right")

        def _open_this_slot(event=None):
            self.selected_slot = slot
            self.show_game_details(game, initial_slot_path=slot["path"])

        for w in scard.winfo_children() + inner.winfo_children() + top.winfo_children() + meta_row.winfo_children() + foot.winfo_children():
            w.bind("<Button-1>", _open_this_slot)
        scard.bind("<Button-1>", _open_this_slot)

    def _create_suggestions_card(self, parent, suggestions: List[Dict[str, Any]], neighbor_name: str):
        """Card de sugestão de jogo vizinho com botões Ignorar e Adicionar (#11:2240)."""
        sug = suggestions[0]
        card = ctk.CTkFrame(
            parent, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_SUBTLE
        )
        card.pack(fill="x", pady=10, padx=2)

        p = ctk.CTkFrame(card, fg_color="transparent")
        p.pack(fill="x", padx=18, pady=14)

        star_tile = ctk.CTkFrame(
            p, width=36, height=36, corner_radius=8,
            fg_color=WARNING_BG, border_width=1, border_color=PRIMARY_COLOR
        )
        star_tile.pack(side="left", padx=(0, 12))
        star_tile.pack_propagate(False)

        star_ico = get_icon("star", size=(16, 16), tint=PRIMARY_COLOR[1])
        ctk.CTkLabel(star_tile, text="" if star_ico else "★", image=star_ico).pack(expand=True)

        txt_col = ctk.CTkFrame(p, fg_color="transparent")
        txt_col.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            txt_col,
            text=f"Outro jogo encontrado ao lado de {neighbor_name}",
            font=get_ui_font(13, "bold"), text_color=TEXT_MAIN, anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            txt_col,
            text=f"{sug['path']} · {sug['saves_count']} saves detectados · {sug['engine']}",
            font=get_mono_font(11), text_color=TEXT_MUTED, anchor="w"
        ).pack(anchor="w")

        plus_ico = get_icon("plus", size=(13, 13))
        ctk.CTkButton(
            p, text=" Adicionar à biblioteca", image=plus_ico, compound="left",
            width=164, height=30, font=get_ui_font(11, "bold"),
            fg_color=BG_SUB, hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE, corner_radius=6,
            command=lambda s=sug: self._add_suggested_game(s)
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            p, text="Ignorar", width=70, height=30,
            font=get_ui_font(11), fg_color="transparent",
            hover_color=BG_SUB, text_color=TEXT_MUTED, corner_radius=6,
            command=lambda sp=sug["path"]: self._ignore_suggested_game(sp)
        ).pack(side="right")

    def _ignore_suggested_game(self, sug_path: str):
        self.ignored_suggestions.add(sug_path)
        self._on_game_filter_change()

    def _add_suggested_game(self, sug: Dict[str, Any]):
        self.lib_mgr.register_game(sug["save_dir"], engine=sug["engine"], title=sug["name"])
        self.show_games_list()

    def _handle_rename_game(self, game: Dict[str, Any]):
        current_title = game.get("title", "")
        new_title = simpledialog.askstring(
            "Renomear Jogo", "Novo nome para o jogo na biblioteca:",
            initialvalue=current_title
        )
        if new_title and new_title.strip():
            self.lib_mgr.rename_game(game["path"], new_title.strip())
            game["title"] = new_title.strip()
            if self.current_screen == "game_detail":
                self.show_game_details(game)
            else:
                self.show_games_list()

    def _open_dir_in_os(self, dir_path: str | Path):
        p = Path(dir_path)
        if p.is_file():
            p = p.parent
        try:
            if os.name == "nt":
                os.startfile(p)
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(p)])
        except Exception:
            messagebox.showinfo("Caminho da Pasta", str(p))

    def show_game_details(self, game: Dict[str, Any], initial_slot_path: Optional[str] = None):
        """Tela 10 do Figma (#11:1618 / #11:2261): Detalhes de um Jogo, 4 Fatos, Tabela com Ouro e Pré-visualização."""
        self.current_screen = "game_detail"
        self.selected_game = game
        for w in self.container.winfo_children():
            w.destroy()

        cur_file = self.get_current_file_path()
        cur_str = str(cur_file) if cur_file else None
        slots = self.lib_mgr.scan_game_slots(game["path"], current_open_file=cur_str)

        # Carrega prévias dos slots para popular Ouro e Tempo
        slot_previews: Dict[str, Dict[str, Any]] = {}
        for s in slots:
            slot_previews[s["path"]] = self._get_cached_slot_preview(s["path"])

        # 1. Card de Cabeçalho do Jogo + Barra de 4 Fatos (#11:2262)
        header_card = ctk.CTkFrame(
            self.container, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        header_card.pack(fill="x", pady=(0, 14))

        p_h = ctk.CTkFrame(header_card, fg_color="transparent")
        p_h.pack(fill="x", padx=20, pady=14)

        btn_back = ctk.CTkButton(
            p_h, text="← Biblioteca", width=96, height=30,
            font=get_ui_font(12, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR, corner_radius=6,
            command=self.show_games_list
        )
        btn_back.pack(side="left", padx=(0, 14))

        cover_tile = ctk.CTkFrame(
            p_h, width=44, height=44, corner_radius=10,
            fg_color=WARNING_BG, border_width=1, border_color=PRIMARY_COLOR
        )
        cover_tile.pack(side="left", padx=(0, 12))
        cover_tile.pack_propagate(False)

        gp_ico = get_icon("gamepad", size=(20, 20), tint=PRIMARY_COLOR[1])
        ctk.CTkLabel(cover_tile, text="" if gp_ico else "🎮", image=gp_ico).pack(expand=True)

        title_box = ctk.CTkFrame(p_h, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        t_row = ctk.CTkFrame(title_box, fg_color="transparent")
        t_row.pack(anchor="w")

        ctk.CTkLabel(
            t_row, text=game.get("title", "Jogo"),
            font=get_ui_font(18, "bold"), text_color=TEXT_MAIN
        ).pack(side="left", padx=(0, 8))

        eng_txt = game.get("engine", "RPG Maker")
        ctk.CTkLabel(
            t_row, text=f"● {eng_txt}", font=get_ui_font(11, "bold"),
            fg_color=WARNING_BG, text_color=PRIMARY_COLOR,
            corner_radius=999, height=20, padx=8
        ).pack(side="left", padx=(0, 6))

        any_db = any(p.get("db_connected") for p in slot_previews.values())
        ctk.CTkLabel(
            t_row, text="● BD conectado" if any_db else "BD automático",
            font=get_ui_font(11, "bold"),
            fg_color=SUCCESS_BG if any_db else BG_ACTIVE,
            text_color=SUCCESS_COLOR if any_db else TEXT_MUTED,
            corner_radius=999, height=20, padx=8
        ).pack(side="left")

        ctk.CTkLabel(
            title_box, text=f"{game.get('save_dir') or game.get('path')}",
            font=get_mono_font(11), text_color=TEXT_SUBTLE, anchor="w"
        ).pack(anchor="w", pady=(2, 0))

        folder_ico = get_icon("folder-open", size=(13, 13))
        ctk.CTkButton(
            p_h, text=" Abrir pasta", image=folder_ico, compound="left",
            width=104, height=30, font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR, corner_radius=6,
            command=lambda p=game.get("save_dir", game["path"]): self._open_dir_in_os(p)
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            p_h, text="Renomear", width=84, height=30,
            font=get_ui_font(11), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER_COLOR, corner_radius=6,
            command=lambda g=game: self._handle_rename_game(g)
        ).pack(side="right")

        ctk.CTkFrame(header_card, height=1, fg_color=BORDER_COLOR).pack(fill="x")

        # Barra de 4 Fatos (#11:2279: SAVES / TEMPO TOTAL / BANCO DE DADOS / ÚLTIMO ABERTO)
        facts_bar = ctk.CTkFrame(header_card, fg_color=BG_SUB, corner_radius=0)
        facts_bar.pack(fill="x", padx=2, pady=(0, 2))
        facts_bar.grid_columnconfigure((0, 1, 2, 3), weight=1)

        never_c = sum(1 for s in slots if s.get("never_opened", False))
        opened_c = len(slots) - never_c
        first_prev = next(iter(slot_previews.values()), {})
        db_sum = first_prev.get("db_summary") or "Catálogo pronto"

        facts = [
            ("SAVES", str(len(slots)), f"{opened_c} abertos · {never_c} nunca abertos"),
            ("TEMPO NO SLOT", first_prev.get("playtime") or "—", "acumulado nos saves"),
            ("BANCO DE DADOS", "Conectado" if any_db else "Padrão", db_sum[:36]),
            ("ÚLTIMO ABERTO", slots[0]["slot_label"] if slots else "—", slots[0]["filename"] if slots else "—"),
        ]
        for idx, (f_lbl, f_val, f_sub) in enumerate(facts):
            f_cell = ctk.CTkFrame(facts_bar, fg_color="transparent")
            f_cell.grid(row=0, column=idx, sticky="nsew", padx=16, pady=10)
            ctk.CTkLabel(f_cell, text=f_lbl, font=get_ui_font(10, "bold"), text_color=TEXT_SUBTLE).pack(anchor="w")
            ctk.CTkLabel(f_cell, text=f_val, font=get_mono_font(14, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
            ctk.CTkLabel(f_cell, text=f_sub, font=get_ui_font(11), text_color=TEXT_MUTED).pack(anchor="w")

        # 2. Painel Dividido (Tabela de Slots à esquerda + Pré-visualização à direita)
        split = ctk.CTkFrame(self.container, fg_color="transparent")
        split.pack(fill="both", expand=True)

        # Tabela de Slots com coluna Ouro (#11:2291)
        left_table_box = ctk.CTkFrame(
            split, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        left_table_box.pack(side="left", fill="both", expand=True, padx=(0, 14))

        cols = ("slot", "heroes", "playtime", "gold", "saved_at", "status")
        self.tree_slots = ttk.Treeview(
            left_table_box, columns=cols, show="headings",
            selectmode="browse"
        )
        self.tree_slots.heading("slot", text="Slot")
        self.tree_slots.heading("heroes", text="Heróis")
        self.tree_slots.heading("playtime", text="Tempo")
        self.tree_slots.heading("gold", text="Ouro")
        self.tree_slots.heading("saved_at", text="Salvo em")
        self.tree_slots.heading("status", text="Status")

        self.tree_slots.column("slot", width=120, anchor="w")
        self.tree_slots.column("heroes", width=160, anchor="w")
        self.tree_slots.column("playtime", width=85, anchor="center")
        self.tree_slots.column("gold", width=100, anchor="e")
        self.tree_slots.column("saved_at", width=105, anchor="center")
        self.tree_slots.column("status", width=110, anchor="center")

        ysb = ttk.Scrollbar(left_table_box, orient="vertical", command=self.tree_slots.yview)
        self.tree_slots.configure(yscrollcommand=ysb.set)

        ysb.pack(side="right", fill="y", padx=(0, 6), pady=10)
        self.tree_slots.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)

        self.tree_slots.bind("<<TreeviewSelect>>", lambda e: self._on_slot_selected(slots, slot_previews))
        self.tree_slots.bind("<Double-1>", lambda e: self._handle_open_slot())

        for s in slots:
            pv = slot_previews.get(s["path"], {})
            self.tree_slots.insert(
                "", "end", iid=s["path"],
                values=(
                    f"{s['slot_label']} ({s['filename']})",
                    pv.get("party_names") or s.get("heroes") or "—",
                    s.get("playtime") or pv.get("playtime") or "—",
                    pv.get("gold_str") or "—",
                    s.get("date_str") or "—",
                    s["status"]
                )
            )

        # Painel Lateral de Pré-Visualização Rico (Direita, width=380 - #11:2401)
        self.right_preview = ctk.CTkFrame(
            split, fg_color=BG_CARD, width=380, corner_radius=12,
            border_width=1, border_color=PRIMARY_COLOR
        )
        self.right_preview.pack(side="right", fill="y")
        self.right_preview.pack_propagate(False)

        self._build_slot_preview_pane()

        # Seleciona o slot inicial
        target_item = (
            initial_slot_path
            if initial_slot_path and any(s["path"] == initial_slot_path for s in slots)
            else (
                str(cur_file.resolve())
                if cur_file and any(s["path"] == str(cur_file.resolve()) for s in slots)
                else (slots[0]["path"] if slots else None)
            )
        )
        if target_item:
            self.tree_slots.selection_set(target_item)
            self._on_slot_selected(slots, slot_previews)

        try:
            self.container.update_idletasks()
        except Exception:
            pass

    def _build_slot_preview_pane(self):
        p = ctk.CTkFrame(self.right_preview, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=18, pady=16)

        # Topo: PRÉ-VISUALIZAÇÃO + Badge de Status (#11:2402)
        top_row = ctk.CTkFrame(p, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 4))

        eye_ico = get_icon("eye", size=(13, 13), tint=PRIMARY_COLOR[1])
        if eye_ico:
            ctk.CTkLabel(top_row, text="", image=eye_ico).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            top_row, text="PRÉ-VISUALIZAÇÃO", font=get_ui_font(10, "bold"),
            text_color=PRIMARY_COLOR
        ).pack(side="left")

        self.lbl_prev_status = ctk.CTkLabel(
            top_row, text="—", font=get_ui_font(10, "bold"),
            fg_color=BG_ACTIVE, text_color=TEXT_MUTED,
            corner_radius=999, height=20, padx=8
        )
        self.lbl_prev_status.pack(side="right")

        self.lbl_prev_slot_title = ctk.CTkLabel(
            p, text="Slot —", font=get_ui_font(20, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        )
        self.lbl_prev_slot_title.pack(fill="x")

        self.lbl_prev_filename = ctk.CTkLabel(
            p, text="Selecione um slot ao lado", font=get_mono_font(11),
            text_color=TEXT_SUBTLE, anchor="w"
        )
        self.lbl_prev_filename.pack(fill="x", pady=(0, 10))

        # 3 Mini-cards: TEMPO / OURO / PASSOS (#11:2413)
        stats_grid = ctk.CTkFrame(p, fg_color="transparent")
        stats_grid.pack(fill="x", pady=(0, 10))
        stats_grid.grid_columnconfigure((0, 1, 2), weight=1)

        self.lbl_prev_time = self._create_mini_stat(stats_grid, 0, "TEMPO", "—", TEXT_MAIN)
        self.lbl_prev_gold = self._create_mini_stat(stats_grid, 1, "OURO", "—", PRIMARY_COLOR)
        self.lbl_prev_steps = self._create_mini_stat(stats_grid, 2, "PASSOS", "—", TEXT_MAIN)

        # Lista do Grupo com barras de HP (#11:2424)
        ctk.CTkLabel(
            p, text="GRUPO", font=get_ui_font(10, "bold"),
            text_color=TEXT_SUBTLE, anchor="w"
        ).pack(fill="x", pady=(2, 4))

        self.prev_party_box = ctk.CTkFrame(p, fg_color="transparent")
        self.prev_party_box.pack(fill="x", pady=(0, 8))

        self.lbl_prev_heroes = ctk.CTkLabel(
            self.prev_party_box, text="—", font=get_ui_font(11), text_color=TEXT_MUTED
        )
        self.lbl_prev_heroes.pack(anchor="w")

        ctk.CTkFrame(p, height=1, fg_color=BORDER_COLOR).pack(fill="x", pady=(4, 6))

        # Linha Inventário (#11:2452)
        inv_row = ctk.CTkFrame(p, fg_color="transparent")
        inv_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(inv_row, text="Inventário", font=get_ui_font(11), text_color=TEXT_MUTED).pack(side="left")
        self.lbl_prev_inv = ctk.CTkLabel(inv_row, text="—", font=get_mono_font(11), text_color=TEXT_MAIN)
        self.lbl_prev_inv.pack(side="right")

        # DB Notice (#11:2455)
        db_row = ctk.CTkFrame(p, fg_color="transparent")
        db_row.pack(fill="x", pady=(2, 6))
        db_ico = get_icon("database", size=(12, 12), tint=SUCCESS_COLOR[1])
        if db_ico:
            ctk.CTkLabel(db_row, text="", image=db_ico).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            db_row, text="Nomes resolvidos pelo banco de dados do jogo",
            font=get_ui_font(10), text_color=SUCCESS_COLOR
        ).pack(side="left")

        # Banner de aviso se houver alterações não salvas no save atual (#11:2462)
        self.dirty_warn_box = ctk.CTkFrame(
            p, fg_color=WARNING_BG, corner_radius=8,
            border_width=1, border_color=PRIMARY_COLOR
        )
        self.lbl_dirty_warn = ctk.CTkLabel(
            self.dirty_warn_box,
            text="O save atual tem alterações não salvas.\nAo abrir outro slot você poderá salvar ou descartar.",
            font=get_ui_font(10), text_color=PRIMARY_COLOR, justify="left", padx=10, pady=6
        )
        self.lbl_dirty_warn.pack(anchor="w")
        if self.is_current_dirty():
            self.dirty_warn_box.pack(fill="x", pady=(2, 6))

        # Botões de Ação do Slot no Rodapé (#11:2466)
        btn_box = ctk.CTkFrame(p, fg_color="transparent")
        btn_box.pack(fill="x", side="bottom")

        self.btn_open_slot = ctk.CTkButton(
            btn_box, text="Abrir no editor", height=34,
            font=get_ui_font(12, "bold"), fg_color=PRIMARY_COLOR,
            hover_color=PRIMARY_HOVER, text_color=PRIMARY_TEXT,
            corner_radius=6, command=self._handle_open_slot
        )
        self.btn_open_slot.pack(fill="x", pady=(0, 6))

        sec_row = ctk.CTkFrame(btn_box, fg_color="transparent")
        sec_row.pack(fill="x")

        self.btn_show_folder = ctk.CTkButton(
            sec_row, text="Mostrar na pasta", height=30,
            font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR, corner_radius=6,
            command=self._handle_show_in_folder
        )
        self.btn_show_folder.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_duplicate_slot = ctk.CTkButton(
            sec_row, text="Duplicar", height=30,
            font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR, corner_radius=6,
            command=self._handle_duplicate_slot
        )
        self.btn_duplicate_slot.pack(side="right", fill="x", expand=True, padx=(4, 0))

    def _create_mini_stat(self, parent, col: int, label: str, initial_val: str, color) -> ctk.CTkLabel:
        cell = ctk.CTkFrame(parent, fg_color=BG_SUB, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        cell.grid(row=0, column=col, padx=3, sticky="nsew")
        ctk.CTkLabel(cell, text=label, font=get_ui_font(9, "bold"), text_color=TEXT_SUBTLE).pack(anchor="w", padx=8, pady=(6, 0))
        lbl = ctk.CTkLabel(cell, text=initial_val, font=get_mono_font(12, "bold"), text_color=color)
        lbl.pack(anchor="w", padx=8, pady=(0, 6))
        return lbl

    def _on_slot_selected(self, slots: List[Dict[str, Any]], slot_previews: Optional[Dict[str, Dict[str, Any]]] = None):
        sel = self.tree_slots.selection()
        if not sel:
            return
        path_str = sel[0]
        slot = next((s for s in slots if s["path"] == path_str), None)
        if not slot:
            return
        self.selected_slot = slot

        pv = (slot_previews or {}).get(path_str) or self._get_cached_slot_preview(path_str)

        self.lbl_prev_slot_title.configure(text=slot["slot_label"])
        self.lbl_prev_filename.configure(text=f"{slot['filename']} · salvo {slot.get('date_str', '')}")
        self.lbl_prev_status.configure(text=slot["status"])

        self.lbl_prev_time.configure(text=slot.get("playtime") or pv.get("playtime") or "—")
        self.lbl_prev_gold.configure(text=pv.get("gold_str") or "—")
        steps = pv.get("steps", 0)
        self.lbl_prev_steps.configure(text=f"{steps:,}".replace(",", ".") if steps else "—")

        ic = pv.get("items_count", 0)
        wc = pv.get("weapons_count", 0)
        ac = pv.get("armors_count", 0)
        self.lbl_prev_inv.configure(text=f"{ic} itens · {wc} armas · {ac} armaduras")

        self.btn_open_slot.configure(text=f"Abrir {slot['slot_label']} no editor")

        # Renderiza membros do grupo com avatar e barra de HP (#11:2426)
        for w in self.prev_party_box.winfo_children():
            w.destroy()

        members = pv.get("party_members") or []
        if not members:
            ctk.CTkLabel(
                self.prev_party_box, text=slot.get("heroes") or "Grupo padrão",
                font=get_ui_font(11), text_color=TEXT_MUTED
            ).pack(anchor="w")
            return

        for m in members[:4]:
            r = ctk.CTkFrame(self.prev_party_box, fg_color=BG_SUB, corner_radius=6, height=30)
            r.pack(fill="x", pady=2)
            r.pack_propagate(False)

            m_name = str(m.get("name", "Herói"))
            parts = m_name.split()
            ini = (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else m_name[:2].upper()

            ctk.CTkLabel(
                r, text=ini, width=22, height=22, corner_radius=11,
                fg_color=BG_ACTIVE, font=get_ui_font(9, "bold"), text_color=PRIMARY_COLOR
            ).pack(side="left", padx=(6, 8))

            ctk.CTkLabel(
                r, text=m_name, font=get_ui_font(11, "bold"), text_color=TEXT_MAIN
            ).pack(side="left")

            ctk.CTkLabel(
                r, text=f"Nv {m.get('level', 1)}", font=get_mono_font(10), text_color=TEXT_MUTED
            ).pack(side="right", padx=(6, 8))

            hp = m.get("hp", 100)
            mhp = max(1, m.get("max_hp", hp) or hp or 1)
            bar = ctk.CTkProgressBar(r, width=54, height=4, corner_radius=2, fg_color=BG_ACTIVE, progress_color=HP_COLOR)
            bar.pack(side="right", padx=4)
            bar.set(min(1.0, max(0.0, float(hp) / float(mhp))))

        try:
            self.prev_party_box.update_idletasks()
        except Exception:
            pass

    def _handle_open_slot(self):
        if not self.selected_slot:
            return
        if self.is_current_dirty():
            ans = self.on_ask_save_dirty()
            if ans is None:
                return
        path = self.selected_slot["path"]
        self.on_open_save_file(path)

    def _handle_duplicate_slot(self):
        if not self.selected_slot:
            return
        orig_path = Path(self.selected_slot["path"])
        dest_path = orig_path.with_name(f"{orig_path.stem}.copy{orig_path.suffix}")
        try:
            shutil.copy2(orig_path, dest_path)
            messagebox.showinfo("Sucesso", f"Slot duplicado com sucesso:\n{dest_path.name}")
            if self.selected_game:
                self.show_game_details(self.selected_game)
        except Exception as e:
            messagebox.showerror("Erro ao duplicar", f"Não foi possível duplicar o slot:\n{e}")

    def _handle_show_in_folder(self):
        if not self.selected_slot:
            return
        self._open_dir_in_os(Path(self.selected_slot["path"]).parent)

    def _handle_add_game_dir(self):
        d = filedialog.askdirectory(title="Selecione a Pasta Raiz ou Pasta de Saves do Jogo")
        if not d:
            return
        p = Path(d)
        self.lib_mgr.register_game(p)
        self.show_games_list()
