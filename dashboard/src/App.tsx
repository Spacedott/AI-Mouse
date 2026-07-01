import { useEffect, useState } from "react";
import { api, type SessionRow, type ZoneTotal } from "./api";
import { ZoneGrid } from "./components/ZoneGrid";

export function App() {
  const [zones, setZones] = useState<ZoneTotal[]>([]);
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.zones(), api.sessions()])
      .then(([z, s]) => {
        setZones(z);
        setSessions(s);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const total = zones.reduce((sum, z) => sum + z.total_clicks, 0);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 24, maxWidth: 900, margin: "0 auto" }}>
      <h1>Mouse-AI Dashboard</h1>
      {error && <p style={{ color: "crimson" }}>API error: {error} — is the API running on :8000?</p>}

      <p>
        <strong>{total.toLocaleString()}</strong> total clicks across{" "}
        <strong>{sessions.length}</strong> session(s).{" "}
        <a href={api.reportUrl()}>Download PDF report</a>
      </p>

      <h2>Click heat by zone</h2>
      <ZoneGrid zones={zones} />

      <h2 style={{ marginTop: 32 }}>Sessions</h2>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={th}>Session</th>
            <th style={th}>Started</th>
            <th style={th}>Clicks</th>
            <th style={th}>Report</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.session_id}>
              <td style={td}>{s.session_id.slice(0, 8)}</td>
              <td style={td}>{new Date(s.started_t * 1000).toLocaleString()}</td>
              <td style={td}>{s.total_clicks}</td>
              <td style={td}>
                <a href={api.reportUrl(s.session_id)}>PDF</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}

const th: React.CSSProperties = { textAlign: "left", borderBottom: "2px solid #333", padding: "6px 8px" };
const td: React.CSSProperties = { borderBottom: "1px solid #ddd", padding: "6px 8px" };
