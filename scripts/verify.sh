#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] Python syntax check (src + scripts)"
python -m py_compile $(find src scripts -type f -name "*.py" -print)

echo "[2/4] Regenerate tests (must be deterministic and compile)"
python scripts/write_tests.py

echo "[3/4] Python syntax check (tests)"
python -m py_compile $(find tests -type f -name "*.py" -print)

echo "[4/4] Run pytest"
pytest

echo "OK: verification passed"
