"""
Enrichers — Módulo de enriquecimento de dados via APIs externas.

Usa mcp-brasil como biblioteca Python (NÃO via protocolo MCP).
Fluxo: dados já extraídos → PostgreSQL → enriquecer com APIs externas.

Uso:
    python3 -m src.enrichers.validacao    # validar CNPJs
    python3 -m src.enrichers.ibge         # dados IBGE dos municípios
    python3 -m src.enrichers.camara       # perfil dos parlamentares
    python3 -m src.enrichers.pipeline     # todas as fases
"""
