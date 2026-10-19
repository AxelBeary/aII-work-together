@echo off
rem Build the board shell (WebView2 + WinForms). ASCII only on purpose.
rem Requires: Windows .NET Framework csc.exe (always present) + the three
rem WebView2 files next to this script (see VENDOR.md).
setlocal
set HERE=%~dp0
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (
  echo Cannot find csc.exe
  exit /b 1
)
set OUT=%HERE%boardshell.exe

echo Building board shell...
"%CSC%" /nologo /target:winexe /codepage:65001 /optimize+ /out:"%OUT%" ^
  /r:System.dll /r:System.Core.dll /r:System.Drawing.dll ^
  /r:System.Windows.Forms.dll /r:System.Net.Http.dll ^
  /r:"%HERE%Microsoft.Web.WebView2.Core.dll" ^
  /r:"%HERE%Microsoft.Web.WebView2.WinForms.dll" ^
  "%HERE%BoardShell.cs"
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)
echo OK: %OUT%
