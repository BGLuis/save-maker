#!/usr/bin/env python3
"""
Library View (Telas 09 e 10 do Figma).
Gerenciamento da biblioteca de jogos, varredura de slots com prévia sem bloqueio
e visualização detalhada de slots de save com abertura direta no editor.
"""

from typing import Callable, List, Dict, Any, Optional
from pathlib import Path
import subprocess
import shutil
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, WARNING_COLOR, DANGER_COLOR,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)

class LibraryView(ctk.CTkFrame):
    """Visualização da Biblioteca de Jogos (Telas 09 e 10)."""

    def __init__(
        self, master,
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

        self._build_ui()

    def _build_ui(self):
        # Container principal com alternância de telas
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.show_games_list()

    def show_games_list(self):
        """Tela 09 do Figma: Lista de Jogos da Biblioteca."""
        self.current_screen = "list"
        for w in self.container.winfo_children():
            w.destroy()

        games = self.lib_mgr.get_games()

        # 1. Header com Métricas e Botões de Ação
        header_card = ctk.CTkFrame(
            self.container, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        header_card.pack(fill="x", pady=(0, 12))

        p_h = ctk.CTkFrame(header_card, fg_color="transparent")
        p_h.pack(fill="x", padx=20, pady=14)

        title_box = ctk.CTkFrame(p_h, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box, text="Biblioteca de Jogos", font=get_ui_font(18, "bold"),
            text_color=TEXT_MAIN
        ).pack(anchor="w")

        total_saves = sum(len(self.lib_mgr.scan_game_slots(g["path"])) for g in games) if games else 0
        self.lbl_stats = ctk.CTkLabel(
            title_box, text=f"{len(games)} jogos · {total_saves} saves encontrados",
            font=get_ui_font(11), text_color=TEXT_MUTED
        )
        self.lbl_stats.pack(anchor="w")

        actions_box = ctk.CTkFrame(p_h, fg_color="transparent")
        actions_box.pack(side="right")

        ref_ico = get_icon("refresh", size=(14, 14))
        ctk.CTkButton(
            actions_box, text=" Reescanear", image=ref_ico, compound="left",
            width=114, height=34, font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE, corner_radius=6,
            command=self.show_games_list
        ).pack(side="left", padx=4)

        plus_ico = get_icon("plus", size=(14, 14), tint="#0B0C10")
        ctk.CTkButton(
            actions_box, text=" Adicionar pasta de jogo", image=plus_ico, compound="left",
            width=188, height=34, font=get_ui_font(11, "bold"), fg_color=PRIMARY_COLOR,
            hover_color=PRIMARY_HOVER, text_color=PRIMARY_TEXT, corner_radius=6,
            command=self._handle_add_game_dir
        ).pack(side="left", padx=4)

        # 2. Lista Scrollável de Jogos
        scroll_list = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        scroll_list.pack(fill="both", expand=True)

        if not games:
            empty_box = ctk.CTkFrame(scroll_list, fg_color=BG_CARD, corner_radius=12)
            empty_box.pack(fill="x", pady=40, padx=20)
            ctk.CTkLabel(
                empty_box,
                text="Nenhum jogo registrado na biblioteca ainda.\nAbra um save ou clique em '+ Adicionar pasta de jogo' acima.",
                font=get_ui_font(13), text_color=TEXT_MUTED, justify="center"
            ).pack(pady=30)
            return

        cur_file = self.get_current_file_path()
        for g in games:
            self._create_game_card(scroll_list, g, cur_file)

        # Sugestões de jogos vizinhos (se houver pelo menos um jogo cadastrado)
        if games:
            suggestions = self.lib_mgr.discover_neighboring_games(games[0]["path"])
            if suggestions:
                self._create_suggestions_card(scroll_list, suggestions, games[0]["title"])

    def _create_game_card(self, parent, game: Dict[str, Any], current_file: Optional[Path]):
        card = ctk.CTkFrame(
            parent, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        card.pack(fill="x", pady=6, padx=2)

        p = ctk.CTkFrame(card, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=18, pady=14)

        # Topo do card
        top_row = ctk.CTkFrame(p, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 10))

        title_box = ctk.CTkFrame(top_row, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        lbl_title = ctk.CTkLabel(
            title_box, text=game.get("title", "Jogo"),
            font=get_ui_font(15, "bold"), text_color=TEXT_MAIN, anchor="w"
        )
        lbl_title.pack(anchor="w")

        lbl_meta = ctk.CTkLabel(
            title_box, text=f"{game.get('engine', 'RPG Maker')} · {game.get('save_dir', game.get('path'))}",
            font=get_ui_font(11), text_color=TEXT_MUTED, anchor="w"
        )
        lbl_meta.pack(anchor="w")

        btn_view_slots = ctk.CTkButton(
            top_row, text="Ver Slots →", width=95, height=32,
            font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=PRIMARY_COLOR,
            border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6,
            command=lambda g=game: self.show_game_details(g)
        )
        btn_view_slots.pack(side="right")

        btn_rename = ctk.CTkButton(
            top_row, text="Renomear", width=80, height=32,
            font=get_ui_font(11), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6,
            command=lambda g=game: self._handle_rename_game(g)
        )
        btn_rename.pack(side="right", padx=(0, 6))

        # Slots Chips Preview
        slots = self.lib_mgr.scan_game_slots(game["path"], current_open_file=str(current_file) if current_file else None)
        if slots:
            slots_row = ctk.CTkFrame(p, fg_color="transparent")
            slots_row.pack(fill="x", pady=(4, 0))

            for s in slots[:5]:
                chip = ctk.CTkFrame(
                    slots_row, fg_color=BG_SUB, corner_radius=6,
                    border_width=1, border_color=PRIMARY_COLOR if s.get("is_current") else BORDER_SUBTLE
                )
                chip.pack(side="left", padx=3)

                chip_p = ctk.CTkFrame(chip, fg_color="transparent")
                chip_p.pack(padx=8, pady=4)

                lbl_s_name = ctk.CTkLabel(
                    chip_p, text=s["slot_label"], font=get_ui_font(10, "bold"),
                    text_color=PRIMARY_COLOR if s.get("is_current") else TEXT_MAIN
                )
                lbl_s_name.pack(anchor="w")

                lbl_s_desc = ctk.CTkLabel(
                    chip_p, text=s.get("date_str") or s["filename"],
                    font=get_mono_font(9), text_color=TEXT_MUTED
                )
                lbl_s_desc.pack(anchor="w")

    def _create_suggestions_card(self, parent, suggestions: List[Dict[str, Any]], neighbor_name: str):
        card = ctk.CTkFrame(
            parent, fg_color=BG_SUB, corner_radius=12,
            border_width=1, border_color=BORDER_SUBTLE
        )
        card.pack(fill="x", pady=12, padx=2)

        p = ctk.CTkFrame(card, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=18, pady=12)

        ctk.CTkLabel(
            p, text=f"💡 Outros jogos encontrados na mesma pasta que {neighbor_name}:",
            font=get_ui_font(12, "bold"), text_color=TEXT_MAIN
        ).pack(anchor="w", pady=(0, 8))

        for sug in suggestions[:3]:
            row = ctk.CTkFrame(p, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row, text=f"• {sug['name']} ({sug['saves_count']} saves · {sug['engine']})",
                font=get_ui_font(11), text_color=TEXT_MUTED
            ).pack(side="left")

            btn_add = ctk.CTkButton(
                row, text="Adicionar à biblioteca", width=140, height=24,
                font=get_ui_font(10, "bold"), fg_color=PRIMARY_COLOR,
                hover_color=PRIMARY_HOVER, text_color=PRIMARY_TEXT,
                command=lambda s=sug: self._add_suggested_game(s)
            )
            btn_add.pack(side="right")

    def _add_suggested_game(self, sug: Dict[str, Any]):
        self.lib_mgr.register_game(sug["save_dir"], engine=sug["engine"], title=sug["name"])
        self.show_games_list()

    def _handle_rename_game(self, game: Dict[str, Any]):
        current_title = game.get("title", "")
        new_title = simpledialog.askstring("Renomear Jogo", "Novo nome para o jogo na biblioteca:", initialvalue=current_title)
        if new_title and new_title.strip():
            self.lib_mgr.rename_game(game["path"], new_title.strip())
            game["title"] = new_title.strip()
            if self.current_screen == "game_detail":
                self.show_game_details(game)
            else:
                self.show_games_list()

    def show_game_details(self, game: Dict[str, Any]):
        """Tela 10 do Figma: Detalhes de um Jogo e seus Slots de Save."""
        self.current_screen = "game_detail"
        self.selected_game = game
        for w in self.container.winfo_children():
            w.destroy()

        cur_file = self.get_current_file_path()
        slots = self.lib_mgr.scan_game_slots(game["path"], current_open_file=str(cur_file) if cur_file else None)

        # 1. Header do Jogo Selecionado
        header_card = ctk.CTkFrame(
            self.container, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        header_card.pack(fill="x", pady=(0, 12))

        p_h = ctk.CTkFrame(header_card, fg_color="transparent")
        p_h.pack(fill="x", padx=20, pady=14)

        btn_back = ctk.CTkButton(
            p_h, text="← Voltar", width=80, height=30,
            font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            command=self.show_games_list
        )
        btn_back.pack(side="left", padx=(0, 14))

        title_box = ctk.CTkFrame(p_h, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            title_box, text=game.get("title", "Jogo"),
            font=get_ui_font(18, "bold"), text_color=TEXT_MAIN
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box, text=f"{game.get('engine', 'RPG Maker')} · {game.get('save_dir')}",
            font=get_ui_font(11), text_color=TEXT_MUTED
        ).pack(anchor="w")

        btn_rename_detail = ctk.CTkButton(
            p_h, text="Renomear Jogo", width=110, height=30,
            font=get_ui_font(11), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6,
            command=lambda g=game: self._handle_rename_game(g)
        )
        btn_rename_detail.pack(side="right", padx=6)

        # 2. Painel Dividido (Tabela de Slots à esquerda + Pré-visualização à direita)
        split = ctk.CTkFrame(self.container, fg_color="transparent")
        split.pack(fill="both", expand=True)

        # Tabela de Slots (Esquerda)
        left_table_box = ctk.CTkFrame(
            split, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        left_table_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        cols = ("slot", "heroes", "playtime", "saved_at", "status")
        self.tree_slots = ttk.Treeview(
            left_table_box, columns=cols, show="headings",
            selectmode="browse"
        )
        self.tree_slots.heading("slot", text="Slot / Arquivo")
        self.tree_slots.heading("heroes", text="Heróis")
        self.tree_slots.heading("playtime", text="Tempo")
        self.tree_slots.heading("saved_at", text="Salvo em")
        self.tree_slots.heading("status", text="Status")

        self.tree_slots.column("slot", width=120, anchor="w")
        self.tree_slots.column("heroes", width=160, anchor="w")
        self.tree_slots.column("playtime", width=80, anchor="center")
        self.tree_slots.column("saved_at", width=110, anchor="center")
        self.tree_slots.column("status", width=110, anchor="center")

        ysb = ttk.Scrollbar(left_table_box, orient="vertical", command=self.tree_slots.yview)
        self.tree_slots.configure(yscrollcommand=ysb.set)

        self.tree_slots.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        ysb.pack(side="right", fill="y", padx=(0, 6), pady=10)

        self.tree_slots.bind("<<TreeviewSelect>>", lambda e: self._on_slot_selected(slots))

        # Preenche a tabela com os slots
        for s in slots:
            self.tree_slots.insert(
                "", "end", iid=s["path"],
                values=(
                    s["slot_label"],
                    s.get("heroes") or "—",
                    s.get("playtime") or "—",
                    s.get("date_str") or "—",
                    s["status"]
                )
            )

        # Painel Lateral de Pré-Visualização (Direita)
        self.right_preview = ctk.CTkFrame(
            split, fg_color=BG_CARD, width=320, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        self.right_preview.pack(side="right", fill="y")
        self.right_preview.pack_propagate(False)

        self._build_slot_preview_pane()

        # Seleciona o primeiro slot ou o atual
        first_item = str(cur_file.resolve()) if cur_file and str(cur_file.resolve()) in [s["path"] for s in slots] else (slots[0]["path"] if slots else None)
        if first_item:
            self.tree_slots.selection_set(first_item)
            self._on_slot_selected(slots)

    def _build_slot_preview_pane(self):
        p = ctk.CTkFrame(self.right_preview, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            p, text="Pré-visualização", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN
        ).pack(anchor="w")

        self.lbl_prev_filename = ctk.CTkLabel(
            p, text="Selecione um slot ao lado", font=get_mono_font(11),
            text_color=PRIMARY_COLOR[1], anchor="w"
        )
        self.lbl_prev_filename.pack(anchor="w", pady=(2, 10))

        # Metadados
        self.meta_prev_box = ctk.CTkFrame(p, fg_color=BG_SUB, corner_radius=8)
        self.meta_prev_box.pack(fill="x", pady=(0, 14))

        mp = ctk.CTkFrame(self.meta_prev_box, fg_color="transparent")
        mp.pack(fill="x", padx=12, pady=10)

        self.lbl_prev_status = ctk.CTkLabel(mp, text="Status: —", font=get_ui_font(11), text_color=TEXT_MAIN)
        self.lbl_prev_status.pack(anchor="w", pady=2)

        self.lbl_prev_heroes = ctk.CTkLabel(mp, text="Grupo: —", font=get_ui_font(11), text_color=TEXT_MUTED)
        self.lbl_prev_heroes.pack(anchor="w", pady=2)

        self.lbl_prev_time = ctk.CTkLabel(mp, text="Tempo: —", font=get_mono_font(11), text_color=TEXT_MUTED)
        self.lbl_prev_time.pack(anchor="w", pady=2)

        # Botões de Ação do Slot
        btn_box = ctk.CTkFrame(p, fg_color="transparent")
        btn_box.pack(fill="x", side="bottom", pady=4)

        self.btn_open_slot = ctk.CTkButton(
            btn_box, text="Abrir no editor", height=36,
            font=get_ui_font(12, "bold"), fg_color=PRIMARY_COLOR,
            hover_color=PRIMARY_HOVER, text_color=PRIMARY_TEXT,
            command=self._handle_open_slot
        )
        self.btn_open_slot.pack(fill="x", pady=4)

        self.btn_duplicate_slot = ctk.CTkButton(
            btn_box, text="Duplicar slot", height=32,
            font=get_ui_font(11), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE,
            command=self._handle_duplicate_slot
        )
        self.btn_duplicate_slot.pack(fill="x", pady=2)

        self.btn_show_folder = ctk.CTkButton(
            btn_box, text="Mostrar na pasta", height=32,
            font=get_ui_font(11), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE,
            command=self._handle_show_in_folder
        )
        self.btn_show_folder.pack(fill="x", pady=2)

    def _on_slot_selected(self, slots: List[Dict[str, Any]]):
        sel = self.tree_slots.selection()
        if not sel: return
        path_str = sel[0]
        slot = next((s for s in slots if s["path"] == path_str), None)
        if not slot: return
        self.selected_slot = slot

        self.lbl_prev_filename.configure(text=f"{slot['filename']} · {slot.get('date_str', '')}")
        self.lbl_prev_status.configure(text=f"Status: {slot['status']}")
        self.lbl_prev_heroes.configure(text=f"Grupo: {slot.get('heroes') or 'N/D'}")
        self.lbl_prev_time.configure(text=f"Tempo: {slot.get('playtime') or 'N/D'}")

    def _handle_open_slot(self):
        if not self.selected_slot: return

        # Se houver alterações pendentes no save atual, confirma antes
        if self.is_current_dirty():
            ans = self.on_ask_save_dirty()
            if ans is None:
                # Cancelou
                return

        path = self.selected_slot["path"]
        self.on_open_save_file(path)

    def _handle_duplicate_slot(self):
        if not self.selected_slot: return
        orig_path = Path(self.selected_slot["path"])
        # Cria uma cópia (ex: file2.1.rpgsave ou file2_copy.rpgsave)
        dest_path = orig_path.with_name(f"{orig_path.stem}.copy{orig_path.suffix}")
        try:
            shutil.copy2(orig_path, dest_path)
            messagebox.showinfo("Sucesso", f"Slot duplicado com sucesso:\n{dest_path.name}")
            if self.selected_game:
                self.show_game_details(self.selected_game)
        except Exception as e:
            messagebox.showerror("Erro ao duplicar", f"Não foi possível duplicar o slot:\n{e}")

    def _handle_show_in_folder(self):
        if not self.selected_slot: return
        f_path = Path(self.selected_slot["path"]).parent
        try:
            if os.name == 'nt':
                os.startfile(f_path)
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(f_path)])
        except Exception as e:
            messagebox.showinfo("Caminho do Save", str(f_path))

    def _handle_add_game_dir(self):
        d = filedialog.askdirectory(title="Selecione a Pasta Raiz ou Pasta de Saves do Jogo")
        if not d: return
        p = Path(d)
        game_info = self.lib_mgr.register_game(p)
        self.show_games_list()
