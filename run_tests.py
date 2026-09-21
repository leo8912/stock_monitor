"""Quick test runner script"""
import subprocess
import sys
import os

os.chdir(r"D:\code\stock")

test_files = [
    "tests/test_di_container.py",
    "tests/test_core_service.py",
    "tests/test_exception_handling.py",
    "tests/test_stock_data_source.py",
    "tests/test_fetcher.py",
    "tests/test_cache_manager.py",
    "tests/test_symbol_resolver.py",
    "tests/test_event_bus.py",
]

cmd = [sys.executable, "-m", "pytest"] + test_files + ["-v", "--tb=short"]
print(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
print(f"EXIT CODE: {result.returncode}")
