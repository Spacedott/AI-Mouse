# Mouse-AI: Windows test environment

This guide runs Mouse-AI from a fresh copy of the GitHub repository. It covers
the Python virtual environment, the two-monitor heatmap, the double-click
pointer-return feature, and the optional click recording and dashboard.

## What the project does

- **Live overlay:** a transparent, always-on-top, click-through window on each
  monitor. Clicks make orange glows that fade after about three seconds.
- **Pointer return:** a fast double left-click returns the pointer to the
  busiest area learned during the current overlay session. That history stays
  after the glows fade and resets when you restart the overlay.
- **Capture agent:** saves click events to a local SQLite database. Stored
  history accumulates across agent sessions.
- **API and dashboard:** display zone totals and sessions and export PDF reports.

The overlay and capture agent run directly on Windows. Their global Windows
input hooks should not be run inside WSL or a Docker container. WSL and Docker
are not required for the Windows setup below.

## 1. Prerequisites

- Windows 11; the live test was performed on Windows 11 ARM64 with two monitors
  at 150% and 100% display scaling.
- **Python 3.12** with `venv` and `pip`. Use Windows ARM64 Python on an ARM64
  computer and x64 Python on an Intel/AMD x64 computer.
- [Git for Windows](https://git-scm.com/downloads/win), or download the repository
  as a ZIP and extract it.
- Internet access for the initial dependency installation.
- Two displays in **Extend** mode to reproduce the two-window test. The overlay
  also works with one display.

Python can be installed using the [official Windows installation instructions](https://docs.python.org/3/using/windows.html).
The commands below use **Windows PowerShell**, opened as your normal Windows
user. Check that your Python installation works:

```powershell
python --version
python -c "import platform, struct; print(platform.machine(), struct.calcsize('P') * 8)"
```

The version should be Python 3.12.x. The architecture should say `ARM64` on an
ARM computer or `AMD64` on an x64 computer, with `64` bits. If the `python`
command opens the Microsoft Store, install Python and reopen PowerShell.

If you already use [uv](https://docs.astral.sh/uv/), it can obtain a matching
Python runtime. Choose **one** of these commands for your computer:

Windows ARM64:

```powershell
uv python install cpython-3.12-windows-aarch64-none
$testPython = uv python find --managed-python cpython-3.12-windows-aarch64-none
```

Windows x64:

```powershell
uv python install cpython-3.12-windows-x86_64-none
$testPython = uv python find --managed-python cpython-3.12-windows-x86_64-none
```

## 2. Get the project

Use a short project path. Qt contains some deeply nested package files, which
can exceed the Windows path limit when the project is extracted into several
nested folders. For example, clone into a `src` folder under your Windows user:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\src" | Out-Null
Set-Location "$env:USERPROFILE\src"
git clone https://github.com/Spacedott/AI-Mouse.git
cd AI-Mouse
```

For a ZIP download, use GitHub's **Code > Download ZIP**, extract it, and open
PowerShell in the extracted project folder. The folder containing `README.md`,
`agent`, `overlay`, and `api` is the **project root** throughout this guide.

## 3. Create a Python virtual environment

From the project root, create a fresh virtual environment:

```powershell
python -m venv .venv
```

If you chose the uv runtime above, use this command instead:

```powershell
& $testPython -m venv .venv
```

Install the project's Python dependencies into that environment:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The root `requirements.txt` installs the agent, overlay, and API requirements.
The component files pin the direct dependency versions used for this setup.

**Activation is optional.** To activate the environment in the current shell:

```powershell
.\.venv\Scripts\Activate.ps1
```

When activated, `python` and `pip` refer to that environment. Use `deactivate`
to leave it. If PowerShell blocks activation scripts, continue with the explicit
`.venv\Scripts\python.exe` commands in this guide; activation is not needed.
Recreate `.venv` on each computer instead of copying it between machines.

## 4. Test the overlay and pointer return

From the project root:

```powershell
cd overlay
..\.venv\Scripts\python.exe -m mouse_ai_overlay.main
```

The terminal should report the number of detected monitors. The overlay windows
have transparent backgrounds, no borders, and no taskbar buttons. Your normal
desktop remains visible underneath them.

1. Click on both monitors. Each click should create an orange glow at the click
   location, and the underlying application should receive the click.
2. Check that the glow fades in about three seconds.
3. Make five single clicks in the same empty desktop area, pausing about half a
   second between clicks. This teaches the overlay a busy location.
4. Move the pointer elsewhere and double left-click quickly, within **300 ms**,
   keeping the two taps within **8 physical pixels**.
5. After the second click is released, the pointer should return to the learned
   area. Repeat with a destination on the other monitor.

Nearby clicks are grouped into 64-pixel areas. The destination is the average
click position in the most-clicked area; ties favor the first learned area.
The two gesture taps are excluded from the pointer-return counts. The original
double-click still reaches the underlying application; no click is generated
at the return destination. Holds and drags do not trigger the return.

To run the visual overlay with pointer return disabled:

```powershell
..\.venv\Scripts\python.exe -m mouse_ai_overlay.main --no-jump
```

Press **Esc** anywhere, or **Ctrl+C** in its terminal, to stop the overlay.

## 5. Optional: record clicks and view the live demo page

The overlay runs by itself. To test saved analytics too, start the capture
agent and API in separate PowerShell windows. The commands below use
`data\test.db`, keeping test clicks separate from the default `data\mouse_ai.db`.

### Terminal A: capture agent

Open PowerShell in the project root, then run:

```powershell
$env:MOUSE_AI_DB = Join-Path (Get-Location) "data\test.db"
cd agent
..\.venv\Scripts\python.exe -m mouse_ai_agent.main
```

The agent creates the database and schema and starts a recording session.
Leave this terminal running and make a few clicks on both monitors.

### Terminal B: API

Open another PowerShell window in the project root:

```powershell
$env:MOUSE_AI_DB = Join-Path (Get-Location) "data\test.db"
.\.venv\Scripts\python.exe -m uvicorn mouse_ai_api.main:app --app-dir api --host 127.0.0.1 --port 8000
```

Open [the API documentation](http://127.0.0.1:8000/docs). The `/api/zones` and
`/api/sessions` endpoints should return your test data. The database paths in
terminals A and B must match.

### Browser: bundled demo page

From a third PowerShell window in the project root:

```powershell
Start-Process .\demo\index.html
```

The bundled presentation includes a live dashboard that reads the API on port
8000. It shows click totals, heat by zone, sessions, and report links. **Node.js
is not required for this page.** Its totals should change as the agent records
clicks. For a PDF, open [the report endpoint](http://127.0.0.1:8000/api/report.pdf).

The dashboard uses saved agent data; pointer return uses only the current
overlay session. Restarting the overlay clears its learned return locations
while leaving recorded database history intact.

Stop the capture agent and API with **Ctrl+C** in their respective terminals.
Esc stops only the overlay. The browser and saved database remain available.

## 6. Optional: launch the presentation kit

If uv is installed, the repository also includes a launcher that prepares
component environments, seeds made-up history into **`data\demo.db`**, and
starts the API, capture agent, overlay, and presentation page:

```powershell
.\demo\Start-Demo.cmd -NoWord
```

Stop any manually started API on port 8000 and any existing overlay before
using the launcher. Use `-Fresh` for an empty demo database or `-Keep` to retain
the previous demo database. Without `-NoWord`, the launcher also opens a copy of
the included practice document if an application for `.docx` files is installed.
It does not modify the checked-in practice document or `data\mouse_ai.db`.

Stop the launcher-managed processes with:

```powershell
.\demo\Stop-Demo.cmd
```

See [the demo README](demo/README.md) for its presentation layout and options.

## 7. Optional: run the React dashboard

The separate React dashboard needs [Node.js LTS](https://nodejs.org/en/download).
Keep the capture agent and API from section 5 running. In a new PowerShell
window at the project root:

```powershell
cd dashboard
npm.cmd ci
npm.cmd run dev
```

Open [localhost:5173](http://localhost:5173). You should see **Mouse-AI
Dashboard**, a total-click count, zone heat grid, sessions table, and PDF links.
This dashboard fetches data when the page loads; refresh it for updated counts.
`npm.cmd` works in PowerShell without relying on the `npm.ps1` wrapper.

## 8. Run automated checks

From the project root, with the Python dependencies installed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

These tests cover geometry, click storage, capture threading, pointer-return
gestures, and Qt rendering on simulated monitors. Input hooks and cursor writes
are mocked in the automated tests, so the suite does not click applications or
move your pointer. Use the manual checks in section 4 to verify the real desktop.

For the React dashboard:

```powershell
cd dashboard
npm.cmd ci
npm.cmd run build
```

## Troubleshooting

| Symptom | Check |
|---|---|
| `python` is missing or opens the Store | Install Python, reopen PowerShell, or use the uv runtime commands in section 1. |
| Virtual environment activation is blocked | Run `.venv\Scripts\python.exe` directly; activation is optional. |
| A copied `.venv` fails to start | Create a new environment on the target computer and reinstall requirements. |
| pip reports a missing deeply nested PySide6 file / Windows long-path error | Move the project to a shorter path, such as `C:\src\AI-Mouse`, recreate `.venv`, and install again. If you already use uv, `uv pip install --python .venv\Scripts\python.exe -r requirements.txt` is another installation route. |
| Access is denied when creating or running the environment | Use the standard `python -m venv` command in a writable folder. A virtual environment can also live in `%LOCALAPPDATA%`; use its Python executable in the launch commands. |
| No glows or only one monitor works | Run the overlay on Windows, use Extend display mode, check its terminal for errors, and stop duplicate overlay processes. |
| Double-click does not return | Teach a location with spaced single clicks first; use two quick left clicks in the same spot and release both clicks. Check that `--no-jump` was not used. |
| API reports a missing database | Start the agent first and use the same absolute `MOUSE_AI_DB` path in both terminals. |
| Counts do not increase | Keep the agent running; check its terminal. The overlay by itself does not record to SQLite. |
| Port 8000 is already in use | Stop the previous API before starting another instance. |
| React dashboard counts are stale | Refresh the browser page. |

## Files to share on GitHub

Commit the source code, requirement files, tests, demo assets, this guide, and
the dashboard lockfile. Local environments and captured data are excluded by
`.gitignore`: `.venv`, `node_modules`, `data`, database files, `config.json`, and
exported PDFs. Everyone creates their own virtual environment and test database.

The repository does not include captured click history or your local test
environments. All captured data stays on the computer running Mouse-AI.

## References

- [Python virtual environments](https://docs.python.org/3/library/venv.html)
- [Python on Windows](https://docs.python.org/3/using/windows.html)
- [uv Python installation](https://docs.astral.sh/uv/guides/install-python/)
- [GitHub: download a repository](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-files-from-github)
