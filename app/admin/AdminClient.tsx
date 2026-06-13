"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  adminLogin,
  deleteRow,
  fetchRows,
  fetchTables,
  insertRow,
  updateRow,
  type AdminRows,
  type AdminTable,
} from "@/lib/adminApi";

const PW_KEY = "heogaon_admin_pw";
const PAGE_SIZE = 50;

type RowRecord = Record<string, string | number>;

export function AdminClient() {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [authError, setAuthError] = useState("");
  const [pwInput, setPwInput] = useState("");

  // 세션에 저장된 비밀번호로 자동 로그인 시도
  useEffect(() => {
    const saved = typeof window !== "undefined" ? window.sessionStorage.getItem(PW_KEY) : null;
    if (!saved) return;
    adminLogin(saved)
      .then(() => {
        setPassword(saved);
        setAuthed(true);
      })
      .catch(() => window.sessionStorage.removeItem(PW_KEY));
  }, []);

  const handleLogin = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setAuthError("");
      try {
        await adminLogin(pwInput);
        window.sessionStorage.setItem(PW_KEY, pwInput);
        setPassword(pwInput);
        setAuthed(true);
      } catch (err) {
        setAuthError(err instanceof Error ? err.message : "로그인 실패");
      }
    },
    [pwInput],
  );

  if (!authed) {
    return (
      <main style={S.loginWrap}>
        <form onSubmit={handleLogin} style={S.loginCard}>
          <h1 style={S.loginTitle}>허가온 DB 관리자</h1>
          <p style={S.loginHint}>문서 링크(서류 발급/제출처) 데이터를 직접 관리합니다.</p>
          <input
            type="password"
            value={pwInput}
            onChange={(e) => setPwInput(e.target.value)}
            placeholder="관리자 비밀번호"
            style={S.input}
            autoFocus
          />
          {authError && <div style={S.error}>{authError}</div>}
          <button type="submit" style={S.primaryBtn}>
            로그인
          </button>
        </form>
      </main>
    );
  }

  return <AdminPanel password={password} onLogout={() => {
    window.sessionStorage.removeItem(PW_KEY);
    setAuthed(false);
    setPassword("");
    setPwInput("");
  }} />;
}

function AdminPanel({ password, onLogout }: { password: string; onLogout: () => void }) {
  const [tables, setTables] = useState<AdminTable[]>([]);
  const [active, setActive] = useState<string>("");
  const [data, setData] = useState<AdminRows | null>(null);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<{ rowid: number | null; values: Record<string, string> } | null>(null);
  const [banner, setBanner] = useState("");

  useEffect(() => {
    fetchTables(password)
      .then((res) => {
        setTables(res.tables);
        if (res.tables.length) setActive(res.tables[0].name);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "테이블 목록 로드 실패"));
  }, [password]);

  const load = useCallback(() => {
    if (!active) return;
    setLoading(true);
    setError("");
    fetchRows(password, active, search, PAGE_SIZE, page * PAGE_SIZE)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "행 로드 실패"))
      .finally(() => setLoading(false));
  }, [password, active, search, page]);

  useEffect(() => {
    load();
  }, [load]);

  const activeMeta = useMemo(() => tables.find((t) => t.name === active), [tables, active]);
  const highlight = useMemo(() => new Set(data?.highlight || []), [data]);

  const showBanner = (msg: string) => {
    setBanner(msg);
    window.setTimeout(() => setBanner(""), 2500);
  };

  const openEdit = (row: RowRecord) => {
    const { _rowid, ...rest } = row;
    const values: Record<string, string> = {};
    (data?.columns || []).forEach((c) => (values[c] = rest[c] == null ? "" : String(rest[c])));
    setEditing({ rowid: Number(_rowid), values });
  };

  const openNew = () => {
    const values: Record<string, string> = {};
    (data?.columns || []).forEach((c) => (values[c] = ""));
    setEditing({ rowid: null, values });
  };

  const save = async () => {
    if (!editing || !active) return;
    try {
      if (editing.rowid == null) {
        await insertRow(password, active, editing.values);
        showBanner("새 행을 추가했습니다.");
      } else {
        await updateRow(password, active, editing.rowid, editing.values);
        showBanner("저장했습니다.");
      }
      setEditing(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 실패");
    }
  };

  const remove = async () => {
    if (!editing || editing.rowid == null || !active) return;
    if (!window.confirm("이 행을 정말 삭제할까요? 되돌릴 수 없습니다.")) return;
    try {
      await deleteRow(password, active, editing.rowid);
      showBanner("삭제했습니다.");
      setEditing(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "삭제 실패");
    }
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <main style={S.shell}>
      <header style={S.header}>
        <div>
          <h1 style={S.h1}>허가온 DB 관리자</h1>
          <p style={S.subtle}>서류 링크(발급처·제출처 URL)를 결정하는 핵심 테이블을 직접 편집합니다.</p>
        </div>
        <button onClick={onLogout} style={S.ghostBtn}>
          로그아웃
        </button>
      </header>

      <div style={S.tabs}>
        {tables.map((t) => (
          <button
            key={t.name}
            onClick={() => {
              setActive(t.name);
              setPage(0);
              setSearch("");
              setSearchInput("");
            }}
            style={{ ...S.tab, ...(t.name === active ? S.tabActive : {}) }}
          >
            {t.label}
            <span style={S.tabCount}>{t.rowCount}</span>
          </button>
        ))}
      </div>

      <div style={S.toolbar}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setPage(0);
            setSearch(searchInput.trim());
          }}
          style={S.searchForm}
        >
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="모든 컬럼에서 검색 (예: 신분증)"
            style={S.input}
          />
          <button type="submit" style={S.primaryBtn}>
            검색
          </button>
          {search && (
            <button
              type="button"
              onClick={() => {
                setSearch("");
                setSearchInput("");
                setPage(0);
              }}
              style={S.ghostBtn}
            >
              초기화
            </button>
          )}
        </form>
        <button onClick={openNew} style={S.primaryBtn} disabled={!data}>
          + 새 행 추가
        </button>
      </div>

      {banner && <div style={S.banner}>{banner}</div>}
      {error && <div style={S.error}>{error}</div>}

      <div style={S.tableWrap}>
        {loading && <div style={S.subtle}>불러오는 중…</div>}
        {data && (
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>#</th>
                {data.columns.map((c) => (
                  <th key={c} style={{ ...S.th, ...(highlight.has(c) ? S.thHi : {}) }}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={String(row._rowid)} style={S.tr} onClick={() => openEdit(row)}>
                  <td style={S.tdIdx}>{String(row._rowid)}</td>
                  {data.columns.map((c) => (
                    <td key={c} style={{ ...S.td, ...(highlight.has(c) ? S.tdHi : {}) }} title={String(row[c] ?? "")}>
                      {truncate(String(row[c] ?? ""))}
                    </td>
                  ))}
                </tr>
              ))}
              {data.rows.length === 0 && (
                <tr>
                  <td colSpan={data.columns.length + 1} style={S.empty}>
                    결과가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {data && (
        <div style={S.pager}>
          <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} style={S.ghostBtn}>
            ← 이전
          </button>
          <span style={S.subtle}>
            {page + 1} / {totalPages} 페이지 · 총 {data.total}행
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page + 1 >= totalPages}
            style={S.ghostBtn}
          >
            다음 →
          </button>
        </div>
      )}

      {editing && data && (
        <div style={S.overlay} onClick={() => setEditing(null)}>
          <div style={S.drawer} onClick={(e) => e.stopPropagation()}>
            <div style={S.drawerHead}>
              <h2 style={S.h2}>{editing.rowid == null ? "새 행 추가" : `행 편집 (rowid ${editing.rowid})`}</h2>
              <button onClick={() => setEditing(null)} style={S.ghostBtn}>
                닫기
              </button>
            </div>
            <p style={S.subtle}>
              {activeMeta?.label} · 강조된 항목이 링크/URL을 결정합니다.
            </p>
            <div style={S.fields}>
              {data.columns.map((c) => (
                <label key={c} style={S.field}>
                  <span style={{ ...S.fieldLabel, ...(highlight.has(c) ? S.fieldLabelHi : {}) }}>{c}</span>
                  <textarea
                    value={editing.values[c] ?? ""}
                    onChange={(e) =>
                      setEditing((prev) => (prev ? { ...prev, values: { ...prev.values, [c]: e.target.value } } : prev))
                    }
                    rows={c.includes("url") || c.includes("text") || c.includes("summary") ? 3 : 1}
                    style={{ ...S.textarea, ...(highlight.has(c) ? S.textareaHi : {}) }}
                  />
                </label>
              ))}
            </div>
            <div style={S.drawerFoot}>
              {editing.rowid != null && (
                <button onClick={remove} style={S.dangerBtn}>
                  삭제
                </button>
              )}
              <div style={{ flex: 1 }} />
              <button onClick={() => setEditing(null)} style={S.ghostBtn}>
                취소
              </button>
              <button onClick={save} style={S.primaryBtn}>
                저장
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function truncate(value: string, max = 48): string {
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

const S: Record<string, React.CSSProperties> = {
  loginWrap: { minHeight: "100vh", display: "grid", placeItems: "center", background: "#0f172a", padding: 24 },
  loginCard: { width: 360, background: "#fff", borderRadius: 16, padding: 28, display: "flex", flexDirection: "column", gap: 12, boxShadow: "0 20px 60px rgba(0,0,0,0.3)" },
  loginTitle: { margin: 0, fontSize: 22, color: "#0f172a" },
  loginHint: { margin: 0, fontSize: 13, color: "#64748b" },
  shell: { maxWidth: 1280, margin: "0 auto", padding: "28px 24px 80px", color: "#0f172a", fontFamily: "system-ui, -apple-system, sans-serif" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 20 },
  h1: { margin: 0, fontSize: 24 },
  h2: { margin: 0, fontSize: 18 },
  subtle: { color: "#64748b", fontSize: 13, margin: "4px 0 0" },
  tabs: { display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" },
  tab: { display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 16px", borderRadius: 10, border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer", fontSize: 14, color: "#334155" },
  tabActive: { background: "#1d4ed8", borderColor: "#1d4ed8", color: "#fff" },
  tabCount: { fontSize: 12, background: "rgba(0,0,0,0.08)", borderRadius: 999, padding: "1px 8px" },
  toolbar: { display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 12, flexWrap: "wrap" },
  searchForm: { display: "flex", gap: 8, flex: 1, minWidth: 280 },
  input: { flex: 1, padding: "10px 12px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 14, minWidth: 0 },
  primaryBtn: { padding: "10px 16px", borderRadius: 10, border: "none", background: "#1d4ed8", color: "#fff", cursor: "pointer", fontSize: 14, whiteSpace: "nowrap" },
  ghostBtn: { padding: "10px 14px", borderRadius: 10, border: "1px solid #cbd5e1", background: "#fff", color: "#334155", cursor: "pointer", fontSize: 14, whiteSpace: "nowrap" },
  dangerBtn: { padding: "10px 16px", borderRadius: 10, border: "1px solid #fecaca", background: "#fee2e2", color: "#b91c1c", cursor: "pointer", fontSize: 14 },
  banner: { background: "#dcfce7", color: "#166534", padding: "10px 14px", borderRadius: 10, marginBottom: 12, fontSize: 14 },
  error: { background: "#fee2e2", color: "#b91c1c", padding: "10px 14px", borderRadius: 10, marginBottom: 12, fontSize: 14 },
  tableWrap: { overflowX: "auto", border: "1px solid #e2e8f0", borderRadius: 12, background: "#fff" },
  table: { borderCollapse: "collapse", width: "100%", fontSize: 13 },
  th: { textAlign: "left", padding: "10px 12px", borderBottom: "2px solid #e2e8f0", whiteSpace: "nowrap", color: "#475569", position: "sticky", top: 0, background: "#f8fafc" },
  thHi: { color: "#1d4ed8", background: "#eff6ff" },
  tr: { cursor: "pointer", borderBottom: "1px solid #f1f5f9" },
  td: { padding: "9px 12px", whiteSpace: "nowrap", color: "#334155", maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis" },
  tdHi: { color: "#1e3a8a", fontWeight: 500 },
  tdIdx: { padding: "9px 12px", color: "#94a3b8", fontVariantNumeric: "tabular-nums" },
  empty: { padding: 24, textAlign: "center", color: "#94a3b8" },
  pager: { display: "flex", alignItems: "center", justifyContent: "center", gap: 16, marginTop: 16 },
  overlay: { position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", display: "flex", justifyContent: "flex-end", zIndex: 50 },
  drawer: { width: "min(560px, 100%)", height: "100%", background: "#fff", padding: 24, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 },
  drawerHead: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  fields: { display: "flex", flexDirection: "column", gap: 12, margin: "12px 0", flex: 1 },
  field: { display: "flex", flexDirection: "column", gap: 4 },
  fieldLabel: { fontSize: 12, color: "#64748b", fontFamily: "monospace" },
  fieldLabelHi: { color: "#1d4ed8", fontWeight: 600 },
  textarea: { padding: "8px 10px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 13, fontFamily: "inherit", resize: "vertical" },
  textareaHi: { borderColor: "#93c5fd", background: "#f8fbff" },
  drawerFoot: { display: "flex", gap: 8, alignItems: "center", paddingTop: 12, borderTop: "1px solid #f1f5f9", position: "sticky", bottom: 0, background: "#fff" },
};
