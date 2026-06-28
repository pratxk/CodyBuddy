-- Run against Neon after deploying this version.
-- The users table is created automatically by create_tables() on startup.
-- projects.user_id must be added manually since create_all() won't ALTER existing tables.

ALTER TABLE projects ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
CREATE INDEX IF NOT EXISTS ix_projects_user_id ON projects(user_id);
