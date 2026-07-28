# TransfereGov API — Extração, Validação, Enriquecimento e Análise de Emendas Pix

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checking: MyPy](https://img.shields.io/badge/type%20checking-mypy-blue.svg)](https://mypy-lang.org/)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![CI/CD](https://github.com/andretwl/tranfere_gov_api/actions/workflows/ci.yml/badge.svg)](https://github.com/andretwl/tranfere_gov_api/actions)

Projeto Python de engenharia de dados e inteligência parlamentar para extração, validação, enriquecimento e análise dos **Planos de Ação** do sistema **Transferegov.br** (Transferências Especiais / Emendas Pix do Governo Federal).

---

## 📌 Visão Geral & Arquitetura

O sistema implementa uma pipeline completa em 8 fases + RAG:

1. **Extração**: Coleta resiliente de dados via API pública do Transferegov com paginação e backoff exponencial.
2. **Validação Pydantic**: Normalização e validação de schemas com `Pydantic v2`.
3. **Persistência PostgreSQL**: Carga idempotente via `upsert_plano_acao()` com schema relacional normalizado.
4. **Enriquecimento Multi-Fonte** (25+ módulos):
   - **Fase 1**: Validação CNPJ (BrasilAPI), Dados IBGE, Mapeamento de municípios, Dados IBGE Agregados, Dados Fiscais SICONFI.
   - **Fase 2**: Perfis e Acompanhamento Legislativo de Deputados (Câmara dos Deputados).
   - **Fase 3**: Vinculação agregada Parlamentar × Beneficiário × Emenda.
   - **Fase 7a/7b**: Dados TSE de Prefeitos e Vereadores eleitos.
   - **Fase 8**: Perfil de Senadores em exercício (API Senado).
   - **Complementares**: Compras (FNDE/TCU), DataJud, Diário Oficial, Saúde/Educação, Proposições, Votações.
5. **Pipeline RAG v3**: Indexação vetorial (Qdrant) e geração de personas com Multi-Query (5 perspectivas temáticas).
6. **Integração LocalAI**: Gerenciamento de modelos locais (Gemma, Qwen, Llama) via API compatível OpenAI — com gerenciamento de VRAM.
7. **Visualização & Servidor MCP**:
   - **Plotly Dash**: 68 gráficos analíticos interativos (17 módulos) na porta `8050`.
   - **Servidor MCP Hub**: Endpoint MCP nativo (`/_mcp`) para Agentes de IA autônomos.
8. **Painel Web FastAPI**: 38 endpoints REST + SPA para inteligência parlamentar e municipal.

```
[ API TransfereGov ] ──► [ Extração & Pydantic ] ──► [ PostgreSQL ]
                                                          │
   ┌──────────────────────┬───────────────────────┬────────┴────────────────────────────────────────────────┐
   ▼                      ▼                       ▼                                                        ▼
[ Enriquecimento ]   [ RAG v3 (Qdrant) ]   [ LocalAI (GPU) ]              [ Dash 68 charts + MCP ]
[ 25+ fontes ]       + Persona (LLM)       Gemma / Qwen / Llama            Porta 8050 /_mcp
                                  │                │
                                  └────────┬───────┘
                                           ▼
                              [ FastAPI Web App — Porta 8080/8000 ]
```

---

## 📁 Estrutura do Projeto

```
tranfere_gov_api/
├── src/                          # Módulos Python principais
│   ├── transferegov_extract.py   # CLI Principal de extração e carga no DB
│   ├── db_import.py              # Importador JSON → PostgreSQL
│   ├── db_report.py              # Relatórios SQL formatados
│   ├── db_utils.py               # Utilitários centralizados de conexão DB
│   ├── formatters.py             # Formatação de moeda e porcentagens
│   ├── schemas.py                # Schemas de validação Pydantic
│   ├── dash_app.py               # Servidor Plotly Dash & MCP Server Hub (Porta 8050)
│   ├── graph_tools.py            # Ferramentas MCP customizadas (@mcp_enabled)
│   ├── graph_factory.py          # Shim backward-compat → src.graphs
│   ├── verify_graphs.py          # Suíte de auditoria e verificação de gráficos
│   ├── deputado_followup.py      # CLI interativo de inteligência parlamentar
│   ├── prefeito_followup.py      # CLI interativo de inteligência municipal
│   ├── redator_transferegov.py   # Redator oficial de documentos (nota-técnica, ofício, parecer)
│   ├── localai_manager.py        # Gerenciamento de VRAM e modelos LocalAI
│   ├── localai_client.py         # Cliente HTTP para API LocalAI
│   ├── mcp_tool_bridge.py        # Bridge MCP ↔ ferramentas externas
│   │
│   ├── api/                      # Aplicação Web FastAPI (38 endpoints)
│   │   ├── app.py                # App FastAPI principal
│   │   ├── routes/               # Endpoints REST
│   │   │   ├── deputados.py      # /api/v1/deputados/* (perfil, emendas, despesas, comissões, votações)
│   │   │   ├── prefeitos.py      # /api/v1/prefeitos/*
│   │   │   ├── vereadores.py     # /api/v1/vereadores/*
│   │   │   ├── analytics.py      # /api/v1/analytics/*
│   │   │   ├── compras.py        # /api/v1/compras/*
│   │   │   ├── auditoria.py      # /api/v1/auditoria/*
│   │   │   ├── diario.py         # /api/v1/diario/*
│   │   │   └── fnde.py           # /api/v1/fnde/*
│   │   └── services/             # Regras de negócio e integração
│   │       ├── db_service.py     # Acesso centralizado ao banco
│   │       ├── camara_service.py # Integração API Câmara dos Deputados
│   │       ├── analytics_service.py # Lógica de agregações analíticas
│   │       └── mcp_service.py    # Serviços MCP
│   │
│   ├── enrichers/                # Pipeline de Enriquecimento (25+ módulos)
│   │   ├── pipeline.py           # Orquestrador do enriquecimento (fases 1-3)
│   │   ├── validacao.py          # Fase 1a: CNPJ via BrasilAPI
│   │   ├── ibge.py               # Fase 1b: Dados locais IBGE
│   │   ├── ibge_agregados.py     # Fase 1d: População, PIB, área
│   │   ├── mapear_municipios.py  # Fase 1c: Fuzzy match → código IBGE
│   │   ├── siconfi.py            # Fase 1e: SICONFI (DCA + RREO)
│   │   ├── camara.py             # Fase 2: Perfis de Deputados
│   │   ├── tse_prefeitos.py      # Fase 7a: Prefeitos eleitos (TSE)
│   │   ├── tse_vereadors.py      # Fase 7b: Candidatos a vereador (TSE)
│   │   ├── tse_deputados.py      # Dados TSE de deputados
│   │   ├── senado.py             # Fase 8: Senadores (API Senado)
│   │   ├── completar_deputados.py # Enriquecimento complementar
│   │   ├── compras.py            # Compras públicas
│   │   ├── datajud.py            # Dados judiciais (DataJud/CNJ)
│   │   ├── discricionarias_sync.py # Emendas discricionárias
│   │   ├── fnde.py               # Dados FNDE (educação)
│   │   ├── saude_educacao.py     # Saúde e educação
│   │   ├── sync_proposicoes.py   # Proposições legislativas
│   │   ├── tcu_compras.py        # Compras TCU
│   │   ├── votacoes_camara.py    # Votações da Câmara
│   │   ├── votacoes_temas.py     # Temas das votações
│   │   ├── diario_oficial_worker.py # Worker DOU
│   │   ├── rag_persona.py        # Multi-Query RAG (5 perspectivas)
│   │   └── rag_qdrant_indexer.py # Indexador vetorial Qdrant
│   │
│   ├── graphs/                   # Módulos Plotly (17 domínios, 68 gráficos)
│   │   ├── registry.py           # @register_chart decorator + CHART_REGISTRY
│   │   ├── theme.py              # Theme tokens, TODAS_UFS, CORES_SITUACAO
│   │   ├── analitico.py (2)      ├── arrecadacao.py (13)
│   │   ├── economia_cruzada.py (2) ├── economico.py (7)
│   │   ├── financas.py (6)       ├── fiscal.py (3)
│   │   ├── geoespacial.py (3)    ├── hierarquico.py (4)
│   │   ├── impacto_social.py (2) ├── intel_politica.py (5)
│   │   ├── intel_proposicoes.py (1) ├── parlamentar.py (3)
│   │   ├── prefeitos.py (2)      ├── radar_diario.py (1)
│   │   ├── siconfi.py (10)       ├── socioeconomico.py (3)
│   │   └── votacoes.py (1)
│   │
│   └── redator/                  # (legado → src/redator_transferegov.py)
│
├── config/                       # Configuração centralizada
│   └── settings.py               # API, DB, paths, LocalAI, RAG, ENRICH_*
│
├── data/                         # Schemas SQL e Migrations
│   ├── schema.sql                # Schema PostgreSQL core
│   └── migration_*.sql           # Migrações aplicadas
│
├── docs/                         # Documentação do desenvolvedor
│   ├── ONBOARDING.md             # Guia passo a passo de onboarding
│   ├── DEVELOPMENT.md            # Padrões de desenvolvimento e pre-commit
│   ├── MIGRATIONS.md             # Instruções e histórico de migrations
│   ├── LOCALAI.md                # Configuração e modelos LocalAI
│   ├── RAG.md                    # Pipeline RAG v3 com Qdrant
│   ├── REDATOR.md                # Redator oficial de documentos
│   ├── MCP_BRIDGE.md             # Bridge MCP para ferramentas externas
│   └── CRON_JOBS.md              # Jobs agendados (Diário Oficial, Qdrant, Dossiê)
│
├── .github/workflows/ci.yml      # CI/CD Pipeline (GitHub Actions)
├── .pre-commit-config.yaml       # Configuração de ganchos de código (Ruff, MyPy)
├── pyproject.toml                # Dependências, ruff e mypy config
├── requirements.txt              # Dependências pip
└── run.sh                        # Interface CLI rápida (atalhos)
```

---

## ⚡ Pré-requisitos & Instalação

### Pré-requisitos
- **Python 3.11+**
- **PostgreSQL 14+**
- **Git**

### Configuração do Ambiente Local

1. **Clonar o repositório:**
   ```bash
   git clone https://github.com/andretwl/tranfere_gov_api.git
   cd tranfere_gov_api
   ```

2. **Criar e ativar ambiente virtual Python:**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instalar dependências (incluindo pacotes de desenvolvimento):**
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

4. **Configurar o Banco de Dados PostgreSQL:**
   Certifique-se de que o serviço PostgreSQL está em execução e crie o banco de dados e usuário:
   ```sql
   CREATE DATABASE transferegov_db;
   CREATE USER cognee WITH PASSWORD 'cognee';
   GRANT ALL PRIVILEGES ON DATABASE transferegov_db TO cognee;
   ```

   Execute o schema inicial e as migrações:
   ```bash
   psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/schema.sql
   # Executar migrações conforme docs/MIGRATIONS.md
   ```

---

## 🚀 Execução CLI & Pipelines

O projeto fornece o script `./run.sh` como atalho para todas as operações comuns.

### Extração de Dados
```bash
./run.sh discover                          # Listar objetos disponíveis
./run.sh cemiterios --db --csv             # Extrair objeto 301 + banco + CSV
./run.sh negados --db                      # Planos negados/impedidos
./run.sh all --db                          # Todos os objetos 2026 no banco
```

### Importação e Relatórios
```bash
./run.sh import                            # Importar JSONs para o banco
./run.sh report resumo                     # Relatório geral
./run.sh report estado                     # Relatório por estado
./run.sh report negados                    # Planos negados
./run.sh report sql "SELECT ..."           # Query SQL customizada
```

### Enriquecimento Multi-Fonte
```bash
# Pipeline completo (todas as fases)
python3 -m src.enrichers.pipeline --fase all

# Fases individuais
python3 -m src.enrichers.validacao         # Fase 1a: CNPJ BrasilAPI
python3 -m src.enrichers.ibge              # Fase 1b: Dados IBGE
python3 -m src.enrichers.mapear_municipios # Fase 1c: Fuzzy match IBGE
python3 -m src.enrichers.ibge_agregados    # Fase 1d: Pop/PIB/área
python3 -m src.enrichers.siconfi           # Fase 1e: SICONFI (DCA + RREO)
python3 -m src.enrichers.camara            # Fase 2: Perfis Deputados
python3 -m src.enrichers.tse_prefeitos     # Fase 7a: Prefeitos (TSE)
python3 -m src.enrichers.tse_vereadors     # Fase 7b: Vereadores (TSE)
python3 -m src.enrichers.senado            # Fase 8: Senadores (API Senado)
```

### Redator Oficial
```bash
./run.sh redator nota-tecnica --parlamentar "AFONSO FLORENCE" --ano 2026
./run.sh redator oficio --dest "Governador" --cargo "Governador" --assunto "Relatório" --corpo "..."
./run.sh redator parecer --processo "001/2026" --consulta "Análise"
./run.sh redator despacho --assunto "Encaminhamento" --texto "..."
./run.sh redator validar --arquivo "docs/nota.txt" --tipo nota_tecnica
./run.sh redator listar-tipos
```

### Jobs Agendados
```bash
./run.sh cron-diario       # Worker do Diário Oficial (baixa DOU e gera resumo)
./run.sh cron-qdrant       # Indexador Qdrant para alimentar RAG
./run.sh cron-dossie       # Geração de dossiês via LLM
```

---

## 🌐 Aplicações Web & Servidor MCP

### 1. Painel Web de Inteligência Parlamentar (FastAPI)
Interface RESTful e SPA com 38 endpoints para consulta de deputados, emendas, despesas CEAP, proposições, prefeitos, vereadores, compras e Diário Oficial.
```bash
./run.sh web                          # Porta 8080 (http://localhost:8080)
# Ou diretamente via uvicorn na porta 8000:
# uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```
- **Interface Web**: [http://localhost:8080](http://localhost:8080) ou [http://localhost:8000](http://localhost:8000)
- **Documentação Swagger/ReDoc**: [http://localhost:8080/docs](http://localhost:8080/docs)

### 2. Plotly Dash & Servidor MCP Hub (Dash 4.3+)
Dashboard analítico interativo com 68 gráficos (17 módulos) e Servidor MCP nativo integrado.
```bash
python3 src/dash_app.py
```
- **Dashboard Web**: [http://localhost:8050](http://localhost:8050)
- **Endpoint MCP Server**: [http://localhost:8050/_mcp](http://localhost:8050/_mcp)

Verificação de integridade dos gráficos:
```bash
python3 src/verify_graphs.py
```

---

## 🤖 Integração LocalAI

Gerenciamento de modelos de linguagem locais via API compatível OpenAI com controle de VRAM. O `LocalAIManager` descarrega modelos inativos antes de invocar novos, evitando OOM/RPC EOF em GPU.

**Modelos validados** (ver `config/settings.py`):
| Modelo | Uso | Velocidade |
|--------|-----|-----------|
| `gemma-4-e2b-it` | Padrão RAG / Redação PT-BR | 36.8 tok/s |
| `qwen2.5-1.5b-instruct-q4-k-m` | Triagem / NER | 88.9 tok/s |
| `llama-3.1-8b-q4-k-m` | Análise investigativa profunda | 7.7 tok/s |

Documentação: [docs/LOCALAI.md](docs/LOCALAI.md)

---

## 📚 Pipeline RAG v3

Sistema de Retrieval-Augmented Generation com Qdrant + LocalAI:

- **Indexação vetorial** via `rag_qdrant_indexer.py` — embeddings `nomic-embed-text-v1.5` (768d).
- **Multi-Query Persona** (`rag_persona.py`) — 5 consultas temáticas por deputado: votos, emendas PIX, proposições, Diário Oficial e conexões políticas municipais (TSE × Emendas).
- **Benchmark de modelos** em `scripts/benchmark_models.py`.

Documentação: [docs/RAG.md](docs/RAG.md)

---

## 📝 Redator Oficial

Geração de documentos oficiais seguindo o Manual de Redação da Presidência (3ª edição). Tipos suportados: ofício, nota técnica, parecer, despacho, portaria, ata.

Documentação: [docs/REDATOR.md](docs/REDATOR.md)

---

## 🛠️ Qualidade de Código, Linting & CI/CD

```bash
pre-commit install                        # Instalar ganchos locais
pre-commit run --all-files                # Verificações completas

# Ou individualmente:
ruff check . --fix                        # Linter
ruff format .                             # Formatação
mypy src config tests                     # Tipos
pytest                                    # Testes
```

Push ou PR para `main`/`master` dispara o workflow GitHub Actions (`.github/workflows/ci.yml`), testando em Python 3.11 e 3.12.

---

## 📖 Documentação Adicional

- [**Guia de Onboarding (`docs/ONBOARDING.md`)**](docs/ONBOARDING.md): Primeiros passos e configuração de ambiente.
- [**Guia de Desenvolvimento (`docs/DEVELOPMENT.md`)**](docs/DEVELOPMENT.md): Padrões de código, Ruff/MyPy e fluxo de PRs.
- [**Guia de Migrações SQL (`docs/MIGRATIONS.md`)**](docs/MIGRATIONS.md): Instruções para aplicação de scripts SQL.
- [**Guia de Agentes (`AGENTS.md`)**](AGENTS.md): Especificações técnicas para agentes autônomos de IA.
- [**Integração LocalAI (`docs/LOCALAI.md`)**](docs/LOCALAI.md): Configuração e modelos LocAI.
- [**Pipeline RAG v3 (`docs/RAG.md`)**](docs/RAG.md): Indexação vetorial e geração de personas.
- [**Redator Oficial (`docs/REDATOR.md`)**](docs/REDATOR.md): Documentos oficiais automatizados.
- [**Bridge MCP (`docs/MCP_BRIDGE.md`)**](docs/MCP_BRIDGE.md): Bridge MCP para ferramentas externas.
- [**Jobs Agendados (`docs/CRON_JOBS.md`)**](docs/CRON_JOBS.md): Configuração de cron-diario, cron-qdrant, cron-dossie.

---

## 📄 Licença
Distribuído sob a licença MIT. Veja [LICENSE](LICENSE) para mais informações.
