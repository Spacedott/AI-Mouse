import type { ZoneTotal } from "../api";

// Renders the unified grid as a heat table. Reads rows/cols from the zone
// ids (r{row}c{col}) so it matches whatever grid the agent recorded.
export function ZoneGrid({ zones }: { zones: ZoneTotal[] }) {
  const byId = new Map(zones.map((z) => [z.zone_id, z.total_clicks]));
  const max = Math.max(1, ...zones.map((z) => z.total_clicks));

  let rows = 0;
  let cols = 0;
  for (const z of zones) {
    const m = /^r(\d+)c(\d+)$/.exec(z.zone_id);
    if (!m) continue;
    rows = Math.max(rows, Number(m[1]) + 1);
    cols = Math.max(cols, Number(m[2]) + 1);
  }
  if (rows === 0 || cols === 0) return <p>No click data yet.</p>;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: 2,
        aspectRatio: `${cols} / ${rows}`,
        maxWidth: 640,
      }}
    >
      {Array.from({ length: rows * cols }).map((_, i) => {
        const r = Math.floor(i / cols);
        const c = i % cols;
        const id = `r${r}c${c}`;
        const count = byId.get(id) ?? 0;
        const intensity = count / max; // 0..1
        return (
          <div
            key={id}
            title={`${id}: ${count} clicks`}
            style={{
              background: `rgba(255, 80, 0, ${0.08 + intensity * 0.92})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 12,
              color: intensity > 0.5 ? "white" : "#333",
              borderRadius: 4,
            }}
          >
            {count}
          </div>
        );
      })}
    </div>
  );
}
