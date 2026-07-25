# Plano de Ação Gemini / Antigravity — TransfereGov API

Este documento consolida o plano de automação e gerenciamento local do projeto **TransfereGov API** através de Agentes e Skills baseadas no Antigravity SDK, incluindo o uso de modelos locais via `LocalAI` para tarefas longas e de relatórios.

## 1. Visão Geral e Necessidades de Automação
Com base na varredura do projeto (`AGENTS.md`, arquitetura e scripts), as seguintes necessidades foram identificadas para automação:

- **Manutenção de Qualidade de Código (QA)**: Cumprimento estrito das regras do `ruff` (line-length 99, target py311), `mypy --strict`, e `pytest`.
- **Extração e Pipeline de Dados Diário**: Gerenciamento das extrações (`run.sh all --db`) e dos enriquecimentos em lote (`src.enrichers.pipeline --fase all`), processos demorados que se beneficiam de execução autônoma via LocalAI.
- **Auditoria de Gráficos e Dashboard**: Garantir que todos os gráficos não falhem e mantenham a resiliência configurada no Dash 4.3+ (`verify_graphs.py`).
- **Geração de Relatórios e Análises (LocalAI)**: Relatórios extensos e processamento repetitivo de dados podem ser roteados para a API do LocalAI configurada no ambiente.

## 2. Equipe de Agentes (Subagents)

Os agentes locais vivem na pasta `.gemini/agents/` e são orquestrados para gerenciar o projeto:
- **`transferegov_qa`**: Especializado em manter e corrigir tipagens (Mypy) e formatação (Ruff).
- **`transferegov_data_ops`**: Cuida de rodar jobs assíncronos longos para o banco e a pipeline de enriquecimento usando LocalAI para deduções ou logs.
- **`transferegov_mcp_admin`**: Agente focado em analisar os gráficos, registrar novos gráficos MCP (`register_custom_graph`) e auditar o Painel.

## 3. Skills (Habilidades)

As skills ensinam os agentes a interagir com o ecossistema:
- **`transferegov_cli`**: Ensina os comandos do `run.sh` e extração.
- **`transferegov_enrichment`**: Como rodar e interagir com o módulo de enriquecimento.
- **`localai_batch_processing`**: Como usar o backend LocalAI localmente para sumários pesados e análise de anomalias no DB.

## 4. Configurações de Editor
A pasta `.vscode` foi criada e configurada com `settings.json` e `extensions.json` para garantir formatação (`ruff`) on save, bem como o uso de `mypy` no modo estrito.
