import pytest
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.getcwd())
os.environ["PYTEST_QT_API"] = "pyqt6"

with open("smoke_result.txt", "w", encoding="utf-8") as f:
    sys.stdout = f
    sys.stderr = f
    ret = pytest.main(["tests", "-v"])
    print(f"\nExit code: {ret}")
