#!/usr/bin/env python3
"""
Importador JSON -> .rpgsave / .rmmzsave

Uso:
  python import_json_to_rpgsave.py import path/to/in.json path/to/out.rmmzsave [--compression gzip|zlib|none]

O script espera o JSON gerado pelo exportador.
Suporta compressão LZString se detectada ou solicitada.
"""
import argparse
import json
import gzip
import zlib
import base64
import shutil
from pathlib import Path

try:
    from lzstring import LZString
    _LZSTRING = LZString()
except Exception:
    _LZSTRING = None


def write_bytes(path: Path, data: bytes):
    path.write_bytes(data)


def compress_bytes(data: bytes, compression: str, encoding: str = "none") -> bytes:
    # Se encoding for lzstring, espera-se escrever base64 textual produzido pelo lzstring
    # Isso é comum em saves Web ou alguns saves MZ
    if encoding == "lzstring" or "lzstring" in compression:
        if _LZSTRING is None:
            raise RuntimeError("lzstring not available in environment (pip install lzstring)")
        # data deve ser UTF-8 text do JSON
        text = data.decode("utf-8")
        comp = _LZSTRING.compressToBase64(text)
        # O resultado do lzstring é texto, mas precisamos retornar bytes para compressão posterior ou escrita
        payload_bytes = comp.encode("utf-8")

        # Se a compressão era APENAS lzstring (ou sem compressão binária adicional), retornamos
        # Se for "gzip+lzstring", o gzip será aplicado abaixo no payload_bytes
        if compression in ("lzstring", "none+lzstring"):
            return payload_bytes
    else:
        payload_bytes = data

    comp = compression.lower() if compression else "none"

    if comp == "zlib-utf8":
        raw_z = zlib.compress(payload_bytes)
        return raw_z.decode("latin-1").encode("utf-8")
    if comp == "raw-zlib-utf8":
        co = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        raw_z = co.compress(payload_bytes) + co.flush()
        return raw_z.decode("latin-1").encode("utf-8")

    # Compressão binária (Gzip / Zlib)
    if "gzip" in comp:
        return gzip.compress(payload_bytes)
    elif "zlib" in comp or "raw-zlib" in comp:
        return zlib.compress(payload_bytes)
    else:
        return payload_bytes


def import_json(src: Path, dst: Path | None = None, forced_compression: str = None, encoding: str = "none"):
    js = json.loads(src.read_text(encoding="utf-8-sig"))

    # Suporte a dois formatos:
    # 1) Formato do exportador (com metadados)
    # 2) JSON direto do jogo (payload puro)

    source_compression = js.get("compression", "none") if isinstance(js, dict) else "none"
    # Se o usuário forçou compressão, usamos ela, caso contrário tentamos preservar a original
    compression = forced_compression if forced_compression is not None else source_compression

    enc = encoding if encoding not in ("none", "lzstring") else "utf-8"

    if isinstance(js, dict) and "data" in js and any(k in js for k in ("format", "engine", "compression")):
        fmt = js.get("format", "json")
        if fmt == "json":
            payload = json.dumps(js["data"], ensure_ascii=False, separators=(",", ":")).encode(enc)
        elif fmt in ("raw_text", "text"):
            payload = str(js.get("text", js["data"])).encode(enc)
        elif fmt in ("base64", "raw"):
            b64_val = js.get("raw_base64", js["data"])
            payload = base64.b64decode(b64_val)
        else:
            raise ValueError(f"Formato desconhecido no JSON: {fmt}")
    elif isinstance(js, dict) and "format" in js:
        fmt = js.get("format")
        if fmt == "json":
            payload = json.dumps(js["data"], ensure_ascii=False, separators=(",", ":")).encode(enc)
        elif fmt in ("text", "raw_text"):
            payload = js.get("text", "").encode(enc)
        elif fmt in ("raw", "base64"):
            b64 = js.get("raw_base64", "")
            payload = base64.b64decode(b64)
        else:
            payload = json.dumps(js, ensure_ascii=False, separators=(",", ":")).encode(enc)
    else:
        # Assume que o JSON inteiro é o payload
        payload = json.dumps(js, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    # Determina o destino se omitido
    if dst is None:
        is_mz = isinstance(js, dict) and js.get("engine") == "RPG Maker MZ"
        dst_path = src.with_suffix(".rmmzsave" if is_mz else ".rpgsave")
    else:
        dst_path = Path(dst).resolve()

    # Verifica se precisa aplicar lzstring via flag de encoding ou string de compressão composta
    final_encoding = encoding
    if "+lzstring" in str(source_compression) and encoding == "none":
        final_encoding = "lzstring"

    out_bytes = compress_bytes(payload, compression, encoding=final_encoding)

    if dst_path.exists():
        bak = dst_path.with_suffix(dst_path.suffix + ".bak")
        shutil.copy2(dst_path, bak)
        print(f"Backup do destino criado em: {bak}")

    write_bytes(dst_path, out_bytes)
    print(f"Arquivo escrito: {dst_path} (compression={compression}, encoding={final_encoding})")


def main():
    p = argparse.ArgumentParser(description="Import JSON -> .rpgsave / .rmmzsave")
    sub = p.add_subparsers(dest="cmd")
    im = sub.add_parser("import")
    im.add_argument("src")
    im.add_argument("dst", nargs="?", default=None)
    im.add_argument(
        "--compression",
        choices=["gzip", "zlib", "zlib-utf8", "raw-zlib-utf8", "none"],
        help="Forçar compressão de saída (default: preserva do JSON)",
    )
    im.add_argument("--encoding", choices=["lzstring", "none"], default="none", help="Forçar codificação textual (lzstring)")
    args = p.parse_args()

    if args.cmd == "import":
        import_json(Path(args.src), Path(args.dst), forced_compression=args.compression, encoding=args.encoding)
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
