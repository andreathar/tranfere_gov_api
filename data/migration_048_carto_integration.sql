-- ============================================================================
-- Migration 048: CARTO integration — read-only role + grants
-- Provides a read-only DB role for external Carto agents to query views/tables
-- IMPORTANT: replace 'changeme' with a strong password and restrict network access
-- ============================================================================

-- Create a read-only role used by Carto agents (change password in production)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carto_reader') THEN
        CREATE ROLE carto_reader WITH LOGIN PASSWORD 'changeme';
    END IF;
END$$;

-- Allow the role to connect to the database
GRANT CONNECT ON DATABASE transferegov_db TO carto_reader;

-- Grant usage on public schema
GRANT USAGE ON SCHEMA public TO carto_reader;

-- Grant SELECT on key views and tables used by Carto graphs
GRANT SELECT ON v_planos_completo TO carto_reader;
GRANT SELECT ON v_planos_enriquecidos TO carto_reader;
GRANT SELECT ON v_resumo_por_estado TO carto_reader;
GRANT SELECT ON v_resumo_por_objeto TO carto_reader;
GRANT SELECT ON v_resumo_por_parlamentar TO carto_reader;
GRANT SELECT ON v_resumo_por_politica_estado TO carto_reader;
GRANT SELECT ON v_resumo_por_objeto_parlamentar TO carto_reader;
GRANT SELECT ON v_ranking_parlamentares_enriquecido TO carto_reader;
GRANT SELECT ON v_parlamentar_municipio TO carto_reader;
GRANT SELECT ON v_negados TO carto_reader;

-- Also grant read access on base tables that may be useful to agents
GRANT SELECT ON beneficiarios TO carto_reader;
GRANT SELECT ON municipios_ibge TO carto_reader;
GRANT SELECT ON planos_acao TO carto_reader;
GRANT SELECT ON parlamentares TO carto_reader;

-- If PostGIS geometries are later added, grant SELECT on spatial columns/views
-- Example (uncomment if municipios_ibge has a geometry column named geom):
-- GRANT SELECT (municipio_id, nome, uf, geom) ON municipios_ibge TO carto_reader;

-- Revoke any superfluous default privileges (safety)
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- Ensure future tables/views grant SELECT to carto_reader (optional)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO carto_reader;

-- Notes for operator: change carto_reader password and restrict DB firewall to Carto IPs.
