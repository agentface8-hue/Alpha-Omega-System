-- AMA (Autonomous Management Agent) tables
CREATE TABLE IF NOT EXISTS ama_memory (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    action TEXT NOT NULL,
    trigger TEXT,
    success BOOLEAN,
    detail TEXT,
    snapshot_json JSONB,
    cycle_number INTEGER
);

CREATE TABLE IF NOT EXISTS ama_state (
    key TEXT PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
