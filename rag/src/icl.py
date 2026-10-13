"""
icl.py
------
In-context learning (ICL) example bank and demonstration-selection
strategies for WP1 (Sec. 4.1 of the task brief).

Three selection strategies are implemented so they can be compared under
controlled conditions (Sec. 6.2):

  1. ZeroShotICL           - no demonstrations (baseline)
  2. FixedFewShotICL       - same k hand-curated demonstrations for every
                              query, chosen to cover the answer-format
                              edge cases (positive, negative, insufficient
                              evidence)
  3. RetrievalFewShotICL   - query-specific demonstrations retrieved by
                              embedding-similarity from a labelled example
                              bank, following retrieval-based ICL, where semantically-matched
                              demonstrations reliably outperform fixed/
                              random selection, including with a simple
                              similarity retriever (no need for a learned
                              retriever to see a gain).

Each strategy returns a list of `Demonstration` objects ready to be
rendered into the prompt by prompts.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np


@dataclass
class Demonstration:
    question: str
    evidence: str
    answer: str          # "Yes" | "No" | "Insufficient Evidence"
    justification: str


def load_example_bank(path: str) -> List[Demonstration]:
    with open(path, "r") as f:
        raw = json.load(f)
    return [Demonstration(**d) for d in raw]


class ZeroShotICL:
    name = "zero_shot"

    def select(self, query: str, k: int = 0) -> List[Demonstration]:
        return []


class FixedFewShotICL:
    """Same curated demonstration set for every query. Curated to cover
    the three answer classes (Yes / No / Insufficient Evidence) so the
    model sees the full output-format contract regardless of what the
    live question turns out to be."""

    name = "fixed_few_shot"

    def __init__(self, example_bank: List[Demonstration], k: int = 3):
        # Prefer one example per answer class if the bank supports it.
        by_class = {}
        for ex in example_bank:
            by_class.setdefault(ex.answer, ex)
        self.fixed_examples = list(by_class.values())[:k] or example_bank[:k]

    def select(self, query: str, k: Optional[int] = None) -> List[Demonstration]:
        return self.fixed_examples[: k or len(self.fixed_examples)]


class RetrievalFewShotICL:
    """Per-query demonstration retrieval by cosine similarity over an
    embedded example bank (Dr.ICL / retrieval-based-ICL style). Falls
    back to a diversity-aware cap: examples are drawn from at most two
    distinct answer classes among the retrieved top-N so the model isn't
    shown a class-imbalanced prompt purely by retrieval coincidence.
    """

    name = "retrieval_few_shot"

    def __init__(self, example_bank: List[Demonstration], embedder, k: int = 4):
        self.example_bank = example_bank
        self.embedder = embedder
        self.k = k
        bank_texts = [ex.question for ex in example_bank]
        self._bank_embs = embedder.embed_passages(bank_texts) if example_bank else np.zeros((0, 1))

    def select(self, query: str, k: Optional[int] = None) -> List[Demonstration]:
        k = k or self.k
        if not self.example_bank:
            return []
        q_emb = self.embedder.embed_queries([query])[0]
        sims = self._bank_embs @ q_emb
        order = np.argsort(-sims)
        return [self.example_bank[i] for i in order[:k]]


STRATEGIES = {
    "zero_shot": ZeroShotICL,
    "fixed_few_shot": FixedFewShotICL,
    "retrieval_few_shot": RetrievalFewShotICL,
}
