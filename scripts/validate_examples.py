import os
import sys
import json
from jsonschema import validate, Draft202012Validator, Draft7Validator, ValidationError

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), '..', 'schemas')
EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'examples')

FILES = [
    ("facts_pack.valid.json", "facts_pack.schema.json", True),
    ("facts_pack.invalid.json", "facts_pack.schema.json", False),
    ("decision_packet.valid.json", "decision_packet.schema.json", True),
    ("decision_packet.invalid.json", "decision_packet.schema.json", False),
]


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_validator(schema):
    # Use Draft 2020-12 if available, else Draft 7
    if schema.get("$schema", "").endswith("2020-12/schema"):
        return Draft202012Validator(schema)
    return Draft7Validator(schema)


def main():
    any_fail = False
    for example_file, schema_file, should_pass in FILES:
        example_path = os.path.join(EXAMPLES_DIR, example_file)
        schema_path = os.path.join(SCHEMA_DIR, schema_file)
        data = load_json(example_path)
        schema = load_json(schema_path)
        validator = get_validator(schema)
        try:
            validator.validate(data)
            if should_pass:
                print(f"PASS: {example_file} (as expected)")
            else:
                print(f"FAIL: {example_file} (should have failed, but passed)")
                any_fail = True
        except ValidationError as e:
            if should_pass:
                print(f"FAIL: {example_file} (should have passed, but failed)")
                print(f"  Reason: {e.message}")
                any_fail = True
            else:
                print(f"PASS: {example_file} (invalid as expected)")
    if any_fail:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
