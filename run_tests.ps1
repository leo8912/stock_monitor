Set-Location "D:\code\stock"
& ".\.venv\Scripts\python.exe" -m pytest tests/ -x -q --tb=short 2>&1
