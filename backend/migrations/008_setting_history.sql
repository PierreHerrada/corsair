CREATE TABLE IF NOT EXISTS setting_history (
    id UUID PRIMARY KEY,
    setting_key VARCHAR(255) NOT NULL,
    old_value TEXT NOT NULL DEFAULT '',
    new_value TEXT NOT NULL DEFAULT '',
    change_source VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_setting_history_key ON setting_history (setting_key);
CREATE INDEX idx_setting_history_created ON setting_history (created_at);
