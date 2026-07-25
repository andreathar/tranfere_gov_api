---
name: transferegov-cli
description: Comandos CLI para rodar as extrações, relatórios e importações de dados do TransfereGov.
---

# Transferegov CLI Skill

Você está encarregado de gerenciar as rotinas primárias de extração usando o script principal do repositório.

## Regras
- Sempre ative a VENV antes: `source .venv/bin/activate`
- Use o utilitário `./run.sh` para atalhos.

## Comandos Chave
1. **Listar Objetos Disponíveis**: `./run.sh discover`
2. **Extração Geral + DB**: `./run.sh all --db`
3. **Extrair apenas Negados para CSV e DB**: `./run.sh negados --csv --db`
4. **Relatório Geral**: `./run.sh report resumo`
5. **Dashboard MCP**: `python3 src/dash_app.py`
6. **Web App FastAPI**: `python3 -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000`

Se ocorrer erro de banco, cheque se o PostgreSQL local está rodando e aceitando conexões.
