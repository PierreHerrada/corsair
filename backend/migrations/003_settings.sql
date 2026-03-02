-- Migration: 003_settings
-- Creates the settings table for storing application configuration

CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY,
    key VARCHAR(255) NOT NULL UNIQUE,
    value TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
