---
name: transferegov-sql-analytics
description: Queries SQL analíticas testadas para cruzamentos de dados no banco transferegov_db.
---

# TransfereGov SQL Analytics Skill

Referência de consultas SQL validadas para alimentar os gráficos Plotly do dashboard.
Banco: `transferegov_db` · User: `cognee` · Host: `127.0.0.1:5432`

## Como executar
```python
from src.db_utils import query_df
df = query_df("SELECT ...")
```

---

## 📊 Cruzamentos Aprovados

### Emendas × IDHM Municipal
```sql
SELECT
    m.nome AS municipio,
    m.uf,
    m.regiao,
    m.idhm,
    m.populacao,
    COUNT(pa.plano_acao_id) AS total_planos,
    SUM(pa.valor_total) AS valor_total,
    ROUND(SUM(pa.valor_total) / NULLIF(m.populacao, 0), 2) AS per_capita
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
JOIN beneficiario_ibge_map bim ON b.beneficiario_id = bim.beneficiario_id
JOIN municipios_ibge m ON bim.municipio_id = m.municipio_id
WHERE pa.plano_acao_situacao NOT IN ('CANCELADO')
GROUP BY m.nome, m.uf, m.regiao, m.idhm, m.populacao
HAVING SUM(pa.valor_total) > 0
ORDER BY valor_total DESC;
```

### Emendas × Partido × UF (Ranking parlamentar)
```sql
SELECT
    p.parlamentar_nome,
    pd.sigla_partido AS partido,
    p.uf,
    COUNT(*) AS total_emendas,
    SUM(p.valor_total) AS valor_total,
    SUM(CASE WHEN p.plano_acao_situacao IN ('IMPEDIDO','REPROVADO','CANCELADO') THEN 1 ELSE 0 END) AS total_negados,
    ROUND(100.0 * SUM(CASE WHEN p.plano_acao_situacao IN ('IMPEDIDO','REPROVADO','CANCELADO') THEN 1 ELSE 0 END) / COUNT(*), 1) AS taxa_impedimento
FROM parlamentar_beneficiario p
LEFT JOIN parlamentares_dados pd ON UPPER(pd.nome) = UPPER(p.parlamentar_nome)
GROUP BY p.parlamentar_nome, pd.sigla_partido, p.uf
ORDER BY valor_total DESC;
```

### Situação dos Planos por UF
```sql
SELECT
    b.uf,
    pa.plano_acao_situacao AS situacao,
    COUNT(*) AS total,
    SUM(pa.valor_total) AS valor_total
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
GROUP BY b.uf, pa.plano_acao_situacao
ORDER BY b.uf, valor_total DESC;
```

### Emendas × SICONFI (Dependência Fiscal)
```sql
SELECT
    s.uf,
    s.municipio,
    s.receita_corrente,
    s.despesa_corrente,
    SUM(pa.valor_total) AS total_emendas,
    ROUND(100.0 * SUM(pa.valor_total) / NULLIF(s.receita_corrente, 0), 2) AS pct_dependencia_emenda
FROM siconfi_dados s
JOIN beneficiarios b ON UPPER(b.municipio) = UPPER(s.municipio) AND b.uf = s.uf
JOIN planos_acao pa ON pa.beneficiario_id = b.beneficiario_id
GROUP BY s.uf, s.municipio, s.receita_corrente, s.despesa_corrente
ORDER BY pct_dependencia_emenda DESC;
```

### Emendas × Compras Públicas (PNCP)
```sql
SELECT
    b.uf,
    b.municipio,
    SUM(pa.valor_total) AS total_emendas,
    COUNT(DISTINCT c.contrato_id) AS total_contratos,
    SUM(c.valor_contrato) AS valor_contratado,
    ROUND(SUM(c.valor_contrato) / NULLIF(SUM(pa.valor_total), 0), 2) AS ratio_execucao
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
LEFT JOIN compras_publicas c ON c.beneficiario_id = b.beneficiario_id
WHERE pa.plano_acao_situacao = 'EM_EXECUCAO'
GROUP BY b.uf, b.municipio
ORDER BY total_emendas DESC;
```

### Fluxo Sankey: Parlamentar → Situação
```sql
SELECT
    pb.parlamentar_nome AS parlamentar,
    pa.plano_acao_situacao AS situacao,
    SUM(pb.valor_total) AS valor
FROM parlamentar_beneficiario pb
JOIN planos_acao pa ON pa.emenda_codigo = pb.emenda_codigo
GROUP BY pb.parlamentar_nome, pa.plano_acao_situacao
HAVING SUM(pb.valor_total) > 1000000
ORDER BY valor DESC
LIMIT 50;
```

---

## Dicas de Performance
- Sempre use `NULLIF(campo, 0)` antes de dividir para evitar `ZeroDivisionError`.
- Use `HAVING SUM(...) > 0` para excluir linhas sem dados.
- Prefira `query_df()` de `src.db_utils` — já configura o timeout e fecha a conexão.
- Para gráficos de mapa, normalize os nomes de `uf` para SIGLA em MAIÚSCULAS (ex: `UPPER(b.uf)`).
