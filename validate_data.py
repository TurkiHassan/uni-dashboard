"""Validate the dashboard data file before it is published.

Usage: python validate_data.py [path-to-data.js]
Returns a non-zero exit code when the payload is empty, malformed, or missing
the minimum Blackboard fields. The updater can use this as a publish gate.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def load(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(r"window\.DATA\s*=\s*(\{.*\})\s*;?\s*$", text, re.S)
    if not match:
        raise ValueError("window.DATA object was not found")
    return json.loads(match.group(1))


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data.get("courses"), list) or not data["courses"]:
        errors.append("courses is empty or missing")
    for i, course in enumerate(data.get("courses", [])):
        for key in ("code", "name"):
            if not course.get(key):
                errors.append(f"courses[{i}].{key} is missing")
    for key in ("tasks", "announcements", "events", "studyPlan"):
        if key not in data or not isinstance(data[key], list):
            errors.append(f"{key} must be an array")
    if not data.get("updated"):
        errors.append("updated timestamp is missing")
    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("data.js")
    try:
        data = load(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}")
        return 2
    errors = validate(data)
    if errors:
        print("INVALID:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"VALID: {len(data['courses'])} courses, {len(data['tasks'])} tasks, {len(data['announcements'])} announcements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
