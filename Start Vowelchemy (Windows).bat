@echo off
rem Double-click me to set up and start Vowelchemy - no typing needed.
rem
rem First run: creates a private Python environment in this folder (.venv-app)
rem and installs Vowelchemy into it (a few minutes, needs internet).
rem Every run after that: starts quickly.
rem
rem If Windows SmartScreen warns about an unrecognized file, click
rem "More info" and then "Run anyway".
setlocal
cd /d "%~dp0"

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python 3 was not found.
  echo Install it from https://www.python.org/downloads/ - on the first installer
  echo screen, tick "Add python.exe to PATH" - then double-click me again.
  pause
  exit /b 1
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
  echo Your Python 3 is too old - Vowelchemy needs 3.9 or newer.
  echo Install the current version from https://www.python.org/downloads/ and try again.
  pause
  exit /b 1
)

rem Install on the first run, and re-install whenever the requirements change.
rem The install is *editable*, so pulling new code takes effect on the next
rem launch - otherwise this folder would keep running the version that was
rem installed the very first time.
set "STAMP=.venv-app\.vowelchemy-stamp"
set "WANT="
for /f "skip=1 delims=" %%h in ('certutil -hashfile pyproject.toml MD5 2^>nul') do (
  if not defined WANT set "WANT=%%h"
)
set "WANT=%WANT: =%"
set "HAVE="
if exist "%STAMP%" set /p HAVE=<"%STAMP%"

set "NEED_INSTALL="
if not exist ".venv-app\Scripts\vowelchemy.exe" (
  echo First-time setup: installing Vowelchemy into a private environment.
  echo This takes a few minutes and needs an internet connection...
  %PY% -m venv .venv-app
  if errorlevel 1 (
    echo Could not create the environment - ask for help and show this window.
    pause
    exit /b 1
  )
  set "NEED_INSTALL=1"
) else if not "%WANT%"=="%HAVE%" (
  echo Vowelchemy's requirements changed - updating ^(this may take a minute^)...
  set "NEED_INSTALL=1"
)

if defined NEED_INSTALL (
  ".venv-app\Scripts\python" -m pip install --upgrade pip >nul 2>&1
  ".venv-app\Scripts\pip" install -e .
  if errorlevel 1 (
    echo Installing Vowelchemy failed. Check your internet connection and try again.
    echo To retry setup from scratch, delete the .venv-app folder first.
    pause
    exit /b 1
  )
  >"%STAMP%" echo %WANT%
  echo Setup complete.
)

echo.
echo Starting Vowelchemy - your browser will open by itself in a moment.
echo Keep this window open while you work; close it to stop Vowelchemy.
echo.
".venv-app\Scripts\vowelchemy" app
pause
