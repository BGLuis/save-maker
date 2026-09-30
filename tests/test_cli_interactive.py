#!/usr/bin/env python3
"""
Testes automatizados para a CLI Interativa e Integrações de Terminal.
Verifica:
  - Varredura de arquivos de save (scan_for_save_files)
  - Sessão interativa (InteractiveCliSession)
  - Subprocessos e scripts auxiliares (export, aliases, scripts/rpg-save-editor)
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from rich.console import Console

# Configura sys.path
TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for p in (str(PROJECT_ROOT), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.cli.interactive import scan_for_save_files, InteractiveCliSession
from scripts.core.database_manager import GameDatabaseManager


class TestCliInteractive(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.sample_save = PROJECT_ROOT / "save" / "file2.rpgsave"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_scan_for_save_files(self):
        # 1. Varredura na pasta do projeto deve encontrar save/file2.rpgsave
        found = scan_for_save_files(PROJECT_ROOT / "save")
        self.assertTrue(len(found) >= 1)
        self.assertTrue(any(f.name == "file2.rpgsave" for f in found))

        # 2. Varredura em caminho inexistente retorna lista vazia
        empty = scan_for_save_files(self.tmp_path / "nonexistent")
        self.assertEqual(empty, [])

        # 3. Passar arquivo direto retorna o próprio arquivo
        direct = scan_for_save_files(self.sample_save)
        self.assertEqual(direct, [self.sample_save.resolve()])

        # 4. Cria arquivos temporários com extensões suportadas
        (self.tmp_path / "slot1.rmmzsave").write_text("dummy")
        (self.tmp_path / "Save01.rvdata2").write_text("dummy")
        (self.tmp_path / "Save01.lsd").write_text("dummy")
        (self.tmp_path / "readme.txt").write_text("ignore me")
        tmp_found = scan_for_save_files(self.tmp_path)
        tmp_names = [f.name for f in tmp_found]
        self.assertIn("slot1.rmmzsave", tmp_names)
        self.assertIn("Save01.rvdata2", tmp_names)
        self.assertIn("Save01.lsd", tmp_names)
        self.assertNotIn("readme.txt", tmp_names)

    def test_session_lifecycle(self):
        # Cria cópia do save de teste
        test_save = self.tmp_path / "test.rpgsave"
        shutil.copy2(self.sample_save, test_save)

        session = InteractiveCliSession(test_save)
        self.assertEqual(session.save_file, test_save.resolve())

        # Carrega o save
        session._load_save(test_save)
        self.assertIsNotNone(session.adapter)
        self.assertIn("RPG Maker MV", session.adapter.engine_name)

        # Verifica banco de dados integrado
        self.assertGreater(len(session.db.items), 0)
        actor1_name = session.db.get_actor_name(1)
        self.assertEqual(actor1_name, "Himeno Iroha")
        self.assertEqual(session.db.get_currency_unit(), "Yen")

        # Testa alterações de ouro
        original_gold = session.adapter.get_gold()
        session.adapter.set_gold(888888)
        self.assertEqual(session.adapter.get_gold(), 888888)
        self.assertTrue(session.adapter.dirty)

        # Testa alterações de atores
        actors = session.adapter.get_actors()
        self.assertGreater(len(actors), 0)
        hero = actors[0]
        session.adapter.update_actor(hero["id"], {"hp": 5000, "max_hp": 5000, "level": 50})
        updated = [a for a in session.adapter.get_actors() if a["id"] == hero["id"]][0]
        self.assertEqual(updated["level"], 50)
        self.assertEqual(updated["hp"], 5000)

        # Salva o arquivo modificado e verifica backup
        session.adapter.save(test_save, backup=True)
        self.assertTrue(test_save.exists())
        self.assertTrue(test_save.with_suffix(".rpgsave.bak").exists())

    def test_export_via_cli(self):
        dst_json = self.tmp_path / "exported.json"
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "export",
            str(self.sample_save),
            str(dst_json)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Export falhou: {res.stderr}")
        self.assertTrue(dst_json.exists())

        # Valida conteúdo JSON
        data = json.loads(dst_json.read_text(encoding="utf-8"))
        self.assertIn("engine", data)
        self.assertIn("RPG Maker MV", data["engine"])
        self.assertIn("data", data)
        self.assertIn("party", data["data"])

    def test_wrapper_script_aliases(self):
        wrapper = PROJECT_ROOT / "scripts" / "rpg-save-editor"
        self.assertTrue(wrapper.exists())
        self.assertTrue(os.access(wrapper, os.X_OK))

        custom_bin = self.tmp_path / "bin"
        env = os.environ.copy()
        env["LOCAL_BIN"] = str(custom_bin)

        # 1. Listar aliases antes
        res = subprocess.run([str(wrapper), "--list-aliases"], env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Nenhum atalho encontrado", res.stdout)

        # 2. Adicionar alias
        res = subprocess.run([str(wrapper), "--add-alias", "se-test"], env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue((custom_bin / "se-test").is_symlink())

        # 3. Listar aliases após
        res = subprocess.run([str(wrapper), "--list-aliases"], env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("se-test", res.stdout)

        # 4. Remover alias
        res = subprocess.run([str(wrapper), "--remove-alias", "se-test"], env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertFalse((custom_bin / "se-test").exists())


    def test_switch_list_discloses_truncated_count(self):
        session = InteractiveCliSession()
        session.console = Console(record=True, width=120)
        session.adapter = Mock()
        session.adapter.get_switches.return_value = [
            {"id": switch_id, "name": f"Switch {switch_id}", "value": False}
            for switch_id in range(1, 779)
        ]

        with patch(
            "scripts.cli.interactive.Prompt.ask",
            side_effect=["", "0", ""],
        ):
            session._action_switches()

        output = session.console.export_text()
        self.assertIn("50 de 778", output)
        self.assertIn("Switch 50", output)
        self.assertNotIn("Switch 51", output)

    def test_inventory_list_discloses_truncated_count(self):
        session = InteractiveCliSession()
        session.console = Console(record=True, width=120)
        session.adapter = Mock()
        session.adapter.get_inventory.return_value = [
            {"id": item_id, "name": f"Item {item_id}", "quantity": 1}
            for item_id in range(1, 151)
        ]

        with patch(
            "scripts.cli.interactive.Prompt.ask",
            side_effect=["1", "", "0", ""],
        ):
            session._action_inventory()

        output = session.console.export_text()
        self.assertIn("100 de 150", output)
        self.assertIn("Item 100", output)
        self.assertNotIn("Item 101", output)

    def test_variable_list_discloses_truncated_count(self):
        session = InteractiveCliSession()
        session.console = Console(record=True, width=120)
        session.adapter = Mock()
        session.adapter.get_variable_name.return_value = "Var"
        session.adapter.get_variables.return_value = [
            {"id": var_id, "name": f"Variable {var_id}", "value": 0}
            for var_id in range(1, 121)
        ]

        with patch(
            "scripts.cli.interactive.Prompt.ask",
            side_effect=["", "0", ""],
        ):
            session._action_variables()

        output = session.console.export_text()
        self.assertIn("50 de 120", output)
        self.assertIn("Variable 50", output)
        self.assertNotIn("Variable 51", output)


if __name__ == "__main__":
    unittest.main()
