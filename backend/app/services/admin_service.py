"""문서 링크를 결정하는 핵심 sqlite 테이블을 사람이 직접 관리하기 위한 서비스.

편집 대상은 화이트리스트로 고정한다:
  - all_document_issue_guide  (document_issue_guide.sqlite)  : 서류별 발급/제출 안내 + source_url
  - department_mapping        (seoul_department_mapping.sqlite): 구청 부서 매핑 + source_url

테이블에 명시적 PK가 없으므로 sqlite 암시적 rowid를 식별자로 사용한다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCUMENT_DB = REPO_ROOT / "heogaon" / "document_issue_guide" / "document_issue_guide.sqlite"
DEPARTMENT_DB = REPO_ROOT / "heogaon" / "department_mapping" / "seoul_department_mapping.sqlite"


# 편집 가능한 테이블만 명시적으로 허용한다. (SQL injection 방지: 식별자는 절대 사용자 입력에서 받지 않음)
ALLOWED_TABLES: dict[str, dict[str, Any]] = {
    "all_document_issue_guide": {
        "db": DOCUMENT_DB,
        "label": "서류 발급/제출 안내 (문서 링크)",
        "highlight": ["document_name", "source_title", "source_url", "submit_to_local_task_key"],
    },
    "department_mapping": {
        "db": DEPARTMENT_DB,
        "label": "구청 부서 매핑 (제출처 링크)",
        "highlight": ["district_name", "local_task_key", "actual_department_name", "source_title", "source_url"],
    },
}


class AdminError(Exception):
    """4xx 수준의 사용자 입력 오류."""


def _resolve(table: str) -> dict[str, Any]:
    meta = ALLOWED_TABLES.get(table)
    if not meta:
        raise AdminError(f"허용되지 않은 테이블입니다: {table}")
    db_path: Path = meta["db"]
    if not db_path.exists():
        raise AdminError(f"DB 파일을 찾을 수 없습니다: {db_path}")
    return meta


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def columns_of(table: str) -> list[str]:
    meta = _resolve(table)
    conn = _connect(meta["db"])
    try:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    finally:
        conn.close()
    return [str(r["name"]) for r in rows]


def list_tables() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, meta in ALLOWED_TABLES.items():
        db_path: Path = meta["db"]
        count = 0
        if db_path.exists():
            conn = _connect(db_path)
            try:
                count = int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
            finally:
                conn.close()
        out.append(
            {
                "name": name,
                "label": meta["label"],
                "rowCount": count,
                "highlight": meta["highlight"],
            }
        )
    return out


def list_rows(table: str, search: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    meta = _resolve(table)
    cols = columns_of(table)
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))

    where = ""
    params: list[Any] = []
    term = (search or "").strip()
    if term:
        clauses = " OR ".join(f'"{c}" LIKE ?' for c in cols)
        where = f"WHERE {clauses}"
        params = [f"%{term}%"] * len(cols)

    conn = _connect(meta["db"])
    try:
        total = int(conn.execute(f'SELECT COUNT(*) FROM "{table}" {where}', params).fetchone()[0])
        col_list = ", ".join(f'"{c}"' for c in cols)
        rows = conn.execute(
            f'SELECT rowid AS _rowid, {col_list} FROM "{table}" {where} '
            f"ORDER BY rowid LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    finally:
        conn.close()

    return {
        "table": table,
        "columns": cols,
        "highlight": meta["highlight"],
        "total": total,
        "limit": limit,
        "offset": offset,
        "rows": [dict(r) for r in rows],
    }


def _clean_values(table: str, values: dict[str, Any]) -> dict[str, str]:
    cols = set(columns_of(table))
    cleaned: dict[str, str] = {}
    for key, value in (values or {}).items():
        if key == "_rowid" or key not in cols:
            continue
        cleaned[key] = "" if value is None else str(value)
    if not cleaned:
        raise AdminError("수정할 컬럼이 없습니다.")
    return cleaned


def update_row(table: str, rowid: int, values: dict[str, Any]) -> dict[str, Any]:
    meta = _resolve(table)
    cleaned = _clean_values(table, values)
    assignments = ", ".join(f'"{c}" = ?' for c in cleaned)
    params = [*cleaned.values(), int(rowid)]

    conn = _connect(meta["db"])
    try:
        cur = conn.execute(f'UPDATE "{table}" SET {assignments} WHERE rowid = ?', params)
        if cur.rowcount == 0:
            raise AdminError(f"해당 행을 찾을 수 없습니다 (rowid={rowid}).")
        conn.commit()
    finally:
        conn.close()
    return _fetch_one(table, int(rowid))


def insert_row(table: str, values: dict[str, Any]) -> dict[str, Any]:
    meta = _resolve(table)
    cleaned = _clean_values(table, values)
    col_list = ", ".join(f'"{c}"' for c in cleaned)
    placeholders = ", ".join("?" for _ in cleaned)

    conn = _connect(meta["db"])
    try:
        cur = conn.execute(
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})',
            list(cleaned.values()),
        )
        conn.commit()
        new_rowid = int(cur.lastrowid)
    finally:
        conn.close()
    return _fetch_one(table, new_rowid)


def delete_row(table: str, rowid: int) -> None:
    meta = _resolve(table)
    conn = _connect(meta["db"])
    try:
        cur = conn.execute(f'DELETE FROM "{table}" WHERE rowid = ?', [int(rowid)])
        if cur.rowcount == 0:
            raise AdminError(f"해당 행을 찾을 수 없습니다 (rowid={rowid}).")
        conn.commit()
    finally:
        conn.close()


def _fetch_one(table: str, rowid: int) -> dict[str, Any]:
    meta = _resolve(table)
    cols = columns_of(table)
    col_list = ", ".join(f'"{c}"' for c in cols)
    conn = _connect(meta["db"])
    try:
        row = conn.execute(
            f'SELECT rowid AS _rowid, {col_list} FROM "{table}" WHERE rowid = ?', [int(rowid)]
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else {}
