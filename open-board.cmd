@echo off
rem Open the board: start the tray app (it starts the backend), then open the page.
rem Kept ASCII-only on purpose: .cmd with non-ASCII breaks under some code pages.
setlocal
set HERE=%~dp0
start "" "%HERE%tray\tray.cmd"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8777/
