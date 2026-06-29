-- Migration: add the `role` column to the users table.
--
-- WHY: db/models.py gained a `role` column (default 'user', NOT NULL) to drive
-- the SUPER_ADMIN gate. SQLAlchemy's create_all() only CREATEs missing tables —
-- it never ALTERs an existing one — so the live Neon `users` table needs this
-- ALTER applied manually.
--
-- HOW TO RUN (Neon): paste into the Neon SQL editor, or:
--   psql "$DATABASE_URL" -f scripts/migrate_add_role.sql
-- Idempotent (IF NOT EXISTS) — safe to run more than once.

ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'user' NOT NULL;
