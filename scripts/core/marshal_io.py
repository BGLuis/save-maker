#!/usr/bin/env python3
"""
marshal_io — Helpers de leitura e escrita multi-objeto para Ruby Marshal 4.8.

A biblioteca rubymarshal não expõe uma API de "leia todos os objetos até EOF".
Ao tentar ler além do último objeto, ela lança ValueError('Expected token \\x04')
com o stream posicionado exatamente no EOF. Este módulo encapsula essa quirk e
fornece uma interface limpa e testável.

Referência de formatos reais:
  VX Ace (.rvdata2): 2 objetos em sequência — make_save_header + make_save_contents
  VX    (.rvdata):   2 objetos (mesmo formato)
  XP    (.rxdata):  12 objetos — timer, system, map, player, switches, variables,
                                 self_sw, actors, party, troop, screen, pictures

Referências:
  https://ruby-doc.org/core/Marshal.html
  https://github.com/orzFly/RPGMakerDefaultScripts (DataManager.rb, Scene_Save.rb)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO, List

try:
    from rubymarshal.reader import load as _ruby_load
    from rubymarshal.writer import write as _ruby_write
    _AVAILABLE = True
except Exception:
    _ruby_load = None  # type: ignore[assignment]
    _ruby_write = None  # type: ignore[assignment]
    _AVAILABLE = False


def ruby_available() -> bool:
    """Retorna True se a biblioteca rubymarshal está instalada."""
    return _AVAILABLE


class MarshalStreamError(ValueError):
    """
    Lançado quando bytes não-Marshal são encontrados após o último objeto válido.
    Indica corrupção ou truncamento de arquivo, não EOF normal.
    """


def marshal_read_all(fd: BinaryIO) -> List[Any]:
    """
    Lê todos os objetos Marshal de *fd* até o fim do stream.

    rubymarshal sinaliza EOF com ValueError('Expected token \\x04') com o stream
    posicionado exatamente no final. Este helper distingue EOF real de corrupção
    verificando se há bytes restantes após a exceção.

    Args:
        fd: File-like object aberto em modo binário de leitura.

    Returns:
        Lista ordenada de objetos desserializados. Lista vazia para stream vazio.

    Raises:
        MarshalStreamError: Bytes inesperados após o último objeto válido
                            (indica corrupção, não EOF normal).
        RuntimeError: rubymarshal não instalada.
    """
    if not _AVAILABLE:
        raise RuntimeError(
            "Biblioteca rubymarshal não disponível (pip install rubymarshal)"
        )
    objects: List[Any] = []
    while True:
        try:
            obj = _ruby_load(fd)
            objects.append(obj)
        except Exception:
            # rubymarshal sinaliza EOF com ValueError — verifica se é EOF real
            remaining = fd.read()
            if remaining:
                raise MarshalStreamError(
                    f"Arquivo Marshal corrompido: {len(remaining)} bytes inesperados "
                    f"após {len(objects)} objeto(s) válido(s). "
                    f"Primeiros bytes: {remaining[:16].hex()}"
                )
            break  # EOF real — todos os objetos foram lidos
    return objects


def marshal_write_all(fd: BinaryIO, objects: List[Any]) -> None:
    """
    Serializa *objects* em *fd*, cada um como objeto Marshal independente.

    Esta é a operação inversa de marshal_read_all: grava N objetos em sequência,
    cada um com seu próprio cabeçalho \\x04\\x08, reproduzindo o formato nativo
    do RPG Maker VX Ace / VX / XP.

    Args:
        fd: File-like object aberto em modo binário de escrita.
        objects: Lista de objetos a serializar. Ordem é preservada.

    Raises:
        RuntimeError: rubymarshal não instalada.
        ValueError: *objects* é vazio — guarda de segurança contra gravar nada
                    (indicaria que o arquivo não foi lido antes de salvar).
    """
    if not _AVAILABLE:
        raise RuntimeError(
            "Biblioteca rubymarshal não disponível (pip install rubymarshal)"
        )
    if not objects:
        raise ValueError(
            "marshal_write_all: lista de objetos vazia — nada a gravar. "
            "O arquivo deve ser carregado antes de chamar save()."
        )
    for obj in objects:
        _ruby_write(fd, obj)


def marshal_read_file(path: Path) -> List[Any]:
    """Atalho: abre *path* em modo binário e delega para marshal_read_all."""
    with open(path, "rb") as fd:
        return marshal_read_all(fd)


def marshal_write_file(path: Path, objects: List[Any]) -> None:
    """Atalho: abre *path* para escrita binária e delega para marshal_write_all."""
    with open(path, "wb") as fd:
        marshal_write_all(fd, objects)
