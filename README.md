# Mouse-AI

Desktop-wide, local-first mouse-**click** analytics for general UI assist.

**Start here:** [Windows test environment guide](WINDOWS_TEST_ENVIRONMENT.md)
includes a fresh Python virtual environment, dependency installation, a
two-monitor test, pointer return, and optional analytics/dashboard setup.

A native **Python agent** records every click across **both monitors**, buckets
each into a **unified grid zone** over the virtual desktop, and stores it in a
local SQLite database that **accumulates across sessions**. A **live overlay**
shows clicks as a real-time heatmap for presentations, a **dashboard** visualizes
usage, and you can export a **PDF report**.

> **Privacy:** all captured data stays on your machine. Nothing is uploaded.
> The click database is **git-ignored** and must never be committed (see below).

For the bundled presentation and live demo, see [demo/README.md](demo/README.md).

## Repo layout

```
mouse-ai/
├── agent/         Python capture agent (run on WINDOWS host)
│   └── mouse_ai_agent/  capture · grid · virtual_desktop · store · config
├── overlay/       Python live heatmap overlay (run on WINDOWS host)
│   └── mouse_ai_overlay/  heatmap · main (PySide6, click-through windows)
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
pip install -r requirements.txt
python -m mouse_ai_overlay.main      # Esc anywhere or Ctrl+C to quit
```

The overlay opens **one transparent, click-through window per monitor** (two
windows on a dual-monitor setup). Clicks pass to the app underneath, and the
overlay does not take keyboard focus. Both windows share one click listener and
the same fading heatmap. Monitors to the left or above the primary display and
different Windows display scales are supported. Windows follow changes to the
monitor layout, including connecting or disconnecting a display.

The overlay runs standalone; it does not need the capture agent running or its
package on `PYTHONPATH`. Start the agent separately when you also want to record
clicks to the database.

**Return to the busiest spot:** a fast double left-click moves the pointer to
the most-clicked area learned during the **current overlay session**. Nearby
clicks are grouped into 64-pixel areas; the destination is the average click
position in the busiest area. That history remains after the glows fade and
resets when you restart the overlay.

To try it, make several single clicks in one spot, with a pause between clicks.
Move elsewhere and double left-click within **300 milliseconds**, keeping the
two clicks within **8 pixels**. The pointer returns after you release the second
click. The two trigger clicks do not contribute to the hotspot counts. The
original double-click still reaches the underlying app; the overlay moves the
pointer without generating a click at the destination.

To use only the visual overlay, disable pointer return:
```powershell
python -m mouse_ai_overlay.main --no-jump
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

The Compose file is an architecture scaffold; container Dockerfiles are not
included. Use the Windows guide above for a complete setup.

## Configuration

Copy `config.example.json` → `config.json` (git-ignored) to set the grid size and
DB path. The API reads `MOUSE_AI_DB` (defaults to `data/mouse_ai.db`).

## Data & privacy

- The SQLite store under `data/` holds **all raw click events** plus derived
  zone totals. It is **git-ignored** — do not commit it.
- PDF reports contain **aggregated** zone/trend data only by default.
- Nothing leaves your machine unless you explicitly share an exported file.
