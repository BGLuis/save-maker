#!/usr/bin/env python3
"""
FormatDetector - Detecção Automática de Formatos de Save do RPG Maker

Analisa extensões de arquivo e cabeçalhos binários (magic bytes) para instanciar
automaticamente o adaptador correto (MV, MZ, VX Ace, VX, XP, 2000/2003, JSON).
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from .base_adapter import BaseSaveAdapter
from .mv_mz_adapter import MvMzAdapter
from .ruby_adapter import RubyAdapter
from .lsd_adapter import LsdAdapter
from .generic_adapter import GenericJsonAdapter
from .wolf_adapter import WolfAdapter, try_parse_wolf_header


def detect_and_create_adapter(path: Path | str, db_manager=None) -> BaseSaveAdapter:
    """
    Analisa o arquivo e retorna o adaptador correspondente já configurado.
    """
    fpath = Path(path).resolve()
    if not fpath.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {fpath}")

    ext = fpath.suffix.lower()
    header = b""
    try:
        header = fpath.read_bytes()[:16]
    except Exception:
        pass

    # 1. Checagem de Magic Bytes específicos
    # RPG Maker 2000 / 2003 (.lsd)
    if header.startswith(b"\x0bLcfSaveData") or ext == ".lsd":
        adapter = LsdAdapter(db_manager)
        adapter.engine_name = "RPG Maker 2000/2003 (.lsd)"
        return adapter

    # Ruby Marshal 4.8 (RPG Maker XP, VX, VX Ace)
    if header.startswith(b"\x04\x08") or ext in (".rvdata2", ".rvdata", ".rxdata"):
        adapter = RubyAdapter(db_manager)
        if ext == ".rvdata2": adapter.engine_name = "RPG Maker VX Ace"
        elif ext == ".rvdata": adapter.engine_name = "RPG Maker VX"
        elif ext == ".rxdata": adapter.engine_name = "RPG Maker XP"
        else: adapter.engine_name = "RPG Maker (Ruby Marshal)"
        return adapter

    # RPG Maker MV (.rpgsave) e MZ (.rmmzsave)
    if ext in (".rpgsave", ".rmmzsave"):
        adapter = MvMzAdapter(db_manager)
        if ext == ".rmmzsave":
            adapter.engine_name = "RPG Maker MZ"
        else:
            adapter.engine_name = "RPG Maker MV"
        return adapter

    # Wolf RPG Editor (.sav) - sem magic bytes; detecção 100% estrutural (descriptografa e
    # valida marcadores + checksum). Restrito a extensões plausíveis para não pagar o custo de
    # ler o arquivo inteiro e descriptografar para todo .json/.txt que chegue até aqui.
    if ext in (".sav", ".dat", ""):
        try:
            full_data = fpath.read_bytes()
        except Exception:
            full_data = b""
        if try_parse_wolf_header(full_data) is not None:
            adapter = WolfAdapter(db_manager)
            adapter.engine_name = "Wolf RPG Editor"
            return adapter

    # GZIP ou ZLIB comprimido
    if len(header) >= 2 and ((header[0] == 0x1F and header[1] == 0x8B) or header[0] == 0x78):
        # Tenta MV/MZ primeiro
        try:
            adapter = MvMzAdapter(db_manager)
            adapter.load(fpath)
            return adapter
        except Exception:
            pass

    # Saves em formato JSON ou texto puro
    if ext in (".json", ".sav", ".dat", ".txt"):
        # Tenta MV/MZ primeiro caso seja um save MV/MZ renomeado
        try:
            adapter = MvMzAdapter(db_manager)
            adapter.load(fpath)
            return adapter
        except Exception:
            pass

        # Fallback para Generic JSON
        adapter = GenericJsonAdapter(db_manager)
        return adapter

    # Fallback padrão: Tenta MvMzAdapter tolerante, depois Generic
    try:
        adapter = MvMzAdapter(db_manager)
        adapter.load(fpath)
        return adapter
    except Exception:
        return GenericJsonAdapter(db_manager)
