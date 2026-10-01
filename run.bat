@echo off
cd /d "%~dp0"
if not exist .venv (
  py -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install -r requirements.txt
)
echo Open http://127.0.0.1:5001 in your browser. Press Ctrl+C to stop.
.venv\Scripts\python -m flask --app app run --port 5001
