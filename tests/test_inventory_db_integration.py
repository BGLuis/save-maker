#!/usr/bin/env python3
"""
Testes de integração para exibição e edição de inventário com banco de dados.
Valida o suporte a include_all_db, inclusão de itens com quantidade 0,
persistência no save e a ação de Completar com BD.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT_DIR))

from core.database_manager import GameDatabaseManager
from core.mv_mz_adapter import MvMzAdapter
from core.ruby_adapter import RubyAdapter
from core.lsd_adapter import LsdAdapter
from core.generic_adapter import GenericJsonAdapter


class MockDb:
    def __init__(self):
        self.items = {
            "1": {"id": 1, "name": "Poção", "description": "Cura 500 HP"},
            "2": {"id": 2, "name": "Super Poção", "description": "Cura 2000 HP"},
            "3": {"id": 3, "name": "Elixir", "description": "Cura tudo"},
            "4": {"id": 4, "name": "", "description": "Vazio"},  # Slot sem nome
        }
        self.weapons = {
            "10": {"id": 10, "name": "Espada de Ferro"},
            "11": {"id": 11, "name": "Espada Longa"}
        }
        self.armors = {
            "20": {"id": 20, "name": "Escudo de Madeira"}
        }

    def is_loaded(self):
        return True

    def get_all_known_items(self):
        return list(self.items.values())

    def get_all_known_weapons(self):
        return list(self.weapons.values())

    def get_all_known_armors(self):
        return list(self.armors.values())

    def get_item_name(self, i_id, default=None):
        s = str(i_id)
        if s in self.items and self.items[s].get("name"):
            return self.items[s]["name"]
        return default or f"Item #{s}"

    def get_weapon_name(self, w_id, default=None):
        s = str(w_id)
        if s in self.weapons and self.weapons[s].get("name"):
            return self.weapons[s]["name"]
        return default or f"Arma #{s}"

    def get_armor_name(self, a_id, default=None):
        s = str(a_id)
        if s in self.armors and self.armors[s].get("name"):
            return self.armors[s]["name"]
        return default or f"Armadura #{s}"


def test_mv_mz_inventory_include_all_db():
    db = MockDb()
    adapter = MvMzAdapter(db)
    # Save com apenas o item 1 (Poção x3)
    adapter.raw_data = {
        "party": {
            "_items": {"1": 3},
            "_weapons": {},
            "_armors": {}
        }
    }

    # 1. Com include_all_db=False (padrão): apenas itens no save
    owned_items = adapter.get_inventory("items", include_all_db=False)
    assert len(owned_items) == 1
    assert owned_items[0]["id"] == "1"
    assert owned_items[0]["name"] == "Poção"
    assert owned_items[0]["quantity"] == 3
    assert "in_save" not in owned_items[0]  # Garante retrocompatibilidade

    # 2. Com include_all_db=True: traz também itens do BD com quantidade 0
    all_items = adapter.get_inventory("items", include_all_db=True)
    # Deve conter itens 1, 2 e 3 (o item 4 sem nome é filtrado)
    assert len(all_items) == 3

    item1 = next(x for x in all_items if x["id"] == "1")
    assert item1["name"] == "Poção"
    assert item1["quantity"] == 3
    assert item1["in_save"] is True

    item2 = next(x for x in all_items if x["id"] == "2")
    assert item2["name"] == "Super Poção"
    assert item2["quantity"] == 0
    assert item2["in_save"] is False

    item3 = next(x for x in all_items if x["id"] == "3")
    assert item3["name"] == "Elixir"
    assert item3["quantity"] == 0
    assert item3["in_save"] is False


def test_set_quantity_on_unowned_item():
    db = MockDb()
    adapter = MvMzAdapter(db)
    adapter.raw_data = {
        "party": {
            "_items": {"1": 3},
            "_weapons": {},
            "_armors": {}
        }
    }

    # Altera Super Poção (ID 2, que antes não estava no save) para x5
    assert "2" not in adapter.raw_data["party"]["_items"]
    adapter.set_item_quantity("items", 2, 5)
    assert adapter.raw_data["party"]["_items"]["2"] == 5

    # Agora deve aparecer em include_all_db=False
    owned = adapter.get_inventory("items", include_all_db=False)
    assert any(x["id"] == "2" and x["quantity"] == 5 for x in owned)

    # Zera Super Poção -> deve ser removida do dicionário do save
    adapter.set_item_quantity("items", 2, 0)
    assert "2" not in adapter.raw_data["party"]["_items"]

    # Mas em include_all_db=True ela continua visível com quantidade 0
    all_items = adapter.get_inventory("items", include_all_db=True)
    item2 = next(x for x in all_items if x["id"] == "2")
    assert item2["quantity"] == 0
    assert item2["in_save"] is False


def test_unlock_all_items_with_db():
    db = MockDb()
    adapter = MvMzAdapter(db)
    adapter.raw_data = {
        "party": {
            "_items": {},
            "_weapons": {},
            "_armors": {}
        }
    }

    count = adapter.unlock_all_items("items", 99)
    # Desbloqueou os itens válidos
    assert count >= 3
    assert adapter.raw_data["party"]["_items"]["1"] == 99
    assert adapter.raw_data["party"]["_items"]["2"] == 99
    assert adapter.raw_data["party"]["_items"]["3"] == 99


def test_generic_adapter_include_all_db():
    db = MockDb()
    adapter = GenericJsonAdapter(db)
    adapter.raw_data = {
        "items": {"1": 10}
    }

    owned = adapter.get_inventory("items", include_all_db=False)
    assert len(owned) == 1
    assert owned[0]["id"] == "1"

    all_items = adapter.get_inventory("items", include_all_db=True)
    assert len(all_items) == 3
    assert any(x["id"] == "2" and x["quantity"] == 0 for x in all_items)
