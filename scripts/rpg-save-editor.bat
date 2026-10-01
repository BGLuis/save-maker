@echo off
:: Save Maker — CLI Wrapper para Windows
:: Garante encoding UTF-8 para Rich/TUI funcionar corretamente no CMD legado
chcp 65001 >nul 2>&1
set PYTHONUTF8=1

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."

:: Detecta Python no venv (.venv\Scripts\), senão usa o Python do sistema
if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe"
) else if exist "%ROOT_DIR%\.venv\Scripts\python3.exe" (
    set "PYTHON=%ROOT_DIR%\.venv\Scripts\python3.exe"
) else (
    set "PYTHON=python"
)

"%PYTHON%" "%ROOT_DIR%\main.py" %*
