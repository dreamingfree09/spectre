import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from spectre import execution_plan

try:
    import jsonschema
except ImportError:
    print("jsonschema is required. Please install with: pip install jsonschema")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Build a dry-run execution plan (no trading)")
    parser.add_argument("--facts", required=True, help="Path to facts_pack.json")
    parser.add_argument("--decision", required=True, help="Path to decision_packet.json")
    parser.add_argument("--out", required=True, help="Path to output execution_plan.json")
    args = parser.parse_args()

    with open(args.facts, "r", encoding="utf-8") as f:
        facts_pack = json.load(f)
    with open(args.decision, "r", encoding="utf-8") as f:
        decision_packet = json.load(f)


    plan = execution_plan.build_execution_plan(
        facts_pack, decision_packet, args.facts, args.decision
    )

    schema_path = Path(__file__).parent.parent / "schemas" / "execution_plan.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    try:
        jsonschema.validate(plan, schema)
    except jsonschema.ValidationError as e:
        print("EXECUTION PLAN INVALID")
        print(e)
        sys.exit(1)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    action = plan["plan"]["action"]
    orders = plan["plan"]["orders"]
    num_orders = len(orders)
    num_refusals = len(plan["refusals"])
    avg_price = 0.0
    if num_orders > 0:
        avg_price = sum(o["price_used"] for o in orders) / num_orders
    num_rules = len(plan.get("exchange_rules", {}).get("symbols", {}))
    print("EXECUTION PLAN VALID")
    print(f"Action: {action}, Orders: {num_orders}, Avg price used: {avg_price:.4f}, Refusals: {num_refusals}")
    print(f"Exchange rules fetched for {num_rules} symbol(s)")
    if num_refusals > 0:
        first_refusal = plan["refusals"][0]
        print(f"First refusal: {first_refusal['code']} ({first_refusal['symbol']})")

if __name__ == "__main__":
    main()
