#!/bin/bash
set -e

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Updating pip..."
pip install --upgrade pip

# Auto-detect GPU availability
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected — installing GPU dependencies..."
    pip install -r requirements.txt
else
    echo "No NVIDIA GPU detected — installing CPU-only dependencies..."
    pip install -r requirements-cpu.txt
fi

echo "Environment setup complete."
echo "Run: ./convert.sh <your_document>"
