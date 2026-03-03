-- Add workspace fields to agent_runs for workspace management and file tree capture
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS workspace_path TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS file_tree JSONB;
