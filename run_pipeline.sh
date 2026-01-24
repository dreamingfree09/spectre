#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

# Ensure src/ layout imports work
export PYTHONPATH="src"

echo "[1/4] Validating examples..."
python scripts/validate_examples.py

echo "[2/4] Building facts_pack.json..."
python scripts/build_facts_pack.py \
  --symbols BTCUSDT,ETHUSDT \
  --lookback-days 365 \
  --out artifacts/facts_pack.json

echo "[3/4] Building decision_packet.json..."
python scripts/build_decision_packet.py \
  --in artifacts/facts_pack.json \
  --out artifacts/decision_packet.json

echo "[4/4] Building execution_plan.json..."
python scripts/build_execution_plan.py \
  --facts artifacts/facts_pack.json \
  --decision artifacts/decision_packet.json \
  --out artifacts/execution_plan.json

echo
echo "PIPELINE OK"
echo
ls -la artifacts
