@echo off
setlocal

echo.
echo ============================================
echo  Research Reader - Setup
echo ============================================
echo.

:: ── Find a compatible Python (3.9 / 3.10 / 3.11) ────────────────
:: Coqui TTS does not support Python 3.12+ yet.
:: We use the Windows py launcher to pick the right version.

set PYTHON_EXE=

py -3.11 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_EXE=py -3.11 & goto :found )

py -3.10 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_EXE=py -3.10 & goto :found )

py -3.9 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_EXE=py -3.9  & goto :found )

echo ERROR: Coqui TTS requires Python 3.9, 3.10, or 3.11.
echo        Your installed Python is too new (3.12+ not yet supported).
echo.
echo  Install Python 3.11 from:
echo  https://www.python.org/downloads/release/python-31110/
echo.
echo  Make sure to tick "Add to PATH" during install.
echo  Then re-run this script.
echo.
pause
exit /b 1

:found
for /f "tokens=2" %%v in ('%PYTHON_EXE% --version 2^>^&1') do set PY_VER=%%v
echo  Found Python %PY_VER% — using %PYTHON_EXE%
echo.

:: ── Virtual environment ──────────────────────────────────────────
echo [1/4] Creating virtual environment...
%PYTHON_EXE% -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause & exit /b 1
)
call venv\Scripts\activate.bat

:: ── PyTorch ──────────────────────────────────────────────────────
echo.
echo [2/4] Installing PyTorch...
echo.
:: Coqui TTS requires torch/torchaudio 2.5.x — both 2.6 releases have
:: breaking changes (weights_only default + torchcodec audio backend).
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo      No NVIDIA GPU detected - installing CPU version.
    echo      Audio will be generated in batch mode before listening.
    pip install "torch==2.5.1" "torchaudio==2.5.1" --index-url https://download.pytorch.org/whl/cpu --quiet
) else (
    echo      NVIDIA GPU detected - installing CUDA 12.1 version.
    pip install "torch==2.5.1" "torchaudio==2.5.1" --index-url https://download.pytorch.org/whl/cu121 --quiet
)
if errorlevel 1 (
    echo ERROR: PyTorch install failed. Check your internet connection.
    pause & exit /b 1
)

:: ── Dependencies ─────────────────────────────────────────────────
echo.
echo [3/4] Installing dependencies...

:: Install spaCy first at a pinned version to prevent pip from pulling
:: spaCy 3.8+ which requires thinc>=8.3.12 (a version that does not exist).
pip install "spacy>=3.7.0,<3.8.0"
if errorlevel 1 (
    echo ERROR: spaCy install failed. See output above.
    pause & exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency install failed. See output above.
    pause & exit /b 1
)

:: ── Data directories ─────────────────────────────────────────────
echo.
echo [4/4] Creating data directories...
mkdir data\papers data\voices data\audio 2>nul

echo.
echo ============================================
echo  Setup complete!
echo.
echo  IMPORTANT: First time you click "Prepare"
echo  or test a voice, the XTTS v2 model (~2 GB)
echo  will download automatically. Let it finish.
echo.
echo  Run 'run.bat' to start the server.
echo ============================================
echo.
pause
