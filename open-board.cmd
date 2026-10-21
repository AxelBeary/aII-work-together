@echo off
rem Open the board.
rem   1st choice: the native shell (WebView2 window, no browser chrome)
rem   fallback   : tray app + default browser (if the shell was not built)
rem Kept ASCII-only on purpose: .cmd with non-ASCII breaks under some code pages.
setlocal
set HERE=%~dp0
rem A stale backend on 8777 makes the new UI talk to an OLD API (E-31).
rem Say it out loud instead of opening a window that shows "not found".
netstat -ano | findstr /C:":8777" | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [board] Port 8777 is already in use.
  echo [board] If that is an old backend, the new UI will talk to the old API.
  echo [board] Find the owner : netstat -ano ^| findstr :8777
  echo [board] Then stop that PID, or set ABOARD_PORT to another port.
  timeout /t 8 >nul
)
if exist "%HERE%shell\boardshell.exe" (
  start "" "%HERE%shell\boardshell.exe"
  exit /b 0
)
start "" "%HERE%tray\tray.cmd"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8777/
