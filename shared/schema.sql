-- Mouse-AI local store schema (SQLite)
-- Authoritative raw event log + derived aggregates.
-- Raw events are retained in full; aggregates are a cache over them.

PRAGMA journal_mode = WAL;      -- concurrent read (dashboard/api) while agent writes
PRAGMA synchronous = NORMAL;

-- One row per capture session (agent start -> stop).
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    started_t    REAL NOT NULL,          -- unix seconds
    ended_t      REAL,                    -- null while active
    grid_rows    INTEGER NOT NULL,
    grid_cols    INTEGER NOT NULL,
    -- virtual-desktop bounds captured at session start
    vx           INTEGER NOT NULL,
    vy           INTEGER NOT NULL,
    vw           INTEGER NOT NULL,
    vh           INTEGER NOT NULL
);

-- One row per click. Nothing here is ever pruned.
CREATE TABLE IF NOT EXISTS clicks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL REFERENCES sessions(session_id),
    seq          INTEGER NOT NULL,        -- per-session ordinal
    t            REAL NOT NULL,           -- unix seconds
    x_virt       INTEGER NOT NULL,        -- absolute virtual-desktop coord (may be negative)
    y_virt       INTEGER NOT NULL,
    x_norm       REAL NOT NULL,           -- 0..1 over the virtual rectangle
    y_norm       REAL NOT NULL,
    button       TEXT NOT NULL,           -- 'left' | 'right' | 'middle'
    monitor_id   INTEGER,                 -- which physical monitor, if known
    zone_id      TEXT NOT NULL            -- unified grid zone, e.g. 'r0c2'
);

CREATE INDEX IF NOT EXISTS ix_clicks_session ON clicks(session_id);
CREATE INDEX IF NOT EXISTS ix_clicks_zone    ON clicks(zone_id);
CREATE INDEX IF NOT EXISTS ix_clicks_t       ON clicks(t);

-- Derived aggregate: cumulative click count per zone (all sessions).
-- Rebuildable from `clicks` at any time; kept for fast dashboards.
CREATE TABLE IF NOT EXISTS zone_totals (
    zone_id      TEXT PRIMARY KEY,
    total_clicks INTEGER NOT NULL DEFAULT 0,
    last_click_t REAL
);
