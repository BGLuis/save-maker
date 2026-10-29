#!/usr/bin/env python3
"""
StatBar component for Save Maker.
Barra de progresso e estatísticas (HP, MP, EXP, TP) com visual moderno e proporcional.
"""

from typing import Tuple, Optional
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, SUCCESS_COLOR, BG_SUB, BG_ACTIVE,
    TEXT_MAIN, TEXT_MUTED, get_ui_font, get_mono_font
)

class StatBar(ctk.CTkFrame):
    """Barra de recursos com valores numéricos e indicador de preenchimento."""

    def __init__(
        self, master, label: str = "HP",
        current: int = 100, maximum: int = 100,
        fill_color: Optional[Tuple[str, str]] = None,
        height: int = 6, **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.label_text = label
        self.current = current
        self.maximum = max(1, maximum)
        self.fill_color = fill_color or SUCCESS_COLOR

        self._build_ui(height)

    def _build_ui(self, bar_height: int):
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 4))

        self.lbl_name = ctk.CTkLabel(
            top_row, text=self.label_text, font=get_ui_font(11, "bold"),
            text_color=TEXT_MUTED
        )
        self.lbl_name.pack(side="left")

        val_str = f"{self.current:,} / {self.maximum:,}".replace(",", ".")
        self.lbl_values = ctk.CTkLabel(
            top_row, text=val_str, font=get_mono_font(11),
            text_color=TEXT_MAIN
        )
        self.lbl_values.pack(side="right")

        # Barra de Progresso CTk
        pct = min(1.0, max(0.0, float(self.current) / float(self.maximum)))
        self.progress_bar = ctk.CTkProgressBar(
            self, height=bar_height, corner_radius=bar_height // 2,
            fg_color=BG_ACTIVE, progress_color=self.fill_color
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(pct)

    def update_values(self, current: int, maximum: int):
        self.current = current
        self.maximum = max(1, maximum)
        val_str = f"{self.current:,} / {self.maximum:,}".replace(",", ".")
        self.lbl_values.configure(text=val_str)
        pct = min(1.0, max(0.0, float(self.current) / float(self.maximum)))
        self.progress_bar.set(pct)
