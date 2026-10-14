@echo off
REM ---------------------------------------------------------------------
REM  Audit Report Assistant - one-command start
REM
REM    run.bat            start everything and open the console
REM    run.bat demo       run the scripted walkthrough in the terminal
REM    run.bat chat       interactive session in the terminal
REM    run.bat check      report what is ready, change nothing
REM    run.bat ingest     re-ingest the corpus
REM    run.bat test       run the test suite
REM
REM  Everything runs locally. Nothing leaves this machine.
REM ---------------------------------------------------------------------
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PORT=8077"
set "MODEL=qwen3:1.7b"

REM --- generation settings -------------------------------------------
REM The reranker is a 0.6B cross-encoder scoring 60 candidates, which is
REM slow on CPU. Off by default so the demo stays responsive; set to
REM true on the GPU server.
set "RAGAUDIT_GENERATION__MODEL_NAME=%MODEL%"
set "RAGAUDIT_RERANKER__ENABLED=false"
set "RAGAUDIT_LOG_JSON=false"

echo.
echo  Audit Report Assistant
echo  ======================
echo.

REM --- 1. locate a Python that has the dependencies ------------------
REM Not the first python on PATH: this project needs the interpreter the
REM packages were installed into, which may not be the active venv.
set "PY="
for %%P in (
  "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) do (
  if not defined PY if exist %%P (
    %%P -c "import fastapi, numpy, pydantic" >nul 2>&1
    if !errorlevel! equ 0 set "PY=%%~P"
  )
)
if not defined PY (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PY (
      "%%P" -c "import fastapi, numpy, pydantic" >nul 2>&1
      if !errorlevel! equ 0 set "PY=%%P"
    )
  )
)
if not defined PY (
  echo  [X] No Python found with the dependencies installed.
  echo.
  echo      Install them with:
  echo        python -m pip install -e ".[models]"
  echo.
  exit /b 1
)
echo  [ok] python    %PY%

REM --- 2. make sure the model server is up ---------------------------
set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
curl -s -o nul --max-time 3 http://localhost:11434/api/tags 2>nul
if errorlevel 1 (
  if not exist "%OLLAMA%" (
    echo  [X] Ollama is not installed at %OLLAMA%
    echo      Install from https://ollama.com, then run this again.
    exit /b 1
  )
  echo  [..] starting Ollama...
  start "" /min "%OLLAMA%" serve
  REM Give it time to bind the port before the readiness probe.
  timeout /t 8 /nobreak >nul
)
curl -s -o nul --max-time 5 http://localhost:11434/api/tags 2>nul
if errorlevel 1 (
  echo  [X] Ollama did not come up on port 11434.
  exit /b 1
)
echo  [ok] ollama    http://localhost:11434

REM --- 3. make sure the model is pulled ------------------------------
curl -s --max-time 5 http://localhost:11434/api/tags | findstr /C:"%MODEL%" >nul
if errorlevel 1 (
  echo  [..] pulling %MODEL% - first run only, about 1.4 GB
  "%OLLAMA%" pull %MODEL%
  if errorlevel 1 (
    echo  [X] Could not pull %MODEL%. Check the network and retry.
    exit /b 1
  )
)
echo  [ok] model     %MODEL%

REM --- 4. make sure something is indexed -----------------------------
if not exist "var\index\ids.json" (
  echo  [..] no index yet - ingesting sample_data, this takes a minute
  "%PY%" -m ragaudit.cli demo setup
  if errorlevel 1 (
    echo  [X] Ingest failed.
    exit /b 1
  )
)
echo  [ok] index     var\index

REM --- 5. dispatch ----------------------------------------------------
if /i "%~1"=="check"  goto :check
if /i "%~1"=="demo"   goto :demo
if /i "%~1"=="chat"   goto :chat
if /i "%~1"=="ingest" goto :ingest
if /i "%~1"=="test"   goto :test
goto :serve

:check
echo.
"%PY%" -m ragaudit.cli demo check
echo.
"%PY%" -m ragaudit.cli status
exit /b 0

:demo
echo.
echo  Running the scripted walkthrough.
echo.
"%PY%" -m ragaudit.cli demo run --transcript var\demo_run.json
exit /b %errorlevel%

:chat
echo.
"%PY%" -m ragaudit.cli chat
exit /b %errorlevel%

:ingest
echo.
"%PY%" -m ragaudit.cli ingest sample_data --force --verbose
exit /b %errorlevel%

:test
echo.
"%PY%" -m pytest tests -q
exit /b %errorlevel%

:serve
echo.
echo  Console:  http://localhost:%PORT%
echo  Stop:     Ctrl-C
echo.
REM Open the browser shortly after the server starts binding.
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:%PORT%"
"%PY%" -m ragaudit.cli serve --port %PORT%
exit /b %errorlevel%
