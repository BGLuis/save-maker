#!/usr/bin/env python3
"""
Loading View — Tela de carregamento moderno e não-bloqueante para o Save Maker.
Exibe feedback visual instantâneo durante leitura de arquivos, descompressão e banco de dados.
Fiel à estética e tokens de design do Figma.
"""

from pathlib import Path
from typing import Optional
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, BG_CARD, BG_SUB, BG_ACTIVE, WARNING_BG,
    TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE, BORDER_COLOR, BORDER_SUBTLE,
    get_ui_font, get_mono_font, get_icon
)


class LoadingView(ctk.CTkFrame):
    """Tela de carregamento exibida durante operações de leitura de save."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._is_animating = False
        self._build_ui()

    def _build_ui(self):
        # Container centralizado
        center_box = ctk.CTkFrame(self, fg_color="transparent")
        center_box.pack(expand=True, fill="both", padx=80, pady=40)

        # Card centralizado
        card = ctk.CTkFrame(
            center_box, fg_color=BG_CARD, corner_radius=14,
            border_width=1, border_color=BORDER_COLOR
        )
        card.pack(expand=True, fill="x", padx=40, pady=20)

        pad = ctk.CTkFrame(card, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=32, pady=36)

        # Tile do Ícone 48x48
        tile = ctk.CTkFrame(
            pad, width=48, height=48, corner_radius=12,
            fg_color=WARNING_BG, border_width=1, border_color=PRIMARY_COLOR
        )
        tile.pack(pady=(0, 16))
        tile.pack_propagate(False)

        ref_ico = get_icon("refresh", size=(24, 24), tint=PRIMARY_COLOR[1])
        lbl_icon = ctk.CTkLabel(tile, text="" if ref_ico else "⏳", image=ref_ico)
        lbl_icon.pack(expand=True)

        # Título
        self.lbl_title = ctk.CTkLabel(
            pad, text="Carregando Save...",
            font=get_ui_font(18, "bold"), text_color=TEXT_MAIN
        )
        self.lbl_title.pack(pady=(0, 6))

        # Nome do arquivo / Subtítulo
        self.lbl_filename = ctk.CTkLabel(
            pad, text="Aguarde enquanto os dados são processados...",
            font=get_mono_font(12), text_color=TEXT_MUTED
        )
        self.lbl_filename.pack(pady=(0, 20))

        # Barra de Progresso Indeterminada
        self.progress_bar = ctk.CTkProgressBar(
            pad, height=6, corner_radius=3,
            fg_color=BG_ACTIVE, progress_color=PRIMARY_COLOR,
            mode="indeterminate"
        )
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 16))

        # Status dinâmico da etapa
        status_box = ctk.CTkFrame(pad, fg_color=BG_SUB, corner_radius=6)
        status_box.pack(fill="x", padx=20)

        self.lbl_status = ctk.CTkLabel(
            status_box, text="Lendo arquivo e banco de dados do jogo...",
            font=get_ui_font(11), text_color=TEXT_SUBTLE,
            pady=8
        )
        self.lbl_status.pack(expand=True)

    def start(self, filename: str = "", message: str = "Lendo arquivo e banco de dados..."):
        """Inicia a animação de carregamento e atualiza os textos informativos."""
        fname = Path(filename).name if filename else ""
        if fname:
            self.lbl_filename.configure(text=f"Arquivo: {fname}")
        else:
            self.lbl_filename.configure(text="Aguarde enquanto os dados são processados...")

        self.lbl_status.configure(text=message)
        if not self._is_animating:
            self._is_animating = True
            try:
                self.progress_bar.start()
            except Exception:
                pass

    def set_status(self, message: str):
        """Atualiza a mensagem descritiva da etapa de carregamento."""
        try:
            self.lbl_status.configure(text=message)
        except Exception:
            pass

    def stop(self):
        """Para a animação de carregamento."""
        self._is_animating = False
        try:
            self.progress_bar.stop()
        except Exception:
            pass
