"""
Cursiv v3 Plugin Registry
Formal manifest of every active plugin/agent.  No external dependencies.
"""

import os
from dataclasses import dataclass, field


# ── Manifest dataclass ─────────────────────────────────────────────────────

@dataclass
class PluginManifest:
    name: str
    version: str
    category: str       # "core" | "agent" | "lens" | "council" | "runtime"
    status: str         # "active" | "requires_key" | "optional"
    commands: list
    description: str
    requires: list = field(default_factory=list)  # plugin-level dependencies


# ── Plugin catalogue ───────────────────────────────────────────────────────

ALL_PLUGINS: list = [

    # ── Core ──────────────────────────────────────────────────────────────
    PluginManifest(
        name="CursivConstitution",
        version="1.0",
        category="core",
        status="active",
        commands=[],
        description="Constitutional sovereignty layer, identity drift protection",
    ),
    PluginManifest(
        name="EvoCore",
        version="2.0",
        category="core",
        status="active",
        commands=[],
        description="Self-improvement engine, proactive routing, intent classification",
    ),
    PluginManifest(
        name="OllamaEngine",
        version="1.0",
        category="core",
        status="active",
        commands=[],
        description="Local AI (llama3.1) -- offline-first, always available",
    ),

    # ── Agents ────────────────────────────────────────────────────────────
    PluginManifest(
        name="BibleStudy",
        version="1.0",
        category="agent",
        status="active",
        commands=["bible", "discuss", "study"],
        description="31,102 verses, 6 translations, philosophical synthesis",
    ),
    PluginManifest(
        name="CivilizationMaster",
        version="1.0",
        category="agent",
        status="active",
        commands=["civilization", "scripture", "philosophy"],
        description="26 philosophers, 7 Bible versions + binary synthesis",
    ),
    PluginManifest(
        name="BabelAgent",
        version="1.0",
        category="agent",
        status="active",
        commands=["babel"],
        description="Universal language translation",
    ),
    PluginManifest(
        name="CodexAgent",
        version="1.0",
        category="agent",
        status="active",
        commands=["codex", "code", "fix"],
        description="Coding assistant (qwen2.5-coder)",
    ),
    PluginManifest(
        name="SearchAgent",
        version="1.0",
        category="agent",
        status="active",
        commands=["search"],
        description="Live web search",
    ),

    # ── Epistemic lenses ──────────────────────────────────────────────────
    PluginManifest(
        name="TruthLens",
        version="1.0",
        category="lens",
        status="requires_key",
        commands=["truth", "lens claude"],
        description="Claude / Anthropic epistemic lens",
    ),
    PluginManifest(
        name="ExplorationLens",
        version="1.0",
        category="lens",
        status="requires_key",
        commands=["explore", "lens gpt"],
        description="GPT-4o / OpenAI exploration lens",
    ),
    PluginManifest(
        name="HardFactsLens",
        version="1.0",
        category="lens",
        status="requires_key",
        commands=["facts", "lens grok"],
        description="Grok / xAI hard-facts lens",
    ),
    PluginManifest(
        name="EpistemicEngine",
        version="1.0",
        category="lens",
        status="optional",
        commands=["deep", "triangulate"],
        description="Triangulation across all lenses (works with any keys present)",
        requires=["TruthLens", "ExplorationLens", "HardFactsLens"],
    ),
    PluginManifest(
        name="ForgeEngine",
        version="1.0",
        category="lens",
        status="optional",
        commands=["forge"],
        description="Sequential refinement pipeline",
    ),

    # ── Council ───────────────────────────────────────────────────────────
    PluginManifest(
        name="CouncilCore",
        version="1.0",
        category="council",
        status="active",
        commands=["council", "/deliberate", "/full"],
        description="14-agent async deliberation",
    ),
    PluginManifest(
        name="KnowledgeGraph",
        version="1.0",
        category="council",
        status="active",
        commands=["graph status", "graph query"],
        description="Persistent concept graph built from council deliberations",
    ),

    # ── Runtime ───────────────────────────────────────────────────────────
    PluginManifest(
        name="SetupCheck",
        version="1.0",
        category="runtime",
        status="active",
        commands=[],
        description="Ollama health check at startup (automatic)",
    ),
    PluginManifest(
        name="MemoryEngine",
        version="1.0",
        category="runtime",
        status="active",
        commands=["anchor this", "recall"],
        description="Conversation anchoring and recall",
    ),
]


# ── Key-to-plugin mapping for live status resolution ──────────────────────

_LENS_KEY_MAP = {
    "TruthLens":       lambda cfg: cfg.get("anthropic_key") or os.getenv("ANTHROPIC_API_KEY", ""),
    "ExplorationLens": lambda cfg: cfg.get("openai_key")    or os.getenv("OPENAI_API_KEY",    ""),
    "HardFactsLens":   lambda cfg: cfg.get("api_key")       or os.getenv("XAI_API_KEY",       ""),
}


# ── Public helpers ─────────────────────────────────────────────────────────

def get_by_category(category: str) -> list:
    """Return all plugins whose category matches."""
    return [p for p in ALL_PLUGINS if p.category == category]


def get_commands() -> dict:
    """
    Flat mapping of command -> plugin name for every active plugin.
    Multi-word commands (e.g. 'graph status') are included as-is.
    """
    result = {}
    for plugin in ALL_PLUGINS:
        if plugin.status == "active":
            for cmd in plugin.commands:
                result[cmd] = plugin.name
    return result


def _effective_status(plugin: "PluginManifest", cfg: dict) -> str:
    """
    Resolve a lens plugin's runtime status given live config.
    Returns "active", "requires_key", or "optional".
    """
    if plugin.name in _LENS_KEY_MAP:
        key_fn = _LENS_KEY_MAP[plugin.name]
        if key_fn(cfg):
            return "active"
        return plugin.status
    return plugin.status


def show_status(cfg: dict = None) -> str:
    """
    Return the full ASCII plugin-status display.
    If cfg is provided, lens plugins are marked [active] when their API key is present.
    """
    if cfg is None:
        cfg = {}

    _STATUS_LABEL = {
        "active":       "[active]  ",
        "requires_key": "[key req] ",
        "optional":     "[optional]",
    }

    lines = []
    lines.append("=======================================================")
    lines.append("  CURSIV v3.14-U10 -- PLUGIN STATUS")
    lines.append("=======================================================")

    category_order = [
        ("core",    "[CORE]"),
        ("agent",   "[AGENTS]"),
        ("lens",    "[EPISTEMIC LENSES]"),
        ("council", "[COUNCIL]"),
        ("runtime", "[RUNTIME]"),
    ]

    for cat_key, cat_label in category_order:
        plugins = get_by_category(cat_key)
        if not plugins:
            continue
        lines.append("")
        lines.append(cat_label)

        for p in plugins:
            eff_status = _effective_status(p, cfg)
            badge = _STATUS_LABEL.get(eff_status, "[unknown]  ")
            name_ver = f"{p.name} v{p.version}"

            # Build right-side info: commands for non-core/runtime, description for core/runtime
            if p.commands:
                info = ", ".join(p.commands)
            else:
                info = p.description

            # Fixed-width name column (28 chars)
            col_name = f"  {name_ver:<28}"
            lines.append(f"{col_name}{badge}  {info}")

    lines.append("")
    lines.append("=======================================================")
    lines.append("Type 'help' for full command list.")
    lines.append("=======================================================")

    return "\n".join(lines)
