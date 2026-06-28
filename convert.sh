#!/bin/bash
set -e
source venv/bin/activate
python convert_doc.py "$@"
