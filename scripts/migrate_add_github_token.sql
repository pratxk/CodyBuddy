-- Migration: add GitHub integration columns to the users table.
--
-- WHY: db/models.py gained `github_token_enc` (the user's GitHub PAT, ENCRYPTED with
-- Fernet — never plaintext) and `github_login` (the cached GitHub username, so /me
-- doesn't call the GitHub API on every request). SQLAlchemy's create_all() only CREATEs
-- missing tables — it never ALTERs an existing one — so the live Neon `users` table
-- needs these ALTERs applied manually.
--
-- HOW TO RUN (Neon): paste into the Neon SQL editor, or:
--   psql "$DATABASE_URL" -f scripts/migrate_add_github_token.sql
-- Idempotent (IF NOT EXISTS) — safe to run more than once.

ALTER TABLE users ADD COLUMN IF NOT EXISTS github_token_enc TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS github_login VARCHAR;
