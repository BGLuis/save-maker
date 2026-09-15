#!/usr/bin/env python3
"""
GenericJsonAdapter - Adaptador para Saves Genéricos, Web Saves e JSON Descriptografados

Suporta arquivos .json, .sav, .dat e .txt com conteúdo JSON ou dicionário chave-valor.
"""

from __future__ import annotations
import json
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_adapter import BaseSaveAdapter


class GenericJsonAdapter(BaseSaveAdapter):
    """Adaptador para arquivos JSON puros ou serializações genéricas."""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self.engine_name = "JSON / Generic Save"
        self.compression = "none"

    def load(self, path: Path | str) -> Any:
        self.file_path = Path(path).resolve()
        raw_text = self.file_path.read_text(encoding="utf-8-sig")

        try:
            self.raw_data = json.loads(raw_text)
        except Exception:
            # Tenta decodificar base64 se falhar
            try:
                decoded = base64.b64decode(raw_text.strip()).decode("utf-8")
                self.raw_data = json.loads(decoded)
                self.compression = "base64"
            except Exception as e:
                raise ValueError(f"Não foi possível interpretar o arquivo como JSON: {e}")

        self.clear_pending_changes()
        return self.raw_data

    def save(self, dst: Path | str, backup: bool = True) -> bool:
        dst_path = Path(dst).resolve()
        if backup and dst_path.exists():
            self.create_backup_if_needed(dst_path)

        text = json.dumps(self.raw_data, ensure_ascii=False, indent=2)
        if self.compression == "base64":
            payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
        else:
            payload = text

        dst_path.write_text(payload, encoding="utf-8")
        self.clear_pending_changes()
        return True

    def get_gold(self) -> int:
        if isinstance(self.raw_data, dict):
            # Tenta chaves comuns de ouro
            for k in ("_gold", "gold", "money", "credits", "coins"):
                if k in self.raw_data:
                    return int(self.raw_data[k])
            # Ou dentro de party
            if "party" in self.raw_data and isinstance(self.raw_data["party"], dict):
                return int(self.raw_data["party"].get("_gold", self.raw_data["party"].get("gold", 0)))
        return 0

    def set_gold(self, amount: int) -> bool:
        if isinstance(self.raw_data, dict):
            val = max(0, int(amount))
            for k in ("_gold", "gold", "money", "credits", "coins"):
                if k in self.raw_data:
                    self.raw_data[k] = val
                    self.mark_dirty(f"Ouro definido para {val:,}")
                    return True
            if "party" in self.raw_data and isinstance(self.raw_data["party"], dict):
                self.raw_data["party"]["_gold"] = val
                self.mark_dirty(f"Ouro definido para {val:,}")
                return True
            # Se não achou, define 'gold'
            self.raw_data["gold"] = val
            self.mark_dirty(f"Ouro definido para {val:,}")
            return True
        return False

    def get_playtime_and_steps(self) -> Tuple[str, int]:
        return "N/A", 0

    def get_actors(self) -> List[Dict[str, Any]]:
        results = []
        if isinstance(self.raw_data, dict) and "actors" in self.raw_data:
            act_data = self.raw_data["actors"]
            lst = act_data if isinstance(act_data, list) else list(act_data.values())
            for idx, a in enumerate(lst):
                if isinstance(a, dict):
                    aid = a.get("id", a.get("_actorId", idx))
                    name = a.get("name", a.get("_name", f"Ator #{aid}"))
                    results.append({
                        "id": aid,
                        "name": name,
                        "level": a.get("level", a.get("_level", 1)),
                        "hp": a.get("hp", a.get("_hp", 100)),
                        "max_hp": a.get("max_hp", a.get("_max_hp", 100)),
                        "mp": a.get("mp", a.get("_mp", 50)),
                        "max_mp": a.get("max_mp", a.get("_max_mp", 50)),
                        "tp": a.get("tp", a.get("_tp", 0)),
                        "atk": a.get("atk", 10),
                        "def": a.get("def", 10),
                        "mat": a.get("mat", 10),
                        "mdf": a.get("mdf", 10),
                        "agi": a.get("agi", 10),
                        "luk": a.get("luk", 10),
                        "exp": a.get("exp", 0),
                        "raw": a
                    })
        return results

    def update_actor(self, actor_id: int | str, stats: Dict[str, Any]) -> bool:
        actors = self.get_actors()
        for a in actors:
            if str(a["id"]) == str(actor_id):
                act_raw = a["raw"]
                for k, v in stats.items():
                    act_raw[k] = v
                    act_raw[f"_{k}"] = v
                self.mark_dirty(f"Ator {a['name']} atualizado")
                return True
        return False

    def get_inventory(self, kind: str = "items") -> List[Dict[str, Any]]:
        results = []
        if isinstance(self.raw_data, dict):
            inv = self.raw_data.get(kind, self.raw_data.get(f"_{kind}", {}))
            if isinstance(inv, dict):
                for k, qty in inv.items():
                    results.append({
                        "id": str(k),
                        "name": self.db.get_item_name(k) if self.db else f"{kind.capitalize()} #{k}",
                        "quantity": int(qty),
                        "kind": kind
                    })
        return sorted(results, key=lambda x: str(x["id"]))

    def set_item_quantity(self, kind: str, item_id: int | str, qty: int) -> bool:
        if isinstance(self.raw_data, dict):
            inv = self.raw_data.setdefault(kind, {})
            if qty <= 0:
                inv.pop(str(item_id), None)
            else:
                inv[str(item_id)] = int(qty)
            self.mark_dirty(f"Item {item_id} ({kind}) definido para {qty}")
            return True
        return False

    def unlock_all_items(self, kind: str = "items", qty: int = 99) -> int:
        count = 0
        if isinstance(self.raw_data, dict):
            inv = self.raw_data.setdefault(kind, {})
            if self.db:
                for item in self.db.get_all_known_items():
                    inv[str(item["id"])] = qty
                    count += 1
            else:
                for k in list(inv.keys()):
                    inv[k] = qty
                    count += 1
        return count

    def get_switches(self) -> List[Dict[str, Any]]:
        results = []
        if isinstance(self.raw_data, dict):
            sw = self.raw_data.get("switches", {})
            if isinstance(sw, dict):
                for k, val in sw.items():
                    results.append({"id": k, "name": f"Switch #{k}", "value": bool(val)})
            elif isinstance(sw, list):
                for idx, val in enumerate(sw):
                    if idx == 0: continue
                    results.append({"id": idx, "name": f"Switch #{idx}", "value": bool(val)})
        return results

    def set_switch(self, switch_id: int, state: bool) -> bool:
        if isinstance(self.raw_data, dict):
            sw = self.raw_data.setdefault("switches", {})
            if isinstance(sw, dict):
                sw[str(switch_id)] = bool(state)
            elif isinstance(sw, list):
                while len(sw) <= int(switch_id):
                    sw.append(False)
                sw[int(switch_id)] = bool(state)
            self.mark_dirty(f"Switch {switch_id} -> {state}")
            return True
        return False

    def get_variables(self) -> List[Dict[str, Any]]:
        results = []
        if isinstance(self.raw_data, dict):
            vr = self.raw_data.get("variables", {})
            if isinstance(vr, dict):
                for k, val in vr.items():
                    results.append({"id": k, "name": f"Variável #{k}", "value": val})
            elif isinstance(vr, list):
                for idx, val in enumerate(vr):
                    if idx == 0: continue
                    results.append({"id": idx, "name": f"Variável #{idx}", "value": val})
        return results

    def set_variable(self, var_id: int, value: Any) -> bool:
        if isinstance(self.raw_data, dict):
            vr = self.raw_data.setdefault("variables", {})
            if isinstance(vr, dict):
                vr[str(var_id)] = value
            elif isinstance(vr, list):
                while len(vr) <= int(var_id):
                    vr.append(0)
                vr[int(var_id)] = value
            self.mark_dirty(f"Variável {var_id} -> {value}")
            return True
        return False
