#!/usr/bin/env python3
"""
Actors View (Tela 02 do Figma - nó #5:896 / #5:2099).
Visualização Master-Detail com lista lateral de heróis (com mini barra de HP e nível),
cabeçalho com 3 badges, Recursos com barras visuais (HP/MP/TP) e linha Nível + Atributos com steppers.
Fiel ao Figma Save Maker.
"""

from typing import Callable, List, Dict, Any, Optional
import customtkinter as ctk

from ui.theme import (
    PRIMARY_COLOR, PRIMARY_HOVER, PRIMARY_TEXT,
    SUCCESS_COLOR, SUCCESS_HOVER, SUCCESS_BG,
    WARNING_COLOR, WARNING_BG, DANGER_COLOR, HP_COLOR, MP_COLOR, TP_COLOR,
    BG_CARD, BG_SUB, BG_ACTIVE, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
    BORDER_COLOR, BORDER_SUBTLE, get_ui_font, get_mono_font, get_icon
)


class ActorsView(ctk.CTkFrame):
    """Ficha completa e lista de heróis em Master-Detail."""

    def __init__(
        self,
        master,
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
        self.hero_lvl_labels: Dict[str, ctk.CTkLabel] = {}
        self.hero_hp_bars: Dict[str, ctk.CTkProgressBar] = {}
        self.actor_entries: Dict[str, ctk.CTkEntry] = {}
        self.resource_bars: Dict[str, ctk.CTkProgressBar] = {}
        self.attr_cards: Dict[str, ctk.CTkFrame] = {}
        self.attr_code_labels: Dict[str, ctk.CTkLabel] = {}
        self._filter_debounce_job = None
        self.original_stats: Dict[str, int] = {}
        self.stat_badges: Dict[str, ctk.CTkLabel] = {}
        self.current_actor_id: Optional[Any] = None
        self._party_ids_set: set = set()

        self._build_ui()

    def _build_ui(self):
        paned = ctk.CTkFrame(self, fg_color="transparent")
        paned.pack(fill="both", expand=True)

        # 1. Coluna Esquerda: Lista de Heróis (width=280, #5:2101)
        left = ctk.CTkFrame(
            paned, fg_color=BG_CARD, width=280, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)

        left_header = ctk.CTkFrame(left, fg_color="transparent")
        left_header.pack(fill="x", padx=14, pady=(14, 8))

        lbl_title = ctk.CTkLabel(
            left_header, text="Heróis", font=get_ui_font(14, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_title.pack(side="left")

        self.lbl_actors_count = ctk.CTkLabel(
            left_header, text="0 no grupo · 0 no BD", font=get_mono_font(11),
            text_color=TEXT_SUBTLE
        )
        self.lbl_actors_count.pack(side="right")

        # Campo de busca de heróis com ícone (#5:2105)
        search_wrap = ctk.CTkFrame(
            left, height=32, fg_color=BG_SUB, corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE
        )
        search_wrap.pack(fill="x", padx=12, pady=(0, 8))

        s_ico = get_icon("search", size=(13, 13))
        lbl_s = ctk.CTkLabel(search_wrap, text="" if s_ico else "🔍", image=s_ico)
        lbl_s.pack(side="left", padx=(8, 4))

        self.entry_filter = ctk.CTkEntry(
            search_wrap, placeholder_text="Filtrar heróis…", font=get_ui_font(12),
            height=26, fg_color="transparent", border_width=0, text_color=TEXT_MAIN
        )
        self.entry_filter.pack(side="left", fill="both", expand=True, pady=2)

        def _on_filter_key(event=None):
            if event and event.keysym == "Escape":
                self.entry_filter.delete(0, "end")
                self._on_filter_change()
                return
            if self._filter_debounce_job:
                self.after_cancel(self._filter_debounce_job)
            self._filter_debounce_job = self.after(150, self._on_filter_change)

        self.entry_filter.bind("<KeyRelease>", _on_filter_key)
        self.entry_filter.bind("<Escape>", lambda e: (self.entry_filter.delete(0, "end"), self._on_filter_change()))
        search_wrap.bind("<Button-1>", lambda e: self.entry_filter.focus_set())
        lbl_s.bind("<Button-1>", lambda e: self.entry_filter.focus_set())

        ctk.CTkFrame(left, height=1, fg_color=BORDER_COLOR).pack(fill="x")

        # Lista scrollável de heróis
        self.actors_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.actors_scroll.pack(fill="both", expand=True, padx=6, pady=(4, 8))

        # 2. Coluna Direita: Ficha de Detalhes (#5:2190)
        self.right = ctk.CTkScrollableFrame(
            paned, fg_color="transparent", corner_radius=0
        )
        self.right.pack(side="right", fill="both", expand=True)

        self._build_actor_sheet()

    def _build_actor_sheet(self):
        # Card 1: Cabeçalho da Ficha (#5:2191)
        self.header_card = ctk.CTkFrame(
            self.right, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        self.header_card.pack(fill="x", pady=(0, 14))

        header_top = ctk.CTkFrame(self.header_card, fg_color="transparent")
        header_top.pack(fill="x", padx=20, pady=18)

        # Avatar Circular 56x56 (#5:2192)
        self.avatar_frame_large = ctk.CTkFrame(
            header_top, width=56, height=56, corner_radius=28,
            fg_color=BG_ACTIVE, border_width=1, border_color=PRIMARY_COLOR
        )
        self.avatar_frame_large.pack(side="left", padx=(0, 16))
        self.avatar_frame_large.pack_propagate(False)

        self.lbl_avatar_large = ctk.CTkLabel(
            self.avatar_frame_large, text="??", font=get_ui_font(18, "bold"),
            text_color=PRIMARY_COLOR
        )
        self.lbl_avatar_large.pack(expand=True)

        info_box = ctk.CTkFrame(header_top, fg_color="transparent")
        info_box.pack(side="left", fill="both", expand=True)

        self.lbl_actor_name = ctk.CTkLabel(
            info_box, text="Selecione um personagem",
            font=get_ui_font(20, "bold"), text_color=TEXT_MAIN, anchor="w"
        )
        self.lbl_actor_name.pack(anchor="w", pady=(0, 4))

        # Linha com 3 badges (#5:2196): ID, Classe e No grupo
        self.badges_row = ctk.CTkFrame(info_box, fg_color="transparent")
        self.badges_row.pack(anchor="w")

        self.lbl_actor_meta = ctk.CTkLabel(
            self.badges_row, text="ID #—", font=get_ui_font(11, "bold"),
            fg_color=BG_ACTIVE, text_color=TEXT_MUTED,
            corner_radius=999, height=20, padx=8
        )
        self.lbl_actor_meta.pack(side="left", padx=(0, 6))

        self.lbl_class_badge = ctk.CTkLabel(
            self.badges_row, text="Classe", font=get_ui_font(11, "bold"),
            fg_color=BG_ACTIVE, text_color=TEXT_MUTED,
            corner_radius=999, height=20, padx=8
        )
        self.lbl_class_badge.pack(side="left", padx=(0, 6))

        self.lbl_party_badge = ctk.CTkLabel(
            self.badges_row, text="● No grupo", font=get_ui_font(11, "bold"),
            fg_color=SUCCESS_BG, text_color=SUCCESS_COLOR,
            corner_radius=999, height=20, padx=8
        )
        self.lbl_party_badge.pack(side="left")

        # Ações Rápidas do herói (#5:2206)
        actions_row = ctk.CTkFrame(header_top, fg_color="transparent")
        actions_row.pack(side="right")

        heal_ico = get_icon("heart", size=(14, 14), tint=HP_COLOR[1])
        self.btn_heal = ctk.CTkButton(
            actions_row, text=" Curar", image=heal_ico, compound="left",
            width=86, height=30, font=get_ui_font(12, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR,
            corner_radius=6, command=self.on_heal_actor
        )
        self.btn_heal.pack(side="left", padx=4)

        max_ico = get_icon("zap", size=(14, 14), tint=PRIMARY_COLOR[1])
        self.btn_max = ctk.CTkButton(
            actions_row, text=" Maximizar atributos", image=max_ico, compound="left",
            width=158, height=30, font=get_ui_font(12, "bold"), fg_color=BG_SUB,
            hover_color=BG_ACTIVE, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_COLOR,
            corner_radius=6, command=self.on_max_stats
        )
        self.btn_max.pack(side="left", padx=4)

        # Card 2: Recursos (HP, MP, TP) com barra de progresso (#5:2220)
        res_card = ctk.CTkFrame(
            self.right, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        res_card.pack(fill="x", pady=(0, 14))

        res_sec = ctk.CTkFrame(res_card, fg_color="transparent")
        res_sec.pack(fill="x", padx=20, pady=16)

        res_hdr = ctk.CTkFrame(res_sec, fg_color="transparent")
        res_hdr.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            res_hdr, text="Recursos", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN
        ).pack(side="left")

        ctk.CTkLabel(
            res_hdr, text="Valores atuais não podem exceder o máximo",
            font=get_ui_font(11), text_color=TEXT_SUBTLE
        ).pack(side="right")

        res_grid = ctk.CTkFrame(res_sec, fg_color="transparent")
        res_grid.pack(fill="x")
        res_grid.grid_columnconfigure((0, 1, 2), weight=1)

        self._create_resource_box(res_grid, 0, "HP", "hp", "max_hp", HP_COLOR)
        self._create_resource_box(res_grid, 1, "MP", "mp", "max_mp", MP_COLOR)
        self._create_resource_box(res_grid, 2, "TP", "tp", None, TP_COLOR)

        # Linha 3: Nível (esquerda, width=240) + Atributos (direita, expand) (#5:2261)
        row_lvl_attr = ctk.CTkFrame(self.right, fg_color="transparent")
        row_lvl_attr.pack(fill="x", pady=(0, 14))
        row_lvl_attr.grid_columnconfigure(0, weight=0, minsize=250)
        row_lvl_attr.grid_columnconfigure(1, weight=1)

        # Card Nível (#5:2262)
        lvl_card = ctk.CTkFrame(
            row_lvl_attr, fg_color=BG_CARD, width=250, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        lvl_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        lvl_sec = ctk.CTkFrame(lvl_card, fg_color="transparent")
        lvl_sec.pack(fill="both", expand=True, padx=18, pady=16)

        ctk.CTkLabel(
            lvl_sec, text="Nível", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN, anchor="w"
        ).pack(fill="x", pady=(0, 10))

        # Stepper de Nível (#5:2266)
        lvl_stepper = ctk.CTkFrame(
            lvl_sec, fg_color=BG_SUB, corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE, height=40
        )
        lvl_stepper.pack(fill="x", pady=(0, 14))

        btn_lvl_minus = ctk.CTkButton(
            lvl_stepper, text="−", width=36, height=34,
            font=get_mono_font(15, "bold"), fg_color="transparent",
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            command=lambda: self._step_entry("level", -1, min_val=1, max_val=999)
        )
        btn_lvl_minus.pack(side="left", padx=2, pady=2)

        self.actor_entries["level"] = ctk.CTkEntry(
            lvl_stepper, height=32, font=get_mono_font(18, "bold"),
            fg_color="transparent", border_width=0, justify="center",
            text_color=TEXT_MAIN
        )
        self.actor_entries["level"].pack(side="left", fill="both", expand=True)
        self.actor_entries["level"].bind("<Return>", lambda e: self.on_save_stats())
        self.actor_entries["level"].bind("<FocusOut>", lambda e: self.on_save_stats())

        btn_lvl_plus = ctk.CTkButton(
            lvl_stepper, text="+", width=36, height=34,
            font=get_mono_font(15, "bold"), fg_color="transparent",
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            command=lambda: self._step_entry("level", 1, min_val=1, max_val=999)
        )
        btn_lvl_plus.pack(side="right", padx=2, pady=2)

        # Barra de EXP (#5:2275)
        exp_box = ctk.CTkFrame(lvl_sec, fg_color="transparent")
        exp_box.pack(fill="x", pady=(0, 12))

        exp_top = ctk.CTkFrame(exp_box, fg_color="transparent")
        exp_top.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            exp_top, text="EXP", font=get_ui_font(11, "bold"),
            text_color=TEXT_MUTED
        ).pack(side="left")

        self.lbl_exp_next = ctk.CTkLabel(
            exp_top, text="/ —", font=get_mono_font(11),
            text_color=TEXT_SUBTLE
        )
        self.lbl_exp_next.pack(side="right")

        self.actor_entries["exp"] = ctk.CTkEntry(
            exp_top, width=82, height=24, font=get_mono_font(11),
            fg_color=BG_SUB, border_color=BORDER_SUBTLE, corner_radius=4,
            justify="right"
        )
        self.actor_entries["exp"].pack(side="right", padx=(4, 4))
        self.actor_entries["exp"].bind("<Return>", lambda e: self.on_save_stats())
        self.actor_entries["exp"].bind("<FocusOut>", lambda e: self.on_save_stats())

        self.exp_bar = ctk.CTkProgressBar(
            exp_box, height=6, corner_radius=3,
            fg_color=BG_ACTIVE, progress_color=PRIMARY_COLOR
        )
        self.exp_bar.pack(fill="x")
        self.exp_bar.set(0.65)

        ctk.CTkLabel(
            lvl_sec,
            text="Alterar o nível recalcula HP/MP máximos pela curva da classe (Classes.json).",
            font=get_ui_font(11), text_color=TEXT_SUBTLE,
            justify="left", anchor="w", wraplength=210
        ).pack(fill="x", pady=(4, 0))

        # Card Atributos (#5:2283)
        attr_card = ctk.CTkFrame(
            row_lvl_attr, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR
        )
        attr_card.grid(row=0, column=1, sticky="nsew")

        attr_sec = ctk.CTkFrame(attr_card, fg_color="transparent")
        attr_sec.pack(fill="both", expand=True, padx=20, pady=16)

        attr_hdr = ctk.CTkFrame(attr_sec, fg_color="transparent")
        attr_hdr.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            attr_hdr, text="Atributos", font=get_ui_font(15, "bold"),
            text_color=TEXT_MAIN
        ).pack(side="left")

        ctk.CTkLabel(
            attr_hdr, text="Base + bônus de equipamento",
            font=get_ui_font(11), text_color=TEXT_SUBTLE
        ).pack(side="right")

        attr_grid = ctk.CTkFrame(attr_sec, fg_color="transparent")
        attr_grid.pack(fill="both", expand=True)
        attr_grid.grid_columnconfigure((0, 1, 2), weight=1)

        attributes = [
            ("atk", "ATK", "Ataque", 0, 0),
            ("def", "DEF", "Defesa", 0, 1),
            ("mat", "MAT", "Ataque Mágico", 0, 2),
            ("mdf", "MDF", "Defesa Mágica", 1, 0),
            ("agi", "AGI", "Agilidade", 1, 1),
            ("luk", "LUK", "Sorte", 1, 2),
        ]

        for key, code, full_name, r, c in attributes:
            self._create_attr_card(attr_grid, key, code, full_name, r, c)

        # Botão Aplicar Alterações do Herói
        btn_box = ctk.CTkFrame(self.right, fg_color="transparent")
        btn_box.pack(fill="x", pady=(0, 8))

        save_ico = get_icon("check", size=(15, 15))
        self.btn_save_actor = ctk.CTkButton(
            btn_box, text=" Aplicar alterações nos atributos", image=save_ico, compound="left",
            font=get_ui_font(12, "bold"), height=34,
            fg_color=BG_CARD, hover_color=BG_ACTIVE,
            text_color=TEXT_MAIN, border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=6, command=self.on_save_stats
        )
        self.btn_save_actor.pack(side="right")

    def _create_resource_box(self, parent, col, label, cur_key, max_key, color):
        """Caixa de recurso (HP / MP / TP) com dot colorido, inputs e barra de progresso (#5:2225)."""
        box = ctk.CTkFrame(parent, fg_color=BG_SUB, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        box.grid(row=0, column=col, padx=5, pady=4, sticky="nsew")

        p = ctk.CTkFrame(box, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=14, pady=12)

        top = ctk.CTkFrame(p, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))

        lbl_row = ctk.CTkFrame(top, fg_color="transparent")
        lbl_row.pack(side="left")

        dot = ctk.CTkLabel(lbl_row, text="●", font=get_ui_font(12), text_color=color)
        dot.pack(side="left", padx=(0, 6))

        ctk.CTkLabel(lbl_row, text=label, font=get_ui_font(13, "bold"), text_color=TEXT_MAIN).pack(side="left")

        f_row = ctk.CTkFrame(top, fg_color="transparent")
        f_row.pack(side="right")

        self.actor_entries[cur_key] = ctk.CTkEntry(
            f_row, width=64, height=28, font=get_mono_font(12, "bold"),
            fg_color=BG_CARD, border_color=BORDER_SUBTLE, corner_radius=5,
            justify="right"
        )
        self.actor_entries[cur_key].pack(side="left")
        self.actor_entries[cur_key].bind("<KeyRelease>", lambda e, ck=cur_key, mk=max_key: self._update_resource_bar(ck, mk))
        self.actor_entries[cur_key].bind("<Return>", lambda e: self.on_save_stats())
        self.actor_entries[cur_key].bind("<FocusOut>", lambda e: self.on_save_stats())

        ctk.CTkLabel(f_row, text="/", font=get_mono_font(12), text_color=TEXT_SUBTLE).pack(side="left", padx=4)

        if max_key:
            self.actor_entries[max_key] = ctk.CTkEntry(
                f_row, width=64, height=28, font=get_mono_font(12),
                fg_color=BG_CARD, border_color=BORDER_SUBTLE, corner_radius=5,
                justify="right", text_color=TEXT_MUTED
            )
            self.actor_entries[max_key].pack(side="left")
            self.actor_entries[max_key].bind("<KeyRelease>", lambda e, ck=cur_key, mk=max_key: self._update_resource_bar(ck, mk))
            self.actor_entries[max_key].bind("<Return>", lambda e: self.on_save_stats())
            self.actor_entries[max_key].bind("<FocusOut>", lambda e: self.on_save_stats())
        else:
            lbl_tp_max = ctk.CTkFrame(
                f_row, width=54, height=28, corner_radius=5,
                fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR
            )
            lbl_tp_max.pack(side="left")
            lbl_tp_max.pack_propagate(False)
            ctk.CTkLabel(
                lbl_tp_max, text="100", font=get_mono_font(12),
                text_color=TEXT_SUBTLE
            ).pack(expand=True, anchor="e", padx=8)

        # Barra de progresso do recurso (#5:2235)
        bar = ctk.CTkProgressBar(
            p, height=6, corner_radius=3,
            fg_color=BG_ACTIVE, progress_color=color
        )
        bar.pack(fill="x", pady=(4, 0))
        bar.set(1.0)
        self.resource_bars[cur_key] = bar

    def _update_resource_bar(self, cur_key: str, max_key: Optional[str]):
        bar = self.resource_bars.get(cur_key)
        if not bar:
            return
        try:
            c_val = int(self.actor_entries[cur_key].get().strip() or 0)
            m_val = int(self.actor_entries[max_key].get().strip() or 100) if max_key else 100
            pct = min(1.0, max(0.0, float(c_val) / float(max(1, m_val))))
            bar.set(pct)
        except ValueError:
            pass

    def _create_attr_card(self, parent, key, code, full_name, row, col):
        """Card de atributo com código, nome, bônus/original e stepper [-] val [+] (#5:2393)."""
        card = ctk.CTkFrame(
            parent, fg_color=BG_SUB, corner_radius=8,
            border_width=1, border_color=BORDER_COLOR
        )
        card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        self.attr_cards[key] = card

        p = ctk.CTkFrame(card, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=12, pady=10)

        left_col = ctk.CTkFrame(p, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True)

        lbl_row = ctk.CTkFrame(left_col, fg_color="transparent")
        lbl_row.pack(fill="x")

        lbl_code = ctk.CTkLabel(
            lbl_row, text=code, font=get_mono_font(12, "bold"),
            text_color=TEXT_MAIN
        )
        lbl_code.pack(side="left")
        self.attr_code_labels[key] = lbl_code

        ctk.CTkLabel(
            lbl_row, text=f"  {full_name}", font=get_ui_font(11),
            text_color=TEXT_MUTED
        ).pack(side="left")

        self.stat_badges[key] = ctk.CTkLabel(
            left_col, text="+0 equip.", font=get_mono_font(10),
            text_color=SUCCESS_COLOR, anchor="w"
        )
        self.stat_badges[key].pack(anchor="w", pady=(2, 0))

        # Stepper à direita (#5:2400)
        stepper = ctk.CTkFrame(
            p, fg_color=BG_CARD, corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE, height=30
        )
        stepper.pack(side="right", padx=(6, 0))

        btn_m = ctk.CTkButton(
            stepper, text="−", width=24, height=26,
            font=get_mono_font(13, "bold"), fg_color="transparent",
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            command=lambda k=key: self._step_entry(k, -1, min_val=-9999, max_val=9999)
        )
        btn_m.pack(side="left", padx=1, pady=1)

        self.actor_entries[key] = ctk.CTkEntry(
            stepper, width=52, height=26, font=get_mono_font(12, "bold"),
            fg_color="transparent", border_width=0, justify="center",
            text_color=TEXT_MAIN
        )
        self.actor_entries[key].pack(side="left")
        self.actor_entries[key].bind("<KeyRelease>", lambda e, k=key: self._on_attr_entry_change(k))
        self.actor_entries[key].bind("<Return>", lambda e: self.on_save_stats())
        self.actor_entries[key].bind("<FocusOut>", lambda e: self.on_save_stats())

        btn_p = ctk.CTkButton(
            stepper, text="+", width=24, height=26,
            font=get_mono_font(13, "bold"), fg_color="transparent",
            hover_color=BG_ACTIVE, text_color=TEXT_MUTED,
            command=lambda k=key: self._step_entry(k, 1, min_val=-9999, max_val=9999)
        )
        btn_p.pack(side="left", padx=1, pady=1)

    def _step_entry(self, key: str, delta: int, min_val: int = 0, max_val: int = 9999):
        ent = self.actor_entries.get(key)
        if not ent:
            return
        try:
            cur = int(ent.get().strip() or 0)
        except ValueError:
            cur = 0
        new_val = max(min_val, min(max_val, cur + delta))
        ent.delete(0, "end")
        ent.insert(0, str(new_val))
        if key in self.attr_cards:
            self._on_attr_entry_change(key)
        if self.on_save_stats:
            self.on_save_stats()

    def _on_attr_entry_change(self, key: str):
        ent = self.actor_entries.get(key)
        card = self.attr_cards.get(key)
        badge = self.stat_badges.get(key)
        code_lbl = self.attr_code_labels.get(key)
        if not ent or not card or not badge:
            return
        try:
            cur = int(ent.get().strip())
        except ValueError:
            return
        orig = self.original_stats.get(key, cur)
        if cur != orig:
            diff = cur - orig
            sign = f"+{diff}" if diff > 0 else str(diff)
            card.configure(border_color=PRIMARY_COLOR)
            if code_lbl:
                code_lbl.configure(text_color=PRIMARY_COLOR)
            badge.configure(text=f"valor original {orig} ({sign})", text_color=PRIMARY_COLOR)
        else:
            card.configure(border_color=BORDER_COLOR)
            if code_lbl:
                code_lbl.configure(text_color=TEXT_MAIN)
            badge.configure(text=f"+{cur} bônus" if cur > 0 else "base padrão", text_color=SUCCESS_COLOR if cur > 0 else TEXT_SUBTLE)

    def populate_actor_list(self, actors: List[Dict[str, Any]], party_ids: List[Any], selected_id: Any):
        for w in self.actors_scroll.winfo_children():
            w.destroy()
        self.actor_buttons.clear()
        self.hero_lvl_labels.clear()
        self.hero_hp_bars.clear()

        self.lbl_actors_count.configure(
            text=f"{len(party_ids)} no grupo · {len(actors)} no BD"
        )

        self._party_ids_set = set(str(pid) for pid in party_ids)

        in_party = [a for a in actors if str(a.get("id")) in self._party_ids_set]
        out_party = [a for a in actors if str(a.get("id")) not in self._party_ids_set]

        if in_party:
            lbl_g = ctk.CTkLabel(
                self.actors_scroll, text="NO GRUPO", font=get_ui_font(10, "bold"),
                text_color=TEXT_SUBTLE, anchor="w"
            )
            lbl_g.pack(fill="x", padx=8, pady=(6, 2))
            for a in in_party:
                self._create_hero_list_item(a, str(a.get("id")) == str(selected_id))

        if out_party:
            lbl_o = ctk.CTkLabel(
                self.actors_scroll, text="FORA DO GRUPO", font=get_ui_font(10, "bold"),
                text_color=TEXT_SUBTLE, anchor="w"
            )
            lbl_o.pack(fill="x", padx=8, pady=(10, 2))
            for a in out_party:
                self._create_hero_list_item(a, str(a.get("id")) == str(selected_id))

        try:
            self.actors_scroll.update_idletasks()
        except Exception:
            pass

    def _create_hero_list_item(self, actor: Dict[str, Any], is_selected: bool):
        aid_str = str(actor.get("id"))
        name_raw = actor.get("name") or "Herói"
        parts = name_raw.split()
        initials = (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else name_raw[:2].upper()
        lvl = actor.get("level", 1)

        row = ctk.CTkFrame(
            self.actors_scroll, fg_color=BG_ACTIVE if is_selected else "transparent",
            corner_radius=6, height=48
        )
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        # Circular avatar 32x32 (#5:2115)
        avatar = ctk.CTkFrame(
            row, width=32, height=32, corner_radius=16,
            fg_color=WARNING_BG if is_selected else BG_SUB,
            border_width=1, border_color=PRIMARY_COLOR if is_selected else BORDER_SUBTLE
        )
        avatar.pack(side="left", padx=(8, 8), pady=8)
        avatar.pack_propagate(False)

        lbl_av = ctk.CTkLabel(
            avatar, text=initials, font=get_ui_font(10, "bold"),
            text_color=PRIMARY_COLOR if is_selected else TEXT_MUTED
        )
        lbl_av.pack(expand=True)

        # Nível à direita (#5:2122)
        lbl_lvl = ctk.CTkLabel(
            row, text=f"Nv {lvl}", font=get_mono_font(11),
            text_color=TEXT_MUTED
        )
        lbl_lvl.pack(side="right", padx=(4, 8))
        self.hero_lvl_labels[aid_str] = lbl_lvl

        # Coluna central com botão do nome + mini barra de HP (#5:2117)
        mid_col = ctk.CTkFrame(row, fg_color="transparent")
        mid_col.pack(side="left", fill="both", expand=True, pady=4)

        btn = ctk.CTkButton(
            mid_col, text=f"{name_raw}\n(Nível {lvl})",
            font=get_ui_font(12, "bold" if is_selected else "normal"),
            anchor="w", fg_color="transparent", height=24,
            hover_color=BG_SUB, text_color=TEXT_MAIN if is_selected else TEXT_MUTED,
            command=lambda: self.on_select_actor(actor.get("id"))
        )
        btn.pack(fill="x")

        hp = actor.get("hp", 0)
        max_hp = max(1, actor.get("max_hp", hp) or hp or 1)
        hp_pct = min(1.0, max(0.0, float(hp) / float(max_hp)))

        mini_hp = ctk.CTkProgressBar(
            mid_col, height=4, corner_radius=2,
            fg_color=BG_SUB, progress_color=HP_COLOR
        )
        mini_hp.pack(fill="x", padx=6, pady=(2, 0))
        mini_hp.set(hp_pct)
        self.hero_hp_bars[aid_str] = mini_hp

        for w in (row, avatar, lbl_av, lbl_lvl):
            w.bind("<Button-1>", lambda e, aid=actor.get("id"): self.on_select_actor(aid))

        self.actor_buttons[aid_str] = btn

    def set_selected_actor_data(self, actor: Dict[str, Any]):
        self.current_actor_id = actor.get("id")
        aid_str = str(self.current_actor_id)
        name = actor.get("name", "Herói")
        self.lbl_actor_name.configure(text=name)

        parts = name.split()
        initials = (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else name[:2].upper()
        self.lbl_avatar_large.configure(text=initials)

        cls_name = actor.get("class_name") or f"Classe #{actor.get('class_id', 1)}"
        self.lbl_actor_meta.configure(text=f"ID #{actor.get('id')}")
        self.lbl_class_badge.configure(text=cls_name)

        if aid_str in self._party_ids_set:
            self.lbl_party_badge.configure(
                text="● No grupo", fg_color=SUCCESS_BG, text_color=SUCCESS_COLOR
            )
        else:
            self.lbl_party_badge.configure(
                text="Fora do grupo", fg_color=BG_ACTIVE, text_color=TEXT_MUTED
            )

        # Preenche os campos
        for k, ent in self.actor_entries.items():
            ent.delete(0, "end")
            val = actor.get(k, 0)
            ent.insert(0, str(val))
            self.original_stats[k] = val

            if k in self.stat_badges:
                self._on_attr_entry_change(k)

        # Atualiza barras de recursos (HP, MP, TP)
        self._update_resource_bar("hp", "max_hp")
        self._update_resource_bar("mp", "max_mp")
        self._update_resource_bar("tp", None)

        # Atualiza barra de EXP
        exp_val = int(actor.get("exp", 0) or 0)
        next_exp = int(actor.get("next_exp", max(exp_val + 1000, int(exp_val * 1.25) or 100)) or 100)
        self.lbl_exp_next.configure(text=f"/ {next_exp:,}".replace(",", "."))
        self.exp_bar.set(min(1.0, max(0.0, float(exp_val) / float(max(1, next_exp)))))

        try:
            self.right.update_idletasks()
        except Exception:
            pass

    def _on_filter_change(self, event=None):
        q = self.entry_filter.get().strip().lower()
        for aid_str, btn in self.actor_buttons.items():
            row_frame = btn.master.master
            if not q or q in btn.cget("text").lower() or q in aid_str:
                row_frame.pack(fill="x", pady=1)
            else:
                row_frame.pack_forget()

        try:
            self.actors_scroll.update_idletasks()
        except Exception:
            pass
