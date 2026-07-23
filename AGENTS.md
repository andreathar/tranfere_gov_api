# AGENTS.md — TransfereGov API

Projeto Python para extração, validação e análise de Planos de Ação do
sistema Transferegov (Transferências Especiais / Emendas Pix) do Governo Federal.

## Comandos Essenciais

```bash
# Ativar venv
source .venv/bin/activate

# Extração
./run.sh discover                          # listar objetos disponíveis
./run.sh cemiterios                        # extrair objeto 301 (cemitérios)
./run.sh negados                           # extrair negados/perdidos
./run.sh cemiterios --db                   # extrair + salvar no PostgreSQL
./run.sh negados --csv --db               # extrair + CSV + banco
./run.sh all --db                          # todos os objetos + banco

# Extração por programa + situação (API server-side)
python3 src/transferegov_extract.py --objeto all --ano 2026 --programa 25 --situacao-api IMPEDIDO --db --csv

# Relatórios
./run.sh report resumo                     # resumo geral
./run.sh report estado                     # por estado (UF)
./run.sh report negados                    # planos negados
./run.sh report top 10                     # top 10 valores
./run.sh report municipio SP               # planos de um estado
./run.sh report emenda                     # por parlamentar/emenda
./run.sh report sql "SELECT ..."           # query customizada

# Importação manual
./run.sh import                            # importa todos os JSONs

# Banco
psql -U cognee -h 127.0.0.1 -d transferegov_db
```

## Estrutura

```
src/                        Scripts Python
  transferegov_extract.py     CLI principal (EXTRAÇÃO + DB)
  schemas.py                  Pydantic schemas (PlanoAcaoSchema)
  http_cache.py               Cache TTL para requests
  db_import.py                Importação JSON → PostgreSQL
  db_report.py                Relatórios SQL formatados
  extract_cemiterios_*        DEPRECATED (usar genérico)

config/
  settings.py                 Config centralizada (API, DB, paths)

data/
  swagger.yaml                Spec OpenAPI 3.0 (engenharia reversa)
  schema.sql                  Schema PostgreSQL completo
  migration_002_relatorios.sql  Migration: tabelas para relatórios

output/                       Gitignored (xlsx, csv, json, logs)

references/mcp-brasil/        MCP server gov.br (533 tools, referência)
```

## Convenções

- **Language**: Português (comentários, logs, CLI help em PT-BR)
- **Style**: ruff (line-length 99, target py311)
- **Types**: mypy strict
- **Tests**: pytest + pytest-asyncio
- **Config**: tudo em `config/settings.py`, importar via `from config.settings import X`
- **Paths**: usar `config.settings.OUTPUT_*` para saídas, nunca hardcodar
- **Schema**: validar com Pydantic antes de processar
- **DB**: usar `upsert_plano_acao()` para import idempotente
- **Commit**: mensagens em PT-BR, sem emoji

## API

- **Endpoint**: `GET https://especiais.transferegov.sistema.gov.br/.../api/public/plano-acao/listagem`
- **Response key**: `listaPlanosAcao` (NÃO `data`/`content`/`items`)
- **Pagination**: `pageSize=100`, `pageNumber=1..N`, break when empty
- **Auth**: NENHUMA (público)
- **IP restriction**: pode bloquear IPs fora do Brasil (TCP timeout)
- **Timeout**: 60s, retries 3 com backoff exponencial

### Parâmetros de Query (descobertos via URL real)

| Param               | Descrição                                    | Exemplo                  |
|---------------------|----------------------------------------------|--------------------------|
| `objetoExecucao`    | Código do objeto (vazio = todos)             | `301`, `662`, ``         |
| `objetoExecucaoAno` | Ano exercício                                | `2026`                   |
| `programaId`        | ID do programa (25 = Transf. Especiais)     | `25`                     |
| `planoAcaoSituacao` | Situação do plano (underscores)              | `IMPEDIDO`               |
| `planoTrabalhoSituacao` | Situação do plano de trabalho           | `ENVIADO_PARA_ANALISE`   |
| `politicasPublicas` | Código da política pública                   | `4`                      |
| `uf`                | UF do beneficiário                           | `AL`, `SP`               |
| `beneficiario`      | ID do beneficiário                           | `9858`                   |
| `parlamentar`       | ID do parlamentar                            | `4291`                   |
| `emenda`            | ID da emenda                                 | `11228`                  |
| `pageSize`          | Itens por página (máx: 100)                  | `100`                    |
| `pageNumber`        | Página atual (1-indexed)                     | `1`                      |

### Mapeamento Situação (display site → valor API)

| Display no Site                                  | Valor API                           |
|--------------------------------------------------|-------------------------------------|
| Aguardando Ciência                               | `AGUARDANDO_CIENCIA`                |
| Plano de Trabalho em Elaboração/...              | `PLANO_TRABALHO_EM_ELABORACAO`      |
| Ciente                                           | `CIENTE`                            |
| Impedido por Restrição Técnica                   | `IMPEDIDO`                          |
| Impedido por Rejeição do Plano de Trabalho       | `IMPEDIDO_REJEICAO_PLANO_TRABALHO`  |
| Aprovado                                         | `APROVADO`                          |
| Reprovado                                        | `REPROVADO`                         |
| Cancelado                                        | `CANCELADO`                         |
| Em Execução                                      | `EM_EXECUCAO`                       |
| Concluído                                        | `CONCLUIDO`                         |
| Não Cumpriu                                      | `NAO_CUMPROU`                       |

## PostgreSQL

- **Banco**: `transferegov_db` em `127.0.0.1:5432`
- **User**: `cognee` / **Pass**: `cognee`

### Schema (9 tabelas + 5 views)

**Tabelas dimensão**: objetos, programas, beneficiarios, parlamentares, emendas, politicas_publicas, situacoes_map
**Tabela fato**: planos_acao (22 colunas + 3 parseadas)
**Controle**: extract_log

**Views**:
- `v_planos_completo` — join completo com parlamentar + situação display
- `v_negados` — só negados (IMPEDIDO, REPROVADO, CANCELADO, NAO_CUMPROU)
- `v_resumo_por_estado` — por UF + situação
- `v_resumo_por_objeto` — por objeto + total parlamentares
- `v_resumo_por_parlamentar` — totais por parlamentar

**Funções**:
- `upsert_plano_acao()` — importação idempotente
- `parse_emenda()` — extrai emenda, parlamentar e ano do código

## Pitfalls

1. Chave do response é `listaPlanosAcao`, não `data`/`content`
2. `planoTrabalhoSituacao` pode ser `None`
3. `total` no response indica o total real — sempre comparar com acumulado
4. Arrow backend do pandas: usar `.fillna("").astype(str).str.len()` não `.map(len)`
5. Valores monetários vêm como float — usar `pd.to_numeric` antes de exportar
6. IP pode ser bloqueado fora do Brasil — TCP timeout = rede gov.br restrita
7. `--db` é idempotente (upsert) — seguro rodar múltiplas vezes
8. Scripts especializados (extract_cemiterios_*) são DEPRECATED
9. Cache TTL em `output/.http_cache/` — limpar com `cache_clear()`
10. Config centralizada: NUNCA hardcodar URLs/paths nos scripts
11. `IMPEDIDO` = Restrição Técnica, `IMPEDIDO_REJEICAO_PLANO_TRABALHO` = Rejeição
12. Parse de emenda é automático no import (emenda_codigo + parlamentar_nome)

## Referência

- `references/mcp-brasil/` — MCP server com 533 tools para dados gov.br
  - patterns: Pydantic schemas, retry, TTL cache, format_brl()
  - feature `transferegov` usa API PostgREST antiga (diferente da nossa)
  - worth studying: `_shared/http_client.py`, `schemas.py`, `formatting.py`
