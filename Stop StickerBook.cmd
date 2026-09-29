@echo off
setlocal
title Stop StickerBook
wsl.exe --cd "%~dp0" bash runtime/stop.sh
if errorlevel 1 (
  echo StickerBook shutdown reported an error.
  pause
  exit /b 1
)
