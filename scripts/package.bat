@echo off
:: ============================================================
:: Cursiv - Package Script
:: Compiles installer\cursiv_setup.iss into Cursiv-Setup-3.14-U07.exe
:: Requires Inno Setup 6 (iscc must be in PATH or found below).
:: Run from repo root:  scripts\package.bat
:: ============================================================
setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo.
echo  Cursiv Installer Packager
echo  =========================================
echo.

:: ---- Locate iscc -------------------------------------------
set "ISCC="

where iscc >nul 2>&1
if %errorlevel% equ 0 set "ISCC=iscc"

:: Check Program Files (x86) directly - no for-loop, no nesting
if not defined ISCC (
    set "_T=%ProgramFiles(x86)%\Inno Setup 6\iscc.exe"
    if exist "!_T!" set "ISCC=!_T!"
)

:: Check Program Files (64-bit)
if not defined ISCC (
    set "_T=%ProgramFiles%\Inno Setup 6\iscc.exe"
    if exist "!_T!" set "ISCC=!_T!"
)

:: Check user AppData\Local\Programs (non-admin install)
if not defined ISCC (
    set "_T=%LOCALAPPDATA%\Programs\Inno Setup 6\iscc.exe"
    if exist "!_T!" set "ISCC=!_T!"
)

if not defined ISCC (
    echo [ERROR] Inno Setup 6 compiler ^(iscc^) not found.
    echo.
    echo  Download from: https://jrsoftware.org/isdl.php
    echo  After installing, re-run this script.
    pause & exit /b 1
)
echo  Inno Setup: %ISCC%

:: ---- Check build exists ------------------------------------
if not exist "dist\Cursiv\Cursiv.exe" (
    echo [ERROR] dist\Cursiv\Cursiv.exe not found.
    echo  Run scripts\build.bat first.
    pause & exit /b 1
)

:: ---- Compile installer -------------------------------------
echo  Compiling installer...
echo.
"%ISCC%" "installer\cursiv_setup.iss"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Inno Setup compilation failed.
    pause & exit /b 1
)

:: ---- Verify output -----------------------------------------
if not exist "installer\Output\Cursiv-Setup-3.14-U07.exe" (
    echo [ERROR] Installer not found at installer\Output\Cursiv-Setup-3.14-U07.exe
    pause & exit /b 1
)

echo.
echo  Installer created!
echo  File: installer\Output\Cursiv-Setup-3.14-U07.exe
echo.
pause
