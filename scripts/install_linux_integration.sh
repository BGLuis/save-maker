#!/usr/bin/env bash
# ==============================================================================
# Script de Instalação de Integração com o Desktop Linux (Menu de Botão Direito)
# ==============================================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI_WRAPPER="$PROJECT_ROOT/scripts/rpg-save-editor"

echo "--- Instalando Integração com o Desktop Linux ---"
echo "Diretório do projeto: $PROJECT_ROOT"

# 1. Registrar Tipos MIME para saves de RPG Maker
MIME_DIR="$HOME/.local/share/mime/packages"
mkdir -p "$MIME_DIR"

cat > "$MIME_DIR/rpgmaker-save.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-rpgsave">
    <comment>RPG Maker MV Save</comment>
    <glob pattern="*.rpgsave"/>
  </mime-type>
  <mime-type type="application/x-rmmzsave">
    <comment>RPG Maker MZ Save</comment>
    <glob pattern="*.rmmzsave"/>
  </mime-type>
  <mime-type type="application/x-rvdata2">
    <comment>RPG Maker VX Ace Save</comment>
    <glob pattern="*.rvdata2"/>
  </mime-type>
  <mime-type type="application/x-rvdata">
    <comment>RPG Maker VX Save</comment>
    <glob pattern="*.rvdata"/>
  </mime-type>
  <mime-type type="application/x-rxdata">
    <comment>RPG Maker XP Save</comment>
    <glob pattern="*.rxdata"/>
  </mime-type>
  <mime-type type="application/x-lsd">
    <comment>RPG Maker 2000/2003 Save</comment>
    <glob pattern="*.lsd"/>
  </mime-type>
</mime-info>
EOF

if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database "$HOME/.local/share/mime" >/dev/null 2>&1 || true
    echo "✓ Tipos MIME registrados e atualizados."
fi

# 2. Criar entrada de aplicativo (.desktop)
APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR"

cat > "$APP_DIR/rpg-save-editor.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=RPG Maker Save Editor
GenericName=Save Editor
Comment=Editor Universal de Saves de RPG Maker (MV, MZ, VX Ace, VX, XP, 2000/2003, JSON)
Exec=$CLI_WRAPPER %f
Icon=applications-games
Terminal=false
Categories=Game;Utility;
MimeType=application/x-rpgsave;application/x-rmmzsave;application/x-rvdata2;application/x-rvdata;application/x-rxdata;application/x-lsd;application/json;
Actions=OpenCLI;ExportJSON;

[Desktop Action OpenCLI]
Name=Editar no Terminal Interativo
Exec=$CLI_WRAPPER --interactive %f
Terminal=true

[Desktop Action ExportJSON]
Name=Exportar para JSON
Exec=$CLI_WRAPPER export %f %f.json
Terminal=false
EOF

echo "✓ Atalho de aplicativo desktop criado em $APP_DIR/rpg-save-editor.desktop"

# 3. Ações de Botão Direito para Nemo e Caja (Cinnamon / MATE / Linux Mint)
NEMO_DIR="$HOME/.local/share/nemo/actions"
[ -d "$HOME/.local/share/file-manager/actions" ] && NEMO_DIR="$HOME/.local/share/file-manager/actions"
mkdir -p "$NEMO_DIR"

cat > "$NEMO_DIR/rpg-save-editor.nemo_action" <<EOF
[Nemo Action]
Name=Editar com RPG Maker Save Editor
Comment=Abre o save no RPG Maker Save Editor
Exec=$CLI_WRAPPER %F
Icon-Name=applications-games
Selection=any
Extensions=rpgsave;rmmzsave;rvdata2;rvdata;rxdata;lsd;json;sav;dat;
EOF

cat > "$NEMO_DIR/rpg-save-editor-cli.nemo_action" <<EOF
[Nemo Action]
Name=Editar no Terminal (RPG Maker CLI)
Comment=Abre o save no terminal interativo
Exec=x-terminal-emulator -e "$CLI_WRAPPER --interactive %F"
Icon-Name=utilities-terminal
Selection=any
Extensions=rpgsave;rmmzsave;rvdata2;rvdata;rxdata;lsd;json;sav;dat;
EOF

echo "✓ Ações de contexto para Nemo/Caja criadas."

# 4. Scripts de Botão Direito para Nautilus (GNOME)
NAUTILUS_DIR="$HOME/.local/share/nautilus/scripts"
mkdir -p "$NAUTILUS_DIR"

cat > "$NAUTILUS_DIR/Editar Save (RPG Maker GUI)" <<EOF
#!/usr/bin/env bash
$CLI_WRAPPER "\$1"
EOF
chmod +x "$NAUTILUS_DIR/Editar Save (RPG Maker GUI)"

cat > "$NAUTILUS_DIR/Editar Save no Terminal (CLI)" <<EOF
#!/usr/bin/env bash
x-terminal-emulator -e "$CLI_WRAPPER --interactive \"\$1\"" || gnome-terminal -- "$CLI_WRAPPER" --interactive "\$1" || konsole -e "$CLI_WRAPPER" --interactive "\$1"
EOF
chmod +x "$NAUTILUS_DIR/Editar Save no Terminal (CLI)"

echo "✓ Scripts de contexto para Nautilus criados."

# 5. Service Menus para Dolphin (KDE Plasma 5 e 6)
for kde_dir in "$HOME/.local/share/kservices5/ServiceMenus" "$HOME/.local/share/kio/servicemenus"; do
    mkdir -p "$kde_dir"
    cat > "$kde_dir/rpg-save-editor.desktop" <<EOF
[Desktop Entry]
Type=Service
ServiceTypes=KonqPopupMenu/Plugin
MimeType=application/x-rpgsave;application/x-rmmzsave;application/x-rvdata2;application/x-rvdata;application/x-rxdata;application/x-lsd;application/json;
Actions=openGUI;openCLI;exportJSON;
X-KDE-Priority=TopLevel

[Desktop Action openGUI]
Name=Abrir no RPG Maker Save Editor
Icon=applications-games
Exec=$CLI_WRAPPER %f

[Desktop Action openCLI]
Name=Editar no Terminal Interativo
Icon=utilities-terminal
Exec=$CLI_WRAPPER --interactive %f

[Desktop Action exportJSON]
Name=Exportar Save para JSON
Icon=document-export
Exec=$CLI_WRAPPER export %f %f.json
EOF
done

echo "✓ Service Menus para Dolphin (KDE) criados."

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo ""
echo "=================================================================="
echo "  ✓ Integração com o sistema concluída com sucesso!"
echo "  Agora você pode clicar com o botão direito em arquivos"
echo "  .rpgsave, .rmmzsave, .rvdata2, .rxdata, .lsd, etc."
echo "  e selecionar 'Editar com RPG Maker Save Editor'!"
echo "=================================================================="
