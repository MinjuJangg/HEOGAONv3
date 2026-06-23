from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

from precheck_common import (
    FIELD_CANDIDATES,
    SEOUL_SIGUNGU_CODES,
    canonical_business_type,
    choose_csv_encoding,
    compact_address_key,
    extract_district,
    extract_neighborhood,
    first_value,
    parse_float,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = ROOT / "data" / "raw" / "public_data_csv" / "seoul"
DEFAULT_OUT = ROOT / "data" / "processed" / "precheck" / "seoul_localdata.sqlite"
DEFAULT_SUMMARY = ROOT / "data" / "processed" / "precheck" / "seoul_localdata_summary.json"
DEFAULT_INCLUDE = ["식품_*.csv"]
SEOUL_DISTRICTS = set(SEOUL_SIGUNGU_CODES)


SCHEMA = """
CREATE TABLE IF NOT EXISTS business_place (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_file TEXT NOT NULL,
  canonical_business_type TEXT NOT NULL,
  license_no TEXT,
  license_date TEXT,
  cancel_date TEXT,
  status TEXT,
  detail_status TEXT,
  status_code TEXT,
  close_date TEXT,
  business_name TEXT,
  subtype TEXT,
  area_m2 REAL,
  road_address TEXT,
  lot_address TEXT,
  road_key TEXT,
  lot_key TEXT,
  district TEXT,
  neighborhood TEXT,
  phone TEXT,
  x TEXT,
  y TEXT,
  raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_business_place_road_key ON business_place(road_key);
CREATE INDEX IF NOT EXISTS idx_business_place_lot_key ON business_place(lot_key);
CREATE INDEX IF NOT EXISTS idx_business_place_district ON business_place(district);
CREATE INDEX IF NOT EXISTS idx_business_place_neighborhood ON business_place(neighborhood);
CREATE INDEX IF NOT EXISTS idx_business_place_type ON business_place(canonical_business_type);
CREATE INDEX IF NOT EXISTS idx_business_place_name ON business_place(business_name);
"""


def matching_files(raw_dir: Path, patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(path for path in raw_dir.glob(pattern) if path.is_file())
    return sorted(set(files))


def reset_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS business_place;
        """
    )
    conn.executescript(SCHEMA)


def row_to_record(path: Path, row: dict[str, str]) -> dict:
    road_address = first_value(row, FIELD_CANDIDATES["road_address"])
    lot_address = first_value(row, FIELD_CANDIDATES["lot_address"])
    address_blob = f"{road_address} {lot_address}".strip()
    district = first_value(row, FIELD_CANDIDATES["district"]) or extract_district(address_blob)
    return {
        "source_file": path.name,
        "canonical_business_type": canonical_business_type(path.name, row),
        "license_no": first_value(row, FIELD_CANDIDATES["license_no"]),
        "license_date": first_value(row, FIELD_CANDIDATES["license_date"]),
        "cancel_date": first_value(row, FIELD_CANDIDATES["cancel_date"]),
        "status": first_value(row, FIELD_CANDIDATES["status"]),
        "detail_status": first_value(row, FIELD_CANDIDATES["detail_status"]),
        "status_code": first_value(row, FIELD_CANDIDATES["status_code"]),
        "close_date": first_value(row, FIELD_CANDIDATES["close_date"]),
        "business_name": first_value(row, FIELD_CANDIDATES["business_name"]),
        "subtype": first_value(row, FIELD_CANDIDATES["subtype"]),
        "area_m2": parse_float(first_value(row, FIELD_CANDIDATES["area_m2"])),
        "road_address": road_address,
        "lot_address": lot_address,
        "road_key": compact_address_key(road_address),
        "lot_key": compact_address_key(lot_address),
        "district": district,
        "neighborhood": extract_neighborhood(address_blob),
        "phone": first_value(row, FIELD_CANDIDATES["phone"]),
        "x": first_value(row, FIELD_CANDIDATES["x"]),
        "y": first_value(row, FIELD_CANDIDATES["y"]),
        "raw_json": json.dumps(row, ensure_ascii=False),
    }


def insert_records(conn: sqlite3.Connection, records: list[dict]) -> None:
    if not records:
        return
    keys = list(records[0].keys())
    placeholders = ", ".join(["?"] * len(keys))
    conn.executemany(
        f"INSERT INTO business_place ({', '.join(keys)}) VALUES ({placeholders})",
        [[record.get(key) for key in keys] for record in records],
    )


def build_index(raw_dir: Path, output: Path, summary_path: Path, patterns: list[str]) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    files = matching_files(raw_dir, patterns)
    conn = sqlite3.connect(output)
    reset_db(conn)

    total = 0
    skipped_non_seoul = 0
    by_file: dict[str, int] = {}
    by_type: Counter[str] = Counter()
    by_district: Counter[str] = Counter()
    batch: list[dict] = []

    for path in files:
        encoding = choose_csv_encoding(path)
        file_count = 0
        with path.open(encoding=encoding, errors="replace", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                record = row_to_record(path, row)
                if record["district"] and record["district"] not in SEOUL_DISTRICTS:
                    skipped_non_seoul += 1
                    continue
                batch.append(record)
                file_count += 1
                total += 1
                by_type[record["canonical_business_type"]] += 1
                if record["district"]:
                    by_district[record["district"]] += 1
                if len(batch) >= 5000:
                    insert_records(conn, batch)
                    conn.commit()
                    batch = []
        by_file[path.name] = file_count

    insert_records(conn, batch)
    conn.commit()
    conn.close()

    summary = {
        "scope": "seoul",
        "raw_dir": str(raw_dir),
        "output": str(output),
        "patterns": patterns,
        "file_count": len(files),
        "rows": total,
        "skipped_non_seoul": skipped_non_seoul,
        "by_file": by_file,
        "by_type": dict(by_type.most_common()),
        "by_district": dict(by_district.most_common()),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Seoul-wide LOCALDATA precheck SQLite index.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--include", action="append", default=[], help="Glob under raw-dir. Repeatable.")
    parser.add_argument("--all", action="store_true", help="Index every CSV under raw-dir.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    patterns = ["*.csv"] if args.all else (args.include or DEFAULT_INCLUDE)
    summary = build_index(args.raw_dir, args.output, args.summary, patterns)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
