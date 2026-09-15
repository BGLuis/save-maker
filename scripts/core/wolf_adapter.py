#!/usr/bin/env python3
"""
WolfAdapter - Adaptador experimental para Saves do Wolf RPG Editor (ウディタ) (.sav)

O formato de save do Wolf RPG Editor não é documentado oficialmente. Esta implementação é um
port do único parser de referência conhecido publicamente, Sinflower/WolfSave (C++, MIT,
https://github.com/Sinflower/WolfSave), lido diretamente do código-fonte durante o
desenvolvimento deste adaptador.

LIMITAÇÕES CONHECIDAS (leia antes de confiar nos dados):
  - A semântica da maioria dos campos das seções SavePart1, SavePart2, SavePart4, SavePart5 e
    SavePart7 é DESCONHECIDA. Eles são preservados estruturalmente (tipo e ordem corretos, para
    permitir round-trip byte-a-byte), mas expostos apenas como blobs genéricos na aba Avançado.
  - get_gold(), get_playtime_and_steps(), get_actors() e get_inventory() são heurísticas de
    melhor esforço: procuram por nomes de campo (via CDataBase.project do jogo) que contenham
    palavras-chave como "Gold"/"所持金". Podem retornar dados incorretos ou vazios em jogos com
    nomenclatura diferente.
  - get_switches()/set_switch() sempre retornam vazio/no-op: o Wolf RPG Editor não tem switches
    globais neste nível de dados (só self-switches por evento/mapa). Limitação intencional.
  - Nenhum save real do Wolf RPG Editor foi usado para validar esta implementação — os testes
    usam apenas fixtures sintéticas construídas em memória. Compatibilidade real é NÃO
    verificada.
  - O Wolf RPG Pro (3.5+) usa criptografia mais forte (AES/ChaCha20) para seus arquivos de
    projeto — não suportado aqui. Arquivos de save no esquema XOR simples (não-Pro) devem
    funcionar independentemente da versão.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_adapter import BaseSaveAdapter

HIGHEST_SUPPORTED_VERSION = 0x8E
START_OFFSET = 0x14  # 20 bytes de header sempre em texto puro; corpo começa aqui


# ---------------------------------------------------------------------------
# Primitivas binárias de baixo nível
# ---------------------------------------------------------------------------

class ByteReader:
    __slots__ = ("data", "pos")

    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def u8(self) -> int:
        v = self.data[self.pos]
        self.pos += 1
        return v

    def u16(self) -> int:
        v = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return v

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def u64(self) -> int:
        v = struct.unpack_from("<Q", self.data, self.pos)[0]
        self.pos += 8
        return v

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return v

    def raw(self, n: int) -> bytes:
        v = self.data[self.pos:self.pos + n]
        self.pos += n
        return v


class ByteWriter:
    __slots__ = ("buf",)

    def __init__(self):
        self.buf = bytearray()

    def u8(self, v: int):
        self.buf.append(v & 0xFF)

    def u16(self, v: int):
        self.buf += struct.pack("<H", v & 0xFFFF)

    def u32(self, v: int):
        self.buf += struct.pack("<I", v & 0xFFFFFFFF)

    def u64(self, v: int):
        self.buf += struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF)

    def i32(self, v: int):
        self.buf += struct.pack("<i", v)

    def raw(self, b: bytes):
        self.buf += b

    def getvalue(self) -> bytes:
        return bytes(self.buf)


def _as_i32(v: int) -> int:
    return v - 0x100000000 if v >= 0x80000000 else v


def _as_i16(v: int) -> int:
    return v - 0x10000 if v >= 0x8000 else v


def _read_memdata(r: ByteReader, width: int) -> bytes:
    """Lê um bloco MemData<WORD|DWORD>: prefixo de tamanho (2 ou 4 bytes) + bytes crus."""
    size = r.u16() if width == 2 else r.u32()
    return r.raw(size) if size else b""


def _write_memdata(w: ByteWriter, data: bytes, width: int):
    if width == 2:
        w.u16(len(data))
    else:
        w.u32(len(data))
    if data:
        w.raw(data)


def _decode_wolf_string(raw: bytes, encoding: str) -> str:
    if raw and raw[-1] == 0:
        raw = raw[:-1]
    return raw.decode(encoding, errors="replace")


def _encode_wolf_string(s: str, encoding: str) -> bytes:
    return s.encode(encoding, errors="replace") + b"\x00"


# ---------------------------------------------------------------------------
# Criptografia: XOR de 3 passadas com LCG estilo rand() do MSVC (auto-inverso)
# ---------------------------------------------------------------------------

_LCG_MUL = 0x343FD
_LCG_ADD = 0x269EC3
_LCG_MASK = 0xFFFFFFFF


def _lcg_byte_stream(seed: int):
    s = seed & _LCG_MASK
    while True:
        s = (s * _LCG_MUL + _LCG_ADD) & _LCG_MASK
        yield (s >> 28) & 7


def _xor_crypt(data: bytearray, start: int = START_OFFSET) -> None:
    """
    Aplica (ou reverte - é auto-inverso) a ofuscação XOR de 3 passadas do Wolf RPG Editor.
    Seeds lidos das posições 0, 3 e 9 do próprio buffer (sempre em texto puro).
    """
    if len(data) < 10 or len(data) <= start:
        return
    seeds = (data[0], data[3], data[9])
    strides = (1, 2, 5)
    for seed, stride in zip(seeds, strides):
        gen = _lcg_byte_stream(seed)
        for i in range(start, len(data), stride):
            data[i] ^= next(gen)


@dataclass
class WolfHeaderInfo:
    encoding: str
    decrypted: bytearray
    game_name: str
    file_version: int
    body_start: int


def try_parse_wolf_header(raw: bytes) -> Optional[WolfHeaderInfo]:
    """
    Detecção estrutural de um save do Wolf RPG Editor. Não existem magic bytes neste formato
    - a única forma de detectar é descriptografar e validar marcadores + checksum. Nunca lança
    exceção: retorna None se o buffer não parecer um save Wolf válido (esquema XOR simples).
    """
    if len(raw) < START_OFFSET + 4:
        return None
    try:
        data = bytearray(raw)
        _xor_crypt(data, start=START_OFFSET)

        if data[START_OFFSET] != 0x19:
            return None
        if data[-1] != 0x19:
            return None

        checksum = sum(data[START_OFFSET:]) & 0xFF
        if data[2] != checksum:
            return None

        encoding = "utf-8" if data[6] == 0x55 else "cp932"

        r = ByteReader(bytes(data), START_OFFSET + 1)
        name_raw = _read_memdata(r, 2)
        file_version = r.u16()

        if file_version > HIGHEST_SUPPORTED_VERSION:
            return None

        game_name = _decode_wolf_string(name_raw, encoding)

        return WolfHeaderInfo(
            encoding=encoding,
            decrypted=data,
            game_name=game_name,
            file_version=file_version,
            body_start=r.pos,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# SavePart1 - semântica desconhecida, preservado estruturalmente (blob opaco tipado)
# ---------------------------------------------------------------------------

def _read_sp1_1_1_1(r: ByteReader) -> dict:
    d: Dict[str, Any] = {}
    d["var1"] = r.u8()
    d["var2"] = r.u8()
    d["vars1"] = [r.u32() for _ in range(d["var2"])]
    d["var3"] = r.u8()
    d["vars2"] = [r.u8() for _ in range(d["var3"])]
    return d


def _write_sp1_1_1_1(w: ByteWriter, d: dict):
    w.u8(d["var1"])
    w.u8(d["var2"])
    for v in d["vars1"]:
        w.u32(v)
    w.u8(d["var3"])
    for v in d["vars2"]:
        w.u8(v)


def _default_sp1_1_1_1() -> dict:
    return {"var1": 0, "var2": 0, "vars1": [], "var3": 0, "vars2": []}


def _read_sp1_1_1(r: ByteReader) -> dict:
    d: Dict[str, Any] = {}
    for k in ("var1", "var2", "var3", "var4", "var5", "var6"):
        d[k] = r.u8()
    d["var7"] = r.u32()
    if d["var7"] > 0x10000:
        raise ValueError("Wolf save: SavePart1_1_1.var7 excede o limite (0x10000)")
    d["items"] = [_read_sp1_1_1_1(r) for _ in range(d["var7"])]
    return d


def _write_sp1_1_1(w: ByteWriter, d: dict):
    for k in ("var1", "var2", "var3", "var4", "var5", "var6"):
        w.u8(d[k])
    w.u32(d["var7"])
    for item in d["items"]:
        _write_sp1_1_1_1(w, item)


def _default_sp1_1_1() -> dict:
    return {"var1": 0, "var2": 0, "var3": 0, "var4": 0, "var5": 0, "var6": 0,
            "var7": 0, "items": []}


def _read_sp1_1(r: ByteReader, version: int) -> dict:
    d: Dict[str, Any] = {}
    d["var1"] = r.u32()
    d["var2"] = r.u32()
    d["var3"] = r.u32()
    d["var4"] = r.u32()
    d["var5"] = r.u8()
    d["var6"] = r.u32()
    d["md1"] = _read_memdata(r, 2)
    d["var7"] = r.u16()
    d["var8"] = r.u16()
    d["var9"] = r.u16()
    d["var10"] = r.u16()
    d["var11"] = r.u8()
    d["var12"] = r.u8()
    d["sp1"] = _read_sp1_1_1(r)
    d["sp2"] = _read_sp1_1_1(r)
    d["var13"] = r.u16()
    d["var14"] = r.u16()
    d["var15"] = r.u16()
    d["var16"] = r.u16()
    d["var17"] = r.u16()
    d["var18"] = r.u16()
    d["var19"] = r.u8()
    d["var20"] = r.u8()
    d["var21"] = r.u8()
    d["var22"] = r.u32()
    d["vars1"] = [r.u32() for _ in range(d["var22"])] if _as_i32(d["var22"]) > 0 else []

    if version >= 0x70:
        d["var23"] = r.u8()
        d["var24"] = r.u8()
    if version >= 0x73:
        d["var25"] = r.u32()
        d["var26"] = r.u32()
        d["var27"] = r.u32()
        d["var28"] = r.u32()
    if version >= 0x78:
        d["var29"] = r.u32()
    if version >= 0x85:
        d["var30"] = r.u32()
        d["var31"] = r.u32()
        d["var32"] = r.u32()
    if version >= 0x8A:
        d["var33"] = r.u16()
        d["mds1"] = [_read_memdata(r, 2) for _ in range(d["var33"])] if 0 < _as_i16(d["var33"]) else []
        d["var34"] = r.u32()
        d["var35"] = r.u8()
        d["var36"] = r.u32()
        d["var37"] = r.u32()
    if version >= 0x8B:
        d["var38"] = r.u32()
    if version < 0x8C:
        return d
    d["var39"] = r.u32()
    return d


def _write_sp1_1(w: ByteWriter, d: dict, version: int):
    w.u32(d["var1"]); w.u32(d["var2"]); w.u32(d["var3"]); w.u32(d["var4"])
    w.u8(d["var5"]); w.u32(d["var6"])
    _write_memdata(w, d["md1"], 2)
    w.u16(d["var7"]); w.u16(d["var8"]); w.u16(d["var9"]); w.u16(d["var10"])
    w.u8(d["var11"]); w.u8(d["var12"])
    _write_sp1_1_1(w, d["sp1"])
    _write_sp1_1_1(w, d["sp2"])
    w.u16(d["var13"]); w.u16(d["var14"]); w.u16(d["var15"])
    w.u16(d["var16"]); w.u16(d["var17"]); w.u16(d["var18"])
    w.u8(d["var19"]); w.u8(d["var20"]); w.u8(d["var21"])
    w.u32(d["var22"])
    if _as_i32(d["var22"]) > 0:
        for v in d["vars1"]:
            w.u32(v)

    if version >= 0x70:
        w.u8(d["var23"]); w.u8(d["var24"])
    if version >= 0x73:
        w.u32(d["var25"]); w.u32(d["var26"]); w.u32(d["var27"]); w.u32(d["var28"])
    if version >= 0x78:
        w.u32(d["var29"])
    if version >= 0x85:
        w.u32(d["var30"]); w.u32(d["var31"]); w.u32(d["var32"])
    if version >= 0x8A:
        w.u16(d["var33"])
        if 0 < _as_i16(d["var33"]):
            for v in d["mds1"]:
                _write_memdata(w, v, 2)
        w.u32(d["var34"]); w.u8(d["var35"]); w.u32(d["var36"]); w.u32(d["var37"])
    if version >= 0x8B:
        w.u32(d["var38"])
    if version < 0x8C:
        return
    w.u32(d["var39"])


def _default_sp1_1(version: int) -> dict:
    d: Dict[str, Any] = {
        "var1": 0, "var2": 0, "var3": 0, "var4": 0, "var5": 0, "var6": 0,
        "md1": b"",
        "var7": 0, "var8": 0, "var9": 0, "var10": 0, "var11": 0, "var12": 0,
        "sp1": _default_sp1_1_1(), "sp2": _default_sp1_1_1(),
        "var13": 0, "var14": 0, "var15": 0, "var16": 0, "var17": 0, "var18": 0,
        "var19": 0, "var20": 0, "var21": 0,
        "var22": 0, "vars1": [],
    }
    if version >= 0x70:
        d["var23"] = 0; d["var24"] = 0
    if version >= 0x73:
        d["var25"] = 0; d["var26"] = 0; d["var27"] = 0; d["var28"] = 0
    if version >= 0x78:
        d["var29"] = 0
    if version >= 0x85:
        d["var30"] = 0; d["var31"] = 0; d["var32"] = 0
    if version >= 0x8A:
        d["var33"] = 0; d["mds1"] = []
        d["var34"] = 0; d["var35"] = 0; d["var36"] = 0; d["var37"] = 0
    if version >= 0x8B:
        d["var38"] = 0
    if version >= 0x8C:
        d["var39"] = 0
    return d


def _read_save_part1(r: ByteReader, version: int) -> dict:
    d: Dict[str, Any] = {}
    d["var1"] = r.u32()
    d["var2"] = r.u32()
    d["var3"] = r.u32()

    if version >= 0x69:
        d["var4"] = r.u32()
        d["var5"] = r.u32()
        var6 = r.u32()
        if _as_i32(var6) != -1:
            r.pos -= 4
            d["_sp1_has_array"] = True
            count = 3 * d["var4"] * d["var5"]
            d["vars1"] = [r.u32() for _ in range(count)]
        else:
            d["_sp1_has_array"] = False
            d["var6"] = var6

    d["md1"] = _read_memdata(r, 4)
    v140 = 7
    if version >= 0x73:
        v140 = 15
    if version >= 0x8A:
        v140 = 31
    d["mds1"] = [_read_memdata(r, 4) for _ in range(v140)]

    d["var7"] = r.u32()
    d["vars2New"] = []
    d["vars2Old"] = []
    if _as_i32(d["var7"]) > 0:
        if version >= 0x64:
            d["vars2New"] = [r.u32() for _ in range(d["var7"])]
        else:
            d["vars2Old"] = [r.u8() for _ in range(d["var7"])]

    d["var8"] = r.u32()
    d["savePart1_1s"] = []
    if _as_i32(d["var8"]) > 0:
        d["savePart1_1s"] = [_read_sp1_1(r, version) for _ in range(d["var8"])]

    if version >= 0x72:
        for k in ("var9", "var10", "var11", "var12", "var13", "var14", "var15",
                   "var16", "var17", "var18", "var19"):
            d[k] = r.u32()

    d["var20"] = r.u32()
    d["vars3"] = []
    if _as_i32(d["var20"]) > 0:
        d["vars3"] = [r.u32() for _ in range(d["var20"])]

    return d


def _write_save_part1(w: ByteWriter, d: dict, version: int):
    w.u32(d["var1"]); w.u32(d["var2"]); w.u32(d["var3"])

    if version >= 0x69:
        w.u32(d["var4"]); w.u32(d["var5"])
        if d.get("_sp1_has_array"):
            for v in d["vars1"]:
                w.u32(v)
        else:
            w.u32(d["var6"])

    _write_memdata(w, d["md1"], 4)
    for md in d["mds1"]:
        _write_memdata(w, md, 4)

    w.u32(d["var7"])
    if _as_i32(d["var7"]) > 0:
        if version >= 0x64:
            for v in d["vars2New"]:
                w.u32(v)
        else:
            for v in d["vars2Old"]:
                w.u8(v)

    w.u32(d["var8"])
    if _as_i32(d["var8"]) > 0:
        for sp in d["savePart1_1s"]:
            _write_sp1_1(w, sp, version)

    if version >= 0x72:
        for k in ("var9", "var10", "var11", "var12", "var13", "var14", "var15",
                   "var16", "var17", "var18", "var19"):
            w.u32(d[k])

    w.u32(d["var20"])
    if _as_i32(d["var20"]) > 0:
        for v in d["vars3"]:
            w.u32(v)


def _default_save_part1(version: int) -> dict:
    d: Dict[str, Any] = {"var1": 0, "var2": 0, "var3": 0}
    if version >= 0x69:
        d["var4"] = 0
        d["var5"] = 0
        d["_sp1_has_array"] = False
        d["var6"] = 0xFFFFFFFF
        d["vars1"] = []
    d["md1"] = b""
    v140 = 7
    if version >= 0x73:
        v140 = 15
    if version >= 0x8A:
        v140 = 31
    d["mds1"] = [b"" for _ in range(v140)]
    d["var7"] = 0
    d["vars2New"] = []
    d["vars2Old"] = []
    d["var8"] = 0
    d["savePart1_1s"] = []
    if version >= 0x72:
        for k in ("var9", "var10", "var11", "var12", "var13", "var14", "var15",
                   "var16", "var17", "var18", "var19"):
            d[k] = 0
    d["var20"] = 0
    d["vars3"] = []
    return d


# ---------------------------------------------------------------------------
# SavePart2 - semântica desconhecida, preservado estruturalmente (blob opaco tipado)
# ---------------------------------------------------------------------------

_SP2_U32_BLOCK_A = ["var3", "var4", "var5", "var6", "var7", "var8", "var9", "var10",
                     "var11", "var12", "var13", "var14", "var15", "var16", "var17",
                     "var18", "var19", "var20", "var21"]


def _read_save_part2(r: ByteReader, version: int) -> dict:
    d: Dict[str, Any] = {}
    d["var1"] = r.u8()
    d["var2"] = r.u8()
    for k in _SP2_U32_BLOCK_A:
        d[k] = r.u32()
    d["var22"] = r.u16()
    d["var23"] = r.u16()
    d["var24"] = r.u16()
    d["var25"] = r.u32()
    d["var26"] = r.u16()
    d["var27"] = r.u16()
    d["var28"] = r.u16()
    d["var29"] = r.u32()
    d["var30"] = r.u32()
    d["var31"] = r.u32()
    d["var32"] = r.u32()
    d["var33"] = r.u32()
    d["var34"] = r.u32()
    d["var35"] = r.u32()
    d["var36"] = r.u32()
    d["var37"] = r.u32()
    d["var38"] = r.u8()
    d["var39"] = r.u16()
    d["var40"] = r.u32()
    d["var41"] = r.u32()
    d["var42"] = r.u16()
    d["var43"] = r.u16()
    d["var44"] = r.u16()
    d["var45"] = r.u16()
    d["var46"] = r.u32()
    d["var47"] = r.u32()
    d["var48"] = r.u32()
    d["var49"] = r.u8()

    if version <= 96:
        d["var50"] = r.u32()
    d["var51"] = r.u32()

    if version >= 98:
        d["var52"] = r.u32()
        d["var53"] = r.u32()

    if version >= 100:
        d["var54"] = r.u32()
        d["var55"] = r.u32()
        d["var56"] = r.u8()
        d["var57"] = r.u32()
        d["mds1"] = [_read_memdata(r, 4) for _ in range(d["var57"])] if _as_i32(d["var57"]) > 0 else []
        d["var58"] = r.u32()
        d["vars1"] = [r.u32() for _ in range(d["var58"])] if _as_i32(d["var58"]) > 0 else []
        d["var59"] = r.u32()
        d["var60"] = r.u32()
        d["var61"] = r.u32()
        d["var62"] = r.u32()
        d["var63"] = r.u32()

    if version >= 101:
        for k in ("var64", "var65", "var66", "var67", "var68", "var69"):
            d[k] = r.u32()

    if version >= 102:
        d["var70"] = r.u16()

    if version >= 103:
        d["md1"] = _read_memdata(r, 2)
        d["md2"] = _read_memdata(r, 2)

    if version >= 104:
        d["var71"] = r.u32()

    if version >= 106:
        d["var72"] = r.u32()
        d["var73"] = r.u32()
        d["var74"] = r.u32()

    if version >= 108:
        d["md3"] = _read_memdata(r, 2)
        d["var75"] = r.u32()
        d["var76"] = r.u32()
        d["var77"] = r.u32()
        d["md4"] = _read_memdata(r, 2)
        d["var78"] = r.u32()
        d["var79"] = r.u32()
        d["var80"] = r.u32()

    if version >= 109:
        d["md5"] = _read_memdata(r, 2)
        d["md6"] = _read_memdata(r, 2)
        d["var81"] = r.u8()

    if version >= 110:
        d["var82"] = r.u8()

    if version >= 119:
        d["md7"] = _read_memdata(r, 2)
        d["md8"] = _read_memdata(r, 2)
        d["md9"] = _read_memdata(r, 2)

    if version >= 121:
        d["var83"] = r.u32()
    if version >= 122:
        d["var84"] = r.u32()
    if version >= 124:
        d["var85"] = r.u32()
    if version >= 126:
        d["var86"] = r.u32()
    if version >= 128:
        d["var87"] = r.u32()
    if version >= 129:
        d["var88"] = r.u32()
        d["var89"] = r.u32()
    if version >= 130:
        d["var90"] = r.u32()
    if version >= 131:
        d["var91"] = r.u32()
    if version >= 132:
        d["var92"] = r.u32()
        d["var93"] = r.u32()
        d["var94"] = r.u32()
        d["var95"] = r.u32()
    if version >= 134:
        d["var96"] = r.u8()
    if version >= 136:
        d["var97"] = r.u8()
    if version >= 137:
        d["var98"] = r.u32()
        d["var99"] = r.u32()
        d["var100"] = r.u32()
        d["var101"] = r.u32()
        d["vars2"] = [r.u32() for _ in range(24)]

    if version >= 0x8A:
        d["var102"] = r.u32()
        d["var103"] = r.u32()
        d["var104"] = r.u32()
        d["var105"] = r.u32()
        d["md10"] = _read_memdata(r, 4)
        d["var106"] = r.u32()
        d["mds2"] = [_read_memdata(r, 4) for _ in range(d["var106"])] if _as_i32(d["var106"]) > 0 else []

    if version < 0x8D:
        return d

    for k in ("var107", "var108", "var109", "var110", "var111", "var112", "var113",
               "var114", "var115", "var116", "var117", "var118", "var119", "var120"):
        d[k] = r.u8()
    d["bytes"] = r.raw(0x100)
    d["var121"] = r.u8()
    d["var122"] = r.u8()

    if version < 0x8E:
        return d
    d["var123"] = r.u32()
    return d


def _write_save_part2(w: ByteWriter, d: dict, version: int):
    w.u8(d["var1"])
    w.u8(d["var2"])
    for k in _SP2_U32_BLOCK_A:
        w.u32(d[k])
    w.u16(d["var22"])
    w.u16(d["var23"])
    w.u16(d["var24"])
    w.u32(d["var25"])
    w.u16(d["var26"])
    w.u16(d["var27"])
    w.u16(d["var28"])
    w.u32(d["var29"])
    w.u32(d["var30"])
    w.u32(d["var31"])
    w.u32(d["var32"])
    w.u32(d["var33"])
    w.u32(d["var34"])
    w.u32(d["var35"])
    w.u32(d["var36"])
    w.u32(d["var37"])
    w.u8(d["var38"])
    w.u16(d["var39"])
    w.u32(d["var40"])
    w.u32(d["var41"])
    w.u16(d["var42"])
    w.u16(d["var43"])
    w.u16(d["var44"])
    w.u16(d["var45"])
    w.u32(d["var46"])
    w.u32(d["var47"])
    w.u32(d["var48"])
    w.u8(d["var49"])

    if version <= 96:
        w.u32(d["var50"])
    w.u32(d["var51"])

    if version >= 98:
        w.u32(d["var52"])
        w.u32(d["var53"])

    if version >= 100:
        w.u32(d["var54"])
        w.u32(d["var55"])
        w.u8(d["var56"])
        w.u32(d["var57"])
        if _as_i32(d["var57"]) > 0:
            for md in d["mds1"]:
                _write_memdata(w, md, 4)
        w.u32(d["var58"])
        if _as_i32(d["var58"]) > 0:
            for v in d["vars1"]:
                w.u32(v)
        w.u32(d["var59"])
        w.u32(d["var60"])
        w.u32(d["var61"])
        w.u32(d["var62"])
        w.u32(d["var63"])

    if version >= 101:
        for k in ("var64", "var65", "var66", "var67", "var68", "var69"):
            w.u32(d[k])

    if version >= 102:
        w.u16(d["var70"])

    if version >= 103:
        _write_memdata(w, d["md1"], 2)
        _write_memdata(w, d["md2"], 2)

    if version >= 104:
        w.u32(d["var71"])

    if version >= 106:
        w.u32(d["var72"])
        w.u32(d["var73"])
        w.u32(d["var74"])

    if version >= 108:
        _write_memdata(w, d["md3"], 2)
        w.u32(d["var75"])
        w.u32(d["var76"])
        w.u32(d["var77"])
        _write_memdata(w, d["md4"], 2)
        w.u32(d["var78"])
        w.u32(d["var79"])
        w.u32(d["var80"])

    if version >= 109:
        _write_memdata(w, d["md5"], 2)
        _write_memdata(w, d["md6"], 2)
        w.u8(d["var81"])

    if version >= 110:
        w.u8(d["var82"])

    if version >= 119:
        _write_memdata(w, d["md7"], 2)
        _write_memdata(w, d["md8"], 2)
        _write_memdata(w, d["md9"], 2)

    if version >= 121:
        w.u32(d["var83"])
    if version >= 122:
        w.u32(d["var84"])
    if version >= 124:
        w.u32(d["var85"])
    if version >= 126:
        w.u32(d["var86"])
    if version >= 128:
        w.u32(d["var87"])
    if version >= 129:
        w.u32(d["var88"])
        w.u32(d["var89"])
    if version >= 130:
        w.u32(d["var90"])
    if version >= 131:
        w.u32(d["var91"])
    if version >= 132:
        w.u32(d["var92"])
        w.u32(d["var93"])
        w.u32(d["var94"])
        w.u32(d["var95"])
    if version >= 134:
        w.u8(d["var96"])
    if version >= 136:
        w.u8(d["var97"])
    if version >= 137:
        w.u32(d["var98"])
        w.u32(d["var99"])
        w.u32(d["var100"])
        w.u32(d["var101"])
        for v in d["vars2"]:
            w.u32(v)

    if version >= 0x8A:
        w.u32(d["var102"])
        w.u32(d["var103"])
        w.u32(d["var104"])
        w.u32(d["var105"])
        _write_memdata(w, d["md10"], 4)
        w.u32(d["var106"])
        if _as_i32(d["var106"]) > 0:
            for md in d["mds2"]:
                _write_memdata(w, md, 4)

    if version < 0x8D:
        return

    for k in ("var107", "var108", "var109", "var110", "var111", "var112", "var113",
               "var114", "var115", "var116", "var117", "var118", "var119", "var120"):
        w.u8(d[k])
    w.raw(d["bytes"])
    w.u8(d["var121"])
    w.u8(d["var122"])

    if version < 0x8E:
        return
    w.u32(d["var123"])


def _default_save_part2(version: int) -> dict:
    d: Dict[str, Any] = {"var1": 0, "var2": 0}
    for k in _SP2_U32_BLOCK_A:
        d[k] = 0
    for k in ("var22", "var23", "var24", "var25", "var26", "var27", "var28", "var29",
               "var30", "var31", "var32", "var33", "var34", "var35", "var36", "var37",
               "var38", "var39", "var40", "var41", "var42", "var43", "var44", "var45",
               "var46", "var47", "var48", "var49"):
        d[k] = 0

    if version <= 96:
        d["var50"] = 0
    d["var51"] = 0

    if version >= 98:
        d["var52"] = 0
        d["var53"] = 0

    if version >= 100:
        for k in ("var54", "var55", "var56", "var57", "var58", "var59", "var60",
                   "var61", "var62", "var63"):
            d[k] = 0
        d["mds1"] = []
        d["vars1"] = []

    if version >= 101:
        for k in ("var64", "var65", "var66", "var67", "var68", "var69"):
            d[k] = 0

    if version >= 102:
        d["var70"] = 0

    if version >= 103:
        d["md1"] = b""
        d["md2"] = b""

    if version >= 104:
        d["var71"] = 0

    if version >= 106:
        d["var72"] = 0
        d["var73"] = 0
        d["var74"] = 0

    if version >= 108:
        d["md3"] = b""
        d["var75"] = 0
        d["var76"] = 0
        d["var77"] = 0
        d["md4"] = b""
        d["var78"] = 0
        d["var79"] = 0
        d["var80"] = 0

    if version >= 109:
        d["md5"] = b""
        d["md6"] = b""
        d["var81"] = 0

    if version >= 110:
        d["var82"] = 0

    if version >= 119:
        d["md7"] = b""
        d["md8"] = b""
        d["md9"] = b""

    if version >= 121:
        d["var83"] = 0
    if version >= 122:
        d["var84"] = 0
    if version >= 124:
        d["var85"] = 0
    if version >= 126:
        d["var86"] = 0
    if version >= 128:
        d["var87"] = 0
    if version >= 129:
        d["var88"] = 0
        d["var89"] = 0
    if version >= 130:
        d["var90"] = 0
    if version >= 131:
        d["var91"] = 0
    if version >= 132:
        d["var92"] = 0
        d["var93"] = 0
        d["var94"] = 0
        d["var95"] = 0
    if version >= 134:
        d["var96"] = 0
    if version >= 136:
        d["var97"] = 0
    if version >= 137:
        d["var98"] = 0
        d["var99"] = 0
        d["var100"] = 0
        d["var101"] = 0
        d["vars2"] = [0] * 24

    if version >= 0x8A:
        d["var102"] = 0
        d["var103"] = 0
        d["var104"] = 0
        d["var105"] = 0
        d["md10"] = b""
        d["var106"] = 0
        d["mds2"] = []

    if version < 0x8D:
        return d

    for k in ("var107", "var108", "var109", "var110", "var111", "var112", "var113",
               "var114", "var115", "var116", "var117", "var118", "var119", "var120"):
        d[k] = 0
    d["bytes"] = bytes(0x100)
    d["var121"] = 0
    d["var122"] = 0

    if version < 0x8E:
        return d
    d["var123"] = 0
    return d


# ---------------------------------------------------------------------------
# SavePart3 - variáveis normais (inteiras) e variáveis de texto
# ---------------------------------------------------------------------------

def _read_save_part3(r: ByteReader, version: int) -> dict:
    d: Dict[str, Any] = {
        "var1": 0, "var2": 0, "vars1": [], "vars2": [], "vars3": [],
        "var3": 0, "vars4": [], "vars5": [],
        "var4": 0, "mds1Old": [], "mds1New": [],
        "var5": 0, "vars6": [], "vars7": [],
        "var6": 0, "vars8": [], "mds2Old": [], "mds2New": [],
    }
    d["var1"] = r.u32()
    d["var2"] = r.u32()

    if _as_i32(d["var2"]) >= 0:
        for _ in range(d["var2"]):
            v1 = r.u32()
            if _as_i32(v1) < 0:
                raise ValueError("Wolf save: SavePart3 corrompido (grupo de variáveis)")
            d["vars1"].append(v1)
            for _ in range(v1):
                v2 = r.u8()
                d["vars2"].append(v2)
                for _ in range(v2):
                    d["vars3"].append(r.u32())

        d["var3"] = r.u32()

        if d["var3"] <= 0x270F:
            if _as_i32(d["var3"]) > 0:
                for _ in range(d["var3"]):
                    v = r.u32()
                    if _as_i32(v) < 0:
                        raise ValueError("Wolf save: SavePart3 corrompido (var4)")
                    d["vars4"].append(v)
                    for _ in range(v):
                        d["vars5"].append(r.u32())

            d["var4"] = r.u32()

            if _as_i32(d["var4"]) >= 0:
                width = 2 if version < 0x6F else 4
                for _ in range(d["var4"]):
                    md = _read_memdata(r, width)
                    (d["mds1Old"] if version < 0x6F else d["mds1New"]).append(md)

                d["var5"] = r.u32()
                if _as_i32(d["var5"]) < 0 or d["var5"] > 10000:
                    raise ValueError("Wolf save: SavePart3 corrompido (var5)")

                for _ in range(d["var5"]):
                    v = r.u8()
                    d["vars6"].append(v)
                    for _ in range(v):
                        d["vars7"].append(r.u32())

                d["var6"] = r.u32()
                if d["var6"] <= 10000:
                    if _as_i32(d["var6"]) <= 0:
                        raise ValueError("Wolf save: SavePart3 corrompido (var6)")
                    width2 = 2 if version < 0x6F else 4
                    target = d["mds2Old"] if version < 0x6F else d["mds2New"]
                    for _ in range(d["var6"]):
                        v = r.u8()
                        d["vars8"].append(v)
                        if v:
                            for _ in range(v):
                                target.append(_read_memdata(r, width2))
    return d


def _write_save_part3(w: ByteWriter, d: dict, version: int):
    w.u32(d["var1"])
    w.u32(d["var2"])

    if _as_i32(d["var2"]) >= 0:
        it2 = iter(d["vars2"])
        it3 = iter(d["vars3"])
        for v1 in d["vars1"]:
            w.u32(v1)
            for _ in range(v1):
                v2 = next(it2)
                w.u8(v2)
                for _ in range(v2):
                    w.u32(next(it3))

        w.u32(d["var3"])

        if d["var3"] <= 0x270F:
            if _as_i32(d["var3"]) > 0:
                it5 = iter(d["vars5"])
                for v in d["vars4"]:
                    w.u32(v)
                    for _ in range(v):
                        w.u32(next(it5))

            w.u32(d["var4"])

            if _as_i32(d["var4"]) >= 0:
                width = 2 if version < 0x6F else 4
                mds = d["mds1Old"] if version < 0x6F else d["mds1New"]
                for md in mds:
                    _write_memdata(w, md, width)

                w.u32(d["var5"])

                it7 = iter(d["vars7"])
                for v in d["vars6"]:
                    w.u8(v)
                    for _ in range(v):
                        w.u32(next(it7))

                w.u32(d["var6"])
                if d["var6"] <= 10000:
                    width2 = 2 if version < 0x6F else 4
                    mds2 = d["mds2Old"] if version < 0x6F else d["mds2New"]
                    it_mds2 = iter(mds2)
                    for v in d["vars8"]:
                        w.u8(v)
                        if v:
                            for _ in range(v):
                                _write_memdata(w, next(it_mds2), width2)


def _default_save_part3(version: int) -> dict:
    return {
        "var1": 0, "var2": 0, "vars1": [], "vars2": [], "vars3": [],
        "var3": 0, "vars4": [], "vars5": [],
        "var4": 0, "mds1Old": [], "mds1New": [],
        "var5": 0, "vars6": [], "vars7": [],
        "var6": 0xFFFFFFFF, "vars8": [], "mds2Old": [], "mds2New": [],
    }


# ---------------------------------------------------------------------------
# SavePart4 - semântica desconhecida, preservado estruturalmente (reusa SavePart1_1)
# ---------------------------------------------------------------------------

def _read_save_part4(r: ByteReader, version: int) -> dict:
    d: Dict[str, Any] = {}
    d["sp1_1_base"] = _read_sp1_1(r, version)
    d["var1"] = r.u32()
    d["savePart1_1s"] = [_read_sp1_1(r, version) for _ in range(d["var1"])]
    d["var2"] = r.u8()
    d["var3"] = r.u8()
    d["var4"] = r.u32()
    d["vars1"] = [r.u32() for _ in range(d["var4"])] if _as_i32(d["var4"]) > 0 else []

    if version < 0x8A:
        return d

    d["var5"] = r.u32()
    d["vars2"] = [r.u64() for _ in range(d["var5"])] if _as_i32(d["var5"]) > 0 else []
    return d


def _write_save_part4(w: ByteWriter, d: dict, version: int):
    _write_sp1_1(w, d["sp1_1_base"], version)
    w.u32(d["var1"])
    for sp in d["savePart1_1s"]:
        _write_sp1_1(w, sp, version)
    w.u8(d["var2"])
    w.u8(d["var3"])
    w.u32(d["var4"])
    if _as_i32(d["var4"]) > 0:
        for v in d["vars1"]:
            w.u32(v)

    if version < 0x8A:
        return

    w.u32(d["var5"])
    if _as_i32(d["var5"]) > 0:
        for v in d["vars2"]:
            w.u64(v)


def _default_save_part4(version: int) -> dict:
    return {
        "sp1_1_base": _default_sp1_1(version),
        "var1": 0, "savePart1_1s": [],
        "var2": 0, "var3": 0,
        "var4": 0, "vars1": [],
        "var5": 0, "vars2": [],
    }


# ---------------------------------------------------------------------------
# SavePart5 - semântica desconhecida, preservado estruturalmente
# ---------------------------------------------------------------------------

_SP5_1_U32_BLOCK_A = ["var19", "var20", "var21", "var22", "var23", "var24", "var25",
                       "var26", "var27", "var28", "var29", "var30", "var31", "var32",
                       "var33", "var34", "var35", "var36"]
_SP5_1_U32_BLOCK_B = ["var64", "var65", "var66", "var67", "var68", "var69", "var70",
                       "var71", "var72", "var73", "var74", "var75", "var76", "var77",
                       "var78", "var79", "var80", "var81", "var82", "var83", "var84"]


def _read_sp5_1(r: ByteReader, version: int) -> dict:
    d: Dict[str, Any] = {}
    d["var1"] = r.u32()
    d["var2"] = r.u8()
    d["var3"] = r.u8()
    d["var4"] = r.u16()
    d["var5"] = r.u8()
    d["var6"] = r.u8()
    d["md1"] = _read_memdata(r, 2)
    d["var7"] = r.u32()
    d["var8"] = r.u32()
    d["var9"] = r.u32()
    d["var10"] = r.u32()
    d["var11"] = r.u32()
    d["var12"] = r.u32()
    d["var13"] = r.u32()
    d["var14"] = r.u32()
    d["var15"] = r.u32()
    d["var16"] = r.u32()
    d["var17"] = r.u32()
    d["var18"] = r.u32()
    d["vals1"] = [r.u32() for _ in range(6)]

    if version >= 0x69:
        for k in _SP5_1_U32_BLOCK_A:
            d[k] = r.u32()
    if version >= 0x6B:
        d["var37"] = r.u8()
    if version >= 0x72:
        d["var38"] = r.u8()
        d["var39"] = r.u8()
        d["vals2"] = [r.u32() for _ in range(4)]
        d["vals3"] = [r.u32() for _ in range(4)]
    if version >= 0x73:
        d["var40"] = r.u32()
        d["var41"] = r.u32()
        d["var42"] = r.u32()
        d["var43"] = r.u32()
        if version >= 0x74:
            d["var44"] = r.u32()
            d["var45"] = r.u32()
            d["var46"] = r.u32()
            d["var47"] = r.u32()
            d["var48"] = r.u32()
        if version >= 0x75:
            d["var49"] = r.u32()
            d["var50"] = r.u32()
            d["var51"] = r.u32()
            d["var52"] = r.u32()
            d["var53"] = r.u32()
            d["var54"] = r.u32()
        d["var55"] = r.u32()
        d["var56"] = r.u32()
        d["var57"] = r.u32()
        d["var58"] = r.u32()
        d["var59"] = r.u32()
        d["var60"] = r.u32()
    if version >= 0x76:
        d["var61"] = r.u32()
        d["var62"] = r.u32()
        d["var63"] = r.u32()

    if version < 0x81:
        return d

    for k in _SP5_1_U32_BLOCK_B:
        d[k] = r.u32()

    if version >= 0x87:
        d["var85"] = r.u32()
        d["var86"] = r.u32()
        d["var87"] = r.u32()
        d["var88"] = r.u32()
        d["var89"] = r.u32()

    if version >= 0x89:
        d["var90"] = r.u32()
        d["vals4"] = []
        d["vals5"] = []
        if _as_i32(d["var90"]) > 0:
            for _ in range(d["var90"]):
                v = r.u32()
                d["vals4"].append(v)
                if _as_i32(v) > 0:
                    for _ in range(v):
                        d["vals5"].append(r.u32())
        d["var91"] = r.u32()
        d["var92"] = r.u32()
        d["var93"] = r.u32()
        d["var94"] = r.u32()
        d["var95"] = r.u32()
        d["var96"] = r.u32()
        d["var97"] = r.u32()

    return d


def _write_sp5_1(w: ByteWriter, d: dict, version: int):
    w.u32(d["var1"])
    w.u8(d["var2"])
    w.u8(d["var3"])
    w.u16(d["var4"])
    w.u8(d["var5"])
    w.u8(d["var6"])
    _write_memdata(w, d["md1"], 2)
    w.u32(d["var7"]); w.u32(d["var8"]); w.u32(d["var9"]); w.u32(d["var10"])
    w.u32(d["var11"]); w.u32(d["var12"]); w.u32(d["var13"]); w.u32(d["var14"])
    w.u32(d["var15"]); w.u32(d["var16"]); w.u32(d["var17"]); w.u32(d["var18"])
    for v in d["vals1"]:
        w.u32(v)

    if version >= 0x69:
        for k in _SP5_1_U32_BLOCK_A:
            w.u32(d[k])
    if version >= 0x6B:
        w.u8(d["var37"])
    if version >= 0x72:
        w.u8(d["var38"])
        w.u8(d["var39"])
        for v in d["vals2"]:
            w.u32(v)
        for v in d["vals3"]:
            w.u32(v)
    if version >= 0x73:
        w.u32(d["var40"]); w.u32(d["var41"]); w.u32(d["var42"]); w.u32(d["var43"])
        if version >= 0x74:
            w.u32(d["var44"]); w.u32(d["var45"]); w.u32(d["var46"])
            w.u32(d["var47"]); w.u32(d["var48"])
        if version >= 0x75:
            w.u32(d["var49"]); w.u32(d["var50"]); w.u32(d["var51"])
            w.u32(d["var52"]); w.u32(d["var53"]); w.u32(d["var54"])
        w.u32(d["var55"]); w.u32(d["var56"]); w.u32(d["var57"])
        w.u32(d["var58"]); w.u32(d["var59"]); w.u32(d["var60"])
    if version >= 0x76:
        w.u32(d["var61"]); w.u32(d["var62"]); w.u32(d["var63"])

    if version < 0x81:
        return

    for k in _SP5_1_U32_BLOCK_B:
        w.u32(d[k])

    if version >= 0x87:
        w.u32(d["var85"]); w.u32(d["var86"]); w.u32(d["var87"])
        w.u32(d["var88"]); w.u32(d["var89"])

    if version >= 0x89:
        w.u32(d["var90"])
        if _as_i32(d["var90"]) > 0:
            it5 = iter(d["vals5"])
            for v in d["vals4"]:
                w.u32(v)
                if _as_i32(v) > 0:
                    for _ in range(v):
                        w.u32(next(it5))
        w.u32(d["var91"]); w.u32(d["var92"]); w.u32(d["var93"])
        w.u32(d["var94"]); w.u32(d["var95"]); w.u32(d["var96"]); w.u32(d["var97"])


def _default_sp5_1(version: int) -> dict:
    d: Dict[str, Any] = {
        "var1": 0, "var2": 0, "var3": 0, "var4": 0, "var5": 0, "var6": 0,
        "md1": b"",
        "var7": 0, "var8": 0, "var9": 0, "var10": 0, "var11": 0, "var12": 0,
        "var13": 0, "var14": 0, "var15": 0, "var16": 0, "var17": 0, "var18": 0,
        "vals1": [0] * 6,
    }
    if version >= 0x69:
        for k in _SP5_1_U32_BLOCK_A:
            d[k] = 0
    if version >= 0x6B:
        d["var37"] = 0
    if version >= 0x72:
        d["var38"] = 0
        d["var39"] = 0
        d["vals2"] = [0] * 4
        d["vals3"] = [0] * 4
    if version >= 0x73:
        for k in ("var40", "var41", "var42", "var43"):
            d[k] = 0
        if version >= 0x74:
            for k in ("var44", "var45", "var46", "var47", "var48"):
                d[k] = 0
        if version >= 0x75:
            for k in ("var49", "var50", "var51", "var52", "var53", "var54"):
                d[k] = 0
        for k in ("var55", "var56", "var57", "var58", "var59", "var60"):
            d[k] = 0
    if version >= 0x76:
        d["var61"] = 0
        d["var62"] = 0
        d["var63"] = 0
    if version < 0x81:
        return d
    for k in _SP5_1_U32_BLOCK_B:
        d[k] = 0
    if version >= 0x87:
        for k in ("var85", "var86", "var87", "var88", "var89"):
            d[k] = 0
    if version >= 0x89:
        d["var90"] = 0
        d["vals4"] = []
        d["vals5"] = []
        for k in ("var91", "var92", "var93", "var94", "var95", "var96", "var97"):
            d[k] = 0
    return d


def _read_save_part5(r: ByteReader, version: int) -> dict:
    d: Dict[str, Any] = {}
    d["var1"] = r.u16()
    d["items"] = []
    if (d["var1"] & 0x8000) == 0:
        d["items"] = [_read_sp5_1(r, version) for _ in range(d["var1"])]
    return d


def _write_save_part5(w: ByteWriter, d: dict, version: int):
    w.u16(d["var1"])
    if (d["var1"] & 0x8000) == 0:
        for item in d["items"]:
            _write_sp5_1(w, item, version)


def _default_save_part5(version: int) -> dict:
    return {"var1": 0, "items": []}


# ---------------------------------------------------------------------------
# SavePart7 - semântica desconhecida, preservado estruturalmente
# ---------------------------------------------------------------------------

def _read_save_part7(r: ByteReader) -> dict:
    d: Dict[str, Any] = {"var1": 0, "items": []}
    d["var1"] = r.u8()
    if d["var1"] != 1:
        return d
    d["var2"] = r.u32()
    for _ in range(d["var2"]):
        v = r.u8()
        if v < 0xFA:
            d["items"].append((v, r.u8(), None))
        else:
            d["items"].append((v, None, r.u32()))
    return d


def _write_save_part7(w: ByteWriter, d: dict):
    w.u8(d["var1"])
    if d["var1"] != 1:
        return
    w.u32(d["var2"])
    for v, b, dw in d["items"]:
        w.u8(v)
        if v < 0xFA:
            w.u8(b)
        else:
            w.u32(dw)


def _default_save_part7() -> dict:
    return {"var1": 0, "items": []}


# ---------------------------------------------------------------------------
# VariableDatabase - estado vivo do "Changeable Database" (CDataBase) do jogo.
# A única seção nomeável (via CDataBase.project). O parse binário em si não depende
# do schema do projeto - apenas a atribuição de nomes amigáveis depende dele.
# ---------------------------------------------------------------------------

def _read_type_data(r: ByteReader, type_config: List[int]) -> List[dict]:
    fields: List[Optional[dict]] = [None] * len(type_config)
    for idx, cfg in enumerate(type_config):
        if cfg < 2000:
            fields[idx] = {"id": idx, "type": 1, "number": r.i32()}
    for idx, cfg in enumerate(type_config):
        if cfg >= 2000:
            fields[idx] = {"id": idx, "type": 2, "string": _read_memdata(r, 4)}
    return fields


def _write_type_data(w: ByteWriter, fields: List[dict], type_config: List[int]):
    for idx, cfg in enumerate(type_config):
        if cfg < 2000:
            w.i32(fields[idx]["number"])
    for idx, cfg in enumerate(type_config):
        if cfg >= 2000:
            _write_memdata(w, fields[idx]["string"], 4)


def _read_variable_type(r: ByteReader) -> dict:
    d: Dict[str, Any] = {}
    unknown = r.i32()
    d["unknown"] = unknown
    field_count = unknown
    d["dis"] = 0
    if unknown <= -1:
        if unknown <= -2:
            d["dis"] = r.i32()
        field_count = r.u32()
        d["fieldCount"] = field_count
    d["typeConfig"] = [r.u32() for _ in range(field_count)] if field_count > 0 else []
    d["typeDataCount"] = r.u32()
    d["rows"] = [_read_type_data(r, d["typeConfig"]) for _ in range(d["typeDataCount"])]
    return d


def _write_variable_type(w: ByteWriter, d: dict):
    w.i32(d["unknown"])
    if d["unknown"] <= -1:
        if d["unknown"] <= -2:
            w.i32(d["dis"])
        w.u32(d["fieldCount"])
    if len(d["typeConfig"]) > 0:
        for v in d["typeConfig"]:
            w.u32(v)
    w.u32(d["typeDataCount"])
    for row in d["rows"]:
        _write_type_data(w, row, d["typeConfig"])


def _default_variable_type() -> dict:
    return {"unknown": 0, "dis": 0, "typeConfig": [], "typeDataCount": 0, "rows": []}


def _read_variable_database(r: ByteReader) -> dict:
    d: Dict[str, Any] = {}
    d["unknown"] = r.u8()
    d["typeCount"] = r.u32()
    d["types"] = [_read_variable_type(r) for _ in range(d["typeCount"])]
    return d


def _write_variable_database(w: ByteWriter, d: dict):
    w.u8(d["unknown"])
    w.u32(d["typeCount"])
    for t in d["types"]:
        _write_variable_type(w, t)


def _default_variable_database() -> dict:
    return {"unknown": 0, "typeCount": 0, "types": []}


# ---------------------------------------------------------------------------
# Palavras-chave para as heurísticas de melhor esforço (ver limitações no topo do arquivo)
# ---------------------------------------------------------------------------

_GOLD_KEYWORDS = ["所持金", "gold", "money", "お金"]
_STEPS_KEYWORDS = ["歩数", "steps", "step count"]
_ACTOR_KEYWORDS = ["アクター", "キャラクター", "actor", "character"]
_QUANTITY_KEYWORDS = ["数", "qty", "quantity", "count", "個数"]
_INVENTORY_KEYWORDS = {
    "items": ["アイテム", "item"],
    "weapons": ["武器", "weapon"],
    "armors": ["防具", "armor", "armour"],
}
_ACTOR_STAT_FIELDS = {
    "hp": ["hp", "体力"], "max_hp": ["maxhp", "最大hp", "最大体力"],
    "mp": ["mp", "魔力"], "max_mp": ["maxmp", "最大mp"],
    "atk": ["atk", "攻撃"], "def": ["def", "防御"],
}


class WolfAdapter(BaseSaveAdapter):
    """
    Adaptador experimental para saves do Wolf RPG Editor (.sav). Leia o docstring do módulo
    para as limitações conhecidas antes de confiar nos dados expostos por este adaptador.
    """

    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self.engine_name = "Wolf RPG Editor"
        self.compression = "wolf_xor"
        self.header = bytearray(20)
        self.header[6] = 0x55  # flag de encoding: UTF-8 por padrão para saves construídos do zero
        self.encoding = "utf-8"
        self.game_name = ""
        self.file_version = HIGHEST_SUPPORTED_VERSION
        self.save_part1 = _default_save_part1(self.file_version)
        self.save_part2 = _default_save_part2(self.file_version)
        self.save_part3 = _default_save_part3(self.file_version)
        self.save_part4 = _default_save_part4(self.file_version)
        self.save_part5 = _default_save_part5(self.file_version)
        self.variable_database = _default_variable_database()
        self.save_part7 = _default_save_part7()
        self._rebuild_raw_data()

    def _rebuild_raw_data(self):
        self.raw_data = {
            "header": {
                "game_name": self.game_name,
                "file_version": self.file_version,
                "encoding": self.encoding,
            },
            "SavePart1": self.save_part1,
            "SavePart2": self.save_part2,
            "SavePart3": self.save_part3,
            "SavePart4": self.save_part4,
            "SavePart5": self.save_part5,
            "VariableDatabase": self.variable_database,
            "SavePart7": self.save_part7,
        }

    # --- Carregamento e escrita -------------------------------------------------

    def load(self, path: Path | str) -> Any:
        self.file_path = Path(path).resolve()
        raw = self.file_path.read_bytes()
        info = try_parse_wolf_header(raw)
        if info is None:
            raise ValueError(
                "O arquivo não é um save válido do Wolf RPG Editor no esquema de criptografia "
                "XOR simples suportado (pode ser outro formato, estar corrompido, ou usar o "
                "esquema de criptografia mais forte do Wolf RPG Pro, que não é suportado)."
            )

        self.header = info.decrypted[:START_OFFSET]
        self.encoding = info.encoding
        self.game_name = info.game_name
        self.file_version = info.file_version

        r = ByteReader(bytes(info.decrypted), info.body_start)
        self.save_part1 = _read_save_part1(r, self.file_version)
        self.save_part2 = _read_save_part2(r, self.file_version)
        self.save_part3 = _read_save_part3(r, self.file_version)
        self.save_part4 = _read_save_part4(r, self.file_version)
        self.save_part5 = _read_save_part5(r, self.file_version)
        self.variable_database = _read_variable_database(r)
        self.save_part7 = _read_save_part7(r)

        if r.pos != len(info.decrypted) - 1:
            raise ValueError(
                "Wolf RPG Editor: a leitura do save terminou numa posição inesperada "
                f"({r.pos} != {len(info.decrypted) - 1}) - o parser pode estar desatualizado "
                "em relação à versão do formato usada por este jogo."
            )
        end_byte = r.u8()
        if end_byte != 0x19:
            raise ValueError(
                f"Wolf RPG Editor: byte final inválido (esperado 0x19, obtido 0x{end_byte:02x})."
            )

        self._rebuild_raw_data()
        self.clear_pending_changes()
        return self.raw_data

    def save(self, dst: Path | str, backup: bool = True) -> bool:
        dst_path = Path(dst).resolve()
        if backup:
            self.create_backup_if_needed(dst_path)

        w = ByteWriter()
        w.raw(bytes(self.header))
        w.u8(0x19)
        _write_memdata(w, _encode_wolf_string(self.game_name, self.encoding), 2)
        w.u16(self.file_version)

        _write_save_part1(w, self.save_part1, self.file_version)
        _write_save_part2(w, self.save_part2, self.file_version)
        _write_save_part3(w, self.save_part3, self.file_version)
        _write_save_part4(w, self.save_part4, self.file_version)
        _write_save_part5(w, self.save_part5, self.file_version)
        _write_variable_database(w, self.variable_database)
        _write_save_part7(w, self.save_part7)
        w.u8(0x19)

        buf = bytearray(w.getvalue())
        checksum = sum(buf[START_OFFSET:]) & 0xFF
        buf[2] = checksum
        _xor_crypt(buf, start=START_OFFSET)

        dst_path.write_bytes(bytes(buf))
        self.clear_pending_changes()
        return True

    # --- Acesso auxiliar à VariableDatabase (usado pelas heurísticas abaixo) ---

    def _locate_wolf_field(self, keywords: List[str]) -> Optional[Tuple[int, int]]:
        """Retorna (type_idx, field_idx) do primeiro campo cujo nome resolvido (via
        CDataBase.project, exposto em self.db.wolf_types) contém uma das palavras-chave.
        Note que o schema do projeto não diz se o campo é numérico ou texto - isso é uma
        propriedade do próprio save (typeConfig), resolvida em _get_wolf_row_field."""
        wolf_types = getattr(self.db, "wolf_types", None) if self.db else None
        if not wolf_types:
            return None
        kws = [k.lower() for k in keywords]
        for type_idx, info in wolf_types.items():
            for field in info.get("fields", []):
                name = (field.get("name") or "").lower()
                if name and any(k in name for k in kws):
                    return (int(type_idx), int(field["index"]))
        return None

    def _get_wolf_row_field(self, type_idx: int, row_idx: int, field_idx: int) -> Optional[dict]:
        types = self.variable_database.get("types", [])
        if type_idx >= len(types):
            return None
        rows = types[type_idx].get("rows", [])
        if row_idx >= len(rows):
            return None
        row = rows[row_idx]
        if field_idx >= len(row) or row[field_idx] is None:
            return None
        return row[field_idx]

    def _set_wolf_row_field(self, type_idx: int, row_idx: int, field_idx: int,
                             value: Any, is_string: bool) -> bool:
        field = self._get_wolf_row_field(type_idx, row_idx, field_idx)
        if field is None:
            return False
        if is_string:
            field["string"] = _encode_wolf_string(str(value), self.encoding)
        else:
            field["number"] = int(value)
        return True

    # --- Ouro / tempo de jogo (melhor esforço) ----------------------------------

    def get_gold(self) -> int:
        loc = self._locate_wolf_field(_GOLD_KEYWORDS)
        if not loc:
            return 0
        field = self._get_wolf_row_field(loc[0], 0, loc[1])
        if not field or field.get("type") != 1:
            return 0
        return int(field["number"])

    def set_gold(self, amount: int) -> bool:
        loc = self._locate_wolf_field(_GOLD_KEYWORDS)
        if not loc:
            return False
        field = self._get_wolf_row_field(loc[0], 0, loc[1])
        if not field or field.get("type") != 1:
            return False
        ok = self._set_wolf_row_field(loc[0], 0, loc[1], max(0, int(amount)), False)
        if ok:
            self.mark_dirty(f"Ouro (melhor esforço) definido para {amount:,}")
        return ok

    def get_playtime_and_steps(self) -> Tuple[str, int]:
        steps = 0
        loc = self._locate_wolf_field(_STEPS_KEYWORDS)
        if loc:
            field = self._get_wolf_row_field(loc[0], 0, loc[1])
            if field and field.get("type") == 1:
                steps = int(field["number"])
        return "N/A", steps

    # --- Atores (melhor esforço) -------------------------------------------------

    def get_actors(self) -> List[Dict[str, Any]]:
        wolf_types = getattr(self.db, "wolf_types", None) if self.db else None
        if not wolf_types:
            return []
        for type_idx, info in wolf_types.items():
            name = (info.get("name") or "").lower()
            if any(k.lower() in name for k in _ACTOR_KEYWORDS):
                return self._rows_as_actors(int(type_idx), info)
        return []

    def _rows_as_actors(self, type_idx: int, info: dict) -> List[Dict[str, Any]]:
        results = []
        types = self.variable_database.get("types", [])
        if type_idx >= len(types):
            return results
        rows_meta = info.get("rows", [])
        rows_data = types[type_idx].get("rows", [])
        fields = info.get("fields", [])
        for row_idx, row in enumerate(rows_data):
            name = rows_meta[row_idx]["name"] if row_idx < len(rows_meta) else f"Ator #{row_idx}"
            stats = {"id": row_idx, "name": name, "level": 1, "hp": 0, "max_hp": 0, "mp": 0,
                     "max_mp": 0, "tp": 0, "atk": 0, "def": 0, "mat": 0, "mdf": 0, "agi": 0,
                     "luk": 0, "exp": 0, "raw": row}
            for stat_key, kws in _ACTOR_STAT_FIELDS.items():
                for field in fields:
                    fname = (field.get("name") or "").lower()
                    if any(k in fname for k in kws):
                        fidx = field["index"]
                        if fidx < len(row) and row[fidx] and "number" in row[fidx]:
                            stats[stat_key] = row[fidx]["number"]
                        break
            results.append(stats)
        return results

    def update_actor(self, actor_id: int | str, stats: Dict[str, Any]) -> bool:
        wolf_types = getattr(self.db, "wolf_types", None) if self.db else None
        if not wolf_types:
            return False
        try:
            row_idx = int(actor_id)
        except Exception:
            return False
        for type_idx, info in wolf_types.items():
            name = (info.get("name") or "").lower()
            if not any(k.lower() in name for k in _ACTOR_KEYWORDS):
                continue
            changed = False
            for stat_key, kws in _ACTOR_STAT_FIELDS.items():
                if stat_key not in stats:
                    continue
                for field in info.get("fields", []):
                    fname = (field.get("name") or "").lower()
                    if any(k in fname for k in kws):
                        if self._set_wolf_row_field(int(type_idx), row_idx, field["index"],
                                                      stats[stat_key], False):
                            changed = True
                        break
            if changed:
                self.mark_dirty(f"Ator {actor_id} atualizado (melhor esforço)")
            return changed
        return False

    # --- Inventário (melhor esforço) --------------------------------------------

    def get_inventory(self, kind: str = "items") -> List[Dict[str, Any]]:
        wolf_types = getattr(self.db, "wolf_types", None) if self.db else None
        if not wolf_types or kind not in _INVENTORY_KEYWORDS:
            return []
        kws = [k.lower() for k in _INVENTORY_KEYWORDS[kind]]
        for type_idx, info in wolf_types.items():
            name = (info.get("name") or "").lower()
            if any(k in name for k in kws):
                return self._rows_as_inventory(int(type_idx), info, kind)
        return []

    def _rows_as_inventory(self, type_idx: int, info: dict, kind: str) -> List[Dict[str, Any]]:
        results = []
        types = self.variable_database.get("types", [])
        if type_idx >= len(types):
            return results
        rows_meta = info.get("rows", [])
        rows_data = types[type_idx].get("rows", [])
        qty_fields = [f for f in info.get("fields", [])
                      if any(k in (f.get("name") or "").lower() for k in _QUANTITY_KEYWORDS)]
        for row_idx, row in enumerate(rows_data):
            name = rows_meta[row_idx]["name"] if row_idx < len(rows_meta) else f"{kind} #{row_idx}"
            qty = 1
            if qty_fields:
                fidx = qty_fields[0]["index"]
                if fidx < len(row) and row[fidx] and "number" in row[fidx]:
                    qty = row[fidx]["number"]
            results.append({"id": str(row_idx), "name": name, "quantity": qty, "kind": kind})
        return results

    def set_item_quantity(self, kind: str, item_id: int | str, qty: int) -> bool:
        wolf_types = getattr(self.db, "wolf_types", None) if self.db else None
        if not wolf_types or kind not in _INVENTORY_KEYWORDS:
            return False
        try:
            row_idx = int(item_id)
        except Exception:
            return False
        kws = [k.lower() for k in _INVENTORY_KEYWORDS[kind]]
        for type_idx, info in wolf_types.items():
            name = (info.get("name") or "").lower()
            if not any(k in name for k in kws):
                continue
            qty_fields = [f for f in info.get("fields", [])
                          if any(k in (f.get("name") or "").lower() for k in _QUANTITY_KEYWORDS)]
            if not qty_fields:
                return False
            ok = self._set_wolf_row_field(int(type_idx), row_idx, qty_fields[0]["index"], qty, False)
            if ok:
                self.mark_dirty(f"{kind} {item_id} (melhor esforço) definido para {qty}")
            return ok
        return False

    def unlock_all_items(self, kind: str = "items", qty: int = 99) -> int:
        count = 0
        for it in self.get_inventory(kind):
            if self.set_item_quantity(kind, it["id"], qty):
                count += 1
        if count:
            self.mark_dirty(f"{count} {kind} (melhor esforço) desbloqueados")
        return count

    # --- Switches: sem suporte por design (ver docstring do módulo) ------------

    def get_switches(self) -> List[Dict[str, Any]]:
        return []

    def set_switch(self, switch_id: int, state: bool) -> bool:
        return False

    # --- Variáveis (melhor esforço, a partir de SavePart3) ----------------------

    def get_variables(self) -> List[Dict[str, Any]]:
        results = []
        vars3 = self.save_part3.get("vars3", [])
        for idx, val in enumerate(vars3):
            results.append({"id": idx, "name": f"Variável #{idx}", "value": val})

        base = len(vars3)
        key = "mds1New" if self.file_version >= 0x6F else "mds1Old"
        for i, raw in enumerate(self.save_part3.get(key, [])):
            results.append({
                "id": base + i,
                "name": f"Variável (texto) #{base + i}",
                "value": _decode_wolf_string(raw, self.encoding),
            })
        return results

    def set_variable(self, var_id: int, value: Any) -> bool:
        var_id = int(var_id)
        vars3 = self.save_part3.get("vars3", [])
        if 0 <= var_id < len(vars3):
            try:
                vars3[var_id] = int(value) & 0xFFFFFFFF
            except Exception:
                return False
            self.mark_dirty(f"Variável {var_id} -> {value}")
            return True

        base = len(vars3)
        key = "mds1New" if self.file_version >= 0x6F else "mds1Old"
        str_list = self.save_part3.get(key, [])
        idx = var_id - base
        if 0 <= idx < len(str_list):
            str_list[idx] = _encode_wolf_string(str(value), self.encoding)
            self.mark_dirty(f"Variável (texto) {var_id} -> {value}")
            return True
        return False
