# Plano de Implementação: Integração mcp-brasil → TransfereGov
# Status: PENDENTE
# Criado: 2026-07-23
# Baseado em: MCP_BRASIL_INTEGRATION_PLAN.md (revisado)

## Diagnóstico do Plano Original

O plano original tem 3 problemas estruturais:

1. **API errada**: Propõe usar `transferegov_buscar_emendas_pix` do mcp-brasil,
   que usa a API PostgREST ANTIGA (`api.transferegov.gestao.gov.br`).
   Nós já temos a API pública NOVA (`especiais.transferegov.sistema.gov.br`)
   com mais campos e filtros. Usar o mcp-brasil para transferegov seria
   um downgrade.

2. **Cliente MCP desnecessário**: O plano cria um `MCPBrasilClient` via protocolo
   MCP (stdio). Mas o mcp-brasil já está instalado como pacote editável —
   podemos chamar as functions diretamente via Python, sem protocolo MCP.

3. **Conflito com código existente**: Propõe criar `src/mcp_integration/` que
   duplica funções que já existem em `src/transferegov_extract.py` e
   `src/db_import.py`.

## Estratégia Correta

O mcp-brasil é útil para ENRIQUECER os dados que já extraímos,
NÃO para extraí-los. O fluxo é:

  [Nossa API] → extrair planos → [Banco PostgreSQL] → [mcp-brasil] → enriquecer

Usamos o mcp-brasil para:
  - Dados IBGE (população, PIB, região dos municípios)
  - Dados Câmara/Senado (perfil dos parlamentares)
  - Validação CNPJ (BrasilAPI)
  - Auditoria TCU (sanções)
  - Dados TSE (perfil eleitoral)

NÃO usamos para:
  - Extração de planos (já temos API melhor)
  - Dados de transferegov (duplicaria nosso trabalho)

## Arquitetura

```
tranfere_gov_api/
├── src/
│   ├── transferegov_extract.py    (EXISTENTE — não modificar)
│   ├── db_import.py               (EXISTENTE — não modificar)
│   ├── db_report.py               (EXISTENTE — não modificar)
│   ├── dashboard.py               (EXISTENTE — não modificar)
│   ├── schemas.py                 (EXISTENTE — não modificar)
│   ├── http_cache.py              (EXISTENTE — não modificar)
│   └── enrichers/                 (NOVO — módulo opcional)
│       ├── __init__.py
│       ├── ibge.py                Fase 1: dados municipais
│       ├── camara.py              Fase 2: perfil parlamentar
│       ├── validacao.py           Fase 1: CNPJ + totais
│       ├── auditoria.py           Fase 3: TCU/sanções
│       └── pipeline.py            Fase 3: orquestração
├── config/
│   └── settings.py                (ATUALIZAR — adding enricher configs)
├── data/
│   ├── schema.sql                 (ATUALIZAR — adding new tables)
│   └── migration_003_enrichment.sql  (NOVO)
└── run.sh                         (ATUALIZAR — adding enrich command)
```

## FASE 1 — Validação & Enriquecimento Imediato

### 1.1 Validador de CNPJs (BrasilAPI)
- Script standalone: `src/enrichers/validacao.py`
- Valida CNPJs dos beneficiários via BrasilAPI
- Adiciona coluna `cnpj_valido` ao DataFrame
- Salva resultados em tabela `validacao_cnpj`
- Custo: 1 request por CNPJ (~4120 únicos)

### 1.2 Enriquecimento IBGE
- Script standalone: `src/enrichers/ibge.py`
- Busca dados IBGE para cada município beneficiário
- Adiciona: população, PIB per capita, região, mesorregião
- Salva em tabela `municipios_enriquecidos`
- Custo: 1 request por UF (27 requests)

### 1.3 Validação Cruzada de Totais
- Compara total extraído vs. API PostgREST (mcp-brasil)
- Apenas para conferência, NÃO para extração
- Salva resultado em `extract_log`

**Arquivos novos:**
  src/enrichers/__init__.py
  src/enrichers/validacao.py
  src/enrichers/ibge.py

**Arquivos modificados:**
  config/settings.py (adicionar MCP_BRASIL_* configs)
  data/migration_003_enrichment.sql (novas tabelas)

## FASE 2 — Perfil de Parlamentares

### 2.1 Dados Câmara dos Deputados
- Para cada parlamentar único no banco:
  - Buscar dados via mcp-brasil (`camara_deputados`)
  - Nome, partido, UF, gabinete, rede social
- Salva em tabela `parlamentares_dados`

### 2.2 Dados TSE (Perfil Eleitoral)
- Para cada parlamentar:
  - Buscar último mandato via mcp-brasil (`tse_candidatos`)
  - Coligação, bens, doações
- Salva em tabela `parlamentares_tse`

### 2.3 Despesas Parlamentares
- Buscar despesas da Câmara para 2026
- Cruzar com valor total de emendas
- Identificar parlamentares com maior destaque

**Arquivos novos:**
  src/enrichers/camara.py

**Tabelas novas:**
  parlamentares_dados (nome, partido, uf, gabinete, ...)
  parlamentares_tse (candidato_id, ano, coligacao,bens, ...)

## FASE 3 — Auditoria & Pipeline

### 3.1 Auditoria TCU
- Verificar beneficiários com sanções
- Verificar parlamentares inabilitados
- Cruzar com dados de execução

### 3.2 Pipeline de Enriquecimento
- Script orquestrador: `src/enrichers/pipeline.py`
- Roda todas as fases em sequência
- Progress bar + logging
- Idempotente (não reprocessa dados já enriquecidos)

### 3.3 Dashboard Enriquecido
- Atualizar `src/dashboard.py` para incluir:
  - Dados demográficos (IBGE)
  - Perfil dos parlamentares (Câmara/TSE)
  - Alertas de auditoria (TCU)

**Arquivos novos:**
  src/enrichers/auditoria.py
  src/enrichers/pipeline.py

## Ordem de Implementação (sem conflitos)

```
Semana 1:
  [ ] Criar src/enrichers/__init__.py
  [ ] Criar migration_003_enrichment.sql
  [ ] Atualizar config/settings.py (configs MCP)
  [ ] Implementar validação CNPJ (validacao.py)
  [ ] Testar com 10 CNPJs

Semana 2:
  [ ] Implementar enriquecimento IBGE (ibge.py)
  [ ] Rodar para todos os 4120 municípios
  [ ] Atualizar dashboard com dados IBGE

Semana 3:
  [ ] Implementar perfil Câmara (camara.py)
  [ ] Rodar para 470 parlamentares
  [ ] Atualizar schema com tabelas novas

Semana 4:
  [ ] Implementar auditoria TCU (auditoria.py)
  [ ] Criar pipeline orquestrador (pipeline.py)
  [ ] Atualizar run.sh com comandos enrich/audit
  [ ] Atualizar AGENTS.md e skill
```

## Configuração Necessária

Adicionar em config/settings.py:
```python
# mcp-brasil integration (opcional)
MCP_BRASIL_ENABLED = os.getenv("MCP_BRASIL_ENABLED", "false").lower() == "true"
MCP_BRASIL_CACHE_TTL = 3600  # 1 hora
MCP_BRASIL_RATE_LIMIT = 10   # req/s
```

Adicionar em .env (opcional):
```
MCP_BRASIL_ENABLED=true
```

## Comandos Novos (run.sh)

```bash
./run.sh enrich validate      # validar CNPJs
./run.sh enrich ibge           # enriquecer municípios
./run.sh enrich camara         # perfil parlamentares
./run.sh enrich all            # todas as fases
./run.sh audit tcu             # auditoria TCU
```

## Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Rate limit APIs externas | Cache TTL + sleep entre requests |
| APIs indisponíveis | Retry com backoff + modo offline |
| Dados inconsistentes | Validação Pydantic antes de salvar |
| Conflito com código existente | Módulo isolado em src/enrichers/ |
| Credenciais API | Usar .env, nunca hardcodar |

## Dependências Novas

Nenhuma dependência nova necessária — mcp-brasil já está instalado.
Apenas usar as functions diretamente via Python:
```python
from mcp_brasil.data.ibge.client import buscar_municipios
from mcp_brasil.data.camara.client import buscar_deputado
```

## Validação

Cada fase deve:
1. Ter testes unitários
2. Ser idempotente (rodar múltiplas vezes sem duplicar)
3. Ter modo dry-run (log sem escrever no banco)
4. Salvar metadados em extract_log
