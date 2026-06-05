# cursiv_v215/nexus/epistemic_engine.py
# Epistemic Triangulation Engine for Cursiv v3.
# Fans out a query to multiple AI models, then synthesizes the responses.
#
# CONSTRAINTS:
#   - All output is ASCII-safe (no Unicode box-drawing or arrow chars).
#   - HTTP calls use urllib.request only.
#   - Parallel execution via concurrent.futures.ThreadPoolExecutor.
#   - API keys from cfg dict with env-var fallback.

import os
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from cursiv_v215.nexus.model_identities import (
    ALL_IDENTITIES,
    IDENTITY_CLAUDE,
    IDENTITY_GPT,
    IDENTITY_GROK,
    IDENTITY_OLLAMA,
)

# ---------------------------------------------------------------------------
# Low-level model callers
# ---------------------------------------------------------------------------

def _call_claude(prompt: str, system: str, cfg: dict) -> str:
    """Call Anthropic Claude via the official SDK. Returns response text or ''."""
    key = cfg.get("anthropic_key", "") or os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return ""
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=IDENTITY_CLAUDE["model"],
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as exc:
        return ""


def _call_gpt(prompt: str, system: str, cfg: dict) -> str:
    """Call OpenAI GPT via raw urllib POST. Returns response text or ''."""
    key = cfg.get("openai_key", "") or os.getenv("OPENAI_API_KEY", "")
    if not key:
        return ""
    try:
        payload = json.dumps({
            "model": IDENTITY_GPT["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 1024,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except Exception:
        return ""


def _call_grok(prompt: str, system: str, cfg: dict) -> str:
    """Call xAI Grok via raw urllib POST. Returns response text or ''."""
    key = cfg.get("api_key", "") or os.getenv("XAI_API_KEY", "")
    if not key:
        return ""
    try:
        payload = json.dumps({
            "model": IDENTITY_GROK["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 1024,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.x.ai/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except Exception:
        return ""


def _call_ollama(prompt: str, system: str, cfg: dict) -> str:
    """Call local Ollama instance via raw urllib POST. Returns response text or ''."""
    try:
        payload = json.dumps({
            "model": IDENTITY_OLLAMA["model"],
            "prompt": f"{system}\n\n{prompt}",
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return data.get("response", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Internal dispatch table
# ---------------------------------------------------------------------------

_CALLER_MAP = {
    "truth":      (_call_claude, IDENTITY_CLAUDE),
    "exploration": (_call_gpt,  IDENTITY_GPT),
    "hard_facts": (_call_grok,  IDENTITY_GROK),
    "sovereign":  (_call_ollama, IDENTITY_OLLAMA),
}


def _key_present(identity: dict, cfg: dict) -> bool:
    """Return True if the required API key is available for this identity."""
    provider = identity["provider"]
    if provider == "ollama":
        return True
    if provider == "anthropic":
        return bool(cfg.get("anthropic_key", "") or os.getenv("ANTHROPIC_API_KEY", ""))
    if provider == "openai":
        return bool(cfg.get("openai_key", "") or os.getenv("OPENAI_API_KEY", ""))
    if provider == "xai":
        return bool(cfg.get("api_key", "") or os.getenv("XAI_API_KEY", ""))
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def available_identities(cfg: dict) -> list:
    """
    Return list of identity dicts whose keys are present (or are Ollama).
    Ollama is always included; cloud models require a key.
    """
    return [ident for ident in ALL_IDENTITIES if _key_present(ident, cfg)]


def fan_out(query: str, cfg: dict) -> dict:
    """
    Query all available identities in parallel.

    Returns dict of {identity_name: response_text}.
    Failed or empty responses are excluded from the result.
    """
    identities = available_identities(cfg)

    def _worker(ident: dict) -> tuple:
        role = ident["role"]
        caller, _ = _CALLER_MAP[role]
        try:
            text = caller(query, ident["system_prompt"], cfg)
        except Exception:
            text = ""
        return ident["name"], text

    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_worker, ident): ident for ident in identities}
        for future in as_completed(futures):
            try:
                name, text = future.result()
                if text:
                    results[name] = text
            except Exception:
                pass

    return results


def synthesize(query: str, responses: dict, cfg: dict) -> str:
    """
    Send all model responses to Ollama for meta-analysis.
    Returns a structured synthesis string.
    """
    if not responses:
        return "[No responses available for synthesis]"

    # Build per-model section, mapping name -> lens label
    name_to_lens = {ident["name"]: ident["lens"] for ident in ALL_IDENTITIES}
    sections = []
    for model_name, text in responses.items():
        lens = name_to_lens.get(model_name, model_name)
        sections.append(f"=== {model_name} ({lens} Lens) ===\n{text}")

    model_block = "\n\n".join(sections)

    meta_prompt = (
        "You are analyzing responses from multiple AI models to the same question.\n"
        "Your job: find consensus, identify contested ground, note domain authority.\n\n"
        f"QUESTION: {query}\n\n"
        f"{model_block}\n\n"
        "Produce exactly this structure:\n"
        "CONSENSUS: [2-4 bullet points all models agree on]\n"
        "CONTESTED: [points where models diverge -- show each model's position briefly]\n"
        "DOMAIN AUTHORITY: [which model seems strongest for this specific question, one sentence why]\n"
        "SYNTHESIS: [your integrated answer in 3-5 sentences drawing on all responses]"
    )

    system = (
        "You are a neutral meta-analyst. Produce only the structured output requested. "
        "Be concise and factual."
    )

    result = _call_ollama(meta_prompt, system, cfg)
    if not result:
        return "[Ollama synthesis unavailable]"
    return result


def confidence_topology(responses: dict) -> str:
    """
    Estimate agreement level across model responses using word-overlap heuristic.
    Returns a short ASCII string like 'Strong consensus (4/4 models aligned)'.
    """
    if not responses:
        return "No responses to analyze."

    total = len(responses)
    if total == 1:
        return f"Single model response (1/{total}) -- no triangulation possible."

    # Tokenize each response into a set of lowercase words (4+ chars, alpha only)
    def _words(text: str) -> set:
        return {w.lower() for w in text.split() if w.isalpha() and len(w) >= 4}

    word_sets = [_words(t) for t in responses.values()]

    # Find words that appear in at least half the responses
    all_words = set()
    for ws in word_sets:
        all_words |= ws

    shared_count = sum(
        1 for w in all_words
        if sum(1 for ws in word_sets if w in ws) >= max(2, total // 2)
    )

    # Count how many model pairs share at least 5 common words
    aligned = 0
    from itertools import combinations
    for a, b in combinations(word_sets, 2):
        if len(a & b) >= 5:
            aligned += 1

    max_pairs = total * (total - 1) // 2
    ratio = aligned / max_pairs if max_pairs else 0

    if ratio >= 0.8:
        level = f"Strong consensus ({total}/{total} models aligned)"
    elif ratio >= 0.5:
        level = f"Moderate consensus ({aligned}/{max_pairs} pairs aligned)"
    elif ratio >= 0.25:
        level = f"Mixed views ({aligned}/{max_pairs} pairs agreed on core)"
    else:
        level = f"Divergent views ({aligned}/{max_pairs} pairs with overlap)"

    return level


def triangulate(query: str, cfg: dict) -> str:
    """
    Full epistemic triangulation pipeline.

    1. fan_out()  -- parallel queries to all available models
    2. synthesize() -- Ollama meta-analysis
    3. Format and return ASCII output

    If only Ollama is available, runs all 4 lens system prompts sequentially
    through Ollama and notes this in the output.
    """
    identities_avail = available_identities(cfg)
    avail_names = {i["name"] for i in identities_avail}
    cloud_avail = [i for i in identities_avail if i["provider"] != "ollama"]

    lines = []
    sep_wide  = "=" * 40
    sep_thin  = "-" * 40

    lines.append(sep_wide)
    lines.append("EPISTEMIC TRIANGULATION")
    lines.append(sep_wide)
    lines.append(f"Query: {query}")

    # ---- Offline-only fallback ------------------------------------------------
    if not cloud_avail:
        lines.append("Models used: Ollama (sovereign-only mode -- no cloud keys found)")
        lines.append("Note: Running all 4 lens prompts through Ollama sequentially.")
        lines.append("")
        responses = {}
        for ident in ALL_IDENTITIES:
            role_label = f"{ident['name']} ({ident['lens']} Lens)"
            lines.append(f"--- {role_label} ---")
            text = _call_ollama(query, ident["system_prompt"], cfg)
            if text:
                responses[ident["name"]] = text
                lines.append(text)
            else:
                lines.append("[Ollama did not return a response for this lens]")
            lines.append("")
    else:
        # ---- Normal multi-model fan-out ----------------------------------------
        responses = fan_out(query, cfg)
        used_names = ", ".join(responses.keys()) if responses else "none"
        lines.append(f"Models used: {used_names}")
        lines.append("")

        name_to_lens = {ident["name"]: ident["lens"] for ident in ALL_IDENTITIES}
        for model_name, text in responses.items():
            lens = name_to_lens.get(model_name, model_name)
            lines.append(f"--- {model_name} ({lens} Lens) ---")
            lines.append(text)
            lines.append("")

    # ---- Confidence topology --------------------------------------------------
    topology = confidence_topology(responses)
    lines.append(f"Agreement: {topology}")
    lines.append("")

    # ---- Synthesis -----------------------------------------------------------
    lines.append(sep_thin)
    lines.append("SYNTHESIS (via Sovereign Lens)")
    lines.append(sep_thin)
    synthesis_text = synthesize(query, responses, cfg)
    lines.append(synthesis_text)
    lines.append(sep_wide)

    return "\n".join(lines)
