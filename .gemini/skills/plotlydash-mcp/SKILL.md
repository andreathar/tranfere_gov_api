---
name: plotlydash-mcp
description: Especialização na utilização do MCP Server do Dash para criar, auditar e gerenciar gráficos Plotly consistentes.
---

# PlotlyDash MCP Skill

Você é responsável por gerenciar e criar as visualizações interativas em tempo real (Plotly Dash 4.3+) que expõem os dados cruzados do banco `transferegov_db` (Dados do IBGE, emendas, prefeitos, e saúde/SICONFI).

## Regras e Diretrizes de UI/UX
- **Consistência Visual (Dark Slate)**: Todo gráfico deve aplicar obrigatoriamente a função `aplicar_tema(fig, titulo)` (localizada em `src.graph_factory` ou `src.graphs.theme`).
- **Resiliência e Anti-Falha**: Os gráficos não podem renderizar caixas brancas vazias. Caso a consulta SQL não retorne dados para o filtro, o gráfico deve exibir uma anotação informativa (ex: `"ℹ️ Dados em sincronização ou insuficientes"`). Sempre valide se `fig_has_data(fig)` está correto.
- **Gráficos Cruzados (Cross-Analysis)**: Ao lidar com dados cruzados (ex: IDEB vs Emendas, SICONFI vs Custeio), utilize mapas coropléticos, scatter plots com dispersão (tamanho da bolha = valor da emenda, cor = região) ou sunburst charts para evidenciar os cruzamentos.

## Uso das Ferramentas MCP (`plotlydash-mcp`)
O servidor Dash expõe em `http://localhost:8050/_mcp` ferramentas nativas que você pode usar:
1. **`list_registered_charts`**: Ver todos os gráficos atualmente registrados e seus filtros.
2. **`inspect_chart_health`**: Auditar um gráfico. Mostra a saúde, se retornou dados, e total de traços (traces).
3. **`get_chart_data_summary`**: Puxa um JSON estatístico sobre um gráfico para embasar a análise do Agente, sem ter que baixar os dados brutos.
4. **`register_custom_graph`**: Cria um novo gráfico! Você submete o ID, Título, Categoria, e a QUERY SQL (ex: `"SELECT uf, SUM(valor_total) as valor FROM parlamentar_beneficiario GROUP BY uf"`), e o servidor injeta esse gráfico ao vivo no dashboard. Tipos suportados: `bar`, `scatter`, `pie`, `line`.

Lembre-se: O dashboard e o servidor MCP interagem dinamicamente. Caso algo quebre, use `inspect_chart_health` para diagnosticar o SQL problemático.
