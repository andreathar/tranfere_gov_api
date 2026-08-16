"""Catálogo de 193 séries temporais do Banco Central do Brasil.

Ported from bcb-br-mcp/src/tools.ts SERIES_POPULARES.
Each entry has: codigo (SGS code), nome, categoria, periodicidade.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class SerieBCB:
    """Uma série temporal do catálogo BCB."""

    codigo: int
    nome: str
    categoria: str
    periodicidade: str


SERIES_POPULARES: list[SerieBCB] = [
    # ==================== JUROS E TAXAS ====================
    SerieBCB(11, "Taxa de juros - Selic acumulada no mês", "Juros", "Mensal"),
    SerieBCB(432, "Taxa de juros - Selic anualizada base 252", "Juros", "Diária"),
    SerieBCB(1178, "Taxa de juros - Selic - Meta definida pelo Copom", "Juros", "Diária"),
    SerieBCB(4189, "Taxa de juros - Selic acumulada no mês anualizada", "Juros", "Mensal"),
    SerieBCB(4390, "Taxa de juros - Selic mensal", "Juros", "Mensal"),
    SerieBCB(12, "Taxa de juros - CDI diária", "Juros", "Diária"),
    SerieBCB(4389, "Taxa de juros - CDI anualizada base 252", "Juros", "Diária"),
    SerieBCB(4391, "Taxa de juros - CDI acumulada no mês", "Juros", "Mensal"),
    SerieBCB(4392, "Taxa de juros - CDI acumulada no mês anualizada", "Juros", "Mensal"),
    SerieBCB(226, "Taxa Referencial (TR) - diária", "Juros", "Diária"),
    SerieBCB(7811, "Taxa Referencial (TR) - mensal", "Juros", "Mensal"),
    SerieBCB(7812, "Taxa Referencial (TR) - anualizada", "Juros", "Mensal"),
    SerieBCB(256, "Taxa de Juros de Longo Prazo (TJLP)", "Juros", "Mensal"),
    SerieBCB(253, "Taxa de juros - CDB pré-fixado - 30 dias", "Juros", "Diária"),
    SerieBCB(14, "Taxa de juros - Poupança", "Juros", "Mensal"),
    # ==================== INFLAÇÃO ====================
    SerieBCB(433, "IPCA - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(13522, "IPCA - Variação acumulada em 12 meses", "Inflação", "Mensal"),
    SerieBCB(7478, "IPCA-15 - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(7479, "IPCA-15 - Variação acumulada em 12 meses", "Inflação", "Mensal"),
    SerieBCB(10764, "IPCA-E - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(16121, "IPCA - Núcleo por exclusão - EX0", "Inflação", "Mensal"),
    SerieBCB(16122, "IPCA - Núcleo de dupla ponderação", "Inflação", "Mensal"),
    SerieBCB(11426, "IPCA - Núcleo de médias aparadas com suavização", "Inflação", "Mensal"),
    SerieBCB(11427, "IPCA - Núcleo de médias aparadas sem suavização", "Inflação", "Mensal"),
    SerieBCB(10841, "IPCA - Alimentação e bebidas", "Inflação", "Mensal"),
    SerieBCB(10842, "IPCA - Habitação", "Inflação", "Mensal"),
    SerieBCB(10843, "IPCA - Artigos de residência", "Inflação", "Mensal"),
    SerieBCB(10844, "IPCA - Serviços", "Inflação", "Mensal"),
    SerieBCB(10845, "IPCA - Vestuário", "Inflação", "Mensal"),
    SerieBCB(10846, "IPCA - Transportes", "Inflação", "Mensal"),
    SerieBCB(10847, "IPCA - Saúde e cuidados pessoais", "Inflação", "Mensal"),
    SerieBCB(10848, "IPCA - Despesas pessoais", "Inflação", "Mensal"),
    SerieBCB(10849, "IPCA - Educação", "Inflação", "Mensal"),
    SerieBCB(10850, "IPCA - Comunicação", "Inflação", "Mensal"),
    SerieBCB(4449, "IPCA - Preços administrados", "Inflação", "Mensal"),
    SerieBCB(11428, "IPCA - Preços livres", "Inflação", "Mensal"),
    SerieBCB(188, "INPC - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(13523, "INPC - Variação acumulada em 12 meses", "Inflação", "Mensal"),
    SerieBCB(189, "IGP-M - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(7447, "IGP-10 - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(7448, "IGP-M - 1ª prévia", "Inflação", "Mensal"),
    SerieBCB(7449, "IGP-M - 2ª prévia", "Inflação", "Mensal"),
    SerieBCB(190, "IGP-DI - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(7450, "IPA-M - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(225, "IPA-DI - Geral - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(7459, "IPA-DI - Produtos industriais", "Inflação", "Mensal"),
    SerieBCB(7460, "IPA-DI - Produtos agrícolas", "Inflação", "Mensal"),
    SerieBCB(191, "IPC-DI - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(193, "IPC-Fipe - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(17679, "IPC-3i - Variação mensal", "Inflação", "Mensal"),
    SerieBCB(17680, "IPC-C1 - Variação mensal", "Inflação", "Mensal"),
    # ==================== CÂMBIO ====================
    SerieBCB(1, "Taxa de câmbio - Livre - Dólar americano (venda)", "Câmbio", "Diária"),
    SerieBCB(10813, "Taxa de câmbio - Livre - Dólar americano (compra)", "Câmbio", "Diária"),
    SerieBCB(3698, "Taxa de câmbio - PTAX - Dólar americano (venda)", "Câmbio", "Diária"),
    SerieBCB(3697, "Taxa de câmbio - PTAX - Dólar americano (compra)", "Câmbio", "Diária"),
    SerieBCB(3695, "Taxa de câmbio - PTAX - Dólar americano (média)", "Câmbio", "Diária"),
    SerieBCB(21619, "Taxa de câmbio - Euro (venda)", "Câmbio", "Diária"),
    SerieBCB(21620, "Taxa de câmbio - Euro (compra)", "Câmbio", "Diária"),
    SerieBCB(21623, "Taxa de câmbio - Libra Esterlina (venda)", "Câmbio", "Diária"),
    SerieBCB(21624, "Taxa de câmbio - Libra Esterlina (compra)", "Câmbio", "Diária"),
    SerieBCB(21621, "Taxa de câmbio - Iene (venda)", "Câmbio", "Diária"),
    SerieBCB(21622, "Taxa de câmbio - Iene (compra)", "Câmbio", "Diária"),
    SerieBCB(21625, "Taxa de câmbio - Franco Suíço (venda)", "Câmbio", "Diária"),
    SerieBCB(21626, "Taxa de câmbio - Franco Suíço (compra)", "Câmbio", "Diária"),
    SerieBCB(21637, "Taxa de câmbio - Peso Argentino (venda)", "Câmbio", "Diária"),
    SerieBCB(21638, "Taxa de câmbio - Peso Argentino (compra)", "Câmbio", "Diária"),
    SerieBCB(21639, "Taxa de câmbio - Yuan Chinês (venda)", "Câmbio", "Diária"),
    SerieBCB(21640, "Taxa de câmbio - Yuan Chinês (compra)", "Câmbio", "Diária"),
    # ==================== PIB E ATIVIDADE ECONÔMICA ====================
    SerieBCB(4380, "PIB mensal - Valores correntes (R$ milhões)", "Atividade Econômica", "Mensal"),
    SerieBCB(
        4381,
        "PIB acumulado no ano - Valores correntes (R$ milhões)",
        "Atividade Econômica",
        "Mensal",
    ),
    SerieBCB(
        4382, "PIB acumulado dos últimos 12 meses (R$ milhões)", "Atividade Econômica", "Mensal"
    ),
    SerieBCB(4385, "PIB mensal em US$ (milhões)", "Atividade Econômica", "Mensal"),
    SerieBCB(4386, "PIB acumulado no ano em US$ (milhões)", "Atividade Econômica", "Mensal"),
    SerieBCB(7324, "PIB anual em US$ (milhões)", "Atividade Econômica", "Anual"),
    SerieBCB(
        24363,
        "IBC-Br - Índice de Atividade Econômica (sem ajuste)",
        "Atividade Econômica",
        "Mensal",
    ),
    SerieBCB(
        24364,
        "IBC-Br - Índice de Atividade Econômica (com ajuste sazonal)",
        "Atividade Econômica",
        "Mensal",
    ),
    SerieBCB(29601, "IBC-Br - Agropecuária (sem ajuste)", "Atividade Econômica", "Mensal"),
    SerieBCB(29602, "IBC-Br - Agropecuária (com ajuste sazonal)", "Atividade Econômica", "Mensal"),
    SerieBCB(29603, "IBC-Br - Indústria (sem ajuste)", "Atividade Econômica", "Mensal"),
    SerieBCB(29604, "IBC-Br - Indústria (com ajuste sazonal)", "Atividade Econômica", "Mensal"),
    SerieBCB(29605, "IBC-Br - Serviços (sem ajuste)", "Atividade Econômica", "Mensal"),
    SerieBCB(29606, "IBC-Br - Serviços (com ajuste sazonal)", "Atividade Econômica", "Mensal"),
    SerieBCB(22099, "PIB trimestral - Taxa de variação (%)", "Atividade Econômica", "Trimestral"),
    SerieBCB(
        22103, "Exportação de bens e serviços - Trimestral", "Atividade Econômica", "Trimestral"
    ),
    SerieBCB(
        22104, "Importação de bens e serviços - Trimestral", "Atividade Econômica", "Trimestral"
    ),
    SerieBCB(22109, "Consumo das famílias - Trimestral", "Atividade Econômica", "Trimestral"),
    SerieBCB(22110, "Consumo do governo - Trimestral", "Atividade Econômica", "Trimestral"),
    SerieBCB(
        22111, "Formação bruta de capital fixo - Trimestral", "Atividade Econômica", "Trimestral"
    ),
    SerieBCB(
        21859, "Produção industrial - Geral - Variação mensal", "Atividade Econômica", "Mensal"
    ),
    SerieBCB(
        21860,
        "Produção industrial - Geral - Variação acum. 12 meses",
        "Atividade Econômica",
        "Mensal",
    ),
    SerieBCB(
        21862, "Utilização da capacidade instalada - Indústria", "Atividade Econômica", "Mensal"
    ),
    # ==================== EMPREGO ====================
    SerieBCB(24369, "Taxa de desocupação - PNAD Contínua", "Emprego", "Mensal"),
    SerieBCB(28763, "Taxa de desocupação - PNAD Contínua - Trimestral", "Emprego", "Trimestral"),
    SerieBCB(24370, "Taxa de participação na força de trabalho", "Emprego", "Mensal"),
    SerieBCB(24380, "Rendimento médio real habitual - Todos os trabalhos", "Emprego", "Mensal"),
    SerieBCB(24381, "Massa de rendimento real habitual", "Emprego", "Mensal"),
    SerieBCB(28785, "Pessoal ocupado - Total (milhões)", "Emprego", "Mensal"),
    SerieBCB(28561, "CAGED - Saldo de empregos formais", "Emprego", "Mensal"),
    # ==================== DÍVIDA PÚBLICA E FISCAL ====================
    SerieBCB(4503, "Dívida líquida do setor público (% PIB)", "Fiscal", "Mensal"),
    SerieBCB(4513, "Dívida bruta do governo geral (% PIB)", "Fiscal", "Mensal"),
    SerieBCB(4505, "Dívida líquida do governo federal (% PIB)", "Fiscal", "Mensal"),
    SerieBCB(4536, "Necessidade de financiamento - Setor público (% PIB)", "Fiscal", "Mensal"),
    SerieBCB(4537, "Resultado primário - Setor público (% PIB)", "Fiscal", "Mensal"),
    SerieBCB(4538, "Juros nominais - Setor público (% PIB)", "Fiscal", "Mensal"),
    SerieBCB(4539, "Resultado nominal - Setor público (% PIB)", "Fiscal", "Mensal"),
    SerieBCB(5364, "Receita total do governo central", "Fiscal", "Mensal"),
    SerieBCB(5793, "Despesa total do governo central", "Fiscal", "Mensal"),
    # ==================== SETOR EXTERNO ====================
    SerieBCB(
        3546, "Reservas internacionais - Conceito liquidez - Total", "Setor Externo", "Diária"
    ),
    SerieBCB(
        13621, "Reservas internacionais - Conceito liquidez - Mensal", "Setor Externo", "Mensal"
    ),
    SerieBCB(22707, "Balança comercial - Saldo mensal (US$ milhões)", "Setor Externo", "Mensal"),
    SerieBCB(22708, "Exportação de bens - Mensal (US$ milhões)", "Setor Externo", "Mensal"),
    SerieBCB(22709, "Importação de bens - Mensal (US$ milhões)", "Setor Externo", "Mensal"),
    SerieBCB(
        22714, "Balança comercial - Saldo acum. 12 meses (US$ milhões)", "Setor Externo", "Mensal"
    ),
    SerieBCB(
        22701, "Transações correntes - Saldo mensal (US$ milhões)", "Setor Externo", "Mensal"
    ),
    SerieBCB(
        22704, "Transações correntes - Saldo acum. 12 meses (% PIB)", "Setor Externo", "Mensal"
    ),
    SerieBCB(22715, "Serviços - Saldo mensal (US$ milhões)", "Setor Externo", "Mensal"),
    SerieBCB(22716, "Renda primária - Saldo mensal (US$ milhões)", "Setor Externo", "Mensal"),
    SerieBCB(
        22846, "Investimento direto no país - Mensal (US$ milhões)", "Setor Externo", "Mensal"
    ),
    SerieBCB(22885, "Investimento em carteira - Mensal (US$ milhões)", "Setor Externo", "Mensal"),
    SerieBCB(13690, "Dívida externa total (US$ milhões)", "Setor Externo", "Mensal"),
    # ==================== CRÉDITO ====================
    SerieBCB(20539, "Saldo da carteira de crédito - Total", "Crédito", "Mensal"),
    SerieBCB(20540, "Saldo da carteira de crédito - Pessoas físicas", "Crédito", "Mensal"),
    SerieBCB(20541, "Saldo da carteira de crédito - Pessoas jurídicas", "Crédito", "Mensal"),
    SerieBCB(20542, "Saldo de crédito com recursos livres - Total", "Crédito", "Mensal"),
    SerieBCB(20570, "Saldo de crédito com recursos livres - PF", "Crédito", "Mensal"),
    SerieBCB(20592, "Saldo de crédito com recursos livres - PJ", "Crédito", "Mensal"),
    SerieBCB(20615, "Saldo de crédito com recursos direcionados - Total", "Crédito", "Mensal"),
    SerieBCB(20631, "Concessões de crédito - Total", "Crédito", "Mensal"),
    SerieBCB(20665, "Concessões de crédito - Cheque especial - PF", "Crédito", "Mensal"),
    SerieBCB(20714, "Taxa média de juros - Crédito total", "Crédito", "Mensal"),
    SerieBCB(20716, "Taxa média de juros - Crédito PF", "Crédito", "Mensal"),
    SerieBCB(20740, "Taxa média de juros - Crédito recursos livres - PF", "Crédito", "Mensal"),
    SerieBCB(20749, "Taxa média de juros - Aquisição de veículos - PF", "Crédito", "Mensal"),
    SerieBCB(20772, "Taxa média de juros - Financiamento imobiliário - PF", "Crédito", "Mensal"),
    SerieBCB(
        25497, "Taxa média de juros - Financ. imobiliário taxas mercado", "Crédito", "Mensal"
    ),
    SerieBCB(20783, "Spread médio - Crédito total", "Crédito", "Mensal"),
    SerieBCB(20785, "Spread médio - Crédito PF", "Crédito", "Mensal"),
    SerieBCB(20786, "Spread médio - Crédito PJ", "Crédito", "Mensal"),
    SerieBCB(21082, "Inadimplência - Crédito total", "Crédito", "Mensal"),
    SerieBCB(21084, "Inadimplência - Crédito PF", "Crédito", "Mensal"),
    SerieBCB(21085, "Inadimplência - Crédito PJ", "Crédito", "Mensal"),
    SerieBCB(21128, "Inadimplência - Cartão de crédito parcelado - PF", "Crédito", "Mensal"),
    SerieBCB(21129, "Inadimplência - Cartão de crédito total - PF", "Crédito", "Mensal"),
    SerieBCB(13685, "Inadimplência - Instituições financeiras privadas", "Crédito", "Mensal"),
    # ==================== AGREGADOS MONETÁRIOS ====================
    SerieBCB(1788, "Base monetária - Saldo fim de período", "Agregados Monetários", "Mensal"),
    SerieBCB(
        1833,
        "Base monetária ampliada - M4 - Saldo fim de período",
        "Agregados Monetários",
        "Mensal",
    ),
    SerieBCB(
        27788, "Meios de pagamento - M1 - Saldo fim de período", "Agregados Monetários", "Mensal"
    ),
    SerieBCB(
        27789, "Meios de pagamento - M2 - Saldo fim de período", "Agregados Monetários", "Mensal"
    ),
    SerieBCB(
        27790, "Meios de pagamento - M3 - Saldo fim de período", "Agregados Monetários", "Mensal"
    ),
    SerieBCB(
        27791, "Meios de pagamento - M4 - Saldo fim de período", "Agregados Monetários", "Mensal"
    ),
    SerieBCB(27815, "Multiplicador monetário - Base para M4", "Agregados Monetários", "Mensal"),
    SerieBCB(7530, "Multiplicador monetário - Média do mês", "Agregados Monetários", "Mensal"),
    # ==================== POUPANÇA ====================
    SerieBCB(25, "Poupança - Rendimento no mês de referência", "Poupança", "Mensal"),
    SerieBCB(195, "Poupança - Saldo total", "Poupança", "Mensal"),
    SerieBCB(7165, "Poupança - Captação líquida", "Poupança", "Mensal"),
    SerieBCB(7166, "Poupança - Depósitos", "Poupança", "Mensal"),
    SerieBCB(7167, "Poupança - Retiradas", "Poupança", "Mensal"),
    # ==================== ÍNDICES DE MERCADO ====================
    SerieBCB(12466, "IMA-B - Índice de Mercado ANBIMA (Base)", "Índices de Mercado", "Diária"),
    SerieBCB(
        12467, "IMA-B5 - Índice de Mercado ANBIMA (até 5 anos)", "Índices de Mercado", "Diária"
    ),
    SerieBCB(
        12468, "IMA-B5+ - Índice de Mercado ANBIMA (acima 5 anos)", "Índices de Mercado", "Diária"
    ),
    SerieBCB(7832, "Ibovespa - Índice mensal", "Índices de Mercado", "Mensal"),
    # ==================== EXPECTATIVAS (Focus) ====================
    SerieBCB(29033, "Expectativa IPCA - Mediana - Ano corrente", "Expectativas", "Semanal"),
    SerieBCB(29034, "Expectativa IPCA - Mediana - Próximo ano", "Expectativas", "Semanal"),
    SerieBCB(29035, "Expectativa Selic - Mediana - Ano corrente", "Expectativas", "Semanal"),
    SerieBCB(29036, "Expectativa Selic - Mediana - Próximo ano", "Expectativas", "Semanal"),
    SerieBCB(29037, "Expectativa PIB - Mediana - Ano corrente", "Expectativas", "Semanal"),
    SerieBCB(29038, "Expectativa PIB - Mediana - Próximo ano", "Expectativas", "Semanal"),
    SerieBCB(29039, "Expectativa Câmbio - Mediana - Ano corrente", "Expectativas", "Semanal"),
    SerieBCB(29040, "Expectativa Câmbio - Mediana - Próximo ano", "Expectativas", "Semanal"),
]

# Index by code for O(1) lookup
_SERIES_POR_CODIGO: dict[int, SerieBCB] = {s.codigo: s for s in SERIES_POPULARES}


def buscar_serie_por_codigo(codigo: int) -> SerieBCB | None:
    """Find a series by its SGS code."""
    return _SERIES_POR_CODIGO.get(codigo)


def _normalize(text: str) -> str:
    """Normalize text for accent-insensitive search (NFD + lowercase)."""
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def buscar_series_por_termo(termo: str) -> list[SerieBCB]:
    """Search catalog by term (accent-insensitive, matches name or category)."""
    t = _normalize(termo)
    return [s for s in SERIES_POPULARES if t in _normalize(s.nome) or t in _normalize(s.categoria)]


def listar_por_categoria(categoria: str | None = None) -> dict[str, list[SerieBCB]]:
    """Group series by category. Optionally filter by category name."""
    result: dict[str, list[SerieBCB]] = {}
    for s in SERIES_POPULARES:
        if categoria and _normalize(categoria) not in _normalize(s.categoria):
            continue
        result.setdefault(s.categoria, []).append(s)
    return result
