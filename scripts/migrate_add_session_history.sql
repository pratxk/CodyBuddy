-- Migration: add session-history columns to the projects table.
--
-- WHY: db/models.py gained `chat` (VibeEngineer + UX Master conversation) and
-- `oncall_log` (OnCall auto-repair entries) as JSONB columns. SQLAlchemy's
-- create_all() only CREATEs missing tables — it never ALTERs an existing one —
-- so the live Neon `projects` table needs these ALTERs applied manually.
--
-- HOW TO RUN (Neon): paste into the Neon SQL editor, or:
--   psql "$POSTGRES_URL" -f scripts/migrate_add_session_history.sql
-- Idempotent (IF NOT EXISTS) — safe to run more than once.

ALTER TABLE projects ADD COLUMN IF NOT EXISTS chat JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS oncall_log JSONB NOT NULL DEFAULT '[]'::jsonb;
