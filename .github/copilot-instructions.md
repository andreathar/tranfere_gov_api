# GitHub Copilot Instructions — TransfereGov API

## Centro de Comando e Governança Multi-Agente
Este projeto integra múltiplos agentes autônomos e assistentes (Claude Code, Codex, Google Antigravity/Gemini, Hermes, OpenCode, GitHub Copilot, LocalAI).
Consulte [`docs/AGENT_COMMAND_CENTER.md`](../docs/AGENT_COMMAND_CENTER.md) e [`AGENTS.md`](../AGENTS.md) para as regras canônicas de arquitetura, portas e governança.

## Regras de Código e Execução
- Use sempre `.venv/bin/python` em desenvolvimento local.
- Constantes, endpoints e credenciais **nunca** são hardcoded; importe de `config.settings`.
- Preserva idempotência e operações seguras de upsert no banco `transferegov_db`.
- Código Python segue Python 3.11+, tipagem estrita (mypy), formatação Ruff (line-length 99) e docstrings/logs em PT-BR.

<!-- mermaid-ai-skills:start -->
## Mermaid Diagrams

When the user asks to create, edit, or visualize a diagram, follow the
instructions in `.github/instructions/mermaid.instructions.md`.
<!-- mermaid-ai-skills:end -->

