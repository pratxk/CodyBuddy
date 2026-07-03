-- Add the version-history column to projects (idempotent).
ALTER TABLE projects ADD COLUMN IF NOT EXISTS versions JSONB NOT NULL DEFAULT '[]'::jsonb;
