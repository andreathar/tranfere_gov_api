import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const PORT = 3000;

// Initialize Gemini SDK safely
let ai: GoogleGenAI | null = null;
function getGemini(): GoogleGenAI {
  if (!ai) {
    const key = process.env.GEMINI_API_KEY;
    if (!key) {
      throw new Error("GEMINI_API_KEY environment variable is missing. Please add it via the Settings > Secrets menu.");
    }
    ai = new GoogleGenAI({
      apiKey: key,
      httpOptions: {
        headers: {
          "User-Agent": "aistudio-build",
        },
      },
    });
  }
  return ai;
}

async function startServer() {
  const app = express();
  app.use(express.json());

  // 1. Simulação do IDP Login (Obtenção do Token de Usuário)
  app.post("/api/simulate/login", (req, res) => {
    const { cpf, senha, env } = req.body;

    if (!cpf || !senha) {
      return res.status(400).json({
        errorMessage: "Os parâmetros 'cpf' e 'senha' são obrigatórios para a autenticação."
      });
    }

    // Validação simples de CPF (Apenas para simulação)
    const cleanCpf = cpf.replace(/\D/g, "");
    if (cleanCpf.length !== 11) {
      return res.status(401).json({
        errorMessage: "Erro de autenticação: CPF deve conter 11 dígitos."
      });
    }

    // Gera um JWT simulado
    const mockJwt = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c3VhcmlvIjoi${cleanCpf}IiwicGVyZmlsIjpbIk9wZXJhZG9yIEZpbmFuY2Vpcm8gZG8gQ29udmVuZW50ZSJdLCJjcmVhdGVkX2F0IjoxNzg4NzkzMjAwfQ.mockSignature_${env || "prod"}`;

    return res.json({
      token: mockJwt
    });
  });

  // 2. Simulação de Consulta de Submetas (GET)
  app.get("/api/simulate/projeto-basico/api/v1/po", (req, res) => {
    const epCad = req.headers["ep-cad"];
    const auth = req.headers["authorization"];
    const { nrproposta, anoproposta } = req.query;

    // Validação de Headers (Simulação conforme páginas 10-11 do manual)
    if (!epCad) {
      return res.status(401).json({
        errorMessage: "Acesso negado por falta de autenticação. Verifique se o parâmetro EP-CAD está configurado no head da solicitação."
      });
    }

    if (!auth || !auth.toString().startsWith("Bearer ")) {
      return res.status(401).json({
        errorMessage: "The token was expected to have 3 parts, but got 1. Falta fornecer o token de autenticação do usuário."
      });
    }

    if (!nrproposta || !anoproposta) {
      return res.status(400).json({
        errorMessage: "Número da Proposta e Ano da Proposta são numéricos e obrigatórios."
      });
    }

    // Simulação de Erro se a proposta for inválida (ex: 999)
    if (nrproposta === "999") {
      return res.status(400).json({
        errorMessage: `Não foi possível encontrar a Proposta ${nrproposta}/${anoproposta}.`
      });
    }

    // Se proposta for 123456, simula submeta desabilitada para API
    const isApiDisabled = nrproposta === "123456";

    // Retorno de Sucesso simulado (Baseado na página 7-8 do manual)
    return res.json({
      proposta: {
        ano: parseInt(anoproposta as string) || 2024,
        numero: parseInt(nrproposta as string) || 28206
      },
      sistemaOrigem: "Sistema externo de obras",
      qci: {
        metas: [
          {
            numero: 1,
            descricao: "Reforma da sede da 2ª Companhia do 41º BPM/I.",
            submetas: [
              {
                numero: 1,
                descricao: "SERVIÇOS PRELIMINARES",
                numLote: 1,
                valorRepasse: 7740.18,
                valorContrapartida: 0.0,
                valorOutros: 0.0,
                regimeExecucaoObra: "EMPREITADA_PRECO_GLOBAL",
                po: {
                  indSubmetaViaAPI: isApiDisabled ? false : true,
                  duracaoObra: 6,
                  dataBase: "03/2019",
                  localidade: "SP",
                  indDesonerado: true,
                  previsaoInicioObra: "03/2019",
                  indAcompanhamentoEventos: true, // PLE por padrão
                  indReceberPO_CFFviaAPI: isApiDisabled ? false : true
                }
              }
            ]
          }
        ]
      }
    });
  });

  // 3. Simulação de ConsultarProposta (GET CSV)
  app.get("/api/simulate/voluntarias/proposta/ConsultarProposta/ConsultarProposta.do", (req, res) => {
    const autorDaEmenda = req.query.autorDaEmenda;
    
    // Simula uma resposta CSV
    const csvContent = `Proposta,Status,Órgão Concedente,Convenente,Emenda Parlamentar?,CNPJ do Convenente
023366/2026,Em execução,36000 - MINISTERIO DA SAUDE,SANTA CASA DE MISERICORDIA DE SANTA BARBARA DO OESTE,Sim,56.725.385/0001-09
021877/2026,Em execução,36000 - MINISTERIO DA SAUDE,SANTA CASA DE MISERICORDIA DE APARECIDA,Sim,43.667.179/0001-48
021076/2026,Em execução,36000 - MINISTERIO DA SAUDE,SANTA CASA DE MISERICORDIA DE SANTA BARBARA DO OESTE,Sim,56.725.385/0001-09
020438/2026,Em execução,36000 - MINISTERIO DA SAUDE,SANTA CASA DE MISERICORDIA DE VOTUPORANGA,Sim,72.957.814/0001-20
018284/2026,Em execução,36000 - MINISTERIO DA SAUDE,IRMANDADE SAO JOSE DE NOVO HORIZONTE,Sim,53.174.827/0001-88
018282/2026,Em execução,36000 - MINISTERIO DA SAUDE,SANTA CASA DE MISERICORDIA DE ITAPEVA,Sim,49.797.293/0001-79
009958/2026,Proposta/Plano de Trabalho Rejeitados por Impedimento técnico,44000 - MINISTERIO DO MEIO AMBIENTE,MUNICIPIO DE ITAQUAQUECETUBA,Sim,46.316.600/0001-64
009909/2026,Proposta/Plano de Trabalho Rejeitados por Impedimento técnico,44000 - MINISTERIO DO MEIO AMBIENTE,INSTITUTO EDUCA ECO,Não,32.421.253/0001-25
004152/2026,Proposta Aprovada e Plano de Trabalho em Análise,44000 - MINISTERIO DO MEIO AMBIENTE,MUNICIPIO DE IBITINGA,Sim,45.321.460/0001-50
003721/2026,Proposta/Plano de Trabalho Rejeitados por Impedimento técnico,44000 - MINISTERIO DO MEIO AMBIENTE,MUNICIPIO DE CAMPINA DO MONTE ALEGRE,Sim,67.360.404/0001-67
002695/2026,Proposta/Plano de Trabalho Aprovados,44000 - MINISTERIO DO MEIO AMBIENTE,ABRIGO PITUKINHA INSTITUTO DE AJUDA AOS ANIMAIS,Sim,11.893.084/0001-56
002299/2026,Proposta Aprovada e Plano de Trabalho em Análise,44000 - MINISTERIO DO MEIO AMBIENTE,MUNICIPIO DE ITAI,Sim,46.634.200/0001-05
`;
    res.setHeader('Content-Type', 'text/csv');
    res.status(200).send(csvContent);
  });

  // 4. Simulação de Envio de Planilha Orçamentária (POST)
  app.post("/api/simulate/projeto-basico/api/v1/po", (req, res) => {
    const epCad = req.headers["ep-cad"];
    const auth = req.headers["authorization"];
    const { nrproposta, anoproposta, nrmeta, nrsubmeta } = req.query;
    const payload = req.body;

    if (!epCad) {
      return res.status(401).json({
        errorMessage: "Acesso negado por falta de autenticação. Verifique se o parâmetro EP-CAD está configurado no head da solicitação."
      });
    }

    if (!auth || !auth.toString().startsWith("Bearer ")) {
      return res.status(401).json({
        errorMessage: "The token was expected to have 3 parts, but got 1. Falta fornecer o token de autenticação do usuário."
      });
    }

    if (!nrproposta || !anoproposta || !nrmeta || !nrsubmeta) {
      return res.status(400).json({
        errorMessage: "Número da Proposta, Ano da Proposta, Número da Meta e Número da Submeta são obrigatórios na URL."
      });
    }

    // Simula o erro da opção 'Receber via API?' estar desmarcada
    if (nrproposta === "123456") {
      return res.status(400).json({
        errorMessage: "Não é possível adicionar a Planilha Orçamentaria via API pois a opção Receber dados da 'PO/CFF via API?' não está selecionada na aba Dados Gerais da submeta no Transferegov.br."
      });
    }

    // Validação básica de payload
    if (!payload || !payload.macroservicos || !Array.isArray(payload.macroservicos)) {
      return res.status(400).json({
        errorMessage: "Informações enviadas não estão com estrutura adequada. Erros encontrados em: Objeto 'macroservicos' raiz está ausente ou inválido."
      });
    }

    // Validações internas (simulando regras de negócio do manual)
    for (let i = 0; i < payload.macroservicos.length; i++) {
      const ms = payload.macroservicos[i];
      if (!ms.numeroMacroservico || typeof ms.numeroMacroservico !== "number") {
        return res.status(400).json({
          errorMessage: `Informações enviadas não estão com estrutura adequada. Erro em macroservicos[${i}]: 'numeroMacroservico' deve ser numérico.`
        });
      }
      if (!ms.descricao) {
        return res.status(400).json({
          errorMessage: `Informações enviadas não estão com estrutura adequada. Erro em macroservicos[${i}]: 'descricao' é obrigatória.`
        });
      }
      if (!ms.servicos || !Array.isArray(ms.servicos)) {
        return res.status(400).json({
          errorMessage: `Informações enviadas não estão com estrutura adequada. Erro em macroservicos[${i}]: Array 'servicos' é obrigatório.`
        });
      }

      // Validação de Serviços
      for (let j = 0; j < ms.servicos.length; j++) {
        const s = ms.servicos[j];
        if (!s.numeroServico || s.numeroServico <= 0 || s.numeroServico > 999) {
          return res.status(400).json({
            errorMessage: `[macroservicos[${i}].servicos[${j}].numeroServico - O valor deve ser maior ou igual a 1 e menor ou igual a 999.`
          });
        }
        if (!s.fonte || !["Composição", "Cotação", "SINAPI", "Outros"].includes(s.fonte)) {
          return res.status(400).json({
            errorMessage: `Erro em macroservicos[${i}].servicos[${j}]: 'fonte' inválida. Domínios aceitos: Composição, Cotação, SINAPI, Outros.`
          });
        }
        if (!s.codigo || s.codigo.length > 13) {
          return res.status(400).json({
            errorMessage: `Erro em macroservicos[${i}].servicos[${j}]: 'codigo' é obrigatório e aceita no máximo 13 caracteres.`
          });
        }
        if (!s.descricao || s.descricao.length > 500) {
          return res.status(400).json({
            errorMessage: `Erro em macroservicos[${i}].servicos[${j}]: 'descricao' é obrigatória e aceita no máximo 500 caracteres.`
          });
        }

        // Se houver parcelas (formato BM), valida somatório que não pode ultrapassar 100%
        if (s.parcelas && Array.isArray(s.parcelas)) {
          let totalPct = 0;
          for (const p of s.parcelas) {
            totalPct += p.percentualParcela || 0;
          }
          if (totalPct > 100) {
            return res.status(400).json({
              errorMessage: "O somatório dos percentuais das parcelas de um macrosserviço/serviço tem que ser maior que zero e menor ou igual a 100."
            });
          }
        }
      }
    }

    // Sucesso 201 Created (Página 19)
    return res.status(201).json({
      proposta: `${nrproposta}/${anoproposta}`,
      submeta: `${nrmeta}.${nrsubmeta}`,
      mensagem: `A Planilha Orçamentária da Submeta ${nrmeta}.${nrsubmeta} da Proposta ${nrproposta}/${anoproposta} foi atualizada com sucesso via API do Projeto Básico.`
    });
  });

  // 4. Smart AI Advisor usando a API do Gemini
  app.post("/api/gemini/advisor", async (req, res) => {
    try {
      const { messages } = req.body;

      if (!messages || !Array.isArray(messages)) {
        return res.status(400).json({ error: "O parâmetro 'messages' é obrigatório e deve ser uma lista de mensagens." });
      }

      const gemini = getGemini();

      const systemInstruction = `
Você é o Assistente Virtual e Conselheiro de Integração da API Transferegov.br (focado no módulo Projeto Básico - Planilha Orçamentária de Obras, Versão 1.3). 
Seu objetivo é ajudar desenvolvedores e integradores de sistemas privados no Brasil a integrar com sucesso seus sistemas com as APIs de convênios do governo brasileiro.

Use as seguintes diretrizes para fornecer respostas precisas, claras, educadas e profissionais em PORTUGUÊS:

1. AUTENTICAÇÃO DUPLA (CRÍTICA):
   - A autenticação é composta por dois tokens JWT enviados em todas as chamadas principais:
     A) Token do Usuário: Enviado no cabeçalho 'Authorization: Bearer <token_jwt_usuario>'. Obtido via POST no serviço do IDP:
        - Homologação: https://hom4.idp.transferegov.sistema.gov.br/idp/jwt?usuario={{CPF_USUARIO}}&senha={{senha_USUARIO}}
        - Produção: https://idp.transferegov.sistema.gov.br/idp/jwt?usuario={{CPF_USUARIO}}&senha={{senha_USUARIO}}
        - Requisitos: O usuário do convênio (convenente) deve possuir um perfil válido: 'Operador Financeiro do Convenente', 'Gestor de Convênio do Convenente', ou 'Gestor Financeiro do Convenente'.
     B) Token do Sistema Externo: Enviado no cabeçalho 'EP-CAD: <token_jwt_sistema>'.
        - Este token identifica unicamente o sistema parceiro de obras e deve ser solicitado formalmente via ofício de habilitação direcionado ao Ministério da Gestão e da Inovação em Serviços Públicos.

2. AMBIENTES E URLs:
   - Homologação/Testes:
     - Consultar Submetas: GET https://hom4.mandatarias.transferegov.sistema.gov.br/projeto-basico/api/v1/po?nrproposta={{NR_PROPOSTA}}&anoproposta={{ANO_PROPOSTA}}
     - Enviar Planilha: POST https://hom4.mandatarias.transferegov.sistema.gov.br/projeto-basico/api/v1/po?nrproposta={{NR_PROPOSTA}}&anoproposta={{ANO_PROPOSTA}}&nrmeta={{NR_META}}&nrsubmeta={{NR_SUBMETA}}
   - Produção:
     - Consultar Submetas: GET https://mandatarias.transferegov.sistema.gov.br/projeto-basico/api/v1/po?nrproposta={{NR_PROPOSTA}}&anoproposta={{ANO_PROPOSTA}}
     - Enviar Planilha: POST https://mandatarias.transferegov.sistema.gov.br/projeto-basico/api/v1/po?nrproposta={{NR_PROPOSTA}}&anoproposta={{ANO_PROPOSTA}}&nrmeta={{NR_META}}&nrsubmeta={{NR_SUBMETA}}

3. FORMATOS DE LAYOUT (PLE vs BM):
   - PLE (Planilha de Levantamento de Eventos): Usado quando a obra é acompanhada por eventos (indAcompanhamentoEventos: true). Exige o preenchimento do objeto 'evento' (com numeroEvento e titulo) em cada serviço.
   - BM (Boletim de Medição): Usado quando não há acompanhamento por eventos (indAcompanhamentoEventos: false). Nesse caso, a planilha orçamentária é dividida em parcelas periódicas (objeto 'parcelas' com numeroParcela e percentualParcela, onde o somatório de cada macrosserviço não pode exceder 100.00%).

4. CRÍTICAS DE NEGÓCIO E ERROS COMUNS:
   - "Receber via API?": Se o convenente não habilitar a opção 'Receber dados da PO/CFF via API?' na plataforma Transferegov.br (Aba PO/CFF > Dados Gerais), a API retornará o erro 400 avisando que a submeta não está apta.
   - Sobreposição total: Sempre reforce que os novos envios de planilhas de uma submeta SOBREPÕEM os dados enviados anteriormente na sua totalidade.
   - Domínios de Fontes aceitos: 'Composição', 'Cotação', 'SINAPI', 'Outros'.

5. SUPORTE OFICIAL:
   - Para dúvidas oficiais de integração, forneça o e-mail oficial: seges.api-modulodeobras@gestao.gov.br.

Responda de forma direta, clara e técnica, citando trechos das orientações acima e ajudando na escrita de códigos, comandos curl ou no entendimento do fluxo da API pública do governo brasileiro. Use formatação markdown elegante para códigos, tabelas ou listas.
`;

      const chatHistory = messages.slice(0, messages.length - 1).map((m: any) => {
        return {
          role: m.role === "assistant" ? "model" : "user",
          parts: [{ text: m.content }]
        };
      });

      const userMessage = messages[messages.length - 1].content;

      const chat = gemini.chats.create({
        model: "gemini-3.5-flash",
        history: chatHistory,
        config: {
          systemInstruction,
          temperature: 0.2,
        }
      });

      const response = await chat.sendMessage({
        message: userMessage
      });

      return res.json({
        content: response.text || "Desculpe, não consegui processar sua resposta."
      });
    } catch (error: any) {
      console.error("Gemini Advisor Error:", error);
      return res.status(500).json({ error: error.message || "Erro interno ao processar a consulta do Gemini." });
    }
  });

  // Serve frontend assets or integrate Vite in dev mode
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
