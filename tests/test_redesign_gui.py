#!/usr/bin/env python3
"""
Testes específicos para os novos componentes e telas do Redesign da GUI (Figma).
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tkinter as tk

from scripts.ui.modern_app import ModernSaveEditorApp

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

def test_redesign_sidebar_and_navigation():
    """Valida a navegação pelas áreas via Sidebar e via atalhos."""
    try:
        app = ModernSaveEditorApp()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display não disponível: {e}")

    try:
        assert app.sidebar is not None
        assert app.topbar is not None

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
    """Valida a integração da Topbar com o UndoManager e o Dirty Badge."""
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
        # Não deve lançar exceções e deve alternar o texto na Sidebar
        assert app.sidebar.lbl_theme_text.cget("text") in ("Tema claro", "Tema escuro")

        app.toggle_theme()
        assert app.sidebar.lbl_theme_text.cget("text") in ("Tema claro", "Tema escuro")
    finally:
        app.destroy()
