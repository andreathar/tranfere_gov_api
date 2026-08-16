"""Constants for the Transparência feature."""

# Pagination
DEFAULT_PAGE_SIZE = 15

# API base URL
TRANSPARENCIA_API_BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"

# Auth
AUTH_HEADER_NAME = "chave-api-dados"
AUTH_ENV_VAR = "TRANSPARENCIA_API_KEY"

# Endpoints
CONTRATOS_URL = f"{TRANSPARENCIA_API_BASE}/contratos/cpf-cnpj"
DESPESAS_URL = f"{TRANSPARENCIA_API_BASE}/despesas/recursos-recebidos"
SERVIDORES_URL = f"{TRANSPARENCIA_API_BASE}/servidores"
LICITACOES_URL = f"{TRANSPARENCIA_API_BASE}/licitacoes"
BOLSA_FAMILIA_MUNICIPIO_URL = f"{TRANSPARENCIA_API_BASE}/novo-bolsa-familia-por-municipio"
BOLSA_FAMILIA_NIS_URL = f"{TRANSPARENCIA_API_BASE}/novo-bolsa-familia-sacado-por-nis"
EMENDAS_URL = f"{TRANSPARENCIA_API_BASE}/emendas"
VIAGENS_URL = f"{TRANSPARENCIA_API_BASE}/viagens-por-cpf"
CONVENIOS_URL = f"{TRANSPARENCIA_API_BASE}/convenios"
CARTOES_URL = f"{TRANSPARENCIA_API_BASE}/cartoes"
PEP_URL = f"{TRANSPARENCIA_API_BASE}/peps"
ACORDOS_LENIENCIA_URL = f"{TRANSPARENCIA_API_BASE}/acordos-leniencia"
NOTAS_FISCAIS_URL = f"{TRANSPARENCIA_API_BASE}/notas-fiscais"
BENEFICIOS_CIDADAO_URL = f"{TRANSPARENCIA_API_BASE}/beneficios-cidadao"
PESSOAS_FISICAS_URL = f"{TRANSPARENCIA_API_BASE}/pessoas-fisicas"
PESSOAS_JURIDICAS_URL = f"{TRANSPARENCIA_API_BASE}/pessoas-juridicas"
CONTRATO_DETALHE_URL = f"{TRANSPARENCIA_API_BASE}/contratos/id"
SERVIDOR_DETALHE_URL = f"{TRANSPARENCIA_API_BASE}/servidores"

# --- Novos endpoints (port completo da API) ---

# Imóveis funcionais
IMOVEIS_URL = f"{TRANSPARENCIA_API_BASE}/imoveis"
SITUACAO_IMOVEL_URL = f"{TRANSPARENCIA_API_BASE}/situacao-imovel"
PERMISSIONARIOS_URL = f"{TRANSPARENCIA_API_BASE}/permissionarios"

# Renúncias fiscais
RENUNCIAS_VALOR_URL = f"{TRANSPARENCIA_API_BASE}/renuncias-valor"
RENUNCIAS_IMUNES_URL = f"{TRANSPARENCIA_API_BASE}/renuncias-fiscais-empresas-imunes-isentas"
RENUNCIAS_HABILITADAS_URL = (
    f"{TRANSPARENCIA_API_BASE}/renuncias-fiscais-empresas-habilitadas-beneficios-fiscais"
)

# Órgãos
ORGAOS_SIAPE_URL = f"{TRANSPARENCIA_API_BASE}/orgaos-siape"
ORGAOS_SIAFI_URL = f"{TRANSPARENCIA_API_BASE}/orgaos-siafi"

# Coronavírus
CORONAVIRUS_TRANSFERENCIAS_URL = f"{TRANSPARENCIA_API_BASE}/coronavirus/transferencias"
CORONAVIRUS_DESPESAS_URL = f"{TRANSPARENCIA_API_BASE}/coronavirus/movimento-liquido-despesa"

# Viagens (endpoints adicionais)
VIAGENS_ORGAO_URL = f"{TRANSPARENCIA_API_BASE}/viagens"

# Servidores (sub-endpoints)
SERVIDORES_REMUNERACAO_URL = f"{TRANSPARENCIA_API_BASE}/servidores/remuneracao"
SERVIDORES_POR_ORGAO_URL = f"{TRANSPARENCIA_API_BASE}/servidores/por-orgao"
SERVIDORES_FUNCOES_URL = f"{TRANSPARENCIA_API_BASE}/servidores/funcoes-e-cargos"

# Benefícios (endpoints específicos)
SEGURO_DEFESO_MUNICIPIO_URL = f"{TRANSPARENCIA_API_BASE}/seguro-defeso-por-municipio"
SEGURO_DEFESO_CODIGO_URL = f"{TRANSPARENCIA_API_BASE}/seguro-defeso-codigo"
SAFRA_MUNICIPIO_URL = f"{TRANSPARENCIA_API_BASE}/safra-por-municipio"
SAFRA_CODIGO_URL = f"{TRANSPARENCIA_API_BASE}/safra-codigo-por-cpf-ou-nis"
PETI_MUNICIPIO_URL = f"{TRANSPARENCIA_API_BASE}/peti-por-municipio"
PETI_CODIGO_URL = f"{TRANSPARENCIA_API_BASE}/peti-por-cpf-ou-nis"
BOLSA_FAMILIA_BENEFICIARIO_URL = (
    f"{TRANSPARENCIA_API_BASE}/novo-bolsa-familia-sacado-beneficiario-por-municipio"
)

# Licitações (sub-endpoints)
LICITACOES_UGS_URL = f"{TRANSPARENCIA_API_BASE}/licitacoes/ugs"
LICITACOES_POR_PROCESSO_URL = f"{TRANSPARENCIA_API_BASE}/licitacoes/por-processo"
LICITACOES_POR_UG_URL = f"{TRANSPARENCIA_API_BASE}/licitacoes/por-ug-modalidade-numero"
LICITACOES_PARTICIPANTES_URL = f"{TRANSPARENCIA_API_BASE}/licitacoes/participantes"
LICITACOES_MODALIDADES_URL = f"{TRANSPARENCIA_API_BASE}/licitacoes/modalidades"
LICITACOES_ITENS_URL = f"{TRANSPARENCIA_API_BASE}/licitacoes/itens-licitados"
LICITACOES_EMPENHOS_URL = f"{TRANSPARENCIA_API_BASE}/licitacoes/empenhos"
LICITACOES_CONTRATOS_URL = f"{TRANSPARENCIA_API_BASE}/licitacoes/contratos-relacionados-licitacao"

# Emendas (sub-endpoints)
EMENDAS_DOCUMENTOS_URL = f"{TRANSPARENCIA_API_BASE}/emendas/documentos"

# Despesas (sub-endpoints)
DESPESAS_ORGAO_URL = f"{TRANSPARENCIA_API_BASE}/despesas/por-orgao"
DESPESAS_FUNCIONAL_URL = f"{TRANSPARENCIA_API_BASE}/despesas/por-funcional-programatica"
DESPESAS_FUNCIONAL_MOV_URL = (
    f"{TRANSPARENCIA_API_BASE}/despesas/por-funcional-programatica/movimentacao-liquida"
)
DESPESAS_DOCUMENTOS_URL = f"{TRANSPARENCIA_API_BASE}/despesas/documentos"
DESPESAS_DOCUMENTOS_FAVORECIDO_URL = f"{TRANSPARENCIA_API_BASE}/despesas/documentos-por-favorecido"
DESPESAS_ITENS_EMPENHO_URL = f"{TRANSPARENCIA_API_BASE}/despesas/itens-de-empenho"
DESPESAS_TIPO_TRANSFERENCIA_URL = f"{TRANSPARENCIA_API_BASE}/despesas/tipo-transferencia"
DESPESAS_PLANO_ORC_URL = f"{TRANSPARENCIA_API_BASE}/despesas/plano-orcamentario"
DESPESAS_FAVORECIDOS_DOC_URL = (
    f"{TRANSPARENCIA_API_BASE}/despesas/favorecidos-finais-por-documento"
)

# Convênios (sub-endpoints)
CONVENIO_ID_URL = f"{TRANSPARENCIA_API_BASE}/convenios/id"
CONVENIO_NUMERO_URL = f"{TRANSPARENCIA_API_BASE}/convenios/numero"
CONVENIO_PROCESSO_URL = f"{TRANSPARENCIA_API_BASE}/convenios/numero-processo"
CONVENIO_TIPOS_URL = f"{TRANSPARENCIA_API_BASE}/convenios/tipo-instrumento"

# Contratos (sub-endpoints)
CONTRATOS_GERAL_URL = f"{TRANSPARENCIA_API_BASE}/contratos"
CONTRATO_NUMERO_URL = f"{TRANSPARENCIA_API_BASE}/contratos/numero"
CONTRATO_PROCESSO_URL = f"{TRANSPARENCIA_API_BASE}/contratos/processo"
CONTRATO_TERMOS_URL = f"{TRANSPARENCIA_API_BASE}/contratos/termo-aditivo"
CONTRATO_ITENS_URL = f"{TRANSPARENCIA_API_BASE}/contratos/itens-contratados"
CONTRATO_DOCS_URL = f"{TRANSPARENCIA_API_BASE}/contratos/documentos-relacionados"
CONTRATO_APOSTILAMENTO_URL = f"{TRANSPARENCIA_API_BASE}/contratos/apostilamento"

# Notas fiscais (sub-endpoint)
NOTA_FISCAL_CHAVE_URL = f"{TRANSPARENCIA_API_BASE}/notas-fiscais-por-chave"

# Sanções — cada base tem endpoint e nome de parâmetro diferentes
SANCOES_DATABASES: dict[str, dict[str, str]] = {
    "ceis": {
        "url": f"{TRANSPARENCIA_API_BASE}/ceis",
        "param_cpf_cnpj": "codigoSancionado",
        "param_nome": "nomeSancionado",
        "nome": "CEIS (Empresas Inidôneas e Suspensas)",
    },
    "cnep": {
        "url": f"{TRANSPARENCIA_API_BASE}/cnep",
        "param_cpf_cnpj": "codigoSancionado",
        "param_nome": "nomeSancionado",
        "nome": "CNEP (Empresas Punidas)",
    },
    "cepim": {
        "url": f"{TRANSPARENCIA_API_BASE}/cepim",
        "param_cpf_cnpj": "cnpjSancionado",
        "param_nome": "nomeSancionado",
        "nome": "CEPIM (Entidades Privadas sem Fins Lucrativos Impedidas)",
    },
    "ceaf": {
        "url": f"{TRANSPARENCIA_API_BASE}/ceaf",
        "param_cpf_cnpj": "cpfSancionado",
        "param_nome": "nomeSancionado",
        "nome": "CEAF (Expulsões da Administração Federal)",
    },
}
