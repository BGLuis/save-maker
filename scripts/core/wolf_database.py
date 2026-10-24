#!/usr/bin/env python3
"""
wolf_database - Parser do schema do projeto Wolf RPG Editor (Data/BasicData/CDataBase.project)

Resolve nomes amigáveis (tipos, campos e linhas de dados) da "Changeable Database" (CDataBase)
do jogo, usada para rotular o conteúdo da seção VariableDatabase embutida nos saves. Port do
parser de referência Sinflower/WolfSave (Database.h), lido diretamente do código-fonte durante
o desenvolvimento.

Não implementa a leitura dos valores de ".dat" (dados fixos de referência, análogos a
Items.json) - apenas o schema do ".project" (nomes), que é o que basta para rotular o estado
vivo já presente no save. Nunca lança em uso normal de descoberta: falhas retornam None/[]
para que a descoberta de banco de dados degrade graciosamente (nomes numéricos) em vez de
quebrar, seguindo o mesmo padrão já aceito para RPG Maker 2000/2003 (.lsd) no projeto.

LIMITAÇÃO: só o esquema de criptografia mais simples do Wolf RPG (v2 texto puro / v3 XOR de
byte único, com força bruta de chave) é suportado. O Wolf RPG Pro (3.5+) usa criptografia mais
forte (AES/ChaCha20) para arquivos de projeto - não suportado; ver WolfCryptoUnsupportedError.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .wolf_adapter import (
    ByteReader, _decode_wolf_string, _read_memdata, _xor_crypt, _LCG_MUL, _LCG_ADD, _LCG_MASK,
)


class WolfCryptoUnsupportedError(Exception):
    """Levantado quando um arquivo .project não pôde ser descriptografado com o esquema
    XOR simples conhecido - possivelmente usa a criptografia mais forte do Wolf RPG Pro."""


def _srand_from_byte_seed(seed: int) -> int:
    """
    Replica o cast int8_t->unsigned int feito por srand(static_cast<int8_t>(seed)) no C++
    de referência: seeds >= 128 sofrem sign-extension antes de virar o estado do LCG.
    """
    signed = seed - 256 if seed >= 128 else seed
    return signed & _LCG_MASK


def _msvc_rand_byte_stream(seed: int):
    """
    Gera o stream de bytes equivalente a chamadas sucessivas de rand() do MSVC truncadas
    para uint8_t: byte = (next_seed >> 16) & 0xFF. Esquema usado pelos arquivos .project
    (byte cheio), diferente do esquema de 3 bits usado nos saves .sav (ver wolf_adapter.py).
    """
    s = seed & _LCG_MASK
    while True:
        s = (s * _LCG_MUL + _LCG_ADD) & _LCG_MASK
        yield (s >> 16) & 0xFF


def _brute_force_project_seed(header_u32: int) -> Optional[int]:
    """Tenta as 256 seeds possíveis (1 byte) até o typeCount decodificado ser plausível
    (<= 0xFF, mesmo critério usado pelo WolfSave de referência)."""
    header_bytes = header_u32.to_bytes(4, "little")
    for seed in range(256):
        gen = _msvc_rand_byte_stream(_srand_from_byte_seed(seed))
        decoded = bytes(b ^ next(gen) for b in header_bytes)
        type_count = int.from_bytes(decoded, "little")
        if type_count <= 0xFF:
            return seed
    return None


def _decrypt_project_bytes(data: bytes, seed: int) -> bytes:
    gen = _msvc_rand_byte_stream(_srand_from_byte_seed(seed))
    return bytes(b ^ next(gen) for b in data)


def _load_project_plaintext(path: Path) -> Tuple[bytes, str]:
    """Lê e, se necessário, descriptografa um arquivo .project. Retorna (bytes, encoding)."""
    data = path.read_bytes()
    if len(data) < 4:
        raise WolfCryptoUnsupportedError(f"Arquivo .project vazio ou truncado demais: {path}")

    header_u32 = int.from_bytes(data[:4], "little")
    if header_u32 <= 0xFF:
        # Não criptografado: convenção v2 (Shift-JIS)
        return data, "cp932"

    seed = _brute_force_project_seed(header_u32)
    if seed is None:
        raise WolfCryptoUnsupportedError(
            f"Não foi possível determinar a chave de descriptografia de {path} - o jogo pode "
            "usar a criptografia mais forte do Wolf RPG Pro, que não é suportada."
        )
    # Convenção v3 (UTF-8), esquema XOR de byte único
    return _decrypt_project_bytes(data, seed), "utf-8"


def _read_project_type(r: ByteReader) -> Dict[str, Any]:
    name = _read_memdata(r, 4)
    field_count = r.u32()
    field_names = [_read_memdata(r, 4) for _ in range(field_count)]
    data_count = r.u32()
    data_names = [_read_memdata(r, 4) for _ in range(data_count)]
    _description = _read_memdata(r, 4)  # não usado para resolução de nomes

    field_type_list_size = r.u32()
    consumed = 0
    for _ in range(field_count):
        r.u8()
        consumed += 1
    remaining = field_type_list_size - consumed
    if remaining > 0:
        r.raw(remaining)

    unknown1_count = r.u32()
    for _ in range(unknown1_count):
        _read_memdata(r, 4)

    string_args_count = r.u32()
    for _ in range(string_args_count):
        args_cnt = r.u32()
        for _ in range(args_cnt):
            _read_memdata(r, 4)

    numeric_args_count = r.u32()
    for _ in range(numeric_args_count):
        args_cnt = r.u32()
        for _ in range(args_cnt):
            r.u32()

    trailing_count = r.u32()
    for _ in range(trailing_count):
        r.u32()

    return {"name": name, "field_names": field_names, "data_names": data_names}


def parse_wolf_project(path: Path | str) -> List[Dict[str, Any]]:
    """
    Faz o parse de um arquivo CDataBase.project e retorna a lista de tipos na ordem em que
    aparecem no arquivo (mesma ordem/índice usada pela seção VariableDatabase dos saves):
    [{"name": str, "fields": [str, ...], "rows": [str, ...]}, ...]

    Levanta WolfCryptoUnsupportedError se o esquema de criptografia não for reconhecido.
    Outras falhas de parsing (arquivo corrompido/formato inesperado) propagam como exceções
    comuns - o chamador (database_manager.py) é responsável por capturá-las e degradar.
    """
    path = Path(path)
    data, encoding = _load_project_plaintext(path)

    r = ByteReader(data, 0)
    type_count = r.u32()
    types: List[Dict[str, Any]] = []
    for _ in range(type_count):
        raw_type = _read_project_type(r)
        types.append({
            "name": _decode_wolf_string(raw_type["name"], encoding),
            "fields": [_decode_wolf_string(f, encoding) for f in raw_type["field_names"]],
            "rows": [_decode_wolf_string(d, encoding) for d in raw_type["data_names"]],
        })
    return types


def project_types_to_wolf_types(types: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    Converte o resultado de parse_wolf_project() para o formato consumido pelas heurísticas
    de melhor esforço do WolfAdapter (self.db.wolf_types): um dict indexado por índice de tipo,
    cada um com {"name", "fields": [{"index","name"}], "rows": [{"index","name"}]}.
    """
    wolf_types: Dict[int, Dict[str, Any]] = {}
    for type_idx, t in enumerate(types):
        wolf_types[type_idx] = {
            "name": t["name"],
            "fields": [{"index": i, "name": n} for i, n in enumerate(t["fields"])],
            "rows": [{"index": i, "name": n} for i, n in enumerate(t["rows"])],
        }
    return wolf_types


_DAT_MAGIC = b"W\x00\x00OL"
_DAT_MAGIC_NEXT = b"FM\x00"
_DAT_TYPE_SEPARATOR = b"\xfe\xff\xff\xff"
_DAT_STRING_FIELD_START = 2000
_DAT_UTF8_FLAG = 0x55


def _read_dat_names(path: Path) -> List[List[str]]:
    """Lê um .dat do Wolf RPG (DataBase.dat / CDataBase.dat) e devolve, por tipo, o primeiro
    valor de texto de cada linha - onde o editor guarda o nome do registro. Tipos sem campo de
    texto resultam em nomes vazios. O .dat vem em texto puro ou cifrado com o mesmo XOR de 3
    passadas dos saves (sementes nos bytes 0, 3 e 9)."""
    data = bytearray(path.read_bytes())
    if not (data.startswith(_DAT_MAGIC) or data.startswith(b"\x00" + _DAT_MAGIC)):
        _xor_crypt(data, start=0)

    r = ByteReader(bytes(data), 1 if data.startswith(b"\x00" + _DAT_MAGIC) else 0)
    if r.raw(len(_DAT_MAGIC)) != _DAT_MAGIC:
        raise WolfCryptoUnsupportedError(f"Arquivo .dat sem assinatura Wolf após decifrar: {path}")
    encoding = "utf-8" if r.u8() == _DAT_UTF8_FLAG else "cp932"
    if r.raw(len(_DAT_MAGIC_NEXT)) != _DAT_MAGIC_NEXT:
        raise WolfCryptoUnsupportedError(f"Cabeçalho .dat inesperado: {path}")
    r.u8()  # versão do motor

    types: List[List[str]] = []
    for _ in range(r.u32()):
        if r.raw(len(_DAT_TYPE_SEPARATOR)) != _DAT_TYPE_SEPARATOR:
            raise ValueError(f"Separador de tipo ausente em {path} (offset {r.pos})")
        r.u32()
        field_infos = [r.u32() for _ in range(r.u32())]
        int_count = sum(1 for f in field_infos if f < _DAT_STRING_FIELD_START)
        str_count = len(field_infos) - int_count
        names: List[str] = []
        for _ in range(r.u32()):
            for _ in range(int_count):
                r.u32()
            strings = [_decode_wolf_string(_read_memdata(r, 4), encoding) for _ in range(str_count)]
            names.append(strings[0] if strings else "")
        types.append(names)
    return types


def parse_wolf_fixed_database(dat_path: Path | str, project_path: Path | str | None = None) -> List[Dict[str, Any]]:
    """
    Resolve nomes de tipos e linhas do banco fixo (DataBase.dat + DataBase.project), onde o
    Wolf guarda os nomes de itens, armas e armaduras que o save só referencia por índice.
    O nome da linha é o do .project quando preenchido; senão, o primeiro texto do .dat.
    Retorna [{"name": str, "rows": [str, ...]}, ...] na ordem dos tipos do arquivo.
    """
    dat_types = _read_dat_names(Path(dat_path))
    project_types = parse_wolf_project(project_path) if project_path and Path(project_path).is_file() else []

    result: List[Dict[str, Any]] = []
    for idx, dat_rows in enumerate(dat_types):
        project = project_types[idx] if idx < len(project_types) else {"name": "", "rows": []}
        rows = [
            (project["rows"][i] if i < len(project["rows"]) else "") or dat_name
            for i, dat_name in enumerate(dat_rows)
        ]
        result.append({"name": project["name"] or f"Type_{idx}", "rows": rows})
    return result
