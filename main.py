#!/usr/bin/env python3
"""
Save Maker — Ponto de Entrada Principal (Universal Edition)

Suporta:
  - RPG Maker MV (.rpgsave)
  - RPG Maker MZ (.rmmzsave)
  - RPG Maker VX Ace (.rvdata2)
  - RPG Maker VX (.rvdata)
  - RPG Maker XP (.rxdata)
  - RPG Maker 2000 / 2003 (.lsd)
  - Saves em JSON e Web Saves (.json, .sav, .dat, .txt)

Uso:
  python main.py                     # Inicia a interface gráfica moderna (CustomTkinter)
  python main.py [arquivo_save]      # Inicia a interface já abrindo o save
  python main.py --classic           # Inicia a interface gráfica clássica (Tkinter retro)
  python main.py export <src> <dst>  # Exporta qualquer save de RPG Maker para JSON
  python main.py import <src> <dst>  # Importa JSON para arquivo de save
"""
import os
import sys
import argparse
from pathlib import Path

# Adiciona o diretório scripts ao sys.path
ROOT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
for d in (str(SCRIPTS_DIR), str(ROOT_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)


def main():
    # Se o primeiro argumento for um arquivo existente ou não for um comando de subparser, trata como arquivo para abrir na GUI
    args_list = sys.argv[1:]
    target_file = None
    use_classic = "--classic" in args_list
    if "--classic" in args_list:
        args_list.remove("--classic")

    use_interactive = "--interactive" in args_list or "-i" in args_list
    if "--interactive" in args_list: args_list.remove("--interactive")
    if "-i" in args_list: args_list.remove("-i")

    use_gui = "--gui" in args_list
    if "--gui" in args_list: args_list.remove("--gui")

    if args_list and not args_list[0].startswith("-") and args_list[0] not in ("export", "import", "gui", "cli"):
        target_file = args_list[0]
        args_list = args_list[1:]

    parser = argparse.ArgumentParser(
        description="Save Maker — Editor e Conversor Universal de Saves de RPG Maker (MV, MZ, VX Ace, VX, XP, 2000/2003, JSON)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="cmd")

    # Subcomando CLI interativa
    cli_p = subparsers.add_parser("cli", help="Inicia o modo interativo no terminal (CLI/TUI)")
    cli_p.add_argument("save_file", nargs="?", default=None, help="Arquivo de save para abrir")

    # Subcomando GUI explícito
    gui_p = subparsers.add_parser("gui", help="Inicia a interface gráfica")
    gui_p.add_argument("save_file", nargs="?", default=None, help="Arquivo de save para abrir")

    # Subcomando Export
    ex = subparsers.add_parser("export", help="Exporta qualquer save suportado para JSON")
    ex.add_argument("src", help="Arquivo de save de origem")
    ex.add_argument("dst", help="Arquivo JSON de destino")

    # Subcomando Import
    im = subparsers.add_parser("import", help="Importa JSON de volta para save")
    im.add_argument("src", help="Arquivo JSON de origem")
    im.add_argument("dst", help="Arquivo de save de destino")
    im.add_argument(
        "--compression",
        choices=["gzip", "zlib", "none"],
        default=None,
        help="Forçar compressão de saída (padrão: automático)"
    )
    im.add_argument(
        "--encoding",
        choices=["lzstring", "none"],
        default="none",
        help="Forçar codificação textual lzstring"
    )

    parsed_args = parser.parse_args(args_list)

    if parsed_args.cmd == "export":
        from core.database_manager import GLOBAL_DB
        from core.detector import detect_and_create_adapter

        src_p = Path(parsed_args.src)
        dst_p = Path(parsed_args.dst)

        GLOBAL_DB.discover_and_load(src_p)
        adapter = detect_and_create_adapter(src_p, GLOBAL_DB)
        adapter.load(src_p)

        import json
        out = {
            "engine": adapter.engine_name,
            "compression": adapter.compression,
            "data": adapter.raw_data
        }
        dst_p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✔ Exportado com sucesso: {src_p} -> {dst_p} ({adapter.engine_name})")
        return 0

    elif parsed_args.cmd == "import":
        from import_json_to_rpgsave import import_json
        import_json(
            Path(parsed_args.src),
            Path(parsed_args.dst),
            forced_compression=parsed_args.compression,
            encoding=parsed_args.encoding
        )
        return 0

    target_save = target_file or getattr(parsed_args, "save_file", None)

    # Modo Interativo CLI
    if use_interactive or parsed_args.cmd == "cli":
        from cli.interactive import InteractiveCliSession
        session = InteractiveCliSession(target_save)
        session.start()
        return 0

    if use_classic:
        from gui_rpgsave import main as gui_classic_main
        gui_classic_main()
        return 0

    # Verifica se há display disponível
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    if not has_display and not parsed_args.cmd == "gui":
        # Em ambiente sem display gráfico (ex: SSH / console puro), inicia modo interativo
        print("[Info] Nenhum display gráfico detectado. Iniciando modo interativo no terminal...")
        from cli.interactive import InteractiveCliSession
        session = InteractiveCliSession(target_save)
        session.start()
        return 0

    # GUI Moderna (Padrão)
    try:
        from ui.modern_app import ModernSaveEditorApp
        app = ModernSaveEditorApp()
        if target_save and Path(target_save).is_file():
            app.load_save_file(target_save)
        app.mainloop()
        return 0
    except Exception as e:
        print(f"[Aviso] Falha ao iniciar interface moderna ({e}). Carregando interface clássica...")
        try:
            from gui_rpgsave import main as gui_classic_main
            gui_classic_main()
            return 0
        except Exception:
            # Fallback para CLI interativa
            from cli.interactive import InteractiveCliSession
            session = InteractiveCliSession(target_save)
            session.start()
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
