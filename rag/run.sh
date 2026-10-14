#!/usr/bin/env bash
# ---------------------------------------------------------------------
#  Audit Report Assistant - one-command start
#
#    ./run.sh            start everything and open the console
#    ./run.sh demo       run the scripted walkthrough in the terminal
#    ./run.sh chat       interactive session in the terminal
#    ./run.sh check      report what is ready, change nothing
#    ./run.sh ingest     re-ingest the corpus
#    ./run.sh test       run the test suite
#
#  Everything runs locally. Nothing leaves this machine.
# ---------------------------------------------------------------------
set -uo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8077}"
MODEL="${MODEL:-qwen3:1.7b}"

# The reranker is a 0.6B cross-encoder scoring 60 candidates, which is slow
# on CPU. Off by default so the demo stays responsive; set to true on the
# GPU server.
export RAGAUDIT_GENERATION__MODEL_NAME="$MODEL"
export RAGAUDIT_RERANKER__ENABLED="${RAGAUDIT_RERANKER__ENABLED:-false}"
export RAGAUDIT_LOG_JSON="${RAGAUDIT_LOG_JSON:-false}"

printf '\n  Audit Report Assistant\n  ======================\n\n'

die() { printf '  [X] %s\n\n' "$1" >&2; exit 1; }

# --- 1. locate a Python that has the dependencies --------------------
# Not simply the first python on PATH: this project needs the interpreter
# the packages were installed into, which may not be the active venv.
PY=""
for candidate in \
  "$LOCALAPPDATA/Programs/Python/Python310/python.exe" \
  "$LOCALAPPDATA/Programs/Python/Python311/python.exe" \
  "$LOCALAPPDATA/Programs/Python/Python312/python.exe" \
  python3 python
do
  [ -n "$PY" ] && break
  command -v "$candidate" >/dev/null 2>&1 || [ -x "$candidate" ] || continue
  if "$candidate" -c "import fastapi, numpy, pydantic" >/dev/null 2>&1; then
    PY="$candidate"
  fi
done
[ -n "$PY" ] || die $'No Python found with the dependencies installed.\n      Install them with:  python -m pip install -e ".[models]"'
printf '  [ok] python    %s\n' "$PY"

# --- 2. make sure the model server is up -----------------------------
OLLAMA_BIN="${OLLAMA_BIN:-$LOCALAPPDATA/Programs/Ollama/ollama.exe}"
command -v ollama >/dev/null 2>&1 && OLLAMA_BIN="$(command -v ollama)"

if ! curl -s -o /dev/null --max-time 3 http://localhost:11434/api/tags; then
  [ -x "$OLLAMA_BIN" ] || die "Ollama not found. Install from https://ollama.com"
  printf '  [..] starting Ollama...\n'
  "$OLLAMA_BIN" serve >/tmp/ollama.log 2>&1 &
  # Poll rather than sleeping a fixed time: it binds in a second on a warm
  # machine and much slower on a cold one.
  for _ in $(seq 1 20); do
    curl -s -o /dev/null --max-time 2 http://localhost:11434/api/tags && break
    sleep 1
  done
fi
curl -s -o /dev/null --max-time 5 http://localhost:11434/api/tags \
  || die "Ollama did not come up on port 11434. See /tmp/ollama.log"
printf '  [ok] ollama    http://localhost:11434\n'

# --- 3. make sure the model is pulled --------------------------------
if ! curl -s --max-time 5 http://localhost:11434/api/tags | grep -q "$MODEL"; then
  printf '  [..] pulling %s - first run only, about 1.4 GB\n' "$MODEL"
  "$OLLAMA_BIN" pull "$MODEL" || die "Could not pull $MODEL"
fi
printf '  [ok] model     %s\n' "$MODEL"

# --- 4. make sure something is indexed -------------------------------
if [ ! -f var/index/ids.json ]; then
  printf '  [..] no index yet - ingesting sample_data, this takes a minute\n'
  "$PY" -m ragaudit.cli demo setup || die "Ingest failed."
fi
printf '  [ok] index     var/index\n'

# --- 5. dispatch ------------------------------------------------------
case "${1:-serve}" in
  check)
    echo
    "$PY" -m ragaudit.cli demo check
    echo
    exec "$PY" -m ragaudit.cli status
    ;;
  demo)
    printf '\n  Running the scripted walkthrough.\n\n'
    exec "$PY" -m ragaudit.cli demo run --transcript var/demo_run.json
    ;;
  chat)
    echo
    exec "$PY" -m ragaudit.cli chat
    ;;
  ingest)
    echo
    exec "$PY" -m ragaudit.cli ingest sample_data --force --verbose
    ;;
  test)
    echo
    exec "$PY" -m pytest tests -q
    ;;
  serve|*)
    printf '\n  Console:  http://localhost:%s\n  Stop:     Ctrl-C\n\n' "$PORT"
    exec "$PY" -m ragaudit.cli serve --port "$PORT"
    ;;
esac
