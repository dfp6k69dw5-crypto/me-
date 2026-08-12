@echo off
setlocal
set "HTML=%~dp0langlands-fluid-desktop.html"
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%LocalAppData%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" (
  echo Microsoft Edge was not found.
  echo Open langlands-fluid-desktop.html manually in a browser instead.
  pause
  exit /b 1
)
start "" "%EDGE%" --kiosk "%HTML%" --edge-kiosk-type=fullscreen --no-first-run --kiosk-idle-timeout-minutes=0
endlocal
