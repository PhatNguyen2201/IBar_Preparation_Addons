@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 install_addons.py
    goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
    python install_addons.py
    goto :eof
)

echo [LOI] Khong tim thay Python tren may. Vui long cai Python 3 tu https://www.python.org/downloads/
pause
