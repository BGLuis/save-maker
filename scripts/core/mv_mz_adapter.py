#!/usr/bin/env python3
"""
MvMzAdapter - Adaptador de Saves para RPG Maker MV (.rpgsave) e MZ (.rmmzsave)

Suporta compressão LZString (Base64 / UTF-16), Zlib stream tolerante a bytes extras,
Gzip e JSON direto. Mapeia ouro, grupo, inventário, atores, switches e variáveis.
"""

from __future__ import annotations
import json
import gzip
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_adapter import BaseSaveAdapter

try:
    from lzstring import LZString
    _LZSTRING = LZString()
except Exception:
    _LZSTRING = None


class MvMzAdapter(BaseSaveAdapter):
    """Adaptador para saves de RPG Maker MV (.rpgsave) e MZ (.rmmzsave)."""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self.raw_json_wrapper: Optional[Dict[str, Any]] = None
        self.engine_name = "RPG Maker MV/MZ"
        self._is_jsonex_wrapped: bool = False

    def load(self, path: Path | str) -> bool:
        resolved_path = Path(path).resolve()
        if getattr(self, "_already_loaded_path", None) == resolved_path and self.raw_data is not None:
            self._already_loaded_path = None
            return True

        self.file_path = resolved_path
        self._backed_up_paths = set()
        self._mutation_seq = 0
        raw_bytes = self.file_path.read_bytes()

        decompressed, comp = self._decompress(raw_bytes)
        parsed = self._parse_json(decompressed)

        # Se falhou parse inicial, tenta camada LZString
        if parsed is None and _LZSTRING:
            try:
                txt = decompressed.decode("utf-8", errors="ignore").strip()
                if not txt.startswith("{") and not txt.startswith("["):
                    unb64 = _LZSTRING.decompressFromBase64(txt)
                    if unb64:
                        parsed = json.loads(unb64)
                        comp = f"{comp}+lzstring"
            except Exception:
                pass

        if parsed is None:
            # Tenta decodificar como texto direto
            try:
                parsed = json.loads(decompressed.decode("utf-8-sig"))
            except Exception as e:
                raise ValueError(f"Arquivo não pôde ser interpretado como JSON de MV/MZ: {e}")

        self.compression = comp
        self.encoding = "lzstring" if "+lzstring" in comp else "none"

        # Suporte a JSON com metadados ou JSON direto do jogo
        if isinstance(parsed, dict) and "data" in parsed and "compression" in parsed:
            self.raw_json_wrapper = parsed
            self.raw_data = parsed["data"]
            self._is_jsonex_wrapped = False
        elif isinstance(parsed, dict) and parsed.get("@") == "JsonEx" and "data" in parsed:
            self.raw_json_wrapper = None
            self.raw_data = parsed["data"]
            self._is_jsonex_wrapped = True
        else:
            self.raw_json_wrapper = None
            self.raw_data = parsed
            self._is_jsonex_wrapped = False

        if self.file_path.suffix.lower() == ".rmmzsave":
            self.engine_name = "RPG Maker MZ"
        else:
            self.engine_name = "RPG Maker MV"

        self.clear_pending_changes()
        return True

    def serialize_snapshot(self) -> bytes:
        export_payload = self.raw_data
        if getattr(self, "_is_jsonex_wrapped", False):
            export_payload = {"@": "JsonEx", "data": self.raw_data}
        enc = "utf-8" if getattr(self, "encoding", "none") in ("lzstring", "none") else getattr(self, "encoding", "utf-8")
        return json.dumps(export_payload, ensure_ascii=False, separators=(",", ":")).encode(enc)

    def save(
        self,
        dst: Path | str,
        backup: bool = True,
        pre_serialized_json: Optional[bytes] = None,
        expected_seq: Optional[int] = None,
    ) -> bool:
        seq_at_start = expected_seq if expected_seq is not None else getattr(self, "_mutation_seq", 0)
        dst_path = Path(dst).resolve()
        if backup and dst_path.exists():
            self.create_backup_if_needed(dst_path)

        raw_json_bytes = pre_serialized_json if pre_serialized_json is not None else self.serialize_snapshot()
        out_bytes = self._compress(raw_json_bytes, self.compression, self.encoding)

        if hasattr(self, "atomic_write_bytes"):
            self.atomic_write_bytes(dst_path, out_bytes)
        else:
            import os
            tmp_f = dst_path.with_name(f"{dst_path.name}.tmp.{os.getpid()}")
            tmp_f.write_bytes(out_bytes)
            tmp_f.replace(dst_path)

        current_bytes = self.serialize_snapshot()
        if current_bytes != raw_json_bytes or getattr(self, "_mutation_seq", 0) != seq_at_start:
            self.dirty = True
            if getattr(self, "changes_count", 0) == 0:
                self.changes_count = 1
        else:
            try:
                self.clear_pending_changes(expected_seq=seq_at_start)
            except TypeError:
                self.clear_pending_changes()
        return True

    def export_to_json(self, dst: Path | str) -> bool:
        """Exporta o save como um arquivo JSON formatado legível."""
        dst_path = Path(dst).resolve()
        out = {
            "format": "json",
            "engine": self.engine_name,
            "compression": self.compression,
            "encoding": self.encoding,
            "data": self.raw_data,
        }
        json_bytes = json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8")
        if hasattr(self, "atomic_write_bytes"):
            self.atomic_write_bytes(dst_path, json_bytes)
        else:
            dst_path.write_bytes(json_bytes)
        return True

    # --- Implementações Normalizadas ---

    def get_party_dict(self) -> Dict[str, Any]:
        cur = self.raw_data
        if isinstance(cur, dict):
            if "party" in cur and isinstance(cur["party"], dict):
                return cur["party"]
        return {}

    def get_gold(self) -> int:
        party = self.get_party_dict()
        return int(party.get("_gold", 0))

    def set_gold(self, amount: int) -> bool:
        party = self.get_party_dict()
        if party is not None:
            party["_gold"] = max(0, int(amount))
            self.mark_dirty(f"Ouro definido para {amount:,}")
            return True
        return False

    def get_playtime_and_steps(self) -> Tuple[str, int]:
        steps = 0
        party = self.get_party_dict()
        if party:
            steps = int(party.get("_steps", 0))

        playtime = "Desconhecido"
        if isinstance(self.raw_data, dict):
            sys_node = self.raw_data.get("system", {})
            if isinstance(sys_node, dict):
                frames = sys_node.get("_framesOnSave", 0)
                total_secs = frames // 60
                hrs = total_secs // 3600
                mins = (total_secs % 3600) // 60
                secs = total_secs % 60
                playtime = f"{hrs:02d}:{mins:02d}:{secs:02d}"

        return playtime, steps

    def _get_param_plus_list(self, act: Dict[str, Any], create: bool = False) -> List[int]:
        raw_pp = act.get("_paramPlus")
        if isinstance(raw_pp, dict) and isinstance(raw_pp.get("@a"), list):
            target_list = raw_pp["@a"]
            if create:
                for k in list(raw_pp.keys()):
                    if k not in ("@c", "@a", "@"):
                        del raw_pp[k]
                while len(target_list) < 8:
                    target_list.append(0)
                return target_list
            else:
                padded = list(target_list)
                while len(padded) < 8:
                    padded.append(0)
                return padded
        elif isinstance(raw_pp, list):
            if create:
                while len(raw_pp) < 8:
                    raw_pp.append(0)
                return raw_pp
            else:
                padded = list(raw_pp)
                while len(padded) < 8:
                    padded.append(0)
                return padded
        else:
            if create:
                new_list = [0] * 8
                act["_paramPlus"] = new_list
                return new_list
            return [0] * 8

    def get_actors(self) -> List[Dict[str, Any]]:
        results = []
        if not isinstance(self.raw_data, dict):
            return results

        actors_container = self.raw_data.get("actors", {}).get("_data", {})
        actor_list = []
        if isinstance(actors_container, dict) and "@a" in actors_container:
            actor_list = actors_container["@a"]
        elif isinstance(actors_container, list):
            actor_list = actors_container
        elif isinstance(actors_container, dict):
            actor_list = [v for k, v in actors_container.items() if k not in ("@c", "@")]

        for idx, act in enumerate(actor_list):
            if not isinstance(act, dict):
                continue
            aid = act.get("_actorId", idx)
            name = act.get("_name")
            if not name and self.db:
                name = self.db.get_actor_name(aid)
            if not name:
                name = f"Ator #{aid}"

            lvl = act.get("_level", 1)
            hp = act.get("_hp", 0)
            mp = act.get("_mp", 0)
            tp = act.get("_tp", 0)

            class_id = act.get("_classId", 1)
            param_plus = self._get_param_plus_list(act, create=False)

            base_mhp = (self.db.get_class_param_base(class_id, 0, lvl) or 0) if (self.db and hasattr(self.db, "get_class_param_base")) else 0
            base_mmp = (self.db.get_class_param_base(class_id, 1, lvl) or 0) if (self.db and hasattr(self.db, "get_class_param_base")) else 0

            calc_max_hp = max(1, base_mhp + param_plus[0]) if base_mhp > 0 else (param_plus[0] if param_plus[0] > 0 else hp)
            calc_max_mp = max(0, base_mmp + param_plus[1]) if base_mmp > 0 else (param_plus[1] if param_plus[1] > 0 else mp)

            exp_dict = act.get("_exp", {})
            if isinstance(exp_dict, dict):
                exp_val = exp_dict.get(str(class_id), exp_dict.get(class_id, exp_dict.get("1", 0)))
            else:
                exp_val = 0

            # RPG Maker MV/MZ parâmetros: 0: mhp, 1: mmp, 2: atk, 3: def, 4: mat, 5: mdf, 6: agi, 7: luk
            results.append({
                "id": aid,
                "name": name,
                "class_id": class_id,
                "level": lvl,
                "hp": hp,
                "max_hp": calc_max_hp,
                "mhp_bonus": param_plus[0],
                "mp": mp,
                "max_mp": calc_max_mp,
                "mmp_bonus": param_plus[1],
                "tp": tp,
                "atk": param_plus[2],
                "def": param_plus[3],
                "mat": param_plus[4],
                "mdf": param_plus[5],
                "agi": param_plus[6],
                "luk": param_plus[7],
                "exp": exp_val,
                "raw": act,
            })
        return results

    def update_actor(self, actor_id: int | str, stats: Dict[str, Any]) -> bool:
        actors = self.get_actors()
        for a in actors:
            if str(a["id"]) == str(actor_id):
                act_raw = a["raw"]
                class_id = act_raw.get("_classId", 1)

                if "level" in stats:
                    new_lvl = max(1, min(999, int(stats["level"])))
                    act_raw["_level"] = new_lvl

                    if "exp" in stats:
                        exp_val = int(stats["exp"])
                    elif self.db and hasattr(self.db, "get_exp_for_level"):
                        res = self.db.get_exp_for_level(class_id, new_lvl)
                        if res is not None:
                            exp_val = int(res)
                        else:
                            exp_val = (
                                0
                                if new_lvl <= 1
                                else int(
                                    round(
                                        30.0
                                        * ((new_lvl - 1) ** (0.9 + 30.0 / 250.0))
                                        * new_lvl
                                        * (new_lvl + 1)
                                        / (6.0 + (new_lvl ** 2) / 50.0 / 30.0)
                                        + (new_lvl - 1) * 20.0
                                    )
                                )
                            )
                    else:
                        exp_val = (
                            0
                            if new_lvl <= 1
                            else int(
                                round(
                                    30.0
                                    * ((new_lvl - 1) ** (0.9 + 30.0 / 250.0))
                                    * new_lvl
                                    * (new_lvl + 1)
                                    / (6.0 + (new_lvl ** 2) / 50.0 / 30.0)
                                    + (new_lvl - 1) * 20.0
                                )
                            )
                        )

                    if not isinstance(act_raw.get("_exp"), dict):
                        act_raw["_exp"] = {}
                    act_raw["_exp"][str(class_id)] = exp_val
                elif "exp" in stats:
                    if not isinstance(act_raw.get("_exp"), dict):
                        act_raw["_exp"] = {}
                    act_raw["_exp"][str(class_id)] = int(stats["exp"])

                if "hp" in stats:
                    act_raw["_hp"] = max(0, int(stats["hp"]))
                if "mp" in stats:
                    act_raw["_mp"] = max(0, int(stats["mp"]))
                if "tp" in stats:
                    act_raw["_tp"] = max(0, int(stats["tp"]))

                # Atualiza paramPlus
                param_mapping = {
                    "max_hp": 0,
                    "mhp_bonus": 0,
                    "max_mp": 1,
                    "mmp_bonus": 1,
                    "atk": 2,
                    "def": 3,
                    "mat": 4,
                    "mdf": 5,
                    "agi": 6,
                    "luk": 7,
                }
                has_param_update = any(k in stats for k in param_mapping)
                if has_param_update:
                    target_pp = self._get_param_plus_list(act_raw, create=True)
                    for k, idx in param_mapping.items():
                        if k in stats:
                            target_pp[idx] = int(stats[k])

                self.mark_dirty(f"Ator {a['name']} atualizado")
                return True
        return False

    def get_inventory(self, kind: str = "items") -> List[Dict[str, Any]]:
        results = []
        party = self.get_party_dict()
        key_map = {
            "items": "_items",
            "weapons": "_weapons",
            "armors": "_armors"
        }
        target_key = key_map.get(kind, "_items")
        inv_dict = party.get(target_key, {})

        if isinstance(inv_dict, dict):
            for k, qty in inv_dict.items():
                if str(k).startswith("@"):
                    continue
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
        party = self.get_party_dict()
        key_map = {
            "items": "_items",
            "weapons": "_weapons",
            "armors": "_armors"
        }
        target_key = key_map.get(kind, "_items")
        inv_dict = party.setdefault(target_key, {})

        s_id = str(item_id)
        if qty <= 0:
            inv_dict.pop(s_id, None)
            self.mark_dirty(f"Item {s_id} ({kind}) removido")
        else:
            inv_dict[s_id] = int(qty)
            self.mark_dirty(f"Item {s_id} ({kind}) definido para {qty}")
        return True

    def unlock_all_items(self, kind: str = "items", qty: int = 99) -> int:
        party = self.get_party_dict()
        key_map = {
            "items": "_items",
            "weapons": "_weapons",
            "armors": "_armors"
        }
        target_key = key_map.get(kind, "_items")
        inv_dict = party.setdefault(target_key, {})

        count = 0
        if self.db:
            source = []
            if kind == "items": source = self.db.get_all_known_items()
            elif kind == "weapons": source = self.db.get_all_known_weapons()
            elif kind == "armors": source = self.db.get_all_known_armors()

            for entry in source:
                i_id = str(entry["id"])
                inv_dict[i_id] = qty
                count += 1
        else:
            # Define os que já existem para qty
            for k in list(inv_dict.keys()):
                if not str(k).startswith("@"):
                    inv_dict[k] = qty
                    count += 1

        self.mark_dirty(f"{count} {kind} atualizados para x{qty}")
        return count

    def get_switches(self) -> List[Dict[str, Any]]:
        results = []
        if not isinstance(self.raw_data, dict):
            return results
        sw_data = self.raw_data.get("switches", {}).get("_data", [])

        # Desembrulha @a se existir
        if isinstance(sw_data, dict) and "@a" in sw_data:
            sw_data = sw_data["@a"]

        if isinstance(sw_data, list):
            for idx, val in enumerate(sw_data):
                if idx == 0: continue
                name = self.db.get_switch_name(idx) if self.db else None
                results.append({
                    "id": idx,
                    "name": name or f"Switch #{idx}",
                    "value": bool(val)
                })
        elif isinstance(sw_data, dict):
            for k, val in sw_data.items():
                if str(k).startswith("@") or not str(k).isdigit(): continue
                idx = int(k)
                name = self.db.get_switch_name(idx) if self.db else None
                results.append({
                    "id": idx,
                    "name": name or f"Switch #{idx}",
                    "value": bool(val)
                })
        return sorted(results, key=lambda x: x["id"])

    def set_switch(self, switch_id: int, state: bool) -> bool:
        if not isinstance(self.raw_data, dict):
            return False
        sw_container = self.raw_data.setdefault("switches", {})
        sw_data = sw_container.setdefault("_data", [])

        # Desembrulha @a se existir
        target = sw_data["@a"] if (isinstance(sw_data, dict) and "@a" in sw_data) else sw_data

        idx = int(switch_id)
        if isinstance(target, list):
            while len(target) <= idx:
                target.append(False)
            target[idx] = bool(state)
        elif isinstance(target, dict):
            target[str(idx)] = bool(state)

        name = self.db.get_switch_name(idx) if self.db else f"Switch #{idx}"
        self.mark_dirty(f"{name} -> {'ON' if state else 'OFF'}")
        return True

    def get_variables(self) -> List[Dict[str, Any]]:
        results = []
        if not isinstance(self.raw_data, dict):
            return results
        var_data = self.raw_data.get("variables", {}).get("_data", [])

        # Desembrulha @a se existir
        if isinstance(var_data, dict) and "@a" in var_data:
            var_data = var_data["@a"]

        if isinstance(var_data, list):
            for idx, val in enumerate(var_data):
                if idx == 0: continue
                name = self.db.get_variable_name(idx) if self.db else None
                results.append({
                    "id": idx,
                    "name": name or f"Variável #{idx}",
                    "value": val
                })
        elif isinstance(var_data, dict):
            for k, val in var_data.items():
                if str(k).startswith("@") or not str(k).isdigit(): continue
                idx = int(k)
                name = self.db.get_variable_name(idx) if self.db else None
                results.append({
                    "id": idx,
                    "name": name or f"Variável #{idx}",
                    "value": val
                })
        return sorted(results, key=lambda x: x["id"])

    def set_variable(self, var_id: int, value: Any) -> bool:
        if not isinstance(self.raw_data, dict):
            return False
        var_container = self.raw_data.setdefault("variables", {})
        var_data = var_container.setdefault("_data", [])

        target = var_data["@a"] if (isinstance(var_data, dict) and "@a" in var_data) else var_data

        idx = int(var_id)
        # Converte para int se possível
        try:
            if isinstance(value, str) and value.lstrip("-").isdigit():
                val_to_set = int(value)
            else:
                val_to_set = value
        except Exception:
            val_to_set = value

        if isinstance(target, list):
            while len(target) <= idx:
                target.append(0)
            target[idx] = val_to_set
        elif isinstance(target, dict):
            target[str(idx)] = val_to_set

        name = self.db.get_variable_name(idx) if self.db else f"Variável #{idx}"
        self.mark_dirty(f"{name} -> {val_to_set}")
        return True

    # --- Métodos de Compressão e Descompressão Internos ---

    def _decompress(self, data: bytes) -> Tuple[bytes, str]:
        # 1. Gzip
        if len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B:
            try:
                return gzip.decompress(data), "gzip"
            except Exception:
                pass

        # 2. Zlib Stream tolerante (resolve trailing garbage)
        try:
            do = zlib.decompressobj()
            decompressed = do.decompress(data)
            if decompressed:
                return decompressed, "zlib"
        except Exception:
            pass

        # 3. Zlib Raw (sem cabeçalho)
        try:
            do = zlib.decompressobj(wbits=-zlib.MAX_WBITS)
            decompressed = do.decompress(data)
            if decompressed:
                return decompressed, "raw-zlib"
        except Exception:
            pass

        # 4 & 5. Zlib / Raw-Zlib salvo como string UTF-8 (formato RPG Maker MZ)
        try:
            raw = data.decode("utf-8").encode("latin-1")
        except UnicodeError:
            raw = None

        if raw is not None:
            try:
                decompressed = zlib.decompress(raw)
                if decompressed:
                    return decompressed, "zlib-utf8"
            except Exception:
                pass
            try:
                do = zlib.decompressobj(wbits=-zlib.MAX_WBITS)
                decompressed = do.decompress(raw)
                if decompressed:
                    return decompressed, "raw-zlib-utf8"
            except Exception:
                pass

        return data, "none"

    def _parse_json(self, bytes_data: bytes) -> Optional[Any]:
        try:
            text = bytes_data.decode("utf-8-sig")
            return json.loads(text)
        except Exception:
            return None

    def _compress(self, data: bytes, compression: str, encoding: str = "none") -> bytes:
        payload = data
        if encoding == "lzstring" or "lzstring" in compression:
            if _LZSTRING is None:
                raise RuntimeError("lzstring indisponível")
            txt = payload.decode("utf-8")
            comp = _LZSTRING.compressToBase64(txt)
            payload = comp.encode("utf-8")
            if compression in ("lzstring", "none+lzstring"):
                return payload

        if "gzip" in compression:
            return gzip.compress(payload)
        elif compression == "zlib-utf8":
            # Formato RPG Maker MZ: comprime com zlib, depois cada byte do resultado
            # é tratado como codepoint Unicode (0–255) e reencodado como UTF-8.
            compressed_bytes = zlib.compress(payload)
            return compressed_bytes.decode("latin-1").encode("utf-8")
        elif compression == "raw-zlib-utf8":
            # Variante sem cabeçalho zlib salva como UTF-8
            compressed_bytes = zlib.compress(payload)[2:-4]  # remove header/checksum
            return compressed_bytes.decode("latin-1").encode("utf-8")
        elif "zlib" in compression or "raw-zlib" in compression:
            return zlib.compress(payload)
        else:
            return payload
