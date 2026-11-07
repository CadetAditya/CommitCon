"""Convenience root test runner delegating to src.test_system."""
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.test_system import run_all_tests

if __name__ == "__main__":
    run_all_tests()
