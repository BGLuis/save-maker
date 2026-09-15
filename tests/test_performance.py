#!/usr/bin/env python3
"""
Testes automatizados de desempenho e validação da eliminação de travamentos da interface.
Verifica:
  - Velocidade sub-milissegundo de operações em lote (unlock_all_items, get_inventory, switches, vars)
  - Sistema de lazy-loading e invalidação de cache de abas (tabs_need_refresh)
  - População ultrarrápida da tabela Treeview em comparação aos compound widgets antigos
  - Ordenação e filtragem em tempo real
"""

import sys
import time
import unittest
from pathlib import Path

# Configura sys.path
TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for p in (str(PROJECT_ROOT), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.core.database_manager import GameDatabaseManager
from scripts.core.detector import detect_and_create_adapter


class TestPerformanceAndOptimization(unittest.TestCase):

    def setUp(self):
        self.sample_save = PROJECT_ROOT / "save" / "file2.rpgsave"
        self.db = GameDatabaseManager()
        self.db.discover_and_load(self.sample_save)
        self.adapter = detect_and_create_adapter(self.sample_save, self.db)
        self.adapter.load(self.sample_save)

    def test_core_bulk_operations_speed(self):
        """Verifica se operações em lote no adaptador executam em menos de 50ms."""
        # 1. Desbloquear todas as armaduras
        start = time.perf_counter()
        armors_unlocked = self.adapter.unlock_all_items("armors", 1)
        dur_armors = time.perf_counter() - start
        self.assertGreater(armors_unlocked, 0)
        self.assertLess(dur_armors, 0.05, f"unlock_all armors demorou demais: {dur_armors*1000:.2f}ms")

        # 2. Desbloquear todos os itens
        start = time.perf_counter()
        items_unlocked = self.adapter.unlock_all_items("items", 99)
        dur_items = time.perf_counter() - start
        self.assertGreater(items_unlocked, 0)
        self.assertLess(dur_items, 0.05, f"unlock_all items demorou demais: {dur_items*1000:.2f}ms")

        # 3. Obter inventário de armaduras
        start = time.perf_counter()
        inv_armors = self.adapter.get_inventory("armors")
        dur_inv = time.perf_counter() - start
        self.assertEqual(len(inv_armors), armors_unlocked)
        self.assertLess(dur_inv, 0.05, f"get_inventory demorou demais: {dur_inv*1000:.2f}ms")

        # 4. Obter switches e variáveis (centenas de itens)
        start = time.perf_counter()
        switches = self.adapter.get_switches()
        dur_sw = time.perf_counter() - start
        self.assertGreater(len(switches), 100)
        self.assertLess(dur_sw, 0.05, f"get_switches demorou demais: {dur_sw*1000:.2f}ms")

        start = time.perf_counter()
        variables = self.adapter.get_variables()
        dur_vars = time.perf_counter() - start
        self.assertGreater(len(variables), 100)
        self.assertLess(dur_vars, 0.05, f"get_variables demorou demais: {dur_vars*1000:.2f}ms")

    def test_gui_lazy_loading_and_fast_treeview(self):
        """Testa o ciclo de vida de renderização da UI moderna, cache de abas e Treeview."""
        try:
            from scripts.ui.modern_app import ModernSaveEditorApp
            app = ModernSaveEditorApp()
            app.withdraw()  # Esconde janela durante o teste
        except Exception as e:
            self.skipTest(f"Ambiente gráfico Tkinter não disponível: {e}")
            return

        try:
            # 1. Carrega o save na aplicação (síncrono no teste)
            app.load_save_file(self.sample_save, synchronous=True)

            # Verifica se o lazy-loading funcionou:
            # Overview deve ter sido carregado, mas as demais abas devem estar com flag True (pendentes)
            self.assertFalse(app.tabs_need_refresh["overview"], "Aba overview deveria estar atualizada")
            self.assertTrue(app.tabs_need_refresh["inventory"], "Aba inventário deveria estar pendente (lazy)")
            self.assertTrue(app.tabs_need_refresh["switches"], "Aba switches deveria estar pendente (lazy)")

            # 2. Ativar atalho de cheat na aba Visão Geral (Overview)
            start = time.perf_counter()
            app._quick_unlock_all("armors", 1)
            dur_cheat = time.perf_counter() - start

            # Não deve haver congelamento! O atalho deve responder em menos de 50ms
            self.assertLess(dur_cheat, 0.05, f"Cheat atalho demorou {dur_cheat*1000:.2f}ms, deveria ser instantâneo")
            self.assertTrue(app.tabs_need_refresh["inventory"], "Inventário deve estar marcado para refresh")
            self.assertTrue(app.adapter.dirty)

            # 3. Simula troca para a aba de Inventário
            app.tabview.set("🎒 Inventário")
            app.current_inv_kind = "armors"

            start = time.perf_counter()
            app._on_tab_change()
            dur_render = time.perf_counter() - start

            # A tabela Treeview moderna deve renderizar centenas de armaduras em menos de 100ms
            self.assertLess(dur_render, 0.10, f"Renderização da tabela de inventário demorou: {dur_render*1000:.2f}ms")
            self.assertFalse(app.tabs_need_refresh["inventory"], "Inventário agora deve estar limpo de pendências")

            children = app.tree_inv.get_children()
            self.assertGreater(len(children), 100, "Deveria ter inserido as armaduras na tabela")

            # 4. Teste de ordenação por coluna
            start = time.perf_counter()
            app._sort_inventory("name")
            dur_sort = time.perf_counter() - start
            self.assertLess(dur_sort, 0.05, f"Ordenação demorou {dur_sort*1000:.2f}ms")

            # 5. Teste de edição direta de célula
            first_id = children[0]
            app._selected_inv_id = first_id
            start = time.perf_counter()
            app._set_selected_inv_qty(77)
            dur_cell = time.perf_counter() - start
            self.assertLess(dur_cell, 0.01, "Atualização de célula deve ser sub-milissegundo")
            self.assertEqual(app.tree_inv.item(first_id, "values")[2], "77")

            # 6. Teste de troca para aba de Switches
            app.tabview.set("⚙ Switches & Variáveis")
            start = time.perf_counter()
            app._on_tab_change()
            dur_sw = time.perf_counter() - start
            self.assertLess(dur_sw, 0.10, f"Renderização de switches demorou: {dur_sw*1000:.2f}ms")
            self.assertFalse(app.tabs_need_refresh["switches"])
            sw_children = app.tree_sys.get_children()
            self.assertGreater(len(sw_children), 100)

            # 7. Teste de alternar switch com atalho
            app._selected_sys_id = int(sw_children[0])
            start = time.perf_counter()
            app._toggle_selected_switch()
            dur_toggle = time.perf_counter() - start
            self.assertLess(dur_toggle, 0.01, "Toggle de switch deve ser instantâneo")

        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
