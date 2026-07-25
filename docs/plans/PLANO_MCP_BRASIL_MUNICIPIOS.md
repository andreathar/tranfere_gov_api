# Plano de Aprendizado: mcp-brasil para Dados Municipais

## Contexto

O projeto TransfereGov possui um pipeline de enriquecimento que atualmente popula a tabela `municipios_ibge` com dados básicos (nome, UF, região, mesorregião, microrregião) e vincula beneficiários a códigos IBGE via match fuzzy. O **mcp-brasil** (533 tools, 70 features) oferece acesso a uma variedade de fontes de dados que podem enriquecer significativamente a análise por município.

Este plano mapeia: o que o mcp-brasil oferece → o que o projeto já tem → gaps → caminho de aprendizado.

---

## 1. Dados Municipais Disponíveis no mcp-brasil

### 1.1 IBGE (População, PIB, Geografia)

**Tools**: `ibge_listar_estados`, `ibge_buscar_municipios`, `ibge_buscar_municipio_por_codigo`, `ibge_municipio_por_codigo`, `ibge_buscar_agregados`, `ibge_obter_agregado`, `ibge_listar_pesquisas`, `ibge_listar_agregados_por_pesquisa`, `ibge_consultar_nomes`, `ibge_ranking_nomes`, `ibge_malha_geografica`

**Agregados pré-configurados** (constants.py):
| Agregado | ID | Variável | Descrição |
|----------|-----|----------|-----------|
| População | 6579 | 9324 | População residente estimada |
| PIB | 5938 | 37 | Produto Interno Bruto a preços correntes |
| PIB per capita | 6784 | 9812 | Valores correntes (apenas nível país) |
| Área territorial | 1301 | 615 | Área em km² |

**Exemplo de uso**:
```python
# Buscar municípios de SP
municipios = ibge_buscar_municipios(uf="SP")

# Obter população de um município por código
pop = ibge_buscar_agregados(tabela=6579, localidade="N6[3550308]", variavel=9324)

# Malha geográfica (GeoJSON)
malha = ibge_malha_geografica(municipio=3550308)
```

### 1.2 SICONFI (Finanças Municipais)

**Tools**: `siconfi_listar_entes`, `siconfi_consultar_rreo`, `siconfi_consultar_rgf`, `siconfi_consultar_dca`, `siconfi_exportar_dca_json`

**Dados disponíveis**:
- **DCA** (Declaração de Contas Anuais): receitas, despesas, patrimônio
- **RREO** (Relatório Resumido da Execução Orçamentária): execução orçamentária
- **RGF** (Relatório de Gestão Fiscal): dívida, investimentos, pessoal

**Exemplo**:
```python
# Listar entes disponíveis
entes = siconfi_listar_entes(tipo="M")

# Consultar RREO de um município
rreo = siconfi_consultar_rreo(ano=2025, periodo=6, ibge=3550308)
```

### 1.3 Compras/PNCP (Licitações e Contratos Municipais)

**Tools**: `compras_buscar_contratacoes`, `compras_listar_modalidades`, `compras_consultar_contratacao`

**Dados disponíveis**: licitações, contratos, fornecedores em nível municipal
- Modalidades: Pregão Eletrônico (6), Dispensa (8), Inexigibilidade (9), Concorrência (4)
- Filtro por UF, CNPJ órgão, período

### 1.4 FNDE (Transferências Educacionais)

**Tools**: `fnde_listar_programas`, `fnde_buscar_transferencias_por_municipio`

**Dados**: repasses do FNDE (fundo de educação federal) por município

### 1.5 Farmácia Popular (Saúde)

**Tools**: `farmacia_popular_listar_unidades`, `farmacia_popular_consultar_unidade`

**Dados**: unidades credenciadas do Programa Farmácia Popular por município

### 1.6 Atlas da Violência (Segurança)

**Tools**: `atlas_violencia_consultar_municipio`

**Dados**: taxas de homicídio, roubo, violência por município e ano

### 1.7 TSE (Dados Eleitorais)

**Tools** (6 módulos): `tse_listar_candidatos`, `tse_consultar_candidato`, `tse_listar_bens`, `tse_listar_doacoes`, `tse_listar_prestacao_contas`, `tse_listar_eleitores`

**Dados**: perfil eleitoral, bens, doações de parlamentares autores de emendas

### 1.8 Transparência Federal (Gastos)

**Tools**: `transparencia_listar_despesas`, `transparencia_listar_contratos`, `transparencia_listar_licitacoes`

**Dados**: execução orçamentária, contratos, licitações em nível federal/municipal

---

## 2. Estado Atual do Projeto

### 2.1 Pipeline de Enriquecimento Atual

```
Fase 1a: validacao.py    → Valida CNPJs (BrasilAPI)
Fase 1b: ibge.py          → Lista municípios por UF (APENAS nomes/códigos/geo)
Fase 1c: mapear_municipios.py → Match fuzzy beneficiário→IBGE
Fase 2:  camara.py        → Perfil deputados autores
Fase 3:  pipeline.py      → Agregação parlamentar×município×emenda
```

### 2.2 Tabela `municipios_ibge` (schema atual)

```sql
CREATE TABLE municipios_ibge (
    municipio_id INTEGER PRIMARY KEY,  -- código IBGE 7 dígitos
    nome TEXT,
    uf CHAR(2),
    regiao TEXT,
    mesorregiao TEXT,
    microrregiao TEXT
);
```

### 2.3 O que falta (Gaps)

| Dimensão | Dados Atuais | Dados Disponíveis no mcp-brasil |
|----------|-------------|--------------------------------|
| Demografia | Nome, UF, região | + População, área, PIB, PIB per capita |
| Economia | Nada | + Receitas/despesas (SICONFI), PIB, IDHM |
| Compras | Nada | + Licitações, contratos, fornecedores |
| Educação | Nada | + Repasses FNDE, escolas |
| Saúde | Nada | + Farmácias populares, UBS |
| Segurança | Nada | + Taxas de violência/homicídio |
| Política | Nada | + Dados eleitorais, perfil parlamentar |
| Execução | Nada | + Despesas federais, contratos públicos |

---

## 3. Caminho de Aprendizado (Priorizado)

### Prioridade 1: Enriquecimento Demográfico/Econômico (IBGE)
**Objetivo**: Adicionar população, PIB e área territorial à tabela `municipios_ibge`

1. Estudar `references/mcp-brasil/src/mcp_brasil/data/ibge/tools.py` (11 tools)
2. Entender o sistema de agregados (IDs de tabelas IBGE)
3. Criar script `src/enrichers/ibge_agregados.py` que:
   - Consulta população (tabela 6579, variável 9324) para cada município mapeado
   - Consulta PIB (tabela 5938, variável 37) para cada município
   - Consulta área territorial (tabela 1301, variável 615)
   - Atualiza `municipios_ibge` com novas colunas
4. Adicionar migration SQL para novas colunas (`populacao`, `pib`, `area_km2`)

### Prioridade 2: Finanças Municipais (SICONFI)
**Objetivo**: Dados fiscais dos municípios que recebem transferências

1. Estudar `references/mcp-brasil/src/mcp_brasil/data/siconfi/tools.py`
2. Entender RREO (execução orçamentária) e RGF (gestão fiscal)
3. Criar tabela `municipios_financeiro` (receitas, despesas, dívida)
4. Script `src/enrichers/siconfi.py` que:
   - Consulta RREO dos municípios mapeados (último período disponível)
   - Extrai receitas correntes, despesas correntes, investimentos
   - Salva na nova tabela

### Prioridade 3: Compras e Contratos (PNCP)
**Objetivo**: Rastrear licitações e contratos nos municípios beneficiários

1. Estudar `references/mcp-brasil/src/mcp_brasil/data/compras/pncp/tools.py`
2. Criar tabela `municipios_compras` (contratos recentes)
3. Script `src/enrichers/compras_municipios.py` que:
   - Busca licitações dos últimos 6 meses por UF
   - Filtra por texto relacionado aos objetos do programa
   - Agrega por município

### Prioridade 4: Transferências Educacionais (FNDE)
**Objetivo**: Cruzar emendas pix com repasses do FNDE

1. Estudar `references/mcp-brasil/src/mcp_brasil/data/fnde/`
2. Criar tabela `municipios_fnde` (programas, valores)
3. Script `src/enrichers/fnde.py` que:
   - Lista programas disponíveis
   - Busca transferências dos municípios mapeados
   - Cruza com dados de emendas pix

---

## 4. Integração Técnica

### 4.1 Como mcp-brasil funciona (importante!)

O mcp-brasil é uma **biblioteca Python**, NÃO um protocolo MCP para conectar:
```python
# Forma correta de usar
from mcp_brasil.data.ibge.tools import ibge_buscar_municipios
# Chamar diretamente como função Python

# OU via FastMCP server (se rodar como MCP server)
# Não precisa de stdio_client / ClientSession
```

**Convenção ADR-001**:
- `tools.py` NUNCA faz HTTP diretamente — delega para `client.py`
- `client.py` usa `httpx` + cache
- `schemas.py` define Pydantic models

### 4.2 Configuração

Adicionar em `config/settings.py`:
```python
# Enriquecimento via mcp-brasil
MCP_BRASIL_ENABLED = True
MCP_BRASIL_CACHE_TTL = 3600  # 1 hora
MCP_BRASIL_RATE_LIMIT = 0.2  # 5s entre requests (igual ENRICH_RATE_LIMIT)
```

### 4.3 Padrão de Enriquecedor

Seguir o padrão existente em `src/enrichers/`:
- Script standalone via `python3 -m src.enrichers.<nome>`
- Aceita `--dry-run` e `--limit N`
- Usa `psycopg2` direto (sem ORM)
- Idempotente (INSERT...ON CONFLICT)
- Rate limit entre requests
- Logs em PT-BR

---

## 5. Referências

- **Fonte primária**: `references/mcp-brasil/src/mcp_brasil/data/` (57 features)
- **Plano existente**: `MCP_BRASIL_INTEGRATION_PLAN.md` (320 linhas, roadmap 8 semanas)
- **Schema atual**: `data/migration_002_relatorios.sql`
- **Enricher atual**: `src/enrichers/ibge.py` (92 LOC)
- **Fuzzy matching**: `src/enrichers/mapear_municipios.py` (104 LOC)
