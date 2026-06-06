# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for Cursiv.

Two EXEs in one bundle (share the same _internal folder):
  - CursivLauncher.exe  console=False  GUI launcher / tray
  - Cursiv.exe          console=True   CLI terminal (like 'claude' command)

Usage (from repo root):
    pyinstaller launcher/build.spec

Output:
    dist/Cursiv/CursivLauncher.exe   (windowed GUI)
    dist/Cursiv/Cursiv.exe           (console CLI)
"""

import sys
from pathlib import Path

try:
    import PyQt6 as _qt6
    _qt6_dir = Path(_qt6.__file__).parent
    _qt6_bin = _qt6_dir / "Qt6" / "bin"
    _qt6_res = _qt6_dir / "Qt6" / "resources"
    _qt6_tr  = _qt6_dir / "Qt6" / "translations"

    _extra_binaries = []
    _extra_datas    = []
    _extra_hidden   = ["PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets"]

    # Qt WebEngine DLLs + subprocess helper — must land in bundle root
    # so Windows DLL search finds them when the .pyd loads
    for _fname in [
        "Qt6WebEngine.dll", "Qt6WebEngineCore.dll",
        "Qt6WebEngineWidgets.dll", "QtWebEngineProcess.exe",
    ]:
        _fp = _qt6_bin / _fname
        if _fp.exists():
            _extra_binaries.append((str(_fp), "."))

    # ICU data / pak files WebEngine needs at runtime
    if _qt6_res.exists():
        _extra_datas.append((str(_qt6_res), "resources"))

    # WebEngine translation catalogs only (keeps size down)
    if _qt6_tr.exists():
        for _tf in _qt6_tr.glob("qtwebengine*"):
            _extra_datas.append((str(_tf), "translations"))

except Exception as _e:
    print(f"[build.spec] WebEngine collection skipped: {_e}")
    _extra_binaries = []
    _extra_datas    = []
    _extra_hidden   = []

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT     = Path(SPECPATH).parent          # repo root (one level above launcher/)
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

# Collect data files from packages that read files at import time
for _pkg in ("safehttpx", "gradio", "gradio_client", "uvicorn"):
    try:
        datas += collect_data_files(_pkg)
    except Exception:
        pass

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
    "cursiv_v215.agents",
    "cursiv_v215.agents.civilization_agent",
    "cursiv_v215.agents.bible_study",
    "cursiv_v215.nexus.epistemic_engine",
    "cursiv_v215.nexus.model_identities",
    "cursiv_v215.nexus.forge",
    "cursiv_v215.runtime.setup_check",
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
    "gradio",
    "gradio_client",
    "safehttpx",
]

_excludes = [
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
]

# ── GUI launcher Analysis (windowed, no console) ─────────────────────────────
a = Analysis(
    [str(LAUNCHER / "main.py")],
    pathex=[str(ROOT), str(LAUNCHER)],
    binaries=[] + _extra_binaries,
    datas=datas + _extra_datas,
    hiddenimports=hiddenimports + _extra_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── CLI terminal Analysis (console=True, proper stdin/stdout from the start) ─
a_cli = Analysis(
    [str(LAUNCHER / "cli_main.py")],
    pathex=[str(ROOT), str(LAUNCHER)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_excludes + _extra_hidden,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz     = PYZ(a.pure,     a.zipped_data,     cipher=block_cipher)
pyz_cli = PYZ(a_cli.pure, a_cli.zipped_data, cipher=block_cipher)

# ── GUI EXE — windowed, no console window ────────────────────────────────────
exe_gui = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CursivLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(LAUNCHER / "resources" / "icons" / "cursiv.ico"),
)

# ── CLI EXE — console=True, proper handles, no AttachConsole needed ──────────
exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name="Cursiv",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(LAUNCHER / "resources" / "icons" / "cursiv.ico"),
)

# ── One-dir bundle — both EXEs share the same _internal folder ───────────────
coll = COLLECT(
    exe_gui,
    a.binaries,
    a.zipfiles,
    a.datas,
    exe_cli,
    a_cli.binaries,
    a_cli.zipfiles,
    a_cli.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Cursiv",                          # output: dist\Cursiv\
)
