@echo off
setlocal EnableExtensions

echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    exit /b 1
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    exit /b 1
)

echo Updating pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip.
    exit /b 1
)

REM Auto-detect GPU availability
nvidia-smi >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo NVIDIA GPU detected — installing GPU dependencies...
    pip install -r requirements-windows.txt
) else (
    echo No NVIDIA GPU detected — installing CPU-only dependencies...
    pip install -r requirements-cpu.txt
)

if errorlevel 1 (
    echo ERROR: Dependency installation failed. See pip output above.
    exit /b 1
)

echo Environment setup complete.
echo Run: convert.bat ^<your_document^>
