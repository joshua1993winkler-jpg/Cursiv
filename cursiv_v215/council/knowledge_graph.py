"""
cursiv_v215/council/knowledge_graph.py

Persistent concept graph for the PiForge Council.  Grows with every
deliberation, building a web of connected ideas, recurring themes and
prior wisdom the council can reference in future sessions.

Storage: ~/.cursiv/council_graph.json
Thread-safety: write-to-temp-then-rename pattern.
Dependencies: pure Python stdlib only (json, pathlib, datetime, re, collections).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Stop-word list (English, minimal, all lower-case)
# ---------------------------------------------------------------------------
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "not",
    "it", "its", "this", "that", "these", "those", "i", "we", "you",
    "he", "she", "they", "me", "us", "him", "her", "them", "my", "our",
    "your", "his", "their", "what", "how", "why", "when", "where", "who",
    "which", "as", "so", "no", "yes", "up", "out", "about", "into",
    "than", "then", "there", "here", "all", "each", "any", "some", "one",
    "two", "also", "just", "more", "very", "much", "such", "now", "new",
    "even", "both", "well", "only", "most", "over", "after", "through",
    "while", "between", "among", "see", "say", "said", "use", "used",
    "get", "got", "make", "made", "go", "going", "come", "came", "take",
    "took", "give", "given", "know", "known", "think", "thought", "part",
    "way", "time", "life", "people", "world", "man", "men", "woman",
    "women", "thing", "things", "other", "another", "first", "last",
    "long", "great", "little", "own", "right", "old", "big", "high",
    "different", "small", "large", "good", "same", "next", "early",
    "young", "important", "public", "private", "real", "best", "free",
    "true", "false", "every", "many", "within", "without", "during",
    "before", "above", "below", "between", "against", "under", "around",
    "throughout", "across", "behind", "along", "following", "since",
    "based", "case", "point", "fact", "area", "however", "therefore",
    "thus", "hence", "further", "already", "often", "never", "always",
})

# Well-known named entities that should always be captured as concepts.
_NAMED_ENTITIES: frozenset[str] = frozenset({
    # Philosophers
    "aristotle", "plato", "socrates", "kant", "hegel", "nietzsche",
    "descartes", "locke", "hume", "spinoza", "leibniz", "wittgenstein",
    "kierkegaard", "sartre", "camus", "heidegger", "foucault", "derrida",
    "aquinas", "augustine", "boethius", "plotinus",
    # Theologians / biblical figures
    "moses", "paul", "peter", "john", "isaiah", "jeremiah", "ezekiel",
    "genesis", "exodus", "psalms", "proverbs", "ecclesiastes", "romans",
    "corinthians", "galatians", "ephesians", "revelation",
    # Technology terms
    "python", "javascript", "typescript", "rust", "golang", "kubernetes",
    "docker", "llm", "transformer", "neural", "gpu", "cpu", "api",
    "ollama", "pytorch", "tensorflow", "sqlite", "postgres", "redis",
    # Key Cursiv concepts
    "piforge", "cursiv", "substrate", "ruw", "council", "synthesis",
    "deliberation", "sovereignty", "inference", "attractor", "vector",
    "embedding", "consciousness", "identity", "wisdom", "eternity",
    "covenant", "grace", "truth", "faith", "reason", "logos", "pneuma",
})

# Category keyword maps (lower-case)
_CATEGORY_SIGNALS: dict[str, list[str]] = {
    "philosophy": [
        "philosophy", "ethics", "epistemology", "ontology", "metaphysics",
        "logic", "dialectic", "virtue", "consciousness", "identity",
        "freedom", "existence", "being", "phenomenology", "aesthetics",
        "truth", "reason", "logos", "wisdom", "soul", "mind",
    ],
    "theology": [
        "theology", "god", "bible", "scripture", "faith", "grace", "sin",
        "salvation", "church", "prayer", "covenant", "spirit", "divine",
        "sacred", "holy", "eternal", "heaven", "gospel", "exodus",
        "genesis", "psalms", "revelation", "christ", "lord", "jesus",
        "torah", "islam", "quran", "buddhism", "dharma",
    ],
    "science": [
        "science", "physics", "chemistry", "biology", "mathematics",
        "quantum", "relativity", "evolution", "neuroscience", "cosmology",
        "algorithm", "neural", "computation", "thermodynamics", "entropy",
        "genome", "protein", "atom", "particle", "energy", "wave",
    ],
    "code": [
        "python", "javascript", "code", "function", "class", "api",
        "database", "server", "client", "async", "thread", "process",
        "memory", "runtime", "compiler", "llm", "transformer", "model",
        "inference", "embedding", "vector", "token", "prompt", "gpu",
        "docker", "kubernetes", "ollama", "pytorch", "tensorflow",
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _categorize(word: str) -> str:
    low = word.lower()
    for cat, signals in _CATEGORY_SIGNALS.items():
        if low in signals:
            return cat
    return "general"


def _edge_key(a: str, b: str) -> str:
    """Canonical (sorted) edge key so A|||B == B|||A."""
    pair = sorted([a, b])
    return f"{pair[0]}|||{pair[1]}"


# ---------------------------------------------------------------------------
# Concept extraction
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lower-case word tokens, letters and hyphens only."""
    return re.findall(r"[a-zA-Z][a-zA-Z\-]*[a-zA-Z]|[a-zA-Z]", text.lower())


def _extract_concepts(text: str, max_concepts: int = 8) -> list[str]:
    """
    Simple heuristic concept extraction.  Returns a de-duplicated list of
    concept strings (title-cased for display) with 3-8 items.
    """
    tokens = _tokenize(text)
    candidates: dict[str, int] = {}  # concept -> rough score

    # 1. Named entities — always include if present
    for tok in tokens:
        if tok in _NAMED_ENTITIES:
            key = tok.title()
            candidates[key] = candidates.get(key, 0) + 10

    # 2. Bigrams and trigrams that don't start/end with a stop word
    words = tokens  # already lower-cased
    for n in (3, 2):
        for i in range(len(words) - n + 1):
            gram = words[i : i + n]
            if gram[0] in _STOP_WORDS or gram[-1] in _STOP_WORDS:
                continue
            if all(w not in _STOP_WORDS for w in gram):
                phrase = " ".join(w.title() for w in gram)
                # Only keep if each word is 4+ chars (avoids noise)
                if all(len(w) >= 4 for w in gram):
                    candidates[phrase] = candidates.get(phrase, 0) + 3

    # 3. Significant single words (non-stop, 5+ chars, frequent)
    freq = Counter(w for w in words if w not in _STOP_WORDS and len(w) >= 5)
    for word, count in freq.most_common(15):
        key = word.title()
        candidates[key] = candidates.get(key, 0) + count

    # 4. Capitalised words in original text (likely proper nouns)
    for match in re.finditer(r"\b[A-Z][a-z]{3,}\b", text):
        word = match.group(0)
        if word.lower() not in _STOP_WORDS:
            candidates[word] = candidates.get(word, 0) + 2

    # Sort by score, deduplicate substrings, cap at max_concepts
    ranked = sorted(candidates.items(), key=lambda kv: -kv[1])
    result: list[str] = []
    seen_tokens: set[str] = set()
    for concept, _ in ranked:
        low = concept.lower()
        # Skip if this concept is a substring of one already selected
        if any(low in s.lower() and low != s.lower() for s in result):
            continue
        # Skip if all its tokens are already covered by a longer concept
        c_tokens = frozenset(low.split())
        if c_tokens <= seen_tokens and len(c_tokens) < 2:
            continue
        result.append(concept)
        seen_tokens |= c_tokens
        if len(result) >= max_concepts:
            break

    return result


# ---------------------------------------------------------------------------
# KnowledgeGraph
# ---------------------------------------------------------------------------

class KnowledgeGraph:
    """
    Persistent concept graph that grows with every council deliberation.

    Nodes  = concepts extracted from queries and syntheses.
    Edges  = co-occurrence within the same deliberation; strength accumulates.
    """

    DEFAULT_PATH = Path.home() / ".cursiv" / "council_graph.json"

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path: Path = Path(path) if path else self.DEFAULT_PATH
        self._nodes: dict[str, dict] = {}
        self._edges: dict[str, dict] = {}
        self._meta: dict = {
            "total_deliberations": 0,
            "last_updated": _now_iso(),
            "version": "1.0",
        }
        self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_deliberation(self, query: str, synthesis: str) -> int:
        """
        Extract concepts from *query* and *synthesis*, update nodes and edges.
        Returns the number of **new** concepts added.
        """
        combined = f"{query} {synthesis}"
        concepts = _extract_concepts(combined, max_concepts=8)

        new_count = 0
        now = _now_iso()

        # Update / create nodes
        for concept in concepts:
            if concept in self._nodes:
                node = self._nodes[concept]
                node["mention_count"] += 1
                # Keep the last 10 unique contexts
                ctx: list[str] = node.setdefault("contexts", [])
                if query not in ctx:
                    ctx.append(query)
                    if len(ctx) > 10:
                        ctx.pop(0)
            else:
                self._nodes[concept] = {
                    "concept": concept,
                    "first_seen": now,
                    "mention_count": 1,
                    "contexts": [query],
                    "category": _categorize(concept),
                }
                new_count += 1

        # Update / create edges (co-occurrence)
        for i, a in enumerate(concepts):
            for b in concepts[i + 1 :]:
                key = _edge_key(a, b)
                if key in self._edges:
                    self._edges[key]["strength"] += 1
                else:
                    self._edges[key] = {
                        "from": a,
                        "to": b,
                        "strength": 1,
                        "first_linked": now,
                    }

        # Update meta
        self._meta["total_deliberations"] += 1
        self._meta["last_updated"] = now

        self.save()
        return new_count

    def query_concept(self, concept: str) -> dict:
        """
        Case-insensitive fuzzy lookup.  Returns node data plus connected
        concepts (sorted by edge strength descending).
        Returns empty dict if not found.
        """
        node = self._find_node(concept)
        if node is None:
            return {}

        canon = node["concept"]
        connected = self._connected_edges(canon)

        return {
            **node,
            "connected": [
                {"concept": other, "strength": strength}
                for other, strength in connected
            ],
        }

    def related_to(self, concept: str, depth: int = 1) -> list[str]:
        """
        Return concepts connected to *concept* up to *depth* hops,
        sorted by edge strength descending (BFS, strongest-first).
        """
        node = self._find_node(concept)
        if node is None:
            return []

        start = node["concept"]
        visited: set[str] = {start}
        frontier: list[str] = [start]
        result: list[tuple[str, int]] = []  # (concept, cumulative_strength)

        for _ in range(depth):
            next_frontier: list[str] = []
            for current in frontier:
                for other, strength in self._connected_edges(current):
                    if other not in visited:
                        visited.add(other)
                        result.append((other, strength))
                        next_frontier.append(other)
            frontier = next_frontier
            if not frontier:
                break

        # Sort by strength descending, return concept names
        result.sort(key=lambda x: -x[1])
        return [c for c, _ in result]

    def prior_wisdom(self, query: str) -> Optional[str]:
        """
        Search stored contexts for matches against *query* terms.
        Returns a formatted string if anything relevant is found, else None.
        """
        query_tokens = set(
            w for w in _tokenize(query) if w not in _STOP_WORDS and len(w) >= 4
        )
        if not query_tokens:
            return None

        # Score each node by how many of its context words overlap with query
        matches: list[tuple[str, int, str]] = []  # (concept, score, best_ctx)
        for concept, node in self._nodes.items():
            score = 0
            best_ctx = ""
            for ctx in node.get("contexts", []):
                ctx_tokens = set(
                    w for w in _tokenize(ctx) if w not in _STOP_WORDS
                )
                overlap = len(query_tokens & ctx_tokens)
                if overlap > score:
                    score = overlap
                    best_ctx = ctx
            if score > 0:
                matches.append((concept, score, best_ctx))

        if not matches:
            return None

        matches.sort(key=lambda x: -x[1])
        top = matches[:5]

        related_concepts = ", ".join(c for c, _, _ in top)
        lines = [
            "[Prior Wisdom from Council Graph]",
            f"Related concepts: {related_concepts}",
        ]
        # Show the best context from the top match
        _, _, best_ctx = top[0]
        if best_ctx:
            lines.append(f'Previously deliberated: "{best_ctx}"')

        return "\n".join(lines)

    def summary(self) -> str:
        """Return a compact ASCII summary of the graph state."""
        node_count = len(self._nodes)
        edge_count = len(self._edges)
        total_delibs = self._meta.get("total_deliberations", 0)

        # Top concepts by mention count
        top = sorted(
            self._nodes.values(), key=lambda n: -n.get("mention_count", 0)
        )[:5]
        top_str = ", ".join(
            f"{n['concept']} ({n['mention_count']})" for n in top
        ) or "none yet"

        lines = [
            "=== COUNCIL KNOWLEDGE GRAPH ===",
            f"Nodes (concepts): {node_count}",
            f"Edges (connections): {edge_count}",
            f"Total deliberations indexed: {total_delibs}",
            f"Top concepts: {top_str}",
            "================================",
        ]
        return "\n".join(lines)

    def save(self) -> None:
        """
        Atomically write graph to JSON via temp-file + rename.
        Creates parent directory if needed.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": self._nodes,
            "edges": self._edges,
            "meta": self._meta,
        }
        # Write to a sibling temp file, then rename (atomic on POSIX;
        # best-effort on Windows which may raise on cross-device rename).
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self._path.parent, suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=True, indent=2)
            # On Windows, target must not exist for os.rename in some cases
            try:
                os.replace(tmp_path, self._path)  # atomic on both POSIX + Win
            except OSError:
                # Fallback: copy then delete temp
                import shutil
                shutil.copy2(tmp_path, self._path)
                os.unlink(tmp_path)
        except Exception:
            # Clean up temp file if write failed
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def load(self) -> None:
        """
        Read graph from JSON.  Silently rebuilds an empty graph on any error
        (missing file, corrupted JSON, unexpected schema).
        """
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("Top-level JSON must be an object")
            self._nodes = data.get("nodes", {})
            self._edges = data.get("edges", {})
            meta = data.get("meta", {})
            # Merge loaded meta with defaults so missing keys are tolerated
            self._meta = {**self._meta, **meta}
        except Exception:
            # Corrupted or unreadable — start fresh
            self._nodes = {}
            self._edges = {}
            self._meta = {
                "total_deliberations": 0,
                "last_updated": _now_iso(),
                "version": "1.0",
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_node(self, concept: str) -> Optional[dict]:
        """Case-insensitive node lookup; returns node dict or None."""
        # Exact match first
        if concept in self._nodes:
            return self._nodes[concept]
        # Case-insensitive scan
        low = concept.lower()
        for key, node in self._nodes.items():
            if key.lower() == low:
                return node
        return None

    def _connected_edges(self, concept: str) -> list[tuple[str, int]]:
        """
        Return [(other_concept, strength), ...] for all edges touching
        *concept*, sorted by strength descending.
        """
        results: list[tuple[str, int]] = []
        for key, edge in self._edges.items():
            if edge["from"] == concept:
                results.append((edge["to"], edge["strength"]))
            elif edge["to"] == concept:
                results.append((edge["from"], edge["strength"]))
        results.sort(key=lambda x: -x[1])
        return results


# ---------------------------------------------------------------------------
# Module-level singleton convenience
# ---------------------------------------------------------------------------

_graph: Optional[KnowledgeGraph] = None


def get_graph() -> KnowledgeGraph:
    """Return the process-level singleton KnowledgeGraph, creating it if needed."""
    global _graph
    if _graph is None:
        _graph = KnowledgeGraph()
    return _graph


def ingest(query: str, synthesis: str) -> int:
    """Ingest a deliberation into the singleton graph. Returns new concept count."""
    return get_graph().ingest_deliberation(query, synthesis)


def prior_wisdom(query: str) -> Optional[str]:
    """Query the singleton graph for prior wisdom relevant to *query*."""
    return get_graph().prior_wisdom(query)
