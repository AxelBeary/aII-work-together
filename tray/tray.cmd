@echo off
rem Build (if needed) and launch the tray app.
setlocal
set HERE=%~dp0
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
set EXE=%HERE%boardtray.exe

if not exist "%EXE%" goto build
if "%HERE%BoardTray.cs"=="" goto run
for %%A in ("%HERE%BoardTray.cs") do for %%B in ("%EXE%") do if %%~tA GTR %%~tB goto build
goto run

:build
echo Building tray app...
"%CSC%" /nologo /target:winexe /codepage:65001 /out:"%EXE%" /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Net.Http.dll "%HERE%BoardTray.cs"
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

:run
start "" "%EXE%"
