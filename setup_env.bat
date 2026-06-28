@echo off
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo Updating pip...
pip install --upgrade pip

REM Auto-detect GPU availability
nvidia-smi >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo NVIDIA GPU detected — installing GPU dependencies...
    pip install -r requirements.txt
) else (
    echo No NVIDIA GPU detected — installing CPU-only dependencies...
    pip install -r requirements-cpu.txt
)

echo Environment setup complete.
echo Run: convert.bat ^<your_document^>
