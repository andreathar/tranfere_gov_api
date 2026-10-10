CARTO integration — TransfereGov (quick guide)

Objective
---------
Expose a read-only Postgres connection so Carto agents and Carto-hosted graphs can query TransfereGov data securely.

Quick steps
-----------
1) Create a read-only DB role (migration_048_carto_integration.sql included). Replace the placeholder password and run the migration as DB admin.

2) In Carto (or your Carto-agent configuration) set these env/secrets:
   - CARTO_PG_HOST
   - CARTO_PG_PORT
   - CARTO_PG_DB (default: transferegov_db)
   - CARTO_PG_USER (default: carto_reader)
   - CARTO_PG_PASS (strong password)
   Example connection string: postgresql://carto_reader:STRONGPASSWORD@db.example.org:5432/transferegov_db

3) Recommended objects for Carto agents
   - v_planos_completo: full dataset for table-based widgets and filters
   - v_planos_enriquecidos: enriched rows with IBGE joins (recommended for choropleth by municipio)
   - v_resumo_por_estado, v_resumo_por_objeto, v_resumo_por_parlamentar: aggregates for dashboards
   - v_parlamentar_municipio: top parlamentar×municipio combos
   - beneficiarios, municipios_ibge: base lookup tables

4) Geo / maps
   - Current schema does not include geometry columns. If Carto needs geometries, add a geometry column to municipios_ibge (PostGIS) or create views that return GeoJSON.
   - Example view (PostGIS installed):
     CREATE VIEW v_municipios_geo AS
     SELECT municipio_id, nome, uf, ST_AsGeoJSON(geom)::json AS geojson
     FROM municipios_ibge;
   - Grant SELECT on the view to carto_reader.

5) Security & best practices
   - Use a strong password and rotate regularly. Store secrets in Carto's secret store or the agent runtime.
   - Restrict DB network access to Carto IP ranges or to an allowlist.
   - Provide only SELECT privileges; avoid granting superuser or write access.

6) Troubleshooting & testing
   - Test connection locally with psql using CARTO credentials.
   - If Carto reports missing columns, ensure the view names above exist (see data/migration_008_enriched_views.sql and data/schema.sql).
   - A helper script exists to create/update the carto_reader role if you run it as a DB superuser:
     .venv/bin/python scripts/create_carto_reader.py
     The script will print a generated password and a connection string for Carto.
   - A test script is available to validate Carto credentials and query sample rows:
     .venv/bin/python scripts/test_carto_connection.py
     Requires CARTO_PG_* env vars or CARTO_DATABASE_URL set in the environment.

6b) Registering the connection in CARTO Workspace (API-based)
   - The steps above give Carto Agents / custom scripts a raw Postgres connection
     string. To instead register this DB as a proper data source inside CARTO
     Workspace/Builder, use CARTO's Connections API
     (https://docs.carto.com/carto-for-developers/reference/carto-api/resources-api/connections.md).
   - That API requires an OAuth Access Token (client_credentials grant), not a
     plain API Access Token. Create an M2M OAuth Client under
     Workspace > Developers > Credentials > OAuth Clients.
   - Find your deployment's API Base URL under
     Workspace > Developers > Credentials > API Base URL
     (https://docs.carto.com/carto-user-manual/developers/managing-credentials/api-base-url) —
     e.g. https://gcp-us-east1.api.carto.com for CARTO Cloud US, or
     https://your-tenant-domain.com/api for Self-Hosted.
   - Set env vars and run:
     export CARTO_API_BASE_URL=...
     export CARTO_OAUTH_CLIENT_ID=... CARTO_OAUTH_CLIENT_SECRET=...
     export CARTO_PG_HOST=... CARTO_PG_PORT=... CARTO_PG_DB=...
     export CARTO_PG_USER=carto_reader CARTO_PG_PASS=...   # from create_carto_reader.py
     .venv/bin/python scripts/register_carto_connection.py
   - IMPORTANT: CARTO Cloud reaches your database from region-specific static
     IPs, not from Carto Agent runtimes. Allowlist those IPs on the DB firewall
     first (see CARTO's IP allowlisting guide) — correct credentials alone will
     not connect otherwise.

7) Sample Carto SQL & widget examples
   - Basic table source (SQL datasource in Carto):
     SELECT * FROM v_planos_enriquecidos WHERE beneficiario_uf = 'SP'

   - Aggregation for choropleth by UF:
     SELECT beneficiario_uf AS uf, SUM(valor_total) AS valor_total
     FROM v_planos_enriquecidos
     GROUP BY beneficiario_uf

   - Top parlamentares for a widget:
     SELECT parlamentar_nome, SUM(valor_total) AS valor_total
     FROM v_planos_enriquecidos
     GROUP BY parlamentar_nome
     ORDER BY valor_total DESC
     LIMIT 50

8) Onboarding checklist
   - Run migration data/migration_048_carto_integration.sql (DBA) or run scripts/create_carto_reader.py as superuser.
   - Store generated connection string in Carto secrets.
   - Set CARTO_PG_* env vars in Carto agent runtime or use CARTO_DATABASE_URL.
   - Test with .venv/bin/python scripts/test_carto_connection.py
   - Allowlist CARTO's static IPs for your region on the DB firewall.
   - (Optional, for CARTO Workspace/Builder) Register the connection via the API:
     .venv/bin/python scripts/register_carto_connection.py (see section 6b).
   - Create datasets/widgets in Carto using the sample SQL above.

9) Mapas por RA do DF (polígonos) — tabela transferegov_df_ra_poligonos
   - Tabela BigQuery no CARTO DW (dataset privado):
     carto-dw-ac-xx7br32v.private_andreabenathar_a5f83fac.transferegov_df_ra_poligonos
   - Schema: ra_codigo INT64, nome_ra STRING, populacao_est INT64,
     area_km2 FLOAT64, densidade FLOAT64, latitude FLOAT64, longitude FLOAT64,
     geom GEOGRAPHY.
   - Fonte dos polígonos: camada oficial GDF/IBRAM 2025
     "Territorio/Regioes_Administrativas_DF_2025" (ArcGIS REST, 35 RAs),
     baixada em f=geojson e cacheada em data/carto_exports/ra_boundaries_raw.geojson.
     Data da extração: 2026-08-21.
   - Demografia: tabela local df_regioes_administrativas (PostgreSQL), casamento
     por nome normalizado + aliases (Sobradinho I -> Sobradinho;
     Sol Nascente/Pôr do Sol -> Sol Nascente e Pôr do Sol; Setor de Industrias -> SIA).
   - Cobertura atual: 35 linhas, todas com geom e demografia — exceto Água
     Quente (RA institucionalizada após o Censo 2022, sem contagem própria;
     ver migration_052_df_ra_data_fix.sql). df_regioes_administrativas foi
     corrigida (migration_052) para casar 1:1 com as 35 RAs oficiais: removidas
     6 linhas indevidas (municípios de Goiás e duplicatas — Águas Lindas de
     Goiás, Novo Gama, Iguatemi, Miguel Couto, Ponte Alta, Sobradinho I) e
     adicionadas as 6 RAs oficiais que faltavam (Brazlândia, Arniqueira, SCIA,
     Riacho Fundo II, Varjão, Água Quente), com área/centroide calculados a
     partir do próprio polígono oficial (ST_AREA/ST_CENTROID) e população do
     Censo 2022 IBGE/Codeplan.
   - Regeneração (idempotente, CREATE OR REPLACE):
     .venv/bin/python scripts/push_ra_poligonos_carto.py [--dry-run]
     Requer CARTO_API_KEY no .env. Retry automático para falhas transitórias de rede.
   - SQL de exemplo para Builder/choropleth:
     SELECT nome_ra, populacao_est, densidade, area_km2, geom
     FROM `carto-dw-ac-xx7br32v.private_andreabenathar_a5f83fac.transferegov_df_ra_poligonos`
     ORDER BY populacao_est DESC
   - Viewer 3D standalone (deck.gl + MapLibre, sem build): abra
     data/carto_exports/mapa_ra_3d.html no navegador. A chave é solicitada na
     primeira abertura e guardada em localStorage ('carto_api_key'); botão 🔑 troca a chave.

10) Mapas cruzados: RA × Deputados Distritais (CLDF) — transferegov_df_ra_deputados_cldf
    - Tabela BigQuery no CARTO DW (dataset privado):
      carto-dw-ac-xx7br32v.private_andreabenathar_a5f83fac.transferegov_df_ra_deputados_cldf
    - Estende a tabela de polígonos (seção 9) com resumo de emendas
      orçamentárias da CLDF por RA (total_emendas, vl_emenda, vl_empenhado,
      vl_liquidado) e os 5 deputados distritais mais atuantes por RA
      (dep1..dep5: nome, partido, total de proposições), calculados por
      total_deputados_atuantes.
    - Fonte: tabelas cldf_deputado_ra_impacto e cldf_ra_emendas_resumo,
      populadas por .venv/bin/python -m src.enrichers.deputado_ra_impacto
      (casamento de cldf_proposicoes.regiao_admin / autor_nome e
      cldf_emendas.nome_uo com df_regioes_administrativas). Rodar o enricher
      ANTES deste script sempre que cldf_proposicoes/cldf_emendas forem
      atualizadas.
    - Regeneração (idempotente, CREATE OR REPLACE):
      .venv/bin/python -m src.enrichers.deputado_ra_impacto
      .venv/bin/python scripts/push_ra_deputados_carto.py [--dry-run]
    - Viewer 3D standalone: data/carto_exports/mapa_ra_deputados_3d.html —
      toggle Emendas/Liquidado/Deputados Atuantes/População, tooltip lista os
      deputados mais atuantes por RA com partido e nº de proposições.
    - Gráficos no dashboard Dash (`src/graphs/df_ra_deputados_cldf.py`):
      df_ra_mapa_emendas_cldf, df_ra_ranking_deputados_cldf,
      df_ra_tabela_emendas_deputados.

Contact
-------
For help, run: .venv/bin/python src/db_report.py to preview views and sample rows, or open an issue in the repo.
