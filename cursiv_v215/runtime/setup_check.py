# cursiv_v215/runtime/setup_check.py
# Ollama health check and first-run guidance.
# Runs at startup — detects common install problems before they hit the user as a 404.

import json
import subprocess
import sys
import urllib.request
import urllib.error
import time


_OLLAMA_URL = "http://localhost:11434"

_MSG_NOT_RUNNING = """
=======================================================
  CURSIV -- FIRST-RUN SETUP
=======================================================

  The local AI engine (Ollama) is not running.

  Cursiv tried to start it automatically but could not
  find it. You may need to install it.

  STEP 1: Download and install Ollama (free, 1 min):
    https://ollama.com

  STEP 2: After installing, open a terminal and run:
    ollama pull llama3.1

  That downloads the AI model (~4.7 GB, one time only).
  After it finishes, restart Cursiv.

  If you have an Anthropic, OpenAI, or xAI API key,
  Cursiv can use those now -- Ollama is optional.
  Type: help  inside Cursiv to see key setup.
=======================================================
"""

_MSG_NO_MODEL = """
=======================================================
  CURSIV -- ONE MORE STEP
=======================================================

  Ollama is running but the AI model is not downloaded.
  This is a one-time setup (~4.7 GB).

  Open a terminal and run:
    ollama pull llama3.1

  While it downloads you can still use Cursiv if you
  have an API key (Anthropic, OpenAI, or xAI).

  Once the download finishes, everything works offline.
=======================================================
"""

_MSG_READY = ""  # nothing to show if all good


def check_ollama() -> dict:
    """
    Returns:
      {"running": bool, "has_model": bool, "models": list[str]}
    """
    try:
        req = urllib.request.Request(
            f"{_OLLAMA_URL}/api/tags",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        has_model = any(
            "llama3.1" in m or "llama3" in m
            for m in models
        )
        return {"running": True, "has_model": has_model, "models": models}
    except OSError:
        # Connection refused -- Ollama not installed or not running
        return {"running": False, "has_model": False, "models": []}
    except Exception:
        return {"running": False, "has_model": False, "models": []}


def _try_auto_start() -> bool:
    """
    Attempt to launch `ollama serve` in the background.
    Returns True if Ollama is reachable within 4 seconds.
    """
    try:
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
    except (FileNotFoundError, OSError):
        return False

    # Wait up to 4 seconds for it to come up
    for _ in range(4):
        time.sleep(1)
        if check_ollama()["running"]:
            return True
    return False


def ensure_ollama(auto_start: bool = True, quiet: bool = False) -> dict:
    """
    Check Ollama status. If not running and auto_start=True, try to start it.
    Prints guidance to console if setup is needed.

    Returns the final status dict.
    """
    status = check_ollama()

    if not status["running"] and auto_start:
        status = check_ollama()  # re-check after possible system-tray startup
        if not status["running"]:
            _try_auto_start()
            status = check_ollama()

    if not quiet:
        if not status["running"]:
            print(_MSG_NOT_RUNNING)
        elif not status["has_model"]:
            print(_MSG_NO_MODEL)

    return status
