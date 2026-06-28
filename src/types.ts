export interface Proposta {
  ano: number;
  numero: number;
}

export interface PoConfig {
  indSubmetaViaAPI: boolean;
  duracaoObra: number;
  dataBase: string;
  localidade: string;
  indDesonerado: boolean;
  previsaoInicioObra: string;
  indAcompanhamentoEventos: boolean;
  indReceberPO_CFFviaAPI: boolean;
}

export interface Submeta {
  numero: number;
  descricao: string;
  numLote: number;
  valorRepasse: number;
  valorContrapartida: number;
  valorOutros: number;
  regimeExecucaoObra: string;
  po: PoConfig;
}

export interface Meta {
  numero: number;
  descricao: string;
  submetas: Submeta[];
}

export interface QciResponse {
  proposta: Proposta;
  sistemaOrigem: string;
  qci: {
    metas: Meta[];
  };
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  id: string;
  timestamp: string;
}

export interface FrenteDeObra {
  numero: number;
  nomeFrenteObra: string;
  quantidadeItens: number;
  numeroMesConclusao?: number;
}

export interface Evento {
  numeroEvento: number;
  titulo: string;
}

export interface Parcela {
  numeroParcela: number;
  percentualParcela: number;
}

export interface Servico {
  numeroServico: number;
  fonte: "Composição" | "Cotação" | "SINAPI" | "Outros";
  codigo: string;
  descricao: string;
  unidade: string;
  custoUnitarioReferencia: number;
  custoUnitario: number;
  bdi: number;
  observacao: string;
  evento?: Evento;
  frentesDeObra: FrenteDeObra[];
  parcelas?: Parcela[];
}

export interface Macroservico {
  numeroMacroservico: number;
  descricao: string;
  servicos: Servico[];
}

export interface PlanilhaOrcamentariaPayload {
  macroservicos: Macroservico[];
}
