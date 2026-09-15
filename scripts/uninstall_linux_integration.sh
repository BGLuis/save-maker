#!/usr/bin/env bash
# ==============================================================================
# Script de Desinstalação da Integração Desktop Linux
# ==============================================================================
set -e

echo "--- Removendo integrações com o Desktop Linux ---"

rm -f "$HOME/.local/share/applications/rpg-save-editor.desktop"
rm -f "$HOME/.local/share/nemo/actions/rpg-save-editor.nemo_action"
rm -f "$HOME/.local/share/nemo/actions/rpg-save-editor-cli.nemo_action"
rm -f "$HOME/.local/share/file-manager/actions/rpg-save-editor.nemo_action"
rm -f "$HOME/.local/share/file-manager/actions/rpg-save-editor-cli.nemo_action"
rm -f "$HOME/.local/share/nautilus/scripts/Editar Save (RPG Maker GUI)"
rm -f "$HOME/.local/share/nautilus/scripts/Editar Save no Terminal (CLI)"
rm -f "$HOME/.local/share/kservices5/ServiceMenus/rpg-save-editor.desktop"
rm -f "$HOME/.local/share/kio/servicemenus/rpg-save-editor.desktop"
rm -f "$HOME/.local/share/mime/packages/rpgmaker-save.xml"

if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database "$HOME/.local/share/mime" >/dev/null 2>&1 || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi

echo "✓ Todas as integrações de botão direito e atalhos de desktop foram removidas."
