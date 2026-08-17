@echo off
title Stop GlazedMind
cd /d "%~dp0"
docker compose stop
if errorlevel 1 (
  echo.
  echo Docker could not stop GlazedMind.
  pause
  exit /b 1
)
echo.
echo GlazedMind has stopped safely. Your local data was preserved.
pause
