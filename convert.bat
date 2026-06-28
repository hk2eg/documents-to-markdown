@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat

if "%~1"=="" (
    echo No file specified — running batch mode on input\ folder...
    python convert_doc.py --batch
) else (
    python convert_doc.py %*
)

echo.
pause
