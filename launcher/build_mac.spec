# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for Cursiv on macOS.

Usage (from repo root, on a Mac with Python + PyInstaller):
    pip install pyinstaller PyQt6 anthropic openai psutil bcrypt PyJWT
    pyinstaller launcher/build_mac.spec

Output:
    dist/Cursiv/CursivLauncher        (GUI .app equivalent — windowed)
    dist/Cursiv/cursiv                (CLI terminal binary)

Differences from Windows build:
  - No PyQt6-WebEngine (install separately if you want the substrate browser)
  - No win32api / win32gui / win32con / servicemanager
  - console=True CLI binary is named 'cursiv' (lowercase, no .exe)
  - Icon uses .icns format — add one at launcher/resources/icons/cursiv.icns
"""

import sys
from pathlib import Path

ROOT     = Path(SPECPATH).parent
LAUNCHER = ROOT / "launcher"
CURSIV   = ROOT / "cursiv_v215"
SERVICES = ROOT / "services"

block_cipher = None

datas = [
    (str(LAUNCHER / "resources" / "icons"), "launcher/resources/icons"),
    (str(CURSIV), "cursiv_v215"),
    (str(SERVICES), "services"),
]

from PyInstaller.utils.hooks import collect_data_files
for _pkg in ("uvicorn",):
    try:
        datas += collect_data_files(_pkg)
    except Exception:
        pass

hiddenimports = [
    "cursiv_v215", "cursiv_v215.ui", "cursiv_v215.ui.chat_cli",
    "cursiv_v215.core", "cursiv_v215.core.agent",
    "cursiv_v215.guardian", "cursiv_v215.guardian.access_gate",
    "cursiv_v215.memory", "cursiv_v215.runtime", "cursiv_v215.runtime.config",
    "cursiv_v215.academy", "cursiv_v215.council", "cursiv_v215.forge",
    "cursiv_v215.knowledge", "cursiv_v215.nexus", "cursiv_v215.substrate",
    "cursiv_v215.agents", "cursiv_v215.agents.civilization_agent",
    "cursiv_v215.agents.bible_study",
    "cursiv_v215.nexus.epistemic_engine", "cursiv_v215.nexus.model_identities",
    "cursiv_v215.nexus.forge", "cursiv_v215.runtime.setup_check",
    "cursiv_v215.web", "cursiv_v215.web.app",
    "cursiv_launcher", "login_dialog", "tray",
    "PyQt6", "PyQt6.QtWidgets", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.sip",
    "uvicorn", "fastapi", "starlette", "pydantic",
    "psutil", "anthropic", "openai", "httpx",
    "bcrypt",
]

_excludes = [
    "tkinter", "matplotlib", "scipy", "pandas",
    "torch", "torchvision", "tensorflow", "keras",
    "transformers", "tokenizers", "datasets",
    "notebook", "ipykernel",
    # Windows-only
    "win32api", "win32con", "win32gui", "win32event",
    "win32serviceutil", "win32service", "servicemanager",
]

# ── GUI launcher (windowed, no terminal window on launch) ─────────────────────
a = Analysis(
    [str(LAUNCHER / "main.py")],
    pathex=[str(ROOT), str(LAUNCHER)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=_excludes,
    cipher=block_cipher,
    noarchive=False,
)

# ── CLI terminal (console=True — proper stdin/stdout) ─────────────────────────
a_cli = Analysis(
    [str(LAUNCHER / "cli_main.py")],
    pathex=[str(ROOT), str(LAUNCHER)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=_excludes,
    cipher=block_cipher,
    noarchive=False,
)

pyz     = PYZ(a.pure,     a.zipped_data, cipher=block_cipher)
pyz_cli = PYZ(a_cli.pure, a_cli.zipped_data, cipher=block_cipher)

exe_gui = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="CursivLauncher",
    debug=False, strip=False, upx=False,
    console=False,
    # icon=str(LAUNCHER / "resources" / "icons" / "cursiv.icns"),
)

exe_cli = EXE(
    pyz_cli, a_cli.scripts, [],
    exclude_binaries=True,
    name="cursiv",
    debug=False, strip=False, upx=False,
    console=True,
    # icon=str(LAUNCHER / "resources" / "icons" / "cursiv.icns"),
)

coll = COLLECT(
    exe_gui, a.binaries, a.zipfiles, a.datas,
    exe_cli, a_cli.binaries, a_cli.zipfiles, a_cli.datas,
    strip=False, upx=False,
    name="Cursiv",
)
