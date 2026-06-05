# cursiv_v215/nexus/forge.py
# Sequential Forge Pipeline for Cursiv v3.
# Four passes: Draft -> Expand -> Sharpen -> Ground.
# Each pass builds on the output of the previous.
#
# CONSTRAINTS:
#   - All output is ASCII-safe (no Unicode box-drawing or arrow chars).
#   - HTTP calls via epistemic_engine helpers (urllib.request only).
#   - Ollama always runs; cloud models require a key.

import os

from cursiv_v215.nexus.epistemic_engine import (
    _call_claude,
    _call_gpt,
    _call_grok,
    _call_ollama,
    _key_present,
)
from cursiv_v215.nexus.model_identities import (
    IDENTITY_CLAUDE,
    IDENTITY_GPT,
    IDENTITY_GROK,
    IDENTITY_OLLAMA,
)

_SEP_WIDE = "=" * 40
_SEP_THIN = "-" * 40
_SKIP_CLAUDE  = "[Claude not available -- skipped]"
_SKIP_GPT     = "[GPT not available -- skipped]"
_SKIP_GROK    = "[Grok not available -- skipped]"


def forge_pipeline(query: str, cfg: dict) -> str:
    """
    Run the four-pass forge pipeline on a query.

    Pass 1 (DRAFT)   -- Claude (Truth Lens):      accurate, nuanced draft
    Pass 2 (EXPAND)  -- GPT (Exploration Lens):   broaden and deepen
    Pass 3 (SHARPEN) -- Grok (Hard Facts Lens):   strip hedging, add hard facts
    Pass 4 (GROUND)  -- Ollama (Sovereign Lens):  make practical and actionable

    If a cloud model is unavailable its pass is skipped and noted. Ollama always runs.
    Returns a formatted ASCII string.
    """
    lines = []
    lines.append(_SEP_WIDE)
    lines.append("FORGE PIPELINE")
    lines.append(_SEP_WIDE)
    lines.append(f"Query: {query}")
    lines.append("")

    # ------------------------------------------------------------------
    # Pass 1 -- DRAFT (Claude / Truth Lens)
    # ------------------------------------------------------------------
    pass1_system = (
        "You are drafting the best possible answer to this question. "
        "Focus on accuracy and nuance. Acknowledge what you're uncertain about."
    )

    if _key_present(IDENTITY_CLAUDE, cfg):
        pass1 = _call_claude(query, pass1_system, cfg)
        if not pass1:
            pass1 = _SKIP_CLAUDE
    else:
        pass1 = _SKIP_CLAUDE

    lines.append("--- PASS 1: DRAFT (Claude / Truth Lens) ---")
    lines.append(pass1)
    lines.append("")

    # ------------------------------------------------------------------
    # Pass 2 -- EXPAND (GPT / Exploration Lens)
    # ------------------------------------------------------------------
    # If Pass 1 was skipped we still give GPT the original query as context.
    draft_context = pass1 if pass1 != _SKIP_CLAUDE else f"[Original question: {query}]"

    pass2_system = (
        "You are expanding and deepening a draft answer. The draft is below. "
        "Add creative connections, broader perspectives, and anything important "
        "that's missing. Don't repeat -- add.\n\n"
        f"DRAFT:\n{draft_context}"
    )

    if _key_present(IDENTITY_GPT, cfg):
        pass2 = _call_gpt(query, pass2_system, cfg)
        if not pass2:
            pass2 = _SKIP_GPT
    else:
        pass2 = _SKIP_GPT

    lines.append("--- PASS 2: EXPAND (GPT / Exploration Lens) ---")
    lines.append(pass2)
    lines.append("")

    # ------------------------------------------------------------------
    # Pass 3 -- SHARPEN (Grok / Hard Facts Lens)
    # ------------------------------------------------------------------
    # Walk back through passes to find the most complete text so far.
    current_best = next(
        (t for t in [pass2, pass1] if t not in (_SKIP_GPT, _SKIP_CLAUDE)),
        f"[Original question: {query}]",
    )

    pass3_system = (
        "You are sharpening a response to its hardest, most verifiable core. "
        "Remove hedging. State facts directly. Add any missing hard facts. "
        "Cut what can't be verified.\n\n"
        f"CURRENT:\n{current_best}"
    )

    if _key_present(IDENTITY_GROK, cfg):
        pass3 = _call_grok(query, pass3_system, cfg)
        if not pass3:
            pass3 = _SKIP_GROK
    else:
        pass3 = _SKIP_GROK

    lines.append("--- PASS 3: SHARPEN (Grok / Hard Facts Lens) ---")
    lines.append(pass3)
    lines.append("")

    # ------------------------------------------------------------------
    # Pass 4 -- GROUND (Ollama / Sovereign Lens)
    # ------------------------------------------------------------------
    refined = next(
        (t for t in [pass3, pass2, pass1] if t not in (_SKIP_GROK, _SKIP_GPT, _SKIP_CLAUDE)),
        f"[Original question: {query}]",
    )

    pass4_system = (
        "You are grounding a refined answer in practical reality. "
        "Make it actionable and honest. What can the person actually do with this? "
        "What is still genuinely uncertain?\n\n"
        f"REFINED:\n{refined}"
    )

    pass4 = _call_ollama(query, pass4_system, cfg)
    if not pass4:
        pass4 = "[Ollama did not return a response -- check that Ollama is running on localhost:11434]"

    lines.append("--- PASS 4: GROUND (Ollama / Sovereign Lens) ---")
    lines.append(pass4)
    lines.append("")

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    lines.append(_SEP_WIDE)
    lines.append("FORGE COMPLETE")
    lines.append(_SEP_WIDE)
    lines.append("Final answer is Pass 4 above.")

    return "\n".join(lines)
