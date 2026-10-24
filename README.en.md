<div align="center">

<!-- GitHub Status Badges -->
![GitHub Stars](https://www.shieldcn.dev/github/stars/bgluis/save-maker.svg?variant=secondary&size=sm)
![GitHub Forks](https://www.shieldcn.dev/github/forks/bgluis/save-maker.svg?variant=secondary&size=sm)
![Watchers](https://www.shieldcn.dev/github/watchers/bgluis/save-maker.svg?variant=secondary&size=sm)
![Contributors](https://www.shieldcn.dev/github/contributors/bgluis/save-maker.svg?theme=emerald&size=sm)
![License](https://www.shieldcn.dev/github/license/bgluis/save-maker.svg?variant=ghost&size=sm)

<br/>

<!-- Technology Badges -->
![Python](https://shieldcn.dev/badge/Python-3.10+-3776AB.svg?logo=python&variant=branded&size=sm)
![Linux](https://shieldcn.dev/badge/Linux-FCC624.svg?logo=linux&variant=branded&size=sm)

  <h3>Save Maker</h3>
  Universal save editor and converter for RPG Maker and related games with modern GUI and interactive TUI.

  <br/>

  <p align="center">
    <a href="README.md">🇧🇷 <b>Versão em Português</b></a> &nbsp;•&nbsp; 🇺🇸 <b>English</b>
  </p>
</div>

# 📖 About
**Save Maker** is a universal, modern, and high-performance save file editor and converter for games built with **RPG Maker** and related game engines. It is designed to inspect, modify, and recover save files using either a **Modern Graphical User Interface (GUI)** powered by CustomTkinter or an **Interactive Terminal User Interface (TUI)** built with Rich, alongside convenient command-line utilities for direct JSON export and import.

### 🎮 Supported Engines and Formats

| Engine / Format | Extensions | Support Level | Verification Status |
|---|---|---|---|
| **RPG Maker MV** | `.rpgsave` | Full Support | ✅ Verified with real saves and database fixtures (`Classes.json` stat curves, `JsonEx` `@a` array wrappers, LZString/None/Zlib/Gzip compressions). |
| **RPG Maker MZ** | `.rmmzsave` | Supported | ✅ Verified for `zlib`, `zlib-utf8` (`pako`), and `LZString` compressions. |
| **RPG Maker VX Ace / VX / XP** | `.rvdata2`, `.rvdata`, `.rxdata` | Supported | ✅ Multi-object Ruby Marshal 4.8 stream preservation via `marshal_io.py`. |
| **RPG Maker 2000 / 2003** | `.lsd` | Basic / Experimental | ⚠️ Support for chunk `0x6D` (`SaveInventory` gold and items) in binary `LcfSaveData` format. |
| **Generic JSON / Web Saves** | `.json`, `.sav`, `.dat`, `.txt` | Supported | ✅ Parsing and manipulation of JSON-structured or encoded web saves. |
| **Wolf RPG Editor / ウディタ** | `.sav` | Experimental | ⚠️ Experimental support for decoding and basic editing. Item, weapon and armor names come from `Data/BasicData/DataBase.dat`; if automatic pairing is wrong, create `wolf_name_map.json` (e.g. `{"7": 2, "8": 3, "9": 4}`, save type → DataBase type) in the save folder. |

### Key Features
- **Modern Graphical User Interface (GUI):**
  - Built with **CustomTkinter** with full Dark and Light mode support.
  - Native Drag & Drop for save files.
  - Specialized tabs for **Overview**, **Inventory**, **Party / Heroes**, **Switches & Variables**, **Quick Cheats**, and **Raw JSON Tree**.
  - Responsive performance architecture: `ttk.Treeview` with lazy tab rendering (renders only on tab switch), paginated JSON tree (200 items per batch on demand), and background thread I/O to keep the interface smooth and non-blocking.
- **Smart Game Database Autodiscovery:**
  - Automatically identifies game data folders (`data/`, `Data/`, `www/data/`) and correlates numeric IDs with real in-game names for items, weapons, armor, heroes, switches, and variables.
- **Interactive CLI / TUI:**
  - Colorful terminal menus and tables directly in your terminal via Rich, with automatic fallback for SSH sessions or headless environments.
- **Command-Line Interface:**
  - Direct conversion between save files and readable JSON (`export` and `import`).
- **Native Linux Desktop Integration:**
  - Right-click context menus for file managers (Nautilus, Nemo, Dolphin) and global CLI aliases (`save-maker`, `savemaker`, `rse`, etc.).

# 📋 Motivation
Just a tool to edit saves when games bug out.

# 💻 Getting Started

### Requirements
- [Python 3.10+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/)
- [Tkinter / python3-tk](https://docs.python.org/3/library/tkinter.html) *(required for GUI on Linux: `sudo apt install python3-tk` or distribution equivalent)*
- [GNU Make](https://www.gnu.org/software/make/) *(optional, for simplified Makefile execution)*

### Installation

1. Clone the project repository:
  ```sh
  git clone https://github.com/bgluis/save-maker.git
  ```

2. Navigate to the project directory:
  ```sh
  cd save-maker
  ```

3. Set up the virtual environment and install dependencies using one of the methods below:

  **Method 1: Automatic via Makefile (Recommended)**
  ```sh
  make venv
  ```

  **Method 2: Manual via Python venv**
  ```sh
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

### Usage

- **Modern Graphical User Interface (GUI):**
  ```sh
  # Start default GUI
  make gui
  # Or directly via Python:
  ./.venv/bin/python main.py

  # Open a save file directly in the GUI:
  ./.venv/bin/python main.py /path/to/save/file1.rpgsave
  ```

- **Interactive Terminal Interface (CLI / TUI):**
  ```sh
  # Start in interactive mode
  make run
  # Or directly via Python:
  ./.venv/bin/python main.py --interactive
  ```

- **Direct Export & Import (Command Line):**
  ```sh
  # Export supported save file to readable JSON
  ./.venv/bin/python main.py export save/file1.rpgsave save1.json

  # Import JSON back into game save format
  ./.venv/bin/python main.py import save1.json save/file1_edited.rpgsave
  ```

- **Linux Desktop Integration (Aliases & Right-Click Menus):**
  ```sh
  # Installs terminal shortcuts and file manager context menus (Nautilus, Nemo, Dolphin)
  make install
  ```

- **Run Automated Tests:**
  ```sh
  make test
  # Or directly via pytest:
  ./.venv/bin/python -m pytest -v
  ```

# 💻 Getting Started on Windows

### Requirements
- [Python 3.10+](https://www.python.org/downloads/) — check **"Add Python to PATH"** during setup
- [Git](https://git-scm.com/)

### Installation

1. Clone the repository:
  ```powershell
  git clone https://github.com/bgluis/save-maker.git
  cd save-maker
  ```

2. Create the virtual environment and install dependencies:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\activate
  pip install -r requirements.txt
  ```

3. *(Optional)* Global system installation with terminal aliases:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
  ```

### Usage on Windows

- **Modern Graphical User Interface (GUI):**
  ```powershell
  .\.venv\Scripts\python.exe main.py
  ```

- **Interactive Terminal Interface (CLI / TUI):**
  ```powershell
  .\.venv\Scripts\python.exe main.py --interactive
  ```

- **Direct Export & Import:**
  ```powershell
  .\.venv\Scripts\python.exe main.py export save\file1.rpgsave save1.json
  .\.venv\Scripts\python.exe main.py import save1.json save\file1_edited.rpgsave
  ```

> **Terminal note:** For the best CLI/TUI experience (colors and Unicode), use **Windows Terminal** or **PowerShell 7+**. In legacy CMD, run `chcp 65001` before starting.

# 🤝 Contributors
 <a href="https://github.com/bgluis/save-maker/graphs/contributors">
   <img src="https://contrib.rocks/image?repo=bgluis/save-maker"/>
 </a>
