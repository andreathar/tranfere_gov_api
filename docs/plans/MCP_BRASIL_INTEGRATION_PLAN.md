# Plano de Integração mcp-brasil → TransfereGov Extractor

## Visão Geral

O projeto **TransfereGov Extractor** já possui uma arquitetura sólida para extração de Planos de Ação do sistema Transferegov (Transferências Especiais / Emendas Pix). O **mcp-brasil** oferece 533 tools em 70 features que podem enriquecer, validar e expandir significativamente este projeto.

---

## 1. Features mcp-brasil Diretamente Relevantes

### 1.1 Feature `transferegov` (Já ativa)
| Tool | Uso no Projeto |
|------|----------------|
| `transferegov_buscar_emendas_pix` | Validação cruzada dos dados extraídos via API direta |
| `transferegov_resumo_emendas_ano` | Benchmarking: comparar totais extraídos vs. totais oficiais |
| `transferegov_emendas_por_municipio` | Enriquecer dados de municípios com info de emendas |
| `transferegov_buscar_emenda_por_autor` | Análise por parlamentar (cross-ref com `parlamentares` table) |
| `transferegov_detalhe_emenda` | Detalhamento profundo de planos específicos (valores custeio/investimento) |

### 1.2 Features Complementares de Alto Valor

| Feature | Tools Relevantes | Aplicação |
|---------|------------------|-----------|
| **`camara`** | `camara_deputados`, `camara_despesas_deputado`, `camara_proposicoes` | Cruzar parlamentares autores de emendas com votações, despesas, proposições |
| **`senado`** | `senado_senadores`, `senado_materias`, `senado_emendas_materia` | Mesmo para senadores |
| **`tse`** | `tse_candidatos`, `tse_bens_candidato`, `tse_prestacao_contas` | Perfil eleitoral dos parlamentares autores |
| **`transparencia`** | `transparencia_contratos`, `transparencia_despesas`, `transparencia_licitacoes` | Verificar execução orçamentária pós-repasse |
| **`compras`** | `compras_contratos`, `compras_licitacoes`, `compras_fornecedores` | Rastrear contratos firmados com recursos das emendas |
| **`ibge`** | `ibge_municipios`, `ibge_estados`, `ibge_populacao` | Enriquecer `beneficiarios` com dados demográficos/econômicos |
| **`bacen`** | `bacen_series_temporais` (IPCA, PIB, câmbio) | Deflacionar valores monetários para análise real |
| **`tcu`** | `tcu_acordaos`, `tcu_inabilitados`, `tcu_idoneos` | Auditoria: cruzar beneficiários/parlamentares com sanções TCU |
| **`tce_*`** (27 TCs estaduais) | `tce_sp_despesas`, `tce_rj_obras_paralisadas`, etc. | Fiscalização subnacional da execução |
| **`diario_oficial`** | `diario_oficial_buscar` | Acompanhar publicações de convênios/termos de execução |
| **`brasilapi`** | `brasilapi_consultar_cnpj`, `brasilapi_consultar_cep` | Validar CNPJs/CEPs dos beneficiários |
| **`spu_imoveis`** | `spu_imoveis_consultar` | Verificar imóveis da União nos municípios beneficiados |

---

## 2. Ideias de Integração por Fase

### FASE 1 — Validação & Enriquecimento Imediato (Baixo Esforço)

#### 1.1 Validação Cruzada de Totais
```python
# Em src/transferegov_extract.py, após extração:
# Comparar total extraído vs. total oficial mcp-brasil
mcp_total = call_tool("transferegov_resumo_emendas_ano", {"ano": 2026})
local_total = df["valorTotal"].sum()
assert abs(local_total - mcp_total) / mcp_total < 0.05  # 5% tolerância
```

#### 1.2 Enriquecimento de Municípios (IBGE)
```python
# Adicionar colunas ao DataFrame antes de exportar:
# - população, PIB per capita, região, mesorregião, microrregião
mcp_data = call_tool("ibge_municipios", {"uf": "SP"})  # ou buscar todos
```

#### 1.3 Validação de CNPJs (BrasilAPI)
```python
# Validar CNPJs dos beneficiários antes de importar no DB
for cnpj in df["beneficiarioCnpj"].unique():
    result = call_tool("brasilapi_consultar_cnpj", {"cnpj": cnpj})
    if "erro" in result:
        logger.warning(f"CNPJ inválido: {cnpj}")
```

### FASE 2 — Análise de Parlamentares & Execução (Médio Esforço)

#### 2.1 Perfil Completo do Parlamentar Autor
```python
# Para cada parlamentar único no dataset:
parlamentar = call_tool("camara_deputados", {"nome": "Arthur Lira"})
despesas = call_tool("camara_despesas_deputado", {"id": parlamentar.id, "ano": 2026})
proposicoes = call_tool("camara_proposicoes", {"autor": parlamentar.id})
bens = call_tool("tse_bens_candidato", {"nome": "Arthur Lira", "ano": 2022})
```

#### 2.2 Rastreamento da Execução (Transparência + Compras)
```python
# Após repasse liberado (situacao = CONCLUIDO/EM_EXECUCAO):
contratos = call_tool("compras_contratos", {
    "municipio": beneficiario_nome,
    "uf": uf,
    "data_inicio": data_repasse
})
licitacoes = call_tool("compras_licitacoes", {...})
```

#### 2.3 Auditoria TCU/TCs
```python
# Verificar se beneficiário ou parlamentar tem sanções
sanções_tcu = call_tool("tcu_inabilitados", {"nome": parlamentar_nome})
sanções_tce = call_tool("tce_sp_despesas", {"municipio": beneficiario_nome})
```

### FASE 3 — Pipeline Automatizado & Dashboards (Alto Esforço)

#### 3.1 Pipeline Diário/Semanal com `planejar_consulta` + `executar_lote`
```python
# Plano de execução multi-fonte para relatório semanal
plano = planejar_consulta("""
Gerar relatório semanal de emendas pix 2026:
1. Buscar novas emendas (transferegov_buscar_emendas_pix)
2. Para cada parlamentar autor: buscar despesas Câmara (camara_despesas_deputado)
3. Para cada município beneficiado: buscar contratos (compras_contratos)
4. Cruzar com sanções TCU (tcu_inabilitados)
5. Agregar por UF/região com dados IBGE
""")
resultados = executar_lote(plano.consultas)
```

#### 3.2 Dataset Unificado para Análise (DuckDB/Parquet)
```python
# Exportar tudo para Parquet particionado por ano/UF/objeto
# Permite queries OLAP rápidas via DuckDB ou Polars
```

#### 3.3 Alertas Automatizados
- Nova emenda para município monitorado
- Parlamentar com sanção TCU recebendo emendas
- Execução orçamentária divergente do repasse

---

## 3. Arquitetura Técnica Sugerida

### 3.1 Novo Módulo: `src/mcp_integration/`
```
src/mcp_integration/
├── __init__.py
├── client.py           # Wrapper assíncrono para mcp-brasil
├── cache.py            # Cache local (Redis/SQLite) para evitar rate limits
├── enrichers/
│   ├── __init__.py
│   ├── municipios.py   # IBGE, BrasilAPI
│   ├── parlamentares.py # Câmara, Senado, TSE
│   ├── execucao.py     # Transparência, Compras
│   └── auditoria.py    # TCU, TCEs
├── validators/
│   ├── __init__.py
│   ├── cnpj.py
│   ├── totals.py
│   └── schema.py
└── pipeline.py         # Orquestração de enriquecimento em lote
```

### 3.2 Configuração (`.env` / `config/settings.py`)
```python
# config/settings.py — adicionar
MCP_BRASIL_ENABLED = True
MCP_BRASIL_CACHE_TTL = 3600  # 1 hora
MCP_BRASIL_RATE_LIMIT = 10   # req/s
MCP_BRASIL_FEATURES = [
    "transferegov", "camara", "senado", "ibge",
    "brasilapi", "transparencia", "compras", "tcu"
]
```

### 3.3 CLI Estendido (`run.sh`)
```bash
./run.sh enrich --municipios --parlamentares --execucao
./run.sh audit --tcu --tce-sp
./run.sh report --weekly --output dashboard/
```

---

## 4. Exemplos Práticos de Código

### 4.1 Cliente MCP Assíncrono
```python
# src/mcp_integration/client.py
import asyncio
from typing import Any, Dict, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPBrasilClient:
    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Any] = {}
        self._session: Optional[ClientSession] = None

    async def __aenter__(self):
        params = StdioServerParameters(
            command="uvx",
            args=["--from", "mcp-brasil", "python", "-m", "mcp_brasil.server"],
        )
        self._read, self._write = await stdio_client(params).__aenter__()
        self._session = ClientSession(self._read, self._write)
        await self._session.initialize()
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.__aexit__(*args)

    async def call_tool(self, name: str, args: Dict) -> Any:
        cache_key = f"{name}:{hash(frozenset(args.items()))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = await self._session.call_tool(name, args)
        self._cache[cache_key] = result
        return result

    async def call_batch(self, calls: List[Dict]) -> List[Any]:
        """Executa múltiplas tools em paralelo via executar_lote."""
        return await self.call_tool("mcp_brasil_executar_lote", {"consultas": calls})
```

### 4.2 Enriquecedor de Municípios
```python
# src/mcp_integration/enrichers/municipios.py
async def enriquecer_municipios(client: MCPBrasilClient, df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona dados IBGE aos municípios beneficiários."""
    ufs = df["uf"].unique()
    ibge_data = {}
    
    for uf in ufs:
        result = await client.call_tool("ibge_municipios", {"uf": uf})
        for mun in result:
            key = (mun["nome"].upper(), uf)
            ibge_data[key] = {
                "populacao": mun.get("populacao"),
                "pib_per_capita": mun.get("pib_per_capita"),
                "regiao": mun.get("regiao"),
                "mesorregiao": mun.get("mesorregiao"),
                "microrregiao": mun.get("microrregiao"),
            }
    
    def lookup(row):
        key = (str(row["beneficiarioNome"]).upper(), row["uf"])
        return ibge_data.get(key, {})
    
    enriched = df.apply(lookup, axis=1, result_type="expand")
    return pd.concat([df, enriched], axis=1)
```

### 4.3 Validador de Totais
```python
# src/mcp_integration/validators/totals.py
async def validar_totais_anuais(client: MCPBrasilClient, df: pd.DataFrame, ano: int) -> Dict:
    """Compara totais extraídos vs. API oficial mcp-brasil."""
    mcp_result = await client.call_tool("transferegov_resumo_emendas_ano", {"ano": ano})
    mcp_total = parse_mcp_total(mcp_result)
    local_total = df["valorTotal"].sum()
    
    diff_pct = abs(local_total - mcp_total) / mcp_total * 100
    return {
        "ano": ano,
        "mcp_total": mcp_total,
        "local_total": local_total,
        "diff_pct": diff_pct,
        "status": "OK" if diff_pct < 5 else "DIVERGÊNCIA"
    }
```

---

## 5. Roadmap de Implementação

| Semana | Entregável | Tools mcp-brasil |
|--------|------------|------------------|
| 1 | Cliente MCP assíncrono + cache | `transferegov`, `ibge`, `brasilapi` |
| 2 | Validação cruzada de totais + CNPJ | `transferegov_resumo_emendas_ano`, `brasilapi_consultar_cnpj` |
| 3 | Enriquecimento IBGE (população, PIB, região) | `ibge_municipios`, `ibge_estados` |
| 4 | Perfil parlamentar (Câmara + TSE) | `camara_deputados`, `camara_despesas_deputado`, `tse_candidatos` |
| 5 | Rastreamento execução (Compras + Transparência) | `compras_contratos`, `transparencia_despesas` |
| 6 | Auditoria TCU/TCEs | `tcu_inabilitados`, `tce_sp_despesas` |
| 7 | Pipeline `planejar_consulta` + `executar_lote` | Orquestração multi-fonte |
| 8 | Dashboard/Relatórios automatizados | Export Parquet + DuckDB + Metabase/Streamlit |

---

## 6. Benefícios Esperados

| Métrica | Atual | Com mcp-brasil |
|---------|-------|----------------|
| **Cobertura de validação** | 0% (apenas schema local) | 100% (cruzamento API oficial) |
| **Dados por município** | Nome, UF, CNPJ | + População, PIB, região, IDEB, saneamento |
| **Dados por parlamentar** | Nome, partido | + Despesas, votações, bens, doações, sanções |
| **Rastreamento execução** | Nenhum | Contratos, licitações, pagamentos, obras |
| **Auditoria** | Manual | Automatizada (TCU + 27 TCEs) |
| **Frequência de atualização** | Sob demanda | Diária/semanal automatizada |

---

## 7. Próximos Passos Imediatos

1. **Instalar mcp-brasil no ambiente de dev**
   ```bash
   pip install mcp-brasil
   # ou
   uv add mcp-brasil
   ```

2. **Testar tools transferegov** (já disponíveis no servidor MCP)
   ```python
   # Testar no Python REPL
   from mcp import ClientSession, StdioServerParameters
   from mcp.client.stdio import stdio_client
   ```

3. **Criar `src/mcp_integration/client.py`** com wrapper assíncrono

4. **Adicionar flag `--enrich` no `transferegov_extract.py`** para enriquecimento opcional

5. **Criar script `src/enrich_municipios.py`** standalone para testar IBGE

---

## 8. Referências

- **mcp-brasil GitHub**: https://github.com/mcp-brasil/mcp-brasil
- **Documentação Tools**: `mcp_mcp-brasil__search_tools` / `mcp_mcp-brasil__listar_features`
- **TransfereGov API Docs**: `data/swagger.yaml` (engenharia reversa)
- **Schema DB**: `data/schema.sql` + `data/migration_002_relatorios.sql`
- **AGENTS.md**: Contexto completo do projeto para agentes