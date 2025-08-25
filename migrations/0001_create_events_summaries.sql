-- Create events and summaries tables

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    camera_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts);
CREATE INDEX IF NOT EXISTS idx_events_camera_ts ON events (camera_id, ts);

CREATE TABLE IF NOT EXISTS summaries (
    id BIGSERIAL PRIMARY KEY,
    date_hour TIMESTAMPTZ NOT NULL,
    camera_id TEXT NOT NULL,
    "group" TEXT NOT NULL,
    metric TEXT NOT NULL,
    value INT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_summaries_date_camera_group_metric
    ON summaries (date_hour, camera_id, "group", metric);
