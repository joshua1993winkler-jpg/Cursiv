"""
Cursiv CLI — clean console entry point.

This is the executable users get when they type `cursiv` in any terminal.
Built with console=True so stdin/stdout are real console handles from the start.
No AttachConsole, no prompt_toolkit conflicts, no encoding hacks needed.
"""

import sys
import os
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = Path(__file__).parent.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Windows: UTF-8 output + ANSI colors ──────────────────────────────────────
if sys.platform == "win32":
    # Enable ANSI escape codes in Windows console (Windows 10+)
    try:
        import ctypes
        _k32 = ctypes.windll.kernel32
        # ENABLE_PROCESSED_OUTPUT | ENABLE_WRAP_AT_EOL_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        _k32.SetConsoleMode(_k32.GetStdHandle(-11), 0x0007)
    except Exception:
        pass

    # UTF-8 output — avoids cp1252 crashes on Unicode output
    try:
        import io
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
    except Exception:
        pass

    # Set console code page to UTF-8
    try:
        _k32.SetConsoleOutputCP(65001)
        _k32.SetConsoleCP(65001)
    except Exception:
        pass


def main() -> None:
    # Ollama health check before launching UI
    try:
        from cursiv_v215.runtime.setup_check import ensure_ollama
        ensure_ollama(auto_start=True, quiet=False)
    except Exception:
        pass

    from cursiv_v215.ui.chat_cli import main as _cli_main
    _cli_main()


if __name__ == "__main__":
    main()
