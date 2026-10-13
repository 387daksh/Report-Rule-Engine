"""Ingest: validation gate, normalisation, chunking, idempotency."""

from __future__ import annotations

import json

import pytest

from ragaudit.domain.models import FindingStatus, Severity
from ragaudit.ingest.chunking import FieldAwareChunker
from ragaudit.ingest.normalize import normalize_report
from ragaudit.ingest.pipeline import derive_report_id
from ragaudit.ingest.validate import Level, validate_report


# --------------------------------------------------------------------------
# Validation gate
# --------------------------------------------------------------------------


def test_detects_url_in_title_column(sample_data):
    """The real defect in 2-report.json: every summary row's title is a URL."""
    result = validate_report(sample_data, "R1")
    issue = next((i for i in result.issues if i.check == "title_not_a_url"), None)
    assert issue is not None
    assert issue.level is Level.BLOCKING
    assert not result.ok


def test_counts_alone_do_not_prove_extraction_is_sound(sample_data):
    """Guards the premise of the gate.

    Every count-based check passes on this report while a column is
    misaligned, which is why shape checks exist alongside count checks.
    """
    result = validate_report(sample_data, "R1")
    count_checks = {"total_matches_array", "severity_counts_sum", "summary_detail_ids_match"}
    assert not [i for i in result.issues if i.check in count_checks]
    assert [i for i in result.blocking if i.check == "title_not_a_url"]


def test_detects_orphan_summary_row():
    data = {
        "executive_summary": {
            "total_findings": 2,
            "summary_table": [
                {"finding_id": "OBS-01", "title": "Weak cipher"},
                {"finding_id": "OBS-02", "title": "Missing header"},
                {"finding_id": "OBS-99", "title": "AFFECTED ASSET header row"},
            ],
        },
        "detailed_observations": [
            {"finding_id": "OBS-01", "title": "Weak cipher", "observation_description": "x"},
            {"finding_id": "OBS-02", "title": "Missing header", "observation_description": "y"},
        ],
    }
    result = validate_report(data, "R1")
    issue = next(i for i in result.issues if i.check == "summary_detail_ids_match")
    assert issue.level is Level.BLOCKING
    assert "OBS-99" in issue.message


def test_detects_methodology_phases_as_findings():
    data = {
        "detailed_observations": [
            {"finding_id": f"OBS-0{i}", "title": t, "observation_description": "text", "severity": "High"}
            for i, t in enumerate(["Initiation", "Discovery", "Validation", "Reporting"], start=1)
        ]
    }
    result = validate_report(data, "R1")
    assert any(i.check == "title_not_a_methodology_phase" and i.level is Level.BLOCKING
               for i in result.issues)


def test_detects_constant_severity_fill():
    data = {
        "detailed_observations": [
            {"finding_id": f"OBS-{i:02d}", "title": f"Issue {i}",
             "severity": "High", "observation_description": "text"}
            for i in range(1, 9)
        ]
    }
    result = validate_report(data, "R1")
    assert any(i.check == "severity_variation" for i in result.issues)


def test_clean_report_passes():
    data = {
        "report_meta": {"report_title": "Clean", "classification": "Confidential"},
        "executive_summary": {
            "total_findings": 2,
            "severity_count": {"high": 1, "low": 1},
            "summary_table": [
                {"finding_id": "OBS-01", "title": "Broken access control"},
                {"finding_id": "OBS-02", "title": "Verbose errors"},
            ],
        },
        "detailed_observations": [
            {"finding_id": "OBS-01", "title": "Broken access control", "severity": "High",
             "status": "Open", "observation_description": "Endpoint lacked authorisation."},
            {"finding_id": "OBS-02", "title": "Verbose errors", "severity": "Low",
             "status": "Closed", "observation_description": "Stack traces returned."},
        ],
    }
    result = validate_report(data, "R1")
    assert result.ok, [str(i) for i in result.blocking]


def test_missing_findings_array_blocks_but_empty_array_only_warns():
    assert not validate_report({"report_meta": {}}, "R1").ok
    result = validate_report({"detailed_observations": []}, "R1")
    assert result.ok
    assert any(i.check == "findings_array_empty" for i in result.warnings)


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------


def test_normalises_field_drift_between_vendors():
    """Both spellings of the findings array produce the same canonical shape."""
    a = {"detailed_observations": [
        {"finding_id": "F1", "title": "T", "severity": "High", "status": "Open",
         "observation_description": "obs"}]}
    b = {"vulnerabilities": [
        {"id": "F1", "vulnerability_title": "T", "severity": "High", "status": "Open",
         "detailed_observation": "obs"}]}
    fa = normalize_report(a, "R1").findings[0]
    fb = normalize_report(b, "R1").findings[0]
    assert (fa.finding_id, fa.title, fa.severity, fa.observation) == \
           (fb.finding_id, fb.title, fb.severity, fb.observation)


def test_severity_and_status_parse_aliases():
    assert Severity.parse("critical") is Severity.CRITICAL
    assert Severity.parse("INFO") is Severity.INFORMATIONAL
    assert Severity.parse("weird value") is Severity.UNKNOWN
    assert FindingStatus.parse("Remediated") is FindingStatus.CLOSED
    assert FindingStatus.parse("") is FindingStatus.UNKNOWN


def test_figure_tokens_are_preserved_not_dropped(sample_data):
    """Regression: the previous parser deleted these tokens by policy."""
    report = normalize_report(sample_data, "R1")
    total = sum(len(f.figure_tokens) for f in report.findings)
    assert total == 15
    assert all(t.startswith("[IMAGE_PAGE_") for f in report.findings for t in f.figure_tokens)


def test_placeholder_report_ids_are_rejected(tmp_path):
    """'NA' appears as report_id in the corpus and would collide globally."""
    path = tmp_path / "myreport.json"
    path.write_text("{}", encoding="utf-8")
    assert derive_report_id({"report_meta": {"report_id": "NA"}}, path) == "MYREPORT"
    assert derive_report_id({"report_meta": {"report_id": "AR-2026-001"}}, path) == "AR-2026-001"


def test_hard_wraps_are_collapsed():
    data = {"detailed_observations": [
        {"finding_id": "F1", "observation_description": "line one \nline two  \n line three"}]}
    assert normalize_report(data, "R1").findings[0].observation == "line one line two line three"


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------


def test_small_finding_becomes_one_chunk():
    data = {"detailed_observations": [
        {"finding_id": "F1", "title": "Short", "severity": "Low", "status": "Open",
         "observation_description": "A brief observation."}]}
    chunks = FieldAwareChunker().chunk_report(normalize_report(data, "R1"))
    assert len(chunks) == 1
    assert chunks[0].finding_id == "F1"
    assert "Severity: Low" in chunks[0].text


def test_large_finding_splits_on_field_boundaries():
    long_text = "This sentence describes the issue in detail. " * 60
    data = {"detailed_observations": [
        {"finding_id": "F1", "title": "Big", "severity": "High", "status": "Open",
         "observation_description": long_text, "recommendation": long_text}]}
    chunks = FieldAwareChunker(max_tokens=200).chunk_report(normalize_report(data, "R1"))
    paths = {c.field_path for c in chunks}
    assert "findings[F1].observation" in paths
    assert "findings[F1].recommendation" in paths
    # Every piece keeps the header so a chunk retrieved alone is identifiable.
    assert all("[F1]" in c.text for c in chunks)


def test_offsets_are_valid_and_monotonic_within_a_field():
    long_text = "Sentence number one here. " * 80
    data = {"detailed_observations": [
        {"finding_id": "F1", "observation_description": long_text}]}
    chunks = [c for c in FieldAwareChunker(max_tokens=120).chunk_report(normalize_report(data, "R1"))
              if c.field_path.endswith(".observation")]
    assert len(chunks) > 1
    assert all(0 <= c.start_char < c.end_char for c in chunks)
    assert [c.start_char for c in chunks] == sorted(c.start_char for c in chunks)


def test_offsets_survive_repeated_phrases():
    """A phrase repeated verbatim is where str.find-based offsets mislocate."""
    repeated = "The control was not implemented. " * 40
    data = {"detailed_observations": [{"finding_id": "F1", "observation_description": repeated}]}
    chunks = [c for c in FieldAwareChunker(max_tokens=100).chunk_report(normalize_report(data, "R1"))
              if c.field_path.endswith(".observation")]
    starts = [c.start_char for c in chunks]
    assert len(set(starts)) == len(starts), "offsets collapsed onto the first occurrence"


def test_chunk_ids_are_stable_across_runs(sample_data):
    report = normalize_report(sample_data, "R1")
    first = [c.chunk_id for c in FieldAwareChunker().chunk_report(report)]
    second = [c.chunk_id for c in FieldAwareChunker().chunk_report(normalize_report(sample_data, "R1"))]
    assert first == second


def test_context_prefix_is_not_quotable():
    """Contextual Retrieval text must not leak into citations (D04)."""
    from ragaudit.domain.models import Chunk

    chunk = Chunk(
        chunk_id="c1", report_id="R1", section="Findings", field_path="findings[F1]",
        text="The endpoint lacked authorisation.", start_char=0, end_char=34,
        token_count=6, context_prefix="This passage is from the API audit of Acme.",
    )
    assert "Acme" in chunk.embedding_text
    assert "Acme" not in chunk.quotable_text


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------


def test_ingest_is_idempotent(pipeline, catalog, index, sample_report_path):
    first = pipeline.ingest_file(sample_report_path, force=True)
    chunks_after_first = catalog.stats()["chunks"]
    vectors_after_first = len(index)

    second = pipeline.ingest_file(sample_report_path, force=True)
    assert second.chunks == first.chunks
    assert catalog.stats()["chunks"] == chunks_after_first
    assert len(index) == vectors_after_first


def test_unchanged_source_is_skipped(pipeline, sample_report_path):
    pipeline.ingest_file(sample_report_path, force=True)
    assert pipeline.ingest_file(sample_report_path).status == "skipped"


def test_blocking_validation_quarantines_without_indexing(catalog, index, embedder, tmp_path):
    from ragaudit.ingest.pipeline import IngestPipeline

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "executive_summary": {"total_findings": 9},
        "detailed_observations": [{"finding_id": "F1", "observation_description": "text"}],
    }), encoding="utf-8")

    strict = IngestPipeline(catalog, index, embedder, fail_on_validation_error=True)
    outcome = strict.ingest_file(bad)

    assert outcome.status == "quarantined"
    assert outcome.blocking
    # Quarantined content must not be retrievable.
    assert catalog.stats()["chunks"] == 0
    assert len(index) == 0


def test_reingest_removes_superseded_vectors(catalog, index, embedder, tmp_path):
    from ragaudit.ingest.pipeline import IngestPipeline

    path = tmp_path / "r.json"
    path.write_text(json.dumps({"detailed_observations": [
        {"finding_id": f"F{i}", "title": f"T{i}", "observation_description": "text " * 30}
        for i in range(6)]}), encoding="utf-8")

    pipe = IngestPipeline(catalog, index, embedder, fail_on_validation_error=False)
    pipe.ingest_file(path, force=True)
    before = len(index)

    path.write_text(json.dumps({"detailed_observations": [
        {"finding_id": "F0", "title": "T0", "observation_description": "text " * 30}]}),
        encoding="utf-8")
    pipe.ingest_file(path, force=True)

    assert len(index) < before, "old vectors from the previous extraction are still searchable"
    assert catalog.stats()["findings"] == 1
