#!/usr/bin/env python3
"""
Overview View (Tela 01 do Figma - nó #5:74 / #5:223).
Apresenta o resumo do save: Ouro com botões rápidos e delta, Estatísticas da Campanha em linhas,
Ações Rápidas em Lote com ícones 36x36 e contagens dinâmicas, e Cards do Grupo Atual.
Fiel ao Figma Save Maker.
"""

from typing import Callable, List, Dict, Any, Optional
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, SUCCESS_BG, DANGER_COLOR, DANGER_HOVER, DANGER_BG,
    WARNING_COLOR, WARNING_BG, INFO_COLOR, INFO_BG, HP_COLOR, MP_COLOR,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)
from ui.components.stat_bar import StatBar


class OverviewView(ctk.CTkScrollableFrame):
    """Tela de Visão Geral com cards informativos e cheats rápidos."""

    def __init__(
        self,
        master,
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
        self.cheat_desc_labels: Dict[str, ctk.CTkLabel] = {}

        self._build_ui()

    def _build_ui(self):
        # 1. Linha Superior: Ouro & Campanha (#5:244)
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 16))
        top_row.grid_columnconfigure(0, weight=3)
        top_row.grid_columnconfigure(1, weight=2)

        # Card de Ouro (lado esquerdo - #5:245)
        self.card_gold = ctk.CTkFrame(
            top_row, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        self.card_gold.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_gold_card()

        # Card de Campanha (lado direito - #5:318)
        self.card_campaign = ctk.CTkFrame(
            top_row, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        self.card_campaign.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._build_campaign_card()

        # 2. Card de Ações Rápidas (#5:341)
        self.card_cheats = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        self.card_cheats.pack(fill="x", pady=(0, 16))
        self._build_cheats_card()

        # 3. Card do Grupo Atual (#5:499)
        self.card_party = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        self.card_party.pack(fill="x", pady=(0, 16))
        self._build_party_card()

    def _build_gold_card(self):
        pad_box = ctk.CTkFrame(self.card_gold, fg_color="transparent")
        pad_box.pack(fill="both", expand=True, padx=20, pady=18)

        # Cabeçalho com tile 32x32 dourado (#5:246)
        header = ctk.CTkFrame(pad_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))

        icon_tile = ctk.CTkFrame(
            header, width=32, height=32, corner_radius=8,
            fg_color=WARNING_BG, border_width=1, border_color=PRIMARY_COLOR
        )
        icon_tile.pack(side="left", padx=(0, 10))
        icon_tile.pack_propagate(False)

        coins_icon = get_icon("coins", size=(16, 16), tint=PRIMARY_COLOR[1])
        lbl_icon = ctk.CTkLabel(icon_tile, text="" if coins_icon else "🪙", image=coins_icon)
        lbl_icon.pack(expand=True)

        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.pack(side="left", fill="x", expand=True)

        lbl_title = ctk.CTkLabel(
            title_col, text="Ouro do grupo", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            title_col, text="Moeda compartilhada entre todos os heróis",
            font=get_ui_font(12), text_color=TEXT_MUTED, anchor="w"
        )
        lbl_sub.pack(anchor="w")

        # Valor em destaque Mono Display (#5:253)
        val_row = ctk.CTkFrame(pad_box, fg_color="transparent")
        val_row.pack(fill="x", pady=(0, 14))

        self.lbl_gold_display = ctk.CTkLabel(
            val_row, text="0", font=get_mono_font(30, "bold"),
            text_color=TEXT_MAIN
        )
        self.lbl_gold_display.pack(side="left")

        self.lbl_gold_unit = ctk.CTkLabel(
            val_row, text="G", font=get_mono_font(16, "bold"),
            text_color=PRIMARY_COLOR
        )
        self.lbl_gold_unit.pack(side="left", padx=(8, 10), pady=(8, 0))

        self.gold_delta_badge = ctk.CTkFrame(
            val_row, fg_color="transparent", corner_radius=999
        )
        self.gold_delta_badge.pack(side="left", pady=(6, 0))

        self.lbl_gold_delta = ctk.CTkLabel(
            self.gold_delta_badge, text="", font=get_ui_font(11, "bold"),
            text_color=SUCCESS_COLOR, padx=8, pady=2
        )
        self.lbl_gold_delta.pack()

        # Entrada manual com ícone coins e botão Aplicar Secondary (#5:259)
        edit_row = ctk.CTkFrame(pad_box, fg_color="transparent")
        edit_row.pack(fill="x", pady=(0, 12))

        input_wrap = ctk.CTkFrame(
            edit_row, height=34, fg_color=BG_SUB, corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE
        )
        input_wrap.pack(side="left", fill="x", expand=True, padx=(0, 8))

        in_coins = get_icon("coins", size=(14, 14))
        lbl_in_ico = ctk.CTkLabel(input_wrap, text="" if in_coins else "🪙", image=in_coins)
        lbl_in_ico.pack(side="left", padx=(10, 4))

        self.entry_gold = ctk.CTkEntry(
            input_wrap, height=30, font=get_mono_font(13),
            fg_color="transparent", border_width=0, text_color=TEXT_MAIN
        )
        self.entry_gold.pack(side="left", fill="both", expand=True)
        self.entry_gold.bind("<Return>", lambda e: self._handle_apply_gold())

        lbl_in_unit = ctk.CTkLabel(
            input_wrap, text="G", font=get_mono_font(11),
            text_color=TEXT_SUBTLE
        )
        lbl_in_unit.pack(side="right", padx=(4, 10))

        btn_apply = ctk.CTkButton(
            edit_row, text="Aplicar", width=84, height=34,
            font=get_ui_font(13, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6, command=self._handle_apply_gold
        )
        btn_apply.pack(side="right")

        # Botões rápidos com ícones (#5:269)
        quick_row = ctk.CTkFrame(pad_box, fg_color="transparent")
        quick_row.pack(fill="x")

        plus_ico = get_icon("plus", size=(12, 12))
        zap_ico = get_icon("zap", size=(12, 12))
        x_ico = get_icon("x", size=(12, 12), tint=DANGER_COLOR[1])

        for label, amount in (("+10 mil", 10000), ("+100 mil", 100000), ("+1 milhão", 1000000)):
            ctk.CTkButton(
                quick_row, text=f" {label}", image=plus_ico, compound="left",
                width=84, height=28, font=get_ui_font(12, "bold"),
                fg_color=BG_SUB, hover_color=BG_ACTIVE,
                border_width=1, border_color=BORDER_COLOR,
                text_color=TEXT_MAIN, corner_radius=6,
                command=lambda a=amount: self.on_add_gold(a)
            ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            quick_row, text=" Máximo · 99.999.999", image=zap_ico, compound="left",
            width=150, height=28, font=get_ui_font(12, "bold"),
            fg_color=BG_SUB, hover_color=BG_ACTIVE,
            border_width=1, border_color=BORDER_COLOR,
            text_color=TEXT_MAIN, corner_radius=6,
            command=lambda: self.on_set_gold(99999999)
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            quick_row, text=" Zerar", image=x_ico, compound="left",
            width=68, height=28, font=get_ui_font(12, "bold"),
            fg_color=DANGER_BG, hover_color=DANGER_HOVER,
            border_width=1, border_color=DANGER_COLOR,
            text_color=DANGER_COLOR, corner_radius=6,
            command=lambda: self.on_set_gold(0)
        ).pack(side="left")

    def _build_campaign_card(self):
        """Card Campanha como lista vertical de 4 linhas com divisores (#5:318)."""
        pad_box = ctk.CTkFrame(self.card_campaign, fg_color="transparent")
        pad_box.pack(fill="both", expand=True, padx=20, pady=18)

        lbl_title = ctk.CTkLabel(
            pad_box, text="Campanha", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        )
        lbl_title.pack(fill="x", pady=(0, 10))

        rows_box = ctk.CTkFrame(pad_box, fg_color="transparent")
        rows_box.pack(fill="both", expand=True)

        self.lbl_time_val = self._create_campaign_row(rows_box, "clock", "Tempo de jogo", "00:00:00", has_divider=True)
        self.lbl_steps_val = self._create_campaign_row(rows_box, "steps", "Passos dados", "0", has_divider=True)
        self.lbl_party_val = self._create_campaign_row(rows_box, "users", "Heróis no grupo", "0 de 0", has_divider=True)
        self.lbl_saved_val = self._create_campaign_row(rows_box, "save", "Salvo em", "—", has_divider=False)

    def _create_campaign_row(self, parent, icon_name: str, label: str, initial_val: str, has_divider: bool = True) -> ctk.CTkLabel:
        row = ctk.CTkFrame(parent, fg_color="transparent", height=36)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        ico = get_icon(icon_name, size=(14, 14))
        if ico:
            lbl_ico = ctk.CTkLabel(row, text="", image=ico)
            lbl_ico.pack(side="left", padx=(0, 8))

        lbl_l = ctk.CTkLabel(row, text=label, font=get_ui_font(12), text_color=TEXT_MUTED)
        lbl_l.pack(side="left")

        lbl_v = ctk.CTkLabel(row, text=initial_val, font=get_mono_font(13, "bold"), text_color=TEXT_MAIN)
        lbl_v.pack(side="right")

        if has_divider:
            ctk.CTkFrame(parent, height=1, fg_color=BORDER_COLOR).pack(fill="x")

        return lbl_v

    def _build_cheats_card(self):
        """Card Ações Rápidas com tiles 36x36 coloridos e chevron-right (#5:341)."""
        pad_box = ctk.CTkFrame(self.card_cheats, fg_color="transparent")
        pad_box.pack(fill="x", padx=20, pady=18)

        header = ctk.CTkFrame(pad_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        lbl_title = ctk.CTkLabel(
            header, text="Ações rápidas", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_title.pack(side="left")

        lbl_sub = ctk.CTkLabel(
            header, text="Cada ação gera um ponto de desfazer · Ctrl Z",
            font=get_ui_font(11), text_color=TEXT_SUBTLE
        )
        lbl_sub.pack(side="right")

        grid = ctk.CTkFrame(pad_box, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1, 2), weight=1)

        cheats = [
            ("heal", "heart", SUCCESS_COLOR[1], SUCCESS_BG, "Curar o grupo", "HP e MP no máximo para os heróis", self.on_quick_heal_all, 0, 0),
            ("level", "level-up", PRIMARY_COLOR[1], WARNING_BG, "Subir 5 níveis", "+5 níveis para todos os heróis do grupo", self.on_quick_level_up, 0, 1),
            ("stats", "zap", PRIMARY_COLOR[1], WARNING_BG, "Atributos no máximo", "ATK, DEF, MAT, MDF, AGI, LUK → 999", self.on_quick_max_stats, 0, 2),
            ("items", "gift", INFO_COLOR[1], INFO_BG, "Todos os itens", "Adiciona os itens do banco × 99", self.on_unlock_items, 1, 0),
            ("weapons", "sword", TEXT_MAIN[1], BG_ACTIVE, "Todas as armas", "Adiciona as armas do banco × 1", self.on_unlock_weapons, 1, 1),
            ("armors", "shield", TEXT_MAIN[1], BG_ACTIVE, "Todas as armaduras", "Adiciona as armaduras do banco × 1", self.on_unlock_armors, 1, 2),
        ]

        chev_ico = get_icon("chevron-right", size=(16, 16))

        for key, icon_n, tint, tile_bg, title, desc, cmd, r, c in cheats:
            card = ctk.CTkFrame(
                grid, fg_color=BG_SUB, corner_radius=8,
                border_width=1, border_color=BORDER_COLOR, cursor="hand2"
            )
            card.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=14, pady=12)

            # Icon tile 36x36 (#5:348)
            tile = ctk.CTkFrame(inner, width=36, height=36, corner_radius=8, fg_color=tile_bg)
            tile.pack(side="left", padx=(0, 12))
            tile.pack_propagate(False)

            ico = get_icon(icon_n, size=(18, 18), tint=tint)
            lbl_ico = ctk.CTkLabel(tile, text="" if ico else "⚡", image=ico)
            lbl_ico.pack(expand=True)

            txt_col = ctk.CTkFrame(inner, fg_color="transparent")
            txt_col.pack(side="left", fill="both", expand=True)

            lbl_t = ctk.CTkLabel(
                txt_col, text=title, font=get_ui_font(13, "bold"),
                text_color=TEXT_MAIN, anchor="w"
            )
            lbl_t.pack(anchor="w")

            lbl_d = ctk.CTkLabel(
                txt_col, text=desc, font=get_ui_font(11),
                text_color=TEXT_MUTED, anchor="w"
            )
            lbl_d.pack(anchor="w")
            self.cheat_desc_labels[key] = lbl_d

            lbl_ch = ctk.CTkLabel(inner, text="" if chev_ico else "›", image=chev_ico)
            lbl_ch.pack(side="right", padx=(6, 0))

            for w in (card, inner, tile, lbl_ico, txt_col, lbl_t, lbl_d, lbl_ch):
                w.bind("<Button-1>", lambda e, fn=cmd: fn() if fn else None)

    def update_cheat_counts(self, party_count: int, items_count: int, weapons_count: int, armors_count: int):
        """Atualiza dinamicamente os subtítulos dos cards de ações rápidas conforme o banco (#5:359)."""
        if "heal" in self.cheat_desc_labels and party_count > 0:
            self.cheat_desc_labels["heal"].configure(text=f"HP e MP no máximo para os {party_count} heróis")
        if "items" in self.cheat_desc_labels and items_count > 0:
            self.cheat_desc_labels["items"].configure(text=f"Adiciona os {items_count} itens do banco × 99")
        if "weapons" in self.cheat_desc_labels and weapons_count > 0:
            self.cheat_desc_labels["weapons"].configure(text=f"Adiciona as {weapons_count} armas do banco × 1")
        if "armors" in self.cheat_desc_labels and armors_count > 0:
            self.cheat_desc_labels["armors"].configure(text=f"Adiciona as {armors_count} armaduras do banco × 1")

    def _build_party_card(self):
        pad_box = ctk.CTkFrame(self.card_party, fg_color="transparent")
        pad_box.pack(fill="x", padx=20, pady=18)

        header = ctk.CTkFrame(pad_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        lbl_title = ctk.CTkLabel(
            header, text="Grupo atual", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_title.pack(side="left")

        chevron_ico = get_icon("chevron-right", size=(12, 12), tint=PRIMARY_COLOR[1])
        btn_more = ctk.CTkButton(
            header, text="Editar personagens ", image=chevron_ico, compound="right",
            font=get_ui_font(12, "bold"), fg_color="transparent", hover_color=BG_SUB,
            text_color=PRIMARY_COLOR, height=26, command=self.on_navigate_to_actors
        )
        btn_more.pack(side="right")

        # Container para os cards dos heróis do grupo
        self.heroes_container = ctk.CTkFrame(pad_box, fg_color="transparent")
        self.heroes_container.pack(fill="x")

    def _handle_apply_gold(self):
        val_str = self.entry_gold.get().strip().replace(".", "").replace(",", "")
        try:
            val = int(val_str)
            if val < 0:
                val = 0
            self.on_apply_gold(val)
        except ValueError:
            pass

    def update_gold(self, gold: int):
        if self._initial_gold is None:
            self._initial_gold = gold

        val_str = f"{gold:,}".replace(",", ".")
        self.lbl_gold_display.configure(text=val_str)
        self.entry_gold.delete(0, "end")
        self.entry_gold.insert(0, val_str)

        delta = gold - self._initial_gold
        if delta > 0:
            self.gold_delta_badge.configure(fg_color=SUCCESS_BG)
            self.lbl_gold_delta.configure(
                text=f"+{delta:,} desde o carregamento".replace(",", "."),
                text_color=SUCCESS_COLOR
            )
        elif delta < 0:
            self.gold_delta_badge.configure(fg_color=DANGER_BG)
            self.lbl_gold_delta.configure(
                text=f"{delta:,} desde o carregamento".replace(",", "."),
                text_color=DANGER_COLOR
            )
        else:
            self.gold_delta_badge.configure(fg_color="transparent")
            self.lbl_gold_delta.configure(text="")

    def update_campaign_stats(self, playtime_str: str, steps: int, party_count: int, total_actors: int, saved_date: str):
        # Formata tempo no padrão "14h 32m 18s" quando vier como "14:32:18"
        pt = playtime_str or "00:00:00"
        if ":" in pt and len(pt.split(":")) == 3:
            parts = pt.split(":")
            pt = f"{int(parts[0])}h {parts[1]}m {parts[2]}s"
        self.lbl_time_val.configure(text=pt)
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

        count = min(4, len(party_actors))
        self.heroes_container.grid_columnconfigure(tuple(range(count)), weight=1)

        for col, a in enumerate(party_actors[:4]):
            card = ctk.CTkFrame(
                self.heroes_container, fg_color=BG_SUB, corner_radius=8,
                border_width=1, border_color=BORDER_COLOR
            )
            card.grid(row=0, column=col, padx=5, pady=4, sticky="nsew")

            card_pad = ctk.CTkFrame(card, fg_color="transparent")
            card_pad.pack(fill="both", expand=True, padx=14, pady=12)

            # Avatar circular 32x32 + Nome + Classe (#5:506)
            top_h = ctk.CTkFrame(card_pad, fg_color="transparent")
            top_h.pack(fill="x", pady=(0, 10))

            name_raw = a.get("name") or "Herói"
            parts = name_raw.split()
            initials = (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else name_raw[:2].upper()

            avatar = ctk.CTkFrame(
                top_h, width=32, height=32, corner_radius=16,
                fg_color=BG_ACTIVE, border_width=1, border_color=BORDER_SUBTLE
            )
            avatar.pack(side="left", padx=(0, 10))
            avatar.pack_propagate(False)

            lbl_av = ctk.CTkLabel(
                avatar, text=initials, font=get_ui_font(11, "bold"),
                text_color=PRIMARY_COLOR
            )
            lbl_av.pack(expand=True)

            name_box = ctk.CTkFrame(top_h, fg_color="transparent")
            name_box.pack(side="left", fill="both", expand=True)

            lbl_n = ctk.CTkLabel(
                name_box, text=name_raw, font=get_ui_font(13, "bold"),
                text_color=TEXT_MAIN, anchor="w"
            )
            lbl_n.pack(anchor="w")

            lvl = a.get("level", 1)
            cls_name = a.get("class_name") or ""
            sub_txt = f"Nível {lvl} · {cls_name}" if cls_name else f"Nível {lvl}"
            lbl_lvl = ctk.CTkLabel(
                name_box, text=sub_txt, font=get_ui_font(11),
                text_color=TEXT_MUTED, anchor="w"
            )
            lbl_lvl.pack(anchor="w")

            # HP (Vermelho Coral #F2706B) & MP (Azul #6E8BFF) StatBars (#5:512, #5:519)
            hp = a.get("hp", 0)
            max_hp = a.get("max_hp", hp) or hp or 1
            mp = a.get("mp", 0)
            max_mp = a.get("max_mp", mp) or mp or 1

            bar_hp = StatBar(card_pad, label="HP", current=hp, maximum=max_hp, fill_color=HP_COLOR, height=6)
            bar_hp.pack(fill="x", pady=3)

            bar_mp = StatBar(card_pad, label="MP", current=mp, maximum=max_mp, fill_color=MP_COLOR, height=6)
            bar_mp.pack(fill="x", pady=3)
