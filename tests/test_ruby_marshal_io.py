#!/usr/bin/env python3
"""
Testes unitários para scripts/core/marshal_io.py.

Protegem a lógica de I/O multi-objeto Marshal isolada do RubyAdapter.
Se a rubymarshal mudar o comportamento de EOF, estes testes capturam primeiro.
"""
import io
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

try:
    from rubymarshal.writer import write as ruby_write
    from rubymarshal.classes import RubyObject
    _RUBY = True
except Exception:
    _RUBY = False

from core.marshal_io import (
    marshal_read_all,
    marshal_write_all,
    marshal_read_file,
    marshal_write_file,
    MarshalStreamError,
    ruby_available,
)


def _obj(cls: str, **attrs) -> "RubyObject":
    return RubyObject(cls, {f"@{k}": v for k, v in attrs.items()})


def test_availability():
    """Flag ruby_available() é coerente com o estado real dos imports."""
    assert ruby_available() == _RUBY
    print("✔ test_availability")


def test_single_object_roundtrip():
    """marshal_read_all lê 1 objeto corretamente — baseline."""
    if not _RUBY:
        print("⚠ test_single_object_roundtrip pulado (rubymarshal indisponível)")
        return
    buf = io.BytesIO()
    ruby_write(buf, _obj("Game_System", timer=0))
    buf.seek(0)
    result = marshal_read_all(buf)
    assert len(result) == 1
    assert result[0].ruby_class_name == "Game_System"
    print("✔ test_single_object_roundtrip")


def test_two_object_roundtrip():
    """
    Formato VX Ace real: header + contents em sequência.
    Round-trip deve ser byte-exato.
    """
    if not _RUBY:
        print("⚠ test_two_object_roundtrip pulado")
        return
    header = _obj("RPG::SaveHeader", characters=[], playtime_s="00:00")
    contents = {"party": _obj("Game_Party", gold=1500)}

    buf = io.BytesIO()
    ruby_write(buf, header)
    ruby_write(buf, contents)
    original_bytes = buf.getvalue()

    buf.seek(0)
    objects = marshal_read_all(buf)
    assert len(objects) == 2, f"Esperado 2 objetos, obtidos {len(objects)}"
    assert objects[0].ruby_class_name == "RPG::SaveHeader"
    assert isinstance(objects[1], dict)
    assert objects[1]["party"].attributes["@gold"] == 1500

    # Round-trip byte-exato
    out = io.BytesIO()
    marshal_write_all(out, objects)
    assert out.getvalue() == original_bytes, "Round-trip não preservou bytes exatos"
    print("✔ test_two_object_roundtrip")


def test_twelve_object_roundtrip():
    """Formato XP real: 12 objetos sequenciais na ordem canônica do Scene_Save.rb."""
    if not _RUBY:
        print("⚠ test_twelve_object_roundtrip pulado")
        return
    xp_classes = [
        "Game_Timer", "Game_System", "Game_Map", "Game_Player",
        "Game_Switches", "Game_Variables", "Game_SelfSwitches",
        "Game_Actors", "Game_Party", "Game_Troop", "Game_Screen", "Game_Pictures",
    ]
    buf = io.BytesIO()
    for cls in xp_classes:
        ruby_write(buf, RubyObject(cls, {}))
    buf.seek(0)

    objects = marshal_read_all(buf)
    assert len(objects) == 12, f"Esperado 12 objetos, obtidos {len(objects)}"
    assert [getattr(o, "ruby_class_name", "") for o in objects] == xp_classes
    print("✔ test_twelve_object_roundtrip")


def test_empty_stream_returns_empty_list():
    """Stream vazio retorna lista vazia sem lançar exceção."""
    if not _RUBY:
        print("⚠ test_empty_stream_returns_empty_list pulado")
        return
    result = marshal_read_all(io.BytesIO(b""))
    assert result == []
    print("✔ test_empty_stream_returns_empty_list")


def test_corrupted_stream_raises_marshal_error():
    """Bytes extras após o último objeto válido lançam MarshalStreamError."""
    if not _RUBY:
        print("⚠ test_corrupted_stream_raises_marshal_error pulado")
        return
    buf = io.BytesIO()
    ruby_write(buf, _obj("Game_System"))
    buf.write(b"\xDE\xAD\xBE\xEF")  # garbage após o objeto válido
    buf.seek(0)

    try:
        marshal_read_all(buf)
        assert False, "Deveria ter lançado MarshalStreamError"
    except MarshalStreamError as e:
        assert "corrompido" in str(e).lower(), f"Mensagem inesperada: {e}"
    print("✔ test_corrupted_stream_raises_marshal_error")


def test_write_empty_list_raises():
    """marshal_write_all com lista vazia lança ValueError com mensagem clara."""
    if not _RUBY:
        print("⚠ test_write_empty_list_raises pulado")
        return
    try:
        marshal_write_all(io.BytesIO(), [])
        assert False, "Deveria ter lançado ValueError"
    except ValueError as e:
        assert "vazia" in str(e).lower(), f"Mensagem inesperada: {e}"
    print("✔ test_write_empty_list_raises")


def test_file_helpers_roundtrip():
    """marshal_read_file e marshal_write_file são atalhos corretos."""
    if not _RUBY:
        print("⚠ test_file_helpers_roundtrip pulado")
        return
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "test.rvdata2"
        marshal_write_file(p, [_obj("Game_Party", gold=777)])
        objects = marshal_read_file(p)
        assert len(objects) == 1
        assert objects[0].attributes["@gold"] == 777
    print("✔ test_file_helpers_roundtrip")


if __name__ == "__main__":
    test_availability()
    test_single_object_roundtrip()
    test_two_object_roundtrip()
    test_twelve_object_roundtrip()
    test_empty_stream_returns_empty_list()
    test_corrupted_stream_raises_marshal_error()
    test_write_empty_list_raises()
    test_file_helpers_roundtrip()
    print("\nTODOS OS TESTES DE marshal_io PASSARAM!")
