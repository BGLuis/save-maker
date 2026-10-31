#!/usr/bin/env python3
"""
Testes específicos para os novos componentes e telas do Redesign da GUI (Figma).
Valida a fidelidade estrutural e interativa com o Figma Save Maker (#0:1).
"""

import pytest
from pathlib import Path
from scripts.ui.modern_app import ModernSaveEditorApp
from scripts.ui.views.switches_view import extract_category_and_clean_name

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_redesign_sidebar_and_navigation():
    """Valida a navegação pelas áreas via Sidebar, atalhos visíveis, statusbar e busca."""
    try:
        app = ModernSaveEditorApp()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display não disponível: {e}")

    try:
        assert app.sidebar is not None
        assert app.topbar is not None
        assert hasattr(app, "statusbar")
        assert hasattr(app, "lbl_status_text")

        # Verifica atalhos visíveis nos botões da Sidebar (Ctrl 0 a Ctrl 5)
        assert "library" in app.sidebar.nav_shortcuts
        assert app.sidebar.nav_shortcuts["library"].cget("text") == "Ctrl 0"
        assert app.sidebar.nav_shortcuts["overview"].cget("text") == "Ctrl 1"
        assert app.sidebar.nav_shortcuts["advanced"].cget("text") == "Ctrl 5"

        # Topbar possui método focus_search (Ctrl+K) e botão Exportar JSON
        app.topbar.focus_search()
        assert "Exportar JSON" in app.topbar.btn_export.cget("text")

        # Teste de navegação para cada uma das áreas
        app.select_nav_area("overview")
        assert app.sidebar.current_area == "overview"
        assert app.topbar.lbl_title.cget("text") == "Visão geral"

        app.select_nav_area("actors")
        assert app.sidebar.current_area == "actors"
        assert app.topbar.lbl_title.cget("text") == "Personagens"

        app.select_nav_area("inventory")
        assert app.sidebar.current_area == "inventory"
        assert app.topbar.lbl_title.cget("text") == "Inventário"

        app.select_nav_area("switches")
        assert app.sidebar.current_area == "switches"
        assert app.topbar.lbl_title.cget("text") == "Switches & variáveis"

        app.select_nav_area("advanced")
        assert app.sidebar.current_area == "advanced"
        assert app.topbar.lbl_title.cget("text") == "Árvore JSON"

        app.select_nav_area("library")
        assert app.sidebar.current_area == "library"
        assert app.topbar.lbl_title.cget("text") == "Biblioteca de Jogos"
    finally:
        app.destroy()


def test_redesign_undo_redo_and_dirty_badge():
    """Valida a integração da Topbar com o UndoManager, Dirty Badge e telas detalhadas do Figma."""
    try:
        app = ModernSaveEditorApp()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display não disponível: {e}")

    try:
        fixture = FIXTURES_DIR / "file2.rpgsave"
        app.load_save_file(fixture, synchronous=True)

        assert app.adapter is not None
        initial_gold = app.adapter.get_gold()

        # Statusbar atualizada com tempo de carregamento
        assert "save carregado em" in app.lbl_status_text.cget("text")

        # O botão desfazer deve começar desabilitado
        assert app.topbar.btn_undo.cget("state") == "disabled"
        assert app.topbar.lbl_dirty_text.cget("text") == "Salvo"

        # Altera ouro -> grava ponto no UndoManager
        app._set_gold(initial_gold + 5000)
        assert app.adapter.get_gold() == initial_gold + 5000
        assert app.topbar.btn_undo.cget("state") == "normal"
        assert "alteração" in app.topbar.lbl_dirty_text.cget("text")

        # Aciona Desfazer (Ctrl Z)
        app.undo_last_action()
        assert app.adapter.get_gold() == initial_gold
        assert app.topbar.btn_undo.cget("state") == "disabled"

        # Verifica Tela 02 (Personagens): barras de recursos, badges e barra de EXP
        app.select_nav_area("actors")
        assert "hp" in app.view_actors.resource_bars
        assert "mp" in app.view_actors.resource_bars
        assert "tp" in app.view_actors.resource_bars
        assert hasattr(app.view_actors, "exp_bar")
        assert hasattr(app.view_actors, "lbl_class_badge")
        assert hasattr(app.view_actors, "lbl_party_badge")

        # Verifica Tela 03 (Inventário): coluna de descrição preservando índice 2 como quantidade
        app.select_nav_area("inventory")
        assert tuple(app.tree_inv.cget("displaycolumns")) == ("id", "name", "desc", "qty")
        inv_children = app.tree_inv.get_children()
        assert len(inv_children) > 0
        first_vals = app.tree_inv.item(inv_children[0], "values")
        assert len(first_vals) == 4  # (id, name, qty, desc)

        # Verifica Tela 04 (Switches): coluna de categoria preservando índice 2 como estado/valor
        cat, clean = extract_category_and_clean_name("[Chefe] Dragão Derrotado")
        assert cat == "Chefe"
        assert clean == "Dragão Derrotado"
        app.select_nav_area("switches")
        assert tuple(app.tree_sys.cget("displaycolumns")) == ("id", "cat", "name", "val")

        # Verifica Tela 05 (Árvore JSON): breadcrumb e validação ao vivo
        app.select_nav_area("advanced")
        app.view_advanced.set_inspector_node("party._gold", 12480)
        assert "party" in app.view_advanced.lbl_breadcrumb.cget("text")
        assert "JSON válido" in app.view_advanced.lbl_validation.cget("text")

        # Verifica Tela 09 e 10 (Biblioteca): filtro, ordenação e detalhes com coluna Ouro
        app.select_nav_area("library")
        assert hasattr(app.view_library, "entry_game_filter")
        assert "recent" in app.view_library.sort_btns
        games = app.lib_mgr.get_games()
        if games:
            app.view_library.show_game_details(games[0])
            assert "gold" in tuple(app.view_library.tree_slots.cget("columns"))
    finally:
        app.destroy()


def test_redesign_theme_toggle():
    """Valida a alternância de temas Dark/Light nos novos componentes."""
    try:
        app = ModernSaveEditorApp()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display não disponível: {e}")

    try:
        # Modo inicial
        app.toggle_theme()
        # Não deve lançar exceções e deve alternar o texto e o pill switch na Sidebar
        assert app.sidebar.lbl_theme_text.cget("text") in ("Tema claro", "Tema escuro")
        assert hasattr(app.sidebar, "theme_switch_pill")

        app.toggle_theme()
        assert app.sidebar.lbl_theme_text.cget("text") in ("Tema claro", "Tema escuro")
    finally:
        app.destroy()
