#!/usr/bin/env python3
"""
Testes automatizados para o Save Editor RPG Maker
"""
import sys
import json
import tempfile
from pathlib import Path

# Configura paths
ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT_DIR))

from export_rpgsave_to_json import export_rpgsave
from import_json_to_rpgsave import import_json


def test_export_and_import_roundtrip():
    """Testa exportação e importação de save MV real com LZString."""
    src_save = ROOT_DIR / "save" / "file2.rpgsave"
    assert src_save.exists(), f"Save de teste não encontrado: {src_save}"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        json_out = tmppath / "exported.json"
        save_reimported = tmppath / "reimported.rpgsave"
        json_reexported = tmppath / "reexported.json"

        # 1. Exporta save original
        export_rpgsave(src_save, json_out)
        assert json_out.exists(), "JSON não foi gerado"

        data_orig = json.loads(json_out.read_text(encoding="utf-8-sig"))
        assert data_orig.get("format") == "json", f"Formato inválido: {data_orig.get('format')}"
        assert "none+lzstring" in data_orig.get("compression"), f"Compressão inesperada: {data_orig.get('compression')}"
        assert "data" in data_orig, "Chave 'data' ausente"
        assert "_gold" in data_orig["data"]["party"], "Campo '_gold' ausente na party"

        # 2. Modifica valor e reimporta
        orig_gold = data_orig["data"]["party"]["_gold"]
        data_orig["data"]["party"]["_gold"] = 777888
        json_out.write_text(json.dumps(data_orig, ensure_ascii=False, indent=2), encoding="utf-8")

        import_json(json_out, save_reimported)
        assert save_reimported.exists(), "Save reimportado não foi gerado"

        # 3. Reexporta e valida modificação
        export_rpgsave(save_reimported, json_reexported)
        data_reexp = json.loads(json_reexported.read_text(encoding="utf-8-sig"))
        assert data_reexp["data"]["party"]["_gold"] == 777888, "O valor de gold modificado não bateu!"

        print("✔ test_export_and_import_roundtrip passou com sucesso!")


def test_database_mappings_load():
    """Testa o carregamento de mapeamento de nomes da pasta save/data/."""
    data_dir = ROOT_DIR / "save" / "data"
    assert data_dir.exists(), "Pasta save/data não encontrada"

    mapping_files = {
        'items': 'Items.json',
        'weapons': 'Weapons.json',
        'armors': 'Armors.json',
        'actors': 'Actors.json'
    }

    mappings = {}
    for kind, filename in mapping_files.items():
        fpath = data_dir / filename
        assert fpath.exists(), f"Arquivo {filename} não encontrado"
        data = json.loads(fpath.read_text(encoding="utf-8-sig"))
        mp = {}
        lst = data if isinstance(data, list) else data.get("data", [])
        for item in lst:
            if item and "id" in item and "name" in item:
                mp[str(item["id"])] = item["name"]
        mappings[kind] = mp
        assert len(mp) > 0, f"Mapeamento {kind} está vazio"

    print(f"✔ test_database_mappings_load carregou {len(mappings['items'])} itens, {len(mappings['weapons'])} armas, {len(mappings['armors'])} armaduras e {len(mappings['actors'])} atores!")


def test_path_navigation_and_helpers():
    """Testa a lógica de navegação por caminho get_by_path / set_by_path."""
    sample = {
        "data": {
            "party": {
                "_gold": 1234,
                "_items": {"1": 5, "@c": 10}
            },
            "actors": {
                "_data": {
                    "@a": [None, {"_actorId": 1, "_name": "Hero", "_level": 10}]
                }
            }
        }
    }

    # Simula get_by_path
    def get_by_path(root, path):
        cur = root
        for p in path:
            if isinstance(cur, dict): cur = cur.get(p)
            elif isinstance(cur, list): cur = cur[int(p)]
            else: return None
        return cur

    # Simula set_by_path
    def set_by_path(root, path, value):
        cur = root
        for i, p in enumerate(path):
            if i == len(path) - 1:
                if isinstance(cur, dict): cur[p] = value
                elif isinstance(cur, list): cur[int(p)] = value
                return True
            else:
                if isinstance(cur, dict): cur = cur[p]
                elif isinstance(cur, list): cur = cur[int(p)]
        return False

    assert get_by_path(sample, ["data", "party", "_gold"]) == 1234
    assert set_by_path(sample, ["data", "party", "_gold"], 9999) is True
    assert get_by_path(sample, ["data", "party", "_gold"]) == 9999

    hero = get_by_path(sample, ["data", "actors", "_data", "@a", 1])
    assert hero["_name"] == "Hero"
    assert hero["_level"] == 10

    print("✔ test_path_navigation_and_helpers passou com sucesso!")


if __name__ == "__main__":
    test_export_and_import_roundtrip()
    test_database_mappings_load()
    test_path_navigation_and_helpers()
    print("\nTODOS OS TESTES PASSARAM COM SUCESSO!")
