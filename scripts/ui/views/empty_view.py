#!/usr/bin/env python3
"""
Empty State View (Tela 06 do Figma).
Aparece quando nenhum save está aberto, oferecendo Drag & Drop, atalhos de abertura
e lista de arquivos recentemente abertos.
Fiel ao Figma Save Maker.
"""

from typing import Callable, List, Dict, Any, Optional
from pathlib import Path
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    BG_CANVAS, BG_CARD, BG_SUB, BG_ACTIVE,
    TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE, BORDER_COLOR, BORDER_SUBTLE,
    get_ui_font, get_mono_font, get_icon
)

class EmptyView(ctk.CTkFrame):
    """Tela de boas-vindas e seleção de save."""

    def __init__(
        self, master,
        on_choose_file: Callable[[], None],
        on_choose_game_dir: Callable[[], None],
        on_open_recent: Callable[[str], None],
        get_recent_files: Callable[[], List[Dict[str, Any]]],
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_choose_file = on_choose_file
        self.on_choose_game_dir = on_choose_game_dir
        self.on_open_recent = on_open_recent
        self.get_recent_files = get_recent_files

        self._build_ui()

    def _build_ui(self):
        # Container centralizado
        center_box = ctk.CTkFrame(self, fg_color="transparent")
        center_box.pack(expand=True, fill="both", padx=40, pady=24)

        # 1. Card de Drag & Drop
        drop_card = ctk.CTkFrame(
            center_box, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        drop_card.pack(fill="x", pady=(0, 16), ipady=16)

        upload_ico = get_icon("upload", size=(36, 36), tint="#E2B342")
        lbl_icon = ctk.CTkLabel(drop_card, text="" if upload_ico else "📥", image=upload_ico)
        lbl_icon.pack(pady=(16, 6))

        lbl_title = ctk.CTkLabel(
            drop_card, text="Arraste um arquivo de save para cá",
            font=get_ui_font(18, "bold"), text_color=TEXT_MAIN
        )
        lbl_title.pack(pady=(0, 6))

        lbl_desc = ctk.CTkLabel(
            drop_card,
            text="O motor e a compressão são detectados automaticamente.\nNada é alterado até você clicar em Salvar — um backup .bak é criado antes.",
            font=get_ui_font(12), text_color=TEXT_MUTED, justify="center"
        )
        lbl_desc.pack(pady=(0, 16))

        # Botões de Ação
        btn_row = ctk.CTkFrame(drop_card, fg_color="transparent")
        btn_row.pack(pady=(0, 14))

        folder_ico = get_icon("folder-open", size=(16, 16), tint="#0B0C10")
        btn_open = ctk.CTkButton(
            btn_row, text=" Escolher arquivo…", image=folder_ico, compound="left",
            font=get_ui_font(13, "bold"), width=164, height=36,
            fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER,
            text_color=PRIMARY_TEXT, corner_radius=6, command=self.on_choose_file
        )
        btn_open.pack(side="left", padx=8)

        db_ico = get_icon("database", size=(15, 15))
        btn_dir = ctk.CTkButton(
            btn_row, text=" Selecionar pasta do jogo", image=db_ico, compound="left",
            font=get_ui_font(13), width=188, height=36, fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6, command=self.on_choose_game_dir
        )
        btn_dir.pack(side="left", padx=8)

        # Formatos Suportados
        formats_row = ctk.CTkFrame(drop_card, fg_color="transparent")
        formats_row.pack(pady=(4, 8))

        formats = [".rpgsave", ".rmmzsave", ".rvdata2", ".rvdata", ".rxdata", ".lsd", ".sav (Wolf)", ".json"]
        for fmt in formats:
            chip = ctk.CTkLabel(
                formats_row, text=fmt, font=get_mono_font(10),
                text_color=TEXT_SUBTLE, fg_color=BG_SUB,
                corner_radius=4, padx=6, pady=2
            )
            chip.pack(side="left", padx=3)

        # 2. Card de Abertos Recentemente
        self.recent_card = ctk.CTkFrame(
            center_box, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.recent_card.pack(fill="both", expand=True)

        recent_header = ctk.CTkFrame(self.recent_card, fg_color="transparent")
        recent_header.pack(fill="x", padx=20, pady=(14, 8))

        lbl_recent_title = ctk.CTkLabel(
            recent_header, text="Abertos recentemente", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_recent_title.pack(side="left")

        # Container scrollável para a lista de recentes
        self.recent_list_frame = ctk.CTkScrollableFrame(
            self.recent_card, fg_color="transparent"
        )
        self.recent_list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.refresh_recents()

    def refresh_recents(self):
        """Atualiza a lista de arquivos recentes a partir do LibraryManager."""
        for w in self.recent_list_frame.winfo_children():
            w.destroy()

        recents = self.get_recent_files()
        if not recents:
            lbl_empty = ctk.CTkLabel(
                self.recent_list_frame, text="Nenhum arquivo aberto recentemente.",
                font=get_ui_font(12), text_color=TEXT_MUTED
            )
            lbl_empty.pack(pady=20)
            return

        for item in recents[:6]:
            row = ctk.CTkFrame(
                self.recent_list_frame, fg_color=BG_SUB, corner_radius=6,
                height=48, border_width=1, border_color=BORDER_SUBTLE
            )
            row.pack(fill="x", pady=4, padx=4)
            row.pack_propagate(False)

            p_str = item["path"]

            file_ico = get_icon("file", size=(14, 14))
            lbl_f_icon = ctk.CTkLabel(row, text="" if file_ico else "📄", image=file_ico)
            lbl_f_icon.pack(side="left", padx=(12, 8))

            name_box = ctk.CTkFrame(row, fg_color="transparent")
            name_box.pack(side="left", fill="both", expand=True, pady=6)

            title_text = item.get("game_title") or Path(p_str).name
            lbl_fname = ctk.CTkLabel(
                name_box, text=title_text, font=get_ui_font(12, "bold"),
                text_color=TEXT_MAIN, anchor="w"
            )
            lbl_fname.pack(anchor="w")

            lbl_fpath = ctk.CTkLabel(
                name_box, text=f"{p_str} · {item.get('engine', 'RPG Maker')}",
                font=get_mono_font(10), text_color=TEXT_MUTED, anchor="w"
            )
            lbl_fpath.pack(anchor="w")

            btn_open_rec = ctk.CTkButton(
                row, text="Abrir", width=64, height=28,
                font=get_ui_font(11, "bold"), fg_color=BG_CARD,
                hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
                border_width=1, border_color=BORDER_SUBTLE,
                corner_radius=4, command=lambda p=p_str: self.on_open_recent(p)
            )
            btn_open_rec.pack(side="right", padx=10)
