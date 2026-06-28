@echo off
call venv\Scripts\activate.bat
python convert_doc.py %*
