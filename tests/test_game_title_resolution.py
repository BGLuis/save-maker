#!/usr/bin/env python3
import pytest
from pathlib import Path
import json
from scripts.core.library_manager import (
    LibraryManager, resolve_game_title, clean_noisy_title, is_generic_or_save_name
)

def test_is_generic_or_save_name():
    assert is_generic_or_save_name("SaveData07") is True
    assert is_generic_or_save_name("SaveData02.sav") is True
    assert is_generic_or_save_name("file1") is True
    assert is_generic_or_save_name("slot2") is True
    assert is_generic_or_save_name("sample") is True
    assert is_generic_or_save_name("global") is True
    assert is_generic_or_save_name("save") is True
    assert is_generic_or_save_name("saves") is True
    assert is_generic_or_save_name("data") is True
    assert is_generic_or_save_name("") is True
    assert is_generic_or_save_name("Warrior Maiden Lecia and the Lost Fortress") is False
    assert is_generic_or_save_name("Final Fantasy VII") is False

def test_clean_noisy_title():
    raw_noisy = "v1.01 | TL: DazedAnon[Pular balão de fala: Z | Apagar mensagem: Shift | Pular texto: CTRL | Pendências: PageUp | Reiniciar: F5]"
    cleaned = clean_noisy_title(raw_noisy)
    # Como não há nome de jogo real nessa string, deve ficar vazia
    assert cleaned == ""

    with_name = "Dragon Quest Remake v1.01 [TL: TeamX]"
    assert clean_noisy_title(with_name) == "Dragon Quest Remake v1.01"

    with_controls = "Legend of Heroes | TL: Translators [Pular balão de fala: Z]"
    assert clean_noisy_title(with_controls) == "Legend of Heroes"

def test_resolve_game_title_wolf_rpg(tmp_path):
    # Simula o cenário relatado pelo usuário:
    # /caminho/Warrior Maiden Lecia and the Lost Fortress/Save/SaveData07.sav
    game_dir = tmp_path / "Warrior Maiden Lecia and the Lost Fortress"
    save_dir = game_dir / "Save"
    save_dir.mkdir(parents=True)
    save_file = save_dir / "SaveData07.sav"
    save_file.write_text("wolfsave")

    # Passando stem de save como raw_title deve rejeitar e usar o nome da pasta
    title1 = resolve_game_title(save_file, raw_title="SaveData07", engine="Wolf RPG Editor")
    assert title1 == "Warrior Maiden Lecia and the Lost Fortress"

    # Passando vazio deve usar o nome da pasta
    title2 = resolve_game_title(save_file, raw_title="", engine="Wolf RPG Editor")
    assert title2 == "Warrior Maiden Lecia and the Lost Fortress"

def test_resolve_game_title_game_ini(tmp_path):
    game_dir = tmp_path / "MyRpgGame"
    save_dir = game_dir / "save"
    save_dir.mkdir(parents=True)
    save_file = save_dir / "file1.rpgsave"
    save_file.write_text("save")

    ini_file = game_dir / "Game.ini"
    ini_file.write_text("[Game]\nTitle=Chronicles of Alda\nScripts=Data\\Scripts.rvdata2\n", encoding="utf-8")

    title = resolve_game_title(save_file, raw_title="", engine="RPG Maker VX Ace")
    assert title == "Chronicles of Alda"

def test_resolve_game_title_package_json(tmp_path):
    game_dir = tmp_path / "MyNwjsGame"
    save_dir = game_dir / "www" / "save"
    save_dir.mkdir(parents=True)
    save_file = save_dir / "file1.rpgsave"
    save_file.write_text("save")

    pkg_file = game_dir / "package.json"
    pkg_file.write_text(json.dumps({
        "name": "labyrinth_hero",
        "window": {"title": "Labyrinth Hero: Quest"}
    }), encoding="utf-8")

    title = resolve_game_title(save_file, raw_title="", engine="RPG Maker MV")
    assert title == "Labyrinth Hero: Quest"

def test_rename_game_persistence(tmp_path):
    cfg_file = tmp_path / "library.json"
    mgr = LibraryManager(config_file=cfg_file)

    game_dir = tmp_path / "CoolGame"
    save_dir = game_dir / "save"
    save_dir.mkdir(parents=True)
    save_file = save_dir / "file1.rpgsave"
    save_file.write_text("save")

    mgr.register_game(save_file, engine="RPG Maker MZ", title="Initial Name")
    mgr.add_recent_file(save_file, engine="RPG Maker MZ", title="Initial Name")

    # Renomeia
    success = mgr.rename_game(str(game_dir), "My Renamed Game")
    assert success is True

    games = mgr.get_games()
    assert games[0]["title"] == "My Renamed Game"
    assert games[0]["custom_title"] is True

    recents = mgr.get_recent_files()
    assert recents[0]["title"] == "My Renamed Game"

    # Novo scan não deve sobrescrever título customizado
    mgr.register_game(save_file, engine="RPG Maker MZ", title="Another Auto Name")
    games_after = mgr.get_games()
    assert games_after[0]["title"] == "My Renamed Game"

def test_auto_migration_of_corrupt_titles(tmp_path):
    cfg_file = tmp_path / "library.json"
    wolf_game_dir = tmp_path / "Warrior Maiden Lecia and the Lost Fortress"
    save_dir = wolf_game_dir / "Save"
    save_dir.mkdir(parents=True)
    save_file = save_dir / "SaveData07.sav"
    save_file.write_text("save")

    # Cria library.json pré-existente com títulos corrompidos
    pre_existing = {
        "recent_files": [
            {
                "path": str(save_file),
                "filename": "SaveData07.sav",
                "engine": "Wolf RPG Editor",
                "title": "SaveData07",
                "last_opened": 1000
            }
        ],
        "games": {
            str(wolf_game_dir): {
                "path": str(wolf_game_dir),
                "title": "SaveData07",
                "save_dir": str(save_dir),
                "engine": "Wolf RPG Editor",
                "last_opened": 1000
            }
        }
    }
    cfg_file.write_text(json.dumps(pre_existing), encoding="utf-8")

    # Ao carregar, o LibraryManager deve migrar automaticamente
    mgr = LibraryManager(config_file=cfg_file)
    games = mgr.get_games()
    assert games[0]["title"] == "Warrior Maiden Lecia and the Lost Fortress"

    recents = mgr.get_recent_files()
    assert recents[0]["title"] == "Warrior Maiden Lecia and the Lost Fortress"
