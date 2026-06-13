const API_BASE_URL = (process.env.NEXT_PUBLIC_HEOGAON_API_BASE_URL || "http://127.0.0.1:4100").replace(/\/$/, "");

export interface AdminTable {
  name: string;
  label: string;
  rowCount: number;
  highlight: string[];
}

export interface AdminRows {
  table: string;
  columns: string[];
  highlight: string[];
  total: number;
  limit: number;
  offset: number;
  rows: Array<Record<string, string | number>>;
}

async function request<T>(path: string, password: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Password": password,
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = `API ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export function adminLogin(password: string): Promise<{ ok: boolean }> {
  return request("/api/admin/login", password, { method: "POST" });
}

export function fetchTables(password: string): Promise<{ tables: AdminTable[] }> {
  return request("/api/admin/tables", password);
}

export function fetchRows(
  password: string,
  table: string,
  search: string,
  limit: number,
  offset: number,
): Promise<AdminRows> {
  const qs = new URLSearchParams({ search, limit: String(limit), offset: String(offset) });
  return request(`/api/admin/tables/${encodeURIComponent(table)}/rows?${qs}`, password);
}

export function updateRow(
  password: string,
  table: string,
  rowid: number,
  values: Record<string, string>,
): Promise<{ row: Record<string, string | number> }> {
  return request(`/api/admin/tables/${encodeURIComponent(table)}/rows/${rowid}`, password, {
    method: "PUT",
    body: JSON.stringify({ values }),
  });
}

export function insertRow(
  password: string,
  table: string,
  values: Record<string, string>,
): Promise<{ row: Record<string, string | number> }> {
  return request(`/api/admin/tables/${encodeURIComponent(table)}/rows`, password, {
    method: "POST",
    body: JSON.stringify({ values }),
  });
}

export function deleteRow(password: string, table: string, rowid: number): Promise<{ ok: boolean }> {
  return request(`/api/admin/tables/${encodeURIComponent(table)}/rows/${rowid}`, password, {
    method: "DELETE",
  });
}
