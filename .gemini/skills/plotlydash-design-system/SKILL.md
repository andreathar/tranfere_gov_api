---
name: plotlydash-design-system
description: Design System completo para gráficos Plotly do projeto TransfereGov — paleta, padrões de interação e templates de código.
---

# PlotlyDash Design System — TransfereGov

Este documento é a referência canônica de design para todos os gráficos do dashboard.
**Todo gráfico novo DEVE obedecer estas diretrizes.**

---

## Tokens de Design (Dark Slate)
```python
from src.graphs.theme import (
    THEME_CARD_BG,  # "#1e293b"  — fundo do card
    THEME_TEXT,     # "#f8fafc"  — texto principal
    THEME_GRID,     # "#334155"  — linhas de grade
    CORES_SITUACAO, # dict → situação → hex
    aplicar_tema,   # função obrigatória de aplicação do tema
)
```

## Paleta de Cores Aprovada
| Uso | Cor Hex |
|-----|---------|
| Acento primário (destaque) | `#3b82f6` (azul) |
| Sucesso / Execução | `#22c55e` (verde) |
| Alerta / Impedimento | `#ef4444` (vermelho) |
| Laranja / Rejeição | `#f97316` |
| Roxo / Reprovado | `#a855f7` |
| Cinza / Cancelado | `#64748b` |
| Cor neutra de texto | `#94a3b8` |
| Gradiente regional | `px.colors.sequential.Blues` ou `Viridis` |

**NÃO use**: branco puro, preto puro, ou cores saturadas sem contraste no fundo dark.

---

## Templates de Código por Tipo de Gráfico

### 📊 Bar Chart Horizontal (Rankings)
```python
import plotly.express as px
from src.graphs.theme import aplicar_tema

def build_ranking(df, x_col, y_col, titulo):
    fig = px.bar(
        df.sort_values(x_col, ascending=True).tail(15),
        x=x_col, y=y_col,
        orientation="h",
        color=x_col,
        color_continuous_scale="Blues",
        text=x_col,
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    return aplicar_tema(fig, titulo)
```

### 🫧 Scatter com Bolha (Cruzamentos IDHM × Valor)
```python
fig = px.scatter(
    df,
    x="idhm", y="valor_medio",
    size="total_beneficios",  # tamanho da bolha = volume
    color="regiao",
    hover_name="municipio",
    color_discrete_sequence=px.colors.qualitative.Set2,
)
fig.update_traces(marker=dict(opacity=0.75, line=dict(width=0.5, color="#475569")))
return aplicar_tema(fig, titulo)
```

### 🗺️ Mapa Coroplético (Distribuição por UF)
```python
import plotly.graph_objects as go
import json, urllib.request

# Carrega GeoJSON dos estados brasileiros
geojson_url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
# (ou usar data/brazil_states.json local)

fig = px.choropleth(
    df,
    geojson=geojson,
    locations="uf",
    featureidkey="properties.sigla",
    color="valor_total",
    color_continuous_scale="Blues",
    hover_data=["uf", "valor_total", "total_planos"],
)
fig.update_geos(fitbounds="locations", visible=False)
return aplicar_tema(fig, titulo)
```

### 🌀 Sunburst / Drilldown Hierárquico
```python
fig = px.sunburst(
    df,
    path=["regiao", "uf", "parlamentar_nome"],
    values="valor_total",
    color="taxa_impedimento",
    color_continuous_scale=[[0, "#22c55e"], [0.5, "#f97316"], [1, "#ef4444"]],
)
return aplicar_tema(fig, titulo, altura=550)
```

### 🔀 Sankey (Fluxo Financeiro)
```python
fig = go.Figure(go.Sankey(
    node=dict(
        label=nodes_labels,
        color=nodes_colors,
        pad=15, thickness=20,
    ),
    link=dict(source=links_src, target=links_tgt, value=links_val),
))
return aplicar_tema(fig, titulo, altura=600)
```

### 📡 Radar Chart (Multi-Indicador por UF)
```python
fig = go.Figure()
for uf in ufs_selecionados:
    row = df[df.uf == uf].iloc[0]
    fig.add_trace(go.Scatterpolar(
        r=[row.idhm_norm, row.per_capita_norm, row.taxa_exec_norm, row.saude_norm, row.educ_norm],
        theta=["IDHM", "Emenda/hab", "Execução", "Saúde", "Educação"],
        fill="toself", name=uf,
    ))
fig.update_layout(polar=dict(bgcolor="#0f172a"))
return aplicar_tema(fig, titulo)
```

---

## Registro de Gráficos (`@register_chart`)

Todo novo gráfico no `src/graphs/` deve usar o decorator de registro:
```python
from src.graphs.registry import register_chart

@register_chart(
    id="meu_grafico_id",
    title="Título Legível do Gráfico",
    description="Descrição clara do que a análise mostra.",
    category="Parlamentar",  # categoria da sidebar
    controls=[                # filtros interativos (opcional)
        Control(id="uf_filter", label="Filtrar por UF", options=TODAS_UFS, default="TODOS"),
    ]
)
def build_meu_grafico(uf_filter: str = "TODOS") -> go.Figure:
    ...
```

---

## Anti-Padrões (NUNCA faça)
- ❌ Não retornar `aplicar_tema()` — deixa o gráfico com fundo branco padrão Plotly.
- ❌ Não verificar `fig_has_data(fig)` — risco de caixas brancas vazias no dashboard.
- ❌ Hardcodar strings de conexão com o banco. Use sempre `src.db_utils.get_connection()`.
- ❌ Usar `px.colors.qualitative.Plotly` — cores padrão não combinam com o Dark Slate.
- ❌ Labels em inglês — toda UI deve estar em PT-BR.
- ❌ Títulos de eixos em camelCase ou sem acentuação. Ex: `"Valor Total (R$)"` ✅.

---

## Categorias de Gráficos Existentes
| Categoria | Nº Gráficos | Módulo |
|-----------|------------|--------|
| SICONFI Fiscal | 10 | `siconfi.py` |
| Socioeconômico | 3 | `socioeconomico.py` |
| Hierárquico | 3 | `hierarquico.py` |
| Parlamentar | 2 | `parlamentar.py` |
| Análise Parlamentar | 2 | `parlamentar.py` |
| Fiscal & Geográfico | 2 | `fiscal.py` |
| Geográfico & Mapas | 2 | `geoespacial.py` |
| Impacto Social | 2 | `impacto_social.py` |
| Prefeitos | 2 | `prefeitos.py` |
| Riscos & Impedimentos | 1 | `fiscal.py` |
| Temporal | 1 | `analitico.py` |

**Total: 31 gráficos registrados no `CHART_REGISTRY`.**
