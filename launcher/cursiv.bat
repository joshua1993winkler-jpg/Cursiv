@echo off
:: ============================================================
:: cursiv.bat — Cursiv CLI chat interface
:: Installed to {app}\ and added to user PATH by the installer.
:: Usage: cursiv [any args are forwarded to chat_cli]
:: ============================================================

:: Resolve the directory this .bat lives in (works from any cwd)
set "CURSIV_APP=%~dp0"
:: Strip trailing backslash
if "%CURSIV_APP:~-1%"=="\" set "CURSIV_APP=%CURSIV_APP:~0,-1%"

set "VENV_PYTHON=%CURSIV_APP%\cursiv_env\Scripts\python.exe"
set "VENV_PIP=%CURSIV_APP%\cursiv_env\Scripts\pip.exe"

:: ── Sanity check: venv must exist ────────────────────────────
if not exist "%VENV_PYTHON%" (
    echo.
    echo  [Cursiv] Virtual environment not found.
    echo  Expected: %VENV_PYTHON%
    echo.
    echo  Run the bootstrap script to set up the environment:
    echo    powershell -File "%CURSIV_APP%\scripts\cursiv_bootstrap.ps1" -AppDir "%CURSIV_APP%"
    echo.
    pause
    exit /b 1
)

:: ── Add {app} to PATH for this session so sub-imports find launchers ─────────
set "PATH=%CURSIV_APP%;%PATH%"

:: ── Set PYTHONPATH so `import cursiv_v215` resolves from {app} ───────────────
set "PYTHONPATH=%CURSIV_APP%;%PYTHONPATH%"

:: ── Launch ───────────────────────────────────────────────────
::  眼 of Horus appears inside chat_cli on startup
"%VENV_PYTHON%" -m cursiv_v215.ui.chat_cli %*
