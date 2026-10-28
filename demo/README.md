# Mouse-AI live demo

A one-click demo kit for presenting Mouse-AI on Windows. It shows a
presentation page in the browser, a practice document in Word, the live overlay
and the capture agent, all running for real against a separate demo database.

## Run it

Double-click **`demo\Start-Demo.cmd`**. It will:

1. Prepare Python environments with `uv`. The first run downloads packages, including PySide6, and takes a few minutes.
2. Create `data\demo.db` with a week of sample sessions. Your real `data\mouse_ai.db` is never touched.
3. Open three console windows: **API** (port 8000), **Capture agent** and **Overlay**.
4. Open `demo\index.html` (the presentation and live dashboard) in your default browser.
5. Open a copy of `Mouse-AI-Practice.docx` in Word.

Double-click **`demo\Stop-Demo.cmd`** to close the API, agent and overlay. Word and
the browser stay open.

Options (run from PowerShell, e.g. `demo\Start-Demo.cmd -Fresh`):

| Option | Effect |
|---|---|
| `-Fresh` | Start with no sample history. Every click on screen is live. |
| `-Keep` | Keep the demo store from last time and add a new session. |
| `-NoOverlay` | Don't start the on-screen heatmap. |
| `-NoWord` | Don't open Word. |

Requires [uv](https://docs.astral.sh/uv/). Node.js is **not** needed: the
presentation page reads the API directly.

## Rehearse before presenting

Run through it once before the real presentation, so the first-run downloads
are out of the way and you know which monitor gets which window. A good layout:

- **Screen 1 (projected):** browser with the presentation page.
- **Screen 2:** Word, with the agent/API/overlay console windows minimized.

The run sheet is at the bottom of the presentation page (**Run sheet** in the
top navigation).

## Files

| File | Purpose |
|---|---|
| `Start-Demo.cmd` / `start-demo.ps1` | Launcher |
| `Stop-Demo.cmd` / `stop-demo.ps1` | Shut down everything the launcher started |
| `index.html` | Presentation + live dashboard (polls `http://localhost:8000`) |
| `seed_demo.py` | Creates/seeds `data\demo.db` |
| `Mouse-AI-Practice.docx` | Word task list for the live portion |
| `build_practice_doc.py` | Regenerates the .docx (`pip install python-docx`) |
