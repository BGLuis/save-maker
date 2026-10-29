#!/usr/bin/env python3
"""
Game Library and Recent Files Manager for Save Maker.
Indexa jogos, varre slots de save e gera prévias sem travar a interface.
Resolução inteligente de títulos de jogos e sanitização de ruídos.
"""

from pathlib import Path
import json
import os
import time
import re
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


def is_generic_or_save_name(name: str) -> bool:
    """Verifica se uma string é vazia, genérica ou um nome/stem típico de arquivo de save."""
    if not name:
        return True
    n = name.strip()
    # Remove extensão se houver (ex: SaveData02.sav -> SaveData02)
    stem = Path(n).stem.lower()
    nl = n.lower()
    # Padrões comuns de saves (ex: SaveData07, file1, slot2, sample, global)
    if re.match(r'^(save|savedata|file|slot|sample|global)\d*$', stem):
        return True
    if nl in ("save", "saves", "savedata", "data", "www", "fixtures", "tests", "default", "temp", "tmp", "jogo"):
        return True
    if stem in ("save", "saves", "savedata", "data", "www", "fixtures", "tests", "default", "temp", "tmp", "jogo"):
        return True
    return False


def clean_noisy_title(raw_title: str) -> str:
    """
    Sanitiza títulos poluídos por notas de tradutores, versões órfãs ou mapas de atalhos.
    Exemplo: 'v1.01 | TL: DazedAnon[Pular balão de fala: Z | Apagar mensagem: Shift | Pular texto: CTRL]'
    """
    if not raw_title:
        return ""
    t = raw_title.strip()

    # Remove quebras de linha
    t = " ".join(t.split())

    # Se o título contém atalhos de teclado entre colchetes, remove o bloco
    t = re.sub(r'\[.*?(?:Pular|Shift|CTRL|F5|Enter|Espaço|Tecla|Key|PageUp|PageDown).*?\]', '', t, flags=re.IGNORECASE).strip()

    # Remove colchetes de tradução como [TL: ...], [Traduzido por ...]
    t = re.sub(r'\[.*?(?:TL:|Traduzido|Translation|Patch).*?\]', '', t, flags=re.IGNORECASE).strip()

    # Se restar algo como "v1.01 | TL: DazedAnon", remove o bloco de TL
    if re.search(r'\bTL:\s*[\w\.\-]+', t, re.IGNORECASE):
        t = re.sub(r'\|?\s*TL:\s*[\w\.\-]+', '', t, flags=re.IGNORECASE).strip()
        t = re.sub(r'^v?\d+(\.\d+)*\s*\|?\s*', '', t, flags=re.IGNORECASE).strip()

    # Remove pipes e traços órfãos no início ou fim
    t = t.strip(" |-\t\n\r")
    return t


def resolve_game_title(save_or_game_path: str | Path, raw_title: str = "", engine: str = "") -> str:
    """
    Determina o título mais apropriado para o jogo:
    1. Se raw_title for um título limpo e não for nome de save, usa-o.
    2. Busca metadados estruturados: Game.ini ([Game] Title) ou package.json (window.title / name).
    3. Recorre ao nome da pasta raiz do jogo (ex.: 'Warrior Maiden Lecia and the Lost Fortress').
    """
    p = Path(save_or_game_path).resolve()
    save_dir = p if p.is_dir() else p.parent

    # Identifica a raiz do jogo
    if save_dir.name.lower() in ("save", "saves", "savedata"):
        if save_dir.parent.name.lower() == "www":
            game_dir = save_dir.parent.parent
        else:
            game_dir = save_dir.parent
    elif save_dir.parent.name.lower() in ("save", "saves") and save_dir.parent.parent.name.lower() == "www":
        game_dir = save_dir.parent.parent.parent
    else:
        game_dir = save_dir

    # 1. Se raw_title foi fornecido, limpa e valida se não é ruído ou stem de save
    if raw_title:
        cleaned = clean_noisy_title(raw_title)
        if cleaned and not is_generic_or_save_name(cleaned):
            return cleaned

    # 2. Busca Game.ini (RPG Maker XP / VX / VX Ace / Wolf RPG)
    ini_candidates = [
        game_dir / "Game.ini",
        game_dir / "game.ini",
        save_dir / "Game.ini",
        save_dir.parent / "Game.ini"
    ]
    for ini_path in ini_candidates:
        if ini_path.is_file():
            try:
                import configparser
                cfg = configparser.ConfigParser(interpolation=None)
                cfg.read(ini_path, encoding="utf-8-sig")
                if cfg.has_section("Game") and cfg.has_option("Game", "Title"):
                    ini_title = cfg.get("Game", "Title").strip()
                    cleaned_ini = clean_noisy_title(ini_title)
                    if cleaned_ini and not is_generic_or_save_name(cleaned_ini):
                        return cleaned_ini
            except Exception:
                try:
                    lines = ini_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
                    for line in lines:
                        if line.strip().lower().startswith("title="):
                            ini_title = line.split("=", 1)[1].strip()
                            cleaned_ini = clean_noisy_title(ini_title)
                            if cleaned_ini and not is_generic_or_save_name(cleaned_ini):
                                return cleaned_ini
                except Exception:
                    pass

    # 3. Busca package.json (RPG Maker MV / MZ NW.js / Electron)
    pkg_candidates = [
        game_dir / "package.json",
        game_dir / "www" / "package.json",
        save_dir.parent / "package.json",
        save_dir.parent / "www" / "package.json"
    ]
    for pkg_path in pkg_candidates:
        if pkg_path.is_file():
            try:
                with open(pkg_path, "r", encoding="utf-8-sig") as f:
                    pkg_data = json.load(f)
                pkg_title = (
                    pkg_data.get("window", {}).get("title") or
                    pkg_data.get("title") or
                    pkg_data.get("name")
                )
                if pkg_title:
                    cleaned_pkg = clean_noisy_title(str(pkg_title))
                    if cleaned_pkg and not is_generic_or_save_name(cleaned_pkg):
                        return cleaned_pkg
            except Exception:
                pass

    # 4. Fallback para o nome do diretório do jogo
    # Ex: /mnt/hdd/game/Warrior Maiden Lecia and the Lost Fortress/Save -> 'Warrior Maiden Lecia and the Lost Fortress'
    if game_dir.name and not is_generic_or_save_name(game_dir.name):
        return game_dir.name

    if game_dir.parent and not is_generic_or_save_name(game_dir.parent.name):
        return game_dir.parent.name

    return game_dir.name or "Jogo RPG Maker"


class LibraryManager:
    """Gerencia a biblioteca local de jogos e o histórico de arquivos recentes."""

    def __init__(self, config_file: Optional[Path] = None):
        if config_file:
            self.config_file = Path(config_file).resolve()
        else:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                base_dir = Path(xdg_config) / "save-maker"
            else:
                base_dir = Path.home() / ".config" / "save-maker"
            self.config_file = base_dir / "library.json"

        self.data: Dict[str, Any] = {
            "recent_files": [],
            "games": {}
        }
        self.load()

    def load(self):
        """Carrega os dados persistidos da biblioteca e migra títulos corrompidos."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                if "recent_files" not in self.data:
                    self.data["recent_files"] = []
                if "games" not in self.data:
                    self.data["games"] = {}

                # Migração automática de títulos corrompidos existentes
                changed = False
                for g_key, g_val in list(self.data.get("games", {}).items()):
                    cur_title = g_val.get("title", "")
                    if not g_val.get("custom_title"):
                        if is_generic_or_save_name(cur_title) or "Pular balão" in cur_title or cur_title.startswith("v1.01 | TL:"):
                            save_target = g_val.get("save_dir") or g_key
                            new_t = resolve_game_title(save_target, raw_title=cur_title, engine=g_val.get("engine", ""))
                            if new_t and new_t != cur_title:
                                g_val["title"] = new_t
                                changed = True

                for r in self.data.get("recent_files", []):
                    r_title = r.get("title", "")
                    if is_generic_or_save_name(r_title) or "Pular balão" in r_title or r_title.startswith("v1.01 | TL:"):
                        new_rt = resolve_game_title(r.get("path", ""), raw_title="", engine=r.get("engine", ""))
                        if new_rt and new_rt != r_title:
                            r["title"] = new_rt
                            changed = True

                if changed:
                    self.save()

            except Exception as e:
                logger.error(f"Erro ao carregar {self.config_file}: {e}")

    def save(self):
        """Persiste atomicamente os dados da biblioteca."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.config_file.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            tmp_file.replace(self.config_file)
        except Exception as e:
            logger.error(f"Erro ao salvar biblioteca em {self.config_file}: {e}")

    def add_recent_file(self, path: str | Path, engine: str = "", title: str = ""):
        """Adiciona ou atualiza um save na lista de recentes com título inteligente."""
        p = Path(path).resolve()
        p_str = str(p)

        resolved_title = resolve_game_title(p, raw_title=title, engine=engine)

        recents = [r for r in self.data.get("recent_files", []) if r.get("path") != p_str]
        entry = {
            "path": p_str,
            "filename": p.name,
            "engine": engine,
            "title": resolved_title,
            "last_opened": time.time()
        }
        recents.insert(0, entry)
        self.data["recent_files"] = recents[:20]
        self.save()

    def get_recent_files(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna os arquivos recentes existentes com tempo relativo formatado."""
        res = []
        for r in self.data.get("recent_files", []):
            p = Path(r["path"])
            r_copy = dict(r)
            r_copy["exists"] = p.exists()
            r_copy["relative_time"] = self._format_relative_time(r.get("last_opened", 0))
            res.append(r_copy)
            if len(res) >= limit:
                break
        return res

    def register_game(self, save_path: str | Path, engine: str = "", title: str = "", data_dir: Optional[str | Path] = None) -> Dict[str, Any]:
        """Registra ou atualiza um jogo na biblioteca a partir do caminho de um save ou pasta."""
        p = Path(save_path).resolve()
        save_dir = p if p.is_dir() else p.parent

        # Identifica a raiz do jogo
        if save_dir.name.lower() in ("save", "saves", "savedata"):
            if save_dir.parent.name.lower() == "www":
                game_dir = save_dir.parent.parent
            else:
                game_dir = save_dir.parent
        elif save_dir.parent.name.lower() in ("save", "saves") and save_dir.parent.parent.name.lower() == "www":
            game_dir = save_dir.parent.parent.parent
        else:
            game_dir = save_dir

        game_key = str(game_dir)
        game_info = self.data["games"].get(game_key, {})

        # Preserva título se foi customizado manualmente pelo usuário
        if game_info.get("custom_title") and game_info.get("title"):
            game_title = game_info["title"]
        else:
            game_title = resolve_game_title(p, raw_title=title, engine=engine)

        game_info.update({
            "path": game_key,
            "title": game_title,
            "save_dir": str(save_dir),
            "data_dir": str(data_dir) if data_dir else game_info.get("data_dir", ""),
            "engine": engine or game_info.get("engine", "RPG Maker"),
            "last_opened": time.time()
        })
        self.data["games"][game_key] = game_info
        self.save()
        return game_info

    def rename_game(self, game_key: str, new_title: str) -> bool:
        """Permite ao usuário renomear manualmente um jogo na biblioteca."""
        t = new_title.strip()
        if not t:
            return False

        gk_resolved = str(Path(game_key).resolve())
        target_info = None

        if gk_resolved in self.data.get("games", {}):
            target_info = self.data["games"][gk_resolved]
        else:
            # Tenta encontrar por matching
            for k, g in self.data.get("games", {}).items():
                if k == game_key or g.get("save_dir") == game_key:
                    target_info = g
                    break

        if target_info:
            target_info["title"] = t
            target_info["custom_title"] = True

            # Atualiza também nos recentes que pertencem a esse jogo
            save_dir = target_info.get("save_dir", "")
            for r in self.data.get("recent_files", []):
                p_r = r.get("path", "")
                if p_r.startswith(target_info["path"]) or (save_dir and p_r.startswith(save_dir)):
                    r["title"] = t

            self.save()
            return True
        return False

    def get_games(self) -> List[Dict[str, Any]]:
        """Retorna todos os jogos registrados."""
        games = list(self.data.get("games", {}).values())
        games.sort(key=lambda g: g.get("last_opened", 0), reverse=True)
        return games

    def scan_game_slots(self, game_path: str | Path, current_open_file: Optional[str | Path] = None) -> List[Dict[str, Any]]:
        """
        Varre a pasta de saves de um jogo e retorna a lista de slots com metadados.
        """
        gp = Path(game_path).resolve()
        game_key = str(gp)
        game_data = self.data.get("games", {}).get(game_key, {})
        save_dir_str = game_data.get("save_dir")

        if save_dir_str and Path(save_dir_str).exists():
            save_dir = Path(save_dir_str)
        elif (gp / "www" / "save").exists():
            save_dir = gp / "www" / "save"
        elif (gp / "save").exists():
            save_dir = gp / "save"
        elif (gp / "Saves").exists():
            save_dir = gp / "Saves"
        elif (gp / "Save").exists():
            save_dir = gp / "Save"
        elif gp.is_dir():
            save_dir = gp
        else:
            save_dir = gp.parent

        if not save_dir.exists():
            return []

        patterns = ["*.rpgsave", "*.rmmzsave", "*.rvdata2", "*.rvdata", "*.rxdata", "*.lsd", "Save*.sav", "SaveData*.sav"]
        all_save_files: Dict[str, Path] = {}
        for pat in patterns:
            for f in save_dir.glob(pat):
                if not f.name.endswith(".bak"):
                    all_save_files[f.name] = f

        # Carrega dados do global.rpgsave para MV/MZ caso exista
        global_info: Dict[int, Dict[str, Any]] = {}
        global_file = save_dir / "global.rpgsave"
        if not global_file.exists():
            global_file = save_dir / "global.rmmzsave"

        if global_file.exists():
            try:
                import json
                raw_txt = global_file.read_text(encoding="utf-8-sig", errors="ignore")
                g_data = json.loads(raw_txt)
                if isinstance(g_data, list):
                    for idx, slot_data in enumerate(g_data):
                        if slot_data and isinstance(slot_data, dict):
                            global_info[idx] = slot_data
            except Exception:
                pass

        cur_p = Path(current_open_file).resolve() if current_open_file else None

        # Monta a lista unificada de slots
        slots = []
        for name, fpath in all_save_files.items():
            slot_num = self._extract_slot_number(name)
            stat = fpath.stat()
            bak_path = fpath.with_name(f"{name}.bak")
            has_bak = bak_path.exists()

            # Status do slot
            is_current = bool(cur_p and cur_p == fpath.resolve())
            if is_current:
                status = "Aberto agora"
            elif has_bak:
                status = "Editado"
            else:
                status = "Existente"

            # Metadados do global se disponíveis
            playtime = ""
            date_str = time.strftime("%d/%m %H:%M", time.localtime(stat.st_mtime))
            heroes_summary = ""

            if slot_num is not None and slot_num in global_info:
                g_slot = global_info[slot_num]
                playtime = g_slot.get("playtime", "")
                if "characters" in g_slot:
                    chars = g_slot.get("characters", [])
                    heroes_summary = f"{len(chars)} heróis" if chars else ""

            slots.append({
                "slot_number": slot_num,
                "slot_label": f"Slot {slot_num}" if slot_num is not None else name,
                "filename": name,
                "path": str(fpath),
                "mtime": stat.st_mtime,
                "date_str": date_str,
                "playtime": playtime,
                "heroes": heroes_summary,
                "status": status,
                "is_current": is_current,
                "has_backup": has_bak
            })

        slots.sort(key=lambda s: (s["slot_number"] if s["slot_number"] is not None else 9999, s["filename"]))
        return slots

    def discover_neighboring_games(self, reference_path: str | Path) -> List[Dict[str, Any]]:
        """Descobre jogos vizinhos no mesmo diretório pai ou diretório de jogos."""
        ref = Path(reference_path).resolve()
        parent_dir = ref.parent
        if not parent_dir.exists():
            return []

        suggestions = []
        registered_keys = set(self.data.get("games", {}).keys())

        for sibling in parent_dir.iterdir():
            if sibling.is_dir() and sibling != ref:
                # Verifica se o irmão possui uma pasta save ou arquivos de save
                save_candidates = [
                    sibling / "save",
                    sibling / "Save",
                    sibling / "www" / "save",
                    sibling / "www" / "Save",
                    sibling
                ]
                for sc in save_candidates:
                    if sc.is_dir():
                        saves = list(sc.glob("*.rpgsave")) + list(sc.glob("*.rmmzsave")) + list(sc.glob("Save*.sav"))
                        if saves:
                            s_key = str(sibling)
                            if s_key not in registered_keys:
                                engine_detected = "Wolf RPG" if any(f.name.endswith(".sav") for f in saves) else "RPG Maker"
                                resolved_sug_title = resolve_game_title(sibling, engine=engine_detected)
                                suggestions.append({
                                    "name": resolved_sug_title,
                                    "path": s_key,
                                    "save_dir": str(sc),
                                    "saves_count": len(saves),
                                    "engine": engine_detected
                                })
                            break

        return suggestions

    def _extract_slot_number(self, filename: str) -> Optional[int]:
        m = re.search(r'(?:file|slot|savedata)(\d+)', filename, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
        return None

    def _format_relative_time(self, ts: float) -> str:
        diff = time.time() - ts
        if diff < 60:
            return "agora mesmo"
        elif diff < 3600:
            mins = int(diff // 60)
            return f"há {mins} min" if mins > 1 else "há 1 min"
        elif diff < 86400:
            hrs = int(diff // 3600)
            return f"há {hrs}h"
        else:
            days = int(diff // 86400)
            return f"há {days}d"
