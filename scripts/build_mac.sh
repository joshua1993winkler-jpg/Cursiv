#!/usr/bin/env bash
# Build Cursiv for macOS.
# Run from the repo root on a Mac with Python 3.11+ installed.
#
# Quick start:
#   chmod +x scripts/build_mac.sh
#   ./scripts/build_mac.sh

set -e
cd "$(dirname "$0")/.."

echo "[Cursiv Mac Build] Installing Python dependencies..."
pip install --quiet pyinstaller PyQt6 anthropic openai psutil bcrypt "PyJWT>=2.8" \
    uvicorn fastapi starlette pydantic httpx

echo "[Cursiv Mac Build] Running PyInstaller..."
pyinstaller launcher/build_mac.spec --noconfirm

echo "[Cursiv Mac Build] Done!"
echo "  GUI launcher: dist/Cursiv/CursivLauncher"
echo "  CLI terminal:  dist/Cursiv/cursiv"
echo ""
echo "To run the CLI: ./dist/Cursiv/cursiv"
echo "To run the GUI: ./dist/Cursiv/CursivLauncher"
echo ""
echo "To create a .dmg (optional, requires create-dmg):"
echo "  brew install create-dmg"
echo "  create-dmg --volname Cursiv --app-drop-link 425 120 Cursiv.dmg dist/Cursiv/"
