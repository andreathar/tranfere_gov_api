"""
Cache TTL simples para requests HTTP.

Evita bater na API do governo repetidamente.
Cache em arquivo JSON com expiração.
Capacidade máxima: 2000 entradas (LRU por arquivo mais antigo).
"""

import json
import time

from config.settings import OUTPUT_DIR

CACHE_DIR = OUTPUT_DIR / ".http_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TTL = 300  # 5 minutos
MAX_CACHE_ENTRIES = 2000


def _evict_oldest_if_needed():
    """Remove arquivos mais antigos quando cache excede MAX_CACHE_ENTRIES."""
    files = sorted(CACHE_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    if len(files) <= MAX_CACHE_ENTRIES:
        return
    to_remove = files[: len(files) - MAX_CACHE_ENTRIES]
    for f in to_remove:
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass


def _cache_key(url: str, params: dict) -> str:
    """Gera chave de cache a partir de URL + params."""
    import hashlib
    key_data = f"{url}?{json.dumps(params, sort_keys=True)}"
    return hashlib.md5(key_data.encode()).hexdigest()


def cache_get(url: str, params: dict, ttl: int = DEFAULT_TTL) -> dict | None:
    """Busca no cache. Retorna dict com 'data' se válido, None se expirado."""
    key = _cache_key(url, params)
    cache_file = CACHE_DIR / f"{key}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file) as f:
            entry = json.load(f)

        if time.time() - entry.get("ts", 0) > ttl:
            cache_file.unlink(missing_ok=True)
            return None

        return entry.get("data")  # type: ignore[no-any-return]
    except (json.JSONDecodeError, KeyError):
        cache_file.unlink(missing_ok=True)
        return None


def cache_set(url: str, params: dict, data: dict) -> None:
    """Salva no cache com eviction automática."""
    key = _cache_key(url, params)
    cache_file = CACHE_DIR / f"{key}.json"

    entry = {"ts": time.time(), "data": data}
    with open(cache_file, "w") as f:
        json.dump(entry, f)

    _evict_oldest_if_needed()


def cache_clear() -> int:
    """Limpa todo o cache. Retorna número de arquivos removidos."""
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count
