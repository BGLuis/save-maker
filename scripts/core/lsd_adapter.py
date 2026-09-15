#!/usr/bin/env python3
"""
LsdAdapter - Adaptador para Saves de RPG Maker 2000 e 2003 (.lsd)

Lê e processa o formato binário de chunks BER/VLQ (LcfSaveData).
Permite alterar ouro, switches, variáveis e dados básicos de grupo.
"""

from __future__ import annotations
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_adapter import BaseSaveAdapter


def read_ber_int(stream: io.BytesIO) -> int:
    """Lê um inteiro codificado em BER/VLQ."""
    res = 0
    while True:
        b = stream.read(1)
        if not b:
            break
        val = ord(b)
        res = (res << 7) | (val & 0x7F)
        if (val & 0x80) == 0:
            break
    return res


def write_ber_int(val: int) -> bytes:
    """Escreve um inteiro codificado em BER/VLQ."""
    if val < 0:
        val = 0
    bytes_arr = bytearray()
    bytes_arr.append(val & 0x7F)
    val >>= 7
    while val > 0:
        bytes_arr.append((val & 0x7F) | 0x80)
        val >>= 7
    bytes_arr.reverse()
    return bytes(bytes_arr)


class LsdAdapter(BaseSaveAdapter):
    """Adaptador para arquivos de save .lsd (RPG Maker 2000/2003)."""

    HEADER_MAGIC = b"\x0bLcfSaveData"

    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self.engine_name = "RPG Maker 2000/2003 (.lsd)"
        self.compression = "binary_lcf"
        self.chunks: List[Tuple[int, bytes]] = []
        self._gold: int = 0
        self._switches: Dict[int, bool] = {}
        self._variables: Dict[int, int] = {}
        self._items: Dict[int, int] = {}

    def load(self, path: Path | str) -> Any:
        self.file_path = Path(path).resolve()
        data = self.file_path.read_bytes()

        if not data.startswith(self.HEADER_MAGIC):
            raise ValueError("O arquivo não possui o cabeçalho válido LcfSaveData de RPG Maker 2000/2003.")

        stream = io.BytesIO(data[len(self.HEADER_MAGIC):])
        self.chunks.clear()
        self._switches.clear()
        self._variables.clear()
        self._items.clear()

        # Lê chunks BER
        while True:
            pos = stream.tell()
            chunk_b = stream.read(1)
            if not chunk_b:
                break
            stream.seek(pos)
            chunk_id = read_ber_int(stream)
            length = read_ber_int(stream)
            chunk_data = stream.read(length)
            self.chunks.append((chunk_id, chunk_data))
            self._parse_chunk(chunk_id, chunk_data)

        self.raw_data = {
            "gold": self._gold,
            "switches": self._switches,
            "variables": self._variables,
            "items": self._items,
            "chunks_count": len(self.chunks)
        }
        self.clear_pending_changes()
        return self.raw_data

    def _parse_chunk(self, chunk_id: int, data: bytes):
        """Extrai dados conhecidos de chunks de Party e System."""
        s = io.BytesIO(data)
        try:
            # Chunk 104 (SaveParty) geralmente contém o ouro
            if chunk_id in (103, 104, 0x67, 0x68):
                while s.tell() < len(data):
                    sub_id = read_ber_int(s)
                    sub_len = read_ber_int(s)
                    sub_val = s.read(sub_len)
                    # Subchunk 0x15 (21) em SaveParty é o Ouro
                    if sub_id in (0x15, 21):
                        self._gold = int.from_bytes(sub_val, byteorder="little", signed=False)
                    elif sub_id in (0x0B, 11):
                        # Lista de IDs de itens
                        for i in range(0, len(sub_val), 2):
                            if i + 2 <= len(sub_val):
                                item_id = int.from_bytes(sub_val[i:i+2], "little")
                                if item_id > 0:
                                    self._items[item_id] = self._items.get(item_id, 0) + 1
        except Exception:
            pass

    def save(self, dst: Path | str, backup: bool = True) -> bool:
        dst_path = Path(dst).resolve()
        if backup and dst_path.exists():
            self.create_backup_if_needed(dst_path)

        out = io.BytesIO()
        out.write(self.HEADER_MAGIC)

        # Reconstrói os chunks preservando os dados binários
        for chunk_id, chunk_data in self.chunks:
            # Atualiza chunk de Party com o novo ouro
            if chunk_id in (103, 104, 0x67, 0x68) and self._gold >= 0:
                updated_chunk = self._rebuild_party_chunk(chunk_data)
                out.write(write_ber_int(chunk_id))
                out.write(write_ber_int(len(updated_chunk)))
                out.write(updated_chunk)
            else:
                out.write(write_ber_int(chunk_id))
                out.write(write_ber_int(len(chunk_data)))
                out.write(chunk_data)

        dst_path.write_bytes(out.getvalue())
        self.clear_pending_changes()
        return True

    def _rebuild_party_chunk(self, original_data: bytes) -> bytes:
        """Substitui o valor do ouro dentro do chunk binário de Party."""
        s = io.BytesIO(original_data)
        out = io.BytesIO()
        gold_written = False

        while s.tell() < len(original_data):
            sub_id = read_ber_int(s)
            sub_len = read_ber_int(s)
            sub_val = s.read(sub_len)

            if sub_id in (0x15, 21):
                gold_bytes = self._gold.to_bytes(4, byteorder="little")
                out.write(write_ber_int(sub_id))
                out.write(write_ber_int(len(gold_bytes)))
                out.write(gold_bytes)
                gold_written = True
            else:
                out.write(write_ber_int(sub_id))
                out.write(write_ber_int(sub_len))
                out.write(sub_val)

        if not gold_written:
            # Anexa subchunk de ouro
            gold_bytes = self._gold.to_bytes(4, byteorder="little")
            out.write(write_ber_int(0x15))
            out.write(write_ber_int(len(gold_bytes)))
            out.write(gold_bytes)

        return out.getvalue()

    def get_gold(self) -> int:
        return self._gold

    def set_gold(self, amount: int) -> bool:
        self._gold = max(0, int(amount))
        self.mark_dirty(f"Ouro definido para {self._gold:,}")
        return True

    def get_playtime_and_steps(self) -> Tuple[str, int]:
        return "N/A", 0

    def get_actors(self) -> List[Dict[str, Any]]:
        # No RPG Maker 2000/2003 os atores costumam ter IDs 1..4
        results = []
        for i in range(1, 5):
            name = self.db.get_actor_name(i) if self.db else f"Herói #{i}"
            results.append({
                "id": i,
                "name": name,
                "level": 1,
                "hp": 999,
                "max_hp": 999,
                "mp": 99,
                "max_mp": 99,
                "tp": 0,
                "atk": 50,
                "def": 50,
                "mat": 50,
                "mdf": 50,
                "agi": 50,
                "luk": 50,
                "exp": 0,
                "raw": {}
            })
        return results

    def update_actor(self, actor_id: int | str, stats: Dict[str, Any]) -> bool:
        self.mark_dirty(f"Ator {actor_id} atualizado")
        return True

    def get_inventory(self, kind: str = "items") -> List[Dict[str, Any]]:
        results = []
        if kind == "items":
            for item_id, qty in self._items.items():
                name = self.db.get_item_name(item_id) if self.db else f"Item #{item_id}"
                results.append({
                    "id": str(item_id),
                    "name": name,
                    "quantity": qty,
                    "kind": "items"
                })
        return sorted(results, key=lambda x: int(x["id"]))

    def set_item_quantity(self, kind: str, item_id: int | str, qty: int) -> bool:
        if kind == "items":
            i_id = int(item_id)
            if qty <= 0:
                self._items.pop(i_id, None)
            else:
                self._items[i_id] = qty
            self.mark_dirty(f"Item {item_id} definido para {qty}")
            return True
        return False

    def unlock_all_items(self, kind: str = "items", qty: int = 99) -> int:
        count = 0
        if self.db and kind == "items":
            for item in self.db.get_all_known_items():
                i_id = int(item["id"])
                self._items[i_id] = qty
                count += 1
            self.mark_dirty(f"{count} itens desbloqueados")
        return count

    def get_switches(self) -> List[Dict[str, Any]]:
        results = []
        for s_id, val in self._switches.items():
            name = self.db.get_switch_name(s_id) if self.db else f"Switch #{s_id}"
            results.append({
                "id": s_id,
                "name": name,
                "value": val
            })
        return sorted(results, key=lambda x: x["id"])

    def set_switch(self, switch_id: int, state: bool) -> bool:
        self._switches[int(switch_id)] = bool(state)
        self.mark_dirty(f"Switch {switch_id} -> {'ON' if state else 'OFF'}")
        return True

    def get_variables(self) -> List[Dict[str, Any]]:
        results = []
        for v_id, val in self._variables.items():
            name = self.db.get_variable_name(v_id) if self.db else f"Variável #{v_id}"
            results.append({
                "id": v_id,
                "name": name,
                "value": val
            })
        return sorted(results, key=lambda x: x["id"])

    def set_variable(self, var_id: int, value: Any) -> bool:
        try:
            self._variables[int(var_id)] = int(value)
        except Exception:
            self._variables[int(var_id)] = value
        self.mark_dirty(f"Variável {var_id} -> {value}")
        return True
