# Running the demo

## One command

```
run.bat
```

Double-click it, or run it from a terminal in this folder. It finds a Python
with the dependencies, starts Ollama if it is not already up, pulls the model
on first run, ingests the corpus if the index is empty, then starts the
console and opens the browser.

On Linux or macOS, or in Git Bash: `./run.sh`

| Command | What it does |
|---|---|
| `run.bat` | Start everything, open http://localhost:8077 |
| `run.bat demo` | Scripted walkthrough in the terminal |
| `run.bat chat` | Interactive session in the terminal |
| `run.bat check` | Report what is ready, change nothing |
| `run.bat ingest` | Re-ingest the corpus |
| `run.bat test` | Run the test suite |

Stop the server with Ctrl-C.

---

## Doing it by hand

If you would rather drive each step yourself, or `run.bat` fails and you want
to see where:

```bat
cd E:\DTU-MEITY\rag
set PY=C:\Users\hp\AppData\Local\Programs\Python\Python310\python.exe
set RAGAUDIT_GENERATION__MODEL_NAME=qwen3:1.7b
set RAGAUDIT_RERANKER__ENABLED=false

REM 1. Model server, in its own terminal
"%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve

REM 2. First run only, about 1.4 GB
"%LOCALAPPDATA%\Programs\Ollama\ollama.exe" pull qwen3:1.7b

REM 3. Check everything is wired up
%PY% -m ragaudit.cli demo check

REM 4. Ingest, if var\index is empty
%PY% -m ragaudit.cli demo setup

REM 5. Start the console
%PY% -m ragaudit.cli serve --port 8077
```

Then open **http://localhost:8077**.

Use the interpreter the packages were installed into, which is not
necessarily the first `python` on PATH — that is the one thing `run.bat`
resolves for you that is easy to get wrong by hand.

---

## The console

The right-hand panel has three groups of example questions, one per path.
Each answer shows a **route badge**, the **evidence** behind it, any
**figures**, and any **review flags**. Those flags are the point: they are
what the system caught itself doing.

## Driving it from the terminal instead

```bash
%PY% -m ragaudit.cli demo run          # the full scripted walkthrough
%PY% -m ragaudit.cli chat              # free-form interactive session
%PY% -m ragaudit.cli ask "..." --json  # one question
```

---

## What to show, in order

### 1. Most audit questions are not retrieval questions

> **How many high-severity findings are still open?**

Badge reads `structured`. Answer is exact, in **0.0s**, with no model involved
— it is a SQL count over every row.

The point: a count taken from the top-k retrieved chunks is unsound, because
retrieval never promises it saw everything. All eight questions in the
supplied benchmark are predicates like this one.

> **Are all findings closed?**

Answered by looking for a counterexample. One finding that is not closed
settles it, and the completeness of the scan is what makes a "yes" credible.

### 2. Open-ended questions get prose, not a verdict

> **What access control weaknesses were identified?**

Badge reads `narrative`. The answer is prose with citations. The previous
system's schema allowed only `Yes` / `No` / `Insufficient Evidence`, so this
question was structurally unanswerable.

### 3. It says when it does not know

> **Was the database server patched?**

> *"The report does not say whether the database server was patched. The
> evidence provided focuses on API security issues, error handling, and
> access control…"*

Nothing in the corpus covers this, and it says so instead of assembling
something plausible.

### 4. Every quote is checked before you see it

Watch for a `quote_not_in_chunk` flag. That is the system catching the model
attributing one finding's text to another finding's id, and discarding the
citation rather than displaying it.

This is worth dwelling on: the check is what makes the citations trustworthy,
and it fires on real output from this model.

### 5. Figures come from a join, not a search

> **Show me the proof of concept for the access control finding**

Figures are listed per finding. The extractor already binds each image to its
finding, so this is a lookup — no image search, no visual index.

They show as *referenced but not staged*, because the extraction pipeline
emits placeholder tokens (`[IMAGE_PAGE_13_FIG_1]`) and never produced the
image files. The system reports that honestly rather than hiding it.

### 6. It is a conversation

> **Tell me more about it**

Has no standalone meaning. Session state resolves the reference before
retrieval runs.

---

## The extraction gate

Worth showing on its own, because it found real defects in the supplied
corpus:

```bash
%PY% -m ragaudit.cli validate sample_data
```

| Report | Defect found |
|---|---|
| `2-report.json` | All 7 summary rows carry a **URL in the title field** — column misalignment |
| `4-report.json` | 16 summary rows for 15 findings; row 16 is a **table header parsed as data** |
| `4-report.json` | OBS-01–04 are titled `Initiation`, `Discovery`, `Validation`, `Reporting` — the **methodology table was parsed into the findings array** |
| `4-report.json` | All 15 findings are severity `High` — a constant-fill artefact |

Every count-based check passes on `2-report.json` while a column is
misaligned. That is why the gate checks shapes, not just totals.

---

## Numbers as measured

Eight scripted questions, this machine, 2026-10-14:

| | |
|---|---|
| Routing | 8/8 as expected |
| Mean latency | 5.0s |
| Structured answers | 0.0s (no model) |
| Truncated answers | 0 |
| Tests | 122 passing |

**CPU only.** Ollama dropped the GPU (`gfx1103` unsupported by its ROCm
build), so every latency here is a CPU figure and should improve on the
target GPU server.

---

## If something breaks

| Symptom | Cause | Fix |
|---|---|---|
| `llm offline` badge | Ollama not running | Start `ollama serve` |
| `index unavailable` | Nothing ingested | `ragaudit demo setup` |
| `truncated_generation` flag | Answer hit the token cap | Raise `RAGAUDIT_GENERATION__MAX_TOKENS` |
| Slow first question | Embedder loading from disk | Expected once per process start |
| Reranker slow on CPU | 0.6B cross-encoder over 60 candidates | `RAGAUDIT_RERANKER__ENABLED=false` for the demo |

## Switching to the production model

`qwen3:1.7b` is used here because it is responsive on CPU. For the GPU server:

```bash
ollama pull qwen3:8b
set RAGAUDIT_GENERATION__MODEL_NAME=qwen3:8b
set RAGAUDIT_EMBEDDING__DEVICE=cuda
set RAGAUDIT_RERANKER__DEVICE=cuda
```

Answer quality improves noticeably; the 1.7B model tends to list finding ids
where a larger one explains them.
