# Mouse-AI

Desktop-wide, local-first mouse-**click** analytics for general UI assist.

A native **Python agent** records every click across **both monitors**, buckets
each into a **unified grid zone** over the virtual desktop, and stores it in a
local SQLite database that **accumulates across sessions**. A **live overlay**
shows clicks as a real-time heatmap for presentations, a **dashboard** visualizes
usage, and you can export a **PDF report**.

> **Privacy:** all captured data stays on your machine. Nothing is uploaded.
> The click database is **git-ignored** and must never be committed (see below).

See [`Mouse-AI_Project_Scope.md`](../Mouse-AI_Project_Scope.md) for full scope.

## Repo layout

```
mouse-ai/
├── agent/         Python capture agent (run on WINDOWS host)
│   └── mouse_ai_agent/  capture · grid · virtual_desktop · store · config
├── overlay/       Python live heatmap overlay (run on WINDOWS host)
│   └── mouse_ai_overlay/  heatmap · main (PySide6, click-through window)
├── api/           FastAPI read bridge + PDF report (WSL/Docker ok)
│   └── mouse_ai_api/  main · queries · report
├── dashboard/     React + Vite dashboard (WSL/Docker ok)
│   └── src/        App · api · components/ZoneGrid
├── shared/        schema.sql (single source of truth for the DB)
├── data/          local SQLite store  ← git-ignored, never committed
├── config.example.json
└── docker-compose.yml
```

## Why two runtimes?

A browser (and a Docker container) can only see clicks inside its own window, so
**capture must be a native process on Windows**. The dashboard/API are ordinary
web services and can run under WSL2/Docker. They meet at the shared SQLite file.

## Quick start

### 1. Capture agent — on the **Windows** host
```powershell
cd mouse-ai\agent
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\config.example.json ..\config.json
python -m mouse_ai_agent.main        # Ctrl+C to stop
```

### 2. Live overlay (optional, for demos) — on **Windows**
```powershell
cd mouse-ai\overlay
pip install PySide6 pynput
# ensure the agent package is importable (same venv or PYTHONPATH=..\agent)
python -m mouse_ai_overlay.main      # Esc to quit
```

### 3. API + dashboard — WSL/Docker or Windows
```bash
# API
cd mouse-ai/api && pip install -r requirements.txt
MOUSE_AI_DB=../data/mouse_ai.db uvicorn mouse_ai_api.main:app --port 8000

# Dashboard (new terminal)
cd mouse-ai/dashboard && npm install && npm run dev
# open http://localhost:5173
```

Or: `docker compose up` (starts API + dashboard; agent/overlay stay on Windows).

## Configuration

Copy `config.example.json` → `config.json` (git-ignored) to set the grid size and
DB path. The API reads `MOUSE_AI_DB` (defaults to `data/mouse_ai.db`).

## Data & privacy

- The SQLite store under `data/` holds **all raw click events** plus derived
  zone totals. It is **git-ignored** — do not commit it.
- PDF reports contain **aggregated** zone/trend data only by default.
- Nothing leaves your machine unless you explicitly share an exported file.
