
# spectre

## Quickstart (Windows)

```powershell
# Activate venv (if not already active)
.\.venv\Scripts\Activate.ps1
# Run the full validation pipeline
.\run_pipeline.ps1
Spectre — Deterministic Crypto Trading Planner (Dry-Run)
======================================================

**What it is:**
Spectre is a deterministic pipeline that produces a schema-validated, dry-run execution plan for crypto trading using only public Binance endpoints. It is designed for research, planning, and auditability—**not** for live trading.

**What it is NOT:**
- Not an automated trading bot
- Does not place orders or require API/auth keys
- Not financial advice

## Architecture Overview (Pass 1–4.3)

**Pass 1:** Validate schema examples (ensures all input/output formats are correct)

**Pass 2:** Build `facts_pack.json` (fetches public candle data for selected symbols)

**Pass 3:** Build `decision_packet.json` (applies deterministic, non-AI rules to facts)

**Pass 4.3:** Build `execution_plan.json` (produces a dry-run plan using public pricing and Binance exchangeInfo filters—step size, min qty, min notional—with audit fields)

## Produced Artefacts

- **facts_pack.json**: Contains public market data (candles) for selected symbols and lookback period.
- **decision_packet.json**: Contains deterministic trade decisions based on rules (no AI, no randomness).
- **execution_plan.json**: Contains a dry-run plan for hypothetical trades, validated against schema, with audit fields and all Binance filters applied.

## Safety Guarantees

- Uses only public endpoints (no keys, no secrets)
- Dry-run only: does **not** place orders or execute trades
- All outputs are validated against strict JSON Schemas

## Quickstart

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
./run_pipeline.ps1
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run_pipeline.sh
```
> **Note:** `run_pipeline.sh` is provided for Linux/macOS users and runs the same pipeline as the PowerShell script.

## Configuration Notes

- **Symbols** and **lookback-days** are CLI arguments for `build_facts_pack.py`.
- The **current budget** is fixed at 50 USDT and is split equally across all allowed symbols. This is currently hard-coded in the pipeline logic (see `build_decision_packet.py` and related modules for conceptual location).

## Disclaimer

This project is for research and educational purposes only. It is **not financial advice**. Trading cryptocurrencies is risky. You are solely responsible for any use of this software.

## License

MIT License — see [LICENSE](LICENSE).
```

This runs all validation/build steps (Pass 1–4.3) in order, stopping on first error. On success, prints a summary and artifact info.

AI-governed market intelligence system

## Pass 1: Schema Contracts & Validation Harness

**No ingestion, no analytics, no LLM.**

### Setup (Windows PowerShell, repo root)

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\scripts\validate_examples.py
```

- `validate_examples.py` validates all example files against their schemas.
- Returns exit code 0 if all valid/invalid examples behave as expected.
- Schemas use JSON Schema Draft 2020-12 (or Draft 7 if needed).

#### Schema Limitations
- `facts_pack.correlation.matrix` is required to be square and match the length of `correlation.symbols`, but JSON Schema cannot strictly enforce this; validation is best-effort.
- `allowed_symbols` and `blocked_symbols` are required to be disjoint; best-effort enforcement via schema, but not guaranteed by all validators.

**Pass 1 includes no ingestion, no analytics, no LLM.**


## Pass 2: Build a real facts pack (Binance public)

**No trading, no LLM.**

### Setup & Run (Windows PowerShell, repo root)

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\scripts\build_facts_pack.py --symbols BTCUSDT,ETHUSDT --lookback-days 365 --out artifacts\facts_pack.json
*No numpy required; all computations are pure Python.*
```

- `build_facts_pack.py` fetches daily candles for each symbol from Binance Spot public REST, computes deterministic metrics, builds a facts pack, validates it, and writes to the output path.
- Prints “FACTS PACK VALID” and a summary if successful.
- Produces `artifacts\facts_pack.json`.
- No API keys, no trading, no authenticated endpoints.


## Pass 3: Build a deterministic decision packet (no AI)

**No AI, no trading. Deterministic rules only.**

### Setup & Run (Windows PowerShell, repo root)

```
$env:PYTHONPATH="src"
python .\scripts\build_decision_packet.py --in artifacts\facts_pack.json --out artifacts\decision_packet.json
```

- `build_decision_packet.py` loads a facts pack, builds a deterministic decision packet using explicit rules, validates it against the schema, writes output, and prints a summary.
- Prints DECISION PACKET VALID and a summary if successful.
- Produces `artifacts\decision_packet.json`.
- No LLM, no trading, no API keys.



## Pass 4: Build a dry-run execution plan (no trading)



**No trading, no API keys, no exchange auth. Deterministic dry-run only.**

- Uses Binance public ticker prices (no auth)
- Fetches exchangeInfo filters for step size, minQty, and minNotional (robust parsing)
- Step-size rounding and min_qty enforcement
- Enforces min_notional (when available)
- Output includes restored audit fields (schema_version, as_of_utc, venue, mode, inputs, portfolio, pricing, exchange_rules, plan, refusals)

Includes public price snapshot and quantity calculation (still dry-run).

### Setup & Run (Windows PowerShell, repo root)

```
$env:PYTHONPATH="src"
python .\scripts\build_execution_plan.py --facts artifacts\facts_pack.json --decision artifacts\decision_packet.json --out artifacts\execution_plan.json
```

### Setup & Run (Linux, repo root)

```
export PYTHONPATH=src
python3 ./scripts/build_execution_plan.py --facts artifacts/facts_pack.json --decision artifacts/decision_packet.json --out artifacts/execution_plan.json
```

- `build_execution_plan.py` loads a facts pack and decision packet, builds a deterministic dry-run execution plan, validates it against the schema, writes output, and prints a summary.
- Prints “EXECUTION PLAN VALID” and a summary if successful.
- Produces `artifacts/execution_plan.json`.
- No trading, no API keys, no exchange auth.

**Pass 4 does not break Pass 1–3.**
