# Resume notes — audit RAG rebuild

**Last session:** 2026-10-13. Stopped mid-build for battery; nothing is broken.
**Test suite:** 112 passing (`cd rag && python -m pytest tests/ -q`).

---

## How to pick up

```bash
cd E:\DTU-MEITY\rag
python -m pytest tests/ -q                 # expect 112 passed
python -m ragaudit.cli status              # component readiness
```

The planning document (full review, research, roadmap) is at
https://claude.ai/code/artifact/1a57b57e-c1f4-4218-812b-d058a44c9371

---

## Decisions already settled (do not relitigate)

| Question | Answer |
|---|---|
| Goal | Production system, not a submission |
| Scope | `rag/` plus a structured store; sibling projects untouched |
| Deployment | Air-gapped, GPU server |
| Product | Conversational Q&A over report contents, per the official brief |
| Answer format | Free-text prose with citations, **not** Yes/No/Insufficient |
| Clustering role | Canonical field mapping only — routes, never answers |
| Figures | Join on `finding_id`, no visual search |

**Still open:** the real question mix (what share is exact/aggregate vs
interpretive). The router handles both and reports its reasoning, so this
does not block building — it blocks tuning.

---

## What is built and working

New package `rag/ragaudit/`, installable, replaces `rag/src/`.

| Module | State |
|---|---|
| `config.py` | Pydantic settings, all env-overridable (`RAGAUDIT_*`) |
| `domain/models.py` | Chunk, Finding, Report, Citation, FigureRef, Answer |
| `ingest/validate.py` | 11-check extraction gate — **catches real defects in both sample reports** |
| `ingest/normalize.py` | Canonical field mapping across vendor spellings |
| `ingest/chunking.py` | Field-aware; offsets carried, never `str.find` |
| `ingest/pipeline.py` | Incremental, idempotent, resumable, quarantines bad reports |
| `store/catalog.py` | SQLite + FTS5; findings, identifiers, assets, figures, chunks |
| `store/vectors.py` | Numpy + FAISS backends, prefilter inside search, no pickle |
| `retrieve/embedder.py` | Qwen3 embedder + reranker, **fail-loud on load failure** |
| `retrieve/hybrid.py` | RRF fusion, rank-based not score-based |
| `retrieve/router.py` | Deterministic structured/narrative/hybrid routing |
| `retrieve/structured.py` | SQL answering, counterexample search for universals |
| `generate/llm.py` | Pooled session, no 4xx retry, jittered backoff, circuit breaker |
| `generate/prompts.py` | Free-text schema, reasoning before conclusion |
| `generate/icl.py` | Demos that **do** cite; abstention slot guaranteed |
| `chat/session.py` | Multi-turn state, TTL, bounded |
| `chat/service.py` | Orchestration + citation verification |
| `eval/metrics.py` | Bootstrap CIs, McNemar, failures as own class |
| `eval/harness.py` | Runs against the live index |
| `api/server.py` | FastAPI: `/ask` `/findings` `/figures` `/healthz` `/readyz` |
| `cli.py` | validate, ingest, route, findings, ask, chat, serve, status, evaluate |
| `observability.py` | JSON logs, trace ids, per-stage timing |

### Verified against real data and real models

- Ingest ran with the **real Qwen3-Embedding-0.6B**: 2 reports, 22 findings,
  34 chunks, 147 figure refs tracked, 0 image assets staged.
- Structured queries work: `--severity High`, `--cwe CWE-284` both correct.
- Routing verified over all 26 available benchmark questions.

### Real defects this build found in your corpus

1. `2-report.json` — all 7 `summary_table` rows have a **URL in the title
   field**. Column misalignment. All count checks pass, which is why shape
   checks exist.
2. `4-report.json` — `summary_table` has 16 rows for 15 findings; row 16 is a
   **table header parsed as data** (`"AFFECTED ASSET Public and authenticated
   web routes..."`).
3. `4-report.json` — OBS-01..04 are titled `Initiation`, `Discovery`,
   `Validation`, `Reporting`: the **methodology table was parsed into the
   findings array**.
4. `4-report.json` — all 15 findings are severity `High`. Constant-fill
   artefact; severity filters on this report are unreliable.
5. **Qwen3-Reranker was being loaded wrong** (found by running it):
   `AutoModelForSequenceClassification` on a `Qwen3ForCausalLM` succeeds but
   randomly initialises `score.weight`, so rankings would have been confident
   noise. Now loads as causal LM and scores via the yes/no token logits the
   weights ship (`1_LogitScore/config.json`: true=9693, false=2152).

---

## Where it stopped

**Mid-verification of the fixed reranker.** The code change is complete and
committed to disk; the end-to-end check was still running when the session
ended. Resume with:

```bash
cd E:\DTU-MEITY\rag
python -c "
import sys,warnings; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
from ragaudit.app import Application
from ragaudit.config import load_settings
s = load_settings(); s.log_json = False
app = Application(s, configure_logs=False)
for h in app.build_retriever().retrieve('broken access control on token endpoints', top_k=3):
    print(f'{h.score:.3f} {h.chunk.report_id} {h.chunk.field_path}')
app.close()
"
```

Expect three hits, highest scoring on `2-REPORT findings[OBS-01]`. Scores are
log-softmax, so negative values near zero are good.

---

## Next steps, in order

1. **Finish reranker verification** (above). If scores look wrong, suspect
   prompt format in `embedder.py::_build_prompt`.
2. **Add a reranker test** — assert a relevant passage outranks an irrelevant
   one, so this class of bug cannot return silently.
3. **Finish the deliverables.** `docs/D01` and `docs/D02` are written. Still
   to write, each recording decisions and rationale:
   - D03 service architecture and the LLM client
   - D04 ingest, validation, chunking, provenance
   - D05 retrieval, fusion, scoping, ANN backends
   - D06 prompts, ICL, conversation, citation verification
   - D07 figures
   - D08 evaluation dataset and the gold-label problem
   - D09 evaluation methodology and statistics
   - D10 observability
   - D11 security and multi-tenancy
   - D12 results, limits, and what is not yet proven
4. **End-to-end chat test with a live Ollama** (`ollama serve`, `qwen3:8b`).
   Everything downstream of the LLM is tested with doubles; the real call path
   has not been exercised.
5. **Re-author gold labels** against the real JSON reports. Existing labels
   reference the synthetic text report and are keyed to chunk ids that no
   longer exist.
6. **CI**: ruff + mypy + pytest. Pin dependencies with hashes.

---

## Not done, deliberately

- Contextual Retrieval (the real LLM-generated kind) — scaffolded in config
  (`ingest.contextualize`), not implemented. Wait until evaluation can show
  whether it helps.
- FAISS HNSW is implemented but untested at scale; numpy backend is the
  default and is exact.
- Auth, rate limiting, per-tenant isolation — designed for, not built.
- `rag/src/` is untouched and still runnable. Nothing was deleted.
