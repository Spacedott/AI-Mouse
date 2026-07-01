// Thin client for the local Mouse-AI API (see api/mouse_ai_api).

export interface ZoneTotal {
  zone_id: string;
  total_clicks: number;
  last_click_t: number | null;
}

export interface SessionRow {
  session_id: string;
  started_t: number;
  ended_t: number | null;
  grid_rows: number;
  grid_cols: number;
  total_clicks: number;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  zones: () => getJSON<ZoneTotal[]>("/api/zones"),
  sessions: () => getJSON<SessionRow[]>("/api/sessions"),
  reportUrl: (sessionId?: string) =>
    sessionId ? `/api/report.pdf?session_id=${sessionId}` : "/api/report.pdf",
};
