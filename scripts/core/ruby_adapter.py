#!/usr/bin/env python3
"""
RubyAdapter - Adaptador para Saves de RPG Maker VX Ace (.rvdata2), VX (.rvdata) e XP (.rxdata)

Utiliza a biblioteca rubymarshal para ler, decodificar, editar e re-serializar
os objetos de jogo nativos do RGSS (Game_Party, Game_Actors, Game_Switches, Game_Variables).
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_adapter import BaseSaveAdapter

try:
    from rubymarshal.classes import RubyObject, Symbol
    _RUBY_AVAILABLE = True
except Exception:
    RubyObject = None
    Symbol = None
    _RUBY_AVAILABLE = False

from .marshal_io import marshal_read_file, marshal_write_file, ruby_available


class RubyAdapter(BaseSaveAdapter):
    """Adaptador para arquivos de save do RPG Maker XP / VX / VX Ace baseados em Ruby Marshal."""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self._marshal_objects: list = []
        self.game_party_obj = None
        self.game_actors_obj = None
        self.game_switches_obj = None
        self.game_variables_obj = None
        self.game_system_obj = None

    def load(self, path: Path | str) -> Any:
        if not ruby_available():
            raise RuntimeError(
                "Biblioteca rubymarshal não está disponível no ambiente (pip install rubymarshal)"
            )

        self.file_path = Path(path).resolve()
        # Lê todos os objetos Marshal em sequência até EOF.
        # VX Ace / VX gravam 2 objetos; XP grava 12. ruby_load sozinho lê só o 1.º.
        self._marshal_objects = marshal_read_file(self.file_path)
        self.raw_data = self._marshal_objects  # preserva compatibilidade com get_by_path

        ext = self.file_path.suffix.lower()
        if ext == ".rvdata2":
            self.engine_name = "RPG Maker VX Ace"
        elif ext == ".rvdata":
            self.engine_name = "RPG Maker VX"
        elif ext == ".rxdata":
            self.engine_name = "RPG Maker XP"
        else:
            self.engine_name = "RPG Maker (Ruby Marshal)"

        self.compression = "ruby_marshal_4.8"
        self._locate_rgss_objects()
        self.clear_pending_changes()
        return self.raw_data

    def save(self, dst: Path | str, backup: bool = True) -> bool:
        if not ruby_available():
            raise RuntimeError("Biblioteca rubymarshal não está disponível")

        dst_path = Path(dst).resolve()
        if backup and dst_path.exists():
            self.create_backup_if_needed(dst_path)

        # Grava todos os objetos Marshal em sequência, preservando o formato original.
        # marshal_write_file lança ValueError se _marshal_objects estiver vazio.
        marshal_write_file(dst_path, self._marshal_objects)

        self.clear_pending_changes()
        return True

    def _locate_rgss_objects(self):
        """
        Varre todos os objetos Marshal lidos para localizar Game_Party, Game_Actors, etc.

        Cada objeto top-level em _marshal_objects pode ser:
          - RubyObject diretamente (ex.: Game_Party no XP, Game_System, cabeçalho)
          - dict/hash com valores RubyObject (ex.: make_save_contents no VX Ace)
          - list de RubyObjects (formato legado single-stream)
        """
        self.game_party_obj = None
        self.game_actors_obj = None
        self.game_switches_obj = None
        self.game_variables_obj = None
        self.game_system_obj = None

        def _assign(candidate) -> None:
            if candidate is None:
                return
            name = getattr(candidate, "ruby_class_name", "")
            if not name:
                return
            if "Game_Party" in name and self.game_party_obj is None:
                self.game_party_obj = candidate
            elif "Game_Actors" in name and self.game_actors_obj is None:
                self.game_actors_obj = candidate
            elif "Game_Switches" in name and self.game_switches_obj is None:
                self.game_switches_obj = candidate
            elif "Game_Variables" in name and self.game_variables_obj is None:
                self.game_variables_obj = candidate
            elif "Game_System" in name and self.game_system_obj is None:
                self.game_system_obj = candidate

        def _scan(top) -> None:
            if isinstance(top, dict):
                for v in top.values():
                    _assign(v)
            elif isinstance(top, list):
                for item in top:
                    _assign(item)
            else:
                _assign(top)

        for obj in self._marshal_objects:
            _scan(obj)

    def _get_attr(self, obj: Any, key: str, default: Any = None) -> Any:
        if obj is None or not hasattr(obj, "attributes"):
            return default
        attrs = obj.attributes
        # Tenta com '@' e sem '@', ou via Symbol
        cand_keys = [f"@{key.lstrip('@')}", key.lstrip("@")]
        for k in cand_keys:
            if k in attrs:
                return attrs[k]
        return default

    def _set_attr(self, obj: Any, key: str, value: Any) -> bool:
        if obj is None or not hasattr(obj, "attributes"):
            return False
        k = f"@{key.lstrip('@')}"
        obj.attributes[k] = value
        return True

    # --- Ouro e Geral ---

    def get_gold(self) -> int:
        if self.game_party_obj:
            return int(self._get_attr(self.game_party_obj, "gold", 0))
        return 0

    def set_gold(self, amount: int) -> bool:
        if self.game_party_obj:
            val = max(0, int(amount))
            self._set_attr(self.game_party_obj, "gold", val)
            self.mark_dirty(f"Ouro definido para {val:,}")
            return True
        return False

    def get_playtime_and_steps(self) -> Tuple[str, int]:
        steps = 0
        if self.game_party_obj:
            steps = int(self._get_attr(self.game_party_obj, "steps", 0))

        playtime = "Desconhecido"
        if self.game_system_obj:
            timer = self._get_attr(self.game_system_obj, "timer", 0)
            if timer:
                mins = timer // 60
                secs = timer % 60
                playtime = f"{mins:02d}:{secs:02d}"

        return playtime, steps

    # --- Atores ---

    def get_actors(self) -> List[Dict[str, Any]]:
        results = []
        if not self.game_actors_obj:
            return results

        data_list = self._get_attr(self.game_actors_obj, "data", [])
        if isinstance(data_list, dict):
            data_list = list(data_list.values())

        if isinstance(data_list, list):
            for idx, act in enumerate(data_list):
                if act is None:
                    continue
                aid = self._get_attr(act, "actor_id", idx)
                name = self._get_attr(act, "name")
                if not name and self.db:
                    name = self.db.get_actor_name(aid)
                if not name:
                    name = f"Ator #{aid}"

                lvl = self._get_attr(act, "level", 1)
                hp = self._get_attr(act, "hp", 0)
                max_hp = self._get_attr(act, "maxhp", hp)
                mp = self._get_attr(act, "mp") or self._get_attr(act, "sp", 0)
                max_mp = self._get_attr(act, "maxmp") or self._get_attr(act, "maxsp", mp)

                results.append({
                    "id": aid,
                    "name": name,
                    "level": lvl,
                    "hp": hp,
                    "max_hp": max_hp,
                    "mp": mp,
                    "max_mp": max_mp,
                    "tp": self._get_attr(act, "tp", 0),
                    "atk": self._get_attr(act, "atk", 0),
                    "def": self._get_attr(act, "def", 0),
                    "mat": self._get_attr(act, "spi") or self._get_attr(act, "mat", 0),
                    "mdf": self._get_attr(act, "mdf", 0),
                    "agi": self._get_attr(act, "agi", 0),
                    "luk": self._get_attr(act, "luk", 0),
                    "exp": self._get_attr(act, "exp", 0),
                    "raw": act
                })
        return results

    def update_actor(self, actor_id: int | str, stats: Dict[str, Any]) -> bool:
        actors = self.get_actors()
        for a in actors:
            if str(a["id"]) == str(actor_id):
                act_raw = a["raw"]
                if "level" in stats:
                    self._set_attr(act_raw, "level", int(stats["level"]))
                if "hp" in stats:
                    self._set_attr(act_raw, "hp", int(stats["hp"]))
                if "max_hp" in stats:
                    self._set_attr(act_raw, "maxhp", int(stats["max_hp"]))
                if "mp" in stats:
                    self._set_attr(act_raw, "mp", int(stats["mp"]))
                    self._set_attr(act_raw, "sp", int(stats["mp"]))
                if "max_mp" in stats:
                    self._set_attr(act_raw, "maxmp", int(stats["max_mp"]))
                    self._set_attr(act_raw, "maxsp", int(stats["max_mp"]))
                if "tp" in stats:
                    self._set_attr(act_raw, "tp", int(stats["tp"]))

                self.mark_dirty(f"Ator {a['name']} atualizado")
                return True
        return False

    # --- Inventário ---

    def get_inventory(self, kind: str = "items") -> List[Dict[str, Any]]:
        results = []
        if not self.game_party_obj:
            return results

        attr_key = f"@{kind}"
        inv_dict = self._get_attr(self.game_party_obj, kind, {})

        if isinstance(inv_dict, dict):
            for k, qty in inv_dict.items():
                name = None
                if self.db:
                    if kind == "items": name = self.db.get_item_name(k)
                    elif kind == "weapons": name = self.db.get_weapon_name(k)
                    elif kind == "armors": name = self.db.get_armor_name(k)
                if not name:
                    name = f"{kind.capitalize()} #{k}"

                results.append({
                    "id": str(k),
                    "name": name,
                    "quantity": int(qty),
                    "kind": kind
                })
        return sorted(results, key=lambda x: int(x["id"]) if x["id"].isdigit() else str(x["id"]))

    def set_item_quantity(self, kind: str, item_id: int | str, qty: int) -> bool:
        if not self.game_party_obj:
            return False

        inv_dict = self._get_attr(self.game_party_obj, kind)
        if inv_dict is None or not isinstance(inv_dict, dict):
            inv_dict = {}
            self._set_attr(self.game_party_obj, kind, inv_dict)

        try:
            k_id = int(item_id)
        except Exception:
            k_id = str(item_id)

        if qty <= 0:
            inv_dict.pop(k_id, None)
            inv_dict.pop(str(k_id), None)
            self.mark_dirty(f"Item {item_id} ({kind}) removido")
        else:
            inv_dict[k_id] = int(qty)
            self.mark_dirty(f"Item {item_id} ({kind}) definido para {qty}")
        return True

    def unlock_all_items(self, kind: str = "items", qty: int = 99) -> int:
        if not self.game_party_obj:
            return 0

        inv_dict = self._get_attr(self.game_party_obj, kind)
        if inv_dict is None or not isinstance(inv_dict, dict):
            inv_dict = {}
            self._set_attr(self.game_party_obj, kind, inv_dict)

        count = 0
        if self.db:
            source = []
            if kind == "items": source = self.db.get_all_known_items()
            elif kind == "weapons": source = self.db.get_all_known_weapons()
            elif kind == "armors": source = self.db.get_all_known_armors()

            for entry in source:
                try:
                    i_id = int(entry["id"])
                except Exception:
                    i_id = str(entry["id"])
                inv_dict[i_id] = qty
                count += 1
        else:
            for k in list(inv_dict.keys()):
                inv_dict[k] = qty
                count += 1

        self.mark_dirty(f"{count} {kind} atualizados para x{qty}")
        return count

    # --- Switches e Variáveis ---

    def get_switches(self) -> List[Dict[str, Any]]:
        results = []
        if not self.game_switches_obj:
            return results

        data = self._get_attr(self.game_switches_obj, "data", [])
        if isinstance(data, list):
            for idx, val in enumerate(data):
                if idx == 0: continue
                name = self.db.get_switch_name(idx) if self.db else None
                results.append({
                    "id": idx,
                    "name": name or f"Switch #{idx}",
                    "value": bool(val)
                })
        return sorted(results, key=lambda x: x["id"])

    def set_switch(self, switch_id: int, state: bool) -> bool:
        if not self.game_switches_obj:
            return False

        data = self._get_attr(self.game_switches_obj, "data")
        if data is None or not isinstance(data, list):
            data = []
            self._set_attr(self.game_switches_obj, "data", data)

        idx = int(switch_id)
        while len(data) <= idx:
            data.append(False)
        data[idx] = bool(state)

        name = self.db.get_switch_name(idx) if self.db else f"Switch #{idx}"
        self.mark_dirty(f"{name} -> {'ON' if state else 'OFF'}")
        return True

    def get_variables(self) -> List[Dict[str, Any]]:
        results = []
        if not self.game_variables_obj:
            return results

        data = self._get_attr(self.game_variables_obj, "data", [])
        if isinstance(data, list):
            for idx, val in enumerate(data):
                if idx == 0: continue
                name = self.db.get_variable_name(idx) if self.db else None
                results.append({
                    "id": idx,
                    "name": name or f"Variável #{idx}",
                    "value": val
                })
        return sorted(results, key=lambda x: x["id"])

    def set_variable(self, var_id: int, value: Any) -> bool:
        if not self.game_variables_obj:
            return False

        data = self._get_attr(self.game_variables_obj, "data")
        if data is None or not isinstance(data, list):
            data = []
            self._set_attr(self.game_variables_obj, "data", data)

        idx = int(var_id)
        try:
            val_to_set = int(value)
        except Exception:
            val_to_set = value

        while len(data) <= idx:
            data.append(0)
        data[idx] = val_to_set

        name = self.db.get_variable_name(idx) if self.db else f"Variável #{idx}"
        self.mark_dirty(f"{name} -> {val_to_set}")
        return True
