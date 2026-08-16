"""Pydantic models for Portal da Transparência API responses."""

from __future__ import annotations

from pydantic import BaseModel


class ContratoFornecedor(BaseModel):
    """Contrato federal por CPF/CNPJ do fornecedor."""

    id: int | None = None
    numero: str | None = None
    objeto: str | None = None
    valor_inicial: float | None = None
    valor_final: float | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    orgao: str | None = None
    fornecedor: str | None = None


class RecursoRecebido(BaseModel):
    """Recurso recebido (despesa) por favorecido."""

    ano: int | None = None
    mes: int | None = None
    valor: float | None = None
    favorecido_nome: str | None = None
    orgao_nome: str | None = None
    uf: str | None = None


class Servidor(BaseModel):
    """Servidor público federal."""

    id: int | None = None
    cpf: str | None = None
    nome: str | None = None
    tipo_servidor: str | None = None
    situacao: str | None = None
    orgao: str | None = None


class Licitacao(BaseModel):
    """Licitação federal."""

    id: int | None = None
    numero: str | None = None
    objeto: str | None = None
    modalidade: str | None = None
    situacao: str | None = None
    valor_estimado: float | None = None
    data_abertura: str | None = None
    orgao: str | None = None


class BolsaFamiliaMunicipio(BaseModel):
    """Dados do Novo Bolsa Família por município."""

    municipio: str | None = None
    uf: str | None = None
    quantidade: int | None = None
    valor: float | None = None
    data_referencia: str | None = None


class BolsaFamiliaSacado(BaseModel):
    """Dados do Novo Bolsa Família por NIS do sacado."""

    nis: str | None = None
    nome: str | None = None
    municipio: str | None = None
    uf: str | None = None
    valor: float | None = None


class Sancao(BaseModel):
    """Sanção de pessoa física ou jurídica."""

    fonte: str | None = None
    tipo: str | None = None
    nome: str | None = None
    cpf_cnpj: str | None = None
    orgao: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    fundamentacao: str | None = None


class Emenda(BaseModel):
    """Emenda parlamentar."""

    numero: str | None = None
    autor: str | None = None
    tipo: str | None = None
    localidade: str | None = None
    valor_empenhado: float | None = None
    valor_pago: float | None = None
    ano: int | None = None


class Viagem(BaseModel):
    """Viagem a serviço de servidor federal."""

    id: int | None = None
    cpf: str | None = None
    nome: str | None = None
    cargo: str | None = None
    orgao: str | None = None
    destino: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    valor_passagens: float | None = None
    valor_diarias: float | None = None


class Convenio(BaseModel):
    """Convênio ou transferência voluntária."""

    numero: str | None = None
    objeto: str | None = None
    situacao: str | None = None
    valor_convenio: float | None = None
    valor_liberado: float | None = None
    orgao: str | None = None
    convenente: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None


class CartaoPagamento(BaseModel):
    """Pagamento com cartão corporativo / suprimento de fundos."""

    portador: str | None = None
    cpf: str | None = None
    orgao: str | None = None
    valor: float | None = None
    data: str | None = None
    tipo: str | None = None
    estabelecimento: str | None = None


class PessoaExpostaPoliticamente(BaseModel):
    """Pessoa Exposta Politicamente (PEP)."""

    cpf: str | None = None
    nome: str | None = None
    orgao: str | None = None
    funcao: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None


class AcordoLeniencia(BaseModel):
    """Acordo de leniência (anticorrupção)."""

    empresa: str | None = None
    cnpj: str | None = None
    orgao: str | None = None
    situacao: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    valor: float | None = None


class NotaFiscal(BaseModel):
    """Nota fiscal eletrônica."""

    numero: str | None = None
    serie: str | None = None
    emitente: str | None = None
    cnpj_emitente: str | None = None
    valor: float | None = None
    data_emissao: str | None = None


class BeneficioSocial(BaseModel):
    """Benefício social (BPC, seguro-desemprego, etc.)."""

    tipo: str | None = None
    nome_beneficiario: str | None = None
    cpf: str | None = None
    nis: str | None = None
    valor: float | None = None
    mes_referencia: str | None = None
    municipio: str | None = None
    uf: str | None = None


class PessoaFisicaVinculos(BaseModel):
    """Vínculos e benefícios de pessoa física por CPF."""

    cpf: str | None = None
    nome: str | None = None
    tipo_vinculo: str | None = None
    orgao: str | None = None
    beneficios: str | None = None


class PessoaJuridicaVinculos(BaseModel):
    """Sanções e contratos de pessoa jurídica por CNPJ."""

    cnpj: str | None = None
    razao_social: str | None = None
    sancoes: str | None = None
    contratos: str | None = None


class ContratoDetalhe(BaseModel):
    """Detalhe completo de um contrato federal."""

    id: int | None = None
    numero: str | None = None
    objeto: str | None = None
    valor_inicial: float | None = None
    valor_final: float | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    orgao: str | None = None
    fornecedor: str | None = None
    modalidade: str | None = None
    situacao: str | None = None
    licitacao: str | None = None


class ServidorDetalhe(BaseModel):
    """Detalhe completo de servidor com remuneração."""

    id: int | None = None
    cpf: str | None = None
    nome: str | None = None
    tipo_servidor: str | None = None
    situacao: str | None = None
    orgao: str | None = None
    cargo: str | None = None
    funcao: str | None = None
    remuneracao_basica: float | None = None
    remuneracao_apos_deducoes: float | None = None
    honorarios: float | None = None
    outras_remuneracoes: float | None = None
    jetons: float | None = None


# --- Novos schemas (port completo da API) ---


class ImovelFuncional(BaseModel):
    """Imóvel funcional da União."""

    id: int | None = None
    endereco: str | None = None
    cep: str | None = None
    regiao: str | None = None
    situacao: str | None = None
    orgao_responsavel: str | None = None
    data_referencia: str | None = None


class Permissionario(BaseModel):
    """Ocupante/permissionário de imóvel funcional."""

    cpf: str | None = None
    nome: str | None = None
    orgao: str | None = None
    orgao_permissionario: str | None = None
    cargo: str | None = None
    valor_pago_mes: float | None = None
    data_inicio: str | None = None


class RenunciaFiscal(BaseModel):
    """Renúncia de receita fiscal."""

    cnpj: str | None = None
    razao_social: str | None = None
    tipo_renuncia: str | None = None
    beneficio_fiscal: str | None = None
    tributo: str | None = None
    uf: str | None = None
    valor: float | None = None
    ano: int | None = None


class EmpresaBeneficioFiscal(BaseModel):
    """Empresa habilitada a benefício fiscal ou imune/isenta."""

    cnpj: str | None = None
    razao_social: str | None = None
    nome_fantasia: str | None = None
    beneficio_fiscal: str | None = None
    fruicao_vigente: str | None = None
    uf: str | None = None


class Orgao(BaseModel):
    """Órgão do governo federal (SIAPE ou SIAFI)."""

    codigo: str | None = None
    descricao: str | None = None


class CoronavirusTransferencia(BaseModel):
    """Transferência emergencial COVID-19."""

    tipo: str | None = None
    orgao: str | None = None
    favorecido: str | None = None
    valor: float | None = None
    acao: str | None = None
    grupo_despesa: str | None = None


class CoronavirusDespesa(BaseModel):
    """Despesa pública COVID-19."""

    funcao: str | None = None
    acao: str | None = None
    programa: str | None = None
    grupo_despesa: str | None = None
    empenhado: float | None = None
    liquidado: float | None = None
    pago: float | None = None


class RemuneracaoServidor(BaseModel):
    """Remuneração de servidor público federal."""

    id: int | None = None
    cpf: str | None = None
    nome: str | None = None
    orgao: str | None = None
    remuneracao_basica: float | None = None
    remuneracao_apos_deducoes: float | None = None


class ServidorAgregado(BaseModel):
    """Servidores agregados por órgão."""

    orgao_codigo: str | None = None
    orgao_nome: str | None = None
    quantidade: int | None = None


class FuncaoCargo(BaseModel):
    """Função ou cargo de confiança."""

    id: int | None = None
    nome: str | None = None
    nivel: str | None = None
    orgao: str | None = None
    tipo: str | None = None


class SeguroDefeso(BaseModel):
    """Seguro-defeso (pescador artesanal)."""

    nis: str | None = None
    nome: str | None = None
    municipio: str | None = None
    uf: str | None = None
    valor: float | None = None
    quantidade: int | None = None
    data_referencia: str | None = None


class GarantiaSafra(BaseModel):
    """Garantia-safra (agricultura familiar)."""

    nis: str | None = None
    nome: str | None = None
    municipio: str | None = None
    uf: str | None = None
    valor: float | None = None
    quantidade: int | None = None
    data_referencia: str | None = None


class PetiBeneficio(BaseModel):
    """PETI — Programa de Erradicação do Trabalho Infantil."""

    nis: str | None = None
    nome: str | None = None
    municipio: str | None = None
    uf: str | None = None
    valor: float | None = None
    quantidade: int | None = None
    data_referencia: str | None = None


class LicitacaoDetalhe(BaseModel):
    """Detalhe completo de licitação."""

    id: int | None = None
    numero: str | None = None
    objeto: str | None = None
    modalidade: str | None = None
    situacao: str | None = None
    valor_estimado: float | None = None
    data_abertura: str | None = None
    orgao: str | None = None
    processo: str | None = None
    fornecedor_vencedor: str | None = None


class ParticipanteLicitacao(BaseModel):
    """Participante de processo licitatório."""

    cpf_cnpj: str | None = None
    nome: str | None = None
    situacao: str | None = None
    valor_proposta: float | None = None


class ItemLicitado(BaseModel):
    """Item de licitação."""

    descricao: str | None = None
    quantidade: int | None = None
    valor_estimado: float | None = None
    valor_homologado: float | None = None
    fornecedor: str | None = None


class DocumentoEmenda(BaseModel):
    """Documento relacionado a emenda parlamentar."""

    codigo: str | None = None
    tipo: str | None = None
    descricao: str | None = None
    valor: float | None = None
    data: str | None = None


class DespesaOrgao(BaseModel):
    """Despesa por órgão."""

    orgao_codigo: str | None = None
    orgao_nome: str | None = None
    empenhado: float | None = None
    liquidado: float | None = None
    pago: float | None = None
    ano: int | None = None
    mes: int | None = None


class DespesaFuncional(BaseModel):
    """Despesa por classificação funcional-programática."""

    funcao: str | None = None
    subfuncao: str | None = None
    programa: str | None = None
    acao: str | None = None
    empenhado: float | None = None
    liquidado: float | None = None
    pago: float | None = None


class DocumentoDespesa(BaseModel):
    """Documento de despesa (empenho, liquidação, pagamento)."""

    codigo: str | None = None
    tipo: str | None = None
    data: str | None = None
    valor: float | None = None
    favorecido: str | None = None
    orgao: str | None = None


class ItemEmpenho(BaseModel):
    """Item de empenho de despesa."""

    descricao: str | None = None
    quantidade: int | None = None
    valor_unitario: float | None = None
    valor_total: float | None = None


class ConvenioDetalhe(BaseModel):
    """Detalhe completo de convênio."""

    id: int | None = None
    numero: str | None = None
    objeto: str | None = None
    situacao: str | None = None
    valor_convenio: float | None = None
    valor_liberado: float | None = None
    valor_contrapartida: float | None = None
    orgao: str | None = None
    convenente: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    tipo_instrumento: str | None = None


class ContratoGeral(BaseModel):
    """Contrato federal (busca geral)."""

    id: int | None = None
    numero: str | None = None
    objeto: str | None = None
    valor_inicial: float | None = None
    valor_final: float | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    orgao: str | None = None
    fornecedor: str | None = None
    modalidade: str | None = None
    situacao: str | None = None


class TermoAditivo(BaseModel):
    """Termo aditivo de contrato."""

    numero: str | None = None
    objeto: str | None = None
    data: str | None = None
    valor: float | None = None


class ItemContratado(BaseModel):
    """Item contratado."""

    descricao: str | None = None
    quantidade: int | None = None
    valor_unitario: float | None = None
    valor_total: float | None = None


class SancaoDetalhe(BaseModel):
    """Detalhe completo de sanção por ID."""

    id: int | None = None
    fonte: str | None = None
    tipo: str | None = None
    nome: str | None = None
    cpf_cnpj: str | None = None
    orgao: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    fundamentacao: str | None = None
    processo: str | None = None
    valor_multa: float | None = None


class UnidadeGestora(BaseModel):
    """Unidade gestora de licitações/contratos."""

    codigo: str | None = None
    nome: str | None = None
    orgao_vinculado: str | None = None
    municipio: str | None = None
    uf: str | None = None
