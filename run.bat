@echo off
call venv\Scripts\activate.bat

echo.
echo ============================================
echo  Research Reader
echo  http://localhost:8000
echo.
echo  From phone (same network or Tailscale):
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set IP=%%a
    goto :found
)
:found
echo  http://%IP: =% :8000
echo ============================================
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
