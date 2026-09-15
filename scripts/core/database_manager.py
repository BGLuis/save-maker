#!/usr/bin/env python3
"""
GameDatabaseManager - Descoberta e Carregamento Automático de Banco de Dados do Jogo

Localiza e carrega automaticamente arquivos como:
- Items.json / Items.rvdata2 / Items.rxdata
- Weapons.json / Weapons.rvdata2 / Weapons.rxdata
- Armors.json / Armors.rvdata2 / Armors.rxdata
- Actors.json / Actors.rvdata2 / Actors.rxdata
- Classes.json / Classes.rvdata2 / Classes.rxdata
- Skills.json / Skills.rvdata2 / Skills.rxdata
- System.json / System.rvdata2 / System.rxdata (Nomes de switches, variáveis, título e moeda)
- config.json

Permite que a interface apresente imediatamente o nome real de qualquer item,
equipamento, ator, switch e variável em vez de apenas IDs numéricos crus.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rubymarshal.reader import load as ruby_load
    _RUBY_AVAILABLE = True
except Exception:
    ruby_load = None
    _RUBY_AVAILABLE = False


class GameDatabaseManager:
    """Gerencia mapeamentos de nomes, ícones e descrições do jogo."""

    def __init__(self):
        self.data_dir: Optional[Path] = None
        self.items: Dict[str, Dict[str, Any]] = {}
        self.weapons: Dict[str, Dict[str, Any]] = {}
        self.armors: Dict[str, Dict[str, Any]] = {}
        self.actors: Dict[str, Dict[str, Any]] = {}
        self.classes: Dict[str, Dict[str, Any]] = {}
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.switches: Dict[int, str] = {}
        self.variables: Dict[int, str] = {}
        self.currency_unit: str = "G"
        self.game_title: str = ""
        self.config: Dict[str, Any] = {}

    def is_loaded(self) -> bool:
        """Retorna True se algum banco de dados relevante foi carregado."""
        return bool(self.items or self.weapons or self.armors or self.actors or self.switches or self.variables)

    def summary_info(self) -> str:
        """Gera uma string descritiva com o resumo do que foi carregado."""
        parts = []
        if self.items:
            parts.append(f"{len(self.items)} itens")
        if self.weapons:
            parts.append(f"{len(self.weapons)} armas")
        if self.armors:
            parts.append(f"{len(self.armors)} armaduras")
        if self.actors:
            parts.append(f"{len(self.actors)} heróis")
        if self.switches:
            parts.append(f"{len(self.switches)} switches")
        if self.variables:
            parts.append(f"{len(self.variables)} vars")

        if not parts:
            return "Nenhum banco de dados conectado"
        return ", ".join(parts)

    def discover_and_load(self, save_path: Path | str) -> bool:
        """
        Varre automaticamente as pastas vizinhas e ascendentes do save
        para encontrar a pasta de dados do jogo.
        """
        p = Path(save_path).resolve()
        save_dir = p if p.is_dir() else p.parent

        candidate_dirs: List[Path] = [
            # Subpastas da pasta do save
            save_dir / "data",
            save_dir / "Data",
            save_dir / "save" / "data",
            # Pasta pai (ex: Game/save -> Game/data)
            save_dir.parent / "data",
            save_dir.parent / "Data",
            # Padrão Steam/PC MV/MZ (Game/www/data ou Game/save -> Game/www/data)
            save_dir.parent / "www" / "data",
            save_dir.parent / "www" / "Data",
            save_dir / "www" / "data",
            # Pasta avô (ex: Game/www/save -> Game/www/data)
            save_dir.parent.parent / "data",
            save_dir.parent.parent / "Data",
            save_dir.parent.parent / "www" / "data",
            save_dir.parent.parent / "www" / "Data",
        ]

        # Adiciona pasta interna de dados do projeto como fallback
        root_dir = Path(__file__).resolve().parent.parent.parent
        candidate_dirs.append(root_dir / "save" / "data")
        candidate_dirs.append(root_dir / "data")

        for cand in candidate_dirs:
            if cand.is_dir() and self._is_rpg_data_dir(cand):
                if self.load_directory(cand):
                    return True

        return False

    def _is_rpg_data_dir(self, directory: Path) -> bool:
        """Verifica se um diretório contém arquivos típicos de RPG Maker."""
        key_files = [
            "Items.json", "items.json", "Items.rvdata2", "Items.rxdata",
            "System.json", "system.json", "System.rvdata2", "System.rxdata",
            "Armors.json", "armors.json", "Armors.rvdata2", "Armors.rxdata"
        ]
        for k in key_files:
            if (directory / k).exists():
                return True
        return False

    def load_directory(self, directory: Path | str) -> bool:
        """Carrega todos os arquivos de banco de dados encontrados no diretório."""
        d = Path(directory).resolve()
        if not d.is_dir():
            return False

        self.clear()
        self.data_dir = d

        loaded_any = False

        # 1. Carrega Items
        if self._load_data_file(d, "Items", self.items): loaded_any = True
        # 2. Carrega Weapons
        if self._load_data_file(d, "Weapons", self.weapons): loaded_any = True
        # 3. Carrega Armors
        if self._load_data_file(d, "Armors", self.armors): loaded_any = True
        # 4. Carrega Actors
        if self._load_data_file(d, "Actors", self.actors): loaded_any = True
        # 5. Carrega Classes
        if self._load_data_file(d, "Classes", self.classes): loaded_any = True
        # 6. Carrega Skills
        if self._load_data_file(d, "Skills", self.skills): loaded_any = True
        # 7. Carrega System (switches, variables, moeda)
        if self._load_system_file(d): loaded_any = True
        # 8. Carrega config.json se existir
        self._load_config_file(d)

        return loaded_any

    def clear(self):
        """Limpa todos os dados carregados."""
        self.data_dir = None
        self.items.clear()
        self.weapons.clear()
        self.armors.clear()
        self.actors.clear()
        self.classes.clear()
        self.skills.clear()
        self.switches.clear()
        self.variables.clear()
        self.currency_unit = "G"
        self.game_title = ""
        self.config.clear()

    # --- Métodos de consulta amigável ---

    def get_item_name(self, item_id: int | str, default: Optional[str] = None) -> str:
        s_id = str(item_id)
        if s_id in self.items and self.items[s_id].get("name"):
            return self.items[s_id]["name"]
        return default if default is not None else f"Item #{s_id}"

    def get_weapon_name(self, weapon_id: int | str, default: Optional[str] = None) -> str:
        s_id = str(weapon_id)
        if s_id in self.weapons and self.weapons[s_id].get("name"):
            return self.weapons[s_id]["name"]
        return default if default is not None else f"Arma #{s_id}"

    def get_armor_name(self, armor_id: int | str, default: Optional[str] = None) -> str:
        s_id = str(armor_id)
        if s_id in self.armors and self.armors[s_id].get("name"):
            return self.armors[s_id]["name"]
        return default if default is not None else f"Armadura #{s_id}"

    def get_actor_name(self, actor_id: int | str, default: Optional[str] = None) -> str:
        s_id = str(actor_id)
        if s_id in self.actors and self.actors[s_id].get("name"):
            return self.actors[s_id]["name"]
        return default if default is not None else f"Personagem #{s_id}"

    def get_class_name(self, class_id: int | str, default: Optional[str] = None) -> str:
        s_id = str(class_id)
        if s_id in self.classes and self.classes[s_id].get("name"):
            return self.classes[s_id]["name"]
        return default if default is not None else f"Classe #{s_id}"

    def get_skill_name(self, skill_id: int | str, default: Optional[str] = None) -> str:
        s_id = str(skill_id)
        if s_id in self.skills and self.skills[s_id].get("name"):
            return self.skills[s_id]["name"]
        return default if default is not None else f"Habilidade #{s_id}"

    def get_switch_name(self, switch_id: int | str, default: Optional[str] = None) -> str:
        try:
            i_id = int(switch_id)
            if i_id in self.switches and self.switches[i_id]:
                return self.switches[i_id]
        except Exception:
            pass
        return default if default is not None else f"Switch #{switch_id}"

    def get_variable_name(self, var_id: int | str, default: Optional[str] = None) -> str:
        try:
            i_id = int(var_id)
            if i_id in self.variables and self.variables[i_id]:
                return self.variables[i_id]
        except Exception:
            pass
        return default if default is not None else f"Variável #{var_id}"

    def get_currency_unit(self) -> str:
        return self.currency_unit or "G"

    def get_all_known_items(self) -> List[Dict[str, Any]]:
        return list(self.items.values())

    def get_all_known_weapons(self) -> List[Dict[str, Any]]:
        return list(self.weapons.values())

    def get_all_known_armors(self) -> List[Dict[str, Any]]:
        return list(self.armors.values())

    # --- Carregadores internos tolerantes a falhas ---

    def _find_case_insensitive_file(self, directory: Path, basename: str, exts: List[str]) -> Optional[Path]:
        """Procura arquivo ignorando maiúsculas/minúsculas no nome ou extensão."""
        for ext in exts:
            candidates = [
                directory / f"{basename}{ext}",
                directory / f"{basename.lower()}{ext}",
                directory / f"{basename.capitalize()}{ext}",
                directory / f"{basename.upper()}{ext}",
            ]
            for c in candidates:
                if c.is_file():
                    return c
        # Varredura completa se não achou direto
        try:
            b_low = basename.lower()
            ext_lows = [e.lower() for e in exts]
            for child in directory.iterdir():
                if child.is_file():
                    if child.stem.lower() == b_low and child.suffix.lower() in ext_lows:
                        return child
        except Exception:
            pass
        return None

    def _load_data_file(self, directory: Path, basename: str, target_dict: Dict[str, Dict[str, Any]]) -> bool:
        """Carrega arquivos como Items.json ou Items.rvdata2."""
        fpath = self._find_case_insensitive_file(directory, basename, [".json", ".rvdata2", ".rxdata"])
        if not fpath:
            return False

        try:
            if fpath.suffix.lower() == ".json":
                content = json.loads(fpath.read_text(encoding="utf-8-sig"))
            elif _RUBY_AVAILABLE and ruby_load is not None:
                with open(fpath, "rb") as fd:
                    content = ruby_load(fd)
            else:
                return False

            entries = []
            if isinstance(content, list):
                entries = content
            elif isinstance(content, dict):
                entries = content.get("data", list(content.values()))

            count = 0
            for item in entries:
                if item is None:
                    continue

                item_dict = {}
                if isinstance(item, dict):
                    item_dict = item
                elif hasattr(item, "attributes"):
                    # Objeto Ruby
                    attrs = getattr(item, "attributes", {})
                    for k, v in attrs.items():
                        clean_k = str(k).lstrip("@")
                        item_dict[clean_k] = v

                i_id = item_dict.get("id")
                i_name = item_dict.get("name")
                if i_id is not None:
                    target_dict[str(i_id)] = {
                        "id": i_id,
                        "name": str(i_name) if i_name is not None else f"{basename} {i_id}",
                        "description": str(item_dict.get("description", "")),
                        "price": item_dict.get("price", 0),
                        "iconIndex": item_dict.get("iconIndex", 0),
                        "raw": item_dict
                    }
                    count += 1
            return count > 0
        except Exception as e:
            print(f"[GameDatabaseManager] Erro ao ler {fpath.name}: {e}")
            return False

    def _load_system_file(self, directory: Path) -> bool:
        """Carrega System.json / System.rvdata2 para obter switches e variáveis."""
        fpath = self._find_case_insensitive_file(directory, "System", [".json", ".rvdata2", ".rxdata"])
        if not fpath:
            return False

        try:
            if fpath.suffix.lower() == ".json":
                sys_data = json.loads(fpath.read_text(encoding="utf-8-sig"))
            elif _RUBY_AVAILABLE and ruby_load is not None:
                with open(fpath, "rb") as fd:
                    raw_obj = ruby_load(fd)
                    sys_data = getattr(raw_obj, "attributes", {})
            else:
                return False

            # Moeda e Título
            self.currency_unit = sys_data.get("currencyUnit") or sys_data.get("@currency_unit") or "G"
            self.game_title = sys_data.get("gameTitle") or sys_data.get("@game_title") or ""

            # Switches
            raw_switches = sys_data.get("switches") or sys_data.get("@switches") or []
            if isinstance(raw_switches, list):
                for idx, name in enumerate(raw_switches):
                    if idx > 0 and name:
                        self.switches[idx] = str(name).strip()

            # Variables
            raw_vars = sys_data.get("variables") or sys_data.get("@variables") or []
            if isinstance(raw_vars, list):
                for idx, name in enumerate(raw_vars):
                    if idx > 0 and name:
                        self.variables[idx] = str(name).strip()

            return bool(self.switches or self.variables or self.game_title)
        except Exception as e:
            print(f"[GameDatabaseManager] Erro ao ler System: {e}")
            return False

    def _load_config_file(self, directory: Path):
        """Carrega config.json se presente."""
        fpath = self._find_case_insensitive_file(directory, "config", [".json"])
        if not fpath:
            # Tenta na pasta pai (raiz do jogo)
            fpath = self._find_case_insensitive_file(directory.parent, "config", [".json"])

        if fpath and fpath.is_file():
            try:
                self.config = json.loads(fpath.read_text(encoding="utf-8-sig"))
            except Exception:
                pass


# Instância global para reuso conveniente
GLOBAL_DB = GameDatabaseManager()
