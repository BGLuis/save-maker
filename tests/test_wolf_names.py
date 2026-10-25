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


def test_wolf_v2_lz4_mt19937_v0x92_roundtrip_and_database_resolution(tmp_path):
    """Valida o container v2 (header[8]=0x02, LZ4 + MT19937), versão 0x92, campos placeholder (cfg=0),
    tradução em DataBase.dat sobrepondo rótulos CJK do DataBase.project, fusão de tabelas de ator,
    tempo de jogo, slots de equipamento e nomes de variáveis do SysDatabase.project."""
    dat_types = [
        (1, ["", "Lecia", "比較元装備用"]),
        (1, ["", "Poção Verde", "★フィールド素材"]),
    ]
    proj_types = [
        ("主人公グラフィック", "キャラ名", ["", "レイシア", "比較元装備用"]),
        ("アイテム", "名前", ["", "グリーンポーション", "★フィールド素材"]),
    ]
    (tmp_path / "DataBase.dat").write_bytes(build_dat(dat_types, encrypt=True))
    (tmp_path / "DataBase.project").write_bytes(build_project(proj_types))

    sys_types = [
        (f"Sys_{i}", "f", ["v0"]) for i in range(4)
    ] + [
        ("文字変数名", "f", ["Mensagem", "Nome Input"]),
    ] + [
        (f"Sys_{i}", "f", ["v0"]) for i in range(5, 14)
    ] + [
        ("通常変数名", "f", ["ID Personagem", "Dificuldade"]),
    ]
    (tmp_path / "SysDataBase.project").write_bytes(build_project(sys_types))

    db = GameDatabaseManager()
    db.wolf_types = {
        0: {
            "name": "主人公基礎ステータス",
            "fields": [{"index": 0, "name": "Lv"}, {"index": 1, "name": "獲得経験値"}, {"index": 2, "name": ""}],
            "rows": [{"index": 0, "name": ""}, {"index": 1, "name": ""}, {"index": 2, "name": "比較元装備用"}],
        },
        1: {
            "name": "主人公可変ステータス",
            "fields": [{"index": 0, "name": "HP"}, {"index": 1, "name": "最大HP"}, {"index": 2, "name": "攻撃力"}],
            "rows": [{"index": 0, "name": ""}, {"index": 1, "name": ""}, {"index": 2, "name": "比較元装備用"}],
        },
        2: {
            "name": "所持アイテム",
            "fields": [{"index": 0, "name": "所持数"}],
            "rows": [{"index": 0, "name": ""}, {"index": 1, "name": ""}, {"index": 2, "name": ""}],
        },
        3: {
            "name": "所持武器",
            "fields": [{"index": 0, "name": "名称(確認用)"}, {"index": 1, "name": "装備ID"}, {"index": 2, "name": "敵撃破数"}],
            "rows": [{"index": i, "name": ""} for i in range(20)],
        },
        4: {
            "name": "プレイ時間",
            "fields": [{"index": 0, "name": "秒"}, {"index": 1, "name": "分"}, {"index": 2, "name": "時"}],
            "rows": [{"index": 0, "name": ""}],
        },
    }
    db._load_wolf_fixed_database(tmp_path)

    adapter = WolfAdapter(db)
    adapter.header[0] = 0x12
    adapter.header[1] = 0x34
    adapter.header[5] = 0x56
    adapter.header[8] = 0x02  # Container v2 (LZ4 + MT19937)
    adapter.header[9] = 0x7A  # Semente do checksum16
    adapter.file_version = 0x92
    adapter.game_name = "Warrior Maiden Lecia"

    adapter.save_part2["var124"] = 1
    adapter.save_part2["mds3"] = [[b"test\x00"]]
    adapter.save_part3["var3"] = 1
    adapter.save_part3["vars4"] = [2]
    adapter.save_part3["vars5"] = [1, 3]
    adapter.save_part3["var4"] = 2
    adapter.save_part3["mds1New"] = ["Gigiiiii!".encode("utf-8") + b"\x00", b"\x00"]

    weapon_rows = [[{"id": 0, "type": 2, "string": b"\x00"}, {"id": 1, "type": 1, "number": 0}, {"id": 2, "type": 1, "number": 0}] for _ in range(20)]
    weapon_rows[1] = [{"id": 0, "type": 2, "string": "Estoc".encode("utf-8") + b"\x00"}, {"id": 1, "type": 1, "number": 10}, {"id": 2, "type": 1, "number": 45}]

    adapter.variable_database = {
        "unknown": 1,
        "typeCount": 5,
        "types": [
            {
                "unknown": -2, "dis": 0, "fieldCount": 3, "typeConfig": [1000, 1001, 0], "typeDataCount": 3,
                "rows": [
                    [{"id": 0, "type": 1, "number": 0}, {"id": 1, "type": 1, "number": 0}, {"id": 2, "type": 0}],
                    [{"id": 0, "type": 1, "number": 16}, {"id": 1, "type": 1, "number": 635}, {"id": 2, "type": 0}],
                    [{"id": 0, "type": 1, "number": 14}, {"id": 1, "type": 1, "number": 500}, {"id": 2, "type": 0}],
                ],
            },
            {
                "unknown": -2, "dis": 0, "fieldCount": 3, "typeConfig": [1000, 1001, 1002], "typeDataCount": 3,
                "rows": [
                    [{"id": 0, "type": 1, "number": 0}, {"id": 1, "type": 1, "number": 0}, {"id": 2, "type": 1, "number": 0}],
                    [{"id": 0, "type": 1, "number": 5110}, {"id": 1, "type": 1, "number": 5110}, {"id": 2, "type": 1, "number": 325}],
                    [{"id": 0, "type": 1, "number": 4864}, {"id": 1, "type": 1, "number": 4864}, {"id": 2, "type": 1, "number": 305}],
                ],
            },
            {
                "unknown": -2, "dis": 0, "fieldCount": 1, "typeConfig": [1000], "typeDataCount": 3,
                "rows": [
                    [{"id": 0, "type": 1, "number": 0}],
                    [{"id": 0, "type": 1, "number": 4}],
                    [{"id": 0, "type": 1, "number": 0}],
                ],
            },
            {
                "unknown": -2, "dis": 0, "fieldCount": 3, "typeConfig": [2000, 1000, 1001], "typeDataCount": 20,
                "rows": weapon_rows,
            },
            {
                "unknown": -2, "dis": 0, "fieldCount": 3, "typeConfig": [1000, 1001, 1002], "typeDataCount": 1,
                "rows": [[{"id": 0, "type": 1, "number": 33}, {"id": 1, "type": 1, "number": 3}, {"id": 2, "type": 1, "number": 2}]],
            },
        ],
    }

    sav_path = tmp_path / "SaveData10.sav"
    assert adapter.save(sav_path, backup=False)

    reloaded = WolfAdapter(db)
    reloaded.load(sav_path)
    assert reloaded.compression == "wolf_lz4_mt19937"
    assert reloaded.file_version == 0x92
    assert reloaded.get_playtime_and_steps() == ("02:03:33", 0)

    actors = reloaded.get_actors()
    assert len(actors) == 1
    assert actors[0]["name"] == "Lecia"
    assert actors[0]["level"] == 16
    assert actors[0]["exp"] == 635
    assert actors[0]["hp"] == 5110
    assert actors[0]["max_hp"] == 5110
    assert actors[0]["atk"] == 325

    items = reloaded.get_inventory("items")
    assert [(i["name"], i["quantity"]) for i in items if i["quantity"] > 0] == [("Poção Verde", 4)]

    weapons = reloaded.get_inventory("weapons")
    assert weapons == [{"id": "1", "name": "Estoc", "quantity": 1, "kind": "weapons"}]

    variables = reloaded.get_variables()
    assert [(v["name"], v["value"]) for v in variables] == [
        ("Mensagem", "Gigiiiii!"),
        ("Nome Input", ""),
        ("ID Personagem", 1),
        ("Dificuldade", 3),
    ]

