-- Initialize Zorix Agent Database
-- This script sets up the initial database schema and users

-- Create additional databases if needed
CREATE DATABASE IF NOT EXISTS grafana;

-- Create users for different services
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'grafana') THEN
        CREATE USER grafana WITH PASSWORD 'grafana_password';
    END IF;
END
$$;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE grafana TO grafana;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create initial tables for application metadata
CREATE TABLE IF NOT EXISTS app_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(255) UNIQUE NOT NULL,
    value JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create table for deployment tracking
CREATE TABLE IF NOT EXISTS deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version VARCHAR(100) NOT NULL,
    environment VARCHAR(50) NOT NULL,
    deployed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deployed_by VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB
);

-- Insert initial metadata
INSERT INTO app_metadata (key, value) VALUES 
    ('version', '"1.0.0"'),
    ('initialized_at', to_jsonb(NOW())),
    ('schema_version', '1')
ON CONFLICT (key) DO NOTHING;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_app_metadata_key ON app_metadata(key);
CREATE INDEX IF NOT EXISTS idx_deployments_environment ON deployments(environment);
CREATE INDEX IF NOT EXISTS idx_deployments_deployed_at ON deployments(deployed_at);

-- Create function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for app_metadata
DROP TRIGGER IF EXISTS update_app_metadata_updated_at ON app_metadata;
CREATE TRIGGER update_app_metadata_updated_at
    BEFORE UPDATE ON app_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();