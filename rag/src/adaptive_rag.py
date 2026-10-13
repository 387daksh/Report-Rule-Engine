"""Small, deterministic additions for the modern audit-RAG path.

Keeps routing and citation checks independent of any model or vector database,
so the same safety behavior works in an air-gapped deployment and in tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class QueryRoute:
    mode: str
    queries: List[str]


_INJECTION_PATTERNS = (
    r"ignore (?:all )?(?:previous|prior) instructions",
    r"system prompt",
    r"developer message",
    r"reveal (?:the )?(?:prompt|instructions)",
    r"<\s*(?:system|assistant|tool)\s*>",
)


def contains_prompt_injection(text: str) -> bool:
    """Detect instruction-like report text and force human review."""
    return any(re.search(pattern, text, re.I) for pattern in _INJECTION_PATTERNS)


def route_query(question: str) -> QueryRoute:
    """Choose cheap retrieval paths from observable question features."""
    q = question.strip()
    exact = bool(re.search(r"\b(?:CVE|CWE|CVSS|ISO|NIST|Q\d+)\b|\b\d+(?:\.\d+)?%", q, re.I))
    aggregate = bool(re.search(r"\b(all|each|every|across|trend|repeated|agency|vendors|reports)\b", q, re.I))
    if exact:
        return QueryRoute("exact", [q])
    if aggregate:
        return QueryRoute("aggregate", [q, q.replace("?", "") + " evidence findings scope coverage"])
    return QueryRoute("local", [q])


def valid_citations(cited_ids: Iterable[str], retrieved_ids: Sequence[str]) -> bool:
    """Reject citations that were not present in the evidence context."""
    cited = {str(x) for x in cited_ids if str(x).strip()}
    return cited.issubset(set(retrieved_ids))


def evidence_supports(quote: str, texts: Sequence[str], threshold: float = 0.70) -> bool:
    """Conservative lexical support check; entailment still needs a verifier model."""
    words = set(re.findall(r"\w+", quote.lower()))
    if not words:
        return False
    for text in texts:
        lower = text.lower()
        if quote.lower().strip() in lower:
            return True
        overlap = len(words & set(re.findall(r"\w+", lower))) / len(words)
        if overlap >= threshold:
            return True
    return False
