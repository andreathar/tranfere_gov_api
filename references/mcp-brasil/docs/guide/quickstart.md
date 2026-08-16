# Quick Start

## Instalar

```bash
pip install mcp-brasil
```

ou com uv:

```bash
uv add mcp-brasil
```

## Conectar ao seu cliente MCP

### Claude Desktop

Adicione ao `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-brasil": {
      "command": "uvx",
      "args": ["--from", "mcp-brasil", "python", "-m", "mcp_brasil.server"],
      "env": {
        "TRANSPARENCIA_API_KEY": "sua-chave-aqui",
        "DATAJUD_API_KEY": "sua-chave-aqui"
      }
    }
  }
}
```

> As chaves sao opcionais — sem elas, as 24 APIs restantes funcionam normalmente.

### VS Code / Cursor

Crie `.vscode/mcp.json` na raiz do projeto:

```json
{
  "servers": {
    "mcp-brasil": {
      "command": "uvx",
      "args": ["--from", "mcp-brasil", "python", "-m", "mcp_brasil.server"],
      "env": {
        "TRANSPARENCIA_API_KEY": "sua-chave-aqui",
        "DATAJUD_API_KEY": "sua-chave-aqui"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add mcp-brasil -- uvx --from mcp-brasil python -m mcp_brasil.server
```

### HTTP (outros clientes)

```bash
fastmcp run mcp_brasil.server:mcp --transport http --port 8000
# Server disponivel em http://localhost:8000/mcp
```

## Testar

Conecte o server e faca perguntas em linguagem natural:

> "Quais projetos de lei sobre inteligencia artificial tramitaram na Camara em 2024?"

> "Qual a tendencia da taxa Selic nos ultimos 12 meses? Compare com a inflacao (IPCA)."

> "Quais os 10 maiores contratos do governo federal em 2024? Quem sao os fornecedores?"

> "Busque processos sobre licitacao irregular no TCU. Quais foram as penalidades?"

> "Quais os maiores doadores da campanha do candidato X?"

## Chaves de API

| API | Obrigatoria? | Como obter |
|-----|-------------|------------|
| Portal da Transparencia | Opcional (mais rate limit) | [Cadastro gratuito](http://portaldatransparencia.gov.br/api-de-dados/cadastrar-email) |
| DataJud/CNJ | Opcional (mais rate limit) | [Cadastro gratuito](https://datajud-wiki.cnj.jus.br/api-publica/acesso) |
| Todas as outras (24) | Nenhuma chave | — |

## Proximo passo

Veja o [Catalogo de Features](../reference/features.md) para conhecer todas as 205 tools disponiveis.
