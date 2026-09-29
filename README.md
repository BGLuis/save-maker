<div align="center">

<!-- Badges de Status do GitHub -->
![GitHub Stars](https://www.shieldcn.dev/github/stars/bgluis/save-maker.svg?variant=secondary&size=sm)
![GitHub Forks](https://www.shieldcn.dev/github/forks/bgluis/save-maker.svg?variant=secondary&size=sm)
![Watchers](https://www.shieldcn.dev/github/watchers/bgluis/save-maker.svg?variant=secondary&size=sm)
![Contributors](https://www.shieldcn.dev/github/contributors/bgluis/save-maker.svg?theme=emerald&size=sm)
![License](https://www.shieldcn.dev/github/license/bgluis/save-maker.svg?variant=ghost&size=sm)

<br/>

<!-- Badges das Tecnologias Utilizadas -->
![Python](https://shieldcn.dev/badge/Python-3.10+-3776AB.svg?logo=python&variant=branded&size=sm)
![Linux](https://shieldcn.dev/badge/Linux-FCC624.svg?logo=linux&variant=branded&size=sm)

  <h3>Save Maker</h3>
  Editor e conversor universal de saves para jogos de RPG Maker e correlatos com GUI e TUI interativa.

  <br/>

  <p align="center">
    <a href="#-português">🇧🇷 <b>Português</b></a> &nbsp;•&nbsp; <a href="#-english">🇺🇸 <b>English</b></a>
  </p>
</div>

---

## 🇧🇷 Português

# 📖 Sobre
O **Save Maker** é um editor e conversor universal, moderno e de alto desempenho para arquivos de save de jogos desenvolvidos em **RPG Maker** e motores correlatos. Ele foi projetado para permitir a visualização, modificação e recuperação de saves tanto através de uma **Interface Gráfica Moderna (GUI)** construída com CustomTkinter quanto por uma **Interface Interativa no Terminal (TUI)** desenvolvida com Rich, além de utilitários de linha de comando para exportação e importação direta.

### Recursos Principais
- **Suporte Universal a Motores de Jogos:**
  - **RPG Maker MV** (`.rpgsave` — compressões None, Zlib, Gzip e LZString)
  - **RPG Maker MZ** (`.rmmzsave` — formato LZString moderno)
  - **RPG Maker VX Ace** (`.rvdata2` — serialização Ruby Marshal)
  - **RPG Maker VX** (`.rvdata` — Ruby Marshal)
  - **RPG Maker XP** (`.rxdata` — Ruby Marshal)
  - **RPG Maker 2000 / 2003** (`.lsd` — formato binário LcfSaveData)
  - **Wolf RPG Editor / ウディタ** (`.sav` — decodificação e edição)
  - **Saves em JSON e Web** (`.json`, `.sav`, `.dat`, `.txt`)
- **Autodescoberta Inteligente de Banco de Dados:**
  - Identifica automaticamente pastas de dados do jogo (`data/`, `Data/`, `www/data/`) e correlaciona IDs numéricos com os nomes reais de itens, armas, armaduras, heróis, switches e variáveis.
- **Múltiplas Formas de Utilização:**
  - **GUI Moderna:** Drag & Drop nativo de arquivos, alternância entre temas Dark e Light, abas para Visão Geral, Inventário, Grupo, Switches & Variáveis, Cheats Rápidos e Árvore JSON Raw.
  - **CLI / TUI Interativa:** Menus visuais e coloridos diretamente no terminal via Rich, com fallback automático para conexões SSH e ambientes headless.
  - **Linha de Comando:** Conversão direta ou em lote entre arquivos de save de RPG Maker e JSON legível.
- **Integração Nativa com o Desktop Linux:**
  - Menus de contexto no botão direito para gerenciadores de arquivos (Nautilus, Nemo, Dolphin) e atalhos de terminal globais (`save-maker`, `savemaker`, `rse`, etc.).

# 📋 Motivo
Apenas uma ferramenta para editar saves quando jogos bugam.

# 💻 Como iniciar

### Requisitos
- [Python 3.10+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/)
- [Tkinter / python3-tk](https://docs.python.org/3/library/tkinter.html) *(necessário para execução da GUI no Linux: `sudo apt install python3-tk` ou equivalente da sua distribuição)*
- [GNU Make](https://www.gnu.org/software/make/) *(opcional, para execução simplificada dos comandos via Makefile)*

### Instalação

1. Clone o repositório do projeto:
  ```sh
  git clone https://github.com/bgluis/save-maker.git
  ```

2. Navegue até o diretório do projeto:
  ```sh
  cd save-maker
  ```

3. Configure o ambiente virtual e instale as dependências através de um dos métodos abaixo:

  **Método 1: Automático via Makefile (Recomendado)**
  ```sh
  make venv
  ```

  **Método 2: Manual via Python venv**
  ```sh
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

### Como Usar

- **Interface Gráfica Moderna (GUI):**
  ```sh
  # Iniciar a GUI padrão
  make gui
  # Ou diretamente via Python:
  ./.venv/bin/python main.py

  # Abrir diretamente um arquivo de save na GUI:
  ./.venv/bin/python main.py /caminho/para/o/save/file1.rpgsave
  ```

- **Interface Interativa no Terminal (CLI / TUI):**
  ```sh
  # Iniciar no modo interativo
  make run
  # Ou diretamente via Python:
  ./.venv/bin/python main.py --interactive
  ```

- **Exportação e Importação Direta (Linha de Comando):**
  ```sh
  # Exportar save suportado para JSON legível
  ./.venv/bin/python main.py export save/file1.rpgsave save1.json

  # Importar JSON de volta para o formato de save do jogo
  ./.venv/bin/python main.py import save1.json save/file1_editado.rpgsave
  ```

- **Integração Global no Desktop Linux (Atalhos & Botão Direito):**
  ```sh
  # Instala atalhos de terminal e ações de contexto no Nautilus, Nemo e Dolphin
  make install
  ```

- **Executar Testes Automatizados:**
  ```sh
  make test
  ```

# 🤝 Contribuidores
 <a href="https://github.com/bgluis/save-maker/graphs/contributors">
   <img src="https://contrib.rocks/image?repo=bgluis/save-maker"/>
 </a>

---

## 🇺🇸 English

<p align="center">
  <i>(A standalone English version is also available at <a href="README.en.md">README.en.md</a>)</i>
</p>

# 📖 About
**Save Maker** is a universal, modern, and high-performance save file editor and converter for games built with **RPG Maker** and related game engines. It is designed to inspect, modify, and recover save files using either a **Modern Graphical User Interface (GUI)** powered by CustomTkinter or an **Interactive Terminal User Interface (TUI)** built with Rich, alongside convenient command-line utilities for direct JSON export and import.

### Key Features
- **Universal Engine Support:**
  - **RPG Maker MV** (`.rpgsave` — None, Zlib, Gzip compressions, and LZString)
  - **RPG Maker MZ** (`.rmmzsave` — modern LZString format)
  - **RPG Maker VX Ace** (`.rvdata2` — Ruby Marshal serialization)
  - **RPG Maker VX** (`.rvdata` — Ruby Marshal)
  - **RPG Maker XP** (`.rxdata` — Ruby Marshal)
  - **RPG Maker 2000 / 2003** (`.lsd` — binary LcfSaveData format)
  - **Wolf RPG Editor / ウディタ** (`.sav` — decoding and editing)
  - **JSON & Web Saves** (`.json`, `.sav`, `.dat`, `.txt`)
- **Smart Game Database Autodiscovery:**
  - Automatically identifies game data folders (`data/`, `Data/`, `www/data/`) and correlates numeric IDs with real in-game names for items, weapons, armor, heroes, switches, and variables.
- **Multiple Ways to Run:**
  - **Modern GUI:** Native Drag & Drop, Dark and Light mode toggle, specialized tabs for Overview, Inventory, Party, Switches & Variables, Quick Cheats, and Raw JSON Tree.
  - **Interactive CLI / TUI:** Colorful terminal menus and tables directly in your terminal via Rich, with automatic fallback for SSH sessions or headless environments.
  - **Command-Line Interface:** Direct conversion between save files and readable JSON.
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
  ```

# 🤝 Contributors
 <a href="https://github.com/bgluis/save-maker/graphs/contributors">
   <img src="https://contrib.rocks/image?repo=bgluis/save-maker"/>
 </a>
