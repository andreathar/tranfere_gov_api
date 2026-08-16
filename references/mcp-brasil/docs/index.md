# mcp-brasil Documentation

**MCP Server para 39 APIs publicas brasileiras**

309 tools · 80 resources · 62 prompts · 36 APIs sem chave · 14 areas tematicas

---

## O que e o mcp-brasil?

O mcp-brasil e um pacote Python que expoe APIs publicas brasileiras como um servidor [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Ele permite que AI agents (Claude, GPT, Copilot, etc.) consultem dados governamentais oficiais do Brasil em linguagem natural.

### O que ele cobre

| Categoria | O que voce pode perguntar |
|-----------|--------------------------|
| **Economia e Financas** | Selic, IPCA, cambio, PIB, financiamentos BNDES, precos de saude |
| **Geografia e Estatistica** | Estados, municipios, populacao, nomes, agregados demograficos |
| **Legislativo** | Deputados, senadores, projetos de lei, votacoes, despesas parlamentares |
| **Transparencia e Fiscalizacao** | Contratos federais, despesas, servidores, sancoes, TCU, 9 TCEs estaduais |
| **Judiciario** | Processos judiciais, jurisprudencia do STF/STJ/TST, acordaos do TCU |
| **Eleitoral** | Candidatos, resultados de eleicoes, prestacao de contas, anuncios eleitorais |
| **Meio Ambiente** | Focos de queimadas, desmatamento, reservatorios, estacoes hidrologicas |
| **Saude** | Estabelecimentos de saude, profissionais, leitos, vacinacao, SRAG, ANVISA, auditorias |
| **Seguranca Publica** | Publicacoes sobre violencia, criminalidade, Atlas da Violencia, Anuario FBSP |
| **Compras Publicas** | Licitacoes, contratos (PNCP + ComprasNet/SIASG), transferencias |
| **Educacao** | Dados do Cadastro Nacional de Estabelecimentos de Saude (RENAME) |
| **Utilidades** | CEP, CNPJ, bancos, FIPE, diarios oficiais, datasets abertos, tabua de mares |

## Documentacao

| Pagina | Descricao |
|--------|-----------|
| [Quick Start](guide/quickstart.md) | Instalacao e configuracao em 2 minutos |
| [Arquitetura](concepts/architecture.md) | Como o projeto funciona por dentro |
| [Catalogo de Features](reference/features.md) | Todas as 39 features e suas 309 tools |
| [Smart Tools](reference/smart-tools.md) | Meta-tools: planner, batch, discovery |
| [Adicionando Features](guide/adding-features.md) | Guia para contribuir com novas APIs |
| [Configuracao](reference/configuration.md) | Variaveis de ambiente e opcoes |
| [Desenvolvimento](guide/development.md) | Setup de dev, testes, lint, CI |
