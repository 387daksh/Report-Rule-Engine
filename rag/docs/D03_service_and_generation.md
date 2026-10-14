# D03 — Service architecture and the generation client

**Decision:** ingestion and serving are separate programs over shared
persistent state, and every dependency failure is visible in the response.

---

## 1. Ingest / serve split

The previous harness did everything in one run: parse, chunk, embed, index,
query, score. It wrote a fresh index per run, which left more than twenty
near-duplicate FAISS copies under `results/`.

That cannot scale to 3,000 reports, for a reason that is structural rather
than a matter of tuning: answering one question required rebuilding the whole
corpus.

| Program | Entry point | Responsibility |
|---|---|---|
| Ingest | `ragaudit ingest` | Parse, validate, normalise, chunk, embed, upsert |
| Serve | `ragaudit serve` | Load the existing index, answer questions |
| Evaluate | `ragaudit evaluate` | Run a question set against the **serving** index |

Evaluation deliberately does not build its own index. What is measured is what
runs.

### Incremental and idempotent

`IngestPipeline` skips a report whose source SHA-256 is unchanged, and a
re-ingest *replaces* rather than appends:

```python
self.index.remove_report(report.report_id)      # drop superseded vectors
self.catalog.upsert_report(report, ...)         # delete-then-insert rows
```

Append-only would leave the previous extraction retrievable, so the assistant
could cite superseded evidence as current. `test_reingest_removes_superseded_vectors`
pins this.

## 2. Configuration

Everything is a `pydantic-settings` field with a `RAGAUDIT_` environment
override. Nothing reads a hardcoded host, path or model name at call time.

```bash
RAGAUDIT_GENERATION__MODEL_NAME=qwen3:8b
RAGAUDIT_GENERATION__BASE_URL=http://gpu-01:11434
RAGAUDIT_RETRIEVAL__BACKEND=faiss
```

The previous client had `OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"`
as a module constant, which made a remote inference host a code change.

## 3. The generation client

`ragaudit/generate/llm.py`. Each property below exists because its absence
caused a specific failure.

| Property | Why |
|---|---|
| Pooled `requests.Session` | The previous client opened a fresh connection per call; at 3 calls per question that is pure latency |
| Split connect / read timeouts | A dead host should fail in 5s, not after the 120s read budget |
| No retry on 4xx | A malformed request fails identically on attempt three. The old client retried everything, tripling the latency of guaranteed failures |
| Full-jitter backoff | Concurrent workers must not retry in lockstep |
| Circuit breaker | A dead backend fails fast instead of every request burning its full retry budget |
| Client errors do not trip the breaker | The server is healthy; the request was wrong. Opening the circuit would take down every other caller for one bad payload |
| Token accounting | Prompt and completion tokens are returned, so cost is measurable |

## 4. Two context failures found by running the system

Both were invisible to the test suite because both produced *plausible*
output from a broken configuration. They are recorded in full because they are
the clearest examples of the failure class this project exists to eliminate.

### 4.1 Ollama silently truncates the prompt

Ollama defaults `num_ctx` to 4096 tokens and **discards anything beyond it
without error**. The real prompt measured 5,330 tokens:

```
retrieved chunks: 20
prompt chars: 20062  (+system = 21322)
approx tokens: 5330
```

So roughly 1,200 tokens were cut from the tail — which is exactly where the
response-format instruction lives. The model never saw the instruction to emit
JSON, produced prose, and the failure was attributed to the model.

Fix, in two parts:

1. `num_ctx` is now set explicitly from `generation.context_tokens`
   (default 16384). Never rely on a server default that fails silently.
2. Evidence is fitted to a prompt budget before sending
   (`fit_evidence_to_budget`), dropping the lowest-ranked chunks first and
   reporting the count as `evidence_trimmed_to_context:<n>` on the answer.

The second part matters independently: a context window large enough today
will not be large enough for every question, and the system must trim
deliberately rather than let the server do it blindly.

### 4.2 Truncated generation reported as a parse failure

With the context fixed, answers still failed. Raw output showed
`out_tokens=1024` — exactly the cap — with the JSON cut mid-object.

`Completion.truncated` is now set when the model stops because it hit the cap
rather than because it finished. The chat service distinguishes the two:

| Condition | `abstention_reason` | What the user sees |
|---|---|---|
| Hit the token cap | `truncated_generation` | "The answer was cut off before it finished. Raise generation.max_tokens, or ask a narrower question." |
| Genuinely malformed | `unparseable_model_output` | "I could not produce a well-formed answer…" |

"Ran out of room" has an obvious fix; "malformed output" sends you debugging
the wrong thing. Reporting both identically hid a configuration problem behind
an apparent model problem.

`max_tokens` default raised 1024 → 2048, and the prompt now asks for at most
400 words and six citations, so the budget is spent on the answer rather than
on a preamble.

## 5. Fail-loud policy

Four paths in the previous implementation degraded silently into something
that looked like success:

| Component | Old behaviour | Now |
|---|---|---|
| Embedder | Fell back `bge-m3` → `bge-large`, changing the vector space, unrecorded | `ModelLoadError` naming the path |
| Reranker | Returned `1.0/(i+1)` as a score, so rank 0 always scored exactly 1.0 | `ModelLoadError` |
| CRAG gate | Any exception returned `verdict="CORRECT"` | Removed; the router is deterministic and cannot fail open |
| Docling chunker | Both branches called the fallback; the import result was discarded | Replaced by field-aware chunking (D04) |

The principle: **a component that cannot do its job must say so.** A retrieval
system that cannot load its retriever has nothing useful to contribute, and
silence is better than invented confidence.

## 6. Health endpoints

`/healthz` answers whether the process is alive and touches no dependency.
`/readyz` answers whether a question can actually be served:

```json
{"ready": true, "checks": {
  "catalog": {"reports": 2, "findings": 22, "chunks": 34, "figures": 147},
  "index_vectors": 34,
  "embedding_model": "Qwen3-Embedding-0.6B:1024",
  "llm_reachable": true}}
```

`embedding_model` carries the vector-space fingerprint, so a model swap that
would invalidate the index is visible before it corrupts answers rather than
after.

## 7. Verified configuration

Measured on this machine, 2026-10-14:

| Component | Value |
|---|---|
| Embedding | `Qwen3-Embedding-0.6B`, 1024-dim, CPU |
| Reranking | `Qwen3-Reranker-0.6B`, logit scoring, CPU |
| Generation | `qwen3:1.7b` via Ollama, CPU |
| GPU | Unavailable — Ollama dropped the ROCm device (`gfx1103` unsupported) |

The GPU note matters for interpreting latency: every figure in D12 is CPU-only
and should improve substantially on the target GPU server.
