#!/usr/bin/env python3
"""
Testes automatizados para todos os formatos de save de RPG Maker:
- MV (.rpgsave)
- MZ (.rmmzsave)
- VX Ace (.rvdata2)
- VX (.rvdata)
- XP (.rxdata)
- 2000 / 2003 (.lsd)
- JSON / Web saves (.json)
"""
import sys
import io
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT_DIR))

from core.database_manager import GameDatabaseManager
from core.detector import detect_and_create_adapter
from core.mv_mz_adapter import MvMzAdapter
from core.ruby_adapter import RubyAdapter
from core.lsd_adapter import LsdAdapter, write_ber_int
from core.generic_adapter import GenericJsonAdapter

try:
    from rubymarshal.writer import writes as ruby_writes
    from rubymarshal.classes import RubyObject, Symbol
    _RUBY = True
except Exception:
    _RUBY = False


def test_mv_adapter_roundtrip():
    """Testa carregamento, edição e re-escrita de save real RPG Maker MV."""
    src = ROOT_DIR / "save" / "file2.rpgsave"
    assert src.exists()

    db = GameDatabaseManager()
    db.discover_and_load(src)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dst = Path(tmpdir) / "edited.rpgsave"

        adapter = MvMzAdapter(db)
        adapter.load(src)

        # 1. Checa ouro
        orig_gold = adapter.get_gold()
        adapter.set_gold(777888)
        assert adapter.get_gold() == 777888

        # 2. Checa ator
        actors = adapter.get_actors()
        assert len(actors) > 0
        first_actor = actors[0]
        adapter.update_actor(first_actor["id"], {"hp": 9999, "level": 99})

        # 3. Checa itens
        adapter.set_item_quantity("items", 116, 42)
        inv = adapter.get_inventory("items")
        item_116 = next((x for x in inv if str(x["id"]) == "116"), None)
        assert item_116 is not None
        assert item_116["quantity"] == 42

        # 4. Checa switch e variável
        adapter.set_switch(1, False)
        adapter.set_variable(2, 999)

        # 5. Salva e recarrega
        adapter.save(tmp_dst, backup=False)
        assert tmp_dst.exists()

        reloaded = MvMzAdapter(db)
        reloaded.load(tmp_dst)
        assert reloaded.get_gold() == 777888
        assert reloaded.get_actors()[0]["hp"] == 9999
        assert reloaded.get_actors()[0]["level"] == 99

        inv_reloaded = reloaded.get_inventory("items")
        reloaded_116 = next((x for x in inv_reloaded if str(x["id"]) == "116"), None)
        assert reloaded_116["quantity"] == 42
        assert reloaded.get_switches()[0]["value"] is False
        assert reloaded.get_variables()[1]["value"] == 999

    print("✔ test_mv_adapter_roundtrip passou com sucesso!")


def test_ruby_adapter_roundtrip():
    """Testa suporte a Ruby Marshal (.rvdata2, .rvdata, .rxdata)."""
    if not _RUBY:
        print("⚠ rubymarshal não disponível, pulando teste Ruby.")
        return

    # Constrói objetos simulados de RGSS
    party = RubyObject("Game_Party", {
        "@gold": 1500,
        "@items": {1: 5, 2: 10},
        "@weapons": {3: 1},
        "@armors": {4: 2},
        "@steps": 350
    })
    actor = RubyObject("Game_Actor", {
        "@actor_id": 1,
        "@name": "Eric",
        "@level": 5,
        "@hp": 450,
        "@maxhp": 450,
        "@mp": 100,
        "@maxmp": 100,
        "@atk": 35,
        "@def": 25
    })
    actors = RubyObject("Game_Actors", {
        "@data": [None, actor]
    })
    switches = RubyObject("Game_Switches", {
        "@data": [False, True, False, True]
    })
    variables = RubyObject("Game_Variables", {
        "@data": [0, 10, 20, 30]
    })

    save_payload = [party, actors, switches, variables]
    blob = ruby_writes(save_payload)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "Save01.rvdata2"
        test_file.write_bytes(blob)

        adapter = RubyAdapter()
        adapter.load(test_file)

        assert adapter.engine_name == "RPG Maker VX Ace"
        assert adapter.get_gold() == 1500

        # Modifica
        adapter.set_gold(99999)
        adapter.update_actor(1, {"hp": 9999, "level": 99})
        adapter.set_item_quantity("items", 1, 99)
        adapter.set_switch(2, True)
        adapter.set_variable(1, 888)

        # Salva
        edited_file = Path(tmpdir) / "Save01_edited.rvdata2"
        adapter.save(edited_file, backup=False)

        # Re-lê
        reloaded = RubyAdapter()
        reloaded.load(edited_file)
        assert reloaded.get_gold() == 99999
        assert reloaded.get_actors()[0]["hp"] == 9999
        assert reloaded.get_actors()[0]["level"] == 99
        assert reloaded.get_inventory("items")[0]["quantity"] == 99
        assert reloaded.get_switches()[1]["value"] is True
        assert reloaded.get_variables()[0]["value"] == 888

    print("✔ test_ruby_adapter_roundtrip passou com sucesso!")


def test_lsd_adapter_roundtrip():
    """Testa formato binário LcfSaveData de RPG Maker 2000/2003."""
    out = io.BytesIO()
    out.write(b"\x0bLcfSaveData")

    # Cria subchunk de ouro (id 0x15, valor 2500)
    sub = io.BytesIO()
    gold_bytes = (2500).to_bytes(4, "little")
    sub.write(write_ber_int(0x15))
    sub.write(write_ber_int(len(gold_bytes)))
    sub.write(gold_bytes)
    party_chunk_data = sub.getvalue()

    # Escreve chunk de Party (id 104)
    out.write(write_ber_int(104))
    out.write(write_ber_int(len(party_chunk_data)))
    out.write(party_chunk_data)

    payload = out.getvalue()

    with tempfile.TemporaryDirectory() as tmpdir:
        lsd_file = Path(tmpdir) / "Save01.lsd"
        lsd_file.write_bytes(payload)

        adapter = LsdAdapter()
        adapter.load(lsd_file)
        assert adapter.get_gold() == 2500

        # Altera ouro
        adapter.set_gold(88888)

        edited_lsd = Path(tmpdir) / "Save01_edited.lsd"
        adapter.save(edited_lsd, backup=False)

        reloaded = LsdAdapter()
        reloaded.load(edited_lsd)
        assert reloaded.get_gold() == 88888

    print("✔ test_lsd_adapter_roundtrip passou com sucesso!")


def test_generic_json_adapter():
    """Testa adaptador de JSON genérico."""
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "save.json"
        f.write_text('{"gold": 1234, "items": {"1": 10}, "switches": [false, true]}', encoding="utf-8")

        adapter = GenericJsonAdapter()
        adapter.load(f)
        assert adapter.get_gold() == 1234
        adapter.set_gold(5555)

        adapter.save(f, backup=False)
        reloaded = GenericJsonAdapter()
        reloaded.load(f)
        assert reloaded.get_gold() == 5555

    print("✔ test_generic_json_adapter passou com sucesso!")


def test_detector():
    """Testa detecção automática de formatos."""
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)

        p_mv = d / "test.rpgsave"
        p_mv.write_bytes(b'{"party": {"_gold": 100}}')
        a_mv = detect_and_create_adapter(p_mv)
        assert isinstance(a_mv, MvMzAdapter)

        p_mz = d / "test.rmmzsave"
        p_mz.write_bytes(b'{"party": {"_gold": 100}}')
        a_mz = detect_and_create_adapter(p_mz)
        assert isinstance(a_mz, MvMzAdapter)

        p_ace = d / "Save01.rvdata2"
        p_ace.write_bytes(b"\x04\x08[\x00")
        a_ace = detect_and_create_adapter(p_ace)
        assert isinstance(a_ace, RubyAdapter)

        p_lsd = d / "Save01.lsd"
        p_lsd.write_bytes(b"\x0bLcfSaveData\x00\x00")
        a_lsd = detect_and_create_adapter(p_lsd)
        assert isinstance(a_lsd, LsdAdapter)

    print("✔ test_detector passou com sucesso!")


if __name__ == "__main__":
    test_mv_adapter_roundtrip()
    test_ruby_adapter_roundtrip()
    test_lsd_adapter_roundtrip()
    test_generic_json_adapter()
    test_detector()
    print("\nTODOS OS TESTES DE FORMATO PASSARAM COM SUCESSO!")
