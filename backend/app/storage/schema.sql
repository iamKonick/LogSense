CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS routing_receipts (
    event_id text PRIMARY KEY,
    prediction jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS events (
    id text PRIMARY KEY,
    priority text NOT NULL CHECK (priority IN ('P4','P5')),
    timestamp timestamptz NOT NULL,
    payload jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS events_time_idx ON events(timestamp DESC);
CREATE TABLE IF NOT EXISTS incidents (
    id text PRIMARY KEY REFERENCES events(id),
    status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','investigating','resolved')),
    root_cause text NOT NULL DEFAULT '',
    resolution text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS incident_history (
    id bigserial PRIMARY KEY,
    incident_id text NOT NULL REFERENCES incidents(id),
    status text NOT NULL,
    actor text NOT NULL,
    note text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS knowledge (
    id text PRIMARY KEY,
    title text NOT NULL,
    content text NOT NULL,
    kind text NOT NULL,
    source text NOT NULL,
    verified boolean NOT NULL DEFAULT false,
    embedding vector(384) NOT NULL,
    observations integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS knowledge_kind_idx ON knowledge(kind);
CREATE TABLE IF NOT EXISTS knowledge_observations (
    event_id text PRIMARY KEY,
    knowledge_id text NOT NULL REFERENCES knowledge(id),
    observed_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS events_received_idx ON events (((payload->>'received_at')));
CREATE INDEX IF NOT EXISTS events_source_idx ON events ((payload->>'source'));
CREATE INDEX IF NOT EXISTS events_dataset_idx ON events ((payload->>'dataset'));

ALTER TABLE knowledge_observations ADD COLUMN IF NOT EXISTS predicted_priority text;
ALTER TABLE knowledge_observations ADD COLUMN IF NOT EXISTS model_version text;
