"""
intent_engine.py  --  EvoCore v2.0 query-intent classifier
=============================================================
Runs BEFORE the main chat loop to classify incoming queries and
suggest optimal routing.  Pure stdlib, no network, <10ms target.

Usage
-----
    from cursiv_v215.runtime.intent_engine import classify, suggest_route, proactive_hint, intent_summary
"""

from __future__ import annotations

import math
import re
from typing import Optional

# ---------------------------------------------------------------------------
# Intent label constants
# ---------------------------------------------------------------------------

INTENT_BIBLE      = "bible"
INTENT_PHILOSOPHY = "philosophy"
INTENT_CODE       = "code"
INTENT_SEARCH     = "search"
INTENT_COUNCIL    = "council"
INTENT_DEEP       = "deep"
INTENT_FORGE      = "forge"
INTENT_TRANSLATE  = "translate"
INTENT_MEMORY     = "memory"
INTENT_SYSTEM     = "system"
INTENT_CASUAL     = "casual"

# ---------------------------------------------------------------------------
# Heuristic signal tables
# Single data-structure design: each row is
#   (intent_label, keyword_list, regex_patterns, kw_weight, re_weight)
# Scores accumulate; highest score wins.
# ---------------------------------------------------------------------------

_BIBLE_BOOKS: list[str] = [
    "genesis", "exodus", "leviticus", "numbers", "deuteronomy",
    "joshua", "judges", "ruth", "samuel", "kings", "chronicles",
    "ezra", "nehemiah", "esther", "job", "psalm", "psalms",
    "proverbs", "ecclesiastes", "isaiah", "jeremiah", "lamentations",
    "ezekiel", "daniel", "hosea", "joel", "amos", "obadiah",
    "jonah", "micah", "nahum", "habakkuk", "zephaniah", "haggai",
    "zechariah", "malachi",
    "matthew", "mark", "luke", "john", "acts", "romans",
    "corinthians", "galatians", "ephesians", "philippians",
    "colossians", "thessalonians", "timothy", "titus", "philemon",
    "hebrews", "james", "peter", "jude", "revelation",
]

_PHILOSOPHERS: list[str] = [
    "socrates", "plato", "aristotle", "epicurus", "marcus aurelius",
    "seneca", "epictetus", "descartes", "kant", "hegel", "nietzsche",
    "schopenhauer", "wittgenstein", "heidegger", "sartre", "camus",
    "foucault", "derrida", "spinoza", "leibniz", "locke", "hume",
    "rousseau", "voltaire", "kierkegaard", "confucius", "lao tzu",
    "laozi", "zhuangzi", "nagarjuna", "rumi", "ibn rushd", "averroes",
    "ibn sina", "avicenna", "maimonides", "aquinas", "augustine",
    "pascal", "mill", "bentham", "rawls", "nozick",
]

# Dynamic patterns that require list-joining — built once at import time.
_RE_BIBLE_DISCUSS: str = (
    r"\bdiscuss\s+(?:" + "|".join(_BIBLE_BOOKS) + r")\b"
)
_RE_PHIL_WHAT_DID: str = (
    r"\bwhat did (?:"
    + "|".join(re.escape(p) for p in _PHILOSOPHERS)
    + r") (?:say|believe|teach|mean)\b"
)

# Each row: (label, keyword_list, regex_pattern_list, kw_weight, re_weight)
_SIGNAL_TABLE: list[tuple[str, list[str], list[str], float, float]] = [

    (INTENT_BIBLE, [
        "scripture", "verse", "verses", "kjv", "niv", "esv",
        "bible", "biblical", "gospel", "testament", "covenant",
        "prophecy", "christ", "sermon",
    ] + _BIBLE_BOOKS, [
        # verse reference: word(s) + chapter:verse, e.g. "John 3:16"
        r"\b[A-Za-z]+\s+\d+:\d+\b",
        _RE_BIBLE_DISCUSS,
    ], 0.25, 0.45),

    (INTENT_PHILOSOPHY, [
        "philosophy", "philosophical", "wisdom", "tradition", "stoic",
        "stoicism", "buddhist", "buddhism", "zen", "taoism", "taoist",
        "existentialism", "existential", "metaphysics", "epistemology",
        "ethics", "virtue", "dialectic", "ontology",
    ] + _PHILOSOPHERS, [
        _RE_PHIL_WHAT_DID,
        r"\baccording to \w+\s*(?:philosophy|tradition|teaching)\b",
    ], 0.22, 0.40),

    (INTENT_CODE, [
        "code", "function", "debug", "error", "import", "module",
        "traceback", "exception", "syntax", "compile", "run",
        "script", "class", "variable", "loop", "api", "endpoint",
        "database", "sql", "git", "terminal", "bash", "python",
        "javascript", "typescript", "react", "html", "css", "json",
        "yaml", "dockerfile", "kubernetes", "lambda", "recursion",
        "algorithm", "dataframe", "pandas", "numpy", "flask", "django",
    ], [
        r"\.[a-z]{2,4}\b",
        r"\bwrite a (?:script|function|class|program|module|test)\b",
        r"\bbuild a \w+",
        r"\bfix (?:the|this|my)?\s*(?:bug|error|code|function)\b",
        r"```",
        r"\bdef \w+\(",
        r"\bimport \w+",
    ], 0.20, 0.42),

    (INTENT_SEARCH, [
        "latest", "news", "today", "current", "right now",
        "happening", "recently", "update", "breaking", "report",
        "forecast", "live", "real-time",
        "2024", "2025", "2026",
    ], [
        r"\bwhat is happening\b",
        r"\bwhat(?:'s| is) (?:the )?(?:latest|current|recent)\b",
        r"\bright now\b",
        r"\btoday(?:'s)?\s+\w+",
    ], 0.22, 0.40),

    (INTENT_COUNCIL, [
        "council", "deliberate", "perspective", "angles", "viewpoints",
        "weigh", "pros and cons", "advice", "recommend",
    ], [
        r"\bshould i\b",
        r"\bwhat would you do\b",
        r"\bbig decision\b",
        r"\bmultiple angles\b",
        r"\bhelp me decide\b",
        r"\bwhat(?:'s| is) (?:your|the) (?:take|opinion|view) on\b",
    ], 0.22, 0.42),

    (INTENT_DEEP, [], [
        r"^deep\s+",
        r"^triangulate\s+",
    ], 0.0, 0.90),

    (INTENT_FORGE, [], [
        r"^forge\s+",
    ], 0.0, 0.95),

    (INTENT_TRANSLATE, [
        "translate", "babel", "translation",
    ], [
        r"\bin (?:spanish|french|german|japanese|chinese|arabic|portuguese|"
        r"italian|russian|korean|hindi|dutch|polish|swedish|turkish)\b",
        r"\bwhat does .{1,40} mean\b",
        r"\bhow (?:do you |to )?say .{1,30} in \w+\b",
    ], 0.30, 0.50),

    (INTENT_MEMORY, [
        "remember", "anchor", "recall", "memorize", "note",
        "save this", "log this",
    ], [
        r"\bsave (?:this|that)\b",
        r"\bremember (?:this|that|when)\b",
        r"\bwhat did we (?:talk|discuss|say)\b",
        r"\brecall\b",
        r"\banchored?\b",
    ], 0.28, 0.45),

    (INTENT_SYSTEM, [
        "help", "version", "status", "config", "settings",
        "commands", "changelog",
    ], [
        r"\bwhat can you\b",
        r"\bshow (?:me )?(?:help|commands|status|version)\b",
        r"\bhow (?:do i|to) use\b",
        r"\b(?:cursiv|evocore) status\b",
    ], 0.28, 0.45),
]

# Command prefixes that indicate the user already knows the route.
# suggest_route stays silent when the query starts with one of these.
_COMMAND_PREFIXES: tuple[str, ...] = (
    "bible ", "forge ", "deep ", "search ", "council ", "babel ",
    "translate ", "memory ", "status", "help", "substrate",
)

# Thresholds
_SUGGEST_THRESHOLD: float = 0.65   # minimum confidence to emit a suggestion
_HINT_MIN: float = 0.40            # hint band floor (below suggests = ambiguous)
_HINT_MAX: float = 0.75            # hint band ceiling (above = already clear)
_CASUAL_THRESHOLD: float = 0.30    # below this, fall back to casual


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip leading/trailing space."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _score_intent(
    norm_query: str,
    keywords: list[str],
    patterns: list[str],
    kw_weight: float,
    re_weight: float,
) -> float:
    """
    Accumulate a raw score for one intent row.
    Each matched keyword adds kw_weight; each matched pattern adds re_weight
    (capped at one match per distinct pattern).
    """
    score = 0.0
    for kw in keywords:
        if kw in norm_query:
            score += kw_weight
    for pat in patterns:
        try:
            if re.search(pat, norm_query, re.IGNORECASE):
                score += re_weight
        except re.error:
            pass
    return score


def _raw_scores(query: str) -> list[tuple[str, float]]:
    """Return list of (label, raw_score) for every intent in _SIGNAL_TABLE."""
    norm = _normalise(query)
    return [
        (label, _score_intent(norm, kws, pats, kw_w, re_w))
        for label, kws, pats, kw_w, re_w in _SIGNAL_TABLE
    ]


def _normalise_confidence(raw: float) -> float:
    """
    Map a raw accumulated score to [0.0, 1.0] using tanh so that a single
    strong pattern hit (~0.45 raw) yields ~0.45 confidence and two hits
    (~0.90 raw) yield ~0.72 confidence, saturating gracefully toward 1.0.
    """
    if raw <= 0.0:
        return 0.0
    return round(min(1.0, math.tanh(raw * 1.1)), 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(query: str) -> tuple[str, float]:
    """
    Classify *query* into an intent label with a confidence score.

    Returns
    -------
    (intent_label, confidence)
        confidence is in [0.0, 1.0].
        Falls back to (INTENT_CASUAL, 0.0) when no signal clears the threshold.
    """
    if not query or not query.strip():
        return (INTENT_CASUAL, 0.0)

    scores = _raw_scores(query)
    best_label, best_raw = max(scores, key=lambda t: t[1])
    confidence = _normalise_confidence(best_raw)

    if confidence < _CASUAL_THRESHOLD:
        return (INTENT_CASUAL, 0.0)

    return (best_label, confidence)


def suggest_route(query: str) -> Optional[str]:
    """
    If the intent is clear (confidence >= _SUGGEST_THRESHOLD) and the query
    is not already using a known command prefix, return a suggested command
    string.  Returns None otherwise.
    """
    norm = _normalise(query)
    for prefix in _COMMAND_PREFIXES:
        if norm.startswith(prefix):
            return None  # already routed — stay silent

    label, confidence = classify(query)
    if confidence < _SUGGEST_THRESHOLD or label == INTENT_CASUAL:
        return None

    q = query.strip()
    norm_q = _normalise(q)

    if label == INTENT_BIBLE:
        verse_match = re.search(r"([A-Za-z]+\s+\d+:\d+)", q)
        if verse_match:
            return "bible " + verse_match.group(1)
        return "bible " + q

    if label == INTENT_TRANSLATE:
        lang_match = re.search(
            r"\bin (spanish|french|german|japanese|chinese|arabic|"
            r"portuguese|italian|russian|korean|hindi|dutch|polish|"
            r"swedish|turkish)\b",
            norm_q,
        )
        if lang_match:
            parts = re.split(r"\bin " + lang_match.group(1), norm_q, maxsplit=1)
            payload = parts[0].strip()
            payload = re.sub(
                r"^(?:can you |please )?(?:translate|say)\s*", "", payload
            ).strip()
            return "babel " + (payload or q)
        return "babel " + q

    if label == INTENT_SEARCH:
        stripped = re.sub(
            r"^what(?:'s| is) (?:the )?(?:latest|current|happening|news)"
            r"(?:\s+about)?\s*",
            "",
            norm_q,
        ).strip()
        return "search " + (stripped or q)

    if label == INTENT_COUNCIL:
        stripped = re.sub(
            r"^(?:what would you do(?: if)?|can you help me decide|help me decide)\s*",
            "",
            norm_q,
        ).strip()
        return "council " + (stripped or q)

    if label == INTENT_DEEP:
        stripped = re.sub(r"^(?:deep|triangulate)\s+", "", norm_q).strip()
        return "deep " + (stripped or q)

    if label == INTENT_FORGE:
        stripped = re.sub(r"^forge\s+", "", norm_q).strip()
        return "forge " + (stripped or q)

    if label == INTENT_SYSTEM:
        return "status"

    # CODE, MEMORY, PHILOSOPHY: no single prefix command; let them flow inline
    return None


def proactive_hint(query: str) -> Optional[str]:
    """
    Return a one-line [EvoCore] hint when routing could genuinely improve
    the response.  Only fires within the ambiguous-confidence band
    [_HINT_MIN, _HINT_MAX] to avoid spamming on clear hits or irrelevant
    queries.  Returns None when silent is better.
    """
    label, confidence = classify(query)

    if label == INTENT_CASUAL or confidence == 0.0:
        return None

    norm_q = _normalise(query)
    for prefix in _COMMAND_PREFIXES:
        if norm_q.startswith(prefix):
            return None  # already prefixed

    if not (_HINT_MIN <= confidence <= _HINT_MAX):
        return None

    q = query.strip()

    _HINTS: dict[str, str] = {
        INTENT_BIBLE:
            "[EvoCore] Tip: try 'bible " + q + "' to route directly to the scripture reader",
        INTENT_PHILOSOPHY:
            "[EvoCore] Tip: try 'deep " + q + "' for multi-model philosophical perspectives",
        INTENT_CODE:
            "[EvoCore] Tip: try 'forge " + q + "' for a full step-by-step code-build pipeline",
        INTENT_SEARCH:
            "[EvoCore] Tip: try 'search " + q + "' to trigger a live web lookup for current data",
        INTENT_COUNCIL:
            "[EvoCore] Tip: try 'council " + q + "' to activate multi-voice deliberation",
        INTENT_DEEP:
            "[EvoCore] Tip: try 'deep " + q + "' to get Claude + GPT + Grok perspectives",
        INTENT_TRANSLATE:
            "[EvoCore] Tip: try 'babel " + q + "' to route through the translation engine",
        INTENT_MEMORY:
            "[EvoCore] Tip: use 'anchor: " + q + "' to persist this to substrate memory",
        INTENT_SYSTEM:
            "[EvoCore] Tip: type 'status' or 'help' to see full system info",
    }

    return _HINTS.get(label)


def intent_summary(query: str) -> str:
    """
    Return a short debug/status line.

    Example output::

        Intent: bible (0.87) -- suggested: bible John 3:16
    """
    label, confidence = classify(query)
    suggestion = suggest_route(query)
    conf_str = "{:.2f}".format(confidence)
    if suggestion:
        return "Intent: {} ({}) -- suggested: {}".format(label, conf_str, suggestion)
    return "Intent: {} ({})".format(label, conf_str)


# ---------------------------------------------------------------------------
# Convenience wrapper: all four functions in one call
# ---------------------------------------------------------------------------

class IntentResult:
    """
    Lightweight result object bundling classify + suggest_route + proactive_hint.
    Avoids any external dataclass/attrs dependency.
    """

    __slots__ = ("label", "confidence", "suggestion", "hint")

    def __init__(self, query: str) -> None:
        self.label, self.confidence = classify(query)
        self.suggestion: Optional[str] = suggest_route(query)
        self.hint: Optional[str] = proactive_hint(query)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            "IntentResult(label={!r}, confidence={:.2f}, suggestion={!r})".format(
                self.label, self.confidence, self.suggestion
            )
        )


def analyse(query: str) -> IntentResult:
    """Run classify, suggest_route, and proactive_hint in one call."""
    return IntentResult(query)
