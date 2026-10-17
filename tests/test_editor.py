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
from core.generic_adapter import GenericJsonAdapter
from core.mv_mz_adapter import MvMzAdapter


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
    """Testa a lógica de navegação por caminho get_by_path / set_by_path usando BaseSaveAdapter."""
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

    adapter = GenericJsonAdapter()
    adapter.raw_data = sample

    assert adapter.get_by_path(["data", "party", "_gold"]) == 1234
    assert adapter.set_by_path(["data", "party", "_gold"], 9999) is True
    assert adapter.get_by_path(["data", "party", "_gold"]) == 9999

    hero = adapter.get_by_path(["data", "actors", "_data", "@a", 1])
    assert hero["_name"] == "Hero"
    assert hero["_level"] == 10

    print("✔ test_path_navigation_and_helpers passou com sucesso!")


def test_cli_export_import_roundtrip_subprocess():
    """Testa roundtrip de exportação e importação via subprocesso chamando main.py."""
    import subprocess
    fixture_rpgsave = ROOT_DIR / "tests" / "fixtures" / "file2.rpgsave"
    if not fixture_rpgsave.exists():
        fixture_rpgsave = ROOT_DIR / "save" / "file2.rpgsave"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        e_json = tmppath / "e.json"
        r_rpgsave = tmppath / "r.rpgsave"
        e2_json = tmppath / "e2.json"

        # 1. main.py export <fixture_rpgsave> e.json
        cmd1 = [sys.executable, str(ROOT_DIR / "main.py"), "export", str(fixture_rpgsave), str(e_json)]
        res1 = subprocess.run(cmd1, capture_output=True, text=True)
        assert res1.returncode == 0, f"Export 1 falhou: {res1.stderr}"
        assert e_json.exists()

        # 2. main.py import e.json r.rpgsave
        cmd2 = [sys.executable, str(ROOT_DIR / "main.py"), "import", str(e_json), str(r_rpgsave)]
        res2 = subprocess.run(cmd2, capture_output=True, text=True)
        assert res2.returncode == 0, f"Import falhou: {res2.stderr}"
        assert r_rpgsave.exists()

        # 3. main.py export r.rpgsave e2.json
        cmd3 = [sys.executable, str(ROOT_DIR / "main.py"), "export", str(r_rpgsave), str(e2_json)]
        res3 = subprocess.run(cmd3, capture_output=True, text=True)
        assert res3.returncode == 0, f"Export 2 falhou: {res3.stderr}"
        assert e2_json.exists()

        e1_data = json.loads(e_json.read_text(encoding="utf-8"))
        e2_data = json.loads(e2_json.read_text(encoding="utf-8"))
        assert e2_data["data"] == e1_data["data"], "Os dados exportados diferem após roundtrip!"

        # Verifica se party está no root de r.rpgsave quando carregado por MvMzAdapter
        adapter = MvMzAdapter()
        adapter.load(r_rpgsave)
        assert "party" in adapter.raw_data, "Chave 'party' não está no root do save reimportado!"
        print("✔ test_cli_export_import_roundtrip_subprocess passou com sucesso!")


if __name__ == "__main__":
    test_export_and_import_roundtrip()
    test_database_mappings_load()
    test_path_navigation_and_helpers()
    test_cli_export_import_roundtrip_subprocess()
    print("\nTODOS OS TESTES PASSARAM COM SUCESSO!")
