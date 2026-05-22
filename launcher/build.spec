# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for Cursiv Launcher.

Usage (from repo root):
    pyinstaller launcher/build.spec

Output: dist/Cursiv/Cursiv.exe  (one-dir bundle, windowed)
"""

import sys
from pathlib import Path

try:
    from PyInstaller.utils.hooks import collect_all
    _we_d,  _we_b,  _we_h  = collect_all("PyQt6.QtWebEngineWidgets")
    _wec_d, _wec_b, _wec_h = collect_all("PyQt6.QtWebEngineCore")
    _extra_datas    = _we_d  + _wec_d
    _extra_binaries = _we_b  + _wec_b
    _extra_hidden   = _we_h  + _wec_h
except Exception:
    _extra_datas    = []
    _extra_binaries = []
    _extra_hidden   = []

ROOT = Path(SPECPATH).parent          # repo root (one level above launcher/)
LAUNCHER = ROOT / "launcher"
CURSIV   = ROOT / "cursiv_v215"
SERVICES = ROOT / "services"

block_cipher = None

# ── Data files bundled into the exe ──────────────────────────────────────────
datas = [
    # Icons
    (str(LAUNCHER / "resources" / "icons"), "launcher/resources/icons"),
    # cursiv_v215 package (everything — models, prompts, templates)
    (str(CURSIV), "cursiv_v215"),
    # Services (guardian_service standalone runner)
    (str(SERVICES), "services"),
]

# ── Hidden imports that PyInstaller static analysis misses ───────────────────
hiddenimports = [
    # cursiv_v215 sub-packages
    "cursiv_v215",
    "cursiv_v215.ui",
    "cursiv_v215.ui.chat_app",
    "cursiv_v215.ui.chat_cli",
    "cursiv_v215.core",
    "cursiv_v215.core.agent",
    "cursiv_v215.core.constitution",
    "cursiv_v215.core.memory",
    "cursiv_v215.core.rate_limiter",
    "cursiv_v215.core.scan_display",
    "cursiv_v215.core.strand",
    "cursiv_v215.guardian",
    "cursiv_v215.guardian.access_gate",
    "cursiv_v215.guardian.security_questions",
    "cursiv_v215.guardian.decoys",
    "cursiv_v215.guardian.obfuscation",
    "cursiv_v215.guardian.temple_guardian",
    "bcrypt",
    "cursiv_v215.memory",
    "cursiv_v215.runtime",
    "cursiv_v215.runtime.config",
    "cursiv_v215.runtime.db",
    "cursiv_v215.runtime.evolution_engine",
    "cursiv_v215.runtime.guardian",
    "cursiv_v215.runtime.metrics",
    "cursiv_v215.academy",
    "cursiv_v215.cli",
    "cursiv_v215.council",
    "cursiv_v215.dugout",
    "cursiv_v215.forge",
    "cursiv_v215.knowledge",
    "cursiv_v215.nexus",
    "cursiv_v215.obsidian",
    "cursiv_v215.weave",
    # launcher
    "cursiv_launcher",
    "cursiv_browser",
    "login_dialog",
    "tray",
    # PyQt6
    "PyQt6",
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.sip",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "starlette",
    "pydantic",
    "cursiv_v215.web",
    "cursiv_v215.web.app",
    "cursiv_v215.web.db",
    "cursiv_v215.web.auth",
    "cursiv_v215.web.sentinel",
    "cursiv_v215.web.maze",
    "cursiv_v215.substrate",
    "cursiv_v215.substrate.activator",
    "cursiv_v215.substrate.ruw",
    "cursiv_v215.substrate.curs_lang",
    # Windows / system
    "win32api",
    "win32con",
    "win32gui",
    "win32event",
    "win32serviceutil",
    "win32service",
    "servicemanager",
    "psutil",
    "anthropic",
    "openai",
    "httpx",
    "PIL",
]

a = Analysis(
    [str(LAUNCHER / "main.py")],
    pathex=[str(ROOT), str(LAUNCHER)],
    binaries=[] + _extra_binaries,
    datas=datas + _extra_datas,
    hiddenimports=hiddenimports + _extra_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "pandas", "IPython",
        # Heavy ML libs — not needed by launcher/chat UI; load separately at runtime
        "torch", "torchvision", "torchaudio",
        "tensorflow", "keras", "jax",
        "bitsandbytes",
        "transformers", "tokenizers", "datasets",
        "sentence_transformers",
        "sklearn", "xgboost", "lightgbm",
        "cv2", "skimage",
        # Jupyter / dev tools
        "notebook", "ipykernel", "ipywidgets",
        # Unused stdlib
        "unittest", "doctest", "pdb",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Cursiv",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                          # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(LAUNCHER / "resources" / "icons" / "cursiv.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Cursiv",                          # output: dist\Cursiv\
)
