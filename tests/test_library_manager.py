#!/usr/bin/env python3
import pytest
from pathlib import Path
import json
import time
from scripts.core.library_manager import LibraryManager

def test_library_manager_recents(tmp_path):
    cfg_file = tmp_path / "library.json"
    mgr = LibraryManager(config_file=cfg_file)

    dummy_save1 = tmp_path / "file1.rpgsave"
    dummy_save1.write_text("dummy")

    dummy_save2 = tmp_path / "file2.rpgsave"
    dummy_save2.write_text("dummy")

    mgr.add_recent_file(dummy_save1, engine="RPG Maker MV", title="Jogo 1")
    mgr.add_recent_file(dummy_save2, engine="RPG Maker MZ", title="Jogo 2")

    recents = mgr.get_recent_files()
    assert len(recents) == 2
    assert recents[0]["filename"] == "file2.rpgsave"
    assert recents[0]["engine"] == "RPG Maker MZ"
    assert recents[0]["exists"] is True

    # Re-abrir save 1 deve colocá-lo no topo
    mgr.add_recent_file(dummy_save1, engine="RPG Maker MV", title="Jogo 1")
    recents_updated = mgr.get_recent_files()
    assert recents_updated[0]["filename"] == "file1.rpgsave"

def test_library_manager_game_registration_and_slots(tmp_path):
    cfg_file = tmp_path / "library.json"
    mgr = LibraryManager(config_file=cfg_file)

    game_dir = tmp_path / "MyGame"
    save_dir = game_dir / "www" / "save"
    save_dir.mkdir(parents=True)

    s1 = save_dir / "file1.rpgsave"
    s1.write_text("save1")
    s2 = save_dir / "file2.rpgsave"
    s2.write_text("save2")
    s2_bak = save_dir / "file2.rpgsave.bak"
    s2_bak.write_text("save2_bak")

    game_info = mgr.register_game(s1, engine="RPG Maker MV", title="My Game Title")
    assert game_info["title"] == "My Game Title"

    slots = mgr.scan_game_slots(game_dir, current_open_file=str(s1))
    assert len(slots) == 2

    slot1 = next(s for s in slots if s["filename"] == "file1.rpgsave")
    assert slot1["status"] == "Aberto agora"
    assert slot1["is_current"] is True

    slot2 = next(s for s in slots if s["filename"] == "file2.rpgsave")
    assert slot2["status"] == "Editado"
    assert slot2["has_backup"] is True

def test_library_manager_neighboring_games(tmp_path):
    cfg_file = tmp_path / "library.json"
    mgr = LibraryManager(config_file=cfg_file)

    root = tmp_path / "Games"
    game1 = root / "Game1"
    (game1 / "save").mkdir(parents=True)
    (game1 / "save" / "file1.rpgsave").write_text("s1")

    game2 = root / "Game2"
    (game2 / "save").mkdir(parents=True)
    (game2 / "save" / "file1.rpgsave").write_text("s2")

    mgr.register_game(game1 / "save" / "file1.rpgsave", title="Game 1")

    suggestions = mgr.discover_neighboring_games(game1)
    assert len(suggestions) == 1
    assert suggestions[0]["name"] == "Game2"
    assert suggestions[0]["saves_count"] == 1
