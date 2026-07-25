---
name: transferegov-enrichment
description: Pipeline de enriquecimento com IBGE, BrasilAPI e Câmara.
---

# Transferegov Enrichment Skill

Pipeline de Pós-Extração (Requer DB populado). Este processo demora para rodar pois cruza milhares de dados com serviços externos.

## Como rodar
- Dry-run geral (só mostrar o que vai fazer):
  `python3 -m src.enrichers.pipeline --fase all --dry-run`
- Pipeline de Validação CNPJ e IBGE (Fase 1):
  `python3 -m src.enrichers.validacao --limit 100`
- Perfil Parlamentares (Fase 2):
  `python3 -m src.enrichers.camara --limit 100`
- Pipeline Total em Lote:
  `python3 -m src.enrichers.pipeline --fase all`

Em caso de `ENRICH_RATE_LIMIT`, lembre-se que o limite padrão é 0.2 requests/s.
