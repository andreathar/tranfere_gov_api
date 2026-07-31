#!/usr/bin/env python3
"""
Extrator Genérico de Propostas — Discricionárias Transferegov.

Baixa qualquer tipo de proposta/convênio/instrumento do sistema
https://discricionarias.transferegov.sistema.gov.br/voluntarias/

Usa o acesso público (guest) — NÃO requer login Gov.br.

Uso:
  # Listar ajuda
  python3 -m src.extrator_discricionarias --help

  # Detalhar proposta específica
  python3 -m src.extrator_discricionarias detalhar --id-proposta 2035559 --id-convenio 1163065

  # Detalhar + exportar JSON
  python3 -m src.extrator_discricionarias detalhar --id-proposta 2035559 --id-convenio 1163065 --json

  # Detalhar + exportar CSV + DB
  python3 -m src.extrator_discricionarias detalhar --id-proposta 2035559 --id-convenio 1163065 --csv --db

  # Buscar propostas por UF
  python3 -m src.extrator_discricionarias buscar --uf SP

  # Buscar propostas por modalidade
  python3 -m src.extrator_discricionarias buscar --modalidade Convenio

  # Buscar por ano + situação
  python3 -m src.extrator_discricionarias buscar --ano 2024 --situacao "Em execução"

  # Buscar por emenda parlamentar
  python3 -m src.extrator_discricionarias buscar --emenda 11228

  # Buscar por CNPJ do proponente
  python3 -m src.extrator_discricionarias buscar --cnpj 11.337.750/0001-70

  # Listar propostas encontrados e detalhar cada um
  python3 -m src.extrator_discricionarias buscar --uf SP --detalhar

  # Exportar dados de busca para CSV/JSON
  python3 -m src.extrator_discricionarias buscar --ano 2025 --csv --json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from config.settings import (
    OUTPUT_CSV,
    OUTPUT_JSON,
    OUTPUT_XLSX,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("extrator_discricionarias")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
BASE_URL = "https://discricionarias.transferegov.sistema.gov.br/voluntarias"

# Parâmetros de acesso guest (público)
GUEST_PARAMS = {"Usr": "guest", "Pwd": "guest"}

# Timeouts
TIMEOUT = 60
SLEEP = 1.0  # cortesia entre requisições

# Modalidades disponíveis no sistema
MODALIDADES = [
    "Termo de Cooperação",
    "Contrato de Repasse",
    "Convênio",
    "Termo de Parceria",
    "Termo de Fomento",
    "Termo de Colaboração",
    "Termo de Compromisso",
]

# Situações disponíveis no sistema
SITUACOES_PROPOSTA = [
    "Proposta/Plano de Trabalho em rascunho",
    "Proposta/Plano de Trabalho Recebidos com pendência",
    "Proposta/Plano de Trabalho Cadastrados",
    "Proposta/Plano de Trabalho enviado para Análise",
    "Proposta/Plano de Trabalho em Análise",
    "Proposta/Plano de Trabalho em Complementação",
    "Proposta/Plano de Trabalho complementado enviada para Análise",
    "Proposta/Plano de Trabalho complementado em Análise",
    "Proposta Aprovada e Plano de Trabalho enviado para Análise",
    "Proposta Aprovada e Plano de Trabalho em Análise",
    "Proposta Aprovada e Plano de Trabalho em Complementação",
    "Proposta Aprovada e Plano de Trabalho Complementado enviado para Análise",
    "Proposta Aprovada e Plano de Trabalho Complementado em Análise",
    "Proposta/Plano de Trabalho Aprovados",
    "Proposta/Plano de Trabalho Cancelados",
    "Proposta/Plano de Trabalho Rejeitados",
    "Assinado",
    "Em execução",
    "Aguardando Prestação de Contas",
    "Prestação de Contas enviada para Análise",
    "Prestação de Contas em Complementação",
    "Prestação de Contas Aprovada",
    "Prestação de Contas Rejeitada",
    "Prestação de Contas Aprovada com Ressalvas",
    "Prestação de Contas Atrasada",
    "Prestação de Contas em Análise",
    "Instrumento Anulado",
    "Instrumento Rescindido",
    "Instrumento Extinto",
    "INADIMPLENTE",
    "Assinatura Pendente Registro TV Siafi",
    "Proposta/Plano de Trabalho Rejeitados por Impedimento técnico",
    "Proposta Aprovada/Contratação Prejudicada",
    "Enviada para Análise Preliminar",
    "Classificada em Análise Preliminar",
    "Eliminada em Análise Preliminar",
    "Eliminada em Análise Definitiva",
    "Classificada em Análise Definitiva",
    "Proposta Aprovada/Aguardando Plano de Trabalho",
    "Proposta Eliminada em Chamamento Público",
    "Prestação de Contas Comprovada - Em Análise",
    "Prestação de Contas Concluída",
    "Prestação de Contas Iniciada por Antecipação",
]


# ---------------------------------------------------------------------------
# Modelo de dados
# ---------------------------------------------------------------------------
@dataclass
class PropostaDiscricionaria:
    """Representa uma proposta/convênio do sistema Transferegov Discricionárias."""

    # Identificação
    id_proposta: str = ""
    id_convenio: str = ""
    codigo_instrumento: str = ""
    numero_proposta: str = ""
    numero_interno_orgao: str = ""
    numero_processo: str = ""

    # Classificação
    modalidade: str = ""
    subtipo_instrumento: str = ""
    situacao_contratacao: str = ""
    situacao: str = ""
    situacao_siafi: str = ""
    regime_simplificado: str = ""

    # Partes
    orgao_codigo: str = ""
    orgao_nome: str = ""
    proponente_cnpj: str = ""
    proponente_nome: str = ""
    fundamento_legal: str = ""

    # Datas
    data_proposta: str = ""
    data_assinatura: str = ""
    data_publicacao_dou: str = ""
    data_inicio_vigencia: str = ""
    data_termino_vigencia: str = ""
    data_limite_prestacao_contas: str = ""

    # Valores
    valor_global: float = 0.0
    valor_repasse: float = 0.0
    valor_contrapartida: float = 0.0
    valor_contrapartida_financeira: float = 0.0
    valor_contrapartida_bens: float = 0.0
    valor_rendimentos_aplicacao: float = 0.0

    # Dados bancários
    banco: str = ""
    agencia: str = ""
    conta: str = ""
    situacao_conta: str = ""

    # Descrição
    objeto: str = ""
    justificativa: str = ""
    publico_alvo: str = ""
    problema_resolver: str = ""
    resultados_esperados: str = ""
    relacao_programa: str = ""
    categorias: str = ""
    caracterizacao_interesses: str = ""
    capacidade_tecnica: str = ""

    # Documentos
    documentos: list[dict[str, str]] = field(default_factory=list)

    # Cronograma de repasses
    cronograma_repasse: list[dict[str, Any]] = field(default_factory=list)

    # OBTV
    opera_obtv: str = ""
    permite_obtv_convenente: str = ""

    # Metadados
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    fonte: str = "discricionarias.transferegov.sistema.gov.br"


# ---------------------------------------------------------------------------
# Parsers HTML
# ---------------------------------------------------------------------------
def _parse_valor(texto: str) -> float:
    """Converte 'R$ 579.315,00' → 579315.00"""
    if not texto:
        return 0.0
    texto = texto.strip()
    texto = texto.replace("R$", "").replace(" ", "")
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def _limpar_texto(texto: str) -> str:
    """Remove espaços extras, quebras de linha e tabs (reais e literais)."""
    if not texto:
        return ""
    # Remove escapes literais comuns em HTML mal formatado
    texto = texto.replace("\\n", " ").replace("\\t", " ").replace("\\r", " ")
    # Remove quebras de linha reais, tabs, espaços múltiplos
    texto = " ".join(texto.split()).strip()
    return texto


def _limpar_campo(valor: str) -> str:
    """
    Limpa um campo extraído, removendo sub-rótulos de tabelas aninhadas.

    Algumas células do HTML têm sub-tabelas que adicionam texto extra
    (ex: "Situação no SIAFI Enviado para o SIAFI - X"). Este helper
    mantém apenas o texto relevante antes desses sub-rótulos.
    """
    valor = _limpar_texto(valor)
    # Remover sub-rótulos conhecidos de tabelas aninhadas
    for sub in [
        "Situação no SIAFI",
        "Situação",
        "Empenhado",
        "sim",
        "não",
        "Publicação",
        "Publicado",
        "Conta",
        "Enviado para o SIAFI",
    ]:
        idx = valor.find(sub)
        if idx > 3:  # Só cortar se o sub-rótulo não estiver no início
            valor = valor[:idx].strip()
    return _limpar_texto(valor)


# ---------------------------------------------------------------------------
# Cliente — obtém HTML via Playwright e parseia com BeautifulSoup
# ---------------------------------------------------------------------------
# O sistema Discricionárias usa SAML/SSO e bloqueia requests programáticos
# (Python requests, httpx, curl). Apenas navegadores reais funcionam.
# Usamos Playwright headless para obter o HTML e BeautifulSoup para parsear.


class DiscricionariasClient:
    """
    Cliente para o sistema Discricionárias Transferegov.

    Abre navegador headless via Playwright, navega até a página com
    credenciais guest e parseia o HTML com BeautifulSoup.
    """

    def __init__(self, timeout: int = TIMEOUT):
        self.timeout = timeout
        self._base_url = BASE_URL

    # ------------------------------------------------------------------
    # Métodos de consulta
    # ------------------------------------------------------------------

    @staticmethod
    def detalhar_proposta_de_html(
        html: str, id_proposta: str, id_convenio: str = ""
    ) -> PropostaDiscricionaria:
        """
        Parseia HTML de detalhamento de proposta (obtido via navegador).

        Args:
            html: HTML completo da página de detalhamento
            id_proposta: ID da proposta
            id_convenio: ID do convênio

        Returns:
            PropostaDiscricionaria estruturada
        """
        return _parse_detalhes_proposta(html, id_proposta, id_convenio)

    @staticmethod
    def abrir_proposta(id_proposta: str, id_convenio: str = "", headless: bool = True) -> str:
        """
        Abre a página de detalhamento da proposta no navegador via Playwright.

        ATENÇÃO: O servidor Discricionárias bloqueia requests headless (SAML/SSO).
        Use headless=False se estiver em ambiente com display gráfico.

        Args:
            id_proposta: ID da proposta (ex: 2035559)
            id_convenio: ID do convênio (ex: 1163065)
            headless: Se True, tenta modo headless (provavelmente falha)

        Returns:
            HTML completo da página de detalhamento

        Raises:
            RuntimeError: Se o servidor redirecionar para SAML (bot detectado)
        """
        from playwright.sync_api import sync_playwright

        if headless:
            logger.warning(
                "Playwright headless provavelmente será bloqueado pelo servidor. "
                "Use headless=False se tiver display gráfico."
            )

        url = (
            f"{BASE_URL}/ConsultarProposta/"
            f"ResultadoDaConsultaDePropostaDetalharProposta.do"
            f"?idProposta={id_proposta}"
        )
        if id_convenio:
            url += f"&idConvenio={id_convenio}"
        url += "&Usr=guest&Pwd=guest"

        logger.info("Abrindo proposta %s no Playwright...", id_proposta)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
                ),
                locale="pt-BR",
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            html = page.content()
            browser.close()

        # Detectar redirecionamento SAML
        if "idp.transferegov" in html or "SAML" in html or "single_sign_on" in html:
            raise RuntimeError(
                "REDIRECIONADO PARA SAML — O servidor Discricionárias bloqueia "
                "requests automatizados.\n\n"
                "Para obter o HTML manualmente:\n"
                "  1. Abra o navegador VISÍVEL em:\n"
                f"     {url}\n"
                "  2. O login guest deve ser automático.\n"
                "  3. Salve a página (Ctrl+S) em um arquivo HTML.\n"
                "  4. Use: python3 -m src.extrator_discricionarias \\\n"
                f"         detalhar --id-proposta {id_proposta} "
                f"--id-convenio {id_convenio} --arquivo-html /caminho/para/proposta.html\n\n"
                "Ou use o VS Code Copilot para extrair automaticamente:\n"
                "  - Peça para o Copilot abrir o browser e extrair os dados."
            )

        logger.info("HTML obtido (%d chars)", len(html))
        return html

    def detalhar_proposta(
        self, id_proposta: str, id_convenio: str = "", headless: bool = True
    ) -> PropostaDiscricionaria:
        """Abre a proposta no Playwright, parseia e retorna."""
        html = self.abrir_proposta(id_proposta, id_convenio, headless=headless)
        return self.detalhar_proposta_de_html(html, id_proposta, id_convenio)


# ---------------------------------------------------------------------------
# Funções de parsing (standalone)
# ---------------------------------------------------------------------------


def _parse_resultados_busca(html: str) -> list[dict[str, str]]:
    """
    Parseia a página de resultados da busca.

    Extrai a tabela de resultados com links para detalhamento.
    """
    soup = BeautifulSoup(html, "html.parser")
    resultados: list[dict[str, str]] = []

    if "Nenhum registro foi encontrado" in html:
        logger.info("Nenhum resultado encontrado.")
        return resultados

    tabelas = soup.find_all("table")
    for tabela in tabelas:
        linhas = tabela.find_all("tr")
        if len(linhas) < 2:
            continue

        links_detalhar = tabela.find_all("a", href=re.compile(r"DetalharProposta"))
        if not links_detalhar:
            continue

        cabecalhos = [th.get_text(" ", strip=True) for th in linhas[0].find_all(["th", "td"])]

        for linha in linhas[1:]:
            cells = linha.find_all("td")
            if not cells:
                continue

            resultado: dict[str, str] = {}
            for i, cell in enumerate(cells):
                chave = cabecalhos[i] if i < len(cabecalhos) else f"col_{i}"
                resultado[chave] = _limpar_texto(cell.get_text(" ", strip=True))

            links = linha.find_all("a")
            for link in links:
                href_raw = link.get("href", "")
                href = str(href_raw) if href_raw is not None else ""
                if "DetalharProposta" in href or "detalhar" in href.lower():
                    resultado["link_detalhar"] = href
                elif "SelecionarObjeto" in href:
                    resultado["link_selecionar"] = href

            resultados.append(resultado)

    logger.info("Encontrados %d resultados.", len(resultados))
    return resultados


# ---------------------------------------------------------------------------
# Função de parsing (standalone, usada por DiscricionariasClient)
# ---------------------------------------------------------------------------


def _parse_detalhes_proposta(
    html: str, id_proposta: str, id_convenio: str
) -> PropostaDiscricionaria:
    """Parseia a página de detalhamento da proposta usando key-value extraction."""
    soup = BeautifulSoup(html, "html.parser")
    proposta = PropostaDiscricionaria(
        id_proposta=id_proposta,
        id_convenio=id_convenio,
    )

    # Extrair título: "36000 - MINISTERIO DA SAUDE"
    titulo_elem = soup.find(string=re.compile(r"\d{5}\s*-\s*"))
    if titulo_elem:
        match = re.search(r"(\d{5})\s*-\s*(.+)", titulo_elem.strip())
        if match:
            proposta.orgao_codigo = match.group(1)
            proposta.orgao_nome = _limpar_texto(match.group(2))

    # Extrair "Instrumento 971413"
    inst_elem = soup.find(string=re.compile(r"Instrumento\s+\d+"))
    if inst_elem:
        match = re.search(r"Instrumento\s+(\d+)", inst_elem)
        if match:
            proposta.codigo_instrumento = match.group(1)

        # Mapeamento de rótulos → atributos da proposta
        # Formato: (rótulo_na_tabela, nome_do_atributo, é_texto_longo?)
        MAPA_CAMPOS: list[tuple[str, str, bool]] = [
            ("Modalidade", "modalidade", False),
            ("Subtipo do Instrumento", "subtipo_instrumento", False),
            ("Situação de Contratação Atual", "situacao_contratacao", False),
            ("Regime Simplificado", "regime_simplificado", False),
            ("Código do Instrumento", "codigo_instrumento", False),
            ("Número Interno do Órgão", "numero_interno_orgao", False),
            ("Número do Processo", "numero_processo", False),
            ("Fundamento Legal", "fundamento_legal", False),
            ("Órgão", "orgao_nome", False),
            ("Objeto do Instrumento", "objeto", True),
            ("Justificativa", "justificativa", True),
            ("Caracterização dos interesses recíprocos", "caracterizacao_interesses", True),
            ("Público alvo", "publico_alvo", True),
            ("Problema a ser resolvido", "problema_resolver", True),
            ("Resultados esperados", "resultados_esperados", True),
            ("Relação entre a proposta e os objetivos", "relacao_programa", True),
            ("Categorias", "categorias", False),
            ("Capacidade Técnica e Gerencial", "capacidade_tecnica", True),
            ("Data da Proposta", "data_proposta", False),
            ("Data Assinatura", "data_assinatura", False),
            ("publicado no DOU em", "data_publicacao_dou", False),
            ("Data Início de Vigência", "data_inicio_vigencia", False),
            ("Data Término de Vigência Atual", "data_termino_vigencia", False),
            ("Data Limite p/ Prestação de Contas", "data_limite_prestacao_contas", False),
            ("Opera por OBTV", "opera_obtv", False),
            ("Banco", "banco", False),
        ]

        # Iterar por todas as linhas de todas as tabelas
        for linha in soup.find_all("tr"):
            cells = linha.find_all("td")
            if len(cells) < 2:
                continue

            texto_label = _limpar_texto(cells[0].get_text(" ", strip=True))
            if not texto_label:
                continue

            # --- Mapeamento direto label → atributo ---
            for rotulo, attr, is_longo in MAPA_CAMPOS:
                if texto_label.startswith(rotulo) or texto_label == rotulo:
                    raw_valor = cells[1].get_text(" ", strip=True)
                    valor = _limpar_texto(raw_valor) if is_longo else _limpar_campo(raw_valor)
                    # Tratamentos especiais
                    if rotulo == "Órgão" and not valor:
                        continue
                    if rotulo == "Código do Instrumento":
                        proposta.codigo_instrumento = valor
                    elif rotulo == "Banco":
                        proposta.banco = valor
                    else:
                        setattr(proposta, attr, valor)
                    break

            # --- Código do Órgão (separar "36000 - NOME" em código + nome) ---
            if rotulo == "Órgão" and proposta.orgao_nome:
                match = re.match(r"^(\d+)\s*[-–]\s*(.+)", proposta.orgao_nome)
                if match:
                    proposta.orgao_codigo = match.group(1)
                    proposta.orgao_nome = match.group(2).strip()

            # --- Número da Proposta (está na mesma linha de Código do Instrumento) ---
            if "Número da Proposta" in texto_label:
                proposta.numero_proposta = _limpar_campo(cells[1].get_text(" ", strip=True))

            # --- Situação da Proposta (primeira ocorrência) ---
            if texto_label == "Situação" and not proposta.situacao:
                raw = cells[1].get_text(" ", strip=True)
                # Se tiver "Conta" ou "Regularizada", é a situação da conta, não da proposta
                if "Conta" not in raw and "Regularizada" not in raw:
                    proposta.situacao = _limpar_campo(raw)

            # --- Proponente (CNPJ + Nome) ---
            if "Proponente" in texto_label:
                valor_prop = _limpar_texto(cells[1].get_text(" ", strip=True))
                if "CNPJ" in valor_prop:
                    match = re.search(r"CNPJ\s+([\d\.\-/]+)\s*-\s*(.+)", valor_prop)
                    if match:
                        proposta.proponente_cnpj = _limpar_texto(match.group(1))
                        proposta.proponente_nome = _limpar_texto(match.group(2))

            # --- Agência / Conta (estão em linhas consecutivas com labels específicos) ---
            if texto_label == "Agência":
                proposta.agencia = _limpar_campo(cells[1].get_text(" ", strip=True))
                # Conta pode estar na mesma linha ou na próxima célula
                if len(cells) >= 4:
                    label_conta = _limpar_texto(cells[2].get_text(" ", strip=True))
                    if "Conta" in label_conta:
                        proposta.conta = _limpar_campo(cells[3].get_text(" ", strip=True))

            # --- Situação da Conta (vem depois de Agência) ---
            if (
                texto_label == "Situação"
                and not proposta.situacao_conta
                and ("Conta" in cells[1].get_text() or "Regularizada" in cells[1].get_text())
            ):
                proposta.situacao_conta = _limpar_campo(cells[1].get_text(" ", strip=True))

        # --- Valores (linha complexa com divs aninhadas dentro de um único <td>) ---
        # Estrutura: <tr><td colspan=5>
        #   <b>R$ 579.315,00</b> Valor Global
        #   <div><b>R$ 550.000,00</b> Valor de Repasse</div>
        #   <div><b>R$ 29.315,00</b> Valor da Contrapartida</div>
        #   <div><b>R$ 29.315,00</b> Valor Contrapartida Financeira</div>
        #   <div><b>R$ 0,00</b> Valor Contrapartida Bens e Serviços</div>
        #   <div><b>R$ 0,00</b> Valor de Rendimentos de Aplicação</div>
        for linha in soup.find_all("tr"):
            texto_linha = _limpar_texto(linha.get_text())
            if "Valor Global" in texto_linha and "R$" in texto_linha:
                # Extrair cada div individualmente
                for div in linha.find_all("div"):
                    div_texto = _limpar_texto(div.get_text())
                    match = re.search(r"R\$\s*[\d\.,]+", div_texto)
                    if not match:
                        continue
                    valor = _parse_valor(match.group())
                    if "Valor de Repasse" in div_texto:
                        proposta.valor_repasse = valor
                    elif (
                        "Valor da Contrapartida" in div_texto
                        and "Financeira" not in div_texto
                        and "Bens" not in div_texto
                    ):
                        proposta.valor_contrapartida = valor
                    elif "Contrapartida Financeira" in div_texto:
                        proposta.valor_contrapartida_financeira = valor
                    elif (
                        "Contrapartida Bens" in div_texto
                        or "Contrapartida Bens e Serviços" in div_texto
                    ):
                        proposta.valor_contrapartida_bens = valor
                    elif "Rendimentos de Aplicação" in div_texto:
                        proposta.valor_rendimentos_aplicacao = valor

                # Valor Global está no <b> direto (fora das divs)
                b_direto = linha.find("b")
                if b_direto and b_direto.parent and b_direto.parent.name == "td":
                    b_texto = _limpar_texto(b_direto.get_text())
                    match = re.search(r"R\$\s*[\d\.,]+", b_texto)
                    if match:
                        proposta.valor_global = _parse_valor(match.group())

                # Se não encontrou o global no <b> direto, usar o primeiro R$ da linha
                if proposta.valor_global == 0.0:
                    match = re.search(r"R\$\s*[\d\.,]+", texto_linha)
                    if match:
                        proposta.valor_global = _parse_valor(match.group())
                break

        # --- Documentos ---
        for linha in soup.find_all("tr"):
            cells = linha.find_all("td")
            for cell in cells:
                # Procurar link de download de anexo
                link = cell.find("a", href=re.compile(r"DetalharPropostaDownloadAnexo"))
                if link and len(cells) >= 3:
                    nome = _limpar_texto(cells[0].get_text(" ", strip=True))
                    data_upload = _limpar_texto(str(cells[1].get_text(" ", strip=True)))
                    href_raw = link.get("href", "")
                    href = str(href_raw) if href_raw is not None else ""
                    proposta.documentos.append(
                        {
                            "nome": nome,
                            "data_upload": data_upload,
                            "url_download": href,
                        }
                    )

        # --- Cronograma de repasses ---
        crono_header = soup.find(string="Cronograma orçamentário do valor do repasse")
        if crono_header:
            # Procurar a tabela após o header
            current = crono_header.find_next("table")
            if current:
                for linha_crono in current.find_all("tr"):
                    cells = linha_crono.find_all("td")
                    if len(cells) >= 2:
                        ano = _limpar_texto(cells[0].get_text(" ", strip=True))
                        valor_texto = cells[1].get_text(" ", strip=True)
                        if ano and ano.isdigit():
                            proposta.cronograma_repasse.append(
                                {
                                    "ano": ano,
                                    "valor": _parse_valor(valor_texto),
                                }
                            )

        logger.info(
            "Proposta %s | %s | %s (%s) | R$ %.2f | %s",
            proposta.numero_proposta or id_proposta,
            proposta.modalidade or "?",
            proposta.orgao_nome or "?",
            proposta.orgao_codigo or "?",
            proposta.valor_global,
            proposta.situacao or "?",
        )

        return proposta


# ---------------------------------------------------------------------------
# Exportação
# ---------------------------------------------------------------------------
def proposta_para_dict(proposta: PropostaDiscricionaria) -> dict[str, Any]:
    """Converte proposta para dict plano (para JSON/CSV)."""
    d = asdict(proposta)
    # Remover campos complexos
    d["documentos"] = json.dumps(d["documentos"], ensure_ascii=False)
    d["cronograma_repasse"] = json.dumps(d["cronograma_repasse"], ensure_ascii=False)
    return d


def exportar_para_csv(propostas: list[PropostaDiscricionaria], nome_arquivo: str = "") -> str:
    """Exporta lista de propostas para CSV."""
    if not nome_arquivo:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = str(OUTPUT_CSV / f"discricionarias_{timestamp}.csv")

    dados = [proposta_para_dict(p) for p in propostas]
    df = pd.DataFrame(dados)
    df.to_csv(nome_arquivo, index=False, encoding="utf-8-sig")
    logger.info("CSV exportado: %s (%d linhas)", nome_arquivo, len(df))
    return nome_arquivo


def exportar_para_json(propostas: list[PropostaDiscricionaria], nome_arquivo: str = "") -> str:
    """Exporta lista de propostas para JSON."""
    if not nome_arquivo:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = str(OUTPUT_JSON / f"discricionarias_{timestamp}.json")

    dados = [proposta_para_dict(p) for p in propostas]
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, default=str)
    logger.info("JSON exportado: %s (%d registros)", nome_arquivo, len(dados))
    return nome_arquivo


def exportar_para_xlsx(propostas: list[PropostaDiscricionaria], nome_arquivo: str = "") -> str:
    """Exporta lista de propostas para Excel."""
    if not nome_arquivo:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = str(OUTPUT_XLSX / f"discricionarias_{timestamp}.xlsx")

    dados = [proposta_para_dict(p) for p in propostas]
    df = pd.DataFrame(dados)
    df.to_excel(nome_arquivo, index=False, engine="openpyxl")
    logger.info("Excel exportado: %s (%d linhas)", nome_arquivo, len(df))
    return nome_arquivo


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrator Genérico de Propostas — Discricionárias Transferegov",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Detalhar proposta específica
  %(prog)s detalhar --id-proposta 2035559 --id-convenio 1163065

  # Detalhar + exportar JSON
  %(prog)s detalhar --id-proposta 2035559 --id-convenio 1163065 --json

  # Buscar propostas por UF
  %(prog)s buscar --uf SP

  # Buscar por modalidade + situação
  %(prog)s buscar --modalidade Convênio --situacao "Em execução"

  # Buscar por emenda parlamentar
  %(prog)s buscar --emenda 11228

  # Detalhar todos os resultados de uma busca
  %(prog)s buscar --uf SP --detalhar --csv
        """,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Log detalhado")

    subparsers = parser.add_subparsers(dest="comando", help="Comando")

    # --- Comando: detalhar ---
    det_parser = subparsers.add_parser("detalhar", help="Detalhar proposta específica")
    det_parser.add_argument("--id-proposta", required=True, help="ID da proposta")
    det_parser.add_argument("--id-convenio", default="", help="ID do convênio/instrumento")
    det_parser.add_argument(
        "--arquivo-html", default="", help="Arquivo HTML salvo manualmente (dispensa Playwright)"
    )
    det_parser.add_argument("--json", action="store_true", help="Exportar JSON")
    det_parser.add_argument("--csv", action="store_true", help="Exportar CSV")
    det_parser.add_argument("--xlsx", action="store_true", help="Exportar Excel")
    det_parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Forçar modo headless (provavelmente falha)",
    )
    det_parser.add_argument("--todas-abas", action="store_true", help="Extrair todas as abas")

    # --- Comando: buscar ---
    bus_parser = subparsers.add_parser("buscar", help="Buscar propostas")
    bus_parser.add_argument("--uf", help="UF do proponente")
    bus_parser.add_argument("--municipio", help="Município do proponente")
    bus_parser.add_argument("--modalidade", choices=MODALIDADES, help="Modalidade")
    bus_parser.add_argument("--situacao", help="Situação da proposta")
    bus_parser.add_argument("--ano", help="Ano")
    bus_parser.add_argument("--programa", help="Código do programa")
    bus_parser.add_argument("--parlamentar", help="Código do parlamentar")
    bus_parser.add_argument("--emenda", help="Número da emenda parlamentar")
    bus_parser.add_argument("--orgao", help="Órgão da proposta")
    bus_parser.add_argument("--cnpj", help="CNPJ do proponente")
    bus_parser.add_argument("--proponente", help="Nome do proponente")
    bus_parser.add_argument("--numero-proposta", help="Número da proposta")
    bus_parser.add_argument("--detalhar", action="store_true", help="Detalhar cada resultado")
    bus_parser.add_argument("--json", action="store_true", help="Exportar JSON")
    bus_parser.add_argument("--csv", action="store_true", help="Exportar CSV")
    bus_parser.add_argument("--xlsx", action="store_true", help="Exportar Excel")
    bus_parser.add_argument(
        "--limite", type=int, default=0, help="Limite de propostas para detalhar"
    )

    args = parser.parse_args()

    # Logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not args.comando:
        parser.print_help()
        sys.exit(1)

    cliente = DiscricionariasClient()

    if args.comando == "detalhar":
        _cmd_detalhar(cliente, args)

    elif args.comando == "buscar":
        _cmd_buscar(cliente, args)


def _cmd_detalhar(cliente: DiscricionariasClient, args: argparse.Namespace) -> None:
    """Executa comando 'detalhar'."""
    logger.info(
        "=== Detalhando proposta %s (convênio %s) ===",
        args.id_proposta,
        args.id_convenio or "sem convênio",
    )

    if args.arquivo_html:
        logger.info("Carregando HTML de: %s", args.arquivo_html)
        with open(args.arquivo_html, encoding="utf-8") as f:
            html = f.read()
        proposta = cliente.detalhar_proposta_de_html(html, args.id_proposta, args.id_convenio)
    else:
        proposta = cliente.detalhar_proposta(
            args.id_proposta, args.id_convenio, headless=not args.headless
        )

    # Exibir resumo
    print(f"\n{'=' * 60}")
    print(f"PROPOSTA: {proposta.numero_proposta or proposta.id_proposta}")
    print(f"{'=' * 60}")
    print(f"Modalidade:    {proposta.modalidade}")
    print(f"Órgão:         {proposta.orgao_codigo} - {proposta.orgao_nome}")
    print(f"Proponente:    {proposta.proponente_nome} ({proposta.proponente_cnpj})")
    print(f"Situação:      {proposta.situacao}")
    if proposta.objeto:
        print(
            f"Objeto:        {proposta.objeto[:100]}..."
            if len(proposta.objeto) > 100
            else f"Objeto:        {proposta.objeto}"
        )
    print(f"Valor Global:  R$ {proposta.valor_global:,.2f}")
    print(f"Valor Repasse: R$ {proposta.valor_repasse:,.2f}")
    print(f"Processo:      {proposta.numero_processo}")
    print(f"Vigência:      {proposta.data_inicio_vigencia} → {proposta.data_termino_vigencia}")
    print(f"Documentos:    {len(proposta.documentos)} arquivo(s)")
    if proposta.cronograma_repasse:
        print(f"Cronograma:    {len(proposta.cronograma_repasse)} ano(s)")
    print()

    # Exportações
    if args.json:
        exportar_para_json([proposta])
    if args.csv:
        exportar_para_csv([proposta])
    if args.xlsx:
        exportar_para_xlsx([proposta])


def _cmd_buscar(cliente: DiscricionariasClient, args: argparse.Namespace) -> None:
    """
    Executa comando 'buscar'.

    NOTA: A busca por formulário ainda não foi implementada com Playwright.
    O sistema exige preenchimento de formulários JSF/Struts que requerem
    navegação interativa. Use o comando 'detalhar' com IDs conhecidos.

    Para descobrir IDs, use o navegador manualmente:
      1. Acesse https://discricionarias.transferegov.sistema.gov.br/voluntarias/
      2. Faça a busca desejada no formulário
      3. Copie os IDs das propostas dos resultados
      4. Use: python3 -m src.extrator_discricionarias detalhar --id-proposta X --id-convenio Y
    """
    logger.warning("Comando 'buscar' não implementado com Playwright.")
    print("\n" + "=" * 60)
    print("BUSCA NÃO IMPLEMENTADA")
    print("=" * 60)
    print()
    print("O sistema Discricionárias exige preenchimento de formulários")
    print("JSF/Struts para busca. A automação via Playwright ainda não")
    print("foi implementada para este fluxo.")
    print()
    print("Use o comando 'detalhar' com IDs conhecidos:")
    print("  python3 -m src.extrator_discricionarias detalhar --id-proposta 2035559")
    print()
    print("Para descobrir IDs, use o navegador manualmente em:")
    print("  https://discricionarias.transferegov.sistema.gov.br/voluntarias/")
    print()


def _exportar_resultados_busca(resultados: list[dict[str, str]], formato: str) -> None:
    """Exporta resultados da busca."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if formato == "json":
        path = OUTPUT_JSON / f"discricionarias_busca_{timestamp}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        logger.info("JSON exportado: %s", path)

    elif formato == "csv":
        path = OUTPUT_CSV / f"discricionarias_busca_{timestamp}.csv"
        df = pd.DataFrame(resultados)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        logger.info("CSV exportado: %s", path)


if __name__ == "__main__":
    main()
