-- Observability: per-LLM-call log table (SUPER_ADMIN viewer). Idempotent.
CREATE TABLE IF NOT EXISTS ai_call_logs (
    id UUID PRIMARY KEY,
    at TIMESTAMPTZ NOT NULL DEFAULT now(),
    agent TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'chat',
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    latency_ms INTEGER NOT NULL DEFAULT 0,
    ok BOOLEAN NOT NULL DEFAULT TRUE,
    error TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL DEFAULT '',
    response TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_ai_call_logs_at ON ai_call_logs (at DESC);
