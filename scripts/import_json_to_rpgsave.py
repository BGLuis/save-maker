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

    # Compressão binária (Gzip / Zlib)
    if "gzip" in compression:
        return gzip.compress(payload_bytes)
    elif "zlib" in compression or "raw-zlib" in compression:
        return zlib.compress(payload_bytes)
    else:
        return payload_bytes


def import_json(src: Path, dst: Path, forced_compression: str = None, encoding: str = "none"):
    js = json.loads(src.read_text(encoding="utf-8-sig"))

    # Suporte a dois formatos:
    # 1) Formato do exportador (com metadados)
    # 2) JSON direto do jogo (payload puro)

    source_compression = js.get("compression", "none")
    # Se o usuário forçou compressão, usamos ela, caso contrário tentamos preservar a original
    compression = forced_compression if forced_compression is not None else source_compression

    if "format" in js:
        fmt = js.get("format")
        if fmt == "json":
            # reserialize
            payload = json.dumps(js["data"], ensure_ascii=False).encode("utf-8")
        elif fmt == "text":
            payload = js.get("text", "").encode("utf-8")
        elif fmt == "raw":
            b64 = js.get("raw_base64", "")
            payload = base64.b64decode(b64)
        else:
            # unknown: try to use raw_base64 if present
            if "raw_base64" in js:
                payload = base64.b64decode(js["raw_base64"])
            else:
                # Assume que pode ser um JSON puro
                payload = json.dumps(js, ensure_ascii=False).encode("utf-8")
    else:
        # Assume que o JSON inteiro é o payload
        payload = json.dumps(js, ensure_ascii=False).encode("utf-8")

    # Verifica se precisa aplicar lzstring via flag de encoding ou string de compressão composta
    final_encoding = encoding
    if "+lzstring" in str(source_compression) and encoding == "none":
        final_encoding = "lzstring"

    out_bytes = compress_bytes(payload, compression, encoding=final_encoding)

    if dst.exists():
        bak = dst.with_suffix(dst.suffix + ".bak")
        shutil.copy2(dst, bak)
        print(f"Backup do destino criado em: {bak}")

    write_bytes(dst, out_bytes)
    print(f"Arquivo escrito: {dst} (compression={compression}, encoding={final_encoding})")


def main():
    p = argparse.ArgumentParser(description="Import JSON -> .rpgsave / .rmmzsave")
    sub = p.add_subparsers(dest="cmd")
    im = sub.add_parser("import")
    im.add_argument("src")
    im.add_argument("dst")
    im.add_argument("--compression", choices=["gzip", "zlib", "none"], help="Forçar compressão de saída (default: preserva do JSON)")
    im.add_argument("--encoding", choices=["lzstring","none"], default="none", help="Forçar codificação textual (lzstring)")
    args = p.parse_args()

    if args.cmd == "import":
        import_json(Path(args.src), Path(args.dst), forced_compression=args.compression, encoding=args.encoding)
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
