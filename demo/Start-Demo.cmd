@echo off
REM Double-click to launch the Mouse-AI live demo. Extra options: -Fresh, -Keep, -NoOverlay, -NoWord
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-demo.ps1" %*
pause
