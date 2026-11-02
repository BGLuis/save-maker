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
    import orjson
    def _fast_json_loads(data: bytes | str) -> Any:
        if isinstance(data, str):
            data = data.encode("utf-8")
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        return orjson.loads(data)
except ImportError:
    def _fast_json_loads(data: bytes | str) -> Any:
        if isinstance(data, bytes):
            if data.startswith(b"\xef\xbb\xbf"):
                data = data[3:]
            return json.loads(data.decode("utf-8"))
        return json.loads(data)

try:
    from rubymarshal.reader import load as ruby_load
    _RUBY_AVAILABLE = True
except Exception:
    ruby_load = None
    _RUBY_AVAILABLE = False

from .wolf_adapter import _INVENTORY_KEYWORDS
from .wolf_database import (
    parse_wolf_project, parse_wolf_fixed_database, project_types_to_wolf_types, WolfCryptoUnsupportedError,
)

_WOLF_ITEM_NAME_KEYWORDS = ["アイテム", "item"]
_WOLF_ACTOR_NAME_KEYWORDS = ["アクター", "キャラクター", "主人公", "キャラ名", "actor", "character", "hero"]
_WOLF_EQUIP_NAME_KEYWORDS = ["装備", "equip"]
_WOLF_NAME_MAP_FILE = "wolf_name_map.json"


class GameDatabaseManager:
    """Gerencia mapeamentos de nomes, ícones e descrições do jogo."""

    def __init__(self):
        self.data_dir: Optional[Path] = None
        self._dir_cache: Optional[Dict[str, Path]] = None
        self._loaded_items: bool = False
        self._loaded_actors: bool = False
        self._loaded_system: bool = False
        self._loaded_wolf: bool = False

        self._items: Dict[str, Dict[str, Any]] = {}
        self._weapons: Dict[str, Dict[str, Any]] = {}
        self._armors: Dict[str, Dict[str, Any]] = {}
        self._actors: Dict[str, Dict[str, Any]] = {}
        self._classes: Dict[str, Dict[str, Any]] = {}
        self._skills: Dict[str, Dict[str, Any]] = {}
        self._switches: Dict[int, str] = {}
        self._variables: Dict[int, str] = {}

        self.wolf_types: Dict[int, Dict[str, Any]] = {}
        self.wolf_fixed_types: List[Dict[str, Any]] = []
        self.wolf_sys_types: Dict[int, Dict[str, Any]] = {}
        self.wolf_name_map: Dict[str, int] = {}
        self.save_dir: Optional[Path] = None
        self.currency_unit: str = "G"
        self.game_title: str = ""
        self.config: Dict[str, Any] = {}

    @property
    def items(self) -> Dict[str, Dict[str, Any]]:
        self.ensure_items_loaded()
        return self._items

    @items.setter
    def items(self, val: Dict[str, Dict[str, Any]]):
        self._items = val
        self._loaded_items = True

    @property
    def weapons(self) -> Dict[str, Dict[str, Any]]:
        self.ensure_items_loaded()
        return self._weapons

    @weapons.setter
    def weapons(self, val: Dict[str, Dict[str, Any]]):
        self._weapons = val
        self._loaded_items = True

    @property
    def armors(self) -> Dict[str, Dict[str, Any]]:
        self.ensure_items_loaded()
        return self._armors

    @armors.setter
    def armors(self, val: Dict[str, Dict[str, Any]]):
        self._armors = val
        self._loaded_items = True

    @property
    def actors(self) -> Dict[str, Dict[str, Any]]:
        self.ensure_actors_loaded()
        return self._actors

    @actors.setter
    def actors(self, val: Dict[str, Dict[str, Any]]):
        self._actors = val
        self._loaded_actors = True

    @property
    def classes(self) -> Dict[str, Dict[str, Any]]:
        self.ensure_actors_loaded()
        return self._classes

    @classes.setter
    def classes(self, val: Dict[str, Dict[str, Any]]):
        self._classes = val
        self._loaded_actors = True

    @property
    def skills(self) -> Dict[str, Dict[str, Any]]:
        self.ensure_actors_loaded()
        return self._skills

    @skills.setter
    def skills(self, val: Dict[str, Dict[str, Any]]):
        self._skills = val
        self._loaded_actors = True

    @property
    def switches(self) -> Dict[int, str]:
        self.ensure_system_loaded()
        return self._switches

    @switches.setter
    def switches(self, val: Dict[int, str]):
        self._switches = val
        self._loaded_system = True

    @property
    def variables(self) -> Dict[int, str]:
        self.ensure_system_loaded()
        return self._variables

    @variables.setter
    def variables(self, val: Dict[int, str]):
        self._variables = val
        self._loaded_system = True

    def ensure_items_loaded(self):
        """Carrega Items, Weapons e Armors sob demanda se ainda não foram carregados."""
        if self._loaded_items or not self.data_dir:
            return
        self._loaded_items = True
        d = self.data_dir
        cache = self._dir_cache
        self._load_data_file(d, "Items", self._items, cache)
        self._load_data_file(d, "Weapons", self._weapons, cache)
        self._load_data_file(d, "Armors", self._armors, cache)

    def ensure_actors_loaded(self):
        """Carrega Actors, Classes e Skills sob demanda se ainda não foram carregados."""
        if self._loaded_actors or not self.data_dir:
            return
        self._loaded_actors = True
        d = self.data_dir
        cache = self._dir_cache
        self._load_data_file(d, "Actors", self._actors, cache)
        self._load_data_file(d, "Classes", self._classes, cache)
        self._load_data_file(d, "Skills", self._skills, cache)

    def ensure_system_loaded(self):
        """Carrega switches, variáveis e moeda sob demanda se ainda não foram carregados."""
        if self._loaded_system or not self.data_dir:
            return
        self._loaded_system = True
        d = self.data_dir
        cache = self._dir_cache
        self._load_system_file(d, cache)

    def ensure_all_loaded(self) -> bool:
        """Garante que todos os arquivos de banco de dados foram carregados."""
        if not self.data_dir:
            return False
        self.ensure_items_loaded()
        self.ensure_actors_loaded()
        self.ensure_system_loaded()
        d = self.data_dir
        cache = self._dir_cache
        if not self._loaded_wolf and cache and ("cdatabase.project" in cache or "database.dat" in cache):
            self._load_wolf_database(d, cache)
            self._load_wolf_fixed_database(d, cache)
            self._loaded_wolf = True
        self._load_config_file(d, cache)
        return bool(self._items or self._weapons or self._armors or self._actors
                    or self._switches or self._variables or self.wolf_types or self.wolf_fixed_types)

    def is_loaded(self) -> bool:
        """Retorna True se algum banco de dados relevante foi conectado ou carregado."""
        return bool(self.data_dir is not None or self._items or self._weapons or self._armors
                    or self._actors or self._switches or self._variables or self.wolf_types or self.wolf_fixed_types)

    def summary_info(self) -> str:
        """Gera uma string descritiva com o resumo do que foi carregado ou conectado."""
        parts = []
        if self._loaded_items:
            if self._items: parts.append(f"{len(self._items)} itens")
            if self._weapons: parts.append(f"{len(self._weapons)} armas")
            if self._armors: parts.append(f"{len(self._armors)} armaduras")
        if self._loaded_actors:
            if self._actors: parts.append(f"{len(self._actors)} heróis")
        if self._loaded_system:
            if self._switches: parts.append(f"{len(self._switches)} switches")
            if self._variables: parts.append(f"{len(self._variables)} vars")
        if self.wolf_types:
            parts.append(f"{len(self.wolf_types)} tipos Wolf RPG")

        if parts:
            return ", ".join(parts)
        if self.data_dir:
            return f"Banco conectado ({self.data_dir.name})"
        return "Nenhum banco de dados conectado"

    def discover_and_load(self, save_path: Path | str, lazy: bool = True) -> bool:
        """
        Varre automaticamente as pastas vizinhas e ascendentes do save
        para encontrar a pasta de dados do jogo.
        """
        self.clear()
        p = Path(save_path).resolve()
        save_dir = p if p.is_dir() else p.parent
        self.save_dir = save_dir

        ext = p.suffix.lower()
        if ext in (".rpgsave", ".rmmzsave"):
            candidate_dirs: List[Path] = [
                save_dir.parent / "data",
                save_dir.parent / "Data",
                save_dir.parent / "www" / "data",
                save_dir.parent / "www" / "Data",
                save_dir.parent.parent / "data",
                save_dir.parent.parent / "Data",
                save_dir.parent.parent / "www" / "data",
                save_dir / "data",
                save_dir / "Data",
                save_dir / "www" / "data",
            ]
        elif ext in (".rvdata2", ".rvdata", ".rxdata"):
            candidate_dirs = [
                save_dir.parent / "Data",
                save_dir.parent / "data",
                save_dir / "Data",
                save_dir / "data",
                save_dir.parent.parent / "Data",
                save_dir.parent.parent / "data",
            ]
        elif ext in (".sav", ".dat"):
            candidate_dirs = [
                save_dir.parent / "Data" / "BasicData",
                save_dir.parent / "data" / "BasicData",
                save_dir / "Data" / "BasicData",
                save_dir.parent / "data",
                save_dir.parent / "Data",
            ]
        else:
            candidate_dirs = [
                save_dir / "data",
                save_dir / "Data",
                save_dir.parent / "data",
                save_dir.parent / "Data",
                save_dir.parent / "www" / "data",
                save_dir.parent / "www" / "Data",
                save_dir / "www" / "data",
                save_dir.parent.parent / "data",
                save_dir.parent.parent / "Data",
                save_dir.parent.parent / "www" / "data",
                save_dir.parent.parent / "www" / "Data",
                save_dir.parent / "Data" / "BasicData",
                save_dir.parent / "data" / "BasicData",
                save_dir / "Data" / "BasicData",
            ]

        for cand in candidate_dirs:
            if cand.is_dir() and self._is_rpg_data_dir(cand):
                if self.load_directory(cand, lazy=lazy):
                    return True

        return False

    def _is_rpg_data_dir(self, directory: Path) -> bool:
        """Verifica se um diretório contém arquivos típicos de RPG Maker."""
        key_files = [
            "Items.json", "items.json", "Items.rvdata2", "Items.rxdata",
            "System.json", "system.json", "System.rvdata2", "System.rxdata",
            "Armors.json", "armors.json", "Armors.rvdata2", "Armors.rxdata",
            "CDataBase.project", "CDataBase.dat",
        ]
        for k in key_files:
            if (directory / k).exists():
                return True
        return False

    def load_directory(self, directory: Path | str, lazy: bool = False) -> bool:
        """Carrega todos os arquivos de banco de dados encontrados no diretório."""
        d = Path(directory).resolve()
        if not d.is_dir():
            return False

        self.clear()
        self.data_dir = d

        # Pré-indexa os arquivos do diretório em O(1) para evitar varreduras repetidas em HDDs lentos
        dir_cache: Dict[str, Path] = {}
        try:
            for child in d.iterdir():
                if child.is_file():
                    dir_cache[child.name.lower()] = child
        except Exception:
            pass
        self._dir_cache = dir_cache

        # Se for lazy, só carrega o básico necessário imediatamente (System para título e moeda)
        if lazy:
            self.ensure_system_loaded()
            self._load_config_file(d, dir_cache)
            if "cdatabase.project" in dir_cache or "database.dat" in dir_cache:
                self._load_wolf_database(d, dir_cache)
                self._load_wolf_fixed_database(d, dir_cache)
                self._loaded_wolf = True
            return True

        # Eager (carrega tudo imediatamente):
        return self.ensure_all_loaded()

    def clear(self):
        """Limpa todos os dados carregados."""
        self.data_dir = None
        self._dir_cache = None
        self._loaded_items = False
        self._loaded_actors = False
        self._loaded_system = False
        self._loaded_wolf = False
        self._items.clear()
        self._weapons.clear()
        self._armors.clear()
        self._actors.clear()
        self._classes.clear()
        self._skills.clear()
        self._switches.clear()
        self._variables.clear()
        self.wolf_types.clear()
        self.wolf_fixed_types.clear()
        self.wolf_sys_types.clear()
        self.wolf_name_map.clear()
        self.save_dir = None
        self.currency_unit = "G"
        self.game_title = ""
        self.config.clear()
        self.save_dir = None
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

    def get_class_param_base(self, class_id: int | str, param_id: int, level: int) -> int:
        try:
            raw_cls = self.classes.get(str(class_id), {}).get("raw")
            if isinstance(raw_cls, dict) and isinstance(raw_cls.get("params"), list):
                params = raw_cls["params"]
                p_id = int(param_id)
                if 0 <= p_id < len(params) and isinstance(params[p_id], list) and len(params[p_id]) > 0:
                    p_list = params[p_id]
                    idx = max(1, min(int(level), len(p_list) - 1))
                    val = p_list[idx]
                    return int(val) if val is not None else 0
        except Exception:
            pass
        return 0

    def get_exp_for_level(self, class_id: int | str, level: int) -> int:
        try:
            lvl = int(level)
            if lvl <= 1:
                return 0
            raw_cls = self.classes.get(str(class_id), {}).get("raw")
            exp_params = raw_cls.get("expParams") if isinstance(raw_cls, dict) else None
            if not isinstance(exp_params, list) or len(exp_params) < 4:
                exp_params = [30, 20, 30, 30]
            basis, extra, acc_a, acc_b = (float(exp_params[i]) for i in range(4))
            if acc_b == 0:
                acc_b = 1.0
            num = basis * ((lvl - 1) ** (0.9 + acc_a / 250.0)) * lvl * (lvl + 1)
            den = 6.0 + (lvl ** 2) / 50.0 / acc_b
            return int(round(num / den + (lvl - 1) * extra))
        except Exception:
            return 0

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

    def _find_case_insensitive_file(self, directory: Path, basename: str, exts: List[str], dir_cache: Optional[Dict[str, Path]] = None) -> Optional[Path]:
        """Procura arquivo ignorando maiúsculas/minúsculas no nome ou extensão."""
        if dir_cache is not None:
            for ext in exts:
                candidate_name = f"{basename}{ext}".lower()
                if candidate_name in dir_cache:
                    return dir_cache[candidate_name]
            return None

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

    def _load_data_file(self, directory: Path, basename: str, target_dict: Dict[str, Dict[str, Any]], dir_cache: Optional[Dict[str, Path]] = None) -> bool:
        """Carrega arquivos como Items.json ou Items.rvdata2."""
        fpath = self._find_case_insensitive_file(directory, basename, [".json", ".rvdata2", ".rxdata"], dir_cache)
        if not fpath:
            return False

        try:
            if fpath.suffix.lower() == ".json":
                content = _fast_json_loads(fpath.read_bytes())
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

    def _load_system_file(self, directory: Path, dir_cache: Optional[Dict[str, Path]] = None) -> bool:
        """Carrega System.json / System.rvdata2 para obter switches e variáveis."""
        fpath = self._find_case_insensitive_file(directory, "System", [".json", ".rvdata2", ".rxdata"], dir_cache)
        if not fpath:
            return False

        try:
            if fpath.suffix.lower() == ".json":
                sys_data = _fast_json_loads(fpath.read_bytes())
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
                        self._switches[idx] = str(name).strip()

            # Variables
            raw_vars = sys_data.get("variables") or sys_data.get("@variables") or []
            if isinstance(raw_vars, list):
                for idx, name in enumerate(raw_vars):
                    if idx > 0 and name:
                        self._variables[idx] = str(name).strip()

            return bool(self._switches or self._variables or self.game_title)
        except Exception as e:
            print(f"[GameDatabaseManager] Erro ao ler System: {e}")
            return False

    def _load_wolf_database(self, directory: Path, dir_cache: Optional[Dict[str, Path]] = None) -> bool:
        """
        Carrega o schema de CDataBase.project do Wolf RPG Editor (nomes de tipos, campos e
        linhas de dados) para popular self.wolf_types, consumido pelas heurísticas de melhor
        esforço do WolfAdapter. Diferente de items/actors (dados fixos com id->nome 1:1), os
        "tipos" do Wolf são categorias livres definidas pelo próprio jogo - por isso ficam em
        um dict separado em vez de forçados no formato items/actors do RPG Maker.

        Como espelho leve de compatibilidade, linhas de tipos cujo nome pareça um "banco de
        itens" ou "banco de atores" também são copiadas para self.items/self.actors, para que
        as abas existentes de Inventário/Personagens da UI funcionem de graça (mesmo sem
        preço/descrição/stats fixos, que vivem em DataBase.dat - não lido por esta versão).
        Falhas (arquivo ausente, criptografia não suportada, formato inesperado) degradam
        graciosamente para "sem nomes Wolf resolvidos" em vez de interromper a descoberta.
        """
        fpath = self._find_case_insensitive_file(directory, "CDataBase", [".project"], dir_cache)
        if not fpath:
            fpath = directory / "CDataBase.project"
            if not fpath.is_file():
                return False

        try:
            types = parse_wolf_project(fpath)
        except WolfCryptoUnsupportedError as e:
            print(f"[GameDatabaseManager] {e}")
            return False
        except Exception as e:
            print(f"[GameDatabaseManager] Erro ao ler CDataBase.project: {e}")
            return False

        self.wolf_types = project_types_to_wolf_types(types)

        for type_idx, info in self.wolf_types.items():
            name_lower = (info.get("name") or "").lower()
            if any(k in name_lower for k in _WOLF_ITEM_NAME_KEYWORDS):
                target = self._items
            elif any(k in name_lower for k in _WOLF_ACTOR_NAME_KEYWORDS):
                target = self._actors
            else:
                continue
            for row in info.get("rows", []):
                row_id = str(row["index"])
                target[row_id] = {
                    "id": row_id,
                    "name": row["name"] or f"{info['name']} #{row['index']}",
                    "description": "",
                    "price": 0,
                    "iconIndex": 0,
                    "raw": {},
                }

        return bool(self.wolf_types)

    def _load_wolf_fixed_database(self, directory: Path, dir_cache: Optional[Dict[str, Path]] = None) -> bool:
        """Carrega DataBase.dat/.project (nomes de itens, armas, armaduras e atores),
        SysDatabase.project (nomes de variáveis) e o mapa manual opcional wolf_name_map.json."""
        dat_path = self._find_case_insensitive_file(directory, "database", [".dat"], dir_cache)
        if dat_path and dat_path.is_file():
            try:
                proj_path = self._find_case_insensitive_file(directory, "database", [".project"], dir_cache)
                self.wolf_fixed_types = parse_wolf_fixed_database(dat_path, proj_path)
            except Exception as e:
                print(f"[GameDatabaseManager] Erro ao ler DataBase.dat: {e}")

        sys_proj_path = self._find_case_insensitive_file(directory, "sysdatabase", [".project"], dir_cache)
        if sys_proj_path and sys_proj_path.is_file():
            try:
                self.wolf_sys_types = project_types_to_wolf_types(parse_wolf_project(sys_proj_path))
            except Exception as e:
                print(f"[GameDatabaseManager] Erro ao ler SysDatabase.project: {e}")

        self._populate_catalogs_from_wolf_fixed()

        search_dirs = [directory, directory.parent]
        if self.save_dir is not None:
            search_dirs.insert(0, self.save_dir)
        for folder in search_dirs:
            map_path = folder / _WOLF_NAME_MAP_FILE
            if not map_path.is_file():
                continue
            try:
                raw = _fast_json_loads(map_path.read_bytes())
                self.wolf_name_map = {str(k): int(v) for k, v in raw.items()}
            except Exception as e:
                print(f"[GameDatabaseManager] Erro ao ler {map_path.name}: {e}")
            break

        return bool(self.wolf_fixed_types or self.wolf_sys_types)

    def _populate_catalogs_from_wolf_fixed(self):
        """Popula self.items, self.weapons, self.armors e self.actors com os nomes reais de
        DataBase.dat/.project, substituindo placeholders genéricos vindos de CDataBase.project."""
        if not self.wolf_fixed_types:
            return

        def fill_target(target: Dict[str, Dict[str, Any]], rows: List[str], clear_placeholders: bool = False):
            named = [(i, r.strip()) for i, r in enumerate(rows) if r and r.strip()]
            if not named:
                return
            if clear_placeholders:
                for k in [k for k, v in target.items() if f"#{k}" in str(v.get("name", ""))]:
                    del target[k]
            for idx, rname in named:
                s_id = str(idx)
                if s_id not in target or f"#{s_id}" in str(target[s_id].get("name", "")):
                    target[s_id] = {
                        "id": s_id,
                        "name": rname,
                        "description": "",
                        "price": 0,
                        "iconIndex": 0,
                        "raw": {},
                    }

        item_kws = [k.lower() for k in _INVENTORY_KEYWORDS.get("items", [])]
        weapon_kws = [k.lower() for k in _INVENTORY_KEYWORDS.get("weapons", [])]
        armor_kws = [k.lower() for k in _INVENTORY_KEYWORDS.get("armors", [])]
        equip_kws = [k.lower() for k in _WOLF_EQUIP_NAME_KEYWORDS]
        actor_kws = [k.lower() for k in _WOLF_ACTOR_NAME_KEYWORDS]

        actors_filled = False
        for fixed in self.wolf_fixed_types:
            fname = (fixed.get("name") or "").lower()
            rows = fixed.get("rows", [])
            if any(k in fname for k in item_kws):
                fill_target(self._items, rows, clear_placeholders=True)
            if any(k in fname for k in weapon_kws) or any(k in fname for k in equip_kws):
                fill_target(self._weapons, rows)
            if any(k in fname for k in armor_kws) or any(k in fname for k in equip_kws):
                fill_target(self._armors, rows)
            if not actors_filled and any(k in fname for k in actor_kws):
                if any(r and r.strip() for r in rows):
                    fill_target(self._actors, rows, clear_placeholders=True)
                    actors_filled = True

    def resolve_wolf_row_names(self, save_type_idx: int, kind: str) -> List[str]:
        """Nomes das linhas do banco fixo que correspondem ao tipo `save_type_idx` da
        VariableDatabase do save. Ordem: wolf_name_map.json, depois o tipo do DataBase cujo
        nome casa com a categoria (`kind`), preferindo mesma contagem de linhas."""
        if not self.wolf_fixed_types:
            return []
        mapped = self.wolf_name_map.get(str(save_type_idx))
        if mapped is not None:
            return self.wolf_fixed_types[mapped]["rows"] if 0 <= mapped < len(self.wolf_fixed_types) else []

        if kind == "actors":
            keywords = [k.lower() for k in _WOLF_ACTOR_NAME_KEYWORDS]
        else:
            keywords = [k.lower() for k in _INVENTORY_KEYWORDS.get(kind, [])]

        expected_len = len(self.wolf_types.get(save_type_idx, {}).get("rows", [])) if self.wolf_types else 0
        matches = [f for f in self.wolf_fixed_types if any(k in f["name"].lower() for k in keywords)]
        if not matches and kind in ("weapons", "armors"):
            equip_kws = [k.lower() for k in _WOLF_EQUIP_NAME_KEYWORDS]
            matches = [f for f in self.wolf_fixed_types if any(k in f["name"].lower() for k in equip_kws)]
        if not matches:
            return []
        if expected_len > 0:
            for m in matches:
                if len(m["rows"]) == expected_len and any(m["rows"]):
                    return m["rows"]
            return []
        return matches[0]["rows"]

    def _load_config_file(self, directory: Path, dir_cache: Optional[Dict[str, Path]] = None):
        """Carrega config.json se presente."""
        fpath = self._find_case_insensitive_file(directory, "config", [".json"], dir_cache)
        if not fpath:
            # Tenta na pasta pai (raiz do jogo)
            fpath = self._find_case_insensitive_file(directory.parent, "config", [".json"])

        if fpath and fpath.is_file():
            try:
                self.config = _fast_json_loads(fpath.read_bytes())
            except Exception:
                pass


# Instância global para reuso conveniente
GLOBAL_DB = GameDatabaseManager()
