# D02 — Architecture: three stores behind one router

**Decision:** route each question to the store that can answer it soundly.
Structured fields answer by SQL, narrative prose answers by retrieval, and
the canonical schema layer routes but never answers.

---

## 1. The problem with a single retrieval path

The previous system sent every question through the same pipeline: flatten
the report to text, chunk, embed, retrieve top-k, ask a model. Applied to this
corpus that is wrong in two distinct ways.

**It discards structure that already exists.** `docling_parser._parse_json`
turned a clean relational record into lines like
`Findings > [1] > Severity: High`, embedded them, and then asked an 8B model
to recover the field semantics statistically. The extractor had already done
that work.

**Retrieval cannot answer aggregate questions soundly.** "How many high
findings are open?" answered from the top-k chunks is a count over a sample.
Retrieval never promises it saw every row, so the number may be wrong and
there is no way to tell from the output. This is not a tuning problem; it is
a category error.

Measured on the supplied benchmark: **all eight** questions in
`real_reports_benchmark_questions.json` are predicates over extracted fields.

| Question | Resolves to |
|---|---|
| RQ1 contains detailed findings | `len(findings) > 0` |
| RQ2 at least one High finding | `any(severity == 'High')` |
| RQ3 marks findings Open | `any(status == 'Open')` |
| RQ4 provides CWE classifications | `any(cwe_ids)` |
| RQ5 provides recommendations | `any(recommendation)` |
| RQ6 all findings closed | `all(status == 'Closed')` |
| RQ7 includes audit timeline | `audit_timeline` populated |
| RQ8 no findings identified | `len(findings) == 0` |

The reported 81.25% accuracy was measured on a benchmark that roughly ten
lines of SQL answer at 100%, deterministically, in milliseconds.

## 2. The three stores

### Structured field store — `ragaudit/store/catalog.py`

SQLite (Postgres in production), holding normalised findings with severity,
status, CVSS, CWE, CVE and affected assets. Multi-valued attributes get their
own tables so `WHERE cwe = 'CWE-284'` is an index lookup rather than a `LIKE`
scan over JSON.

Answers: counts, universal and existential claims, identifier lookups,
field-presence checks, severity and status breakdowns.

No model is involved, so the answer is reproducible and a reader can re-run
the query by hand. That is what makes it defensible to the party being
audited.

Universal claims are answered by **counterexample search**: "are all findings
closed?" queries for findings that are *not* closed. One counterexample
settles it, and the completeness of the scan is what makes a "yes" credible.

### Narrative vector index — `ragaudit/store/vectors.py`

Dense embeddings over the genuinely prose fields only: `observation`,
`impact`, `recommendation`, `preconditions`, plus report-level sections such
as scope and methodology. 31% of report content by character count.

Answers: interpretive and explanatory questions, where the answer is not in
any field — "why was this accepted as residual risk", "was the methodology
adequate for the stated scope".

### Canonical schema layer — `ragaudit/ingest/normalize.py`

Field aliases mapping vendor spellings onto one shape. The supplied corpus
already drifts: `2-report.json` uses `detailed_observations` where
`report_structure.json` specifies `vulnerabilities`, and
`observation_description` where the schema says `detailed_observation`.

**This layer routes; it never answers.** A user asking about one report does
not want a cluster centroid. What the clustering in `schema_extractor/` buys
is the mapping that lets one assistant work across thousands of reports whose
field names disagree — invisible to the user, and load-bearing.

It also separates two cases a pure retrieval system conflates: a report that
genuinely omits a required section (an audit finding) versus a report where
extraction missed it (a bug). Heading support per vendor distinguishes them.

## 3. Routing

`ragaudit/retrieve/router.py`. A deterministic rule set, not a classifier.

An audit system must explain why a question took the path it did, and a regex
a reader can inspect is a better explanation than a classifier logit. Every
plan carries `reasons`, surfaced on the answer, so a misroute is visible.

Precedence, highest first:

1. **Narrative intent** (`why`, `explain`, `adequate`, `summarise`) wins
   outright. A question can mention a severity and still be asking for
   judgement: "why were the high findings accepted?" is not a SQL query.
2. **Policy qualifier** (`within the organisation's SLA`, `per policy`)
   forces hybrid. The threshold itself lives in prose; the statuses live in
   fields. Answering from either half alone overstates the evidence.
3. **Aggregate or universal** with a field predicate goes structured.
   Soundness requires the complete set.
4. **Field predicate** (severity, status, CWE, CVE) goes structured.
5. **Presence intent plus a field noun** goes structured. Both are required:
   "do all vendor contracts include a breach clause?" reads as a presence
   question, but no field holds it, so it belongs in retrieval.
6. **Figure request** goes hybrid — locate the finding, then join its figures.
7. Otherwise narrative.

Measured over all 26 available questions plus hand-written probes: 13
structured, 12 narrative, 1 hybrid, with no misroutes remaining after the
two corrections recorded in §5.

## 4. Why not the alternatives

| Alternative | Why not |
|---|---|
| Everything through retrieval | Counts and universals become unsound; exact lookups become slow and fallible |
| Everything through SQL | Cannot answer "why", "explain", "was this adequate" — no field holds judgement |
| LLM-generated SQL (text-to-SQL) | Non-deterministic query generation against audit data. A wrong `WHERE` clause produces a confident wrong number with no way to notice |
| Classifier-based routing | Cannot explain itself; needs labelled routing data that does not exist yet |
| Agentic multi-step retrieval | The agentic-RAG survey is explicit that planning yields "less predictable outcomes compared to deterministic workflows". Determinism is a requirement here |

## 5. Corrections made during implementation

Both found by running the router over the real benchmark.

**Presence intent alone over-triggered.** "Do all active third-party vendor
contracts in scope include a data breach notification clause?" routed to SQL
because "include" matched. Fixed by requiring a field noun alongside the
presence verb.

**Policy qualifiers were invisible.** "Have all high-severity vulnerabilities
been remediated within the organisation's internal SLA?" routed to pure SQL,
which would have answered the status question while silently ignoring the SLA
window. Now hybrid.

## 6. Scale

At 3,000 reports × 300 pages:

| Layer | Size | Note |
|---|---|---|
| Narrative vectors | low hundreds of thousands | ≈1.5 GB float32, under 0.5 GB quantised. Fits in memory under HNSW |
| Findings rows | a few hundred thousand | Trivial for Postgres |
| Raw corpus | ≈450M tokens | Never embedded whole; only the 31% that is prose |

Embedding only the narrative is what keeps the index in the hundreds of
thousands rather than the millions a whole-document flattening would produce.
