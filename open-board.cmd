@echo off
rem Open the board.
rem   1st choice: the native shell (WebView2 window, no browser chrome)
rem   fallback   : tray app + default browser (if the shell was not built)
rem Kept ASCII-only on purpose: .cmd with non-ASCII breaks under some code pages.
setlocal
set HERE=%~dp0
if exist "%HERE%shell\boardshell.exe" (
  start "" "%HERE%shell\boardshell.exe"
  exit /b 0
)
start "" "%HERE%tray\tray.cmd"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8777/
