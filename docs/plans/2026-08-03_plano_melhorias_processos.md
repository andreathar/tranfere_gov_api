# Plano de Melhorias — Otimização, Monitoramento e Padronização de Processos

> **Data**: 2026-08-03
> **Baseado em**: Auditoria direta do repositório (sem agentes — falharam por limite de uso; dados coletados via comandos)
> **Escopo**: Scripts, agendamento, logging, migrations, qualidade de código e dados

---

## 1. Situação Atual (Auditoria)

### 1.1 Inventário

| Item | Quantidade | Observação |
|------|-----------|------------|
| Scripts `src/*.py` (top-level) | 28 | + `api/`, `graphs/` (21), `enrichers/` (31) |
| Scripts `scripts/` | 10 | 5 `.py` + 5 `.sh` |
| Arquivos `.py` no repo | 5.772 | inclui submodule `references/mcp-brasil` |
| Comandos em `run.sh` | 26 | 166 linhas |
| Migrations `data/migration_*.sql` | 38 | **com números duplicados** |
| Testes coletados | 358 | via `.venv/bin/python -m pytest` |
| Cobertura | 11,63% | requisito mínimo 7% |
| Erros ruff | **29** | 23 auto-fixáveis |
| Erros mypy | **11** | em 3 de 119 arquivos |

### 1.2 Achados críticos

| # | Achado | Severidade |
|---|--------|-----------|
| A | **Jobs cron documentados NÃO estão agendados.** CRON_JOBS.md descreve `cron-diario` (diário 21h), `cron-qdrant` (seg 02h), `cron-dossie` (dias 1/16 04h) mas apenas como **exemplo** com caminho placeholder `/caminho/para/...`. Não há crontab (`no crontab for athar`), nem systemd user timers, nem entradas em `/etc/cron.d/` para o projeto. **Os 3 jobs nunca rodam automaticamente.** | 🔴 ALTA |
| B | **Invocação inconsistente no `run.sh`**: 12 comandos usam `$PYTHON "$SRC/X.py"` (caminho direto) e 11 usam `$PYTHON -m src.X` (módulo). Ex.: `report`/`import`/`dashboard`/`redator`/`transparencia` diretos; `enrich`/`validate`/`ibge`/`camara`/`cron-*`/`discursos` via módulo. | 🟡 MÉDIA |
| C | **Logging não padronizado**: 46 arquivos usam `print(`, 53 usam `logging`; 223 ocorrências de `print(` só nos enrichers. `logging.basicConfig` com formatos diferentes em 8+ arquivos (`%(asctime)s [%(levelname)s]` vs `%(asctime)s - %(levelname)s -` vs sem formato). Sem handler de arquivo centralizado. | 🟡 MÉDIA |
| D | **Migrations com numeração duplicada**: `015` ×4, `016` ×3, `026` ×2, `021` ×2, `019` ×2, `018` ×2, `017` ×2, `014` ×2. Sem tabela de tracking de migrations no banco; aplicação manual (docstrings "Requer migration_0XX"). Ordem de aplicação ambígua. | 🟡 MÉDIA |
| E | **Dívida de qualidade pequena**: 29 erros ruff (23 fixáveis com `ruff --fix`) + 11 erros mypy em 3 arquivos (`extrator_discricionarias.py`, `localai_client.py`, +1). Pre-commit config e CI existem; hook `.git/hooks/pre-commit` roda `scripts/check_secrets.py` (segredos/CPF/CNPJ). | 🟢 BAIXA |
| F | **Python padrão do shell ≠ venv**: `python3` resolve para pyenv shim (`/home/athar/.pyenv/shims/python3` → sys.prefix `/usr`), **sem pytest**. Testes só funcionam via `.venv/bin/python`. run.sh ativa `.venv` quando existe (OK), mas chamadas manuais sem venv falham. | 🟢 BAIXA |

### 1.3 O que já está bom (manter)

- AGENTS.md extenso e bem estruturado (convenções, pitfalls, comandos, cron documentado)
- Pre-commit config + CI (`ci.yml`: py 3.11+3.12, ruff, mypy, pytest+cov) já existem
- `extract_log` tabela funcional (14 registros, último 2026-07-31) escrita por 4 módulos
- Banco saudável: 36 tabelas + 33 views, todas com PK, 24 FKs, 0 órfãos
- `src/db_utils.py` + `src/formatters.py` como módulos compartilhados ("NÃO redefinir")
- Documentação rica em `docs/` (ONBOARDING, DEVELOPMENT, MIGRATIONS, CRON_JOBS, LOCALAI, RAG, REDATOR)

---

## 2. Plano de Implementação

### FASE 1 — Monitoramento (P0) ⏱ 2-3h

#### 1.1 Agendar os 3 jobs cron de verdade (o problema mais grave)

**Objetivo**: `cron-diario`, `cron-qdrant`, `cron-dossie` rodando automaticamente conforme CRON_JOBS.md, com logs persistentes.

**Arquivos**:
- `~/.config/systemd/user/` — criar 3 unidades `transferegov-<job>.service` + `.timer` (mais robusto que crontab: logs via journald, retry, `systemctl --user status`)
- OU `crontab -e` com entradas do CRON_JOBS.md (mais simples, formato já documentado)

**Decisão**: usar **systemd user timers** (logs estruturados, `OnFailure` para alerta, independente de sessão de terminal). Criar helper `scripts/install_timers.sh` para instalar/remover.

**Verificação**:
- `systemctl --user list-timers | grep transferegov` → 3 timers ativos
- `systemctl --user list-units | grep transferegov` → services existem
- Rodar `./run.sh cron-diario` manualmente uma vez → log gerado em `output/logs/cron-diario.log`
- `journalctl --user -u transferegov-cron-diario --since today` → execução registrada

#### 1.2 Padronizar `extract_log` como fonte de verdade de monitoramento

**Objetivo**: Todas as extrações registram em `extract_log` com `source` padronizado.

**Arquivos**: `src/db_import.py`, `src/transferegov_extract.py`, `src/enrichers/votacoes_camara.py`, `src/enrichers/camara_discursos.py`

**Ação**:
- Garantir que todo módulo que extrai dados insira em `extract_log` (hoje só 4 escrevem)
- Adicionar query de diagnóstico `./run.sh report saude` (novo comando) que mostra: última execução por source, contagens, falhas recentes — para resposta rápida "o pipeline está saudável?"

**Verificação**: `./run.sh report saude` → tabela com últimas extrações por source.

---

### FASE 2 — Padronização de Scripts (P1) ⏱ 3-4h

#### 2.1 Unificar invocação em `run.sh` (módulo `-m` como padrão)

**Objetivo**: 100% dos comandos Python via `$PYTHON -m src.X` (consistente com AGENTS.md "roda como módulo independente via `python3 -m`").

**Arquivos**: `run.sh`

**Ação**: converter os 12 comandos diretos (`discover`, `cemiterios`, `negados`, `import`, `report`, `dashboard`, `dash`, `transparencia`, `vllm`, `vllm-bench`, `redator`, `all`, `qdrant-status`, `qdrant-staleness`) para `-m`. Criar `src/__main__`-style? Não — basta `-m src.modulo`.

**Cuidado**: `vllm-bench` referencia `scripts/benchmark_vllm_vs_localai.py` via `$SRC/../scripts/` — virar `-m scripts.benchmark_vllm_vs_localai` requer `scripts/__init__.py` (verificar existência). Alternativa: manter path absoluto para scripts/ se não for módulo.

**Verificação**: `./run.sh help` mostra 26 comandos; rodar smoke test de 3 comandos baratos (`discover`, `report resumo`, `qdrant-status`) → saída esperada.

#### 2.2 Padronizar logging (substituir `print(` por logging em módulos core)

**Objetivo**: Formato único + handler de arquivo opcional.

**Arquivos**: `src/db_utils.py` (novo helper `setup_logging(name, level)`), depois aplicar nos módulos que hoje usam `basicConfig` variado.

**Ação**:
- Adicionar `setup_logging()` em `src/db_utils.py` com formato canônico `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- Substituir `logging.basicConfig(...)` variado por `setup_logging(__name__)` nos enrichers core
- **Não** converter todos os 223 prints de uma vez (risco alto, baixo retorno). Converter apenas módulos críticos: `transferegov_extract.py`, `db_import.py`, `enrichers/pipeline.py`, `diario_oficial_worker.py`

**Verificação**: `ruff check src/` sem novos erros; smoke test de `./run.sh discover` mostra logs com formato canônico.

---

### FASE 3 — Migrations e Consistência de Dados (P1) ⏱ 3-4h

#### 3.1 Renumerar migrations duplicadas

**Objetivo**: Sequência única 001..038 aplicável em ordem.

**Arquivos**: `data/migration_*.sql` (38 arquivos)

**Ação**:
- Mapear ordem real de aplicação (usar `docs/MIGRATIONS.md` como referência)
- Renumerar conflitos: `015_*` → manter um como 015, re-sequenciar (ex.: 015_discursos, 016_senadores, 017_persona, 018_triangulo — verificar dependências no MIGRATIONS.md)
- Atualizar referências em docstrings ("Requer migration_0XX") via grep

**Verificação**: `ls data/migration_*.sql | sed 's/.*_//;s/_.*//' | sort -n | uniq -c` → todos com contagem 1.

#### 3.2 Criar tracking de migrations no banco

**Objetivo**: Saber quais migrations foram aplicadas sem decifrar por tentativa.

**Arquivos**: `data/migration_001_track.sql` (nova), `scripts/db_migrate.sh` (novo)

**Ação**:
- Tabela `schema_migrations(filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT NOW())`
- Script `scripts/db_migrate.sh` que aplica arquivos `data/migration_*.sql` ainda não registrados, em ordem lexical, e registra cada um
- Registrar as 38 atuais como já aplicadas na primeira execução (modo `--mark-applied`)

**Verificação**: `scripts/db_migrate.sh --status` → lista 38 aplicadas; rodar 2x → "nada a aplicar".

---

### FASE 4 — Qualidade de Código (P2) ⏱ 2h

#### 4.1 Limpar dívida ruff + mypy

**Arquivos**: 29 erros ruff (23 auto-fix) + 11 mypy em 3 arquivos

**Ação**:
- `ruff check src/ --fix` (23 auto-fixáveis)
- Corrigir manualmente os 6 restantes (E402 ×3, B007, F841, SIM117, SIM300)
- Corrigir 11 erros mypy: `extrator_discricionarias.py` (4 erros de tipo em ~605-614), `localai_client.py` (1, `int | str` vs `int`), +1 arquivo

**Verificação**: `ruff check src/` → 0 erros; `mypy src/` → 0 erros; `pre-commit run --all-files` → green.

#### 4.2 Documentar venv obrigatório

**Arquivos**: `docs/ONBOARDING.md`, `AGENTS.md`

**Ação**: Nota clara: usar sempre `.venv/bin/python` ou ativar `.venv` antes de qualquer comando (o `python3` do shell não tem pytest/deps).

---

### FASE 5 — Verificação Final (P0 gate) ⏱ 1h

- [ ] `ruff check src/ scripts/ tests/` → 0 erros
- [ ] `mypy src/` → 0 erros
- [ ] `.venv/bin/python -m pytest` → 358 passando (ou baseline documentado)
- [ ] `./run.sh help` lista 26 comandos, todos `-m`
- [ ] `systemctl --user list-timers | grep transferegov` → 3 ativos
- [ ] `scripts/db_migrate.sh --status` → 38 aplicadas, idempotente
- [ ] `./run.sh report saude` → mostra últimas extrações
- [ ] Git: commit limpo, sem segredos (hook check_secrets passa)

---

## 3. Priorização

| Prioridade | Item | Esforço | Impacto |
|-----------|------|---------|---------|
| **P0** | 1.1 Agendar jobs cron (systemd timers) | 2h | 🔴 Jobs hoje nunca rodam sozinhos |
| **P0** | 1.2 `report saude` + padronizar extract_log | 1h | 🟡 Visibilidade do pipeline |
| **P1** | 2.1 Unificar run.sh (`-m`) | 1,5h | 🟡 Consistência |
| **P1** | 2.2 Logging padronizado (core) | 2h | 🟡 Debuggabilidade |
| **P1** | 3.1 Renumerar migrations | 2h | 🟡 Ordem de aplicação segura |
| **P1** | 3.2 Tracking de migrations | 1,5h | 🟡 Auditoria do schema |
| **P2** | 4.1 Limpar ruff+mypy | 2h | 🟢 Qualidade CI green |
| **P2** | 4.2 Doc venv obrigatório | 15min | 🟢 Onboarding |

## 4. Métricas de Sucesso

| Métrica | Antes | Depois |
|---------|-------|--------|
| Jobs agendados ativos | **0** | 3 |
| Comandos run.sh via `-m` | 11/26 (42%) | 26/26 (100%) |
| Erros ruff | 29 | 0 |
| Erros mypy | 11 | 0 |
| Migrations com número único | 30/38 (79%) | 38/38 (100%) |
| Migrations rastreadas no banco | 0 | 38 |
| Fontes com entrada em extract_log | 4 | ≥6 |
| Logs com formato canônico | 8+ variados | 100% core |

---

## 5. Nota sobre a auditoria

Os 4 agentes `explore` lançados em paralelo falharam ("usage limit has been reached" em gpt-5.4-mini-fast, re-enfileirados em gpt-5.4-nano, um timeout após 30min). A auditoria foi refeita diretamente com comandos — dados acima são verificados empiricamente (ruff/mypy/pytest rodados, crontab e systemd consultados, migrations listadas).
