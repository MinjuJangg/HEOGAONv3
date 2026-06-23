from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ISSUE_DB_PATH = ROOT / "document_issue_guide.sqlite"
DEPARTMENT_DB_PATH = ROOT.parent / "department_mapping" / "seoul_department_mapping.sqlite"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lookup document issue/submission guide.")
    parser.add_argument("--document", required=True, help="Document name keyword, e.g. 위생교육 수료증")
    parser.add_argument("--district-code", help="Seoul district code, e.g. 11440 for Mapo-gu")
    parser.add_argument("--district-name", help="District name, e.g. 마포구")
    parser.add_argument(
        "--core",
        action="store_true",
        help="Search only the compact 18-row demo guide instead of the full graph-derived guide.",
    )
    return parser.parse_args()


def fetch_department(local_task_key: str, district_code: str | None, district_name: str | None) -> dict[str, str] | None:
    if not local_task_key or (not district_code and not district_name):
        return None
    where = "district_code = ?" if district_code else "district_name = ?"
    value = district_code or district_name
    conn = sqlite3.connect(DEPARTMENT_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            f"""
            SELECT *
            FROM department_mapping
            WHERE {where} AND local_task_key = ?
            """,
            (value, local_task_key),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def main() -> None:
    args = parse_args()
    table_name = "document_issue_guide" if args.core else "all_document_issue_guide"
    conn = sqlite3.connect(ISSUE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT *
            FROM {table_name}
            WHERE document_name LIKE ?
            ORDER BY document_group, document_name
            """,
            (f"%{args.document}%",),
        ).fetchall()
    finally:
        conn.close()

    result_rows = []
    for row in rows:
        item = dict(row)
        local_departments = []
        task_keys = [
            key.strip()
            for key in item.get("submit_to_local_task_key", "").split(";")
            if key.strip()
        ]
        for task_key in task_keys:
            department = fetch_department(task_key, args.district_code, args.district_name)
            if department:
                local_departments.append(
                    {
                        "local_task_key": task_key,
                        "district_name": department["district_name"],
                        "actual_department_name": department["actual_department_name"],
                        "actual_team_name": department["actual_team_name"],
                        "phone": department["phone"],
                        "source_url": department["source_url"],
                    }
                )
        if local_departments:
            item["local_departments"] = local_departments
        result_rows.append(item)

    print(json.dumps({"found": bool(result_rows), "rows": result_rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
