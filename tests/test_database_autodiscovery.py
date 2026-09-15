#!/usr/bin/env python3
"""
Testes automatizados para a Descoberta e Mapeamento Automático de Banco de Dados do Jogo
"""
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT_DIR))

from core.database_manager import GameDatabaseManager
from core.wolf_adapter import WolfAdapter, ByteWriter, _write_memdata, _encode_wolf_string


def test_automatic_database_discovery():
    """Testa se a descoberta automática a partir do caminho do save encontra a pasta data."""
    db = GameDatabaseManager()
    save_path = ROOT_DIR / "save" / "file2.rpgsave"
    assert save_path.exists(), f"Save de teste não encontrado: {save_path}"

    found = db.discover_and_load(save_path)
    assert found is True, "Falha na descoberta automática do banco de dados a partir do save"
    assert db.is_loaded() is True, "O banco de dados deveria estar marcado como carregado"

    # Validações de contagem
    assert len(db.items) > 0, "Deveria ter carregado itens"
    assert len(db.weapons) > 0, "Deveria ter carregado armas"
    assert len(db.armors) > 0, "Deveria ter carregado armaduras"
    assert len(db.actors) > 0, "Deveria ter carregado atores"
    assert len(db.switches) > 0, "Deveria ter carregado nomes de switches do System.json"
    assert len(db.variables) > 0, "Deveria ter carregado nomes de variáveis do System.json"

    print(f"✔ test_automatic_database_discovery passou: {db.summary_info()}")


def test_friendly_name_resolutions():
    """Valida se os IDs numéricos são resolvidos para nomes amigáveis em vez de números crus."""
    db = GameDatabaseManager()
    save_path = ROOT_DIR / "save" / "file2.rpgsave"
    db.discover_and_load(save_path)

    # Verifica nomes
    actor_1 = db.get_actor_name(1)
    assert actor_1 == "Himeno Iroha", f"Esperado 'Himeno Iroha', recebido '{actor_1}'"

    armor_1 = db.get_armor_name(1)
    assert "Nu(Normal)" in armor_1, f"Esperado 'Nu(Normal)', recebido '{armor_1}'"

    switch_1 = db.get_switch_name(1)
    assert "[システム]メッセージ表示" in switch_1, f"Nome da switch 1 incorreto: {switch_1}"

    curr = db.get_currency_unit()
    assert curr == "Yen", f"Unidade monetária esperada 'Yen', recebido '{curr}'"

    # Fallback para ID não existente
    fallback_item = db.get_item_name(999999)
    assert fallback_item == "Item #999999", f"Fallback incorreto: {fallback_item}"

    print("✔ test_friendly_name_resolutions passou com sucesso!")


def test_wolf_database_autodiscovery():
    """
    Testa a descoberta automática do schema Wolf RPG Editor (CDataBase.project) a partir do
    caminho convencional <GameDir>/Save/SaveDataNN.sav -> <GameDir>/Data/BasicData. Como não
    há jogo real do Wolf RPG Editor disponível, monta uma fixture sintética de diretório
    (save + CDataBase.project em texto puro) só para este teste.
    """
    with tempfile.TemporaryDirectory() as tmp:
        game_dir = Path(tmp) / "JogoWolfTeste"
        save_dir = game_dir / "Save"
        data_dir = game_dir / "Data" / "BasicData"
        save_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True)

        save_path = save_dir / "SaveData01.sav"
        WolfAdapter().save(save_path, backup=False)

        w = ByteWriter()
        w.u32(1)  # 1 tipo
        _write_memdata(w, _encode_wolf_string("Sistema", "utf-8"), 4)
        w.u32(1)  # 1 campo
        _write_memdata(w, _encode_wolf_string("Gold", "utf-8"), 4)
        w.u32(1)  # 1 linha de dados
        _write_memdata(w, _encode_wolf_string("Config", "utf-8"), 4)
        _write_memdata(w, b"\x00", 4)  # description vazia
        w.u32(1)  # fieldTypeListSize == fieldCount
        w.u8(1)
        w.u32(0); w.u32(0); w.u32(0); w.u32(0)
        (data_dir / "CDataBase.project").write_bytes(w.getvalue())

        db = GameDatabaseManager()
        found = db.discover_and_load(save_path)
        assert found is True, "Falha na descoberta automática do schema Wolf RPG Editor"
        assert 0 in db.wolf_types
        assert db.wolf_types[0]["name"] == "Sistema"
        assert db.wolf_types[0]["fields"][0]["name"] == "Gold"

    print("✔ test_wolf_database_autodiscovery passou com sucesso!")


if __name__ == "__main__":
    test_automatic_database_discovery()
    test_friendly_name_resolutions()
    test_wolf_database_autodiscovery()
    print("\nTODOS OS TESTES DE BANCO DE DADOS PASSARAM!")
