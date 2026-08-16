"""HTTP client for the Portal da Transparência API.

Ported and expanded from mcp-dadosbr/lib/tools/government.ts
(executeTransparencia + executeCeisCnep).

All functions return typed Pydantic models. No LLM formatting here (ADR-001).
Auth is injected via the ``chave-api-dados`` header using ``http_get()``.

Endpoints:
    - /contratos/cpf-cnpj             → buscar_contratos
    - /despesas/recursos-recebidos     → consultar_despesas
    - /servidores                      → buscar_servidores
    - /licitacoes                      → buscar_licitacoes
    - /novo-bolsa-familia-por-municipio → consultar_bolsa_familia_municipio
    - /novo-bolsa-familia-sacado-por-nis → consultar_bolsa_familia_nis
    - /ceis, /cnep, /cepim, /ceaf      → buscar_sancoes
    - /emendas                         → buscar_emendas
    - /viagens-por-cpf                 → consultar_viagens
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from mcp_brasil._shared.formatting import parse_brl_number
from mcp_brasil._shared.http_client import http_get
from mcp_brasil._shared.rate_limiter import RateLimiter
from mcp_brasil.exceptions import AuthError

from .constants import (
    ACORDOS_LENIENCIA_URL,
    AUTH_ENV_VAR,
    AUTH_HEADER_NAME,
    BENEFICIOS_CIDADAO_URL,
    BOLSA_FAMILIA_MUNICIPIO_URL,
    BOLSA_FAMILIA_NIS_URL,
    CARTOES_URL,
    CONTRATO_DETALHE_URL,
    CONTRATO_ITENS_URL,
    CONTRATO_NUMERO_URL,
    CONTRATO_TERMOS_URL,
    CONTRATOS_GERAL_URL,
    CONTRATOS_URL,
    CONVENIO_ID_URL,
    CONVENIO_NUMERO_URL,
    CONVENIOS_URL,
    CORONAVIRUS_DESPESAS_URL,
    CORONAVIRUS_TRANSFERENCIAS_URL,
    DESPESAS_DOCUMENTOS_FAVORECIDO_URL,
    DESPESAS_DOCUMENTOS_URL,
    DESPESAS_FUNCIONAL_URL,
    DESPESAS_ITENS_EMPENHO_URL,
    DESPESAS_ORGAO_URL,
    DESPESAS_URL,
    EMENDAS_DOCUMENTOS_URL,
    EMENDAS_URL,
    IMOVEIS_URL,
    LICITACOES_CONTRATOS_URL,
    LICITACOES_EMPENHOS_URL,
    LICITACOES_ITENS_URL,
    LICITACOES_MODALIDADES_URL,
    LICITACOES_PARTICIPANTES_URL,
    LICITACOES_POR_PROCESSO_URL,
    LICITACOES_POR_UG_URL,
    LICITACOES_UGS_URL,
    LICITACOES_URL,
    NOTA_FISCAL_CHAVE_URL,
    NOTAS_FISCAIS_URL,
    ORGAOS_SIAFI_URL,
    ORGAOS_SIAPE_URL,
    PEP_URL,
    PERMISSIONARIOS_URL,
    PESSOAS_FISICAS_URL,
    PESSOAS_JURIDICAS_URL,
    PETI_CODIGO_URL,
    PETI_MUNICIPIO_URL,
    RENUNCIAS_HABILITADAS_URL,
    RENUNCIAS_IMUNES_URL,
    RENUNCIAS_VALOR_URL,
    SAFRA_CODIGO_URL,
    SAFRA_MUNICIPIO_URL,
    SANCOES_DATABASES,
    SEGURO_DEFESO_CODIGO_URL,
    SEGURO_DEFESO_MUNICIPIO_URL,
    SERVIDOR_DETALHE_URL,
    SERVIDORES_FUNCOES_URL,
    SERVIDORES_POR_ORGAO_URL,
    SERVIDORES_REMUNERACAO_URL,
    SERVIDORES_URL,
    VIAGENS_ORGAO_URL,
    VIAGENS_URL,
)
from .schemas import (
    AcordoLeniencia,
    BeneficioSocial,
    BolsaFamiliaMunicipio,
    BolsaFamiliaSacado,
    CartaoPagamento,
    ContratoDetalhe,
    ContratoFornecedor,
    ContratoGeral,
    Convenio,
    ConvenioDetalhe,
    CoronavirusDespesa,
    CoronavirusTransferencia,
    DespesaFuncional,
    DespesaOrgao,
    DocumentoDespesa,
    DocumentoEmenda,
    Emenda,
    EmpresaBeneficioFiscal,
    FuncaoCargo,
    GarantiaSafra,
    ImovelFuncional,
    ItemContratado,
    ItemEmpenho,
    ItemLicitado,
    Licitacao,
    LicitacaoDetalhe,
    NotaFiscal,
    Orgao,
    ParticipanteLicitacao,
    Permissionario,
    PessoaExpostaPoliticamente,
    PessoaFisicaVinculos,
    PessoaJuridicaVinculos,
    PetiBeneficio,
    RecursoRecebido,
    RemuneracaoServidor,
    RenunciaFiscal,
    Sancao,
    SancaoDetalhe,
    SeguroDefeso,
    Servidor,
    ServidorAgregado,
    ServidorDetalhe,
    TermoAditivo,
    UnidadeGestora,
    Viagem,
)

logger = logging.getLogger(__name__)

# 80 req/min — conservative margin below the 90 req/min daytime limit
_rate_limiter = RateLimiter(max_requests=80, period=60.0)


def _get_api_key() -> str:
    """Return the API key or raise AuthError."""
    key = os.environ.get(AUTH_ENV_VAR, "")
    if not key:
        raise AuthError(
            f"Variável de ambiente {AUTH_ENV_VAR} não configurada. "
            "Cadastre-se em portaldatransparencia.gov.br/api-de-dados/cadastrar-email"
        )
    return key


def _auth_headers() -> dict[str, str]:
    """Build auth headers for the API."""
    return {AUTH_HEADER_NAME: _get_api_key()}


def _clean_cpf_cnpj(valor: str) -> str:
    """Remove non-digit characters from CPF/CNPJ."""
    return re.sub(r"\D", "", valor)


async def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    """Make an authenticated GET request to the Portal da Transparência API."""
    from mcp_brasil.exceptions import HttpClientError

    async with _rate_limiter:
        try:
            return await http_get(url, params=params, headers=_auth_headers())
        except HttpClientError as exc:
            msg = str(exc)
            if "403" in msg:
                logger.warning(
                    "Acesso negado (HTTP 403) para %s — verifique permissões da "
                    "chave API (TRANSPARENCIA_API_KEY). Alguns endpoints exigem "
                    "permissões adicionais.",
                    url,
                )
            raise


def _safe_parse_list(
    data: Any,
    parser: Any,
    endpoint: str,
    **parser_kwargs: Any,
) -> list[Any]:
    """Parse a list response, logging a warning if the shape is unexpected."""
    if isinstance(data, list):
        return [parser(item, **parser_kwargs) for item in data]
    logger.warning(
        "Resposta inesperada (esperava list) do endpoint %s: %s",
        endpoint,
        type(data).__name__,
    )
    return []


# --- Parsing helpers --------------------------------------------------------


def _parse_contrato(raw: dict[str, Any]) -> ContratoFornecedor:
    """Parse a raw contract JSON into a ContratoFornecedor model."""
    fornecedor = raw.get("fornecedor") or {}
    orgao = raw.get("unidadeGestora") or raw.get("orgaoVinculado") or {}
    return ContratoFornecedor(
        id=raw.get("id"),
        numero=raw.get("numero"),
        objeto=raw.get("objeto"),
        valor_inicial=raw.get("valorInicial"),
        valor_final=raw.get("valorFinal"),
        data_inicio=raw.get("dataInicioVigencia"),
        data_fim=raw.get("dataFimVigencia"),
        orgao=orgao.get("nome") or orgao.get("descricao"),
        fornecedor=fornecedor.get("nome") or fornecedor.get("razaoSocialReceita"),
    )


def _parse_recurso(raw: dict[str, Any]) -> RecursoRecebido:
    """Parse a raw expense/resource JSON."""
    return RecursoRecebido(
        ano=raw.get("ano"),
        mes=raw.get("mes"),
        valor=raw.get("valor"),
        favorecido_nome=raw.get("nomeFavorecido"),
        orgao_nome=raw.get("nomeOrgao"),
        uf=raw.get("uf"),
    )


def _parse_servidor(raw: dict[str, Any]) -> Servidor:
    """Parse a raw server/public servant JSON."""
    orgao = raw.get("orgaoServidorExercicio") or raw.get("orgaoServidorLotacao") or {}
    return Servidor(
        id=raw.get("id"),
        cpf=raw.get("cpf"),
        nome=raw.get("nome"),
        tipo_servidor=raw.get("tipoServidor"),
        situacao=raw.get("situacao"),
        orgao=orgao.get("nome") or orgao.get("descricao"),
    )


def _parse_licitacao(raw: dict[str, Any]) -> Licitacao:
    """Parse a raw procurement/bid JSON."""
    orgao = raw.get("unidadeGestora") or raw.get("orgao") or {}
    return Licitacao(
        id=raw.get("id"),
        numero=raw.get("numero"),
        objeto=raw.get("objeto"),
        modalidade=raw.get("modalidadeLicitacao") or raw.get("modalidade"),
        situacao=raw.get("situacao"),
        valor_estimado=raw.get("valorEstimado"),
        data_abertura=raw.get("dataAbertura") or raw.get("dataResultadoCompra"),
        orgao=orgao.get("nome") or orgao.get("descricao"),
    )


def _parse_bolsa_municipio(raw: dict[str, Any]) -> BolsaFamiliaMunicipio:
    """Parse Bolsa Família municipality data."""
    raw_mun = raw.get("municipio")
    municipio = raw_mun if isinstance(raw_mun, dict) else {}
    return BolsaFamiliaMunicipio(
        municipio=municipio.get("nomeIBGE") or (raw_mun if isinstance(raw_mun, str) else None),
        uf=municipio.get("uf", {}).get("sigla") if isinstance(municipio.get("uf"), dict) else None,
        quantidade=raw.get("quantidadeBeneficiados"),
        valor=raw.get("valor"),
        data_referencia=raw.get("dataReferencia"),
    )


def _parse_bolsa_sacado(raw: dict[str, Any]) -> BolsaFamiliaSacado:
    """Parse Bolsa Família NIS beneficiary data."""
    raw_mun = raw.get("municipio")
    municipio = raw_mun if isinstance(raw_mun, dict) else {}
    return BolsaFamiliaSacado(
        nis=raw.get("nis"),
        nome=raw.get("nome"),
        municipio=municipio.get("nomeIBGE") if isinstance(municipio, dict) else None,
        uf=municipio.get("uf", {}).get("sigla")
        if isinstance(municipio, dict) and isinstance(municipio.get("uf"), dict)
        else None,
        valor=raw.get("valor"),
    )


def _parse_sancao(raw: dict[str, Any], fonte: str) -> Sancao:
    """Parse a sanction record from any of the 4 databases."""
    sancionado = raw.get("sancionado") or raw.get("pessoaSancionada") or {}
    orgao = raw.get("orgaoSancionador") or {}
    return Sancao(
        fonte=fonte,
        tipo=raw.get("tipoSancao") or raw.get("tipoPenalidade"),
        nome=sancionado.get("nome") or sancionado.get("razaoSocialReceita"),
        cpf_cnpj=sancionado.get("codigoFormatado") or sancionado.get("cnpjFormatado"),
        orgao=orgao.get("nome"),
        data_inicio=raw.get("dataInicioSancao") or raw.get("dataPublicacao"),
        data_fim=raw.get("dataFimSancao") or raw.get("dataFinalSancao"),
        fundamentacao=raw.get("fundamentacaoLegal") or raw.get("fundamentacao"),
    )


def _parse_emenda(raw: dict[str, Any]) -> Emenda:
    """Parse a parliamentary amendment record."""
    autor = raw.get("autor") or {}
    localidade = raw.get("localidadeDoGasto") or {}
    return Emenda(
        numero=raw.get("numero") or raw.get("codigoEmenda"),
        autor=autor.get("nome") if isinstance(autor, dict) else str(autor) if autor else None,
        tipo=raw.get("tipoEmenda"),
        localidade=localidade.get("nome")
        if isinstance(localidade, dict)
        else str(localidade)
        if localidade
        else None,
        valor_empenhado=parse_brl_number(raw.get("valorEmpenhado")),
        valor_pago=parse_brl_number(raw.get("valorPago")),
        ano=raw.get("ano"),
    )


def _parse_viagem(raw: dict[str, Any]) -> Viagem:
    """Parse a federal travel record."""
    return Viagem(
        id=raw.get("id"),
        cpf=raw.get("cpf"),
        nome=raw.get("nome") or raw.get("nomeProposto"),
        cargo=raw.get("cargo") or raw.get("funcao"),
        orgao=raw.get("nomeOrgao"),
        destino=raw.get("destinos") or raw.get("destino"),
        data_inicio=raw.get("dataInicio") or raw.get("dataInicioAfastamento"),
        data_fim=raw.get("dataFim") or raw.get("dataFimAfastamento"),
        valor_passagens=raw.get("valorPassagens"),
        valor_diarias=raw.get("valorDiarias"),
    )


# --- Public API functions ---------------------------------------------------


async def buscar_contratos(cpf_cnpj: str, pagina: int = 1) -> list[ContratoFornecedor]:
    """Busca contratos federais por CPF/CNPJ do fornecedor.

    Args:
        cpf_cnpj: CPF ou CNPJ do fornecedor (aceita formatado ou só dígitos).
        pagina: Número da página de resultados.
    """
    params = {"cpfCnpj": _clean_cpf_cnpj(cpf_cnpj), "pagina": pagina}
    data = await _get(CONTRATOS_URL, params)
    return _safe_parse_list(data, _parse_contrato, "contratos")


async def consultar_despesas(
    mes_ano_inicio: str,
    mes_ano_fim: str,
    codigo_favorecido: str | None = None,
    pagina: int = 1,
) -> list[RecursoRecebido]:
    """Consulta despesas/recursos recebidos por favorecido.

    Args:
        mes_ano_inicio: Mês/ano início no formato MM/AAAA.
        mes_ano_fim: Mês/ano fim no formato MM/AAAA.
        codigo_favorecido: CPF ou CNPJ do favorecido.
        pagina: Número da página.
    """
    params: dict[str, Any] = {
        "mesAnoInicio": mes_ano_inicio,
        "mesAnoFim": mes_ano_fim,
        "pagina": pagina,
    }
    if codigo_favorecido:
        params["codigoFavorecido"] = _clean_cpf_cnpj(codigo_favorecido)
    data = await _get(DESPESAS_URL, params)
    return _safe_parse_list(data, _parse_recurso, "despesas")


async def buscar_servidores(
    cpf: str | None = None,
    nome: str | None = None,
    codigo_orgao_lotacao: str | None = None,
    codigo_orgao_exercicio: str | None = None,
    pagina: int = 1,
) -> list[Servidor]:
    """Busca servidores públicos federais.

    A API exige pelo menos um filtro obrigatório: CPF, código de órgão de
    lotação ou código de órgão de exercício.

    Args:
        cpf: CPF do servidor.
        nome: Nome do servidor (usado como filtro adicional).
        codigo_orgao_lotacao: Código SIAPE do órgão de lotação.
        codigo_orgao_exercicio: Código SIAPE do órgão de exercício.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if cpf:
        params["cpf"] = _clean_cpf_cnpj(cpf)
    if codigo_orgao_lotacao:
        params["orgaoServidorLotacao"] = codigo_orgao_lotacao
    if codigo_orgao_exercicio:
        params["orgaoServidorExercicio"] = codigo_orgao_exercicio
    if nome:
        params["nome"] = nome
    data = await _get(SERVIDORES_URL, params)
    return _safe_parse_list(data, _parse_servidor, "servidores")


async def buscar_licitacoes(
    codigo_orgao: str | None = None,
    data_inicial: str | None = None,
    data_final: str | None = None,
    pagina: int = 1,
) -> list[Licitacao]:
    """Busca licitações federais.

    Args:
        codigo_orgao: Código do órgão (SIAFI).
        data_inicial: Data inicial no formato DD/MM/AAAA.
        data_final: Data final no formato DD/MM/AAAA.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    if data_inicial:
        params["dataInicial"] = data_inicial
    if data_final:
        params["dataFinal"] = data_final
    data = await _get(LICITACOES_URL, params)
    return _safe_parse_list(data, _parse_licitacao, "licitacoes")


async def consultar_bolsa_familia_municipio(
    mes_ano: str,
    codigo_ibge: str,
    pagina: int = 1,
) -> list[BolsaFamiliaMunicipio]:
    """Consulta dados do Novo Bolsa Família por município.

    Args:
        mes_ano: Mês/ano de referência no formato AAAAMM.
        codigo_ibge: Código IBGE do município.
        pagina: Número da página.
    """
    params: dict[str, Any] = {
        "mesAno": mes_ano,
        "codigoIbge": codigo_ibge,
        "pagina": pagina,
    }
    data = await _get(BOLSA_FAMILIA_MUNICIPIO_URL, params)
    return _safe_parse_list(data, _parse_bolsa_municipio, "bolsa-familia-municipio")


async def consultar_bolsa_familia_nis(
    mes_ano: str,
    nis: str,
    pagina: int = 1,
) -> list[BolsaFamiliaSacado]:
    """Consulta dados do Novo Bolsa Família por NIS do sacado.

    Args:
        mes_ano: Mês/ano de referência no formato AAAAMM.
        nis: Número de Identificação Social do beneficiário.
        pagina: Número da página.
    """
    params: dict[str, Any] = {
        "mesAno": mes_ano,
        "nis": nis,
        "pagina": pagina,
    }
    data = await _get(BOLSA_FAMILIA_NIS_URL, params)
    return _safe_parse_list(data, _parse_bolsa_sacado, "bolsa-familia-nis")


async def buscar_sancoes(
    consulta: str,
    bases: list[str] | None = None,
    pagina: int = 1,
) -> list[Sancao]:
    """Busca sanções em paralelo nas bases CEIS, CNEP, CEPIM e CEAF.

    Tenta primeiro por CPF/CNPJ; se falhar, tenta por nome.

    Args:
        consulta: CPF, CNPJ ou nome da pessoa/empresa.
        bases: Lista de bases a consultar (default: todas).
        pagina: Número da página.
    """
    bases_alvo = bases or list(SANCOES_DATABASES.keys())

    async def _consultar_base(base_key: str) -> list[Sancao]:
        db = SANCOES_DATABASES.get(base_key)
        if not db:
            return []

        url = db["url"]
        is_digits = consulta.strip().replace(".", "").replace("-", "").replace("/", "").isdigit()

        if is_digits:
            param_key = db["param_cpf_cnpj"]
            params: dict[str, Any] = {param_key: _clean_cpf_cnpj(consulta), "pagina": pagina}
        else:
            param_key = db["param_nome"]
            params = {param_key: consulta, "pagina": pagina}

        try:
            data = await _get(url, params=params)
            return _safe_parse_list(data, _parse_sancao, f"sancoes/{base_key}", fonte=db["nome"])
        except Exception:
            logger.warning("Falha ao consultar base %s para '%s'", base_key, consulta)
        return []

    results = await asyncio.gather(*[_consultar_base(b) for b in bases_alvo])
    return [sancao for sublist in results for sancao in sublist]


async def buscar_emendas(
    ano: int | None = None,
    nome_autor: str | None = None,
    pagina: int = 1,
) -> list[Emenda]:
    """Busca emendas parlamentares.

    Args:
        ano: Ano da emenda.
        nome_autor: Nome do autor da emenda.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if ano:
        params["ano"] = ano
    if nome_autor:
        params["nomeAutor"] = nome_autor
    data = await _get(EMENDAS_URL, params)
    return _safe_parse_list(data, _parse_emenda, "emendas")


async def consultar_viagens(cpf: str, pagina: int = 1) -> list[Viagem]:
    """Consulta viagens a serviço por CPF do servidor.

    Args:
        cpf: CPF do servidor.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"cpf": _clean_cpf_cnpj(cpf), "pagina": pagina}
    data = await _get(VIAGENS_URL, params)
    return _safe_parse_list(data, _parse_viagem, "viagens")


# --- Parsing helpers (new endpoints) ----------------------------------------


def _parse_convenio(raw: dict[str, Any]) -> Convenio:
    """Parse a raw agreement/covenant JSON."""
    orgao = raw.get("orgaoConcedente") or raw.get("orgao") or {}
    convenente = raw.get("convenente") or {}
    return Convenio(
        numero=raw.get("numero"),
        objeto=raw.get("objeto"),
        situacao=raw.get("situacao"),
        valor_convenio=raw.get("valorConvenio") or raw.get("valor"),
        valor_liberado=raw.get("valorLiberado"),
        orgao=orgao.get("nome") if isinstance(orgao, dict) else str(orgao) if orgao else None,
        convenente=convenente.get("nome")
        if isinstance(convenente, dict)
        else str(convenente)
        if convenente
        else None,
        data_inicio=raw.get("dataInicioVigencia"),
        data_fim=raw.get("dataFimVigencia"),
    )


def _parse_cartao(raw: dict[str, Any]) -> CartaoPagamento:
    """Parse a raw government credit card payment JSON."""
    return CartaoPagamento(
        portador=raw.get("portador") or raw.get("nomePortador"),
        cpf=raw.get("cpfPortador") or raw.get("cpf"),
        orgao=raw.get("nomeOrgao") or raw.get("orgao"),
        valor=raw.get("valorTransacao") or raw.get("valor"),
        data=raw.get("dataTransacao") or raw.get("data"),
        tipo=raw.get("tipoCartao") or raw.get("tipo"),
        estabelecimento=raw.get("nomeEstabelecimento") or raw.get("estabelecimento"),
    )


def _parse_pep(raw: dict[str, Any]) -> PessoaExpostaPoliticamente:
    """Parse a Politically Exposed Person record."""
    orgao = raw.get("orgao") or {}
    return PessoaExpostaPoliticamente(
        cpf=raw.get("cpf"),
        nome=raw.get("nome"),
        orgao=orgao.get("nome") if isinstance(orgao, dict) else str(orgao) if orgao else None,
        funcao=raw.get("funcao") or raw.get("descricaoFuncao"),
        data_inicio=raw.get("dataInicioExercicio") or raw.get("dataInicio"),
        data_fim=raw.get("dataFimExercicio") or raw.get("dataFim"),
    )


def _parse_acordo_leniencia(raw: dict[str, Any]) -> AcordoLeniencia:
    """Parse a leniency agreement record."""
    empresa = raw.get("pessoa") or raw.get("empresa") or {}
    orgao = raw.get("orgaoResponsavel") or raw.get("orgao") or {}
    return AcordoLeniencia(
        empresa=empresa.get("nome") or empresa.get("razaoSocial")
        if isinstance(empresa, dict)
        else str(empresa)
        if empresa
        else None,
        cnpj=empresa.get("cnpj") or empresa.get("codigoFormatado")
        if isinstance(empresa, dict)
        else None,
        orgao=orgao.get("nome") if isinstance(orgao, dict) else str(orgao) if orgao else None,
        situacao=raw.get("situacao"),
        data_inicio=raw.get("dataInicioAcordo") or raw.get("dataInicio"),
        data_fim=raw.get("dataFimAcordo") or raw.get("dataFim"),
        valor=raw.get("valorMulta") or raw.get("valor"),
    )


def _parse_nota_fiscal(raw: dict[str, Any]) -> NotaFiscal:
    """Parse an electronic invoice record."""
    emitente = raw.get("emitente") or {}
    return NotaFiscal(
        numero=raw.get("numero"),
        serie=raw.get("serie"),
        emitente=emitente.get("nome") or emitente.get("razaoSocial")
        if isinstance(emitente, dict)
        else str(emitente)
        if emitente
        else None,
        cnpj_emitente=emitente.get("cnpj") if isinstance(emitente, dict) else None,
        valor=raw.get("valor") or raw.get("valorTotal"),
        data_emissao=raw.get("dataEmissao"),
    )


def _parse_beneficio_social(raw: dict[str, Any]) -> BeneficioSocial:
    """Parse a social benefit record."""
    municipio_raw = raw.get("municipio")
    municipio = municipio_raw if isinstance(municipio_raw, dict) else {}
    return BeneficioSocial(
        tipo=raw.get("tipoBeneficio") or raw.get("tipo"),
        nome_beneficiario=raw.get("nomeBeneficiario") or raw.get("nome"),
        cpf=raw.get("cpf"),
        nis=raw.get("nis"),
        valor=raw.get("valor"),
        mes_referencia=raw.get("mesReferencia") or raw.get("dataReferencia"),
        municipio=municipio.get("nomeIBGE")
        if isinstance(municipio, dict)
        else str(municipio_raw)
        if municipio_raw
        else None,
        uf=municipio.get("uf", {}).get("sigla")
        if isinstance(municipio, dict) and isinstance(municipio.get("uf"), dict)
        else None,
    )


def _parse_pessoa_fisica(raw: dict[str, Any]) -> PessoaFisicaVinculos:
    """Parse physical person linkage record."""
    return PessoaFisicaVinculos(
        cpf=raw.get("cpf"),
        nome=raw.get("nome"),
        tipo_vinculo=raw.get("tipoVinculo") or raw.get("tipo"),
        orgao=raw.get("orgao") or raw.get("nomeOrgao"),
        beneficios=raw.get("beneficios"),
    )


def _parse_pessoa_juridica(raw: dict[str, Any]) -> PessoaJuridicaVinculos:
    """Parse juridical person linkage record."""
    return PessoaJuridicaVinculos(
        cnpj=raw.get("cnpj"),
        razao_social=raw.get("razaoSocial") or raw.get("nome"),
        sancoes=raw.get("sancoes"),
        contratos=raw.get("contratos"),
    )


def _parse_contrato_detalhe(raw: dict[str, Any]) -> ContratoDetalhe:
    """Parse a detailed contract record."""
    fornecedor = raw.get("fornecedor") or {}
    orgao = raw.get("unidadeGestora") or raw.get("orgaoVinculado") or {}
    return ContratoDetalhe(
        id=raw.get("id"),
        numero=raw.get("numero"),
        objeto=raw.get("objeto"),
        valor_inicial=raw.get("valorInicial"),
        valor_final=raw.get("valorFinal"),
        data_inicio=raw.get("dataInicioVigencia"),
        data_fim=raw.get("dataFimVigencia"),
        orgao=orgao.get("nome") or orgao.get("descricao"),
        fornecedor=fornecedor.get("nome") or fornecedor.get("razaoSocialReceita"),
        modalidade=raw.get("modalidadeCompra") or raw.get("modalidade"),
        situacao=raw.get("situacao"),
        licitacao=raw.get("licitacao") or raw.get("numeroLicitacao"),
    )


def _parse_servidor_detalhe(raw: dict[str, Any]) -> ServidorDetalhe:
    """Parse a detailed public servant record with compensation."""
    orgao = raw.get("orgaoServidorExercicio") or raw.get("orgaoServidorLotacao") or {}
    return ServidorDetalhe(
        id=raw.get("id"),
        cpf=raw.get("cpf"),
        nome=raw.get("nome"),
        tipo_servidor=raw.get("tipoServidor"),
        situacao=raw.get("situacao"),
        orgao=orgao.get("nome") or orgao.get("descricao"),
        cargo=raw.get("cargo"),
        funcao=raw.get("funcao"),
        remuneracao_basica=raw.get("remuneracaoBasicaBruta"),
        remuneracao_apos_deducoes=raw.get("remuneracaoAposDeducoesObrigatorias"),
        honorarios=raw.get("honorariosAdvocaticios") or raw.get("honorarios"),
        outras_remuneracoes=raw.get("outrasRemuneracoesEventuais"),
        jetons=raw.get("jepiRemuneracao") or raw.get("jetons"),
    )


# --- Public API functions (new endpoints) -----------------------------------


async def buscar_convenios(
    orgao: str | None = None,
    convenente: str | None = None,
    pagina: int = 1,
) -> list[Convenio]:
    """Busca convênios e transferências voluntárias.

    Args:
        orgao: Código do órgão concedente.
        convenente: Nome ou CNPJ do convenente.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if orgao:
        params["codigoOrgao"] = orgao
    if convenente:
        params["convenente"] = convenente
    data = await _get(CONVENIOS_URL, params)
    return _safe_parse_list(data, _parse_convenio, "convenios")


async def buscar_cartoes_pagamento(
    cpf_portador: str | None = None,
    codigo_orgao: str | None = None,
    mes_ano_inicio: str | None = None,
    mes_ano_fim: str | None = None,
    pagina: int = 1,
) -> list[CartaoPagamento]:
    """Busca pagamentos com cartão corporativo/suprimento de fundos.

    Args:
        cpf_portador: CPF do portador do cartão.
        codigo_orgao: Código do órgão.
        mes_ano_inicio: Mês/ano de início no formato MM/AAAA.
        mes_ano_fim: Mês/ano de fim no formato MM/AAAA.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if cpf_portador:
        params["cpfPortador"] = _clean_cpf_cnpj(cpf_portador)
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    if mes_ano_inicio:
        params["mesExtratoInicio"] = mes_ano_inicio
    if mes_ano_fim:
        params["mesExtratoFim"] = mes_ano_fim
    data = await _get(CARTOES_URL, params)
    return _safe_parse_list(data, _parse_cartao, "cartoes")


async def buscar_pep(
    cpf: str | None = None,
    nome: str | None = None,
    pagina: int = 1,
) -> list[PessoaExpostaPoliticamente]:
    """Busca Pessoas Expostas Politicamente (PEP).

    Args:
        cpf: CPF da pessoa.
        nome: Nome da pessoa.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if cpf:
        params["cpf"] = _clean_cpf_cnpj(cpf)
    elif nome:
        params["nome"] = nome
    data = await _get(PEP_URL, params)
    return _safe_parse_list(data, _parse_pep, "pep")


async def buscar_acordos_leniencia(
    nome_empresa: str | None = None,
    cnpj: str | None = None,
    pagina: int = 1,
) -> list[AcordoLeniencia]:
    """Busca acordos de leniência (anticorrupção).

    Args:
        nome_empresa: Nome da empresa.
        cnpj: CNPJ da empresa.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if nome_empresa:
        params["nomeEmpresa"] = nome_empresa
    if cnpj:
        params["cnpj"] = _clean_cpf_cnpj(cnpj)
    data = await _get(ACORDOS_LENIENCIA_URL, params)
    return _safe_parse_list(data, _parse_acordo_leniencia, "acordos-leniencia")


async def buscar_notas_fiscais(
    cnpj_emitente: str | None = None,
    data_emissao_de: str | None = None,
    data_emissao_ate: str | None = None,
    pagina: int = 1,
) -> list[NotaFiscal]:
    """Busca notas fiscais eletrônicas.

    Args:
        cnpj_emitente: CNPJ do emitente da nota.
        data_emissao_de: Data de emissão inicial DD/MM/AAAA.
        data_emissao_ate: Data de emissão final DD/MM/AAAA.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if cnpj_emitente:
        params["cnpjEmitente"] = _clean_cpf_cnpj(cnpj_emitente)
    if data_emissao_de:
        params["dataEmissaoDe"] = data_emissao_de
    if data_emissao_ate:
        params["dataEmissaoAte"] = data_emissao_ate
    data = await _get(NOTAS_FISCAIS_URL, params)
    return _safe_parse_list(data, _parse_nota_fiscal, "notas-fiscais")


async def consultar_beneficio_social(
    cpf: str | None = None,
    nis: str | None = None,
    mes_ano: str | None = None,
    pagina: int = 1,
) -> list[BeneficioSocial]:
    """Consulta benefícios sociais (BPC, seguro-desemprego, etc.) por CPF/NIS.

    Args:
        cpf: CPF do beneficiário.
        nis: NIS do beneficiário.
        mes_ano: Mês/ano de referência no formato AAAAMM.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if cpf:
        params["cpf"] = _clean_cpf_cnpj(cpf)
    if nis:
        params["nis"] = nis
    if mes_ano:
        params["mesAno"] = mes_ano
    data = await _get(BENEFICIOS_CIDADAO_URL, params)
    return _safe_parse_list(data, _parse_beneficio_social, "beneficios-cidadao")


async def consultar_cpf(cpf: str, pagina: int = 1) -> list[PessoaFisicaVinculos]:
    """Consulta vínculos e benefícios por CPF.

    Args:
        cpf: CPF da pessoa física.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"cpf": _clean_cpf_cnpj(cpf), "pagina": pagina}
    data = await _get(PESSOAS_FISICAS_URL, params)
    return _safe_parse_list(data, _parse_pessoa_fisica, "pessoas-fisicas")


async def consultar_cnpj(cnpj: str, pagina: int = 1) -> list[PessoaJuridicaVinculos]:
    """Consulta sanções e contratos por CNPJ.

    Args:
        cnpj: CNPJ da pessoa jurídica.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"cnpj": _clean_cpf_cnpj(cnpj), "pagina": pagina}
    data = await _get(PESSOAS_JURIDICAS_URL, params)
    return _safe_parse_list(data, _parse_pessoa_juridica, "pessoas-juridicas")


async def detalhar_contrato(id_contrato: int) -> ContratoDetalhe | None:
    """Busca detalhe de um contrato específico por ID.

    Args:
        id_contrato: ID do contrato no Portal da Transparência.
    """
    url = f"{CONTRATO_DETALHE_URL}/{id_contrato}"
    data = await _get(url)
    if isinstance(data, dict):
        return _parse_contrato_detalhe(data)
    return None


async def detalhar_servidor(id_servidor: int) -> ServidorDetalhe | None:
    """Busca detalhe completo de um servidor com remuneração.

    Args:
        id_servidor: ID do servidor no Portal da Transparência.
    """
    url = f"{SERVIDOR_DETALHE_URL}/{id_servidor}"
    data = await _get(url)
    if isinstance(data, dict):
        return _parse_servidor_detalhe(data)
    return None


# --- Parsing helpers (novos endpoints) ----------------------------------------


def _safe_float(val: Any) -> float | None:
    """Convert a value to float, handling strings and None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _nested_str(val: Any, *keys: str) -> str | None:
    """Extract a string from a value that may be a string, dict, or None.

    Handles the Portal API pattern where some fields are returned as nested
    objects ``{"id": ..., "descricao": ...}`` instead of plain strings.
    """
    if val is None:
        return None
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        for key in (*keys, "descricao", "nome", "sigla"):
            v = val.get(key)
            if v is not None:
                return str(v)
    return str(val) if val else None


def _parse_imovel(raw: dict[str, Any]) -> ImovelFuncional:
    """Parse a functional property record.

    DTO: ImovelFuncionalDTO — id, dataReferencia, orgaoResponsavel{nome, codigoSIAFI},
    situacao{id, descricao}, regiao{id, descricao}, endereco, cep.
    """
    orgao = raw.get("orgaoResponsavel") or {}
    return ImovelFuncional(
        id=raw.get("id"),
        endereco=raw.get("endereco"),
        cep=raw.get("cep"),
        regiao=_nested_str(raw.get("regiao")),
        situacao=_nested_str(raw.get("situacao")),
        orgao_responsavel=orgao.get("nome") if isinstance(orgao, dict) else str(orgao or ""),
        data_referencia=raw.get("dataReferencia"),
    )


def _parse_permissionario(raw: dict[str, Any]) -> Permissionario:
    """Parse a property occupant record.

    DTO: PermissionarioDTO — id, dataReferencia, orgaoResponsavel{nome, codigoSIAFI},
    dataInicioOcupacao, pessoaPermissionario{cpfFormatado, nome, ...},
    permissionario{cpfFormatado, nis, nome}, orgaoPermissionario, cargo, valorPagoMes.
    """
    pessoa = raw.get("pessoaPermissionario") or {}
    perm = raw.get("permissionario") or {}
    orgao = raw.get("orgaoResponsavel") or {}
    cpf = (pessoa.get("cpfFormatado") if isinstance(pessoa, dict) else None) or (
        perm.get("cpfFormatado") if isinstance(perm, dict) else None
    )
    nome = (pessoa.get("nome") if isinstance(pessoa, dict) else None) or (
        perm.get("nome") if isinstance(perm, dict) else None
    )
    orgao_nome = orgao.get("nome") if isinstance(orgao, dict) else str(orgao or "")
    return Permissionario(
        cpf=cpf,
        nome=nome,
        orgao=orgao_nome or None,
        orgao_permissionario=raw.get("orgaoPermissionario"),
        cargo=raw.get("cargo"),
        valor_pago_mes=_safe_float(raw.get("valorPagoMes")),
        data_inicio=raw.get("dataInicioOcupacao"),
    )


def _parse_renuncia(raw: dict[str, Any]) -> RenunciaFiscal:
    """Parse a tax waiver record.

    DTO: RenunciaDTO — ano, valorRenunciado, tipoRenuncia,
    descricaoBeneficioFiscal, descricaoFundamentoLegal, tributo,
    formaTributacao, cnpj, razaoSocial, nomeFantasia,
    cnae*, uf, municipio, codigoIBGE.
    """
    return RenunciaFiscal(
        cnpj=raw.get("cnpj"),
        razao_social=raw.get("razaoSocial") or raw.get("nomeFantasia"),
        tipo_renuncia=raw.get("tipoRenuncia"),
        beneficio_fiscal=raw.get("descricaoBeneficioFiscal"),
        tributo=raw.get("tributo"),
        uf=raw.get("uf"),
        valor=_safe_float(raw.get("valorRenunciado")),
        ano=raw.get("ano"),
    )


def _parse_empresa_beneficio(raw: dict[str, Any]) -> EmpresaBeneficioFiscal:
    """Parse a tax benefit company record.

    DTO (habilitadas): EmpresaHabilitadaBeneficioFiscalDTO — cnpj, beneficiario,
    nomeFantasia, uf, municipio, beneficioFiscal, descricao, fundamentoLegal,
    fruicaoVigente, dataInicioFruicao, dataFimFruicao, cnae*.
    DTO (imunes): EmpresaImuneIsentaDTO — cnpj, beneficiario, nomeFantasia,
    uf, municipio, tipoEntidade, beneficioFiscal, cnae*.
    """
    return EmpresaBeneficioFiscal(
        cnpj=raw.get("cnpj"),
        razao_social=raw.get("beneficiario"),
        nome_fantasia=raw.get("nomeFantasia"),
        beneficio_fiscal=raw.get("beneficioFiscal"),
        fruicao_vigente=raw.get("fruicaoVigente") or raw.get("tipoEntidade"),
        uf=raw.get("uf"),
    )


def _parse_orgao(raw: dict[str, Any]) -> Orgao:
    """Parse an agency record.

    DTO: CodigoDescricaoDTO — codigo, descricao.
    """
    return Orgao(
        codigo=raw.get("codigo"),
        descricao=raw.get("descricao"),
    )


def _parse_covid_transferencia(raw: dict[str, Any]) -> CoronavirusTransferencia:
    """Parse a COVID-19 transfer record.

    DTO: TransferenciaCoronavirusDTO — mesAno, tipoTransferencia, codigoOrgao,
    orgao, tipoFavorecido, codigoFavorecido, favorecido, codigoFuncao, funcao,
    codigoPrograma, programa, codigoAcao, acao, codigoGrupoDespesa,
    grupoDespesa, ..., valor.
    """
    return CoronavirusTransferencia(
        tipo=raw.get("tipoTransferencia"),
        orgao=raw.get("orgao"),
        favorecido=raw.get("favorecido"),
        valor=_safe_float(raw.get("valor")),
        acao=raw.get("acao"),
        grupo_despesa=raw.get("grupoDespesa"),
    )


def _parse_covid_despesa(raw: dict[str, Any]) -> CoronavirusDespesa:
    """Parse a COVID-19 expense record.

    DTO: MovimentacaoLiquidaCovidDTO — mesAno, codigoFuncao, funcao,
    codigoSubfuncao, subfuncao, codigoPrograma, programa, codigoAcao, acao,
    codigoGrupoDespesa, grupoDespesa, ..., empenhado, pago, liquidado.
    """
    return CoronavirusDespesa(
        funcao=raw.get("funcao"),
        acao=raw.get("acao"),
        programa=raw.get("programa"),
        grupo_despesa=raw.get("grupoDespesa"),
        empenhado=_safe_float(raw.get("empenhado")),
        liquidado=_safe_float(raw.get("liquidado")),
        pago=_safe_float(raw.get("pago")),
    )


def _parse_remuneracao(raw: dict[str, Any]) -> RemuneracaoServidor:
    """Parse a server compensation record."""
    orgao = raw.get("orgaoServidorExercicio") or raw.get("orgaoServidorLotacao") or {}
    return RemuneracaoServidor(
        id=raw.get("id"),
        cpf=raw.get("cpf"),
        nome=raw.get("nome"),
        orgao=orgao.get("nome") or orgao.get("descricao")
        if isinstance(orgao, dict)
        else str(orgao)
        if orgao
        else None,
        remuneracao_basica=raw.get("remuneracaoBasicaBruta"),
        remuneracao_apos_deducoes=raw.get("remuneracaoAposDeducoesObrigatorias"),
    )


def _parse_servidor_agregado(raw: dict[str, Any]) -> ServidorAgregado:
    """Parse aggregated server data by agency."""
    orgao = raw.get("orgao") or {}
    return ServidorAgregado(
        orgao_codigo=orgao.get("codigo") if isinstance(orgao, dict) else None,
        orgao_nome=orgao.get("nome") or orgao.get("descricao")
        if isinstance(orgao, dict)
        else str(orgao)
        if orgao
        else None,
        quantidade=raw.get("quantidade") or raw.get("quantidadeServidores"),
    )


def _parse_funcao_cargo(raw: dict[str, Any]) -> FuncaoCargo:
    """Parse a function/position record."""
    orgao = raw.get("orgao") or {}
    return FuncaoCargo(
        id=raw.get("id"),
        nome=raw.get("nome") or raw.get("descricao"),
        nivel=raw.get("nivel"),
        orgao=orgao.get("nome") if isinstance(orgao, dict) else str(orgao) if orgao else None,
        tipo=raw.get("tipo"),
    )


def _parse_beneficio_municipio(
    raw: dict[str, Any],
    cls: type[SeguroDefeso] | type[GarantiaSafra] | type[PetiBeneficio],
) -> SeguroDefeso | GarantiaSafra | PetiBeneficio:
    """Parse a municipality-based benefit record."""
    municipio_raw = raw.get("municipio")
    municipio = municipio_raw if isinstance(municipio_raw, dict) else {}
    return cls(
        nis=raw.get("nis"),
        nome=raw.get("nome"),
        municipio=municipio.get("nomeIBGE")
        if isinstance(municipio, dict)
        else (str(municipio_raw) if municipio_raw else None),
        uf=municipio.get("uf", {}).get("sigla")
        if isinstance(municipio, dict) and isinstance(municipio.get("uf"), dict)
        else None,
        valor=raw.get("valor"),
        quantidade=raw.get("quantidadeBeneficiados"),
        data_referencia=raw.get("dataReferencia") or raw.get("mesReferencia"),
    )


def _parse_licitacao_detalhe(raw: dict[str, Any]) -> LicitacaoDetalhe:
    """Parse a detailed procurement record."""
    orgao = raw.get("unidadeGestora") or raw.get("orgao") or {}
    return LicitacaoDetalhe(
        id=raw.get("id"),
        numero=raw.get("numero"),
        objeto=raw.get("objeto"),
        modalidade=raw.get("modalidadeLicitacao") or raw.get("modalidade"),
        situacao=raw.get("situacao"),
        valor_estimado=raw.get("valorEstimado"),
        data_abertura=raw.get("dataAbertura") or raw.get("dataResultadoCompra"),
        orgao=orgao.get("nome") or orgao.get("descricao"),
        processo=raw.get("processo") or raw.get("numeroProcesso"),
        fornecedor_vencedor=raw.get("fornecedorVencedor"),
    )


def _parse_participante(raw: dict[str, Any]) -> ParticipanteLicitacao:
    """Parse a bid participant record."""
    return ParticipanteLicitacao(
        cpf_cnpj=raw.get("cnpj") or raw.get("cpf") or raw.get("codigoFormatado"),
        nome=raw.get("nome") or raw.get("razaoSocial"),
        situacao=raw.get("situacao") or raw.get("declaracaoVencedor"),
        valor_proposta=raw.get("valorProposta") or raw.get("valor"),
    )


def _parse_item_licitado(raw: dict[str, Any]) -> ItemLicitado:
    """Parse a bid item record."""
    return ItemLicitado(
        descricao=raw.get("descricao") or raw.get("descricaoItem"),
        quantidade=raw.get("quantidade"),
        valor_estimado=raw.get("valorEstimado"),
        valor_homologado=raw.get("valorHomologado"),
        fornecedor=raw.get("nomeFornecedor") or raw.get("fornecedor"),
    )


def _parse_documento_emenda(raw: dict[str, Any]) -> DocumentoEmenda:
    """Parse an amendment document record."""
    return DocumentoEmenda(
        codigo=raw.get("codigo") or raw.get("codigoDocumento"),
        tipo=raw.get("tipo") or raw.get("tipoDocumento"),
        descricao=raw.get("descricao") or raw.get("nomeDocumento"),
        valor=raw.get("valor"),
        data=raw.get("data"),
    )


def _parse_despesa_orgao(raw: dict[str, Any]) -> DespesaOrgao:
    """Parse an expense by agency record."""
    orgao = raw.get("orgao") or {}
    return DespesaOrgao(
        orgao_codigo=orgao.get("codigo") if isinstance(orgao, dict) else None,
        orgao_nome=orgao.get("nome") or orgao.get("descricao")
        if isinstance(orgao, dict)
        else str(orgao)
        if orgao
        else None,
        empenhado=raw.get("valorEmpenhado"),
        liquidado=raw.get("valorLiquidado"),
        pago=raw.get("valorPago"),
        ano=raw.get("ano"),
        mes=raw.get("mes"),
    )


def _extract_desc(obj: Any) -> str | None:
    """Extract description from a dict-or-scalar field."""
    if isinstance(obj, dict):
        return obj.get("descricao")
    return str(obj) if obj else None


def _parse_despesa_funcional(raw: dict[str, Any]) -> DespesaFuncional:
    """Parse a functional-programmatic expense record."""
    return DespesaFuncional(
        funcao=_extract_desc(raw.get("funcao") or {}),
        subfuncao=_extract_desc(raw.get("subfuncao") or {}),
        programa=_extract_desc(raw.get("programa") or {}),
        acao=_extract_desc(raw.get("acao") or {}),
        empenhado=raw.get("valorEmpenhado"),
        liquidado=raw.get("valorLiquidado"),
        pago=raw.get("valorPago"),
    )


def _parse_documento_despesa(raw: dict[str, Any]) -> DocumentoDespesa:
    """Parse an expense document record."""
    return DocumentoDespesa(
        codigo=raw.get("codigo") or raw.get("codigoDocumento"),
        tipo=raw.get("tipo") or raw.get("tipoDocumento"),
        data=raw.get("data") or raw.get("dataDocumento"),
        valor=raw.get("valor"),
        favorecido=raw.get("nomeFavorecido") or raw.get("favorecido"),
        orgao=raw.get("nomeOrgao") or raw.get("orgao"),
    )


def _parse_item_empenho(raw: dict[str, Any]) -> ItemEmpenho:
    """Parse a commitment item record."""
    return ItemEmpenho(
        descricao=raw.get("descricao") or raw.get("descricaoItem"),
        quantidade=raw.get("quantidade"),
        valor_unitario=raw.get("valorUnitario"),
        valor_total=raw.get("valorTotal") or raw.get("valor"),
    )


def _parse_convenio_detalhe(raw: dict[str, Any]) -> ConvenioDetalhe:
    """Parse a detailed agreement record."""
    orgao = raw.get("orgaoConcedente") or raw.get("orgao") or {}
    convenente = raw.get("convenente") or {}
    return ConvenioDetalhe(
        id=raw.get("id"),
        numero=raw.get("numero"),
        objeto=raw.get("objeto"),
        situacao=raw.get("situacao"),
        valor_convenio=raw.get("valorConvenio") or raw.get("valor"),
        valor_liberado=raw.get("valorLiberado"),
        valor_contrapartida=raw.get("valorContrapartida"),
        orgao=orgao.get("nome") if isinstance(orgao, dict) else str(orgao) if orgao else None,
        convenente=convenente.get("nome")
        if isinstance(convenente, dict)
        else str(convenente)
        if convenente
        else None,
        data_inicio=raw.get("dataInicioVigencia"),
        data_fim=raw.get("dataFimVigencia"),
        tipo_instrumento=raw.get("tipoInstrumento"),
    )


def _parse_contrato_geral(raw: dict[str, Any]) -> ContratoGeral:
    """Parse a general contract record."""
    fornecedor = raw.get("fornecedor") or {}
    orgao = raw.get("unidadeGestora") or raw.get("orgaoVinculado") or {}
    return ContratoGeral(
        id=raw.get("id"),
        numero=raw.get("numero"),
        objeto=raw.get("objeto"),
        valor_inicial=raw.get("valorInicial"),
        valor_final=raw.get("valorFinal"),
        data_inicio=raw.get("dataInicioVigencia"),
        data_fim=raw.get("dataFimVigencia"),
        orgao=orgao.get("nome") or orgao.get("descricao"),
        fornecedor=fornecedor.get("nome") or fornecedor.get("razaoSocialReceita"),
        modalidade=raw.get("modalidadeCompra") or raw.get("modalidade"),
        situacao=raw.get("situacao"),
    )


def _parse_termo_aditivo(raw: dict[str, Any]) -> TermoAditivo:
    """Parse a contract additive term record."""
    return TermoAditivo(
        numero=raw.get("numero"),
        objeto=raw.get("objeto") or raw.get("descricao"),
        data=raw.get("dataPublicacao") or raw.get("data"),
        valor=raw.get("valor") or raw.get("valorAcrescimo"),
    )


def _parse_item_contratado(raw: dict[str, Any]) -> ItemContratado:
    """Parse a contracted item record."""
    return ItemContratado(
        descricao=raw.get("descricao") or raw.get("descricaoItem"),
        quantidade=raw.get("quantidade"),
        valor_unitario=raw.get("valorUnitario"),
        valor_total=raw.get("valorTotal") or raw.get("valor"),
    )


def _parse_sancao_detalhe(raw: dict[str, Any], fonte: str) -> SancaoDetalhe:
    """Parse a detailed sanction record."""
    sancionado = raw.get("sancionado") or raw.get("pessoaSancionada") or {}
    orgao = raw.get("orgaoSancionador") or {}
    return SancaoDetalhe(
        id=raw.get("id"),
        fonte=fonte,
        tipo=raw.get("tipoSancao") or raw.get("tipoPenalidade"),
        nome=sancionado.get("nome") or sancionado.get("razaoSocialReceita"),
        cpf_cnpj=sancionado.get("codigoFormatado") or sancionado.get("cnpjFormatado"),
        orgao=orgao.get("nome"),
        data_inicio=raw.get("dataInicioSancao") or raw.get("dataPublicacao"),
        data_fim=raw.get("dataFimSancao") or raw.get("dataFinalSancao"),
        fundamentacao=raw.get("fundamentacaoLegal") or raw.get("fundamentacao"),
        processo=raw.get("processo") or raw.get("numeroProcesso"),
        valor_multa=raw.get("valorMulta"),
    )


def _parse_unidade_gestora(raw: dict[str, Any]) -> UnidadeGestora:
    """Parse a managing unit record."""
    orgao = raw.get("orgaoVinculado") or raw.get("orgao") or {}
    mun = raw.get("municipio") or {}
    return UnidadeGestora(
        codigo=raw.get("codigo"),
        nome=raw.get("nome") or raw.get("descricao"),
        orgao_vinculado=orgao.get("nome") or orgao.get("descricao")
        if isinstance(orgao, dict)
        else str(orgao)
        if orgao
        else None,
        municipio=mun.get("nomeIBGE") if isinstance(mun, dict) else str(mun) if mun else None,
        uf=mun.get("uf", {}).get("sigla")
        if isinstance(mun, dict) and isinstance(mun.get("uf"), dict)
        else None,
    )


# --- Public API (novos endpoints) -------------------------------------------


async def buscar_imoveis_funcionais(
    regiao: str | None = None,
    cep: str | None = None,
    endereco: str | None = None,
    pagina: int = 1,
) -> list[ImovelFuncional]:
    """Busca imóveis funcionais da União.

    Args:
        regiao: Região (ex: Centro-Oeste).
        cep: CEP do imóvel.
        endereco: Trecho do endereço.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if regiao:
        params["regiao"] = regiao
    if cep:
        params["cep"] = cep
    if endereco:
        params["endereco"] = endereco
    data = await _get(IMOVEIS_URL, params)
    return _safe_parse_list(data, _parse_imovel, "imoveis")


async def buscar_permissionarios(
    cpf: str | None = None,
    orgao: str | None = None,
    pagina: int = 1,
) -> list[Permissionario]:
    """Busca permissionários/ocupantes de imóveis funcionais.

    Args:
        cpf: CPF do permissionário.
        orgao: Código do órgão.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if cpf:
        params["cpfOcupante"] = _clean_cpf_cnpj(cpf)
    if orgao:
        params["codigoOrgaoResponsavelGestaoSiafi"] = orgao
    data = await _get(PERMISSIONARIOS_URL, params)
    return _safe_parse_list(data, _parse_permissionario, "permissionarios")


async def buscar_renuncias_fiscais(
    cnpj: str | None = None,
    uf: str | None = None,
    codigo_ibge: str | None = None,
    pagina: int = 1,
) -> list[RenunciaFiscal]:
    """Busca renúncias de receita fiscal.

    Args:
        cnpj: CNPJ da empresa.
        uf: Sigla da UF (ex: SP, RJ).
        codigo_ibge: Código IBGE do município.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if cnpj:
        params["cnpj"] = _clean_cpf_cnpj(cnpj)
    if uf:
        params["nomeSiglaUF"] = uf.upper()
    if codigo_ibge:
        params["codigoIbge"] = codigo_ibge
    data = await _get(RENUNCIAS_VALOR_URL, params)
    return _safe_parse_list(data, _parse_renuncia, "renuncias")


async def buscar_empresas_beneficios_fiscais(
    cnpj: str | None = None,
    tipo: str = "habilitadas",
    pagina: int = 1,
) -> list[EmpresaBeneficioFiscal]:
    """Busca empresas com benefícios fiscais.

    Args:
        cnpj: CNPJ da empresa.
        tipo: 'habilitadas' ou 'imunes' (default: habilitadas).
        pagina: Número da página.
    """
    url = RENUNCIAS_HABILITADAS_URL if tipo == "habilitadas" else RENUNCIAS_IMUNES_URL
    params: dict[str, Any] = {"pagina": pagina}
    if cnpj:
        params["cnpj"] = _clean_cpf_cnpj(cnpj)
    data = await _get(url, params)
    return _safe_parse_list(data, _parse_empresa_beneficio, f"empresas-{tipo}")


async def listar_orgaos(
    tipo: str = "siape",
    pagina: int = 1,
) -> list[Orgao]:
    """Lista órgãos do governo federal.

    Args:
        tipo: 'siape' ou 'siafi'.
        pagina: Número da página.
    """
    url = ORGAOS_SIAPE_URL if tipo == "siape" else ORGAOS_SIAFI_URL
    data = await _get(url, {"pagina": pagina})
    return _safe_parse_list(data, _parse_orgao, f"orgaos-{tipo}")


async def consultar_coronavirus_transferencias(
    mes_ano: str,
    pagina: int = 1,
) -> list[CoronavirusTransferencia]:
    """Consulta transferências emergenciais COVID-19.

    Args:
        mes_ano: Mês/ano no formato AAAAMM (ex: 202003 para março de 2020).
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina, "mesAno": mes_ano}
    data = await _get(CORONAVIRUS_TRANSFERENCIAS_URL, params)
    return _safe_parse_list(data, _parse_covid_transferencia, "covid-transferencias")


async def consultar_coronavirus_despesas(
    mes_ano: str,
    pagina: int = 1,
) -> list[CoronavirusDespesa]:
    """Consulta despesas COVID-19.

    Args:
        mes_ano: Mês/ano no formato AAAAMM (ex: 202003 para março de 2020).
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina, "mesAnoLancamento": mes_ano}
    data = await _get(CORONAVIRUS_DESPESAS_URL, params)
    return _safe_parse_list(data, _parse_covid_despesa, "covid-despesas")


async def buscar_viagens_orgao(
    codigo_orgao: str | None = None,
    data_ida_de: str | None = None,
    data_ida_ate: str | None = None,
    pagina: int = 1,
) -> list[Viagem]:
    """Busca viagens a serviço por período e órgão.

    Args:
        codigo_orgao: Código do órgão.
        data_ida_de: Data de ida início (DD/MM/AAAA).
        data_ida_ate: Data de ida fim (DD/MM/AAAA).
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    if data_ida_de:
        params["dataIdaDe"] = data_ida_de
    if data_ida_ate:
        params["dataIdaAte"] = data_ida_ate
    data = await _get(VIAGENS_ORGAO_URL, params)
    return _safe_parse_list(data, _parse_viagem, "viagens-orgao")


async def detalhar_viagem(id_viagem: int) -> Viagem | None:
    """Busca detalhe de uma viagem por ID.

    Args:
        id_viagem: ID da viagem.
    """
    url = f"{VIAGENS_ORGAO_URL}/{id_viagem}"
    data = await _get(url)
    if isinstance(data, dict):
        return _parse_viagem(data)
    return None


async def buscar_remuneracoes_servidores(
    cpf: str | None = None,
    codigo_orgao: str | None = None,
    pagina: int = 1,
) -> list[RemuneracaoServidor]:
    """Busca remunerações de servidores públicos.

    Args:
        cpf: CPF do servidor.
        codigo_orgao: Código SIAPE do órgão.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if cpf:
        params["cpf"] = _clean_cpf_cnpj(cpf)
    if codigo_orgao:
        params["orgaoServidorLotacao"] = codigo_orgao
    data = await _get(SERVIDORES_REMUNERACAO_URL, params)
    return _safe_parse_list(data, _parse_remuneracao, "remuneracoes")


async def buscar_servidores_por_orgao(
    codigo_orgao: str,
    pagina: int = 1,
) -> list[ServidorAgregado]:
    """Busca servidores agregados por órgão.

    Args:
        codigo_orgao: Código SIAPE do órgão.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"orgaoServidorLotacao": codigo_orgao, "pagina": pagina}
    data = await _get(SERVIDORES_POR_ORGAO_URL, params)
    return _safe_parse_list(data, _parse_servidor_agregado, "servidores-por-orgao")


async def listar_funcoes_cargos(
    codigo_orgao: str | None = None,
    pagina: int = 1,
) -> list[FuncaoCargo]:
    """Lista funções e cargos de confiança.

    Args:
        codigo_orgao: Código SIAPE do órgão (opcional).
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if codigo_orgao:
        params["orgaoServidorLotacao"] = codigo_orgao
    data = await _get(SERVIDORES_FUNCOES_URL, params)
    return _safe_parse_list(data, _parse_funcao_cargo, "funcoes-cargos")


async def consultar_seguro_defeso(
    mes_ano: str,
    codigo_ibge: str | None = None,
    cpf: str | None = None,
    nis: str | None = None,
    pagina: int = 1,
) -> list[SeguroDefeso]:
    """Consulta seguro-defeso (pescador artesanal).

    Args:
        mes_ano: Mês/ano de referência (AAAAMM).
        codigo_ibge: Código IBGE do município.
        cpf: CPF do beneficiário.
        nis: NIS do beneficiário.
        pagina: Número da página.
    """
    if cpf or nis:
        params: dict[str, Any] = {"mesAno": mes_ano, "pagina": pagina}
        if cpf:
            params["cpf"] = _clean_cpf_cnpj(cpf)
        if nis:
            params["nis"] = nis
        data = await _get(SEGURO_DEFESO_CODIGO_URL, params)
    else:
        params = {"mesAno": mes_ano, "pagina": pagina}
        if codigo_ibge:
            params["codigoIbge"] = codigo_ibge
        data = await _get(SEGURO_DEFESO_MUNICIPIO_URL, params)
    return _safe_parse_list(data, _parse_beneficio_municipio, "seguro-defeso", cls=SeguroDefeso)


async def consultar_garantia_safra(
    mes_ano: str,
    codigo_ibge: str | None = None,
    cpf: str | None = None,
    nis: str | None = None,
    pagina: int = 1,
) -> list[GarantiaSafra]:
    """Consulta garantia-safra (agricultura familiar).

    Args:
        mes_ano: Mês/ano de referência (AAAAMM).
        codigo_ibge: Código IBGE do município.
        cpf: CPF do beneficiário.
        nis: NIS do beneficiário.
        pagina: Número da página.
    """
    if cpf or nis:
        params: dict[str, Any] = {"mesAno": mes_ano, "pagina": pagina}
        if cpf:
            params["cpf"] = _clean_cpf_cnpj(cpf)
        if nis:
            params["nis"] = nis
        data = await _get(SAFRA_CODIGO_URL, params)
    else:
        params = {"mesAno": mes_ano, "pagina": pagina}
        if codigo_ibge:
            params["codigoIbge"] = codigo_ibge
        data = await _get(SAFRA_MUNICIPIO_URL, params)
    return _safe_parse_list(data, _parse_beneficio_municipio, "garantia-safra", cls=GarantiaSafra)


async def consultar_peti(
    mes_ano: str,
    codigo_ibge: str | None = None,
    cpf: str | None = None,
    nis: str | None = None,
    pagina: int = 1,
) -> list[PetiBeneficio]:
    """Consulta PETI (Erradicação do Trabalho Infantil).

    Args:
        mes_ano: Mês/ano de referência (AAAAMM).
        codigo_ibge: Código IBGE do município.
        cpf: CPF do beneficiário.
        nis: NIS do beneficiário.
        pagina: Número da página.
    """
    if cpf or nis:
        params: dict[str, Any] = {"mesAno": mes_ano, "pagina": pagina}
        if cpf:
            params["cpf"] = _clean_cpf_cnpj(cpf)
        if nis:
            params["nis"] = nis
        data = await _get(PETI_CODIGO_URL, params)
    else:
        params = {"mesAno": mes_ano, "pagina": pagina}
        if codigo_ibge:
            params["codigoIbge"] = codigo_ibge
        data = await _get(PETI_MUNICIPIO_URL, params)
    return _safe_parse_list(data, _parse_beneficio_municipio, "peti", cls=PetiBeneficio)


async def detalhar_licitacao(id_licitacao: int) -> LicitacaoDetalhe | None:
    """Busca detalhe de uma licitação por ID.

    Args:
        id_licitacao: ID da licitação.
    """
    url = f"{LICITACOES_URL}/{id_licitacao}"
    data = await _get(url)
    if isinstance(data, dict):
        return _parse_licitacao_detalhe(data)
    return None


async def buscar_licitacao_por_processo(
    numero_processo: str,
    pagina: int = 1,
) -> list[Licitacao]:
    """Busca licitações por número de processo.

    Args:
        numero_processo: Número do processo.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"numeroProcesso": numero_processo, "pagina": pagina}
    data = await _get(LICITACOES_POR_PROCESSO_URL, params)
    return _safe_parse_list(data, _parse_licitacao, "licitacoes-processo")


async def buscar_licitacao_por_ug(
    codigo_ug: str,
    modalidade: str,
    numero: str,
    pagina: int = 1,
) -> list[Licitacao]:
    """Busca licitações por UG, modalidade e número.

    Args:
        codigo_ug: Código da unidade gestora.
        modalidade: Código da modalidade.
        numero: Número da licitação.
        pagina: Número da página.
    """
    params: dict[str, Any] = {
        "codigoUG": codigo_ug,
        "modalidade": modalidade,
        "numero": numero,
        "pagina": pagina,
    }
    data = await _get(LICITACOES_POR_UG_URL, params)
    return _safe_parse_list(data, _parse_licitacao, "licitacoes-ug")


async def buscar_participantes_licitacao(
    id_licitacao: int,
    pagina: int = 1,
) -> list[ParticipanteLicitacao]:
    """Busca participantes de uma licitação.

    Args:
        id_licitacao: ID da licitação.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"idLicitacao": id_licitacao, "pagina": pagina}
    data = await _get(LICITACOES_PARTICIPANTES_URL, params)
    return _safe_parse_list(data, _parse_participante, "participantes-licitacao")


async def listar_modalidades_licitacao() -> list[dict[str, Any]]:
    """Lista modalidades de licitação disponíveis."""
    data = await _get(LICITACOES_MODALIDADES_URL)
    if isinstance(data, list):
        return [item if isinstance(item, dict) else {"valor": item} for item in data]
    return []


async def buscar_itens_licitados(
    id_licitacao: int,
    pagina: int = 1,
) -> list[ItemLicitado]:
    """Busca itens de uma licitação.

    Args:
        id_licitacao: ID da licitação.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"idLicitacao": id_licitacao, "pagina": pagina}
    data = await _get(LICITACOES_ITENS_URL, params)
    return _safe_parse_list(data, _parse_item_licitado, "itens-licitados")


async def buscar_empenhos_licitacao(
    id_licitacao: int,
    pagina: int = 1,
) -> list[DocumentoDespesa]:
    """Busca empenhos de uma licitação.

    Args:
        id_licitacao: ID da licitação.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"idLicitacao": id_licitacao, "pagina": pagina}
    data = await _get(LICITACOES_EMPENHOS_URL, params)
    return _safe_parse_list(data, _parse_documento_despesa, "empenhos-licitacao")


async def buscar_contratos_licitacao(
    id_licitacao: int,
    pagina: int = 1,
) -> list[ContratoGeral]:
    """Busca contratos relacionados a uma licitação.

    Args:
        id_licitacao: ID da licitação.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"idLicitacao": id_licitacao, "pagina": pagina}
    data = await _get(LICITACOES_CONTRATOS_URL, params)
    return _safe_parse_list(data, _parse_contrato_geral, "contratos-licitacao")


async def buscar_unidades_gestoras(
    codigo_orgao: str | None = None,
    pagina: int = 1,
) -> list[UnidadeGestora]:
    """Busca unidades gestoras de licitações.

    Args:
        codigo_orgao: Código do órgão (opcional).
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    data = await _get(LICITACOES_UGS_URL, params)
    return _safe_parse_list(data, _parse_unidade_gestora, "ugs")


async def buscar_documentos_emenda(
    codigo_emenda: str,
) -> list[DocumentoEmenda]:
    """Busca documentos relacionados a uma emenda parlamentar.

    Args:
        codigo_emenda: Código da emenda.
    """
    url = f"{EMENDAS_DOCUMENTOS_URL}/{codigo_emenda}"
    data = await _get(url)
    return _safe_parse_list(data, _parse_documento_emenda, "documentos-emenda")


async def consultar_despesas_orgao(
    codigo_orgao: str,
    ano: int | None = None,
    pagina: int = 1,
) -> list[DespesaOrgao]:
    """Consulta despesas por órgão.

    Args:
        codigo_orgao: Código do órgão.
        ano: Ano de referência.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"codigoOrgao": codigo_orgao, "pagina": pagina}
    if ano:
        params["ano"] = ano
    data = await _get(DESPESAS_ORGAO_URL, params)
    return _safe_parse_list(data, _parse_despesa_orgao, "despesas-orgao")


async def consultar_despesas_funcional(
    ano: int,
    codigo_funcao: str | None = None,
    codigo_orgao: str | None = None,
    pagina: int = 1,
) -> list[DespesaFuncional]:
    """Consulta despesas por classificação funcional-programática.

    Args:
        ano: Ano de referência.
        codigo_funcao: Código da função.
        codigo_orgao: Código do órgão.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"ano": ano, "pagina": pagina}
    if codigo_funcao:
        params["codigoFuncao"] = codigo_funcao
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    data = await _get(DESPESAS_FUNCIONAL_URL, params)
    return _safe_parse_list(data, _parse_despesa_funcional, "despesas-funcional")


async def buscar_documentos_despesa(
    codigo_orgao: str | None = None,
    ano: int | None = None,
    codigo_favorecido: str | None = None,
    pagina: int = 1,
) -> list[DocumentoDespesa]:
    """Busca documentos de despesa (empenhos, liquidações, pagamentos).

    Args:
        codigo_orgao: Código do órgão.
        ano: Ano de referência.
        codigo_favorecido: CPF/CNPJ do favorecido.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    if ano:
        params["ano"] = ano
    url = DESPESAS_DOCUMENTOS_URL
    if codigo_favorecido:
        params["codigoFavorecido"] = _clean_cpf_cnpj(codigo_favorecido)
        url = DESPESAS_DOCUMENTOS_FAVORECIDO_URL
    data = await _get(url, params)
    return _safe_parse_list(data, _parse_documento_despesa, "documentos-despesa")


async def buscar_itens_empenho(
    codigo_documento: str,
    pagina: int = 1,
) -> list[ItemEmpenho]:
    """Busca itens de um empenho.

    Args:
        codigo_documento: Código do documento de empenho.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"codigoDocumento": codigo_documento, "pagina": pagina}
    data = await _get(DESPESAS_ITENS_EMPENHO_URL, params)
    return _safe_parse_list(data, _parse_item_empenho, "itens-empenho")


async def detalhar_convenio(id_convenio: int) -> ConvenioDetalhe | None:
    """Busca detalhe de um convênio por ID.

    Args:
        id_convenio: ID do convênio.
    """
    params: dict[str, Any] = {"id": id_convenio}
    data = await _get(CONVENIO_ID_URL, params)
    if isinstance(data, dict):
        return _parse_convenio_detalhe(data)
    if isinstance(data, list) and data:
        return _parse_convenio_detalhe(data[0])
    return None


async def buscar_convenio_numero(
    numero: str,
) -> list[Convenio]:
    """Busca convênio por número.

    Args:
        numero: Número do convênio.
    """
    data = await _get(CONVENIO_NUMERO_URL, {"numero": numero})
    return _safe_parse_list(data, _parse_convenio, "convenio-numero")


async def buscar_contratos_geral(
    codigo_orgao: str | None = None,
    data_inicial: str | None = None,
    data_final: str | None = None,
    pagina: int = 1,
) -> list[ContratoGeral]:
    """Busca geral de contratos federais.

    Args:
        codigo_orgao: Código do órgão.
        data_inicial: Data inicial (DD/MM/AAAA).
        data_final: Data final (DD/MM/AAAA).
        pagina: Número da página.
    """
    params: dict[str, Any] = {"pagina": pagina}
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    if data_inicial:
        params["dataInicial"] = data_inicial
    if data_final:
        params["dataFinal"] = data_final
    data = await _get(CONTRATOS_GERAL_URL, params)
    return _safe_parse_list(data, _parse_contrato_geral, "contratos-geral")


async def buscar_contrato_numero(
    numero: str,
) -> list[ContratoGeral]:
    """Busca contrato por número.

    Args:
        numero: Número do contrato.
    """
    data = await _get(CONTRATO_NUMERO_URL, {"numero": numero})
    return _safe_parse_list(data, _parse_contrato_geral, "contrato-numero")


async def buscar_termos_aditivos(
    id_contrato: int,
    pagina: int = 1,
) -> list[TermoAditivo]:
    """Busca termos aditivos de um contrato.

    Args:
        id_contrato: ID do contrato.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"idContrato": id_contrato, "pagina": pagina}
    data = await _get(CONTRATO_TERMOS_URL, params)
    return _safe_parse_list(data, _parse_termo_aditivo, "termos-aditivos")


async def buscar_itens_contratados(
    id_contrato: int,
    pagina: int = 1,
) -> list[ItemContratado]:
    """Busca itens de um contrato.

    Args:
        id_contrato: ID do contrato.
        pagina: Número da página.
    """
    params: dict[str, Any] = {"idContrato": id_contrato, "pagina": pagina}
    data = await _get(CONTRATO_ITENS_URL, params)
    return _safe_parse_list(data, _parse_item_contratado, "itens-contratados")


async def detalhar_sancao(
    base: str,
    id_sancao: int,
) -> SancaoDetalhe | None:
    """Busca detalhe de uma sanção por base e ID.

    Args:
        base: Base de sanções (ceis, cnep, cepim ou ceaf).
        id_sancao: ID da sanção.
    """
    db = SANCOES_DATABASES.get(base.lower())
    if not db:
        return None
    url = f"{db['url']}/{id_sancao}"
    data = await _get(url)
    if isinstance(data, dict):
        return _parse_sancao_detalhe(data, db["nome"])
    return None


async def buscar_nota_fiscal_chave(
    chave: str,
) -> NotaFiscal | None:
    """Busca nota fiscal eletrônica por chave de acesso.

    Args:
        chave: Chave de acesso da nota fiscal.
    """
    data = await _get(NOTA_FISCAL_CHAVE_URL, {"chave": chave})
    if isinstance(data, dict):
        return _parse_nota_fiscal(data)
    return None
