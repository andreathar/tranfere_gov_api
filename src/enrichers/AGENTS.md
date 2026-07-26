# AGENTS.md — src/enrichers

Pipeline de enriquecimento de dados do TransfereGov. Cada script roda como módulo independente via `python3 -m src.enrichers.<script>`.

---

## Arquitetura

```
pipeline.py  ← orquestrador, executa fases via subprocess
    │
    ├── Fase 1: validacao.py → ibge.py → mapear_municipios.py → ibge_agregados.py
    ├── Fase 1e: siconfi.py (dados financeiros municipais)
    ├── Fase 2: camara.py
    └── Fase 3: SQL JOIN direto no pipeline.py
```

**Requisito**: banco `transferegov_db` populado via extração (`transferegov_extract.py --db`) antes de rodar qualquer enricher.

---

## Scripts por Fase

| Fase | Script | Fonte Externa | Tabela Destino | O que faz |
|------|--------|---------------|----------------|-----------|
| 1a | `validacao.py` | BrasilAPI (CNPJ) | `validacao_cnpj` | Valida situação cadastral dos CNPJs |
| 1b | `ibge.py` | IBGE API (localidades) | `municipios_ibge` | Lista municípios por UF (nomes, códigos, geo) |
| 1c | `mapear_municipios.py` | Match fuzzy (normalize) | `beneficiario_ibge_map` | Liga beneficiários a códigos IBGE |
| 1d | `ibge_agregados.py` | IBGE API (agregados v3) | `municipios_ibge` (colunas extras) | População, PIB, área territorial |
| 1e | `siconfi.py` | SICONFI/Tesouro Nacional (DCA + RREO A03) | `municipios_financeiro` | Dados financeiros + arrecadação de impostos (IPTU/ISS/ICMS/FPM) |
| 2 | `camara.py` | Câmara dos Deputados | `parlamentares_dados` | Perfil completo dos deputados autores |
| 3 | `pipeline.py` (--fase 3) | SQL JOIN | `parlamentar_beneficiario` | Agrega valor total por parlamentar×município×emenda |

### Scripts auxiliares

| Script | Descrição |
|--------|-----------|
| `completar_deputados.py` | Busca partido para deputados que faltam (API Câmara) |
| `discricionarias_sync.py` | Sincroniza emendas discricionárias (Portal Transparência API) |

---

## Comandos

```bash
# Pipeline completo
python3 -m src.enrichers.pipeline --fase all [--dry-run] [--limit N]

# Fases individuais
python3 -m src.enrichers.pipeline --fase 1 [--dry-run]  # Validação + IBGE
python3 -m src.enrichers.pipeline --fase 2 [--dry-run]  # Câmara
python3 -m src.enrichers.pipeline --fase 3 [--dry-run]  # Vinculação

# Scripts avulsos
python3 -m src.enrichers.validacao [--dry-run] [--limit N]
python3 -m src.enrichers.ibge [--dry-run] [--uf UF]
python3 -m src.enrichers.ibge_agregados [--dry-run] [--uf UF] [--limit N]
python3 -m src.enrichers.siconfi [--dry-run] [--uf UF] [--limit N] [--ano ANO] [--rreo]
python3 -m src.enrichers.mapear_municipios [--dry-run]
python3 -m src.enrichers.camara [--dry-run] [--limit N]
python3 -m src.enrichers.completar_deputados
python3 -m src.enrichers.discricionarias_sync
```

---

## Convenções deste módulo

- **Idioma**: Português (comentários, logs, output)
- **Dry-run**: Todo script aceita `--dry-run` — mostra o que faria sem escrever no DB
- **Rate limit**: Respeitar `ENRICH_RATE_LIMIT` (0.2s entre requests) — não sobrecarregar APIs externas
- **Batch**: Processar em lotes de `ENRICH_BATCH_SIZE` (50 registros)
- **Cache**: Usar `http_cache.py` para requests HTTP — TTL `ENRICH_CACHE_TTL` (3600s)
- **DB**: Usar `psycopg2` direto (sem ORM), imports de `config.settings`
- **Imports**: `sys.path.append` no `discricionarias_sync.py` (único outlier — considerar corrigir)
- **Fase 3**: SQL INSERT...ON CONFLICT (upsert) — idempotente, seguro re-executar

---

## Pitfalls

1. `mapear_municipios.py` usa normalização Unicode para fuzzy match — funciona para acentos/abreviações, mas pode falhar para nomes muito diferentes
2. `camara.py` usa `requests` (síncrono) — outros usam `httpx` ou `psycopg2`
3. `discricionarias_sync.py` usa `sys.path.append` para importar config — não é padrão do projeto
4. Rate limit entre requests: mínimo 0.2s — APIs do governo bloqueiam IP por excesso
5. `pipeline.py --fase 3` roda SQL direto (não subprocesso) — único enricher que não delega
6. Dry-run não garante que APIs externas não serão chamadas — mostra output mas não bloqueia HTTP
7. `ibge_agregados.py` requer migration_004 aplicada (colunas populacao, pib, area_km2) e `ibge.py` rodado antes (popula municipios_ibge com códigos)
8. `siconfi.py` requer migration_007 + migration_012 aplicadas (tabelas municipios_financeiro + colunas arrec_*) e `ibge.py` rodado antes (popula municipios_ibge com codigos)
9. `siconfi.py` tem rate limit próprio de 1 req/s — SICONFI bloqueia IP por excesso de requests
10. DCA (Declaração de Contas Anuais) costuma ter 1-2 anos de atraso — o script tenta automaticamente 2025→2023 quando `--ano` não é informado
11. RREO Anexo 03 (`--rreo`) contém arrecadação de impostos por município — usa `nr_periodo=6` (consolidação anual, 6º bimestre)
12. RREO retorna texto com acentos (ex: 'Transferências') — o parser usa `unicodedata.normalize('NFKD')` para normalizar

---

## Tabelas de banco usadas

**Leitura**: `planos_acao`, `beneficiarios`, `parlamentares`, `objetos`, `programas`
**Escrita**: `validacao_cnpj`, `municipios_ibge`, `beneficiario_ibge_map`, `parlamentares_dados`, `parlamentar_beneficiario`, `municipios_financeiro`

Schema completo em `data/migration_002_relatorios.sql`.
