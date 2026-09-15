#!/usr/bin/env python3
"""
RPG Maker Save Editor - Ponto de Entrada Principal

Uso:
  python main.py                     # Inicia a interface gráfica (GUI)
  python main.py gui                 # Inicia a interface gráfica (GUI)
  python main.py export <src> <dst>  # Exporta .rpgsave/.rmmzsave para JSON
  python main.py import <src> <dst>  # Importa JSON para .rpgsave/.rmmzsave
"""
import sys
import argparse
from pathlib import Path

# Adiciona o diretório scripts ao sys.path
ROOT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def main():
    parser = argparse.ArgumentParser(
        description="Editor e Conversor de Saves para RPG Maker MV e MZ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="cmd")

    # Comando GUI
    subparsers.add_parser("gui", help="Inicia a interface gráfica (padrão se nenhum comando fornecido)")

    # Comando Export
    ex = subparsers.add_parser("export", help="Exporta .rpgsave ou .rmmzsave para JSON")
    ex.add_argument("src", help="Arquivo de save de origem (.rpgsave ou .rmmzsave)")
    ex.add_argument("dst", help="Arquivo JSON de destino")

    # Comando Import
    im = subparsers.add_parser("import", help="Importa JSON de volta para .rpgsave ou .rmmzsave")
    im.add_argument("src", help="Arquivo JSON de origem")
    im.add_argument("dst", help="Arquivo de save de destino")
    im.add_argument(
        "--compression",
        choices=["gzip", "zlib", "none"],
        default=None,
        help="Forçar compressão de saída (padrão: preserva do JSON)"
    )
    im.add_argument(
        "--encoding",
        choices=["lzstring", "none"],
        default="none",
        help="Forçar codificação textual lzstring (comum em saves MV)"
    )

    args = parser.parse_args()

    if args.cmd == "export":
        from export_rpgsave_to_json import export_rpgsave
        export_rpgsave(Path(args.src), Path(args.dst))
        return 0

    elif args.cmd == "import":
        from import_json_to_rpgsave import import_json
        import_json(
            Path(args.src),
            Path(args.dst),
            forced_compression=args.compression,
            encoding=args.encoding
        )
        return 0

    else:
        # Padrão: inicia a GUI
        from gui_rpgsave import main as gui_main
        gui_main()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
