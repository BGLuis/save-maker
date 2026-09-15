#!/usr/bin/env python3
"""
Interactive CLI (TUI) for RPG Maker Save Editor

Interface interativa de terminal rica e intuitiva utilizando a biblioteca rich.
Permite visualizar e alterar finanças, grupo, heróis, inventário, switches e variáveis
diretamente no terminal sem necessidade de interface gráfica.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.text import Text

# Importa módulos do núcleo
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SCRIPTS_DIR.parent
for d in (str(SCRIPTS_DIR), str(ROOT_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

from core.database_manager import GameDatabaseManager, GLOBAL_DB
from core.detector import detect_and_create_adapter
from core.base_adapter import BaseSaveAdapter

SUPPORTED_EXTS = (".rpgsave", ".rmmzsave", ".rvdata2", ".rvdata", ".rxdata", ".lsd", ".json")


def scan_for_save_files(start_dir: Path | str, max_depth: int = 3) -> List[Path]:
    """Varre o diretório em busca de arquivos de save suportados."""
    base = Path(start_dir).resolve()
    found: List[Path] = []
    if not base.exists():
        return found

    # Se o próprio caminho for um arquivo suportado
    if base.is_file() and base.suffix.lower() in SUPPORTED_EXTS:
        return [base]

    for root, dirs, files in os.walk(base):
        # Limita profundidade
        rel = Path(root).relative_to(base)
        if len(rel.parts) > max_depth:
            dirs.clear()
            continue

        # Ignora pastas ocultas ou de ambiente
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".venv")]

        for f in files:
            p = Path(root) / f
            ext = p.suffix.lower()
            if ext in SUPPORTED_EXTS:
                # Se for .json, aceita se tiver 'save' ou 'file' no nome, ou for JSON válido
                if ext == ".json":
                    if "save" in f.lower() or "file" in f.lower():
                        found.append(p)
                else:
                    found.append(p)
    return sorted(found, key=lambda x: (x.parent, x.name))


class InteractiveCliSession:
    """Sessão Interativa de Edição via Terminal."""

    def __init__(self, save_path: Optional[Path | str] = None):
        self.console = Console()
        self.db = GLOBAL_DB
        self.adapter: Optional[BaseSaveAdapter] = None
        self.save_file: Optional[Path] = None

        if save_path:
            p = Path(save_path).resolve()
            if p.is_file():
                self.save_file = p

    def start(self):
        """Inicia o loop interativo."""
        self.console.clear()

        # 1. Se não temos arquivo selecionado, descobre ou solicita
        if not self.save_file:
            self.save_file = self._prompt_select_save_file()
            if not self.save_file:
                self.console.print("[yellow]Nenhum arquivo selecionado. Saindo.[/yellow]")
                return

        # 2. Carrega o save e o banco de dados
        self._load_save(self.save_file)
        if not self.adapter:
            return

        # 3. Loop principal de menu
        self._main_menu_loop()

    def _prompt_select_save_file(self) -> Optional[Path]:
        """Apresenta lista de saves encontrados na pasta atual ou solicita caminho."""
        working_dir = Path(os.environ.get("CALLER_WORKING_DIR", os.getcwd())).resolve()

        self.console.print(Panel.fit(
            f"[bold cyan]Save Maker — CLI Interativa[/bold cyan]\n"
            f"[dim]Buscando saves em: {working_dir}[/dim]",
            border_style="cyan"
        ))

        with self.console.status("[bold green]Procurando arquivos de save..."):
            found = scan_for_save_files(working_dir)

        if found:
            self.console.print(f"\n[bold green]Saves encontrados ({len(found)}):[/bold green]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("#", width=4, justify="right")
            table.add_column("Arquivo")
            table.add_column("Diretório", style="dim")
            table.add_column("Tamanho", justify="right")

            for idx, f in enumerate(found, 1):
                sz = f"{f.stat().st_size / 1024:.1f} KB"
                rel_dir = str(f.parent.relative_to(working_dir)) if f.parent != working_dir else "."
                table.add_row(str(idx), f.name, rel_dir, sz)

            self.console.print(table)
            self.console.print("\n[dim]Digite o número do save ou 'o' para digitar outro caminho (0 para sair)[/dim]")

            choice = Prompt.ask("Opção", default="1")
            if choice == "0":
                return None
            if choice.isdigit() and 1 <= int(choice) <= len(found):
                return found[int(choice) - 1]

        # Se não achou ou usuário optou por informar caminho
        manual_path = Prompt.ask("\n[bold]Caminho para o arquivo de save[/bold]")
        if manual_path:
            p = Path(manual_path).expanduser().resolve()
            if p.is_file():
                return p
            else:
                self.console.print(f"[bold red]Arquivo não encontrado:[/bold red] {p}")
        return None

    def _load_save(self, path: Path):
        """Carrega save e banco de dados com feedback visual."""
        with self.console.status(f"[bold green]Carregando {path.name}..."):
            try:
                db_found = self.db.discover_and_load(path)
                adapter = detect_and_create_adapter(path, self.db)
                adapter.load(path)
                self.adapter = adapter
            except Exception as e:
                self.console.print(f"[bold red]Erro ao carregar save:[/bold red] {e}")
                self.adapter = None

    def _render_header(self):
        """Exibe resumo visual da sessão e do save atual."""
        if not self.adapter or not self.save_file:
            return

        gold = self.adapter.get_gold()
        curr = self.db.get_currency_unit()
        playtime, steps = self.adapter.get_playtime_and_steps()
        db_summary = self.db.summary_info()
        dirty_status = f"[bold yellow]● {self.adapter.get_pending_changes_count()} alterações não salvas[/bold yellow]" if self.adapter.dirty else "[bold green]✓ Salvo[/bold green]"

        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)

        info_left = (
            f"[bold white]Arquivo:[/bold white] {self.save_file.name}\n"
            f"[bold white]Motor:[/bold white] [cyan]{self.adapter.engine_name}[/cyan] ({self.adapter.compression})\n"
            f"[bold white]Status:[/bold white] {dirty_status}"
        )
        info_right = (
            f"[bold white]Ouro:[/bold white] [bold yellow]{gold:,} {curr}[/bold yellow]\n"
            f"[bold white]Tempo / Passos:[/bold white] {playtime} | {steps:,} passos\n"
            f"[bold white]Banco de Dados:[/bold white] [dim]{db_summary}[/dim]"
        )
        grid.add_row(info_left, info_right)

        self.console.print(Panel(
            grid,
            title="[bold cyan]🎮 Save Maker — Painel de Controle[/bold cyan]",
            border_style="cyan"
        ))

    def _main_menu_loop(self):
        while True:
            self.console.clear()
            self._render_header()

            self.console.print("\n[bold cyan]Menu de Opções:[/bold cyan]")
            self.console.print("  [bold green]1.[/bold green] 💰 Modificar Ouro / Dinheiro")
            self.console.print("  [bold green]2.[/bold green] 💖 Curar Todo o Grupo (Full HP & MP)")
            self.console.print("  [bold green]3.[/bold green] ⭐ Subir Nível de Todos os Heróis (+5 Níveis)")
            self.console.print("  [bold green]4.[/bold green] 👥 Inspecionar & Editar Herói / Ator")
            self.console.print("  [bold green]5.[/bold green] 🎒 Inspecionar & Editar Inventário (Itens / Armas / Armaduras)")
            self.console.print("  [bold green]6.[/bold green] ⚙ Alternar Switches (Interruptores)")
            self.console.print("  [bold green]7.[/bold green] 🔢 Editar Variáveis de Jogo")
            self.console.print("  [bold green]8.[/bold green] 🎁 Desbloquear Todos os Itens do Jogo (x99)")
            self.console.print("  [bold green]9.[/bold green] 📤 Exportar Save para JSON")
            self.console.print("  [bold green]10.[/bold green] 🖥 Abrir na Interface Gráfica (GUI)")
            self.console.print("  [bold green]11.[/bold green] 💾 Salvar Alterações")
            self.console.print("  [bold red]0.[/bold red] 🚪 Sair")

            choice = Prompt.ask("\n[bold]Escolha uma opção[/bold]", default="11" if self.adapter.dirty else "0")

            if choice == "0":
                if self.adapter.dirty:
                    if Confirm.ask("[bold yellow]Há alterações não salvas. Deseja salvar antes de sair?[/bold yellow]", default=True):
                        self._action_save()
                self.console.print("[bold green]Até logo![/bold green]")
                break

            elif choice == "1":
                self._action_gold()
            elif choice == "2":
                self._action_heal_all()
            elif choice == "3":
                self._action_level_up_all()
            elif choice == "4":
                self._action_actors()
            elif choice == "5":
                self._action_inventory()
            elif choice == "6":
                self._action_switches()
            elif choice == "7":
                self._action_variables()
            elif choice == "8":
                self._action_unlock_all()
            elif choice == "9":
                self._action_export_json()
            elif choice == "10":
                self._action_launch_gui()
            elif choice == "11":
                self._action_save()

    # --- Ações do Menu ---

    def _action_gold(self):
        curr_gold = self.adapter.get_gold()
        curr_unit = self.db.get_currency_unit()
        self.console.print(f"\n[bold]Ouro atual:[/bold] [yellow]{curr_gold:,} {curr_unit}[/yellow]")
        self.console.print("  [1] Informar valor exato")
        self.console.print("  [2] +10.000")
        self.console.print("  [3] +100.000")
        self.console.print("  [4] +1.000.000")
        self.console.print("  [5] Maximizar (99.999.999)")
        self.console.print("  [6] Zerar (0)")
        self.console.print("  [0] Voltar")

        sub = Prompt.ask("Opção", default="1")
        if sub == "1":
            val = IntPrompt.ask("Novo valor de ouro", default=curr_gold)
            self.adapter.set_gold(val)
        elif sub == "2":
            self.adapter.set_gold(curr_gold + 10000)
        elif sub == "3":
            self.adapter.set_gold(curr_gold + 100000)
        elif sub == "4":
            self.adapter.set_gold(curr_gold + 1000000)
        elif sub == "5":
            self.adapter.set_gold(99999999)
        elif sub == "6":
            self.adapter.set_gold(0)

        self.console.print(f"[bold green]✔ Ouro atualizado para {self.adapter.get_gold():,} {curr_unit}![/bold green]")
        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_heal_all(self):
        actors = self.adapter.get_actors()
        for a in actors:
            max_hp = a.get("max_hp", 9999) or 9999
            max_mp = a.get("max_mp", 999) or 999
            self.adapter.update_actor(a["id"], {"hp": max_hp, "mp": max_mp})
        self.console.print("[bold green]✔ Todo o grupo foi totalmente curado com HP e MP máximos![/bold green]")
        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_level_up_all(self):
        actors = self.adapter.get_actors()
        for a in actors:
            new_lvl = min(999, a.get("level", 1) + 5)
            self.adapter.update_actor(a["id"], {"level": new_lvl})
        self.console.print("[bold green]✔ Todos os heróis subiram +5 níveis![/bold green]")
        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_actors(self):
        actors = self.adapter.get_actors()
        if not actors:
            self.console.print("[yellow]Nenhum ator encontrado no save.[/yellow]")
            Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")
            return

        table = Table(title="Personagens / Atores", header_style="bold magenta")
        table.add_column("#", width=3, justify="right")
        table.add_column("Nome", style="bold")
        table.add_column("Nível", justify="right")
        table.add_column("HP", justify="right")
        table.add_column("MP", justify="right")
        table.add_column("ATK", justify="right")
        table.add_column("DEF", justify="right")
        table.add_column("AGI", justify="right")

        for idx, a in enumerate(actors, 1):
            table.add_row(
                str(idx), a["name"], str(a["level"]),
                f"{a['hp']}/{a['max_hp']}", f"{a['mp']}/{a['max_mp']}",
                str(a["atk"]), str(a["def"]), str(a["agi"])
            )

        self.console.print(table)
        choice = Prompt.ask("\nSelecione o número do herói para editar (ou 0 para voltar)", default="0")
        if choice.isdigit() and 1 <= int(choice) <= len(actors):
            target_actor = actors[int(choice) - 1]
            self._edit_single_actor(target_actor)

    def _edit_single_actor(self, actor: Dict[str, Any]):
        aid = actor["id"]
        name = actor["name"]
        self.console.print(f"\n[bold cyan]Editando Herói: {name} (ID #{aid})[/bold cyan]")
        self.console.print("  [1] Nível")
        self.console.print("  [2] HP e HP Máximo")
        self.console.print("  [3] MP e MP Máximo")
        self.console.print("  [4] Maximizar Todos os Atributos (999)")
        self.console.print("  [5] Curar Totalmente")
        self.console.print("  [0] Voltar")

        op = Prompt.ask("Opção", default="0")
        if op == "1":
            lvl = IntPrompt.ask("Novo Nível (1-999)", default=actor["level"])
            self.adapter.update_actor(aid, {"level": lvl})
        elif op == "2":
            hp = IntPrompt.ask("Novo HP", default=actor["hp"])
            max_hp = IntPrompt.ask("Novo HP Máximo", default=max(hp, actor["max_hp"]))
            self.adapter.update_actor(aid, {"hp": hp, "max_hp": max_hp})
        elif op == "3":
            mp = IntPrompt.ask("Novo MP", default=actor["mp"])
            max_mp = IntPrompt.ask("Novo MP Máximo", default=max(mp, actor["max_mp"]))
            self.adapter.update_actor(aid, {"mp": mp, "max_mp": max_mp})
        elif op == "4":
            self.adapter.update_actor(aid, {
                "level": 99, "max_hp": 9999, "hp": 9999, "max_mp": 999, "mp": 999,
                "atk": 999, "def": 999, "mat": 999, "mdf": 999, "agi": 999, "luk": 999
            })
            self.console.print(f"[bold green]✔ {name} maximizado com status lendários![/bold green]")
        elif op == "5":
            self.adapter.update_actor(aid, {"hp": actor["max_hp"], "mp": actor["max_mp"]})
            self.console.print(f"[bold green]✔ {name} totalmente curado![/bold green]")

        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_inventory(self):
        self.console.print("\n[bold]Escolha a categoria do inventário:[/bold]")
        self.console.print("  [1] Itens Consumíveis")
        self.console.print("  [2] Armas")
        self.console.print("  [3] Armaduras")
        self.console.print("  [0] Voltar")

        c = Prompt.ask("Categoria", default="1")
        mapping = {"1": "items", "2": "weapons", "3": "armors"}
        kind = mapping.get(c)
        if not kind:
            return

        inv = self.adapter.get_inventory(kind)
        query = Prompt.ask("\nFiltrar itens por nome ou ID (Enter para ver todos)", default="").strip().lower()
        filtered = [it for it in inv if not query or query in it["name"].lower() or query in str(it["id"])]

        table = Table(title=f"Inventário: {kind.capitalize()} ({len(filtered)} exibidos de {len(inv)})", header_style="bold green")
        table.add_column("ID", width=6, justify="right")
        table.add_column("Nome Real do Item", style="bold")
        table.add_column("Quantidade", width=12, justify="right")

        for it in filtered[:100]:  # Limita para não inundar o terminal
            table.add_row(f"#{it['id']}", it["name"], str(it["quantity"]))

        self.console.print(table)
        self.console.print("\n  [a] Adicionar Item por ID")
        self.console.print("  [m] Maximizar Existentes (x99)")
        self.console.print("  [e] Editar Quantidade de um Item")
        self.console.print("  [0] Voltar")

        sub = Prompt.ask("Ação", default="0")
        if sub == "a":
            i_id = Prompt.ask("ID do item")
            qty = IntPrompt.ask("Quantidade", default=1)
            self.adapter.set_item_quantity(kind, i_id, qty)
            self.console.print(f"[bold green]✔ Item #{i_id} adicionado (x{qty})![/bold green]")
        elif sub == "m":
            for it in inv:
                self.adapter.set_item_quantity(kind, it["id"], 99)
            self.console.print(f"[bold green]✔ Todos os {len(inv)} itens definidos para x99![/bold green]")
        elif sub == "e":
            i_id = Prompt.ask("ID do item para editar")
            qty = IntPrompt.ask("Nova Quantidade (0 para remover)", default=99)
            self.adapter.set_item_quantity(kind, i_id, qty)
            self.console.print(f"[bold green]✔ Item #{i_id} atualizado para x{qty}![/bold green]")

        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_switches(self):
        switches = self.adapter.get_switches()
        query = Prompt.ask("\nFiltrar switches por nome ou ID (Enter para ver todos)", default="").strip().lower()

        filtered = [s for s in switches if not query or query in s["name"].lower() or query in str(s["id"])]
        table = Table(title=f"Switches ({len(filtered)} exibidos)", header_style="bold cyan")
        table.add_column("ID", width=6, justify="right")
        table.add_column("Nome da Switch", style="bold")
        table.add_column("Estado", width=10, justify="center")

        for s in filtered[:50]:
            state_str = "[bold green]LIGADO[/bold green]" if s["value"] else "[dim red]DESLIGADO[/dim red]"
            table.add_row(f"#{s['id']}", s["name"], state_str)

        self.console.print(table)
        target_id = Prompt.ask("\nDigite o ID da switch para alternar (ou 0 para voltar)", default="0")
        if target_id.isdigit() and int(target_id) > 0:
            s_id = int(target_id)
            current_val = next((s["value"] for s in switches if s["id"] == s_id), False)
            new_val = not current_val
            self.adapter.set_switch(s_id, new_val)
            name = self.db.get_switch_name(s_id)
            self.console.print(f"[bold green]✔ {name} alterado para {'ON' if new_val else 'OFF'}![/bold green]")

        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_variables(self):
        variables = self.adapter.get_variables()
        query = Prompt.ask("\nFiltrar variáveis por nome ou ID (Enter para ver todos)", default="").strip().lower()

        filtered = [v for v in variables if not query or query in v["name"].lower() or query in str(v["id"])]
        table = Table(title=f"Variáveis ({len(filtered)} exibidas)", header_style="bold cyan")
        table.add_column("ID", width=6, justify="right")
        table.add_column("Nome da Variável", style="bold")
        table.add_column("Valor Atual", width=18)

        for v in filtered[:50]:
            table.add_row(f"#{v['id']}", v["name"], str(v["value"]))

        self.console.print(table)
        target_id = Prompt.ask("\nDigite o ID da variável para editar (ou 0 para voltar)", default="0")
        if target_id.isdigit() and int(target_id) > 0:
            v_id = int(target_id)
            new_val = Prompt.ask("Novo valor para a variável")
            self.adapter.set_variable(v_id, new_val)
            name = self.db.get_variable_name(v_id)
            self.console.print(f"[bold green]✔ {name} alterado para {new_val}![/bold green]")

        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_unlock_all(self):
        if Confirm.ask("[bold yellow]Deseja desbloquear todos os itens do banco de dados (x99)?[/bold yellow]", default=True):
            count = self.adapter.unlock_all_items("items", 99)
            self.console.print(f"[bold green]✔ Desbloqueados {count} itens com sucesso![/bold green]")
        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_export_json(self):
        default_dst = self.save_file.with_suffix(".json")
        dst = Prompt.ask("Destino do arquivo JSON", default=str(default_dst))
        if dst:
            import json
            out = {
                "engine": self.adapter.engine_name,
                "compression": self.adapter.compression,
                "data": self.adapter.raw_data
            }
            Path(dst).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            self.console.print(f"[bold green]✔ JSON exportado com sucesso em:[/bold green] {dst}")
        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_launch_gui(self):
        self.console.print("[cyan]Iniciando interface gráfica moderna...[/cyan]")
        try:
            from ui.modern_app import ModernSaveEditorApp
            app = ModernSaveEditorApp()
            app.load_save_file(self.save_file)
            app.mainloop()
            # Recarrega o save ao fechar a GUI caso tenha sido salvo
            self._load_save(self.save_file)
        except Exception as e:
            self.console.print(f"[bold red]Não foi possível abrir a GUI:[/bold red] {e}")
            Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")

    def _action_save(self):
        with self.console.status("[bold green]Salvando alterações..."):
            try:
                self.adapter.save(self.save_file, backup=True)
                self.console.print(f"[bold green]✔ Save salvo com sucesso em {self.save_file.name}![/bold green]")
                self.console.print(f"[dim]Backup automático de segurança gerado: {self.save_file.name}.bak[/dim]")
            except Exception as e:
                self.console.print(f"[bold red]Erro ao salvar:[/bold red] {e}")
        Prompt.ask("\n[dim]Pressione Enter para continuar...[/dim]", default="")


def main():
    save_arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    session = InteractiveCliSession(save_arg)
    session.start()


if __name__ == "__main__":
    main()
