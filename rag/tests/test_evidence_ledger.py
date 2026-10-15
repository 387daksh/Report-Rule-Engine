"""Adversarial tests for the evidence ledger.

These are written before the agent loop exists, because the failure they guard
against is invisible: if verification silently becomes a no-op, nothing errors
and the fabrication metric reads as an improvement. Each test encodes one way
that could happen.

The ledger itself does not verify quotes — ``_verify_citations`` /
``_quote_supported`` do that, against ``ledger.shown_text(chunk_id)``. So these
tests assert the two halves together: the ledger stores the right text, and
the existing verifier accepts/rejects correctly against it.
"""

from __future__ import annotations

from ragaudit.agent.evidence import EvidenceLedger
from ragaudit.chat.service import _quote_supported
from ragaudit.domain.models import Chunk


def _chunk(chunk_id: str, text: str, finding_id: str = "OBS-01") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        report_id="R1",
        section="Findings",
        field_path=f"findings[{finding_id}]",
        text=text,
        start_char=0,
        end_char=len(text),
        token_count=max(1, len(text) // 4),
        finding_id=finding_id,
    )


def _verify(ledger: EvidenceLedger, chunk_id: str, quote: str) -> bool:
    """Mirror what _verify_citations does: check the quote against SHOWN text."""
    shown = ledger.shown_text(chunk_id)
    if shown is None:
        return False  # chunk not in evidence
    return _quote_supported(quote, shown)


# --------------------------------------------------------------------------
# The five adversarial cases
# --------------------------------------------------------------------------


def test_quote_from_truncated_away_tail_fails():
    """The subtlest failure: register the shown view, not the full chunk.

    A search returns a long chunk but only its head reaches the model. A quote
    from the tail the model never saw must NOT verify. If the ledger stored
    chunk.quotable_text instead of the shown slice, this passes wrongly.
    """
    full = (
        "The admin endpoint did not enforce authorisation checks. "
        "Separately, the backup server retained credentials in plaintext."
    )
    shown = "The admin endpoint did not enforce authorisation checks."
    ledger = EvidenceLedger()
    ledger.register(_chunk("c1", full), shown_text=shown, step=1)

    assert _verify(ledger, "c1", "did not enforce authorisation checks")
    assert not _verify(ledger, "c1", "backup server retained credentials in plaintext")


def test_citation_to_a_chunk_never_registered_fails():
    """A chunk id the model only saw in a metadata listing is not citable."""
    ledger = EvidenceLedger()
    ledger.register(_chunk("c1", "Authorisation was not enforced."), shown_text="Authorisation was not enforced.", step=1)

    assert "c2" not in ledger
    assert not _verify(ledger, "c2", "anything at all")


def test_quote_lifted_from_another_chunk_fails():
    """Cross-attribution: text belongs to a different registered chunk."""
    ledger = EvidenceLedger()
    ledger.register(_chunk("c1", "Broken access control on the token API."), shown_text="Broken access control on the token API.", step=1)
    ledger.register(_chunk("c2", "Verbose error messages leaked stack traces."), shown_text="Verbose error messages leaked stack traces.", step=2)

    # Quote from c2's text attributed to c1 must fail against c1's shown text.
    assert not _verify(ledger, "c1", "Verbose error messages leaked stack traces")
    # ... and correctly verifies against its real chunk.
    assert _verify(ledger, "c2", "Verbose error messages leaked stack traces")


def test_metadata_listing_without_text_does_not_make_a_chunk_citable():
    """Registering nothing (empty shown_text) must leave the chunk uncitable.

    A tool like list_reports or query_findings surfaces ids and titles but no
    chunk-addressable text. It must not call register with real text, and if
    it accidentally passes empty text, the ledger must ignore it.
    """
    ledger = EvidenceLedger()
    ledger.register(_chunk("c1", "Some real chunk text."), shown_text="", step=1)
    assert "c1" not in ledger
    assert len(ledger) == 0


def test_empty_ledger_verifies_nothing():
    """The catastrophic seeding bug: an empty ledger must reject everything.

    If this ever passed — if an empty or corpus-seeded ledger accepted a real
    chunk id — fabrication detection would be a no-op.
    """
    ledger = EvidenceLedger()
    assert not _verify(ledger, "any-real-looking-id", "a plausible quote")


# --------------------------------------------------------------------------
# Span-growth behaviour
# --------------------------------------------------------------------------


def test_longer_view_of_same_chunk_wins():
    """A fuller later view expands what is citable; a shorter one never shrinks it."""
    short = "Authorisation was not enforced."
    long = "Authorisation was not enforced on any token state transition endpoint."
    ledger = EvidenceLedger()

    ledger.register(_chunk("c1", long), shown_text=short, step=1)
    assert not _verify(ledger, "c1", "token state transition endpoint")

    ledger.register(_chunk("c1", long), shown_text=long, step=3)
    assert _verify(ledger, "c1", "token state transition endpoint")


def test_shorter_later_view_does_not_shrink_citable_span():
    long = "Authorisation was not enforced on any token state transition endpoint."
    short = "Authorisation was not enforced."
    ledger = EvidenceLedger()

    ledger.register(_chunk("c1", long), shown_text=long, step=1)
    ledger.register(_chunk("c1", long), shown_text=short, step=2)
    assert _verify(ledger, "c1", "token state transition endpoint")


def test_earliest_step_is_preserved_across_reregistration():
    long = "Authorisation was not enforced on any token state transition endpoint."
    ledger = EvidenceLedger()
    ledger.register(_chunk("c1", long), shown_text="Authorisation was not enforced.", step=2)
    ledger.register(_chunk("c1", long), shown_text=long, step=5)
    assert ledger.get("c1").first_step == 2


def test_as_retrieved_orders_by_first_appearance():
    ledger = EvidenceLedger()
    ledger.register(_chunk("c2", "second seen."), shown_text="second seen.", step=3)
    ledger.register(_chunk("c1", "first seen."), shown_text="first seen.", step=1)
    retrieved = ledger.as_retrieved()
    assert [r.chunk.chunk_id for r in retrieved] == ["c1", "c2"]
    assert [r.rank for r in retrieved] == [0, 1]
