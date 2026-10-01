# Save Maker — Script de Instalação Global para Windows
# Cria o venv, instala dependências e adiciona atalhos ao PATH do usuário.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 -Uninstall

param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
$VenvDir     = Join-Path $ProjectRoot ".venv"
$WrapperBat  = Join-Path $ProjectRoot "scripts\rpg-save-editor.bat"
$InstallDir  = Join-Path $env:LOCALAPPDATA "Programs\save-maker"

# ── Desinstalação ──────────────────────────────────────────────────────────────
if ($Uninstall) {
    Write-Host "Removendo Save Maker do PATH e diretório de instalação..."
    if (Test-Path $InstallDir) {
        Remove-Item -Path $InstallDir -Recurse -Force
        Write-Host "✓ Diretório '$InstallDir' removido."
    }
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User") -split ";"
    $newPath  = ($userPath | Where-Object { $_ -ne $InstallDir }) -join ";"
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    Write-Host "✓ '$InstallDir' removido do PATH do usuário."
    Write-Host ""
    Write-Host "Desinstalação concluída. Reinicie o terminal para aplicar."
    exit 0
}

# ── Instalação ─────────────────────────────────────────────────────────────────

# 1. Verificar Python disponível
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python não encontrado. Instale Python 3.10+ em https://www.python.org/downloads/ e marque 'Add Python to PATH'."
}

Write-Host "--- Instalando Save Maker no Windows ---"
Write-Host "Diretório do projeto: $ProjectRoot"
Write-Host ""

# 2. Criar venv se não existir
if (-not (Test-Path $VenvDir)) {
    Write-Host "Criando ambiente virtual em '$VenvDir'..."
    python -m venv $VenvDir
} else {
    Write-Host "✓ Ambiente virtual já existe em '$VenvDir'."
}

# 3. Instalar dependências
Write-Host "Instalando dependências de requirements.txt..."
& "$VenvDir\Scripts\pip.exe" install --upgrade pip -q
& "$VenvDir\Scripts\pip.exe" install -r "$ProjectRoot\requirements.txt"
Write-Host "✓ Dependências instaladas."
Write-Host ""

# 4. Criar diretório de instalação
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# 5. Copiar wrapper e criar aliases
$aliases = @{
    "save-maker.bat"    = $WrapperBat
    "savemaker.bat"     = $WrapperBat
    "save-editor.bat"   = $WrapperBat
    "rpg-save-editor.bat" = $WrapperBat
    "rse.bat"           = $WrapperBat
    "rpgse.bat"         = $WrapperBat
    "sm.bat"            = $WrapperBat
}

foreach ($entry in $aliases.GetEnumerator()) {
    $dest = Join-Path $InstallDir $entry.Key
    Copy-Item -Path $entry.Value -Destination $dest -Force
    Write-Host "✓ Atalho '$($entry.Key)' instalado."
}

# 6. Adicionar ao PATH do usuário (persistente entre sessões)
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$userPath;$InstallDir", "User")
    Write-Host ""
    Write-Host "✓ '$InstallDir' adicionado ao PATH do usuário."
} else {
    Write-Host "✓ '$InstallDir' já está no PATH do usuário."
}

Write-Host ""
Write-Host "=================================================================="
Write-Host "  ✓ Instalação concluída com sucesso!"
Write-Host "  Reinicie o terminal e use em qualquer pasta:"
Write-Host ""
Write-Host "    save-maker --interactive     # CLI / TUI interativa"
Write-Host "    save-maker gui               # Interface gráfica"
Write-Host "    rse export save\file1.rpgsave save1.json"
Write-Host "=================================================================="
