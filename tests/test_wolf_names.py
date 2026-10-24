#!/usr/bin/env python3
"""Nomes de itens/armas/armaduras do Wolf RPG vindos de DataBase.dat (o save só guarda quantidades)."""
import json
import struct
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR))

from core.database_manager import GameDatabaseManager
from core.wolf_adapter import WolfAdapter, _lcg_byte_stream
from core.wolf_database import parse_wolf_fixed_database


def _s(text: str) -> bytes:
    raw = text.encode("utf-8") + b"\x00"
    return struct.pack("<I", len(raw)) + raw


def _encrypt_dat(plain: bytes) -> bytes:
    """Inverso de _xor_crypt(start=0). O arquivo cifrado guarda as próprias sementes nos bytes
    0, 3 e 9, então procuramos (byte de versão, semente0) para os quais as três sementes
    derivadas do texto puro coincidam com os bytes resultantes."""
    def xor_pass(buf, seed, stride):
        gen = _lcg_byte_stream(seed)
        for i in range(0, len(buf), stride):
            buf[i] ^= next(gen)

    leading = 1 if plain[0] == 0 else 0
    version_idx = leading + 9
    for version in range(256):
        base = bytearray(plain)
        base[version_idx] = version
        for s0 in range(256):
            head = bytearray(base[:10 + leading])
            xor_pass(head, s0, 1)
            s1, s2 = head[3], head[9]
            buf = bytearray(base)
            for seed, stride in ((s0, 1), (s1, 2), (s2, 5)):
                xor_pass(buf, seed, stride)
            if (buf[0], buf[3], buf[9]) == (s0, s1, s2):
                return bytes(buf)
    raise AssertionError("sem sementes consistentes para a fixture")


def build_dat(types, encrypt=False, leading_zero=False) -> bytes:
    """types: [(n_int_fields, [nome_da_linha, ...]), ...]; cada linha tem 1 campo de texto."""
    out = (b"\x00" if leading_zero else b"") + b"W\x00\x00OL" + b"\x55" + b"FM\x00" + b"\x6d"
    out += struct.pack("<I", len(types))
    for n_ints, names in types:
        out += b"\xfe\xff\xff\xff" + struct.pack("<I", 0)
        infos = [1000 + i for i in range(n_ints)] + [2000]
        out += struct.pack("<I", len(infos)) + b"".join(struct.pack("<I", i) for i in infos)
        out += struct.pack("<I", len(names))
        for name in names:
            out += b"".join(struct.pack("<I", 7) for _ in range(n_ints)) + _s(name)
    out += b"\xc3"
    return _encrypt_dat(out) if encrypt else out


def build_project(types) -> bytes:
    """types: [(nome_do_tipo, nome_do_campo, [nome_da_linha, ...]), ...] em texto puro."""
    out = struct.pack("<I", len(types))
    for tname, fname, rows in types:
        out += _s(tname) + struct.pack("<I", 1) + _s(fname)
        out += struct.pack("<I", len(rows)) + b"".join(_s(r) for r in rows) + _s("")
        out += struct.pack("<I", 1) + b"\x00" + struct.pack("<IIII", 0, 0, 0, 0)
    return out


DAT_TYPES = [(1, ["x"]), (1, ["x"]), (2, ["Poção", "Elixir"]), (2, ["Espada"]), (2, ["Escudo", "Manto"])]
PROJECT_TYPES = [
    ("Sys", "f", ["a"]), ("Sys2", "f", ["a"]),
    ("Items", "f", ["", ""]), ("Weapons", "f", ["Blade"]), ("Armors", "f", ["", ""]),
]


def test_dat_names_match_in_clear_and_encrypted(tmp_path):
    (tmp_path / "plain.dat").write_bytes(build_dat(DAT_TYPES))
    (tmp_path / "enc.dat").write_bytes(build_dat(DAT_TYPES, encrypt=True))
    (tmp_path / "zero.dat").write_bytes(build_dat(DAT_TYPES, leading_zero=True))
    plain, enc, zero = (parse_wolf_fixed_database(tmp_path / f"{n}.dat") for n in ("plain", "enc", "zero"))
    assert plain == enc == zero
    assert plain[2]["rows"] == ["Poção", "Elixir"]


def test_project_row_name_wins_and_dat_fills_blanks(tmp_path):
    (tmp_path / "DataBase.dat").write_bytes(build_dat(DAT_TYPES, encrypt=True))
    (tmp_path / "DataBase.project").write_bytes(build_project(PROJECT_TYPES))
    result = parse_wolf_fixed_database(tmp_path / "DataBase.dat", tmp_path / "DataBase.project")
    assert [t["name"] for t in result][2:] == ["Items", "Weapons", "Armors"]
    assert result[2]["rows"] == ["Poção", "Elixir"]
    assert result[3]["rows"] == ["Blade"]


def _manager(tmp_path, name_map=None) -> GameDatabaseManager:
    (tmp_path / "DataBase.dat").write_bytes(build_dat(DAT_TYPES, encrypt=True))
    (tmp_path / "DataBase.project").write_bytes(build_project(PROJECT_TYPES))
    if name_map is not None:
        (tmp_path / "wolf_name_map.json").write_text(json.dumps(name_map))
    db = GameDatabaseManager()
    db._load_wolf_fixed_database(tmp_path)
    return db


def test_heuristic_pairs_save_type_with_database_by_category(tmp_path):
    db = _manager(tmp_path)
    assert db.resolve_wolf_row_names(7, "items") == ["Poção", "Elixir"]
    assert db.resolve_wolf_row_names(8, "weapons") == ["Blade"]
    assert db.resolve_wolf_row_names(9, "armors") == ["Escudo", "Manto"]


def test_name_map_overrides_heuristic(tmp_path):
    db = _manager(tmp_path, {"7": 4})
    assert db.resolve_wolf_row_names(7, "items") == ["Escudo", "Manto"]


def test_inventory_uses_database_names_and_falls_back_without_them(tmp_path):
    class Db:
        wolf_types = {7: {"name": "Item List", "fields": [{"index": 0, "name": "Quantity"}],
                          "rows": [{"index": 0, "name": ""}, {"index": 1, "name": ""}]}}

        def __init__(self, names):
            self.names = names

        def resolve_wolf_row_names(self, type_idx, kind):
            return self.names

    adapter = WolfAdapter()
    adapter.variable_database = {"types": [{"rows": []}] * 7 + [{"rows": [
        [{"id": 0, "type": 1, "number": 3}], [{"id": 0, "type": 1, "number": 9}]]}]}

    adapter.bind_database(Db(["Poção", "Elixir"]))
    inv = adapter.get_inventory("items")
    assert [(i["name"], i["quantity"]) for i in inv] == [("Poção", 3), ("Elixir", 9)]

    adapter.bind_database(Db([]))
    assert [i["name"] for i in adapter.get_inventory("items")] == ["items #0", "items #1"]
