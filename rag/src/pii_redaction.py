"""
pii_redaction.py
------------------
Optional, best-effort redaction of common personally-identifiable
patterns (email addresses, phone numbers, IP addresses, and common
government-ID-like number formats) in audit-report text before it is
chunked and embedded.

This is a defence-in-depth measure, NOT a substitute for the source
data already being handled per the organisation's data-classification
policy before it ever reaches this pipeline. It is disabled by default
(`redact_pii: false` in eval_config.json) so it never silently changes
evidence text without an explicit opt-in, since redaction can remove
information a benchmark question legitimately needs (e.g. "is the named
data protection officer's contact information published?"). Enable it
for corpora where the audit reports contain personal data,  auditor
names, subject employee names, that should not
be persisted in the vector index or reproduced in LLM output/logs.

This is intentionally simple, regex-based redaction, not a full
named-entity-recognition PII pipeline — appropriate for a proof-of-
concept; a production deployment handling regulated personal data
should replace this with the organisation's approved
DLP/redaction tooling.
"""

from __future__ import annotations

import re

_PATTERNS = {
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "PHONE": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?){2,4}\d{3,4}\b"),
    "IPV4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    # Generic 9-12 digit government-ID-like sequences (e.g. Aadhaar-style,
    # SSN-style). Intentionally broad/conservative — over-redaction of a
    # false-positive number is a far cheaper error than under-redaction.
    "ID_NUMBER": re.compile(r"\b\d{9,12}\b"),
}


def redact(text: str) -> str:
    redacted = text
    for label, pattern in _PATTERNS.items():
        redacted = pattern.sub(f"[REDACTED_{label}]", redacted)
    return redacted


def redact_if_enabled(text: str, enabled: bool) -> str:
    return redact(text) if enabled else text
