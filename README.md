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
![Windows](https://shieldcn.dev/badge/Windows-10%2F11-0078D4.svg?logo=windows&variant=branded&size=sm)

  <h3>Save Maker</h3>
  Editor e conversor universal de saves para jogos de RPG Maker e correlatos com GUI e TUI interativa.

  <br/>

  <p align="center">
    <b>Português</b> &nbsp;•&nbsp; <a href="README.en.md">English</a>
  </p>
</div>

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

# 💻 Como iniciar no Windows

### Requisitos
- [Python 3.10+](https://www.python.org/downloads/) — marque **"Add Python to PATH"** durante a instalação
- [Git](https://git-scm.com/)

### Instalação

1. Clone o repositório:
  ```powershell
  git clone https://github.com/bgluis/save-maker.git
  cd save-maker
  ```

2. Crie o ambiente virtual e instale as dependências:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\activate
  pip install -r requirements.txt
  ```

3. *(Opcional)* Instalação global com atalhos no terminal:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
  ```

### Como Usar no Windows

- **Interface Gráfica Moderna (GUI):**
  ```powershell
  .\.venv\Scripts\python.exe main.py
  ```

- **Interface Interativa no Terminal (CLI / TUI):**
  ```powershell
  .\.venv\Scripts\python.exe main.py --interactive
  ```

- **Exportação e Importação Direta:**
  ```powershell
  .\.venv\Scripts\python.exe main.py export save\file1.rpgsave save1.json
  .\.venv\Scripts\python.exe main.py import save1.json save\file1_editado.rpgsave
  ```

> **Nota sobre terminal:** Para melhor experiência com a CLI/TUI (cores e Unicode), use o **Windows Terminal** ou **PowerShell 7+**. No CMD legado, execute `chcp 65001` antes de iniciar.

# 🤝 Contribuidores
 <a href="https://github.com/bgluis/save-maker/graphs/contributors">
   <img src="https://contrib.rocks/image?repo=bgluis/save-maker"/>
 </a>
