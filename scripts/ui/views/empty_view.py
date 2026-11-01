#!/usr/bin/env python3
"""
Empty State View (Tela 06 do Figma - nó #5:1866).
Aparece quando nenhum save está aberto, oferecendo Drag & Drop, atalhos de abertura
e lista de arquivos recentemente abertos.
Fiel ao Figma Save Maker.
"""

from typing import Callable, List, Dict, Any, Optional
from pathlib import Path
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    BG_CANVAS, BG_CARD, BG_SUB, BG_ACTIVE, WARNING_BG,
    TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE, BORDER_COLOR, BORDER_SUBTLE,
    get_ui_font, get_mono_font, get_icon
)


class EmptyView(ctk.CTkFrame):
    """Tela de boas-vindas e seleção de save."""

    def __init__(
        self,
        master,
        on_choose_file: Callable[[], None],
        on_choose_game_dir: Callable[[], None],
        on_open_recent: Callable[[str], None],
        get_recent_files: Callable[[], List[Dict[str, Any]]],
        on_clear_recents: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_choose_file = on_choose_file
        self.on_choose_game_dir = on_choose_game_dir
        self.on_open_recent = on_open_recent
        self.get_recent_files = get_recent_files
        self.on_clear_recents = on_clear_recents

        self._build_ui()

    def _build_ui(self):
        # Container centralizado (max width 680px fiel ao Figma #5:1866)
        center_box = ctk.CTkFrame(self, fg_color="transparent")
        center_box.pack(expand=True, fill="both", padx=80, pady=24)

        # 1. Card de Drag & Drop (#5:1867)
        drop_card = ctk.CTkFrame(
            center_box, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_SUBTLE
        )
        drop_card.pack(fill="x", pady=(0, 20), ipady=14)

        # Tile 56x56 dourado com ícone upload (#5:1868)
        icon_tile = ctk.CTkFrame(
            drop_card, width=56, height=56, corner_radius=12,
            fg_color=WARNING_BG, border_width=1, border_color=PRIMARY_COLOR
        )
        icon_tile.pack(pady=(24, 12))
        icon_tile.pack_propagate(False)

        upload_ico = get_icon("upload", size=(24, 24), tint=PRIMARY_COLOR[1])
        lbl_icon = ctk.CTkLabel(icon_tile, text="" if upload_ico else "📥", image=upload_ico)
        lbl_icon.pack(expand=True)

        lbl_title = ctk.CTkLabel(
            drop_card, text="Arraste um arquivo de save para cá",
            font=get_ui_font(18, "bold"), text_color=TEXT_MAIN
        )
        lbl_title.pack(pady=(0, 6))

        lbl_desc = ctk.CTkLabel(
            drop_card,
            text="O motor e a compressão são detectados automaticamente.\nNada é alterado até você clicar em Salvar — um backup .bak é criado antes.",
            font=get_ui_font(13), text_color=TEXT_MUTED, justify="center"
        )
        lbl_desc.pack(pady=(0, 16))

        # Botões de Ação (#5:1872)
        btn_row = ctk.CTkFrame(drop_card, fg_color="transparent")
        btn_row.pack(pady=(0, 14))

        folder_ico = get_icon("folder-open", size=(16, 16), tint="#1A1408")
        btn_open = ctk.CTkButton(
            btn_row, text=" Escolher arquivo…", image=folder_ico, compound="left",
            font=get_ui_font(13, "bold"), width=164, height=34,
            fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER,
            text_color=PRIMARY_TEXT, corner_radius=6, command=self.on_choose_file
        )
        btn_open.pack(side="left", padx=5)

        db_ico = get_icon("database", size=(15, 15))
        btn_dir = ctk.CTkButton(
            btn_row, text=" Selecionar pasta do jogo", image=db_ico, compound="left",
            font=get_ui_font(13, "bold"), width=194, height=34, fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR,
            corner_radius=6, command=self.on_choose_game_dir
        )
        btn_dir.pack(side="left", padx=5)

        # Formatos Suportados (#5:1882)
        formats_row = ctk.CTkFrame(drop_card, fg_color="transparent")
        formats_row.pack(pady=(4, 10))

        lbl_fmt = ctk.CTkLabel(
            formats_row, text="Formatos suportados:", font=get_ui_font(11),
            text_color=TEXT_SUBTLE
        )
        lbl_fmt.pack(side="left", padx=(0, 6))

        formats = [".rpgsave", ".rmmzsave", ".rvdata2", ".rvdata", ".rxdata", ".lsd", ".sav (Wolf)", ".json"]
        for fmt in formats:
            chip = ctk.CTkFrame(
                formats_row, fg_color=BG_ACTIVE, corner_radius=999,
                border_width=1, border_color=BORDER_COLOR
            )
            chip.pack(side="left", padx=2)
            lbl_c = ctk.CTkLabel(
                chip, text=fmt, font=get_ui_font(11, "bold"),
                text_color=TEXT_MUTED, padx=8, pady=1
            )
            lbl_c.pack()

        # 2. Card de Abertos Recentemente (#5:1892)
        self.recent_card = ctk.CTkFrame(
            center_box, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        self.recent_card.pack(fill="both", expand=True)

        recent_header = ctk.CTkFrame(self.recent_card, fg_color="transparent")
        recent_header.pack(fill="x", padx=16, pady=(12, 8))

        lbl_recent_title = ctk.CTkLabel(
            recent_header, text="Abertos recentemente", font=get_ui_font(13, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_recent_title.pack(side="left")

        self.btn_clear_recents = ctk.CTkButton(
            recent_header, text="Limpar histórico", width=110, height=22,
            font=get_ui_font(11), fg_color="transparent", hover_color=BG_SUB,
            text_color=TEXT_SUBTLE, corner_radius=4,
            command=self._handle_clear_recents
        )
        self.btn_clear_recents.pack(side="right")

        ctk.CTkFrame(self.recent_card, height=1, fg_color=BORDER_COLOR).pack(fill="x")

        # Container scrollável para a lista de recentes
        self.recent_list_frame = ctk.CTkScrollableFrame(
            self.recent_card, fg_color="transparent"
        )
        self.recent_list_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.refresh_recents()

    def _handle_clear_recents(self):
        if self.on_clear_recents:
            self.on_clear_recents()
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
            lbl_empty.pack(pady=24)
            return

        for idx, item in enumerate(recents[:6]):
            row = ctk.CTkFrame(
                self.recent_list_frame, fg_color="transparent", corner_radius=6,
                height=52, cursor="hand2"
            )
            row.pack(fill="x", pady=1, padx=4)
            row.pack_propagate(False)

            p_str = item["path"]
            fname = item.get("filename") or Path(p_str).name
            g_title = item.get("title") or item.get("game_title") or ""
            eng = item.get("engine") or "RPG Maker"
            rel_time = item.get("relative_time") or ""

            # Tile 32x32 com ícone file (#5:1898)
            f_tile = ctk.CTkFrame(row, width=32, height=32, corner_radius=6, fg_color=BG_SUB)
            f_tile.pack(side="left", padx=(8, 12), pady=10)
            f_tile.pack_propagate(False)

            file_ico = get_icon("file", size=(16, 16))
            lbl_f_icon = ctk.CTkLabel(f_tile, text="" if file_ico else "📄", image=file_ico)
            lbl_f_icon.pack(expand=True)

            name_box = ctk.CTkFrame(row, fg_color="transparent")
            name_box.pack(side="left", fill="both", expand=True, pady=6)

            lbl_fname = ctk.CTkLabel(
                name_box, text=fname, font=get_mono_font(13, "bold"),
                text_color=TEXT_MAIN, anchor="w"
            )
            lbl_fname.pack(anchor="w")

            sub_str = f"{g_title} · {p_str}" if g_title and g_title != fname else p_str
            lbl_fpath = ctk.CTkLabel(
                name_box, text=sub_str,
                font=get_ui_font(11), text_color=TEXT_SUBTLE, anchor="w"
            )
            lbl_fpath.pack(anchor="w")

            # Chevron right (#5:1905)
            chev_ico = get_icon("chevron-right", size=(14, 14))
            lbl_chev = ctk.CTkLabel(row, text="" if chev_ico else "›", image=chev_ico)
            lbl_chev.pack(side="right", padx=(8, 8))

            # Relative time (#5:1904)
            if rel_time:
                lbl_time = ctk.CTkLabel(
                    row, text=rel_time, font=get_mono_font(11),
                    text_color=TEXT_SUBTLE
                )
                lbl_time.pack(side="right", padx=8)

            # Engine badge (#5:1903)
            is_mv_mz = "MV" in eng or "MZ" in eng
            badge_bg = WARNING_BG if is_mv_mz else BG_ACTIVE
            badge_fg = PRIMARY_COLOR if is_mv_mz else TEXT_MUTED
            badge_txt = f"● {eng}" if is_mv_mz else eng
            lbl_eng = ctk.CTkLabel(
                row, text=badge_txt, font=get_ui_font(11, "bold"),
                fg_color=badge_bg, text_color=badge_fg,
                corner_radius=999, height=20, padx=8
            )
            lbl_eng.pack(side="right", padx=6)

            for w in (row, f_tile, lbl_f_icon, name_box, lbl_fname, lbl_fpath, lbl_chev, lbl_eng):
                w.bind("<Button-1>", lambda e, p=p_str: self.on_open_recent(p))

            if idx < len(recents[:6]) - 1:
                ctk.CTkFrame(self.recent_list_frame, height=1, fg_color=BORDER_COLOR).pack(fill="x", padx=8)

        try:
            self.recent_list_frame.update_idletasks()
        except Exception:
            pass
