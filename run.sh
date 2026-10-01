cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi
echo "Open http://127.0.0.1:5001 in your browser. Press Ctrl+C to stop."
.venv/bin/python -m flask --app app run --port 5001
