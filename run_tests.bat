@echo off
.venv\Scripts\python.exe -m pytest tests/ -x -q --tb=short 2>&1
echo EXIT_CODE=%ERRORLEVEL%
