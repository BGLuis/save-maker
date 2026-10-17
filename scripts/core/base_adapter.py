#!/usr/bin/env python3
"""
BaseSaveAdapter - Interface Abstrata e Modelo Unificado de Saves

Define a interface comum para qualquer formato de save (MV, MZ, VX Ace, VX, XP, 2000/2003, JSON).
Permite que a interface gráfica trate todos os jogos de forma consistente e elegante.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Set


class BaseSaveAdapter(ABC):
    """Classe base abstrata para adaptadores de save game."""

    def __init__(self, db_manager=None):
        self.file_path: Optional[Path] = None
        self.raw_data: Any = None
        self.compression: str = "none"
        self.encoding: str = "none"
        self.engine_name: str = "Unknown"
        self.db = db_manager
        self.dirty: bool = False
        self.changes_count: int = 0
        self._pending_changes: List[str] = []
        self._backed_up_paths: Set[Path] = set()
        self._mutation_seq: int = 0
        self._already_loaded_path: Optional[Path] = None

    def bind_database(self, db_manager):
        """Conecta um gerenciador de banco de dados para resolução de nomes."""
        self.db = db_manager

    def mark_dirty(self, description: str = ""):
        """Marca que há alterações não salvas no arquivo."""
        self.dirty = True
        self._mutation_seq += 1
        self.changes_count += 1
        if description:
            self._pending_changes.append(description)

    def get_pending_changes_count(self) -> int:
        return self.changes_count if self.changes_count else len(self._pending_changes)

    def clear_pending_changes(self, expected_seq: Optional[int] = None):
        if expected_seq is None or self._mutation_seq == expected_seq:
            self.dirty = False
            self.changes_count = 0
            self._pending_changes.clear()

    # --- Operações de Carregamento e Escrita ---

    @abstractmethod
    def load(self, path: Path | str) -> Any:
        """Carrega e decodifica o arquivo de save."""
        pass

    @abstractmethod
    def save(self, dst: Path | str, backup: bool = True) -> bool:
        """Serializa e salva o arquivo de save de volta no formato esperado pelo motor."""
        pass

    def create_backup_if_needed(self, dst: Path | str) -> bool:
        """Gera backup .bak antes de sobrescrever arquivo existente."""
        dst_resolved = Path(dst).resolve()
        if dst_resolved.exists():
            bak_path = dst_resolved.with_name(f"{dst_resolved.name}.bak")
            if dst_resolved in self._backed_up_paths and bak_path.exists():
                return True
            shutil.copy2(dst_resolved, bak_path)
            self._backed_up_paths.add(dst_resolved)
            return True
        return False

    def atomic_write_bytes(self, dst: Path | str, data: bytes) -> None:
        dst_path = Path(dst).resolve()
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{dst_path.name}.", suffix=".tmp", dir=str(dst_path.parent)
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, dst_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    def export_to_json(self, dst: Path | str) -> bool:
        dst_path = Path(dst).resolve()
        out = {
            "format": "json",
            "engine": self.engine_name,
            "compression": getattr(self, "compression", "none"),
            "encoding": getattr(self, "encoding", "utf-8"),
            "data": self.raw_data,
        }
        try:
            payload = json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8")
        except TypeError:
            payload = json.dumps(out, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        self.atomic_write_bytes(dst_path, payload)
        return True

    # --- Métodos de Leitura / Escrita Normalizados ---

    @abstractmethod
    def get_gold(self) -> int:
        """Retorna o ouro total da party."""
        pass

    @abstractmethod
    def set_gold(self, amount: int) -> bool:
        """Define o ouro total da party."""
        pass

    @abstractmethod
    def get_playtime_and_steps(self) -> Tuple[str, int]:
        """Retorna (tempo_formatado, passos)."""
        pass

    @abstractmethod
    def get_actors(self) -> List[Dict[str, Any]]:
        """
        Retorna lista de dicionários representando cada ator/personagem:
        {
            'id': int | str,
            'name': str,
            'level': int,
            'hp': int,
            'max_hp': int,
            'mp': int,
            'max_mp': int,
            'tp': int,
            'atk': int,
            'def': int,
            'mat': int,
            'mdf': int,
            'agi': int,
            'luk': int,
            'exp': int,
            'raw': Any
        }
        """
        pass

    @abstractmethod
    def update_actor(self, actor_id: int | str, stats: Dict[str, Any]) -> bool:
        """Atualiza atributos do ator especificado."""
        pass

    @abstractmethod
    def get_inventory(self, kind: str = "items") -> List[Dict[str, Any]]:
        """
        Retorna itens do tipo especificado ('items', 'weapons', 'armors'):
        [
            {
                'id': str,
                'name': str,
                'quantity': int,
                'kind': str
            }
        ]
        """
        pass

    @abstractmethod
    def set_item_quantity(self, kind: str, item_id: int | str, qty: int) -> bool:
        """Define a quantidade de um item no inventário."""
        pass

    @abstractmethod
    def unlock_all_items(self, kind: str = "items", qty: int = 99) -> int:
        """Adiciona todos os itens conhecidos do banco de dados com a quantidade indicada."""
        pass

    @abstractmethod
    def get_switches(self) -> List[Dict[str, Any]]:
        """
        Retorna lista de switches:
        [{'id': int, 'name': str, 'value': bool}]
        """
        pass

    @abstractmethod
    def set_switch(self, switch_id: int, state: bool) -> bool:
        """Define o estado (True/False) de um switch."""
        pass

    @abstractmethod
    def get_variables(self) -> List[Dict[str, Any]]:
        """
        Retorna lista de variáveis:
        [{'id': int, 'name': str, 'value': Any}]
        """
        pass

    @abstractmethod
    def set_variable(self, var_id: int, value: Any) -> bool:
        """Define o valor de uma variável."""
        pass

    # --- Navegação Genérica por Caminho ---

    def get_by_path(self, path: List[Any]) -> Any:
        cur = self.raw_data
        try:
            for p in path:
                if isinstance(cur, dict):
                    cur = cur.get(p)
                elif isinstance(cur, list):
                    cur = cur[int(p)]
                elif hasattr(cur, "attributes"):
                    cur = getattr(cur, "attributes", {}).get(p)
                else:
                    return None
            return cur
        except Exception:
            return None

    def set_by_path(self, path: List[Any], value: Any) -> bool:
        if not path:
            self.raw_data = value
            self.mark_dirty("Root alterado")
            return True
        cur = self.raw_data
        try:
            for i, p in enumerate(path):
                if i == len(path) - 1:
                    if isinstance(cur, dict):
                        cur[p] = value
                    elif isinstance(cur, list):
                        cur[int(p)] = value
                    elif hasattr(cur, "attributes"):
                        cur.attributes[p] = value
                    self.mark_dirty(f"Alterado {' -> '.join(str(x) for x in path)}")
                    return True
                else:
                    if isinstance(cur, dict):
                        cur = cur[p]
                    elif isinstance(cur, list):
                        cur = cur[int(p)]
                    elif hasattr(cur, "attributes"):
                        cur = cur.attributes[p]
        except Exception as e:
            print(f"[BaseSaveAdapter] Erro em set_by_path: {e}")
            return False
        return False
