-- migration_001_track.sql: tabela de tracking de migrations aplicadas.
-- Aplicada automaticamente por scripts/db_migrate.sh (idempotente).
-- As migrations 002-039 são registradas aqui quando aplicadas.

SET client_min_messages = warning;

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ DEFAULT NOW()
);
