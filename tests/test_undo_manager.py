#!/usr/bin/env python3
import pytest
from scripts.core.undo_manager import UndoManager

def test_undo_manager_basic_workflow():
    manager = UndoManager()
    state = {"gold": 100}

    def set_gold(val):
        old_val = state["gold"]
        def undo():
            state["gold"] = old_val
        def redo():
            state["gold"] = val
        state["gold"] = val
        manager.record(f"Muda ouro para {val}", undo, redo)

    assert not manager.can_undo()
    assert not manager.can_redo()

    set_gold(250)
    assert state["gold"] == 250
    assert manager.can_undo()
    assert not manager.can_redo()
    assert manager.get_last_undo_description() == "Muda ouro para 250"

    # Undo
    desc = manager.undo()
    assert desc == "Muda ouro para 250"
    assert state["gold"] == 100
    assert not manager.can_undo()
    assert manager.can_redo()

    # Redo
    desc_redo = manager.redo()
    assert desc_redo == "Muda ouro para 250"
    assert state["gold"] == 250
    assert manager.can_undo()
    assert not manager.can_redo()

def test_undo_manager_listener():
    manager = UndoManager()
    notified = []

    def on_change(mgr):
        notified.append(mgr.can_undo())

    manager.add_listener(on_change)
    manager.record("Ação 1", lambda: None, lambda: None)
    assert len(notified) == 1
    assert notified[0] is True

    manager.undo()
    assert len(notified) == 2
    assert notified[1] is False

def test_undo_manager_clear():
    manager = UndoManager()
    manager.record("Ação 1", lambda: None, lambda: None)
    assert manager.can_undo()
    manager.clear()
    assert not manager.can_undo()
