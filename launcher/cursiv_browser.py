"""
Cursiv Browser — substrate-layer desktop browser.

Handles curs.http:// protocol, translates to the local substrate server.
Designed for integration with the Cursiv Launcher (PyQt6 + QWebEngineView).

Usage:
    from launcher.cursiv_browser import CursivBrowser, open_browser
    browser = open_browser()   # singleton, focus if already open
"""
from __future__ import annotations

import sys
import threading
import urllib.request
from pathlib import Path
from typing import Optional

try:
    from PyQt6.QtCore import QSize, Qt, QTimer, QUrl, pyqtSignal
    from PyQt6.QtGui import QFont, QIcon, QKeySequence, QShortcut
    from PyQt6.QtWidgets import (
        QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
        QMainWindow, QPushButton, QScrollArea, QSplitter,
        QStatusBar, QTextEdit, QVBoxLayout, QWidget,
    )
    from PyQt6.QtWebEngineCore import QWebEnginePage
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _HAS_WEB_ENGINE = True
except ImportError:
    _HAS_WEB_ENGINE = False

# ── Constants ─────────────────────────────────────────────────────────────────

_SUBSTRATE_HOST = "http://127.0.0.1:1969"
_CURS_SCHEMES   = ("curs.http://", "curs://", "curs.https://")

# Palette — matches the launcher
BG     = "#0b0b12"
BG2    = "#13131e"
BG3    = "#1a1a2e"
BORDER = "#2a2a3f"
GOLD   = "#FFD700"
LGOLD  = "#9B7B20"
SILVER = "#C8C8D4"
SILV2  = "#666680"
BLUE   = "#4a6aff"
GREEN  = "#38b060"
PURPLE = "#8844cc"

_BROWSER_QSS = f"""
QWidget {{
    background-color: {BG};
    color: {SILVER};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    border: none;
}}
QLabel  {{ background: transparent; }}
QLineEdit {{
    background: {BG2};
    color: {SILVER};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
    selection-background-color: {BLUE};
}}
QLineEdit:focus {{ border-color: {BLUE}; }}
QPushButton {{
    background: {BG2};
    color: {SILVER};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    min-width: 28px;
}}
QPushButton:hover   {{ background: {BG3}; border-color: {BLUE}; color: {GOLD}; }}
QPushButton:pressed {{ background: {BLUE}; color: #fff; }}
QPushButton:disabled {{ color: {SILV2}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {BG2};
}}
QScrollBar:vertical {{
    background: {BG2}; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 3px;
}}
QStatusBar {{ background: {BG2}; color: {SILV2}; font-size: 11px; }}
QSplitter::handle {{ background: {BORDER}; width: 1px; }}
"""

# ── URL translation ───────────────────────────────────────────────────────────

def _translate_url(raw: str) -> str:
    """
    Convert curs.http:// / curs:// addresses to the local substrate server.

    curs.http://cursiv.winklers-llc.ccursoivm/feed  →  http://127.0.0.1:1969/feed
    curs.http://ruw.cursiv.abc/node/42              →  http://127.0.0.1:1969/node/42
    curs://substrate/status                         →  http://127.0.0.1:1969/substrate/status
    http://...  or anything else                    →  unchanged
    """
    lower = raw.lower()
    for scheme in _CURS_SCHEMES:
        if lower.startswith(scheme):
            remainder = raw[len(scheme):]
            path = ("/" + remainder.split("/", 1)[1]) if "/" in remainder else "/"
            return _SUBSTRATE_HOST + path
    return raw


def _display_url(http_url: str) -> str:
    """Convert a real http URL back to curs.http:// display form."""
    prefix = _SUBSTRATE_HOST
    if http_url.startswith(prefix):
        path = http_url[len(prefix):] or "/"
        return f"curs.http://cursiv.local{path}"
    return http_url


# ── Custom web page — intercepts navigation ───────────────────────────────────

class _SubstratePage(QWebEnginePage):
    def acceptNavigationRequest(
        self,
        url: "QUrl",
        nav_type: "QWebEnginePage.NavigationType",
        is_main_frame: bool,
    ) -> bool:
        raw = url.toString()
        translated = _translate_url(raw)
        if translated != raw:
            self.setUrl(QUrl(translated))
            return False
        return True


# ── Substrate status panel ────────────────────────────────────────────────────

class _StatusPanel(QWidget):
    """Right-side rail: live substrate node count, recent activations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(210)
        self.setStyleSheet(f"background: {BG2};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        title = QLabel("Substrate")
        title.setStyleSheet(f"color: {PURPLE}; font-weight: bold; font-size: 12px;")
        outer.addWidget(title)

        self._nodes_lbl  = QLabel("Nodes: —")
        self._edges_lbl  = QLabel("Edges: —")
        self._energy_lbl = QLabel("Energy: —")
        self._acts_lbl   = QLabel("Activations: —")

        for lbl in (self._nodes_lbl, self._edges_lbl, self._energy_lbl, self._acts_lbl):
            lbl.setStyleSheet(f"color: {SILV2}; font-size: 11px;")
            outer.addWidget(lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        outer.addWidget(sep)

        log_title = QLabel("Recent")
        log_title.setStyleSheet(f"color: {PURPLE}; font-size: 11px; font-weight: bold;")
        outer.addWidget(log_title)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            f"background: {BG}; color: {SILV2}; font-size: 10px;"
            f" border: 1px solid {BORDER};"
        )
        self._log.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        outer.addWidget(self._log, 1)

        outer.addStretch(0)

        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(15_000)
        self._refresh()

    def _refresh(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        import json as _json
        try:
            with urllib.request.urlopen(
                f"{_SUBSTRATE_HOST}/substrate/status", timeout=3
            ) as r:
                data = _json.loads(r.read())
            layer = data.get("layer", {})
            acts  = data.get("activations", 0)
            # must call Qt widget updates on main thread — use a timer trick
            self._pending = {
                "nodes":  layer.get("nodes",  0),
                "edges":  layer.get("edges",  0),
                "weight": layer.get("mean_weight", 0.0),
                "acts":   acts,
                "log":    data.get("constitutional", {}).get("system_owner", ""),
            }
            QTimer.singleShot(0, self._apply)
        except Exception:
            pass

    def _apply(self):
        d = getattr(self, "_pending", None)
        if not d:
            return
        self._nodes_lbl.setText(f"Nodes:  {d['nodes']}")
        self._edges_lbl.setText(f"Edges:  {d['edges']}")
        self._energy_lbl.setText(f"Wt avg: {d['weight']:.3f}")
        self._acts_lbl.setText(f"Acts:   {d['acts']}")
        if d.get("log"):
            self._log.append(d["log"])

    def append_log(self, text: str):
        self._log.append(text)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())


# ── Main browser window ───────────────────────────────────────────────────────

class CursivBrowser(QMainWindow):
    """
    Cursiv Browser window.

    Wraps QWebEngineView with a custom dark chrome, intercepts curs.http://
    navigation, and shows a live substrate status rail on the right.
    """

    closed = pyqtSignal()

    def __init__(self, parent=None):
        if not _HAS_WEB_ENGINE:
            raise ImportError(
                "PyQt6-WebEngine is not installed.\n\n"
                "Run:  pip install PyQt6-WebEngine\nThen relaunch."
            )
        super().__init__(parent)
        self.setWindowTitle("Cursiv — Substrate Browser")
        self.resize(1280, 820)
        self.setStyleSheet(_BROWSER_QSS)
        self._history: list[str] = []
        self._hist_idx: int = -1
        self._build_ui()
        self._connect_shortcuts()
        self._navigate(_SUBSTRATE_HOST)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._make_nav_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self._view = QWebEngineView()
        self._page = _SubstratePage()
        self._view.setPage(self._page)
        splitter.addWidget(self._view)

        self._status_panel = _StatusPanel()
        splitter.addWidget(self._status_panel)
        splitter.setSizes([1060, 210])

        root_layout.addWidget(splitter, 1)

        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_bar = sb
        self._status_lbl = QLabel("Ready")
        sb.addPermanentWidget(self._status_lbl)

        self._view.urlChanged.connect(self._on_url_changed)
        self._view.loadStarted.connect(lambda: self._status_lbl.setText("Loading…"))
        self._view.loadFinished.connect(self._on_load_finished)

    def _make_nav_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet(f"background: {BG2}; border-bottom: 1px solid {BORDER};")
        h = QHBoxLayout(bar)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(4)

        self._btn_back    = QPushButton("◂")
        self._btn_fwd     = QPushButton("▸")
        self._btn_reload  = QPushButton("↺")
        self._btn_home    = QPushButton("⌂")
        self._btn_back.setToolTip("Back  (Alt+←)")
        self._btn_fwd.setToolTip("Forward  (Alt+→)")
        self._btn_reload.setToolTip("Reload  (F5)")
        self._btn_home.setToolTip("Home — substrate dashboard")

        for btn in (self._btn_back, self._btn_fwd, self._btn_reload, self._btn_home):
            btn.setFixedSize(QSize(32, 32))
            btn.setFont(QFont("Segoe UI", 13))
            h.addWidget(btn)

        h.addSpacing(4)

        self._addr_bar = QLineEdit()
        self._addr_bar.setPlaceholderText("curs.http://  —  type a Cursiv address")
        self._addr_bar.setFixedHeight(32)
        h.addWidget(self._addr_bar, 1)

        self._btn_go = QPushButton("Go")
        self._btn_go.setFixedSize(QSize(44, 32))
        h.addWidget(self._btn_go)

        h.addSpacing(4)

        # Substrate indicator LED
        self._led = QLabel("●")
        self._led.setToolTip("Substrate connection")
        self._led.setStyleSheet(f"color: {SILV2}; font-size: 14px;")
        h.addWidget(self._led)

        # Wire buttons
        self._btn_back.clicked.connect(self._go_back)
        self._btn_fwd.clicked.connect(self._go_forward)
        self._btn_reload.clicked.connect(lambda: self._view.reload())
        self._btn_home.clicked.connect(lambda: self._navigate(_SUBSTRATE_HOST))
        self._btn_go.clicked.connect(self._on_go)
        self._addr_bar.returnPressed.connect(self._on_go)

        self._update_nav_buttons()
        return bar

    def _connect_shortcuts(self):
        QShortcut(QKeySequence("F5"),             self, self._view.reload)
        QShortcut(QKeySequence("Ctrl+R"),         self, self._view.reload)
        QShortcut(QKeySequence("Alt+Left"),       self, self._go_back)
        QShortcut(QKeySequence("Alt+Right"),      self, self._go_forward)
        QShortcut(QKeySequence("Ctrl+L"),         self, self._focus_addr)
        QShortcut(QKeySequence("Escape"),         self, self._restore_addr)
        QShortcut(QKeySequence("Alt+Home"),       self, lambda: self._navigate(_SUBSTRATE_HOST))

    # ── Navigation helpers ────────────────────────────────────────────────────

    def _navigate(self, url: str):
        real = _translate_url(url.strip())
        if not real.startswith("http"):
            real = _SUBSTRATE_HOST + "/" + real.lstrip("/")
        self._view.load(QUrl(real))

    def _on_go(self):
        raw = self._addr_bar.text().strip()
        if not raw:
            return
        self._navigate(raw)

    def _on_url_changed(self, url: "QUrl"):
        real = url.toString()
        display = _display_url(real)
        self._addr_bar.setText(display)
        self._update_nav_buttons()
        # check substrate ping
        threading.Thread(target=self._check_substrate, daemon=True).start()

    def _on_load_finished(self, ok: bool):
        if ok:
            self._status_lbl.setText("Done")
            self._status_panel.append_log(
                f"→ {_display_url(self._view.url().toString())}"
            )
        else:
            self._status_lbl.setText("Load error")

    def _go_back(self):
        if self._view.history().canGoBack():
            self._view.back()
        self._update_nav_buttons()

    def _go_forward(self):
        if self._view.history().canGoForward():
            self._view.forward()
        self._update_nav_buttons()

    def _focus_addr(self):
        self._addr_bar.setFocus()
        self._addr_bar.selectAll()

    def _restore_addr(self):
        self._on_url_changed(self._view.url())
        self._view.setFocus()

    def _update_nav_buttons(self):
        if not hasattr(self, "_view"):
            self._btn_back.setEnabled(False)
            self._btn_fwd.setEnabled(False)
            return
        h = self._view.history()
        self._btn_back.setEnabled(h.canGoBack())
        self._btn_fwd.setEnabled(h.canGoForward())

    # ── Substrate ping ────────────────────────────────────────────────────────

    def _check_substrate(self):
        try:
            urllib.request.urlopen(f"{_SUBSTRATE_HOST}/health", timeout=2)
            QTimer.singleShot(0, lambda: self._set_led(True))
        except Exception:
            QTimer.singleShot(0, lambda: self._set_led(False))

    def _set_led(self, online: bool):
        color = GREEN if online else "#cc4444"
        tooltip = "Substrate online" if online else "Substrate offline — start the local server"
        self._led.setStyleSheet(f"color: {color}; font-size: 14px;")
        self._led.setToolTip(tooltip)

    # ── Close ─────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


# ── Singleton helper ──────────────────────────────────────────────────────────

_browser_instance: Optional["CursivBrowser"] = None


def open_browser(parent=None) -> "CursivBrowser":
    """Return the singleton CursivBrowser, creating it if needed."""
    global _browser_instance
    if not _HAS_WEB_ENGINE:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(
            parent,
            "Cursiv Browser",
            "PyQt6-WebEngine is not installed.\n"
            "Run:  pip install PyQt6-WebEngine\n"
            "Then restart the Cursiv Launcher.",
        )
        return None

    if _browser_instance is None or not _browser_instance.isVisible():
        _browser_instance = CursivBrowser(parent)
        _browser_instance.closed.connect(_on_browser_closed)

    _browser_instance.show()
    _browser_instance.raise_()
    _browser_instance.activateWindow()
    return _browser_instance


def _on_browser_closed():
    global _browser_instance
    _browser_instance = None


# ── Standalone entry point ────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Cursiv Browser")
    app.setStyleSheet(_BROWSER_QSS)
    browser = CursivBrowser()
    browser.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
