#!/usr/bin/env python3
"""
Overview View (Tela 01 do Figma).
Apresenta o resumo do save: Ouro com botões rápidos e delta, Estatísticas da Campanha,
Ações Rápidas em Lote descritivas e Cards do Grupo Atual.
Fiel ao Figma Save Maker.
"""

from typing import Callable, List, Dict, Any, Optional
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, DANGER_COLOR, DANGER_HOVER, WARNING_COLOR,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)
from ui.components.stat_bar import StatBar

class OverviewView(ctk.CTkScrollableFrame):
    """Tela de Visão Geral com cards informativos e cheats rápidos."""

    def __init__(
        self, master,
        on_apply_gold: Callable[[int], None],
        on_add_gold: Callable[[int], None],
        on_set_gold: Callable[[int], None],
        on_quick_heal_all: Callable[[], None],
        on_quick_level_up: Callable[[], None],
        on_quick_max_stats: Callable[[], None],
        on_unlock_items: Callable[[], None],
        on_unlock_weapons: Callable[[], None],
        on_unlock_armors: Callable[[], None],
        on_navigate_to_actors: Callable[[], None],
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_apply_gold = on_apply_gold
        self.on_add_gold = on_add_gold
        self.on_set_gold = on_set_gold
        self.on_quick_heal_all = on_quick_heal_all
        self.on_quick_level_up = on_quick_level_up
        self.on_quick_max_stats = on_quick_max_stats
        self.on_unlock_items = on_unlock_items
        self.on_unlock_weapons = on_unlock_weapons
        self.on_unlock_armors = on_unlock_armors
        self.on_navigate_to_actors = on_navigate_to_actors

        self._initial_gold: Optional[int] = None

        self._build_ui()

    def _build_ui(self):
        # 1. Linha Superior: Ouro & Campanha
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 16))

        # Card de Ouro (lado esquerdo)
        self.card_gold = ctk.CTkFrame(
            top_row, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.card_gold.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self._build_gold_card()

        # Card de Campanha (lado direito)
        self.card_campaign = ctk.CTkFrame(
            top_row, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.card_campaign.pack(side="right", fill="both", expand=True, padx=(8, 0))

        self._build_campaign_card()

        # 2. Card de Ações Rápidas (Cheats)
        self.card_cheats = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.card_cheats.pack(fill="x", pady=(0, 16))

        self._build_cheats_card()

        # 3. Card do Grupo Atual
        self.card_party = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.card_party.pack(fill="x", pady=(0, 16))

        self._build_party_card()

    def _build_gold_card(self):
        pad_box = ctk.CTkFrame(self.card_gold, fg_color="transparent")
        pad_box.pack(fill="both", expand=True, padx=20, pady=16)

        header = ctk.CTkFrame(pad_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        coins_icon = get_icon("coins", size=(18, 18), tint="#E2B342")
        lbl_icon = ctk.CTkLabel(header, text="" if coins_icon else "🪙", image=coins_icon)
        lbl_icon.pack(side="left", padx=(0, 6))

        lbl_title = ctk.CTkLabel(
            header, text="Ouro do grupo", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_title.pack(side="left")

        # Valor em destaque Mono Display
        val_row = ctk.CTkFrame(pad_box, fg_color="transparent")
        val_row.pack(fill="x", pady=(0, 12))

        self.lbl_gold_display = ctk.CTkLabel(
            val_row, text="0 G", font=get_mono_font(24, "bold"),
            text_color=TEXT_MAIN
        )
        self.lbl_gold_display.pack(side="left")

        self.lbl_gold_delta = ctk.CTkLabel(
            val_row, text="", font=get_mono_font(11),
            text_color=SUCCESS_COLOR[1], padx=8
        )
        self.lbl_gold_delta.pack(side="left", padx=10)

        # Entrada manual
        edit_row = ctk.CTkFrame(pad_box, fg_color="transparent")
        edit_row.pack(fill="x", pady=(0, 12))

        self.entry_gold = ctk.CTkEntry(
            edit_row, width=140, height=34, font=get_mono_font(13),
            fg_color=BG_SUB, border_color=BORDER_SUBTLE, text_color=TEXT_MAIN
        )
        self.entry_gold.pack(side="left", padx=(0, 8))

        btn_apply = ctk.CTkButton(
            edit_row, text="Aplicar", width=80, height=34,
            font=get_ui_font(12, "bold"), fg_color=PRIMARY_COLOR,
            hover_color=PRIMARY_HOVER, text_color=PRIMARY_TEXT,
            corner_radius=6, command=self._handle_apply_gold
        )
        btn_apply.pack(side="left")

        # Botões rápidos
        quick_row = ctk.CTkFrame(pad_box, fg_color="transparent")
        quick_row.pack(fill="x")

        ctk.CTkButton(
            quick_row, text="+10 mil", width=70, height=30,
            font=get_ui_font(11), fg_color=BG_SUB, hover_color=BG_ACTIVE,
            text_color=TEXT_MAIN, corner_radius=6,
            command=lambda: self.on_add_gold(10000)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            quick_row, text="+100 mil", width=75, height=30,
            font=get_ui_font(11), fg_color=BG_SUB, hover_color=BG_ACTIVE,
            text_color=TEXT_MAIN, corner_radius=6,
            command=lambda: self.on_add_gold(100000)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            quick_row, text="+1 milhão", width=80, height=30,
            font=get_ui_font(11), fg_color=BG_SUB, hover_color=BG_ACTIVE,
            text_color=TEXT_MAIN, corner_radius=6,
            command=lambda: self.on_add_gold(1000000)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            quick_row, text="Máximo", width=70, height=30,
            font=get_ui_font(11), fg_color=BG_SUB, hover_color=BG_ACTIVE,
            text_color=TEXT_MAIN, corner_radius=6,
            command=lambda: self.on_set_gold(99999999)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            quick_row, text="Zerar", width=60, height=30,
            font=get_ui_font(11, "bold"), fg_color=DANGER_COLOR,
            hover_color=DANGER_HOVER, text_color="#FFFFFF", corner_radius=6,
            command=lambda: self.on_set_gold(0)
        ).pack(side="left", padx=4)

    def _build_campaign_card(self):
        pad_box = ctk.CTkFrame(self.card_campaign, fg_color="transparent")
        pad_box.pack(fill="both", expand=True, padx=20, pady=16)

        header = ctk.CTkFrame(pad_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        camp_icon = get_icon("file", size=(16, 16))
        lbl_icon = ctk.CTkLabel(header, text="" if camp_icon else "🚩", image=camp_icon)
        lbl_icon.pack(side="left", padx=(0, 6))

        lbl_title = ctk.CTkLabel(
            header, text="Campanha", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_title.pack(side="left")

        # Grid 2x2 com métricas da campanha
        grid = ctk.CTkFrame(pad_box, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1), weight=1)

        # Tempo de jogo
        self.lbl_time_val = self._create_stat_cell(grid, 0, 0, "clock", "Tempo de jogo", "0h 00m 00s")
        # Passos dados
        self.lbl_steps_val = self._create_stat_cell(grid, 0, 1, "steps", "Passos dados", "0")
        # Heróis no grupo
        self.lbl_party_val = self._create_stat_cell(grid, 1, 0, "users", "Heróis no grupo", "0 de 0")
        # Salvo em
        self.lbl_saved_val = self._create_stat_cell(grid, 1, 1, "save", "Salvo em", "—")

    def _create_stat_cell(self, parent, row, col, icon_name, label, initial_val) -> ctk.CTkLabel:
        cell = ctk.CTkFrame(parent, fg_color=BG_SUB, corner_radius=6)
        cell.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

        top_l = ctk.CTkFrame(cell, fg_color="transparent")
        top_l.pack(fill="x", padx=8, pady=(6, 2))

        ico = get_icon(icon_name, size=(12, 12))
        if ico:
            lbl_ico = ctk.CTkLabel(top_l, text="", image=ico)
            lbl_ico.pack(side="left", padx=(0, 4))

        lbl_l = ctk.CTkLabel(top_l, text=label, font=get_ui_font(11), text_color=TEXT_MUTED)
        lbl_l.pack(side="left")

        lbl_v = ctk.CTkLabel(cell, text=initial_val, font=get_mono_font(13, "bold"), text_color=TEXT_MAIN)
        lbl_v.pack(anchor="w", padx=10, pady=(0, 6))
        return lbl_v

    def _build_cheats_card(self):
        pad_box = ctk.CTkFrame(self.card_cheats, fg_color="transparent")
        pad_box.pack(fill="x", padx=20, pady=16)

        header = ctk.CTkFrame(pad_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        lbl_title = ctk.CTkLabel(
            header, text="Ações rápidas", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_title.pack(side="left")

        lbl_sub = ctk.CTkLabel(
            header, text="Cada ação gera um ponto de desfazer · Ctrl Z",
            font=get_ui_font(11), text_color=TEXT_MUTED
        )
        lbl_sub.pack(side="left", padx=12)

        # Grid 3x2 com os cheats em formato de card informativo
        grid = ctk.CTkFrame(pad_box, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1, 2), weight=1)

        cheats = [
            ("heart", "#F87171", "Curar o grupo", "HP e MP no máximo para todos", self.on_quick_heal_all, 0, 0),
            ("level-up", "#FBBF24", "Subir de nível", "+5 níveis para todos os heróis", self.on_quick_level_up, 0, 1),
            ("zap", "#60A5FA", "Atributos no máximo", "ATK, DEF, MAT, MDF, AGI, LUK em 999", self.on_quick_max_stats, 0, 2),
            ("gift", "#34D399", "Todos os itens", "Adiciona todos os itens do banco × 99", self.on_unlock_items, 1, 0),
            ("sword", "#FBBF24", "Todas as armas", "Adiciona todas as armas do banco × 1", self.on_unlock_weapons, 1, 1),
            ("shield", "#60A5FA", "Todas as armaduras", "Adiciona todas as armaduras do banco × 1", self.on_unlock_armors, 1, 2),
        ]

        for icon_n, tint, title, desc, cmd, r, c in cheats:
            card = ctk.CTkFrame(
                grid, fg_color=BG_SUB, corner_radius=6,
                border_width=1, border_color=BORDER_SUBTLE
            )
            card.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

            ico = get_icon(icon_n, size=(14, 14), tint=tint)
            btn = ctk.CTkButton(
                card, text=f"  {title}", image=ico, compound="left",
                font=get_ui_font(12, "bold"), anchor="w", fg_color="transparent",
                hover_color=BG_ACTIVE, text_color=TEXT_MAIN, height=28, command=cmd
            )
            btn.pack(fill="x", padx=6, pady=(6, 2))

            lbl_d = ctk.CTkLabel(
                card, text=desc, font=get_ui_font(10),
                text_color=TEXT_MUTED, anchor="w"
            )
            lbl_d.pack(fill="x", padx=12, pady=(0, 6))

    def _build_party_card(self):
        pad_box = ctk.CTkFrame(self.card_party, fg_color="transparent")
        pad_box.pack(fill="x", padx=20, pady=16)

        header = ctk.CTkFrame(pad_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        lbl_title = ctk.CTkLabel(
            header, text="Grupo atual", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_title.pack(side="left")

        chevron_ico = get_icon("chevron-right", size=(12, 12), tint=PRIMARY_COLOR[1])
        btn_more = ctk.CTkButton(
            header, text="Ver todos os personagens ", image=chevron_ico, compound="right",
            font=get_ui_font(11, "bold"), fg_color="transparent", hover_color=BG_SUB,
            text_color=PRIMARY_COLOR, command=self.on_navigate_to_actors
        )
        btn_more.pack(side="right")

        # Container para os cards dos heróis do grupo
        self.heroes_container = ctk.CTkFrame(pad_box, fg_color="transparent")
        self.heroes_container.pack(fill="x")

    def _handle_apply_gold(self):
        val_str = self.entry_gold.get().strip().replace(".", "").replace(",", "")
        try:
            val = int(val_str)
            if val < 0: val = 0
            self.on_apply_gold(val)
        except ValueError:
            pass

    def update_gold(self, gold: int):
        if self._initial_gold is None:
            self._initial_gold = gold

        val_str = f"{gold:,} G".replace(",", ".")
        self.lbl_gold_display.configure(text=val_str)
        self.entry_gold.delete(0, "end")
        self.entry_gold.insert(0, str(gold))

        delta = gold - self._initial_gold
        if delta > 0:
            self.lbl_gold_delta.configure(
                text=f"+{delta:,} desde carregamento".replace(",", "."),
                text_color=SUCCESS_COLOR[1]
            )
        elif delta < 0:
            self.lbl_gold_delta.configure(
                text=f"{delta:,} desde carregamento".replace(",", "."),
                text_color=DANGER_COLOR[1]
            )
        else:
            self.lbl_gold_delta.configure(text="")

    def update_campaign_stats(self, playtime_str: str, steps: int, party_count: int, total_actors: int, saved_date: str):
        self.lbl_time_val.configure(text=playtime_str or "00:00:00")
        self.lbl_steps_val.configure(text=f"{steps:,}".replace(",", "."))
        self.lbl_party_val.configure(text=f"{party_count} de {total_actors}")
        self.lbl_saved_val.configure(text=saved_date or "—")

    def update_party_preview(self, party_actors: List[Dict[str, Any]]):
        for w in self.heroes_container.winfo_children():
            w.destroy()

        if not party_actors:
            lbl_none = ctk.CTkLabel(
                self.heroes_container, text="Nenhum herói no grupo ativo.",
                font=get_ui_font(12), text_color=TEXT_MUTED
            )
            lbl_none.pack(pady=10)
            return

        self.heroes_container.grid_columnconfigure(tuple(range(len(party_actors))), weight=1)

        for col, a in enumerate(party_actors[:4]):
            card = ctk.CTkFrame(
                self.heroes_container, fg_color=BG_SUB, corner_radius=6,
                border_width=1, border_color=BORDER_SUBTLE
            )
            card.grid(row=0, column=col, padx=4, pady=4, sticky="nsew")

            card_pad = ctk.CTkFrame(card, fg_color="transparent")
            card_pad.pack(fill="both", expand=True, padx=12, pady=10)

            # Avatar + Nome
            top_h = ctk.CTkFrame(card_pad, fg_color="transparent")
            top_h.pack(fill="x", pady=(0, 8))

            initials = (a.get("name") or "??")[:2].upper()
            avatar = ctk.CTkLabel(
                top_h, text=initials, width=28, height=28, corner_radius=6,
                fg_color=PRIMARY_COLOR, font=get_ui_font(10, "bold"),
                text_color=PRIMARY_TEXT
            )
            avatar.pack(side="left", padx=(0, 8))

            name_box = ctk.CTkFrame(top_h, fg_color="transparent")
            name_box.pack(side="left", fill="both", expand=True)

            lbl_n = ctk.CTkLabel(
                name_box, text=a.get("name", "Herói"), font=get_ui_font(12, "bold"),
                text_color=TEXT_MAIN, anchor="w"
            )
            lbl_n.pack(anchor="w")

            lvl = a.get("level", 1)
            lbl_lvl = ctk.CTkLabel(
                name_box, text=f"Nível {lvl}", font=get_ui_font(10),
                text_color=TEXT_MUTED, anchor="w"
            )
            lbl_lvl.pack(anchor="w")

            # HP & MP StatBars
            hp = a.get("hp", 0)
            max_hp = a.get("max_hp", hp) or hp or 1
            mp = a.get("mp", 0)
            max_mp = a.get("max_mp", mp) or mp or 1

            bar_hp = StatBar(card_pad, label="HP", current=hp, maximum=max_hp, fill_color=SUCCESS_COLOR, height=5)
            bar_hp.pack(fill="x", pady=2)

            bar_mp = StatBar(card_pad, label="MP", current=mp, maximum=max_mp, fill_color=PRIMARY_COLOR, height=5)
            bar_mp.pack(fill="x", pady=2)
