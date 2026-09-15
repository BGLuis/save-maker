#!/usr/bin/env python3
"""
Exportador RPGSave -> JSON (Versão Tolerante a Falhas)
"""
import argparse
import json
import gzip
import zlib
import base64
import traceback
from pathlib import Path

try:
    from lzstring import LZString
    _LZSTRING = LZString()
except Exception:
    _LZSTRING = None

def read_bytes(path: Path) -> bytes:
    return path.read_bytes()

def try_decompress(data: bytes):
    # Debug: Mostra os primeiros bytes para diagnóstico
    header_hex = data[:4].hex()
    print(f"[Debug] Header do arquivo: {header_hex} (Tamanho total: {len(data)} bytes)")

    # 1. Tenta GZIP
    if len(data) >= 2 and data[0] == 0x1f and data[1] == 0x8b:
        try:
            return gzip.decompress(data), "gzip"
        except Exception as e:
            print(f"[Debug] Falha GZIP: {e}")

    # 2. Tenta ZLIB (Modo Stream/Tolerante)
    # Isso resolve o problema de arquivos com bytes extras no final
    try:
        # zlib.decompressobj permite descomprimir fluxos parciais ou com lixo no final
        do = zlib.decompressobj()
        decompressed = do.decompress(data)
        if decompressed:
            print(f"[Debug] Sucesso ZLIB Stream! (Sobrou {len(do.unused_data)} bytes de lixo no final)")
            return decompressed, "zlib"
    except Exception as e:
        print(f"[Debug] Falha ZLIB Stream: {e}")

    # 3. Tenta ZLIB Raw (sem cabeçalho)
    try:
        do = zlib.decompressobj(wbits=-zlib.MAX_WBITS)
        decompressed = do.decompress(data)
        if decompressed:
            return decompressed, "raw-zlib"
    except Exception:
        pass

    return data, "none"

def try_parse_json(bytes_data: bytes):
    try:
        # Remove BOM se existir e decodifica
        text = bytes_data.decode("utf-8-sig")
        return json.loads(text)
    except Exception as e:
        print(f"[Debug] Falha ao converter bytes para JSON: {e}")
        # Tenta mostrar o início do conteúdo para ver se está encriptado
        try:
            sample = bytes_data[:50].decode('utf-8', errors='ignore')
            print(f"[Debug] Amostra do conteúdo descomprimido: {sample}...")
        except:
            pass
        return None

def export_rpgsave(src: Path, dst: Path):
    print(f"--- Processando: {src.name} ---")
    b = read_bytes(src)
    decompressed, compression = try_decompress(b)

    parsed = try_parse_json(decompressed)

    # Se falhou JSON, verifica se é LZString
    if parsed is None and _LZSTRING:
        try:
            txt = decompressed.decode('utf-8', errors='ignore')
            # LZString geralmente não tem espaços no início
            if not txt.strip().startswith('{'):
                print("[Debug] Tentando descomprimir camada LZString...")
                maybe = _LZSTRING.decompressFromBase64(txt.strip())
                if maybe:
                    parsed2 = json.loads(maybe)
                    parsed = parsed2
                    compression += "+lzstring"
                    print("[Debug] Sucesso LZString!")
        except Exception:
            pass

    out = {
        "source_file": str(src),
        "size": len(b),
        "compression": compression,
        "extension": src.suffix
    }

    if parsed is not None:
        out.update({"format": "json", "data": parsed})
        print(f"Sucesso! JSON salvo com compressão detectada: {compression}")
    else:
        print("ALERTA: O arquivo foi descomprimido mas NÃO é um JSON válido.")
        print("Possibilidades: 1. O save é encriptado (Plugin VisuStella). 2. Formato binário desconhecido.")
        # Salva como texto para inspeção
        try:
            text = decompressed.decode("utf-8")
            out.update({"format": "text", "text": text})
        except:
            b64 = base64.b64encode(decompressed).decode("ascii")
            out.update({"format": "raw", "raw_base64": b64})

    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exportado para: {dst}")
    print("---------------------------------")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    ex = sub.add_parser("export")
    ex.add_argument("src")
    ex.add_argument("dst")
    args = p.parse_args()

    if args.cmd == "export":
        export_rpgsave(Path(args.src), Path(args.dst))
        return 0
    return 1

if __name__ == "__main__":
    main()
