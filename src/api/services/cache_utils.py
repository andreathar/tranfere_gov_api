"""
Cache compartilhado para agregados analíticos da API.

Queries agregadas caras (rankings, resumos, KPIs) são cacheadas em memória
com TTL curto (5 min) para suportar picos de leitura sem bater no PostgreSQL
a cada request. Os enrichers chamam `invalidate_analytics_cache()` ao final
do pipeline para que novos dados apareçam imediatamente.
"""

from __future__ import annotations

from cachetools import TTLCache

# maxsize=64, ttl=300s — suficiente para dezenas de agregados distintos
ANALYTICS_CACHE: TTLCache = TTLCache(maxsize=64, ttl=300)


def invalidate_analytics_cache() -> None:
    """Limpa o cache de agregados (chamado pelos enrichers pós-import)."""
    ANALYTICS_CACHE.clear()
