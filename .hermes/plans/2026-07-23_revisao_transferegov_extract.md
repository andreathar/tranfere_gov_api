# Plano: Revisão do transferegov_extract.py
# Criado: 2026-07-23
# Status: PENDENTE

## Contexto

O `transferegov_extract.py` foi criado como CLI genérico antes de descobrirmos:
- O banco PostgreSQL (transferegov_db) com schema normalizado
- O mcp-brasil com padrões de arquitetura superiores
- Os 2 scripts especializados (cemiterios + negados) que ainda existem

O script atual funciona, mas precisa de atualizações para estar coerente
com o ecossistema completo do projeto.

## Diagnóstico

### O QUE FUNCIONA BEM ✓
- Paginação correta (pageSize=100, loop break on empty)
- Retry com backoff exponencial
- Filtros por situação (--negados, --situacao)
- Export Excel com auto-width
- Logging estruturado
- Export JSON como backup
- CLI com argparse completo

### O QUE PRECISA MELHORAR

#### 1. FALTA: Flag --db para salvar direto no PostgreSQL
PROBLEMA: Hoje o script só exporta para arquivos. Para popular o banco,
é necessário rodar extração → JSON → db_import (3 passos).
SOLUÇÃO: Adicionar flag --db que chama a função upsert_plano_acao()
direto após extração, eliminando o passo intermediário.

#### 2. FALTA: Validação Pydantic dos registros
PROBLEMA: Os registros são tratados como dicts brutos. Se a API mudar
um campo, o erro só aparece no pandas/excel.
SOLUÇÃO: Criar schema Pydantic (PlanoAcaoSchema) e validar cada
registro antes de processar. Modo warn (log) ou strict (raise).

#### 3. FALTA: Deduplicação antes de exportar
PROBLEMA: Se rodar a mesma extração 2x, o JSON/Excel terá duplicatas.
O banco resolve com upsert, mas os arquivos não.
SOLUÇÃO: Deduplicar por plano_acao_id antes de criar DataFrame.

#### 4. FRACO: HTTP client síncrono (requests)
PROBLEMA: requests é síncrono e menos robusto que httpx.
O mcp-brasil usa httpx com async + retry nativo.
SOLUÇÃO: Considerar migração para httpx (já instalado). Mas manter
compatibilidade — requests funciona, httpx seria melhoria futura.

#### 5. FRACO: Não há cache de requests
PROBLEMA: Se rodar --discover 2x, bate na API 2x desnecessariamente.
SOLUÇÃO: TTL cache em memória (como mcp-brasil faz) ou cache em arquivo.

#### 6. FRACO: Scripts especializados são duplicatas
PROBLEMA: extract_cemiterios_2026_plano_acao.py e _negados.py são 90%
idênticos ao transferegov_extract.py com --objeto 301.
SOLUÇÃO: Depreciar os scripts especializados. Manter só o genérico.
Adicionar aliases no run.sh:
  ./run.sh cemiterios  → transferegov_extract --objeto 301
  ./run.sh negados     → transferegov_extract --objeto 301 --negados

#### 7. FALTA: Resumo com formatação brasileira
PROBLEMA: O resumo mostra valores como 19871146.99 em vez de R$ 19.871.146,99
SOLUÇÃO: Usar formatting.format_brl() do mcp-brasil ou implementar local.

#### 8. FALTA: Modo incremental
PROBLEMA: Toda extração baixa todos os registros. Se já temos dados
de 2026 no banco, não precisamos re-extrair tudo.
SOLUÇÃO: Modo --incremental que primeiro pergunta ao banco "qual o
último registro extraído?" e só pega novos.

## Plano de Ação

### Fase 1: Schema Pydantic + Validação (baixo risco)
- Criar `src/schemas.py` com PlanoAcaoSchema (Pydantic BaseModel)
- Validar registros na extração (modo warn por padrão)
- Atualizar db_import.py para usar o mesmo schema

### Fase 2: Flag --db (médio risco)
- Adicionar --db ao argparse
- Após extração, conectar ao PostgreSQL e chamar upsert_plano_acao
- Log de quantos registros foram importados vs atualizados
- Usar config.settings.DATABASE_URL

### Fase 3: Deduplicação + Resumo formatado (baixo risco)
- Deduplicar por plano_acao_id antes de criar DataFrame
- Formatar valores monetários como R$ no resumo e Excel

### Fase 4: Depreciar scripts especializados (baixo risco)
- Adicionar deprecation warning nos scripts antigos
- Criar aliases no run.sh
- Atualizar README.md

### Fase 5: Cache + Incremental (futuro)
- TTL cache para requests (evitar APIs repetidas)
- Modo --incremental consultando banco antes de extrair
- Opcional: migração para httpx async

## Arquivos Afetados
- src/transferegov_extract.py → principal (Fases 1-4)
- src/schemas.py → novo (Fase 1)
- src/db_import.py → refatorar para usar schema (Fase 1)
- run.sh → aliases (Fase 4)
- README.md → documentação (Fase 4)

## Ordem de Execução
1. Fase 1 → Schema Pydantic (base para tudo)
2. Fase 2 → Flag --db (maior valor)
3. Fase 3 → Deduplicação + formatação
4. Fase 4 → Depreciar especializados
5. Fase 5 → Futuro (cache + incremental)
