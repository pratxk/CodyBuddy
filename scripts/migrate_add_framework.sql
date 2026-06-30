-- Migration: add the `framework` column to the projects table.
--
-- WHY: db/models.py gained `framework` ("react" | "static" | "nextjs") so a
-- generated app records which framework it was built as. SQLAlchemy's
-- create_all() only CREATEs missing tables — it never ALTERs an existing one —
-- so the live Neon `projects` table needs this ALTER applied manually.
--
-- HOW TO RUN (Neon): paste into the Neon SQL editor, or:
--   psql "$POSTGRES_URL" -f scripts/migrate_add_framework.sql
-- Idempotent (IF NOT EXISTS) — safe to run more than once.

ALTER TABLE projects ADD COLUMN IF NOT EXISTS framework TEXT NOT NULL DEFAULT 'react';
