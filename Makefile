# ==============================================================================
# Makefile para Save Maker (RPG Maker Universal Edition)
# ==============================================================================

SHELL := /bin/bash
PROJECT_DIR := $(shell pwd)
VENV_DIR := $(PROJECT_DIR)/.venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
CLI_WRAPPER := $(PROJECT_DIR)/scripts/rpg-save-editor
LOCAL_BIN := $(HOME)/.local/bin
BINARY_NAME := save-maker
ALIASES ?= savemaker save-editor rpg-save-editor rpgse rse sm

# Fallback se a .venv não existir
ifeq ($(wildcard $(PYTHON)),)
    PYTHON := python3
    PIP := pip3
endif

.PHONY: all help run cli gui install install-cli uninstall-cli install-desktop uninstall-desktop uninstall venv test clean add-alias remove-alias list-aliases

all: help

help:
	@echo ""
	@echo "=================================================================="
	@echo "  🎮 Save Maker — Comandos Disponíveis"
	@echo "=================================================================="
	@echo ""
	@echo "  Execução Rápida:"
	@echo "    make run             - Inicia no modo interativo no terminal (CLI/TUI)"
	@echo "    make cli             - Mesmo que 'make run'"
	@echo "    make gui             - Inicia na interface gráfica moderna (CustomTkinter)"
	@echo ""
	@echo "  Instalação Global no Sistema (Usuário):"
	@echo "    make install         - Instala tudo (atalhos no terminal + menu de botão direito)"
	@echo "    make install-cli     - Instala '$(BINARY_NAME)' e atalhos ($(ALIASES)) em ~/.local/bin"
	@echo "    make uninstall-cli   - Remove o comando '$(BINARY_NAME)' e seus atalhos de ~/.local/bin"
	@echo "    make add-alias       - Adiciona novo atalho de terminal (ex: make add-alias ALIAS=se)"
	@echo "    make remove-alias    - Remove um atalho do terminal (ex: make remove-alias ALIAS=se)"
	@echo "    make list-aliases    - Lista os atalhos atualmente instalados"
	@echo "    make install-desktop - Instala ações de botão direito (Nautilus, Nemo, Dolphin)"
	@echo "    make uninstall-desktop - Remove atalhos e menus de botão direito"
	@echo "    make uninstall       - Desinstalação completa (terminal + desktop)"
	@echo ""
	@echo "  Desenvolvimento & Ambiente:"
	@echo "    make venv            - Cria/atualiza o ambiente virtual (.venv) e dependências"
	@echo "    make test            - Executa todos os testes automatizados"
	@echo "    make clean           - Limpa diretórios temporários e caches (__pycache__)"
	@echo ""
	@echo "=================================================================="
	@echo ""

run:
	@$(PYTHON) main.py --interactive

cli: run

gui:
	@$(PYTHON) main.py gui

venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Criando ambiente virtual em $(VENV_DIR)..."; \
		python3 -m venv $(VENV_DIR); \
	fi
	@echo "Instalando dependências de requirements.txt..."
	@$(PIP) install -r requirements.txt

install-cli:
	@echo "Configurando wrapper executável..."
	@chmod +x $(CLI_WRAPPER)
	@mkdir -p $(LOCAL_BIN)
	@ln -sf $(CLI_WRAPPER) $(LOCAL_BIN)/$(BINARY_NAME)
	@echo "✓ Comando principal '$(BINARY_NAME)' instalado em $(LOCAL_BIN)/$(BINARY_NAME)"
	@for alias in $(ALIASES); do \
		ln -sf $(CLI_WRAPPER) $(LOCAL_BIN)/$$alias; \
		echo "✓ Atalho '$$alias' instalado em $(LOCAL_BIN)/$$alias -> $(BINARY_NAME)"; \
	done
	@if [[ ":$$PATH:" != *":$(LOCAL_BIN):"* ]]; then \
		echo "⚠️  AVISO: '$(LOCAL_BIN)' pode não estar no seu PATH. Adicione-o ao seu ~/.bashrc ou ~/.zshrc se necessário."; \
	fi
	@echo ""
	@echo "Exemplo de uso em qualquer pasta (inclusive dentro da pasta do jogo):"
	@echo "  $(BINARY_NAME) --interactive"
	@echo "  save-editor"
	@echo "  rse save/file1.rpgsave"
	@echo "  $(BINARY_NAME) export save1.rpgsave save1.json"

uninstall-cli:
	@echo "Removendo $(LOCAL_BIN)/$(BINARY_NAME)..."
	@rm -f $(LOCAL_BIN)/$(BINARY_NAME)
	@for alias in $(ALIASES); do \
		rm -f $(LOCAL_BIN)/$$alias; \
		echo "✓ Atalho '$$alias' removido."; \
	done
	@echo "✓ Comandos desinstalados do terminal."

add-alias:
	@if [ -z "$(ALIAS)" ]; then \
		echo "Erro: Especifique o atalho com ALIAS=<nome>. Exemplo: make add-alias ALIAS=se"; \
		exit 1; \
	fi
	@mkdir -p $(LOCAL_BIN)
	@ln -sf $(CLI_WRAPPER) $(LOCAL_BIN)/$(ALIAS)
	@echo "✓ Atalho '$(ALIAS)' instalado com sucesso em $(LOCAL_BIN)/$(ALIAS) -> $(CLI_WRAPPER)"

remove-alias:
	@if [ -z "$(ALIAS)" ]; then \
		echo "Erro: Especifique o atalho com ALIAS=<nome>. Exemplo: make remove-alias ALIAS=se"; \
		exit 1; \
	fi
	@rm -f $(LOCAL_BIN)/$(ALIAS)
	@echo "✓ Atalho '$(ALIAS)' removido de $(LOCAL_BIN)."

list-aliases:
	@chmod +x $(CLI_WRAPPER)
	@$(CLI_WRAPPER) --list-aliases

install-desktop:
	@chmod +x scripts/install_linux_integration.sh
	@bash scripts/install_linux_integration.sh

uninstall-desktop:
	@chmod +x scripts/uninstall_linux_integration.sh
	@bash scripts/uninstall_linux_integration.sh

install: install-cli install-desktop
	@echo "✓ Instalação completa concluída com sucesso!"

uninstall: uninstall-cli uninstall-desktop
	@echo "✓ Desinstalação completa concluída."

test:
	@echo "Executando testes automatizados..."
	@$(PYTHON) tests/test_database_autodiscovery.py
	@$(PYTHON) tests/test_all_formats.py
	@$(PYTHON) tests/test_cli_interactive.py
	@$(PYTHON) tests/test_performance.py
	@$(PYTHON) tests/test_editor.py

clean:
	@echo "Limpando arquivos temporários e caches..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Limpeza concluída."
