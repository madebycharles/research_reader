@echo off
echo === Research Reader — Local setup (playback only) ===
echo Installs serving dependencies only. No TTS, no torch, no spaCy.
echo TTS generation is handled by the RunPod worker.
echo.

:: Find Python — prefer 3.11 but any 3.9+ works for local serving
py -3.11 --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=py -3.11
    goto :found_python
)
py -3.10 --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=py -3.10
    goto :found_python
)
python --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=python
    goto :found_python
)
echo ERROR: Python not found. Install Python from python.org.
pause
exit /b 1

:found_python
echo Python: %PYTHON%
echo.

echo [1/3] Creating virtual environment...
%PYTHON% -m venv venv
call venv\Scripts\activate.bat

echo [2/3] Installing dependencies (~200 MB)...
python -m pip install --upgrade pip --quiet
pip install -r requirements_local.txt --quiet

echo [3/3] Creating data directories...
if not exist data\papers  mkdir data\papers
if not exist data\voices  mkdir data\voices
if not exist data\audio   mkdir data\audio
if not exist data\.gitkeep echo. > data\.gitkeep

echo.
echo === Setup complete ===
echo.
echo To prepare papers via RunPod, set before running:
echo   set RUNPOD_WORKER_URL=https://^<pod-id^>-8000.proxy.runpod.net
echo.
echo Then start the server:
echo   run.bat
echo.
pause
