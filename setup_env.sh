#!/bin/bash
set -e

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Updating pip..."
pip install --upgrade pip

echo "Installing Docling and required packages..."
# Install docling first
pip install docling

# Install onnxruntime-gpu specifically to ensure GPU support
pip install onnxruntime-gpu

# Install verification dependencies
pip install python-docx pandas

echo "Environment setup complete."

echo "Starting document conversion..."

python convert_doc.py

echo "Start integrity verification..."

python verify_integrity.py


