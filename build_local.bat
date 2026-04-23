@echo off
echo ===  FPX Timetracker - Lokaler Build  ===
call .venv\Scripts\activate.bat 2>nul || (echo Kein .venv gefunden, nutze globales Python & echo.)
python build\build_exe.py
if %errorlevel% neq 0 (
    echo.
    echo BUILD FEHLGESCHLAGEN
    pause
    exit /b 1
)
echo.
echo Starte die .exe zum Testen...
start "" dist\FPXTimetracker.exe
