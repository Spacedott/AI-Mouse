@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-demo.ps1"
timeout /t 3 >nul
