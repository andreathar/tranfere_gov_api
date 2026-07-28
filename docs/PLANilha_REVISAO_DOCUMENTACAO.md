# Plano de Revisão e Atualização Documentação — TransfereGov API

**Data**: 27 de Julho de 2026
**Escopo**: Auditoria completa do estado atual do projeto + plano de atualização profissional da documentação

---

## 1. Situação Atual do Projeto (Diagnóstico)

### 1.1. Crescimento desde a Última Revisão Documental

O projeto cresceu significativamente desde que a documentação original foi escrita. Abaixo, o delta entre o documentado e o real:

| Componente | Documentado (AGENTS.md/README) | Real (código) | Status |
|---|---|---|---|
| **Gráficos Dashboard** | 31 gráficos | **68 gráficos** em 17 módulos | ⚠️ Desatualizado |
| **Enrichers (Fases)** | Fases 1-3, ~10 scripts | **25+ scripts**, Fases 1-8 + auxiliares | ⚠️ Desatualizado |
| **Endpoints API** | 10 endpoints (deputados) | **38 endpoints** em 8 routers | ⚠️ Desatualizado |
| **Módulos Routes** | 1 módulo (deputados.py) | **7 módulos** (deputados, prefeitos, vereadores, analytics, auditoria, compras, diario, fnde) | ⚠️ Desatualizado |
| **LocalAI Integration** | Não documentada | **3 módulos novos** (manager, client, bridge) | ❌ Ausente |
| **RAG Pipeline** | Não documentado | **2 módulos** (rag_persona, rag_qdrant_indexer) | ❌ Ausente |
| **Redator Oficial** | Não documentado | **902 linhas**, 6 subcomandos | ❌ Ausente |
| **MCP Tool Bridge** | Não documentado | **926 linhas**, agentic loop completo | ❌ Ausente |
| **Frontend SPA** | Mencionado brevemente | **1200+ linhas JS**, 8 abas, 4 modais | ⚠️ Desatualizado |
| **Services API** | 2 serviços | **4 serviços** (db, camara, analytics, mcp) | ⚠️ Desatualizado |

### 1.2. Componentes Novos (Não Documentados)

#### A. Integração LocalAI (3 módulos, ~1584 linhas)

| Módulo | Linhas | Função |
|---|---|---|
| `src/localai_manager.py` | 76 | Gerenciamento de VRAM — exclusividade de modelo via load/unload/monitor |
| `src/localai_client.py` | 582 | Cliente OpenAI-compatível: chat, streaming, embeddings, classificação em lote, enriquecimento de DataFrame, jobs assíncronos |
| `src/mcp_tool_bridge.py` | 926 | Ponte MCP→OpenAI function calling: descoberta de 533+ tools, agentic loop multi-turno |

**Modelos Configurados** (`config/settings.py`):
- `gemma-4-e2b-it` (Padrão): 36.8 tok/s, PT-BR
- `qwen2.5-1.5b-instruct-q4-k-m` (Fast): 88.9 tok/s, triagem
- `llama-3.1-8b-q4-k-m` (Analysis): 7.7 tok/s, análise profunda
- `nomic-embed-text-v1.5` (Embedding): 768d, cosine
- 4 modelos adicionais (code, general, router)

#### B. Pipeline RAG v3 (2 módulos, ~1030 linhas)

| Módulo | Linhas | Função |
|---|---|---|
| `src/enrichers/rag_qdrant_indexer.py` | 494 | Indexação vetorial: 6 tipos de chunks (perfil, proposições, emendas, votos, diário oficial, conexão política) |
| `src/enrichers/rag_persona.py` | 536 | Geração de dossiês: 5 queries temáticas, prompt adaptativo, versionamento, batch otimizado |

**Fluxo RAG**:
1. PostgreSQL → Extração de 6 tipos de dados
2. Qdrant (coleção `deputados_perfis`, 768d cosine)
3. 5 queries temáticas × top-k
4. Prompt adaptativo por volume de dados
5. LLM gera dossiê → salva em `parlamentares_personas` com versionamento

#### C. Redator Oficial (1 módulo, 902 linhas)

| Módulo | Função |
|---|---|
| `src/redator_transferegov.py` | 6 tipos de documento: nota técnica, ofício, parecer, despacho, validação, listar-tipos |

Segue "Manual de Redação da Presidência da República, 3ª edição (2018)". 27 pronomes de tratamento em 4 tiers, fechos padronizados.

#### D. Novos Enriquecedores (15+ módulos novos)

| Módulo | Fase | Fonte | Tabela Destino |
|---|---|---|---|
| `compras.py` | 5 | PNCP + Compras.gov.br | `compras_municipios` |
| `saude_educacao.py` | 6 | CNES/DataSUS + INEP | `saude_municipios`, `educacao_municipios` |
| `datajud.py` | 4 | MCP Brasil (DataJud) | `beneficiario_processos` |
| `fnde.py` | Aux | FNDE Olinda OData | `fnde_repasses` |
| `tcu_compras.py` | Aux | Local DB | Relatórios |
| `sync_proposicoes.py` | Aux | Câmara API | `parlamentar_proposicoes` |
| `votacoes_camara.py` | Aux | Câmara API | `votacoes_camara`, `votos_camara` |
| `votacoes_temas.py` | Aux | LocalAI LLM | `votacoes_camara.tema` |
| `diario_oficial_worker.py` | Aux | MCP + Câmara | `diario_oficial_atos`, `parlamentar_alertas` |
| `tse_deputados.py` | Aux | TSE DuckDB | `parlamentares_dados` (UPDATE) |

#### E. Novos Gráficos (17 módulos, 68 gráficos)

| Módulo | Gráficos | Categoria |
|---|---|---|
| `arrecadacao.py` | 13 | Arrecadação |
| `siconfi.py` | 10 | SICONFI Fiscal |
| `economico.py` | 7 | Análise Econômica |
| `financas.py` | 6 | Finanças |
| `intel_politica.py` | 5 | Inteligência Política |
| `hierarquico.py` | 4 | Hierárquico |
| `parlamentar.py` | 3 | Parlamentar |
| `socioeconomico.py` | 3 | Socioeconômico |
| `geoespacial.py` | 3 | Geoespacial |
| `fiscal.py` | 3 | Fiscal |
| `economia_cruzada.py` | 2 | Economia Cruzada |
| `impacto_social.py` | 2 | Impacto Social |
| `analitico.py` | 2 | Analítico |
| `prefeitos.py` | 2 | Prefeitos |
| `votacoes.py` | 1 | Votações |
| `intel_proposicoes.py` | 1 | Proposições |
| `radar_diario.py` | 1 | Radar Diário |

#### F. Novas Rotas API (7 novos routers)

| Router | Endpoints | Dados |
|---|---|---|
| `prefeitos.py` | 6 | DB only |
| `vereadores.py` | 6 | DB only |
| `analytics.py` | 4 | DB + Câmara |
| `auditoria.py` | 3 | MCP Brasil |
| `compras.py` | 2 | MCP Brasil |
| `diario.py` | 2 | MCP Brasil |
| `fnde.py` | 5 | DB only |

---

## 2. Lacunas Documentais Identificadas

### 2.1. Documentos Existentes com Lacunas

| Documento | Estado | Lacunas Principais |
|---|---|---|
| `README.md` | ⚠️ Desatualizado | Gráficos 31→68, enrichers incompletos, sem LocalAI/RAG/Redator |
| `AGENTS.md` (raiz) | ⚠️ Desatualizado | 68 gráficos (diz 38), 25+ enrichers (diz ~10), sem LocalAI/MCP bridge |
| `src/enrichers/AGENTS.md` | ⚠️ Desatualizado | Fases 4-8 ausentes, RAG ausente, 15+ enrichers novos não listados |
| `src/api/AGENTS.md` | ⚠️ Desatualizado | Apenas deputados route documentado, 7 routes ausentes |
| `docs/ONBOARDING.md` | ⚠️ Desatualizado | Sem LocalAI setup, sem RAG pipeline, sem cron jobs |
| `docs/DEVELOPMENT.md` | ⚠️ Parcial | Sem padrões LocalAI/MCP bridge |
| `docs/MIGRATIONS.md` | ⚠️ Parcial | Faltam migrations 015-018 |
| `docs/strategy.md` | ⚠️ Genérico | Documento estratégico genérico, não reflete estado atual |

### 2.2. Documentos Ausentes (Não Existem)

| Documento Necessário | Prioridade | Justificativa |
|---|---|---|
| `docs/LOCALAI.md` | **ALTA** | Integração completa com 3 módulos, 7 modelos, VRAM management |
| `docs/RAG.md` | **ALTA** | Pipeline RAG v3 com Qdrant, 5 queries temáticas, versionamento |
| `docs/REDATOR.md` | **MÉDIA** | 6 tipos de documento, 27 pronomes, validação |
| `docs/MCP_BRIDGE.md` | **MÉDIA** | 926 linhas, agentic loop, 533+ tools |
| `docs/API_REFERENCE.md` | **MÉDIA** | 38 endpoints, 8 routers, 4 services |
| `docs/CRON_JOBS.md` | **BAIXA** | 3 cron jobs: diário, Qdrant, dossiê |

---

## 3. Plano de Atualização Documental

### Fase 1: Documentos Core (Prioridade ALTA)

#### 3.1. Atualizar `README.md`
- [ ] Atualizar contagem de gráficos: 31 → 68
- [ ] Atualizar contagem de enrichers: ~10 → 25+
- [ ] Adicionar seção "Integração LocalAI" na visão geral
- [ ] Adicionar seção "Pipeline RAG v3" na visão geral
- [ ] Atualizar estrutura do projeto (adicionar módulos novos)
- [ ] Atualizar diagrama de arquitetura (adicionar LocalAI, Qdrant, MCP Bridge)
- [ ] Adicionar pré-requisitos: LocalAI server, Qdrant server, GPU
- [ ] Atualizar comandos: cron-diario, cron-qdrant, cron-dossie
- [ ] Adicionar seção "Redator Oficial"
- [ ] Adicionar badges de LocalAI e RAG

#### 3.2. Atualizar `AGENTS.md` (raiz)
- [ ] Atualizar tabela de enriquecimento (8 fases, 25+ scripts)
- [ ] Adicionar seção completa "Integração LocalAI"
- [ ] Adicionar seção completa "Pipeline RAG v3"
- [ ] Adicionar seção "Redator Oficial"
- [ ] Adicionar seção "MCP Tool Bridge"
- [ ] Atualizar contagem de gráficos: 38 → 68
- [ ] Atualizar estrutura do projeto
- [ ] Atualizar pitfall list (adicionar novos pitfalls do LocalAI/RAG)
- [ ] Atualizar tabela de views (adicionar novas views das migrations 010-018)

#### 3.3. Criar `docs/LOCALAI.md`
- [ ] Visão geral da integração (3 módulos, arquitetura)
- [ ] Configuração do servidor LocalAI (setup, modelos, VRAM)
- [ ] Tabela de modelos com benchmarks (tok/s, uso recomendado)
- [ ] Padrão `ensure_model_loaded()` — protocolo de exclusividade VRAM
- [ ] `LocalAIClient`: API completa (chat, embed, classify, enrich, stream, jobs)
- [ ] `MCPToolBridge`: arquitetura, categorias, agentic loop
- [ ] Consumidores: rag_persona, votacoes_temas, diario_oficial_worker
- [ ] Benchmarks: como rodar, interpretação de resultados
- [ ] Troubleshooting: OOM, timeout, modelo não encontrado

#### 3.4. Criar `docs/RAG.md`
- [ ] Visão geral do pipeline RAG v3
- [ ] Pré-requisitos: Qdrant, LocalAI, modelos de embedding
- [ ] Indexação: `rag_qdrant_indexer.py` — 6 tipos de chunks
- [ ] Recuperação: 5 queries temáticas, deduplicação, cap de chunks
- [ ] Geração: prompt adaptativo, versionamento, salvamento no DB
- [ ] Comandos: cron-qdrant, cron-dossie, flags
- [ ] Schema do banco: `parlamentares_personas`
- [ ] Troubleshooting: Qdrant offline, embedding falhou, chunks insuficientes

### Fase 2: Documentos de Módulos (Prioridade MÉDIA)

#### 3.5. Atualizar `src/enrichers/AGENTS.md`
- [ ] Adicionar Fases 4-8 na tabela de scripts
- [ ] Adicionar 15+ enrichers auxiliares novos
- [ ] Adicionar seção "Pipeline RAG" (rag_qdrant_indexer, rag_persona)
- [ ] Atualizar comandos (adicionar novos enrichers)
- [ ] Atualizar pitfalls (adicionar 10+ novos pitfalls)
- [ ] Atualizar tabela de tabelas (adicionar 10+ novas tabelas)
- [ ] Documentar dependências entre enrichers (ibge→siconfi, rag→indexer)

#### 3.6. Atualizar `src/api/AGENTS.md`
- [ ] Documentar todos os 7 routers (não apenas deputados)
- [ ] Documentar 38 endpoints com métodos e descrições
- [ ] Documentar 4 services (db, camara, analytics, mcp)
- [ ] Documentar Frontend SPA (8 abas, 4 modais, vanilla JS)
- [ ] Atualizar padrão de fallback (expandir)
- [ ] Adicionar pitfalls novos (async/sync bridge, MCP client)

#### 3.7. Criar `docs/REDATOR.md`
- [ ] Visão geral: 6 tipos de documento
- [ ] Manual de Redação: referência (3ª edição, 2018)
- [ ] Pronomes de tratamento: 27 entradas em 4 tiers
- [ ] Fechos: "Respeitosamente" vs "Atenciosamente"
- [ ] Comandos: nota-tecnica, oficio, parecer, despacho, validar
- [ ] Exemplos de uso
- [ ] Validação: o que checa, como corrigir

#### 3.8. Criar `docs/MCP_BRIDGE.md`
- [ ] Visão geral: MCP → OpenAI function calling
- [ ] Categorias de tools: 15 categorias
- [ ] Descoberta de tools: meta-tools + cached
- [ ] Agentic loop: chat → tool_calls → execute → repeat
- [ ] Uso com LocalAIClient
- [ ] Dashboard tools: list, health, summary, register

### Fase 3: Documentos de Infraestrutura (Prioridade BAIXA)

#### 3.9. Atualizar `docs/ONBOARDING.md`
- [ ] Adicionar pré-requisitos: LocalAI, Qdrant, GPU (recomendado)
- [ ] Adicionar seção "Setup LocalAI"
- [ ] Adicionar seção "Setup Qdrant"
- [ ] Adicionar comandos cron (cron-diario, cron-qdrant, cron-dossie)
- [ ] Atualizar pipeline de enriquecimento (fases 4-8)
- [ ] Adicionar verificação de integração LocalAI

#### 3.10. Atualizar `docs/DEVELOPMENT.md`
- [ ] Adicionar padrões de código LocalAI (ensure_model_loaded, client usage)
- [ ] Adicionar padrões MCP bridge
- [ ] Adicionar padrões RAG (queries temáticas, prompt adaptativo)
- [ ] Atualizar suíte de testes (verify_graphs → 68 gráficos)

#### 3.11. Atualizar `docs/MIGRATIONS.md`
- [ ] Adicionar migrations 015-018 na tabela
- [ ] Documentar dependências das novas migrations

#### 3.12. Criar `docs/CRON_JOBS.md`
- [ ] 3 cron jobs documentados
- [ ] Frequência recomendada
- [ ] Dependências e ordem de execução
- [ ] Monitoramento e logs

---

## 4. Ordem de Execução Recomendada

```
Fase 1 (Core — 1-2 dias):
  1. docs/LOCALAI.md (novo) ← Máxima prioridade, desbloqueia outras docs
  2. docs/RAG.md (novo)
  3. AGENTS.md (raiz) ← Atualização mais impactante
  4. README.md ← Visibilidade pública

Fase 2 (Módulos — 1 dia):
  5. src/enrichers/AGENTS.md
  6. src/api/AGENTS.md
  7. docs/REDATOR.md (novo)
  8. docs/MCP_BRIDGE.md (novo)

Fase 3 (Infra — 0.5 dia):
  9. docs/ONBOARDING.md
  10. docs/DEVELOPMENT.md
  11. docs/MIGRATIONS.md
  12. docs/CRON_JOBS.md (novo)
```

---

## 5. Padrões de Documentação

### 5.1. Estrutura Padrão para Documentos de Módulo

```markdown
# Título — Subtítulo

## Visão Geral
## Arquitetura
## Configuração
## Comandos / Uso
## API / Interface
## Pitfalls
## Troubleshooting
## Referências
```

### 5.2. Convenções

- **Idioma**: Português (PT-BR) para documentação interna
- **Tabelas**: Usar tabelas Markdown para dados estruturados
- **Código**: Blocos de código com linguagem especificada
- **Diagramas**: Mermaid para arquitetura e fluxos
- **Versão**: Incluir data de última atualização em cada documento
- **Linkagem**: Citar outros documentos relevantes

### 5.3. Checklist de Qualidade

- [ ] Todos os módulos documentados estão listados no AGENTS.md raiz
- [ ] Todos os comandos CLI estão documentados com exemplos
- [ ] Todos os endpoints API estão documentados com métodos
- [ ] Todos os pitfalls conhecidos estão documentados
- [ ] Todos os pré-requisitos estão listados
- [ ] Números atualizados (gráficos, enrichers, endpoints)
- [ ] Links internos funcionais

---

## 6. Resumo de Escopo

| Métrica | Valor |
|---|---|
| Documentos existentes a atualizar | 7 |
| Documentos novos a criar | 5 |
| Total de documentos | 12 |
| Linhas estimadas de documentação nova | ~3000-4000 |
| Tempo estimado total | 2.5-3.5 dias |
| Componentes a documentar | 68 gráficos, 25+ enrichers, 38 endpoints, 3 módulos LocalAI, 2 módulos RAG, 1 módulo Redator |
