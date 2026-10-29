#!/usr/bin/env python3
"""
Undo/Redo transaction manager for Save Maker.
Suporta histórico de ações reversíveis com notificações para a interface.
"""

from typing import Callable, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class ActionCommand:
    """Representa uma ação executada no editor que pode ser desfeita e refeita."""

    def __init__(self, description: str, undo_fn: Callable[[], Any], redo_fn: Callable[[], Any]):
        self.description = description
        self.undo_fn = undo_fn
        self.redo_fn = redo_fn

    def undo(self):
        try:
            self.undo_fn()
        except Exception as e:
            logger.error(f"Erro ao desfazer '{self.description}': {e}")
            raise

    def redo(self):
        try:
            self.redo_fn()
        except Exception as e:
            logger.error(f"Erro ao refazer '{self.description}': {e}")
            raise


class UndoManager:
    """Gerenciador de histórico de ações com suporte a Undo (Ctrl+Z) e Redo (Ctrl+Y/Ctrl+Shift+Z)."""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._undo_stack: List[ActionCommand] = []
        self._redo_stack: List[ActionCommand] = []
        self._listeners: List[Callable[["UndoManager"], None]] = []

    def record(self, description: str, undo_fn: Callable[[], Any], redo_fn: Callable[[], Any]):
        """Registra uma nova ação modificadora no topo da pilha."""
        cmd = ActionCommand(description, undo_fn, redo_fn)
        self._undo_stack.append(cmd)
        if len(self._undo_stack) > self.max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._notify()

    def undo(self) -> Optional[str]:
        """Desfaz a última ação registrada."""
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        try:
            cmd.undo()
        finally:
            self._redo_stack.append(cmd)
            self._notify()
        return cmd.description

    def redo(self) -> Optional[str]:
        """Refaz a última ação desfeita."""
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        try:
            cmd.redo()
        finally:
            self._undo_stack.append(cmd)
            self._notify()
        return cmd.description

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def get_last_undo_description(self) -> Optional[str]:
        return self._undo_stack[-1].description if self._undo_stack else None

    def clear(self):
        """Limpa todo o histórico (chamado ao carregar um novo arquivo)."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._notify()

    def add_listener(self, callback: Callable[["UndoManager"], None]):
        """Adiciona um observador para ser notificado quando o estado do histórico mudar."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[["UndoManager"], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self):
        for listener in list(self._listeners):
            try:
                listener(self)
            except Exception as e:
                logger.error(f"Erro ao notificar listener do UndoManager: {e}")
