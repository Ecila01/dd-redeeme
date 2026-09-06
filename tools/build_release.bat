@echo off
rem ============================================================
rem  Build DD RedeeMe (v0.1.0) release artifacts:
rem    1. portable single exe   -> release\v0.1.0\DD RedeeMe.exe
rem    2. Inno Setup installer  -> release\v0.1.0\DD RedeeMe_0.1.0_x64-setup.exe
rem  Requires: project .venv (PySide6 installed). Inno Setup 6 optional
rem  (missing it only skips step 5).
rem ============================================================
setlocal
cd /d "%~dp0.."
set "PY=.venv\Scripts\python.exe"
set "VER=0.1.0"
set "REL=%~dp0..\release\v%VER%"

if not exist "%PY%" (
  echo [ERROR] .venv not found. Create it first:
  echo     python -m venv .venv
  echo     .venv\Scripts\python -m pip install PySide6 requests
  exit /b 1
)

echo [1/5] Installing build deps (pyinstaller, pillow)...
"%PY%" -m pip install --quiet --disable-pip-version-check pyinstaller pillow || goto :fail

echo [2/5] Generating assets\icon.ico and assets\fish_alpha.png ...
"%PY%" tools\prep_assets.py || goto :fail

echo [3/5] PyInstaller onefile build (takes 1-3 minutes)...
"%PY%" -m PyInstaller --noconfirm --clean DDRedeeMe.spec || goto :fail

echo [4/5] Assembling release dir...
if not exist "%REL%" mkdir "%REL%"
copy /y "dist\DD RedeeMe.exe" "%REL%\DD RedeeMe.exe" || goto :fail

echo [5/5] Building installer with Inno Setup...
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo [WARN] Inno Setup 6 not found - installer SKIPPED.
  echo        Install it from https://jrsoftware.org/isdl.php then re-run this script.
  echo.
  echo Portable build finished: %REL%\DD RedeeMe.exe
  exit /b 0
)
"%ISCC%" packaging\dd-redeeme.iss || goto :fail

echo.
echo Done. Artifacts in %REL%:
dir /b "%REL%"
endlocal
exit /b 0

:fail
echo.
echo [FAILED] Build aborted - see messages above.
endlocal
exit /b 1
