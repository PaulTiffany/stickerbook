@echo off
setlocal
title StickerBook
echo Starting powered StickerBook...
wsl.exe --cd "%~dp0" bash runtime/start.sh
if errorlevel 1 (
  echo.
  echo StickerBook did not start. Review the message above.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8756/"
echo.
echo StickerBook is ready. This window can be closed.
