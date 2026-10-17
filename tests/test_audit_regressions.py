#!/usr/bin/env python3
"""
Testes de Regressão e Auditoria Cobrindo Critérios de Aceite das 16 Issues:
- U-03: Export/Import roundtrip via subprocesso + format: json
- U-04: DatabaseManager isolamento, sem fallback para repo e clear()
- U-05: MV Actor paramPlus (@a), sem chaves numéricas avulsas e cálculo correto de cura
- U-06: MV Actor level atualiza exp correspondente
- U-07: GUI close window prompt de alterações não salvas (Cancel -> preserva, No -> destroy)
- U-08: Preservação de backup .bak original e atomic_write / integridade em erro
- U-09: Isolamento de snapshot durante concorrência no save() e dirty=True
- U-10: GUI validação estrita de inputs inválidos para atributos e inventário
- U-11: GUI paginação incremental do Treeview avançado (@a com 852 elementos)
- U-12: GenericJsonAdapter armaduras/armas com DB mapeado e flag dirty
- P-02: Roundtrip de compressão zlib-utf8 (RPG Maker MZ)
- P-03: Detecção de .sav renomeado com descompressão única (cache _already_loaded_path)
- P-04: Atualização in-place de botão de ator sem destruir widgets
"""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

TESTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = TESTS_DIR.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
FIXTURES_DIR = TESTS_DIR / "fixtures"

for p in (str(ROOT_DIR), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from core.database_manager import GameDatabaseManager
from core.detector import detect_and_create_adapter
from core.generic_adapter import GenericJsonAdapter
from core.mv_mz_adapter import MvMzAdapter
from import_json_to_rpgsave import import_json


def test_u03_export_import_roundtrip(tmp_path):
    """U-03: Subprocesso main.py export -> import -> export produz dados idênticos e preserva 'party' no root."""
    fixture = FIXTURES_DIR / "file2.rpgsave"
    e1 = tmp_path / "e1.json"
    reimported = tmp_path / "reimported.rpgsave"
    e2 = tmp_path / "e2.json"

    # 1. main.py export
    r1 = subprocess.run(
        [sys.executable, str(ROOT_DIR / "main.py"), "export", str(fixture), str(e1)],
        capture_output=True,
        text=True,
    )
    assert r1.returncode == 0, f"export falhou: {r1.stderr}"

    # 2. main.py import
    r2 = subprocess.run(
        [sys.executable, str(ROOT_DIR / "main.py"), "import", str(e1), str(reimported)],
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 0, f"import falhou: {r2.stderr}"

    # 3. main.py export reimportado
    r3 = subprocess.run(
        [sys.executable, str(ROOT_DIR / "main.py"), "export", str(reimported), str(e2)],
        capture_output=True,
        text=True,
    )
    assert r3.returncode == 0, f"re-export falhou: {r3.stderr}"

    d1 = json.loads(e1.read_text(encoding="utf-8"))
    d2 = json.loads(e2.read_text(encoding="utf-8"))
    assert d1["data"] == d2["data"]

    adapter = MvMzAdapter()
    adapter.load(reimported)
    assert "party" in adapter.raw_data

    # MvMzAdapter.export_to_json inclui format: json
    json_export = tmp_path / "export_direct.json"
    adapter.export_to_json(json_export)
    loaded_export = json.loads(json_export.read_text(encoding="utf-8"))
    assert loaded_export.get("format") == "json"


def test_u04_database_no_repo_fallback_and_clear(tmp_path):
    """U-04: GameDatabaseManager carrega dados adjacentes e zera completamente sem fallback para repo."""
    db = GameDatabaseManager()
    fixture = FIXTURES_DIR / "file2.rpgsave"
    found = db.discover_and_load(fixture)
    assert found is True
    assert db.is_loaded() is True
    assert len(db.items) > 0

    # Diretório temporário isolado sem pasta data/
    empty_file = tmp_path / "x.rvdata2"
    empty_file.write_bytes(b"dummy")
    found_empty = db.discover_and_load(empty_file)
    assert found_empty is False
    assert db.is_loaded() is False
    assert len(db.items) == 0


def test_u05_mv_actor_param_plus_and_heal():
    """U-05: Modificação de atributos altera _paramPlus['@a'] sem chaves avulsas e cura usa max_hp real."""
    db = GameDatabaseManager()
    fixture = FIXTURES_DIR / "file2.rpgsave"
    db.discover_and_load(fixture)

    adapter = MvMzAdapter(db)
    adapter.load(fixture)

    actor1 = [a for a in adapter.get_actors() if a["id"] == 1][0]
    base_mhp = db.get_class_param_base(actor1["class_id"], 0, actor1["level"])
    # base_mhp 211 + param_plus[0] 50 = 261, hp atual = 211
    assert actor1["max_hp"] == base_mhp + actor1["mhp_bonus"]
    assert actor1["max_hp"] == 261
    assert actor1["max_hp"] > actor1["hp"]
    assert actor1["hp"] == 211

    # Atualiza atk para 999
    adapter.update_actor(1, {"atk": 999})
    actor_raw = [a for a in adapter.get_actors() if a["id"] == 1][0]["raw"]
    assert actor_raw["_paramPlus"]["@a"][2] == 999

    # Nenhuma chave numérica fora de @a
    numeric_keys = [k for k in actor_raw["_paramPlus"].keys() if str(k).isdigit()]
    assert len(numeric_keys) == 0

    # Cura completa define hp para max_hp (261 > 211)
    adapter.update_actor(1, {"hp": actor1["max_hp"]})
    actor1_healed = [a for a in adapter.get_actors() if a["id"] == 1][0]
    assert actor1_healed["hp"] == actor1["max_hp"]
    assert actor1_healed["hp"] > 211


def test_u06_mv_actor_level_updates_exp():
    """U-06: Alteração de nível atualiza a experiência correspondente da classe."""
    db = GameDatabaseManager()
    fixture = FIXTURES_DIR / "file2.rpgsave"
    db.discover_and_load(fixture)

    adapter = MvMzAdapter(db)
    adapter.load(fixture)

    actor1 = [a for a in adapter.get_actors() if a["id"] == 1][0]
    class_id = actor1.get("class_id", 1)

    adapter.update_actor(1, {"level": 10})
    actor_raw = [a for a in adapter.get_actors() if a["id"] == 1][0]["raw"]
    expected_exp = db.get_exp_for_level(class_id, 10)
    assert expected_exp is not None and expected_exp > 0
    assert actor_raw["_exp"][str(class_id)] == expected_exp


def test_u07_gui_close_window_unsaved_warning():
    """U-07: Fechamento de janela avisa se houver alterações pendentes (Cancel aborta, No destrói)."""
    try:
        from ui.modern_app import ModernSaveEditorApp
        app = ModernSaveEditorApp()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display não disponível: {e}")

    try:
        mock_adapter = MagicMock()
        mock_adapter.dirty = True
        mock_adapter.changes_count = 3
        app.adapter = mock_adapter

        # Cenário 1: Usuário cancela o fechamento (None) -> destroy NÃO é chamado
        with patch("ui.modern_app.messagebox.askyesnocancel", return_value=None) as mock_msg, \
             patch.object(app, "destroy") as mock_destroy:
            app._on_close_window()
            mock_msg.assert_called_once()
            mock_destroy.assert_not_called()

        # Cenário 2: Usuário escolhe sair sem salvar (False) -> destroy É chamado
        with patch("ui.modern_app.messagebox.askyesnocancel", return_value=False) as mock_msg, \
             patch.object(app, "destroy") as mock_destroy:
            app._on_close_window()
            mock_msg.assert_called_once()
            mock_destroy.assert_called_once()
    finally:
        app.destroy()


def test_u08_backup_preserved_and_atomic_save(tmp_path):
    """U-08: Backup .bak preserva bytes originais em múltiplas edições e escrita atômica resiste a erros."""
    src_fixture = FIXTURES_DIR / "file2.rpgsave"
    save_file = tmp_path / "test.rpgsave"
    shutil.copy2(src_fixture, save_file)
    original_bytes = save_file.read_bytes()

    adapter = MvMzAdapter()
    adapter.load(save_file)

    # 1ª edição + save
    adapter.set_gold(111111)
    adapter.save(save_file, backup=True)
    bak_file = save_file.with_name(f"{save_file.name}.bak")
    assert bak_file.exists()
    assert bak_file.read_bytes() == original_bytes

    # 2ª edição + save
    adapter.set_gold(222222)
    adapter.save(save_file, backup=True)
    # .bak DEVE conter os bytes originais de antes da 1ª edição
    assert bak_file.read_bytes() == original_bytes

    # Falha simulada durante backup (disk full) em nova instância
    adapter2 = MvMzAdapter()
    adapter2.load(save_file)
    adapter2.set_gold(333333)
    current_save_bytes = save_file.read_bytes()

    with patch("shutil.copy2", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            adapter2.save(save_file, backup=True)

    # Destino permanece intacto
    assert save_file.read_bytes() == current_save_bytes


def test_u09_concurrent_mutation_during_save(tmp_path):
    """U-09: Mutação concorrente durante save() grava o snapshot prévio e mantém dirty=True."""
    src_fixture = FIXTURES_DIR / "file2.rpgsave"
    save_file = tmp_path / "concurrent.rpgsave"
    shutil.copy2(src_fixture, save_file)

    adapter = MvMzAdapter()
    adapter.load(save_file)
    adapter.set_gold(12345)
    initial_gold = adapter.get_gold()

    orig_compress = adapter._compress

    def fake_compress(data, compression, encoding="none"):
        # Muta o objeto durante a compressão do save()
        adapter.set_gold(999999)
        return orig_compress(data, compression, encoding)

    with patch.object(adapter, "_compress", side_effect=fake_compress):
        adapter.save(save_file, backup=False)

    # O arquivo no disco deve refletir o snapshot prévio
    check_adapter = MvMzAdapter()
    check_adapter.load(save_file)
    assert check_adapter.get_gold() == initial_gold
    assert check_adapter.get_gold() != 999999

    # dirty deve permanecer True após o término de save()
    assert adapter.dirty is True


def test_u10_gui_invalid_actor_and_inventory_inputs():
    """U-10: GUI valida valores numéricos e rejeita 'abc' ou '1.000' sem mutar adapter."""
    try:
        from ui.modern_app import ModernSaveEditorApp
        app = ModernSaveEditorApp()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display não disponível: {e}")

    try:
        mock_adapter = MagicMock()
        mock_adapter.get_actors.return_value = [{"id": 1, "name": "Hero", "level": 1, "raw": {}}]
        app.adapter = mock_adapter
        app.selected_actor_id = 1

        # Teste 1: Atributo de ator inválido ('abc')
        mock_entry = MagicMock()
        mock_entry.get.return_value = "abc"
        app.actor_entries = {"atk": mock_entry}

        with patch("ui.modern_app.messagebox.showwarning") as mock_warn:
            app._save_current_actor_stats()
            mock_warn.assert_called_once()
            mock_adapter.update_actor.assert_not_called()

        # Teste 2: Quantidade de inventário inválida ('1.000')
        app.selected_inv_item_id = "1"
        mock_inv_entry = MagicMock()
        mock_inv_entry.get.return_value = "1.000"
        app.entry_inv_qty = mock_inv_entry

        with patch("ui.modern_app.messagebox.showwarning") as mock_warn_inv:
            app._apply_inv_qty_from_entry()
            mock_warn_inv.assert_called_once()
            mock_adapter.set_item_quantity.assert_not_called()
    finally:
        app.destroy()


def test_u11_gui_advanced_tree_pagination():
    """U-11: Árvore avançada carrega incrementalmente e atinge a totalidade de 852 variáveis."""
    try:
        from ui.modern_app import ModernSaveEditorApp
        app = ModernSaveEditorApp()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display não disponível: {e}")

    try:
        fixture = FIXTURES_DIR / "file2.rpgsave"
        app.load_save_file(fixture, synchronous=True)

        app.tabview.set("🌲 Modo Avançado / Árvore")
        app._on_tab_change()

        # Encontra nó 'variables'
        root_children = app.adv_tree.get_children("")
        var_node = next(ch for ch in root_children if app.adv_tree.item(ch, "text") == "variables")

        app.adv_tree.focus(var_node)
        app.adv_tree.selection_set(var_node)
        app._on_tree_open(None)

        # Encontra nó '_data'
        var_children = app.adv_tree.get_children(var_node)
        data_node = next(ch for ch in var_children if app.adv_tree.item(ch, "text") == "_data")

        app.adv_tree.focus(data_node)
        app.adv_tree.selection_set(data_node)
        app._on_tree_open(None)

        # Encontra nó '@a'
        data_children = app.adv_tree.get_children(data_node)
        at_a_node = next(ch for ch in data_children if app.adv_tree.item(ch, "text") == "@a")

        app.adv_tree.focus(at_a_node)
        app.adv_tree.selection_set(at_a_node)
        app._on_tree_open(None)

        # Expande cada nó '… mais N itens' até esgotar
        while True:
            children = app.adv_tree.get_children(at_a_node)
            more_node = None
            for ch in children:
                meta = app.tree_paths.get(ch)
                if isinstance(meta, dict) and meta.get("_is_more"):
                    more_node = ch
                    break
            if not more_node:
                break
            app.adv_tree.focus(more_node)
            app.adv_tree.selection_set(more_node)
            app._on_tree_open(None)

        final_children = app.adv_tree.get_children(at_a_node)
        assert len(final_children) == 852
    finally:
        app.destroy()


def test_u12_generic_json_weapons_armors_and_dirty():
    """U-12: GenericJsonAdapter manipula armas e armaduras com nomes do DB e flag dirty correta."""
    db = GameDatabaseManager()
    db.discover_and_load(FIXTURES_DIR / "file2.rpgsave")
    assert db.is_loaded() is True
    assert len(db.weapons) > 0

    adapter = GenericJsonAdapter(db)
    adapter.raw_data = {"weapons": {}}
    adapter.dirty = False

    adapter.unlock_all_items("weapons")
    assert set(adapter.raw_data["weapons"].keys()) == set(str(k) for k in db.weapons.keys())
    assert adapter.dirty is True

    inv = adapter.get_inventory("weapons")
    assert len(inv) > 0
    first_item = inv[0]
    expected_name = db.get_weapon_name(first_item["id"])
    assert first_item["name"] == expected_name


def test_p02_zlib_utf8_roundtrip(tmp_path):
    """P-02: Suporte completo e roundtrip ao formato zlib-utf8 do RPG Maker MZ."""
    sample_mz = FIXTURES_DIR / "sample.rmmzsave"
    assert sample_mz.exists()

    adapter = MvMzAdapter()
    adapter.load(sample_mz)
    assert adapter.engine_name == "RPG Maker MZ"
    assert adapter.compression == "zlib-utf8"
    assert adapter.get_gold() > 0

    out_save = tmp_path / "saved.rmmzsave"
    adapter.set_gold(888999)
    adapter.save(out_save, backup=False)

    reloaded = MvMzAdapter()
    reloaded.load(out_save)
    assert reloaded.get_gold() == 888999
    assert reloaded.compression == "zlib-utf8"

    # Teste de import_json com zlib-utf8
    exported_json = tmp_path / "exp.json"
    reloaded.export_to_json(exported_json)

    reimported_mz = tmp_path / "reimp.rmmzsave"
    import_json(exported_json, reimported_mz, forced_compression="zlib-utf8")

    check_imp = MvMzAdapter()
    check_imp.load(reimported_mz)
    assert check_imp.get_gold() == 888999
    assert check_imp.compression == "zlib-utf8"


def test_p03_detector_single_load_on_renamed_sav(tmp_path):
    """P-03: Arquivo renomeado para .sav passa por descompressão apenas uma única vez."""
    renamed_sav = tmp_path / "renamed.sav"
    shutil.copy2(FIXTURES_DIR / "file2.rpgsave", renamed_sav)

    db = GameDatabaseManager()
    db.discover_and_load(FIXTURES_DIR / "file2.rpgsave")

    decompress_calls = 0
    real_decompress = MvMzAdapter._decompress

    def spy_decompress(self, data):
        nonlocal decompress_calls
        decompress_calls += 1
        return real_decompress(self, data)

    with patch.object(MvMzAdapter, "_decompress", spy_decompress):
        adapter = detect_and_create_adapter(renamed_sav, db)
        assert isinstance(adapter, MvMzAdapter)
        adapter.load(renamed_sav)

    assert decompress_calls == 1, f"Esperado 1 descompressão, obtido {decompress_calls}"


def test_p04_gui_apply_actor_does_not_destroy_buttons():
    """P-04: Ao salvar atributos de um herói na GUI, os botões são atualizados in-place sem destruição."""
    try:
        from ui.modern_app import ModernSaveEditorApp
        app = ModernSaveEditorApp()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display não disponível: {e}")

    try:
        fixture = FIXTURES_DIR / "file2.rpgsave"
        app.load_save_file(fixture, synchronous=True)

        app.tabview.set("👥 Personagens & Atributos")
        app._on_tab_change()

        assert app.selected_actor_id is not None
        aid_str = str(app.selected_actor_id)
        btn = app.actor_buttons[aid_str]

        with patch.object(app.actors_scroll, "winfo_children", wraps=app.actors_scroll.winfo_children) as mock_winfo, \
             patch.object(btn, "destroy") as mock_destroy, \
             patch.object(btn, "configure", wraps=btn.configure) as mock_configure:

            app.actor_entries["atk"].delete(0, "end")
            app.actor_entries["atk"].insert(0, "555")

            app._save_current_actor_stats()

            mock_winfo.assert_not_called()
            mock_destroy.assert_not_called()
            mock_configure.assert_called()
    finally:
        app.destroy()
