@echo off
title GlazedMind Launcher
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-glazedmind.ps1"
if errorlevel 1 (
  echo.
  echo GlazedMind could not be started. Review the message above.
  pause
)
