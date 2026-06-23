from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "seoul_department_mapping.sqlite"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lookup actual department mapping by district and local task.")
    parser.add_argument("--district-code", help="Seoul district code, e.g. 11440 for Mapo-gu")
    parser.add_argument("--district-name", help="District name, e.g. 마포구")
    parser.add_argument("--task", required=True, help="local_task_key, e.g. food_business_report")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.district_code and not args.district_name:
        raise SystemExit("Provide --district-code or --district-name.")

    where = "district_code = ?" if args.district_code else "district_name = ?"
    value = args.district_code or args.district_name

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            f"""
            SELECT *
            FROM department_mapping
            WHERE {where} AND local_task_key = ?
            """,
            (value, args.task),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        print(json.dumps({"found": False, "reason": "no_mapping_row"}, ensure_ascii=False))
        return

    result = dict(row)
    result["found"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
