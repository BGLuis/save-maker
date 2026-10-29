#!/usr/bin/env python3
"""
Actors View (Tela 02 do Figma).
Visualização Master-Detail com lista lateral de heróis (no grupo e fora do grupo)
e ficha detalhada com StatBars, recálculo de curvas e grid de atributos.
Fiel ao Figma Save Maker.
"""

from typing import Callable, List, Dict, Any, Optional
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, SUCCESS_HOVER, WARNING_COLOR, DANGER_COLOR,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)
from ui.components.stat_bar import StatBar

class ActorsView(ctk.CTkFrame):
    """Ficha completa e lista de heróis em Master-Detail."""

    def __init__(
        self, master,
        on_select_actor: Callable[[Any], None],
        on_save_stats: Callable[[], None],
        on_max_stats: Callable[[], None],
        on_heal_actor: Callable[[], None],
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_select_actor = on_select_actor
        self.on_save_stats = on_save_stats
        self.on_max_stats = on_max_stats
        self.on_heal_actor = on_heal_actor

        self.actor_buttons: Dict[str, ctk.CTkButton] = {}
        self.actor_entries: Dict[str, ctk.CTkEntry] = {}
        self.original_stats: Dict[str, int] = {}
        self.stat_badges: Dict[str, ctk.CTkLabel] = {}
        self.current_actor_id: Optional[Any] = None

        self._build_ui()

    def _build_ui(self):
        paned = ctk.CTkFrame(self, fg_color="transparent")
        paned.pack(fill="both", expand=True)

        # 1. Coluna Esquerda: Lista de Heróis
        left = ctk.CTkFrame(
            paned, fg_color=BG_CARD, width=280, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        left_header = ctk.CTkFrame(left, fg_color="transparent")
        left_header.pack(fill="x", padx=16, pady=(16, 8))

        lbl_title = ctk.CTkLabel(
            left_header, text="Heróis", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_title.pack(anchor="w")

        self.lbl_actors_count = ctk.CTkLabel(
            left_header, text="Carregando heróis…", font=get_ui_font(11),
            text_color=TEXT_MUTED
        )
        self.lbl_actors_count.pack(anchor="w")

        # Campo de busca de heróis
        self.entry_filter = ctk.CTkEntry(
            left, placeholder_text="Filtrar heróis…", font=get_ui_font(12),
            height=32, fg_color=BG_SUB, border_color=BORDER_SUBTLE
        )
        self.entry_filter.pack(fill="x", padx=14, pady=(4, 10))
        self.entry_filter.bind("<KeyRelease>", self._on_filter_change)

        # Lista scrollável de heróis
        self.actors_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.actors_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # 2. Coluna Direita: Ficha de Detalhes
        self.right = ctk.CTkScrollableFrame(
            paned, fg_color=BG_CARD, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        self.right.pack(side="right", fill="both", expand=True)

        self._build_actor_sheet()

    def _build_actor_sheet(self):
        # Cabeçalho da Ficha
        self.header_box = ctk.CTkFrame(self.right, fg_color="transparent")
        self.header_box.pack(fill="x", padx=20, pady=(18, 12))

        header_top = ctk.CTkFrame(self.header_box, fg_color="transparent")
        header_top.pack(fill="x")

        self.lbl_avatar_large = ctk.CTkLabel(
            header_top, text="??", width=44, height=44, corner_radius=8,
            fg_color=PRIMARY_COLOR, font=get_ui_font(15, "bold"),
            text_color=PRIMARY_TEXT
        )
        self.lbl_avatar_large.pack(side="left", padx=(0, 12))

        info_box = ctk.CTkFrame(header_top, fg_color="transparent")
        info_box.pack(side="left", fill="both", expand=True)

        self.lbl_actor_name = ctk.CTkLabel(
            info_box, text="Selecione um personagem",
            font=get_ui_font(18, "bold"), text_color=TEXT_MAIN, anchor="w"
        )
        self.lbl_actor_name.pack(anchor="w")

        self.lbl_actor_meta = ctk.CTkLabel(
            info_box, text="—", font=get_ui_font(12),
            text_color=TEXT_MUTED, anchor="w"
        )
        self.lbl_actor_meta.pack(anchor="w")

        # Ações Rápidas do herói
        actions_row = ctk.CTkFrame(header_top, fg_color="transparent")
        actions_row.pack(side="right")

        heal_ico = get_icon("heart", size=(14, 14), tint="#F87171")
        self.btn_heal = ctk.CTkButton(
            actions_row, text=" Curar", image=heal_ico, compound="left",
            width=84, height=32, font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6, command=self.on_heal_actor
        )
        self.btn_heal.pack(side="left", padx=4)

        max_ico = get_icon("zap", size=(14, 14), tint="#60A5FA")
        self.btn_max = ctk.CTkButton(
            actions_row, text=" Maximizar", image=max_ico, compound="left",
            width=98, height=32, font=get_ui_font(11, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6, command=self.on_max_stats
        )
        self.btn_max.pack(side="left", padx=4)

        # Divisor
        ctk.CTkFrame(self.right, height=1, fg_color=BORDER_COLOR).pack(fill="x", padx=20, pady=8)

        # Seção 1: Recursos (HP, MP, TP)
        res_sec = ctk.CTkFrame(self.right, fg_color="transparent")
        res_sec.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            res_sec, text="Recursos", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN
        ).pack(anchor="w")

        ctk.CTkLabel(
            res_sec, text="Valores atuais não podem exceder o máximo",
            font=get_ui_font(11), text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(0, 8))

        res_grid = ctk.CTkFrame(res_sec, fg_color="transparent")
        res_grid.pack(fill="x")
        res_grid.grid_columnconfigure((0, 1, 2), weight=1)

        self._create_resource_box(res_grid, 0, "HP", "hp", "max_hp", SUCCESS_COLOR)
        self._create_resource_box(res_grid, 1, "MP", "mp", "max_mp", PRIMARY_COLOR)
        self._create_resource_box(res_grid, 2, "TP", "tp", None, WARNING_COLOR)

        # Divisor
        ctk.CTkFrame(self.right, height=1, fg_color=BORDER_COLOR).pack(fill="x", padx=20, pady=8)

        # Seção 2: Nível & EXP
        lvl_sec = ctk.CTkFrame(self.right, fg_color="transparent")
        lvl_sec.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            lvl_sec, text="Nível e EXP", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN
        ).pack(anchor="w")

        lvl_row = ctk.CTkFrame(lvl_sec, fg_color="transparent")
        lvl_row.pack(fill="x", pady=6)

        ctk.CTkLabel(lvl_row, text="Nível:", font=get_ui_font(12), text_color=TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.actor_entries["level"] = ctk.CTkEntry(
            lvl_row, width=80, height=32, font=get_mono_font(12, "bold"),
            fg_color=BG_SUB, border_color=BORDER_SUBTLE, corner_radius=6
        )
        self.actor_entries["level"].pack(side="left", padx=(0, 20))

        ctk.CTkLabel(lvl_row, text="EXP:", font=get_ui_font(12), text_color=TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.actor_entries["exp"] = ctk.CTkEntry(
            lvl_row, width=120, height=32, font=get_mono_font(12),
            fg_color=BG_SUB, border_color=BORDER_SUBTLE, corner_radius=6
        )
        self.actor_entries["exp"].pack(side="left")

        ctk.CTkLabel(
            lvl_sec, text="Alterar o nível recalcula HP/MP máximos pela curva da classe (Classes.json).",
            font=get_ui_font(10), text_color=TEXT_SUBTLE
        ).pack(anchor="w", pady=(2, 0))

        # Divisor
        ctk.CTkFrame(self.right, height=1, fg_color=BORDER_COLOR).pack(fill="x", padx=20, pady=8)

        # Seção 3: Atributos Primários (Grid)
        attr_sec = ctk.CTkFrame(self.right, fg_color="transparent")
        attr_sec.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            attr_sec, text="Atributos", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN
        ).pack(anchor="w")

        ctk.CTkLabel(
            attr_sec, text="Base + bônus de equipamento",
            font=get_ui_font(11), text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(0, 8))

        attr_grid = ctk.CTkFrame(attr_sec, fg_color="transparent")
        attr_grid.pack(fill="x")
        attr_grid.grid_columnconfigure((0, 1, 2), weight=1)

        attributes = [
            ("atk", "ATK", "Ataque", 0, 0),
            ("def", "DEF", "Defesa", 0, 1),
            ("mat", "MAT", "Atq. Mágico", 0, 2),
            ("mdf", "MDF", "Def. Mágica", 1, 0),
            ("agi", "AGI", "Agilidade", 1, 1),
            ("luk", "LUK", "Sorte", 1, 2),
        ]

        for key, code, full_name, r, c in attributes:
            self._create_attr_card(attr_grid, key, code, full_name, r, c)

        # Botão Salvar Herói
        btn_box = ctk.CTkFrame(self.right, fg_color="transparent")
        btn_box.pack(fill="x", padx=20, pady=16)

        save_ico = get_icon("save", size=(15, 15), tint="#0B0C10")
        self.btn_save_actor = ctk.CTkButton(
            btn_box, text=" Salvar Alterações do Herói", image=save_ico, compound="left",
            font=get_ui_font(13, "bold"), height=36,
            fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER,
            text_color=PRIMARY_TEXT, corner_radius=6,
            command=self.on_save_stats
        )
        self.btn_save_actor.pack(side="left")

    def _create_resource_box(self, parent, col, label, cur_key, max_key, color):
        box = ctk.CTkFrame(parent, fg_color=BG_SUB, corner_radius=6, border_width=1, border_color=BORDER_SUBTLE)
        box.grid(row=0, column=col, padx=4, pady=4, sticky="nsew")

        p = ctk.CTkFrame(box, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=12, pady=10)

        ctk.CTkLabel(p, text=label, font=get_ui_font(12, "bold"), text_color=TEXT_MAIN).pack(anchor="w")

        f_row = ctk.CTkFrame(p, fg_color="transparent")
        f_row.pack(fill="x", pady=4)

        self.actor_entries[cur_key] = ctk.CTkEntry(
            f_row, width=70, height=30, font=get_mono_font(11),
            fg_color=BG_CARD, border_color=BORDER_SUBTLE, corner_radius=4
        )
        self.actor_entries[cur_key].pack(side="left")

        if max_key:
            ctk.CTkLabel(f_row, text="/", font=get_ui_font(12), text_color=TEXT_MUTED).pack(side="left", padx=4)
            self.actor_entries[max_key] = ctk.CTkEntry(
                f_row, width=70, height=30, font=get_mono_font(11),
                fg_color=BG_CARD, border_color=BORDER_SUBTLE, corner_radius=4
            )
            self.actor_entries[max_key].pack(side="left")

    def _create_attr_card(self, parent, key, code, full_name, row, col):
        card = ctk.CTkFrame(parent, fg_color=BG_SUB, corner_radius=6, border_width=1, border_color=BORDER_SUBTLE)
        card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

        p = ctk.CTkFrame(card, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=12, pady=8)

        lbl_row = ctk.CTkFrame(p, fg_color="transparent")
        lbl_row.pack(fill="x")

        ctk.CTkLabel(lbl_row, text=code, font=get_ui_font(12, "bold"), text_color=TEXT_MAIN).pack(side="left")
        ctk.CTkLabel(lbl_row, text=f" · {full_name}", font=get_ui_font(10), text_color=TEXT_MUTED).pack(side="left")

        val_row = ctk.CTkFrame(p, fg_color="transparent")
        val_row.pack(fill="x", pady=(6, 2))

        self.actor_entries[key] = ctk.CTkEntry(
            val_row, width=80, height=30, font=get_mono_font(12, "bold"),
            fg_color=BG_CARD, border_color=BORDER_SUBTLE, corner_radius=4
        )
        self.actor_entries[key].pack(side="left")

        self.stat_badges[key] = ctk.CTkLabel(
            val_row, text="", font=get_mono_font(9), text_color=WARNING_COLOR[1]
        )
        self.stat_badges[key].pack(side="left", padx=6)

    def populate_actor_list(self, actors: List[Dict[str, Any]], party_ids: List[Any], selected_id: Any):
        for w in self.actors_scroll.winfo_children():
            w.destroy()
        self.actor_buttons.clear()

        self.lbl_actors_count.configure(
            text=f"{len(party_ids)} no grupo · {len(actors)} no BD"
        )

        party_set = set(str(pid) for pid in party_ids)

        in_party = [a for a in actors if str(a.get("id")) in party_set]
        out_party = [a for a in actors if str(a.get("id")) not in party_set]

        if in_party:
            lbl_g = ctk.CTkLabel(
                self.actors_scroll, text="NO GRUPO", font=get_ui_font(10, "bold"),
                text_color=TEXT_SUBTLE, anchor="w"
            )
            lbl_g.pack(fill="x", padx=6, pady=(6, 2))
            for a in in_party:
                self._create_hero_list_item(a, str(a.get("id")) == str(selected_id))

        if out_party:
            lbl_o = ctk.CTkLabel(
                self.actors_scroll, text="FORA DO GRUPO", font=get_ui_font(10, "bold"),
                text_color=TEXT_SUBTLE, anchor="w"
            )
            lbl_o.pack(fill="x", padx=6, pady=(10, 2))
            for a in out_party:
                self._create_hero_list_item(a, str(a.get("id")) == str(selected_id))

    def _create_hero_list_item(self, actor: Dict[str, Any], is_selected: bool):
        aid_str = str(actor.get("id"))
        initials = (actor.get("name") or "??")[:2].upper()
        lvl = actor.get("level", 1)

        row = ctk.CTkFrame(
            self.actors_scroll, fg_color=BG_ACTIVE if is_selected else "transparent",
            corner_radius=6, height=44
        )
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        avatar = ctk.CTkLabel(
            row, text=initials, width=26, height=26, corner_radius=5,
            fg_color=PRIMARY_COLOR if is_selected else BG_SUB,
            font=get_ui_font(9, "bold"), text_color=PRIMARY_TEXT if is_selected else TEXT_MAIN
        )
        avatar.pack(side="left", padx=(8, 8))

        btn = ctk.CTkButton(
            row, text=f"{actor.get('name', 'Herói')}\nNv {lvl}",
            font=get_ui_font(11), anchor="w", fg_color="transparent",
            hover_color=BG_SUB, text_color=TEXT_MAIN if is_selected else TEXT_MUTED,
            command=lambda: self.on_select_actor(actor.get("id"))
        )
        btn.pack(side="left", fill="both", expand=True)

        self.actor_buttons[aid_str] = btn

    def set_selected_actor_data(self, actor: Dict[str, Any]):
        self.current_actor_id = actor.get("id")
        name = actor.get("name", "Herói")
        self.lbl_actor_name.configure(text=name)
        initials = name[:2].upper()
        self.lbl_avatar_large.configure(text=initials)

        cls_name = actor.get("class_name") or "Classe Padrão"
        self.lbl_actor_meta.configure(text=f"ID #{actor.get('id')} · {cls_name}")

        # Preenche os campos
        for k, ent in self.actor_entries.items():
            ent.delete(0, "end")
            val = actor.get(k, 0)
            ent.insert(0, str(val))
            self.original_stats[k] = val

            # Reseta badges
            if k in self.stat_badges:
                self.stat_badges[k].configure(text="")

    def _on_filter_change(self, event=None):
        q = self.entry_filter.get().strip().lower()
        for aid_str, btn in self.actor_buttons.items():
            btn_parent = btn.master
            if not q or q in btn.cget("text").lower() or q in aid_str:
                btn_parent.pack(fill="x", pady=1)
            else:
                btn_parent.pack_forget()
