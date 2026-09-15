# 🎮 Save Maker

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Interface: CustomTkinter & Rich](https://img.shields.io/badge/UI-CustomTkinter%20%7C%20Rich%20TUI-informational.svg)]()

**Save Maker** é um editor e conversor universal, moderno e de alta performance para arquivos de save de **RPG Maker**. Suporta desde versões clássicas em Ruby até os motores mais recentes em JavaScript/Web, com interface gráfica moderna em **CustomTkinter** (Dark/Light mode), **TUI interativa rica no terminal** com **Rich**, descoberta automática de banco de dados do jogo e integração nativa com o desktop Linux.

---

## 🌟 Recursos Principais

- **Suporte Universal a Motores de RPG Maker:**
  - **RPG Maker MV** (`.rpgsave` — compressão None/Zlib/Gzip + LZString)
  - **RPG Maker MZ** (`.rmmzsave` — formato LZString moderno)
  - **RPG Maker VX Ace** (`.rvdata2` — serialização Ruby Marshal)
  - **RPG Maker VX** (`.rvdata` — Ruby Marshal)
  - **RPG Maker XP** (`.rxdata` — Ruby Marshal)
  - **RPG Maker 2000 / 2003** (`.lsd` — formato binário LcfSaveData)
  - **Saves em JSON e Web** (`.json`, `.sav`, `.dat`, `.txt`)
- **Descoberta Automática de Banco de Dados:**
  - Detecta automaticamente pastas de dados do jogo (`data/`, `Data/`, `www/data/`)
  - Carrega e correlaciona nomes reais e amigáveis de **Itens**, **Armas**, **Armaduras**, **Heróis/Atores**, **Switches** e **Variáveis**
- **Interface Gráfica Moderna (GUI):**
  - Construída com **CustomTkinter** com suporte a Dark e Light Mode
  - Drag & Drop nativo de arquivos de save
  - Abas especializadas para **Visão Geral**, **Equipe / Heróis**, **Inventário**, **Switches & Variáveis**, **Atalhos / Cheats** e **Árvore Completa (JSON Raw)**
  - Otimização extrema de renderização com tabelas virtuais e lazy loading (< 0.1ms para atualizações)
- **CLI Interativa no Terminal (TUI):**
  - Modo interativo no terminal utilizando a biblioteca **Rich**
  - Navegação visual por menus, tabelas formatadas, edição direta de valores e cheats rápidos
  - Fallback automático para terminal quando executado via SSH ou em ambientes sem servidor gráfico (headless)
- **Integração com Desktop Linux:**
  - Menus de contexto no botão direito para gerenciadores de arquivos (**Nautilus**, **Nemo**, **Dolphin**)
  - Associação de tipos MIME e atalhos de terminal globais (`save-maker`, `savemaker`, `rpg-save-editor`, `save-editor`, `rse`, `sm`)

---

## 📦 Instalação

### 1. Clonar o repositório
```bash
git clone https://github.com/BGLuis/save-maker.git
cd save-maker
```

### 2. Configurar o ambiente virtual e dependências
```bash
make venv
```
Ou manualmente:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 🚀 Como Usar

### Interface Gráfica Moderna (GUI)
```bash
# Iniciar a GUI padrão
make gui
# Ou via Python
./.venv/bin/python main.py

# Abrir diretamente um arquivo de save na GUI
./.venv/bin/python main.py /caminho/para/o/save/file1.rpgsave
```

### CLI Interativa no Terminal (TUI)
```bash
# Iniciar no modo interativo
make run
# ou
./.venv/bin/python main.py --interactive
# ou especificando o save
./.venv/bin/python main.py cli /caminho/para/o/save/file1.rpgsave
```

### Exportação e Importação Direta (Linha de Comando)
```bash
# Exportar qualquer save suportado para JSON limpo
./.venv/bin/python main.py export save/file1.rpgsave save1.json

# Importar JSON de volta para o formato de save do jogo
./.venv/bin/python main.py import save1.json save/file1_editado.rpgsave
```

---

## 💻 Instalação Global no Linux (Atalhos & Botão Direito)

Você pode instalar os atalhos globais de terminal e integração com o sistema operacional com apenas um comando:

```bash
# Instala tudo (atalhos no terminal + menus de botão direito nos gerenciadores de arquivos)
make install
```

Após instalado, você pode rodar em qualquer pasta:
```bash
# Atalhos disponíveis no terminal:
save-maker [arquivo]
savemaker [arquivo]
save-editor [arquivo]
rpg-save-editor [arquivo]
rse [arquivo]
sm [arquivo]
```

Para adicionar ou remover atalhos customizados:
```bash
make add-alias ALIAS=se
make remove-alias ALIAS=se
make list-aliases
```

Para desinstalar as integrações:
```bash
make uninstall
```

---

## 🧪 Testes Automatizados

O projeto possui uma suíte abrangente de testes automatizados:
```bash
make test
```

Os testes cobrem:
- Autodescoberta e resolução de bancos de dados (`test_database_autodiscovery.py`)
- Compatibilidade roundtrip de todos os adaptadores e motores (`test_all_formats.py`)
- CLI Interativa e comandos (`test_cli_interactive.py`)
- Performance, latência de renderização e cache (`test_performance.py`)
- Exportação e importação legado/core (`test_editor.py`)

---

## 📂 Estrutura do Projeto

```text
save-maker/
├── main.py                  # Ponto de entrada universal (CLI / GUI / Export / Import)
├── Makefile                 # Comandos para build, instalação, execução e testes
├── requirements.txt         # Dependências do projeto
├── scripts/
│   ├── core/                # Adaptadores de motores (MV/MZ, Ruby/VX/XP, LSD/2000/2003, Generic)
│   │   ├── base_adapter.py
│   │   ├── database_manager.py
│   │   ├── detector.py
│   │   ├── generic_adapter.py
│   │   ├── lsd_adapter.py
│   │   ├── mv_mz_adapter.py
│   │   └── ruby_adapter.py
│   ├── cli/                 # Interface de linha de comando rica (TUI com Rich)
│   │   └── interactive.py
│   ├── ui/                  # Interface Gráfica Moderna (CustomTkinter)
│   │   ├── modern_app.py
│   │   └── theme.py
│   ├── rpg-save-editor      # Wrapper executável para PATH global
│   ├── install_linux_integration.sh
│   └── uninstall_linux_integration.sh
├── tests/                   # Bateria de testes unitários e de performance
└── save/                    # Amostras e dados para desenvolvimento/testes
```

---

## 📄 Licença

Distribuído sob a licença MIT. Veja `LICENSE` para mais detalhes.
