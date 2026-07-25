---
name: localai-batch-processing
description: Utilização do backend LocalAI para jobs longos, processamento e análise do banco.
---

# LocalAI Batch Processing Skill

Para automatizar verificações longas (ex: processamento NLP em descrições de licitação, validação lógica de relatórios) usamos integração com modelos abertos rodando localmente (via servidor compatível com a API OpenAI em http://localhost:8080 ou backend LocalAI nativo).

## Diretrizes
- Jobs em lote devem rodar de forma assíncrona com `run_command` contendo `WaitMsBeforeAsync` ajustado para não travar a conversa primária.
- Prefira scripts em Python para gerenciar o rate limit e as conexões com o `transferegov_db`.
- Quando sumariar muitos registros, puxe os dados da base via `pandas` (ex: `src.db_utils.query_df`), empacote o input e envie via chamadas HTTP (usando `openai` package ou requisições `requests` com a base_url apontando para seu LocalAI).
- Gere `artifacts` em Markdown para salvar a sumarização e as anomalias localizadas na execução do lote.
