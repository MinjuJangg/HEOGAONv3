import type { ApiEnvelope, TurnInput } from "@/types/flow";

const API_BASE_URL = (process.env.NEXT_PUBLIC_HEOGAON_API_BASE_URL || "http://127.0.0.1:4100").replace(/\/$/, "");

export async function startCase(text: string): Promise<ApiEnvelope> {
  return send("/api/cases", { type: "natural_language", text });
}

export async function getCase(caseId: string): Promise<ApiEnvelope> {
  const response = await fetch(`${API_BASE_URL}/api/cases/${caseId}`);
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<ApiEnvelope>;
}

export async function sendTurn(caseId: string, input: TurnInput): Promise<ApiEnvelope> {
  return send(`/api/cases/${caseId}/turns`, input);
}

async function send(path: string, input: TurnInput): Promise<ApiEnvelope> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }

  return response.json() as Promise<ApiEnvelope>;
}

async function responseErrorMessage(response: Response) {
  const text = await response.text();
  if (!text) return `API ${response.status}`;

  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    return text;
  }

  return text;
}
