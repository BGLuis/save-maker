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
- Wolf RPG Editor (.sav) - experimental, ver ressalvas em test_wolf_adapter_roundtrip()
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
from core.wolf_adapter import WolfAdapter

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


def test_wolf_adapter_roundtrip():
    """
    Testa o adaptador experimental do Wolf RPG Editor (.sav) usando uma fixture sintética
    construída em memória pelo próprio teste (populando o WolfAdapter diretamente e chamando
    seu próprio save(), em vez de reimplementar a serialização aqui) - nenhum save real do
    Wolf RPG Editor está disponível para validação.

    Isto valida APENAS a consistência interna do adaptador (round-trip determinístico do
    formato que ele mesmo escreve/lê, incluindo marcadores 0x19 e checksum), NÃO a
    compatibilidade com o motor Wolf RPG Editor real - essa limitação é intencional e está
    documentada no módulo core/wolf_adapter.py.
    """

    class _StubDB:
        """Simula GameDatabaseManager.wolf_types sem depender do parser de .project (Marco 6),
        para testar a lógica de heurística (gold/actors/inventory) isoladamente."""
        wolf_types = {
            0: {
                "name": "Sistema",
                "fields": [{"index": 0, "name": "Gold"}, {"index": 1, "name": "Steps"}],
                "rows": [{"index": 0, "name": "Config"}],
            },
            1: {
                "name": "Characters",
                "fields": [{"index": 0, "name": "HP"}, {"index": 1, "name": "ATK"}],
                "rows": [{"index": 0, "name": "Herói Principal"}],
            },
            2: {
                "name": "Item List",
                "fields": [{"index": 0, "name": "Quantity"}],
                "rows": [{"index": 0, "name": "Poção"}],
            },
        }

    adapter = WolfAdapter()
    adapter.game_name = "Jogo de Teste Wolf RPG"

    # Popula SavePart3 com um grupo de variáveis inteiras e uma variável de texto
    adapter.save_part3["var2"] = 1
    adapter.save_part3["vars1"] = [1]
    adapter.save_part3["vars2"] = [3]
    adapter.save_part3["vars3"] = [10, 20, 30]
    adapter.save_part3["var4"] = 1
    adapter.save_part3["mds1New"] = ["Olá".encode("utf-8") + b"\x00"]

    # Popula VariableDatabase com 3 tipos: sistema (gold/steps), atores e itens
    adapter.variable_database = {
        "unknown": 0, "typeCount": 3,
        "types": [
            {"unknown": -1, "dis": 0, "fieldCount": 2, "typeConfig": [1, 1], "typeDataCount": 1,
             "rows": [[{"id": 0, "type": 1, "number": 500}, {"id": 1, "type": 1, "number": 120}]]},
            {"unknown": -1, "dis": 0, "fieldCount": 2, "typeConfig": [1, 1], "typeDataCount": 1,
             "rows": [[{"id": 0, "type": 1, "number": 350}, {"id": 1, "type": 1, "number": 20}]]},
            {"unknown": -1, "dis": 0, "fieldCount": 1, "typeConfig": [1], "typeDataCount": 1,
             "rows": [[{"id": 0, "type": 1, "number": 5}]]},
        ],
    }
    adapter.bind_database(_StubDB())

    with tempfile.TemporaryDirectory() as tmpdir:
        first_path = Path(tmpdir) / "SaveData01.sav"
        assert adapter.save(first_path, backup=False)

        # 1. Detecção estrutural (sem magic bytes - decripta e valida marcadores/checksum)
        detected = detect_and_create_adapter(first_path)
        assert isinstance(detected, WolfAdapter)

        # 2. Checa getters básicos
        assert adapter.get_gold() == 500
        assert adapter.get_playtime_and_steps() == ("N/A", 120)
        assert adapter.get_switches() == []  # sem suporte por design
        variables = adapter.get_variables()
        assert [v["value"] for v in variables] == [10, 20, 30, "Olá"]

        actors = adapter.get_actors()
        assert len(actors) == 1 and actors[0]["hp"] == 350 and actors[0]["atk"] == 20

        inventory = adapter.get_inventory("items")
        assert len(inventory) == 1 and inventory[0]["quantity"] == 5

        # 3. Muta via todos os setters relevantes
        assert adapter.set_gold(9999)
        assert adapter.set_variable(1, 777)
        assert adapter.set_variable(3, "Novo Texto")
        assert adapter.update_actor(0, {"hp": 999, "atk": 88})
        assert adapter.set_item_quantity("items", 0, 42)
        assert adapter.set_switch(0, True) is False  # confirma no-op documentado

        second_path = Path(tmpdir) / "SaveData02.sav"
        assert adapter.save(second_path, backup=False)

        # 4. Recarrega em instância nova e confirma que tudo persistiu
        reloaded = WolfAdapter()
        reloaded.bind_database(_StubDB())
        reloaded.load(second_path)

        assert reloaded.get_gold() == 9999
        reloaded_vars = reloaded.get_variables()
        assert reloaded_vars[1]["value"] == 777
        assert reloaded_vars[3]["value"] == "Novo Texto"
        assert reloaded.get_actors()[0]["hp"] == 999
        assert reloaded.get_actors()[0]["atk"] == 88
        assert reloaded.get_inventory("items")[0]["quantity"] == 42

        # 5. Sanidade estrutural pós-roundtrip: marcadores e checksum continuam válidos
        raw = second_path.read_bytes()
        from core.wolf_adapter import try_parse_wolf_header
        info = try_parse_wolf_header(raw)
        assert info is not None

    print("✔ test_wolf_adapter_roundtrip passou com sucesso! (fixture sintética - ver ressalvas no docstring)")


def test_wolf_version_gating_roundtrip():
    """Roundtrip byte-a-byte (sem mutação) em duas file_version diferentes, para pegar bugs
    de version-gating (ex: fork u16/u32 de string em SavePart3 na versão 0x6F)."""
    for version in (0x60, 0x8E):
        adapter = WolfAdapter()
        adapter.file_version = version
        from core.wolf_adapter import (_default_save_part1, _default_save_part2,
                                        _default_save_part3, _default_save_part4,
                                        _default_save_part5, _default_save_part7)
        adapter.save_part1 = _default_save_part1(version)
        adapter.save_part2 = _default_save_part2(version)
        adapter.save_part3 = _default_save_part3(version)
        adapter.save_part4 = _default_save_part4(version)
        adapter.save_part5 = _default_save_part5(version)
        adapter.save_part7 = _default_save_part7()

        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = Path(tmpdir) / "a.sav"
            p2 = Path(tmpdir) / "b.sav"
            adapter.save(p1, backup=False)

            reloaded = WolfAdapter()
            reloaded.load(p1)
            assert reloaded.file_version == version
            reloaded.save(p2, backup=False)

            assert p1.read_bytes() == p2.read_bytes(), f"roundtrip não é byte-exato para version=0x{version:x}"

    print("✔ test_wolf_version_gating_roundtrip passou com sucesso!")


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

        # Caso positivo Wolf RPG Editor: sem magic bytes, detecção puramente estrutural
        p_wolf = d / "SaveData01.sav"
        WolfAdapter().save(p_wolf, backup=False)
        a_wolf = detect_and_create_adapter(p_wolf)
        assert isinstance(a_wolf, WolfAdapter)

        # Caso negativo: um .sav que NÃO é Wolf RPG não pode ser misclassificado - deve cair
        # no fallback MV/MZ -> Generic já existente, sem quebrar a detecção de outros formatos
        p_fake_sav = d / "fake.sav"
        p_fake_sav.write_bytes(b'{"party": {"_gold": 100}}')
        a_fake = detect_and_create_adapter(p_fake_sav)
        assert not isinstance(a_fake, WolfAdapter)
        assert isinstance(a_fake, MvMzAdapter)

    print("✔ test_detector passou com sucesso!")


if __name__ == "__main__":
    test_mv_adapter_roundtrip()
    test_ruby_adapter_roundtrip()
    test_lsd_adapter_roundtrip()
    test_generic_json_adapter()
    test_wolf_adapter_roundtrip()
    test_wolf_version_gating_roundtrip()
    test_detector()
    print("\nTODOS OS TESTES DE FORMATO PASSARAM COM SUCESSO!")
