"""
build_decision_packet.py
Builds a deterministic decision packet from a facts pack.
"""
import argparse
import json
import sys
import os
from jsonschema import validate, ValidationError
from spectre.decision_rules import build_decision_packet

def main():
    parser = argparse.ArgumentParser(description="Build deterministic decision packet.")
    parser.add_argument("--in", dest="in_path", required=True, help="Input facts pack JSON path")
    parser.add_argument("--out", dest="out_path", required=True, help="Output decision packet JSON path")
    args = parser.parse_args()

    # Load facts pack
    try:
        with open(args.in_path, "r", encoding="utf-8") as f:
            facts_pack = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load facts pack: {e}", file=sys.stderr)
        sys.exit(1)

    # Build decision packet
    try:
        decision_packet = build_decision_packet(facts_pack)
    except Exception as e:
        print(f"ERROR: Failed to build decision packet: {e}", file=sys.stderr)
        sys.exit(1)

    # Load schema
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schemas", "decision_packet.schema.json")
    schema_path = os.path.abspath(schema_path)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load schema: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate
    try:
        validate(instance=decision_packet, schema=schema)
    except ValidationError as e:
        print(f"ERROR: Decision packet validation failed: {e.message}", file=sys.stderr)
        sys.exit(2)

    # Write output
    try:
        with open(args.out_path, "w", encoding="utf-8") as f:
            json.dump(decision_packet, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"ERROR: Failed to write output: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    print("DECISION PACKET VALID")
    print(f"Regime: {decision_packet['global_regime']}")
    print(f"Risk score: {decision_packet['risk_score']}")
    print(f"Strategy mode: {decision_packet['strategy_mode']}")
    print(f"Allowed symbols: {decision_packet['allowed_symbols']}")
    print(f"Blocked symbols: {decision_packet['blocked_symbols']}")

if __name__ == "__main__":
    main()
