# Guia de Onboarding de Desenvolvimento — TransfereGov API

Este documento fornece um passo a passo completo para configuração do ambiente de desenvolvimento, provisionamento do banco de dados PostgreSQL, execução do pipeline de dados e enriquecimento, e inicialização dos serviços web locais (FastAPI e Plotly Dash MCP).

---

## 1. Pré-requisitos

Antes de iniciar a instalação, certifique-se de que as ferramentas abaixo estão instaladas no seu ambiente operacional Linux / macOS:

### Obrigatórios

- **Python**: versão 3.11 ou superior (recomendado `python3.11`)
- **PostgreSQL**: versão 14 ou superior (com utilitários de CLI `createdb` e `psql`)
- **Git**: para controle de versão e instalação dos hooks de pre-commit
- **virtualenv / venv**: módulo nativo do Python para ambientes virtuais

### Opcionais (funcionalidades avançadas)

- **LocalAI**: servidor de inferência local com API compatível OpenAI. Necessário para RAG v3, geração de personas e dossiês via LLM local. Instalação via Docker. Ver seção 4.
- **Qdrant**: banco de dados vetorial para indexação semântica. Necessário para o pipeline RAG v3. Instalação via Docker. Ver seção 5.
- **GPU (recomendado)**: placa de vídeo com suporte CUDA (mínimo 4 GB VRAM). Melhora drasticamente a velocidade de inferência do LocalAI (36-89 tok/s com GPU vs. ~2 tok/s sem). Sem GPU, os módulos RAG e persona funcionam em modo degradado.

---

## 2. Configuração do Ambiente

Siga as etapas abaixo para clonar o repositório, criar e ativar o ambiente virtual, e instalar as dependências do projeto.

### 2.1. Clonar o Repositório
```bash
git clone https://github.com/andreathar/tranfere_gov_api.git
cd tranfere_gov_api
```

### 2.2. Criar e Ativar o Ambiente Virtual
```bash
# Criar o ambiente virtual na pasta .venv
python3.11 -m venv .venv

# Ativar o ambiente virtual
source .venv/bin/activate
```

### 2.3. Instalar Dependências (Modo Editável + Dev)
```bash
# Instalar o pacote local com suporte a dependências de desenvolvimento
pip install -e ".[dev]"
```

### 2.4. (Recomendado) Configurar Pre-Commit Hooks
Para garantir a aderência às regras de qualidade de código (linter `ruff` e checagem de tipos `mypy`), instale os hooks no repositório local:
```bash
pre-commit install
```

---

## 3. Provisionamento do Banco de Dados PostgreSQL

O projeto exige o PostgreSQL em execução com a base de dados `transferegov_db`.

### 3.1. Configuração do Usuário e Banco de Dados
Por padrão, o sistema utiliza as seguintes credenciais de desenvolvimento (definidas em `config/settings.py`):
- **Host**: `127.0.0.1` (variável `PGHOST`)
- **Porta**: `5432` (variável `PGPORT`)
- **Banco**: `transferegov_db` (variável `PGDATABASE`)
- **Usuário**: `cognee` (variável `PGUSER`)
- **Senha**: `cognee` (variável `PGPASSWORD`)

Se o usuário e o banco ainda não existirem no PostgreSQL local, crie-os com o comando:
```bash
# Criar usuário cognee (caso não exista)
sudo -u postgres psql -c "CREATE USER cognee WITH PASSWORD 'cognee' SUPERUSER;"

# Criar o banco de dados transferegov_db
createdb -h 127.0.0.1 -U cognee transferegov_db
```

### 3.2. Aplicação do Schema Base
Execute o script de schema base (`data/schema.sql`):
```bash
psql -U cognee -h 127.0.0.1 -d transferegov_db -f data/schema.sql
```

### 3.3. Execução das Migrações SQL em Ordem
Conforme especificado em `MIGRATIONS.md`, aplique todas as migrações SQL na sequência numérica:
```bash
# Aplicar todas as migrações na ordem correta
for f in data/migration_*.sql; do
    echo "Aplicando migração: $f..."
    psql -U cognee -h 127.0.0.1 -d transferegov_db -f "$f"
done
```

#### Relação Sequencial de Migrações:
1. `data/migration_002_relatorios.sql` — Tabelas core de relatórios
2. `data/migration_003_enrichment.sql` — Tabelas de enriquecimento (CNPJ, IBGE, Câmara)
3. `data/migration_004_ibge_agregados.sql` — Colunas agregadas do IBGE (população, PIB, área)
4. `data/migration_005_unificacao.sql` — Emendas discricionárias e views unificadas
5. `data/migration_006_datajud.sql` — Cache de processos judiciais DataJud
6. `data/migration_007_siconfi.sql` — Dados financeiros municipais (SICONFI / Tesouro Nacional)
7. `data/migration_008_enriched_views.sql` — Views cruzadas de dados enriquecidos
8. `data/migration_009_novas_fontes.sql` — Compras públicas, saúde, educação e segurança
9. `data/migration_010_prefeitos.sql` — Tabelas e views de inteligência municipal / prefeituras
10. `data/migration_011_tse_deputados.sql` — Cruzamento de dados de deputados com o TSE

---

## 4. Setup LocalAI (Opcional — Inferência Local)

O LocalAI é um servidor de inferência local com API compatível OpenAI. É necessário para o pipeline RAG v3, geração de personas e dossiês via LLM.

### 4.1. Instalação via Docker

```bash
# Com GPU (recomendado — NVIDIA Container Toolkit necessário)
docker run -d --gpus all \
  --name localai \
  -p 8080:8080 \
  -v localai-models:/models \
  localai/localai:latest-gpu-nvidia-cuda-12

# Sem GPU (modo CPU — significativamente mais lento)
docker run -d \
  --name localai \
  -p 8080:8080 \
  -v localai-models:/models \
  localai/localai:latest
```

### 4.2. Download dos Modelos

O projeto utiliza 4 modelos validados (definidos em `config/settings.py`):

```bash
# Modelo principal — RAG e redação PT-BR (36.8 tok/s com GPU)
curl http://localhost:8080/models/apply -H "Content-Type: application/json" \
  -d '{"id": "huggingface://ggml-org/gemma-4-e2b-it-GGUF/gemma-4-e2b-it-Q8_0.gguf"}'

# Modelo rápido — triagem e NER (88.9 tok/s com GPU)
curl http://localhost:8080/models/apply -H "Content-Type: application/json" \
  -d '{"id": "huggingface://Qwen/Qwen2.5-1.5B-Instruct-GGUF/qwen2.5-1.5b-instruct-q4_k_m.gguf"}'

# Modelo de análise profunda (7.7 tok/s com GPU)
curl http://localhost:8080/models/apply -H "Content-Type: application/json" \
  -d '{"id": "huggingface://QuantFactory/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"}'

# Embeddings para indexação vetorial Qdrant
curl http://localhost:8080/models/apply -H "Content-Type: application/json" \
  -d '{"id": "huggingface://nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.Q8_0.gguf"}'
```

### 4.3. Verificação

```bash
# Listar modelos carregados
curl http://localhost:8080/v1/models

# Testar geração
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-4-e2b-it",
    "messages": [{"role": "user", "content": "Resuma o que sao emendas pix em 2 frases."}]
  }'
```

### 4.4. Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `LOCALAI_BASE_URL` | `http://localhost:8080/v1` | Endpoint da API LocalAI |
| `LOCALAI_TIMEOUT` | `300` | Timeout em segundos para requisições |
| `LOCALAI_MAX_RETRIES` | `3` | Número máximo de tentativas |

**Gerenciamento de VRAM**: O módulo `src/localai_manager.py` gerencia a exclusividade de VRAM na GPU automaticamente. Antes de invocar qualquer modelo, o manager descarrega modelos inativos para evitar erros de OOM (estouro de memória). Nunca é necessário descarregar modelos manualmente.

---

## 5. Setup Qdrant (Opcional — Banco Vetorial)

O Qdrant é necessário para o pipeline RAG v3 (indexação vetorial de perfis de deputados e geração de personas).

### 5.1. Instalação via Docker

```bash
# Iniciar Qdrant com persistência de dados
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant-data:/qdrant/storage \
  qdrant/qdrant:latest
```

### 5.2. Verificação

```bash
# Health check
curl http://localhost:6333/healthz

# Listar collections
curl http://localhost:6333/collections
```

### 5.3. Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `QDRANT_URL` | `http://localhost:6333` | Endpoint da API Qdrant |

A collection `deputados_perfis` é criada automaticamente pelo indexador (`src/enrichers/rag_qdrant_indexer.py`) com embeddings do modelo `nomic-embed-text-v1.5` (768 dimensões).

---

## 6. Pipeline de Dados & Enriquecimento

O pipeline de dados opera em duas etapas: extração/ingestão e enriquecimento de dados multi-fonte.

### 6.1. Descobrimento e Extração de Planos de Ação (API Transferegov)
Você pode utilizar o script wrapper `./run.sh` ou invocar diretamente o CLI de extração:

```bash
# 1. Descobrir os objetos de execução disponíveis para o exercício atual (2026)
./run.sh discover

# 2. Extrair TODOS os objetos de 2026 e persistir no PostgreSQL
./run.sh all --db

# Extração customizada por programa e situação (exemplo: Transferências Especiais + IMPEDIDO)
python3 src/transferegov_extract.py --objeto all --ano 2026 --programa 25 --situacao-api IMPEDIDO --db --csv
```

### 6.2. Importação Manual de Arquivos JSON (Opcional)
Se houver arquivos JSON pré-existentes na pasta `output/json/`:
```bash
./run.sh import
```

### 6.3. Pipeline de Enriquecimento Multi-Fase

Após popular o PostgreSQL com os planos de ação base, execute o pipeline de enriquecimento (BrasilAPI + IBGE + Câmara dos Deputados + SICONFI + TSE + Senado):

```bash
# Execução completa de todas as 8 fases de enriquecimento
python3 -m src.enrichers.pipeline --fase all

# (Opcional) Teste sem alterações em banco com limite de registros:
python3 -m src.enrichers.pipeline --fase all --dry-run --limit 100
```

#### Fases do Pipeline (8 fases):

- **Fase 1 (Validacao & IBGE)**:
  - `python3 -m src.enrichers.validacao` -- CNPJs via BrasilAPI
  - `python3 -m src.enrichers.ibge` -- Dados de municipios IBGE
  - `python3 -m src.enrichers.mapear_municipios` -- Mapeamento beneficiario -> IBGE
  - `python3 -m src.enrichers.ibge_agregados` -- Populacao, PIB, area
  - `python3 -m src.enrichers.siconfi` -- Dados financeiros SICONFI (DCA + RREO)
- **Fase 2 (Camara dos Deputados)**:
  - `python3 -m src.enrichers.camara` -- Perfil dos parlamentares
- **Fase 3 (Agregacao & Vinculacao)**:
  - `python3 -m src.enrichers.pipeline --fase 3` -- Cruzamento parlamentar x beneficiario x emenda
- **Fase 4 (Compras Publicas)**:
  - `python3 -m src.enrichers.compras` -- Compras publicas por municipio
- **Fase 5 (Saude & Educacao)**:
  - `python3 -m src.enrichers.saude_educacao` -- Indicadores municipais
- **Fase 6 (DataJud)**:
  - `python3 -m src.enrichers.datajud` -- Processos judiciais vinculados
- **Fase 7 (TSE)**:
  - `python3 -m src.enrichers.tse_prefeitos` -- Prefeitos eleitos (2020/2024)
  - `python3 -m src.enrichers.tse_vereadors` -- Candidatos a vereador (2020/2024)
- **Fase 8 (Senado)**:
  - `python3 -m src.enrichers.senado` -- Senadores em exercicio (API Senado)

### 6.4. Emissão de Relatórios SQL via CLI
```bash
./run.sh report resumo       # Resumo estatístico geral
./run.sh report estado       # Resumo por Estado (UF)
./run.sh report negados      # Planos impedidos/negados
./run.sh report emenda       # Totais por autor de emenda
```

---

## 7. Execução dos Serviços Web Locais

O sistema possui duas aplicações web independentes que podem ser executadas concorrentemente.

### 7.1. Backend API REST & Painel Web (FastAPI)
Painel de Inteligência Parlamentar & Municipal e API REST.

- **Comando**:
  ```bash
  uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
  ```
  *(Alternativamente, via wrapper: `./run.sh web` na porta 8080)*
- **Endereço da Interface Web**: `http://localhost:8000`
- **Documentação Swagger (OpenAPI)**: `http://localhost:8000/docs`
- **Documentação ReDoc**: `http://localhost:8000/redoc`

### 7.2. Dashboard Analítico Interativo & Servidor MCP (Plotly Dash 4.3+)
Dashboard com 68 graficos Plotly (17 modulos) e servidor MCP (Model Context Protocol) integrado para agentes autonomos de IA.

- **Comando**:
  ```bash
  python3 src/dash_app.py
  ```
- **Endereço da Interface Web (Dash)**: `http://localhost:8050`
- **Endpoint do Servidor MCP**: `http://localhost:8050/_mcp`

---

## 8. Jobs Agendados (Cron)

O projeto inclui tres jobs agendados para operacoes recorrentes. Todos podem ser executados manualmente via `./run.sh` ou agendados no cron do sistema.

### 8.1. Diario Oficial (cron-diario)

Baixa e resume atos publicados no Diario Oficial da Uniao (DOU).

```bash
./run.sh cron-diario
# Ou diretamente:
python3 -m src.enrichers.diario_oficial_worker
```

- **Frequencia recomendada**: diaria
- **Descricao**: Realiza scraping do DOU, extrai atos relevantes e gera resumo na tabela `diario_oficial_atos`
- **Dependencias**: conexao com a internet (acesso ao site do DOU)

### 8.2. Indexador Qdrant (cron-qdrant)

Indexa dados de deputados no banco vetorial Qdrant para alimentar o pipeline RAG v3.

```bash
./run.sh cron-qdrant
# Ou diretamente:
python3 -m src.enrichers.rag_qdrant_indexer
```

- **Frequencia recomendada**: semanal
- **Descricao**: Gera embeddings (nomic-embed-text-v1.5, 768d) de 6 tipos de chunks: perfil, emendas, despesas CEAP, proposicoes, votacoes e atas do Diario Oficial
- **Dependencias**: Qdrant rodando (secao 5), LocalAI com modelo de embeddings (secao 4)

### 8.3. Dossie Persona (cron-dossie)

Gera dossies analiticos de deputados via Multi-Query RAG v3 com 5 perspectivas tematicas.

```bash
./run.sh cron-dossie
# Ou diretamente:
python3 -m src.enrichers.rag_persona
```

- **Frequencia recomendada**: sob demanda
- **Descricao**: Para cada deputado, executa 5 consultas no Qdrant (votos, emendas PIX, proposicoes, Diario Oficial, conexoes politicas municipais) e gera persona analitica via LLM
- **Dependencias**: Qdrant indexado (cron-qdrant), LocalAI com modelo gemma (secao 4)

### Agendamento no Cron do Sistema

Exemplo de crontab para execucao automatica:

```bash
# Editar crontab
crontab -e

# Adicionar as seguintes linhas:
0 6 * * *  cd /caminho/para/tranfere_gov_api && ./run.sh cron-diario >> output/logs/cron-diario.log 2>&1
0 3 * * 0  cd /caminho/para/tranfere_gov_api && ./run.sh cron-qdrant >> output/logs/cron-qdrant.log 2>&1
```

---

## 9. Redator Oficial (Quick Start)

Gerador de documentos oficiais seguindo o Manual de Redacao da Presidencia (3a edicao). Tipos suportados: oficio, nota tecnica, parecer, despacho, portaria, ata.

### 9.1. Tipos de Documento

```bash
# Listar todos os tipos disponiveis
./run.sh redator listar-tipos
```

### 9.2. Exemplos Rapidos

```bash
# Nota tecnica para um parlamentar
./run.sh redator nota-tecnica --parlamentar "AFONSO FLORENCE" --ano 2026

# Oficio para autoridade
./run.sh redator oficio --dest "Governador" --cargo "Governador" \
  --assunto "Relatorio de Emendas" --corpo "Segue em anexo..."

# Parecer sobre processo
./run.sh redator parecer --processo "001/2026" --consulta "Analise de emendas"

# Despacho de encaminhamento
./run.sh redator despacho --assunto "Encaminhamento" --texto "Encaminha-se ao MINISTARIO..."

# Validar documento existente
./run.sh redator validar --arquivo "docs/nota.txt" --tipo nota_tecnica
```

### 9.3. Formato de Saida

Os documentos sao gerados em texto simples (`.txt`) no diretorio de output. A data e formatada por extenso (ex: "Brasilia, 27 de julho de 2026.") e os pronomes de tratamento seguem rigorosamente o Manual de Redacao.

Documentacao completa: `docs/REDATOR.md`

---

## 10. Verificacao & Solucao de Problemas (Troubleshooting)

### 10.1. Verificacao da Instalacao e Testes Automatizados

#### Executar a Suíte de Testes com Pytest:
```bash
pytest
```

#### Validar Estilo, Linting e Tipagem Estrita:
```bash
# Executar pre-commit em todos os arquivos
pre-commit run --all-files

# Executar ruff e mypy individualmente
ruff check .
mypy src config tests
```

#### Auditar a Integridade dos 68 Graficos do Dashboard:
```bash
python3 src/verify_graphs.py
```

#### Testar Ferramentas CLI Interativas:
```bash
python3 src/deputado_followup.py --ranking
python3 src/prefeito_followup.py --ranking
```

---

### 10.2. Solucao de Problemas Comuns (Troubleshooting)

| Sintoma / Erro | Causa Provável | Solução Recomendada |
|----------------|----------------|---------------------|
| `psycopg2.OperationalError: could not connect to server` | O serviço do PostgreSQL não está rodando localmente ou as variáveis de ambiente apontam para host/porta incorretos. | Verifique se o daemon do PostgreSQL está ativo (`sudo systemctl status postgresql`). Confirme as variáveis `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`. |
| `FATAL: database "transferegov_db" does not exist` | O banco de dados ainda não foi criado. | Execute `createdb -h 127.0.0.1 -U cognee transferegov_db` e aplique `data/schema.sql` e as migrações. |
| Timeout HTTP ao consultar a API do Transferegov | Restrição de IP / Geoblocking ou lentidão nos servidores do Governo Federal (`transferegov.sistema.gov.br`). | Verifique sua conexão à internet (IPs fora do Brasil podem sofrer bloqueio TCP). O sistema possui retry automático com exponencial backoff. |
| Gráfico exibe aviso "Dados em sincronização ou insuficientes" no Dash | O banco PostgreSQL não possui dados suficientes para a consulta do gráfico selecionado. | Execute `./run.sh all --db` e `python3 -m src.enrichers.pipeline --fase all` para popular o banco de dados. |
| `ModuleNotFoundError: No module named 'src'` | O pacote nao foi instalado em modo editavel ou o `PYTHONPATH` nao inclui a raiz do projeto. | Execute `pip install -e ".[dev]"` na raiz do repositorio ou execute com `PYTHONPATH=. python3 <script>`. |
| `Connection refused` ao LocalAI (`localhost:8080`) | O container LocalAI nao esta rodando ou nao foi iniciado. | Execute `docker ps` para verificar. Se nao estiver listado, inicie com `docker start localai` ou recrie conforme secao 4.1. |
| LocalAI retorna `503 Model not loaded` | O modelo solicitado nao esta carregado na memoria. | O `LocalAIManager` deve descarregar modelos inativos automaticamente. Se persistir, reinicie o container: `docker restart localai`. |
| Erro OOM / CUDA out of memory no LocalAI | A GPU nao possui VRAM suficiente para o modelo solicitado. | Reduza o numero de modelos simultaneos (o manager descarrega automaticamente) ou use modelos menores (qwen2.5-1.5b ao inves de llama-3.1-8b). Verifique com `nvidia-smi`. |
| `Connection refused` ao Qdrant (`localhost:6333`) | O container Qdrant nao esta rodando. | Execute `docker ps` para verificar. Inicie com `docker start qdrant` ou recrie conforme secao 5.1. |
| Qdrant collection `deputados_perfis` nao existe | O indexador Qdrant nunca foi executado ou a collection foi apagada. | Execute `./run.sh cron-qdrant` para recriar e popular a collection automaticamente. |
| Erro de dimensao de embedding no Qdrant | Tentativa de inserir vetores com dimensao incompativel (diferente de 768). | Verifique que o modelo de embeddings e `nomic-embed-text-v1.5` (768d) em `config/settings.py`. Nao misture modelos com dimensoes diferentes. |
