"""Make eval/run_benchmark.py importable in tests (eval/ is a scripts dir, not a package)."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "eval"))
