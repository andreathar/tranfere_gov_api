import React, { useState, useEffect } from "react";
import {
  FileText,
  Send,
  Code,
  ShieldCheck,
  Cpu,
  BookOpen,
  Copy,
  Plus,
  Trash2,
  CheckCircle,
  HelpCircle,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Sparkles,
  Info,
  Terminal,
  Settings,
  Cloud,
  DownloadCloud
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import {
  ChatMessage,
  PlanilhaOrcamentariaPayload,
  Macroservico,
  Servico,
  FrenteDeObra,
  Parcela
} from "./types";
import { initAuth, googleSignIn, logout, auth } from "./lib/auth";
import { saveToDrive, loadFromDrive } from "./lib/drive";
import { User } from "firebase/auth";

export default function App() {
  const [activeTab, setActiveTab] = useState<"overview" | "generator" | "tester" | "advisor">("overview");
  const [language, setLanguage] = useState<"pt" | "en">("pt");

  // State for Payload Generator
  const [payloadType, setPayloadType] = useState<"PLE" | "BM">("PLE");
  const [payload, setPayload] = useState<PlanilhaOrcamentariaPayload>({
    macroservicos: [
      {
        numeroMacroservico: 1,
        descricao: "SERVIÇOS PRELIMINARES",
        servicos: [
          {
            numeroServico: 1,
            fonte: "SINAPI",
            codigo: "74209/1",
            descricao: "PLACA DE OBRA EM CHAPA DE ACO GALVANIZADO",
            unidade: "M2",
            custoUnitarioReferencia: 281.61,
            custoUnitario: 281.61,
            bdi: 24.03,
            observacao: "",
            evento: {
              numeroEvento: 1,
              titulo: "SERVIÇOS PRELIMINARES"
            },
            frentesDeObra: [
              {
                numero: 1,
                nomeFrenteObra: "Rua João Reis E0 a E6+0",
                quantidadeItens: 8,
                numeroMesConclusao: 1
              }
            ],
            parcelas: [
              {
                numeroParcela: 1,
                percentualParcela: 100
              }
            ]
          }
        ]
      }
    ]
  });

  // State for API Tester
  const [selectedEndpoint, setSelectedEndpoint] = useState<"login" | "get_submetas" | "post_po" | "consultar_proposta">("get_submetas");
  const [testerProps, setTesterProps] = useState({
    cpf: "12345678901",
    password: "••••••••",
    env: "homologacao" as "homologacao" | "producao",
    nrproposta: "28206",
    anoproposta: "2018",
    nrmeta: "1",
    nrsubmeta: "1",
    idParlamentar: "1234",
    epCadToken: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzaXN0ZW1hIjoiU2lzdGVtYSBFeHRlcm5vIiwiYWN0aXZlIjp0cnVlfQ...",
    userToken: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c3VhcmlvIjoiMTIzNDU2Nzg5MDEiLCJwZXJmaWwiOlsiT3BlcmFkb3IgRmluYW5jZWlybyJdfQ...",
    customBody: ""
  });

  const [testerLoading, setTesterLoading] = useState(false);
  const [testerResponse, setTesterResponse] = useState<any>(null);
  const [testerStatus, setTesterStatus] = useState<number | null>(null);
  const [testerExplain, setTesterExplain] = useState<string>("");

  // State for AI Advisor
  const [advisorInput, setAdvisorInput] = useState("");
  const [advisorMessages, setAdvisorMessages] = useState<ChatMessage[]>([
    {
      id: "init",
      role: "assistant",
      content: "Olá! Sou o seu Consultor Especialista de Integração da API Transferegov.br. Posso tirar qualquer dúvida sobre a integração de planilhas orçamentárias (módulo Projeto Básico), gerar estruturas JSON complexas, ou explicar erros de autenticação (EP-CAD, IDP) e regras de validação. Como posso te ajudar hoje?",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    }
  ]);
  const [advisorLoading, setAdvisorLoading] = useState(false);

  // Auth & Drive
  const [needsAuth, setNeedsAuth] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [driveLoading, setDriveLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "error" | "warning" | "success" } | null>(null);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    if (payloadType === "BM") {
      for (const ms of payload.macroservicos) {
        for (const s of ms.servicos) {
          if (s.parcelas) {
            const total = s.parcelas.reduce((acc, p) => acc + (p.percentualParcela || 0), 0);
            if (total > 100) {
              setToast({
                message: language === "pt" 
                  ? `Aviso: Serviço ${s.codigo} possui soma de parcelas superior a 100% (${total}%)`
                  : `Warning: Service ${s.codigo} has parcel sum exceeding 100% (${total}%)`,
                type: "warning"
              });
              return;
            }
          }
        }
      }
    }
  }, [payload, payloadType, language]);

  useEffect(() => {
    initAuth(
      (userObj, tkn) => {
        setNeedsAuth(false);
        setUser(userObj);
        setToken(tkn);
      },
      () => {
        setNeedsAuth(true);
        setUser(null);
        setToken(null);
      }
    );
  }, []);

  const handleLogin = async () => {
    setIsLoggingIn(true);
    try {
      const result = await googleSignIn();
      if (result) {
        setToken(result.accessToken);
        setUser(result.user);
        setNeedsAuth(false);
      }
    } catch (err) {
      console.error('Login failed:', err);
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    setNeedsAuth(true);
  };

  const handleSaveToDrive = async () => {
    if (needsAuth) return;
    setDriveLoading(true);
    try {
      const cleanedPayload = JSON.parse(JSON.stringify(payload));
      // cleanup structure for saving
      cleanedPayload.macroservicos.forEach((ms: any) => {
        ms.servicos.forEach((s: any) => {
          if (payloadType === "PLE") delete s.parcelas;
          else delete s.evento;
        });
      });
      await saveToDrive(`Planilha_${payloadType}_${Date.now()}.json`, JSON.stringify(cleanedPayload, null, 2));
      alert(t("Planilha salva no Google Drive com sucesso!", "Worksheet saved to Google Drive successfully!"));
    } catch (err) {
      console.error(err);
      alert(t("Erro ao salvar no Drive.", "Failed to save to Drive."));
    } finally {
      setDriveLoading(false);
    }
  };

  const handleLoadFromDrive = async () => {
    if (needsAuth) return;
    setDriveLoading(true);
    try {
      const content = await loadFromDrive();
      if (content) {
        const parsed = JSON.parse(content);
        setPayload(parsed);
        alert(t("Planilha carregada do Google Drive!", "Worksheet loaded from Google Drive!"));
      } else {
        alert(t("Nenhum arquivo JSON encontrado no seu Drive.", "No JSON files found in your Drive."));
      }
    } catch (err) {
      console.error(err);
      alert(t("Erro ao carregar do Drive.", "Failed to load from Drive."));
    } finally {
      setDriveLoading(false);
    }
  };

  // Synchronize payload changes with customBody inside tester when tab changes or payload type changes
  useEffect(() => {
    // Generate cleaned body based on PLE vs BM
    const cleanedPayload = JSON.parse(JSON.stringify(payload));
    cleanedPayload.macroservicos.forEach((ms: any) => {
      ms.servicos.forEach((s: any) => {
        if (payloadType === "PLE") {
          delete s.parcelas;
        } else {
          delete s.evento;
        }
      });
    });

    setTesterProps(prev => ({
      ...prev,
      customBody: JSON.stringify(cleanedPayload, null, 2)
    }));
  }, [payload, payloadType]);

  // Translate utility
  const t = (pt: string, en: string) => (language === "pt" ? pt : en);

  // Helper to add macroservice
  const addMacroservico = () => {
    const newMs: Macroservico = {
      numeroMacroservico: payload.macroservicos.length + 1,
      descricao: "NOVO MACROSSERVIÇO DE EXEMPLO",
      servicos: [
        {
          numeroServico: 1,
          fonte: "SINAPI",
          codigo: "88244",
          descricao: "SERVIÇO AUXILIAR DE EXEMPLO",
          unidade: "H",
          custoUnitarioReferencia: 15.50,
          custoUnitario: 15.50,
          bdi: 20.0,
          observacao: "",
          evento: {
            numeroEvento: 1,
            titulo: "EVENTO DE EXEMPLO"
          },
          frentesDeObra: [
            {
              numero: 1,
              nomeFrenteObra: "Frente de Obra Primária",
              quantidadeItens: 10,
              numeroMesConclusao: 1
            }
          ],
          parcelas: [
            {
              numeroParcela: 1,
              percentualParcela: 100
            }
          ]
        }
      ]
    };
    setPayload({
      ...payload,
      macroservicos: [...payload.macroservicos, newMs]
    });
  };

  // Helper to remove macroservice
  const removeMacroservico = (index: number) => {
    if (payload.macroservicos.length <= 1) return;
    const list = [...payload.macroservicos];
    list.splice(index, 1);
    // Reindex
    list.forEach((ms, i) => {
      ms.numeroMacroservico = i + 1;
    });
    setPayload({ ...payload, macroservicos: list });
  };

  // Helper to update macroservice description
  const updateMacroservicoDesc = (index: number, val: string) => {
    const list = [...payload.macroservicos];
    list[index].descricao = val.toUpperCase();
    setPayload({ ...payload, macroservicos: list });
  };

  // Helper to add service to macroservice
  const addServico = (msIndex: number) => {
    const list = [...payload.macroservicos];
    const ms = list[msIndex];
    const newS: Servico = {
      numeroServico: ms.servicos.length + 1,
      fonte: "SINAPI",
      codigo: "99999",
      descricao: "NOVO SERVIÇO ADICIONADO",
      unidade: "UN",
      custoUnitarioReferencia: 100.0,
      custoUnitario: 100.0,
      bdi: 25.0,
      observacao: "",
      evento: {
        numeroEvento: ms.servicos.length + 1,
        titulo: "EVENTO ASSOCIADO"
      },
      frentesDeObra: [
        {
          numero: 1,
          nomeFrenteObra: "Frente Geral",
          quantidadeItens: 1,
          numeroMesConclusao: 1
        }
      ],
      parcelas: [
        {
          numeroParcela: 1,
          percentualParcela: 100
        }
      ]
    };
    ms.servicos.push(newS);
    setPayload({ ...payload, macroservicos: list });
  };

  // Helper to remove service
  const removeServico = (msIndex: number, sIndex: number) => {
    const list = [...payload.macroservicos];
    const ms = list[msIndex];
    if (ms.servicos.length <= 1) return;
    ms.servicos.splice(sIndex, 1);
    // Reindex
    ms.servicos.forEach((s, i) => {
      s.numeroServico = i + 1;
    });
    setPayload({ ...payload, macroservicos: list });
  };

  // Helper to update service field
  const updateServicoField = (msIndex: number, sIndex: number, field: keyof Servico, value: any) => {
    const list = [...payload.macroservicos];
    const s = list[msIndex].servicos[sIndex] as any;
    s[field] = value;
    setPayload({ ...payload, macroservicos: list });
  };

  // Run tester call
  const executeSimulatorRequest = async () => {
    setTesterLoading(true);
    setTesterResponse(null);
    setTesterStatus(null);
    setTesterExplain("");

    try {
      let url = "";
      let method = "GET";
      let headers: any = {};
      let body: any = null;

      if (selectedEndpoint === "login") {
        url = "/api/simulate/login";
        method = "POST";
        headers["Content-Type"] = "application/json";
        body = JSON.stringify({
          cpf: testerProps.cpf,
          senha: testerProps.password,
          env: testerProps.env
        });
      } else if (selectedEndpoint === "consultar_proposta") {
        const query = new URLSearchParams({
          autorDaEmenda: testerProps.idParlamentar
        });
        url = `/api/simulate/voluntarias/proposta/ConsultarProposta/ConsultarProposta.do?${query.toString()}`;
        method = "GET";
        headers["Accept"] = "text/csv,application/json";
      } else if (selectedEndpoint === "get_submetas") {
        const query = new URLSearchParams({
          nrproposta: testerProps.nrproposta,
          anoproposta: testerProps.anoproposta
        });
        url = `/api/simulate/projeto-basico/api/v1/po?${query.toString()}`;
        method = "GET";
        headers["ep-cad"] = testerProps.epCadToken;
        headers["Authorization"] = testerProps.userToken.startsWith("Bearer ")
          ? testerProps.userToken
          : `Bearer ${testerProps.userToken}`;
      } else if (selectedEndpoint === "post_po") {
        const query = new URLSearchParams({
          nrproposta: testerProps.nrproposta,
          anoproposta: testerProps.anoproposta,
          nrmeta: testerProps.nrmeta,
          nrsubmeta: testerProps.nrsubmeta
        });
        url = `/api/simulate/projeto-basico/api/v1/po?${query.toString()}`;
        method = "POST";
        headers["Content-Type"] = "application/json";
        headers["ep-cad"] = testerProps.epCadToken;
        headers["Authorization"] = testerProps.userToken.startsWith("Bearer ")
          ? testerProps.userToken
          : `Bearer ${testerProps.userToken}`;
        body = testerProps.customBody;
      }

      const res = await fetch(url, {
        method,
        headers,
        body
      });

      const contentType = res.headers.get("content-type");
      let data;
      if (contentType && (contentType.includes("text/csv") || contentType.includes("text/plain"))) {
        data = await res.text();
      } else {
        data = await res.json();
      }
      
      setTesterStatus(res.status);
      setTesterResponse(data);

      // Business logic explanations
      if (res.status === 201) {
        setTesterExplain(
          language === "pt"
            ? "Sucesso! A planilha orçamentária foi aceita e persistida na base do Transferegov.br. Novos envios sobrepõem estes dados na totalidade."
            : "Success! The budget worksheet was accepted and saved in Transferegov.br. Subsequent submissions overwrite this data entirely."
        );
      } else if (res.status === 200) {
        if (selectedEndpoint === "consultar_proposta") {
          setTesterExplain(
            language === "pt"
              ? "Sucesso! Retornou os dados em CSV para as propostas do autor da emenda."
              : "Success! Returned CSV data for the amendment author proposals."
          );
        } else {
          setTesterExplain(
            language === "pt"
              ? "Sucesso! Foram retornadas as submetas da proposta. Note o campo 'indReceberPO_CFFviaAPI' que indica se a submeta está apta a receber dados via API."
              : "Success! Subgoals returned. Check the 'indReceberPO_CFFviaAPI' flag which determines if the subgoal is enabled to receive API integrations."
          );
        }
      } else if (res.status === 401) {
        setTesterExplain(
          language === "pt"
            ? "Erro de Autenticação (401). Isso ocorre quando o token 'EP-CAD' (do sistema de obras) ou 'Authorization: Bearer' (do usuário) está ausente, incorreto, ou expirou."
            : "Authentication Error (401). This happens when the 'EP-CAD' token (external system) or 'Authorization: Bearer' token (user login) is missing, incorrect, or expired."
        );
      } else if (res.status === 400) {
        if (data.errorMessage?.includes("Receber dados")) {
          setTesterExplain(
            language === "pt"
              ? "Regra de Negócio (400): O convenente deve acessar o painel do Transferegov.br > Projeto Básico > PO/CFF > Dados Gerais e marcar a opção 'Receber dados da PO/CFF via API?' para esta submeta, caso contrário ela rejeitará qualquer inserção."
              : "Business Rule (400): The user must check the option 'Receber dados da PO/CFF via API?' inside the Transferegov.br platform under PO/CFF > General Data for this subgoal before writing data."
          );
        } else {
          setTesterExplain(
            language === "pt"
              ? "Erro de Validação (400). Erro de validação de estrutura ou regra de negócio (ex: número da proposta não numérico, metas não cadastradas ou percentual de parcelas superior a 100%)."
              : "Validation Error (400). Structure or business rule validation failed (e.g. non-numeric proposal, unregistered goals, or installment sum exceeding 100%)."
          );
        }
      }
    } catch (e: any) {
      setTesterStatus(500);
      setTesterResponse({ error: e.message || "Erro de conexão com o simulador local." });
    } finally {
      setTesterLoading(false);
    }
  };

  // Run AI Advisor Query
  const sendAdvisorMessage = async (overridePrompt?: string) => {
    const promptText = overridePrompt || advisorInput;
    if (!promptText.trim()) return;

    const userMsg: ChatMessage = {
      id: Math.random().toString(),
      role: "user",
      content: promptText,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    };

    setAdvisorMessages(prev => [...prev, userMsg]);
    if (!overridePrompt) setAdvisorInput("");
    setAdvisorLoading(true);

    try {
      const payloadMessages = [...advisorMessages, userMsg].map(m => ({
        role: m.role,
        content: m.content
      }));

      const res = await fetch("/api/gemini/advisor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: payloadMessages })
      });

      const data = await res.json();

      const botMsg: ChatMessage = {
        id: Math.random().toString(),
        role: "assistant",
        content: data.content || "Desculpe, ocorreu um erro inesperado na resposta.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      };

      setAdvisorMessages(prev => [...prev, botMsg]);
    } catch (error: any) {
      const errorMsg: ChatMessage = {
        id: Math.random().toString(),
        role: "assistant",
        content: "Ocorreu um erro ao comunicar-se com a API do consultor. Verifique se o servidor está ativo ou se a chave GEMINI_API_KEY está configurada.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      };
      setAdvisorMessages(prev => [...prev, errorMsg]);
    } finally {
      setAdvisorLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const loadPayloadToTester = () => {
    // Generates the cleaned payload
    const cleanedPayload = JSON.parse(JSON.stringify(payload));
    cleanedPayload.macroservicos.forEach((ms: any) => {
      ms.servicos.forEach((s: any) => {
        if (payloadType === "PLE") {
          delete s.parcelas;
        } else {
          delete s.evento;
        }
      });
    });

    setTesterProps(prev => ({
      ...prev,
      customBody: JSON.stringify(cleanedPayload, null, 2)
    }));
    setSelectedEndpoint("post_po");
    setActiveTab("tester");
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-800 flex flex-col font-sans antialiased selection:bg-blue-100 selection:text-blue-900">
      
      {/* Toast Notification */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-3 rounded-lg shadow-lg border flex items-center gap-3 min-w-[300px] ${
              toast.type === "warning" ? "bg-amber-50 border-amber-200 text-amber-800" :
              toast.type === "error" ? "bg-red-50 border-red-200 text-red-800" :
              "bg-green-50 border-green-200 text-green-800"
            }`}
          >
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span className="text-sm font-semibold">{toast.message}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Top Header - Sleek Interface Style */}
      <header className="bg-white border-b border-slate-200 flex flex-col md:flex-row items-center justify-between px-8 py-4 shrink-0 gap-4 shadow-sm z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center shadow-sm">
            <div className="w-4 h-4 bg-yellow-400 rounded-sm rotate-45"></div>
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-slate-850 flex items-center gap-2">
              Transferegov <span className="font-normal text-slate-400">| Dev Portal</span>
              <span className="text-blue-600 font-mono text-[10px] border border-blue-200 px-1.5 py-0.5 rounded ml-1 bg-blue-50">v1.3</span>
            </h1>
            <p className="text-[10px] text-slate-450 mt-0.5 font-medium hidden sm:block">
              {t(
                "Painel de apoio ao desenvolvedor integrador para Planilha Orçamentária de Obras.",
                "Developer support hub for integrating Construction Budget Worksheets."
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Active indicator */}
          <span className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            {t("Simulador Ativo", "Simulator Active")}
          </span>

          {/* Language Switcher & Link */}
          <div className="flex items-center gap-3">
            <div className="bg-slate-100 p-0.5 rounded-lg border border-slate-200 flex shadow-inner">
              <button
                onClick={() => setLanguage("pt")}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all ${
                  language === "pt" ? "bg-white text-blue-600 shadow-sm" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                PT-BR
              </button>
              <button
                onClick={() => setLanguage("en")}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all ${
                  language === "en" ? "bg-white text-blue-600 shadow-sm" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                EN
              </button>
            </div>
            <a
              href="https://www.gov.br/transferegov/pt-br/sobre/apis-integracao/sistemas-de-obras"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-xs text-slate-600 hover:text-slate-900 rounded-lg border border-slate-200 transition-all font-medium"
            >
              <span>{t("Manual", "Manual")}</span>
              <ExternalLink className="w-3 h-3 text-slate-400" />
            </a>
          </div>

          {/* Profile Card from Sleek Design */}
          <div className="flex items-center gap-3 pl-6 border-l border-slate-200">
            <div className="text-right hidden sm:block">
              <p className="text-xs font-bold text-slate-800 leading-none">Private Integrator XP</p>
              <p className="text-[10px] text-slate-400 mt-1 font-mono">ID: 284.992-01</p>
            </div>
            <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs shadow-inner">
              PI
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto w-full flex-grow flex flex-col md:flex-row px-4 py-6 gap-6">
        
        {/* Navigation Sidebar - Sleek Design Style */}
        <aside className="w-full md:w-64 bg-slate-50 border border-slate-200/80 rounded-2xl p-5 flex flex-col gap-5 shrink-0 shadow-sm">
          <div>
            <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 px-1">
              {t("Menu de Navegação", "Navigation Menu")}
            </h3>
            
            <div className="space-y-2">
              <button
                onClick={() => setActiveTab("overview")}
                className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-semibold transition-all border ${
                  activeTab === "overview"
                    ? "bg-white text-blue-600 border-slate-200 shadow-sm"
                    : "text-slate-500 hover:text-slate-800 hover:bg-slate-100/50 border-transparent"
                }`}
              >
                <BookOpen className={`w-4 h-4 ${activeTab === "overview" ? "text-blue-600" : "text-slate-400"}`} />
                <div className="text-left">
                  <span className="block">{t("Visão Geral & Manual", "Overview & Manual")}</span>
                </div>
              </button>

              <button
                onClick={() => setActiveTab("generator")}
                className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-semibold transition-all border ${
                  activeTab === "generator"
                    ? "bg-white text-blue-600 border-slate-200 shadow-sm"
                    : "text-slate-500 hover:text-slate-800 hover:bg-slate-100/50 border-transparent"
                }`}
              >
                <Code className={`w-4 h-4 ${activeTab === "generator" ? "text-blue-600" : "text-slate-400"}`} />
                <div className="text-left">
                  <span className="block">{t("Gerador de Payloads", "Payload Builder")}</span>
                </div>
              </button>

              <button
                onClick={() => setActiveTab("tester")}
                className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-semibold transition-all border ${
                  activeTab === "tester"
                    ? "bg-white text-blue-600 border-slate-200 shadow-sm"
                    : "text-slate-500 hover:text-slate-800 hover:bg-slate-100/50 border-transparent"
                }`}
              >
                <Terminal className={`w-4 h-4 ${activeTab === "tester" ? "text-blue-600" : "text-slate-400"}`} />
                <div className="text-left">
                  <span className="block">{t("Testador & Simulador", "API Tester & Sandbox")}</span>
                </div>
              </button>

              <button
                onClick={() => setActiveTab("advisor")}
                className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-semibold transition-all border relative overflow-hidden ${
                  activeTab === "advisor"
                    ? "bg-white text-blue-600 border-slate-200 shadow-sm"
                    : "text-slate-500 hover:text-slate-800 hover:bg-slate-100/50 border-transparent"
                }`}
              >
                <Sparkles className={`w-4 h-4 ${activeTab === "advisor" ? "text-yellow-500 animate-pulse" : "text-slate-400"}`} />
                <div className="text-left">
                  <span className="block">{t("Consultor IA Especialista", "Smart AI Advisor")}</span>
                </div>
                <div className="absolute right-3 top-4 w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping" />
              </button>
            </div>
          </div>

          {/* Sleek Support box - bottom of sidebar */}
          <div className="mt-auto">
            <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 flex flex-col gap-2">
              <p className="text-xs font-bold text-blue-800">{t("Suporte à Integração", "Official Support")}</p>
              <p className="text-[11px] text-blue-600 leading-relaxed">
                {t(
                  "Dúvidas sobre homologação, ofício de habilitação ou dúvidas de infraestrutura com a equipe federal:",
                  "For questions regarding system authorization, formal letters, or infra issues with the federal team:"
                )}
              </p>
              <a
                href="mailto:seges.api-modulodeobras@gestao.gov.br"
                className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white text-[10px] font-bold rounded-lg shadow-sm text-center transition-all block truncate px-2"
                title="seges.api-modulodeobras@gestao.gov.br"
              >
                seges.api-modulodeobras@gestao.gov.br
              </a>
            </div>
          </div>
        </aside>

        {/* Dynamic Display Screens */}
        <div className="flex-grow min-w-0">
          <AnimatePresence mode="wait">
            
            {/* Screen 1: Overview */}
            {activeTab === "overview" && (
              <motion.div
                key="overview"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-6"
              >
                {/* Integration Summary Hero */}
                <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl" />
                  <div className="flex items-start gap-4">
                    <div className="p-3 bg-blue-50 text-blue-600 rounded-xl border border-blue-100">
                      <Cpu className="w-6 h-6" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-slate-900 mb-2">
                        {t("Como Funciona a Integração da Planilha Orçamentária?", "How the Budget Worksheet Integration Works")}
                      </h2>
                      <p className="text-sm text-slate-500 leading-relaxed max-w-4xl">
                        {t(
                          "A API Transferegov permite que sistemas externos de engenharia alimentem e atualizem a planilha orçamentária e o cronograma físico-financeiro do módulo Projeto Básico. Isso otimiza o fluxo do convenente e evita erros de digitação manual na plataforma federal.",
                          "The Transferegov API enables external engineering systems to directly feed and update the budget sheets and schedule of the Basic Project module. This automates the process for developers and prevents discrepancies."
                        )}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Integration Flow Steps */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  
                  <div className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono bg-blue-50 text-blue-600 border border-blue-100 px-2.5 py-1 rounded-full font-bold">
                        PASSO 1
                      </span>
                      <ShieldCheck className="w-5 h-5 text-blue-600" />
                    </div>
                    <h3 className="font-bold text-slate-800 text-sm">{t("Habilitação do Sistema", "System Habilitation")}</h3>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      {t(
                        "O responsável técnico do sistema parceiro deve formalizar um pedido de ofício ao Ministério. Uma vez aprovado, um token de acesso permanente identificando o sistema é enviado por e-mail. Este deve ser anexado no cabeçalho 'EP-CAD' em todas as solicitações.",
                        "The technical lead of the engineering software must formally request habilitation from the Ministry. Once granted, a unique system token is dispatched. This token goes into the 'EP-CAD' header."
                      )}
                    </p>
                    <a
                      href="https://www.gov.br/transferegov/pt-br/sobre/apis-integracao/sistemas-de-obras"
                      target="_blank"
                      rel="noopener"
                      className="text-xs text-blue-600 hover:text-blue-700 hover:underline flex items-center gap-1 mt-auto font-bold"
                    >
                      {t("Instruções de Habilitação", "Request Instructions")}
                      <ArrowRight className="w-3 h-3" />
                    </a>
                  </div>

                  <div className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono bg-blue-50 text-blue-600 border border-blue-100 px-2.5 py-1 rounded-full font-bold">
                        PASSO 2
                      </span>
                      <Settings className="w-5 h-5 text-blue-600" />
                    </div>
                    <h3 className="font-bold text-slate-800 text-sm">{t("Autenticação do Usuário", "User Authentication")}</h3>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      {t(
                        "O usuário convenente deve se autenticar via IDP do governo fornecendo seu CPF e senha. A API IDP retorna um Token JWT temporário que deve ser informado no cabeçalho 'Authorization: Bearer <token_jwt_usuario>'. O usuário precisa possuir perfil financeiro/gestor no convênio.",
                        "The partner user authenticates through the governmental IDP with their CPF and password. The authentication service returns a user JWT that must be placed in the standard 'Authorization: Bearer' header."
                      )}
                    </p>
                    <button
                      onClick={() => { setSelectedEndpoint("login"); setActiveTab("tester"); }}
                      className="text-xs text-blue-600 hover:text-blue-700 hover:underline flex items-center gap-1 mt-auto font-bold text-left"
                    >
                      {t("Simular IDP Login", "Test IDP Authentication")}
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>

                  <div className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono bg-blue-50 text-blue-600 border border-blue-100 px-2.5 py-1 rounded-full font-bold">
                        PASSO 3
                      </span>
                      <FileText className="w-5 h-5 text-blue-600" />
                    </div>
                    <h3 className="font-bold text-slate-800 text-sm">{t("Habilitação da Submeta", "Enable the Subgoal")}</h3>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      {t(
                        "Antes de enviar os dados por API, o convenente precisa obrigatoriamente acessar a aba 'PO/CFF > Dados Gerais' da submeta no Transferegov.br e ativar o checkbox 'Receber dados da PO/CFF via API?'. Sem isso, a inserção falhará com erro 400.",
                        "Before submitting payload data, the user must explicitly check 'Receber dados da PO/CFF via API?' inside the Transferegov.br web app on PO/CFF > General Data. Otherwise, insertion is rejected with error 400."
                      )}
                    </p>
                    <button
                      onClick={() => { setSelectedEndpoint("get_submetas"); setActiveTab("tester"); }}
                      className="text-xs text-blue-600 hover:text-blue-700 hover:underline flex items-center gap-1 mt-auto font-bold text-left"
                    >
                      {t("Simular Consulta de Submeta", "Check Subgoal State")}
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>

                </div>

                {/* API Request Flow Graphic */}
                <div className="bg-slate-900 rounded-2xl p-6 shadow-xl border border-slate-800">
                  <div className="flex items-center gap-2 mb-4">
                    <div className="flex gap-1.5">
                      <div className="w-3 h-3 rounded-full bg-red-500"></div>
                      <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                      <div className="w-3 h-3 rounded-full bg-green-500"></div>
                    </div>
                    <span className="text-xs text-slate-400 ml-4 font-mono">POST /api/v1/po</span>
                  </div>
                  
                  <div className="p-4 bg-slate-950 rounded-xl border border-slate-850 font-mono text-xs text-slate-300 overflow-x-auto space-y-3">
                    <div>
                      <span className="text-blue-400 font-semibold">POST</span> https://mandatarias.transferegov.sistema.gov.br/projeto-basico/api/v1/po?nrproposta=28206&anoproposta=2018&nrmeta=1&nrsubmeta=1
                    </div>
                    <hr className="border-slate-850" />
                    <div className="space-y-1">
                      <div><span className="text-blue-400">Content-Type:</span> application/json</div>
                      <div><span className="text-blue-400">EP-CAD:</span> <span className="text-slate-400">&lt;token_jwt_sistema_obras&gt;</span> <span className="text-slate-500 font-sans text-[10px] ml-2">({t("Obtido por Ofício oficial", "Obtained via official request")})</span></div>
                      <div><span className="text-blue-400">Authorization:</span> Bearer <span className="text-slate-400">&lt;token_jwt_usuario&gt;</span> <span className="text-slate-500 font-sans text-[10px] ml-2">({t("Obtido via Login no IDP", "Obtained via IDP login endpoint")})</span></div>
                    </div>
                  </div>
                </div>

                {/* Key validation rules checklist */}
                <div className="p-6 rounded-xl bg-white border border-slate-200 shadow-sm space-y-4">
                  <h3 className="font-bold text-slate-900 flex items-center gap-2">
                    <Info className="w-4.5 h-4.5 text-blue-600" />
                    {t("Regras Críticas de Negócio (Manual v1.3)", "Critical Validation Rules (Manual v1.3)")}
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-3">
                      <div className="flex gap-2.5 items-start">
                        <CheckCircle className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                        <p className="text-xs text-slate-600 leading-relaxed">
                          <strong>{t("Sobreposição de Dados:", "Data Overwrite:")}</strong> {t("Qualquer novo envio de planilha orçamentária via API para uma submeta irá sobrepor integralmente os dados anteriores cadastrados para ela.", "Any subsequent sheet upload via API for a specific subgoal will completely overwrite all previously saved items for it.")}
                        </p>
                      </div>
                      <div className="flex gap-2.5 items-start">
                        <CheckCircle className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                        <p className="text-xs text-slate-600 leading-relaxed">
                          <strong>{t("Fontes de Insumos Permitidas:", "Allowed Input Sources:")}</strong> {t("O campo 'fonte' de cada serviço deve ser preenchido rigorosamente com uma destas strings: 'Composição', 'Cotação', 'SINAPI' ou 'Outros'.", "The 'fonte' field of each item/service must strictly be matched with one of: 'Composição', 'Cotação', 'SINAPI', or 'Outros'.")}
                        </p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div className="flex gap-2.5 items-start">
                        <CheckCircle className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                        <p className="text-xs text-slate-600 leading-relaxed">
                          <strong>{t("PLE vs BM:", "PLE vs BM:")}</strong> {t("Se indAcompanhamentoEventos for True, o preenchimento do bloco de 'evento' em cada serviço é obrigatório. Se for False, o bloco de 'parcelas' deve ser informado sem indicação de eventos.", "If indAcompanhamentoEventos is True, the 'evento' block inside services is mandatory. If False, the 'parcelas' block must be specified instead of event info.")}
                        </p>
                      </div>
                      <div className="flex gap-2.5 items-start">
                        <CheckCircle className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                        <p className="text-xs text-slate-600 leading-relaxed">
                          <strong>{t("Percentual Máximo:", "Max Percentile:")}</strong> {t("Para planilhas no formato BM, o somatório dos percentuais das parcelas de cada serviço não pode ultrapassar 100.00%.", "For BM worksheets, the mathematical sum of the installment percentiles for any service cannot exceed 100.00%.")}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

              </motion.div>
            )}

            {/* Screen 2: Payload Generator */}
            {activeTab === "generator" && (
              <motion.div
                key="generator"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="grid grid-cols-1 lg:grid-cols-12 gap-6"
              >
                {/* Form Controls - 7 columns */}
                <div className="lg:col-span-7 space-y-6">
                  <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-6">
                    <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-slate-100 pb-4">
                      <div>
                        <h3 className="font-bold text-slate-900 text-base">
                          {t("Montar Planilha Orçamentária", "Build Budget Worksheet")}
                        </h3>
                        <p className="text-xs text-slate-500 mt-1">
                          {t("Selecione o tipo de acompanhamento de acordo com a submeta", "Choose the tracking type associated with your subgoal")}
                        </p>
                      </div>
 
                      {/* Payload Format Switcher */}
                      <div className="bg-slate-100 p-0.5 rounded-lg border border-slate-200 flex self-start sm:self-auto shadow-inner">
                        <button
                          onClick={() => setPayloadType("PLE")}
                          className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${
                            payloadType === "PLE"
                              ? "bg-white text-blue-600 shadow-sm"
                              : "text-slate-500 hover:text-slate-800"
                          }`}
                        >
                          PLE ({t("Eventos", "Events")})
                        </button>
                        <button
                          onClick={() => setPayloadType("BM")}
                          className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${
                            payloadType === "BM"
                              ? "bg-white text-blue-600 shadow-sm"
                              : "text-slate-500 hover:text-slate-800"
                          }`}
                        >
                          BM ({t("Boletim", "Bulletin")})
                        </button>
                      </div>
                    </div>
 
                    {/* Macroservices list */}
                    <div className="space-y-6">
                      {payload.macroservicos.map((ms, msIndex) => (
                        <div key={msIndex} className="p-5 rounded-2xl bg-slate-50 border border-slate-200/80 relative space-y-4">
                          <div className="flex justify-between items-center gap-2">
                            <span className="text-xs font-mono font-bold text-blue-600 bg-blue-50 border border-blue-100 px-2.5 py-1 rounded">
                              {t("Macrosserviço", "Macroservice")} #{ms.numeroMacroservico}
                            </span>
                            <button
                              onClick={() => removeMacroservico(msIndex)}
                              disabled={payload.macroservicos.length <= 1}
                              className="text-slate-400 hover:text-red-500 transition-colors p-1 disabled:opacity-30 disabled:hover:text-slate-400"
                              title={t("Excluir Macrosserviço", "Delete Macroservice")}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
 
                          <div className="grid grid-cols-1 gap-1.5">
                            <label className="text-[10px] uppercase font-bold text-slate-450">{t("Descrição do Macrosserviço", "Macroservice Description")}</label>
                            <input
                              type="text"
                              value={ms.descricao}
                              onChange={(e) => updateMacroservicoDesc(msIndex, e.target.value)}
                              className="w-full bg-white border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none rounded-lg px-3 py-2 text-xs font-semibold tracking-wide uppercase text-slate-800"
                            />
                          </div>
 
                          {/* Services List inside Macroservice */}
                          <div className="space-y-4 pl-3 border-l-2 border-slate-200">
                            <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                              {t("Itens de Serviços do Macrosserviço", "Services list for this macroservice")}
                            </span>
 
                            {ms.servicos.map((s, sIndex) => (
                              <div key={sIndex} className="p-4 bg-white rounded-xl border border-slate-200/80 shadow-sm space-y-3 relative">
                                <div className="flex justify-between items-center gap-2">
                                  <span className="text-[10px] font-mono font-bold text-blue-600">
                                    {t("Item", "Service")} #{s.numeroServico}
                                  </span>
                                  <button
                                    onClick={() => removeServico(msIndex, sIndex)}
                                    disabled={ms.servicos.length <= 1}
                                    className="text-slate-400 hover:text-red-500 transition-colors p-1 disabled:opacity-30 disabled:hover:text-slate-400"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
 
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[9px] uppercase font-bold text-slate-450">{t("Fonte", "Source")}</label>
                                    <select
                                      value={s.fonte}
                                      onChange={(e) => updateServicoField(msIndex, sIndex, "fonte", e.target.value)}
                                      className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-1.5 text-xs text-slate-700 font-medium"
                                    >
                                      <option value="SINAPI">SINAPI</option>
                                      <option value="Composição">Composição</option>
                                      <option value="Cotação">Cotação</option>
                                      <option value="Outros">Outros</option>
                                    </select>
                                  </div>
 
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[9px] uppercase font-bold text-slate-450">{t("Código", "Code")}</label>
                                    <input
                                      type="text"
                                      value={s.codigo}
                                      onChange={(e) => updateServicoField(msIndex, sIndex, "codigo", e.target.value)}
                                      className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2.5 py-1 text-xs text-slate-700 font-mono"
                                    />
                                  </div>
 
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[9px] uppercase font-bold text-slate-450">{t("Unidade", "Unit")}</label>
                                    <input
                                      type="text"
                                      value={s.unidade}
                                      placeholder="UN, M2, M, H, MES"
                                      onChange={(e) => updateServicoField(msIndex, sIndex, "unidade", e.target.value)}
                                      className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2.5 py-1 text-xs text-slate-700"
                                    />
                                  </div>
                                </div>
 
                                <div className="flex flex-col gap-1">
                                  <label className="text-[9px] uppercase font-bold text-slate-450">{t("Descrição do Serviço", "Service Description")}</label>
                                  <input
                                    type="text"
                                    value={s.descricao}
                                    onChange={(e) => updateServicoField(msIndex, sIndex, "descricao", e.target.value)}
                                    className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2.5 py-1 text-xs text-slate-700"
                                  />
                                </div>
 
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[9px] uppercase font-bold text-slate-450">{t("Custo Ref (R$)", "Ref Cost (R$)")}</label>
                                    <input
                                      type="number"
                                      value={s.custoUnitarioReferencia}
                                      onChange={(e) => updateServicoField(msIndex, sIndex, "custoUnitarioReferencia", parseFloat(e.target.value) || 0)}
                                      className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2.5 py-1 text-xs text-slate-700 font-mono"
                                    />
                                  </div>
 
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[9px] uppercase font-bold text-slate-450">{t("Custo Un (R$)", "Unit Cost (R$)")}</label>
                                    <input
                                      type="number"
                                      value={s.custoUnitario}
                                      onChange={(e) => updateServicoField(msIndex, sIndex, "custoUnitario", parseFloat(e.target.value) || 0)}
                                      className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2.5 py-1 text-xs text-slate-700 font-mono"
                                    />
                                  </div>
 
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[9px] uppercase font-bold text-slate-450">{t("BDI (%)", "BDI (%)")}</label>
                                    <input
                                      type="number"
                                      value={s.bdi}
                                      onChange={(e) => updateServicoField(msIndex, sIndex, "bdi", parseFloat(e.target.value) || 0)}
                                      className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2.5 py-1 text-xs text-slate-700 font-mono"
                                    />
                                  </div>
                                </div>
 
                                {/* Dynamic Condition based on PLE vs BM */}
                                {payloadType === "PLE" ? (
                                  <div className="p-3 bg-blue-50/50 border border-blue-100 rounded-lg space-y-2">
                                    <span className="text-[9px] uppercase font-bold text-blue-600 flex items-center gap-1">
                                      <Info className="w-3 h-3" />
                                      {t("Dados de Acompanhamento do Evento (PLE)", "Event-tracked details (PLE)")}
                                    </span>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                      <div className="flex flex-col gap-1">
                                        <label className="text-[8px] uppercase font-bold text-slate-400">{t("Número do Evento", "Event Number")}</label>
                                        <input
                                          type="number"
                                          value={s.evento?.numeroEvento || 1}
                                          onChange={(e) => {
                                            const val = parseInt(e.target.value) || 1;
                                            updateServicoField(msIndex, sIndex, "evento", {
                                              ...s.evento,
                                              numeroEvento: val
                                            });
                                          }}
                                          className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2 py-0.5 text-xs text-slate-700 font-mono"
                                        />
                                      </div>
                                      <div className="flex flex-col gap-1">
                                        <label className="text-[8px] uppercase font-bold text-slate-400">{t("Título do Evento", "Event Title")}</label>
                                        <input
                                          type="text"
                                          value={s.evento?.titulo || ""}
                                          onChange={(e) => {
                                            updateServicoField(msIndex, sIndex, "evento", {
                                              ...s.evento,
                                              titulo: e.target.value
                                            });
                                          }}
                                          className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2 py-0.5 text-xs text-slate-700"
                                        />
                                      </div>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="p-3 bg-blue-50/50 border border-blue-100 rounded-lg space-y-2">
                                    <span className="text-[9px] uppercase font-bold text-blue-600 flex items-center gap-1">
                                      <Info className="w-3 h-3" />
                                      {t("Distribuição de Parcelas (Formatos BM)", "Installments distribution (BM Format)")}
                                    </span>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                      <div className="flex flex-col gap-1">
                                        <label className="text-[8px] uppercase font-bold text-slate-400">{t("Número da Parcela", "Installment Number")}</label>
                                        <input
                                          type="number"
                                          value={s.parcelas?.[0]?.numeroParcela || 1}
                                          onChange={(e) => {
                                            const val = parseInt(e.target.value) || 1;
                                            updateServicoField(msIndex, sIndex, "parcelas", [
                                              {
                                                numeroParcela: val,
                                                percentualParcela: s.parcelas?.[0]?.percentualParcela || 100
                                              }
                                            ]);
                                          }}
                                          className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2 py-0.5 text-xs text-slate-700 font-mono"
                                        />
                                      </div>
                                      <div className="flex flex-col gap-1">
                                        <label className="text-[8px] uppercase font-bold text-slate-400">{t("Percentual (%) - Máx 100", "Percentage (%) - Max 100")}</label>
                                        <input
                                          type="number"
                                          value={s.parcelas?.[0]?.percentualParcela || 100}
                                          max={100}
                                          min={0}
                                          onChange={(e) => {
                                            const val = parseFloat(e.target.value) || 0;
                                            updateServicoField(msIndex, sIndex, "parcelas", [
                                              {
                                                numeroParcela: s.parcelas?.[0]?.numeroParcela || 1,
                                                percentualParcela: Math.min(val, 100)
                                              }
                                            ]);
                                          }}
                                          className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg px-2 py-0.5 text-xs text-slate-700 font-mono"
                                        />
                                      </div>
                                    </div>
                                  </div>
                                )}
 
                                {/* Frentes de Obra Block */}
                                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80 space-y-1.5">
                                  <span className="text-[8px] font-bold text-slate-450 uppercase tracking-wider block">
                                    {t("Frente de Obra Associada", "Associated Workfront")}
                                  </span>
                                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <div className="flex flex-col gap-0.5">
                                      <label className="text-[7px] uppercase font-bold text-slate-400">{t("Nome", "Name")}</label>
                                      <input
                                        type="text"
                                        value={s.frentesDeObra[0].nomeFrenteObra}
                                        onChange={(e) => {
                                          const listFo = [...s.frentesDeObra];
                                          listFo[0].nomeFrenteObra = e.target.value;
                                          updateServicoField(msIndex, sIndex, "frentesDeObra", listFo);
                                        }}
                                        className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded p-1 text-[11px] text-slate-700"
                                      />
                                    </div>
 
                                    <div className="flex flex-col gap-0.5">
                                      <label className="text-[7px] uppercase font-bold text-slate-400">{t("Quant. Itens", "Items Qty")}</label>
                                      <input
                                        type="number"
                                        value={s.frentesDeObra[0].quantidadeItens}
                                        onChange={(e) => {
                                          const listFo = [...s.frentesDeObra];
                                          listFo[0].quantidadeItens = parseFloat(e.target.value) || 0;
                                          updateServicoField(msIndex, sIndex, "frentesDeObra", listFo);
                                        }}
                                        className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded p-1 text-[11px] text-slate-700 font-mono"
                                      />
                                    </div>
 
                                    <div className="flex flex-col gap-0.5">
                                      <label className="text-[7px] uppercase font-bold text-slate-400">{t("Mês Conclusão", "End Month")}</label>
                                      <input
                                        type="number"
                                        value={s.frentesDeObra[0].numeroMesConclusao || 1}
                                        onChange={(e) => {
                                          const listFo = [...s.frentesDeObra];
                                          listFo[0].numeroMesConclusao = parseInt(e.target.value) || 1;
                                          updateServicoField(msIndex, sIndex, "frentesDeObra", listFo);
                                        }}
                                        className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded p-1 text-[11px] text-slate-700 font-mono"
                                      />
                                    </div>
                                  </div>
                                </div>
 
                              </div>
                            ))}
 
                            <button
                              onClick={() => addServico(msIndex)}
                              className="w-full flex items-center justify-center gap-1 border border-dashed border-slate-300 hover:border-blue-500 hover:bg-blue-50/20 text-slate-500 hover:text-blue-600 rounded-lg py-2 transition-all text-xs font-semibold cursor-pointer"
                            >
                              <Plus className="w-3.5 h-3.5" />
                              {t("Adicionar Item de Serviço", "Add Service Item")}
                            </button>
                          </div>
 
                        </div>
                      ))}
                    </div>
 
                    <div className="flex gap-3 pt-2">
                      <button
                        onClick={addMacroservico}
                        className="flex-grow flex items-center justify-center gap-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 hover:border-slate-300 rounded-xl py-3 transition-all text-xs text-slate-700 font-bold cursor-pointer"
                      >
                        <Plus className="w-4 h-4 text-blue-600" />
                        {t("Adicionar Novo Macrosserviço", "Add New Macroservice")}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Real-time JSON code output - 5 columns */}
                <div className="lg:col-span-5 flex flex-col gap-6">
                  <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 flex-grow flex flex-col min-h-[500px]">
                    <div className="flex justify-between items-center border-b border-slate-800 pb-3 mb-4 shrink-0">
                      <div>
                        <h4 className="font-bold text-white text-xs">{t("Visualização do Payload JSON", "JSON Payload Live View")}</h4>
                        <span className="text-[10px] text-slate-400 font-mono">Format: JSON_PO_{payloadType}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {needsAuth ? (
                          <button
                            onClick={handleLogin}
                            disabled={isLoggingIn}
                            className="text-[10px] px-2 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-600/30 hover:border-blue-500/50 rounded-lg transition-colors flex items-center gap-1.5"
                          >
                            <Cloud className="w-3 h-3" />
                            {isLoggingIn ? "..." : t("Conectar Drive", "Connect Drive")}
                          </button>
                        ) : (
                          <>
                            <button
                              onClick={handleLoadFromDrive}
                              disabled={driveLoading}
                              className="p-1.5 bg-slate-950 hover:bg-slate-850 text-slate-400 hover:text-white border border-slate-800 hover:border-slate-750 rounded-lg transition-colors flex items-center gap-1"
                              title={t("Carregar do Drive", "Load from Drive")}
                            >
                              <DownloadCloud className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={handleSaveToDrive}
                              disabled={driveLoading}
                              className="p-1.5 bg-slate-950 hover:bg-slate-850 text-slate-400 hover:text-white border border-slate-800 hover:border-slate-750 rounded-lg transition-colors flex items-center gap-1"
                              title={t("Salvar no Drive", "Save to Drive")}
                            >
                              <Cloud className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={handleLogout}
                              className="p-1.5 bg-slate-950 hover:bg-red-950/30 text-slate-400 hover:text-red-400 border border-slate-800 hover:border-red-900/50 rounded-lg transition-colors text-[10px]"
                              title={t("Desconectar", "Disconnect")}
                            >
                              Logout
                            </button>
                          </>
                        )}
                        <button
                          onClick={() => {
                            const cleanedPayload = JSON.parse(JSON.stringify(payload));
                            cleanedPayload.macroservicos.forEach((ms: any) => {
                              ms.servicos.forEach((s: any) => {
                                if (payloadType === "PLE") {
                                  delete s.parcelas;
                                } else {
                                  delete s.evento;
                                }
                              });
                            });
                            copyToClipboard(JSON.stringify(cleanedPayload, null, 2));
                          }}
                          className="p-1.5 bg-slate-950 hover:bg-slate-850 text-slate-400 hover:text-white border border-slate-800 hover:border-slate-750 rounded-lg transition-colors ml-1"
                          title={t("Copiar JSON", "Copy JSON")}
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    <div className="flex-grow bg-slate-950 border border-slate-850 rounded-xl p-4 font-mono text-xs text-emerald-400 overflow-y-auto max-h-[500px] select-all">
                      <pre className="whitespace-pre-wrap leading-normal font-medium">
                        {(() => {
                          const cleanedPayload = JSON.parse(JSON.stringify(payload));
                          cleanedPayload.macroservicos.forEach((ms: any) => {
                            ms.servicos.forEach((s: any) => {
                              if (payloadType === "PLE") {
                                delete s.parcelas;
                              } else {
                                delete s.evento;
                              }
                            });
                          });
                          return JSON.stringify(cleanedPayload, null, 2);
                        })()}
                      </pre>
                    </div>

                    <div className="mt-4 pt-4 border-t border-slate-800 shrink-0">
                      <button
                        onClick={loadPayloadToTester}
                        className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-750 active:scale-98 text-white font-bold py-3 px-4 rounded-xl transition-all text-xs shadow-md cursor-pointer"
                      >
                        <Send className="w-4 h-4" />
                        {t("Enviar para o Testador de API", "Load Payload to API Tester")}
                      </button>
                      <p className="text-[10px] text-slate-400 mt-2 text-center">
                        {t(
                          "Envia esta estrutura de planilha orçamentária montada diretamente para as chamadas de teste simuladas.",
                          "Loads this budget structure directly into the live sandbox/API testing tool."
                        )}
                      </p>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Screen 3: API Tester */}
            {activeTab === "tester" && (
              <motion.div
                key="tester"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="grid grid-cols-1 lg:grid-cols-12 gap-6"
              >
                {/* Configuration Panel - 5 columns */}
                <div className="lg:col-span-5 space-y-6">
                  <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-5">
                    <div>
                      <h3 className="font-bold text-slate-900 text-base">{t("Configurar Requisição", "Configure API Call")}</h3>
                      <p className="text-xs text-slate-500 mt-1">{t("Defina os parâmetros, cabeçalhos e credenciais da API", "Specify endpoint, path parameters, and headers")}</p>
                    </div>

                    {/* Endpoint Selector */}
                    <div className="space-y-2">
                      <label className="text-[10px] uppercase font-bold text-slate-450">{t("Serviço / Endpoint", "Service / Endpoint")}</label>
                      <div className="flex flex-col gap-2">
                        <button
                          onClick={() => setSelectedEndpoint("login")}
                          className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-bold flex items-center gap-2 border transition-all cursor-pointer ${
                            selectedEndpoint === "login"
                              ? "bg-blue-50/70 text-blue-600 border-blue-200"
                              : "bg-slate-50 text-slate-600 border-slate-100 hover:bg-slate-100"
                          }`}
                        >
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-blue-100 text-blue-700 font-mono">POST</span>
                          <span>{t("IDP: Obter Token de Usuário", "IDP: User Authentication")}</span>
                        </button>

                        <button
                          onClick={() => setSelectedEndpoint("get_submetas")}
                          className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-bold flex items-center gap-2 border transition-all cursor-pointer ${
                            selectedEndpoint === "get_submetas"
                              ? "bg-blue-50/70 text-blue-600 border-blue-200"
                              : "bg-slate-50 text-slate-600 border-slate-100 hover:bg-slate-100"
                          }`}
                        >
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-emerald-100 text-emerald-700 font-mono">GET</span>
                          <span>{t("projeto-basico: Consultar Submetas", "Consult Subgoals List")}</span>
                        </button>

                        <button
                          onClick={() => setSelectedEndpoint("post_po")}
                          className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-bold flex items-center gap-2 border transition-all cursor-pointer ${
                            selectedEndpoint === "post_po"
                              ? "bg-blue-50/70 text-blue-600 border-blue-200"
                              : "bg-slate-50 text-slate-600 border-slate-100 hover:bg-slate-100"
                          }`}
                        >
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-blue-100 text-blue-700 font-mono">POST</span>
                          <span>{t("projeto-basico: Enviar Planilha", "Send Budget Worksheet")}</span>
                        </button>
                        
                        <button
                          onClick={() => setSelectedEndpoint("consultar_proposta")}
                          className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-bold flex items-center gap-2 border transition-all cursor-pointer ${
                            selectedEndpoint === "consultar_proposta"
                              ? "bg-blue-50/70 text-blue-600 border-blue-200"
                              : "bg-slate-50 text-slate-600 border-slate-100 hover:bg-slate-100"
                          }`}
                        >
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-emerald-100 text-emerald-700 font-mono">GET</span>
                          <span>{t("voluntarias: Consultar Proposta (CSV)", "Consult Proposal (CSV)")}</span>
                        </button>
                      </div>
                    </div>

                    {/* Environment */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] uppercase font-bold text-slate-455">{t("Ambiente", "Environment")}</label>
                        <select
                          value={testerProps.env}
                          onChange={(e: any) => setTesterProps({ ...testerProps, env: e.target.value })}
                          className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-2 text-xs text-slate-700 font-semibold"
                        >
                          <option value="homologacao">{t("Homologação (hom4)", "Homologation (hom4)")}</option>
                          <option value="producao">{t("Produção", "Production")}</option>
                        </select>
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] uppercase font-bold text-slate-455">{t("Ano Proposta", "Proposal Year")}</label>
                        <input
                          type="text"
                          value={testerProps.anoproposta}
                          onChange={(e) => setTesterProps({ ...testerProps, anoproposta: e.target.value })}
                          className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-2 text-xs text-slate-700 font-mono font-semibold"
                        />
                      </div>
                    </div>

                    {/* Proposal parameters */}
                    {selectedEndpoint !== "consultar_proposta" && (
                      <div className="grid grid-cols-3 gap-3">
                        <div className="flex flex-col gap-1">
                          <label className="text-[9px] uppercase font-bold text-slate-455" title="Número da proposta">{t("Nº Proposta", "Proposal #")}</label>
                          <input
                            type="text"
                            value={testerProps.nrproposta}
                            onChange={(e) => setTesterProps({ ...testerProps, nrproposta: e.target.value })}
                            className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-2 text-xs text-slate-700 font-mono font-semibold"
                          />
                          <span className="text-[8px] text-slate-400 font-sans mt-0.5">
                            {t("999 p/ erro 400", "999 for 400 err")}
                          </span>
                        </div>

                        <div className="flex flex-col gap-1">
                          <label className="text-[9px] uppercase font-bold text-slate-455" title="Número da meta">{t("Nº Meta", "Meta #")}</label>
                          <input
                            type="text"
                            value={testerProps.nrmeta}
                            onChange={(e) => setTesterProps({ ...testerProps, nrmeta: e.target.value })}
                            className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-2 text-xs text-slate-700 font-mono font-semibold"
                          />
                        </div>

                        <div className="flex flex-col gap-1">
                          <label className="text-[9px] uppercase font-bold text-slate-455" title="Número da submeta">{t("Nº Submeta", "Submeta #")}</label>
                          <input
                            type="text"
                            value={testerProps.nrsubmeta}
                            onChange={(e) => setTesterProps({ ...testerProps, nrsubmeta: e.target.value })}
                            className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-2 text-xs text-slate-700 font-mono font-semibold"
                          />
                        </div>
                      </div>
                    )}
                    
                    {selectedEndpoint === "consultar_proposta" && (
                      <div className="grid grid-cols-1 gap-3">
                        <div className="flex flex-col gap-1">
                          <label className="text-[9px] uppercase font-bold text-slate-455">{t("ID Parlamentar (Autor Emenda)", "Politician ID (Author)")}</label>
                          <input
                            type="text"
                            value={testerProps.idParlamentar}
                            onChange={(e) => setTesterProps({ ...testerProps, idParlamentar: e.target.value })}
                            className="bg-slate-50 border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-2 text-xs text-slate-700 font-mono font-semibold"
                            placeholder="ex: 1234"
                          />
                        </div>
                      </div>
                    )}

                    {/* Login-specific form fields */}
                    {selectedEndpoint === "login" && (
                      <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                        <span className="text-[10px] uppercase font-bold text-blue-600 block">{t("Credenciais IDP Simulado", "Simulated IDP Credentials")}</span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div className="flex flex-col gap-1">
                            <label className="text-[9px] uppercase font-bold text-slate-500">CPF do Convenente</label>
                            <input
                              type="text"
                              value={testerProps.cpf}
                              onChange={(e) => setTesterProps({ ...testerProps, cpf: e.target.value })}
                              placeholder="111.222.333-44"
                              className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-1.5 text-xs text-slate-700 font-mono font-semibold"
                            />
                          </div>
                          <div className="flex flex-col gap-1">
                            <label className="text-[9px] uppercase font-bold text-slate-500">Senha</label>
                            <input
                              type="password"
                              value={testerProps.password}
                              onChange={(e) => setTesterProps({ ...testerProps, password: e.target.value })}
                              className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-1.5 text-xs text-slate-700 font-semibold"
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Double Authentication credentials panel */}
                    {selectedEndpoint !== "login" && (
                      <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] uppercase font-bold text-blue-600">{t("Cabeçalhos de Autenticação", "Authentication Headers")}</span>
                          <button
                            onClick={() => {
                              setTesterProps(prev => ({
                                ...prev,
                                userToken: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c3VhcmlvIjoi${prev.cpf.replace(/\D/g,"")}IiwicGVyZmlsIjpbIk9wZXJhZG9yIEZpbmFinclpYXBvciJ9.sig`
                              }));
                            }}
                            className="text-[9px] text-blue-500 hover:text-blue-600 font-bold flex items-center gap-1 transition-colors cursor-pointer"
                          >
                            <RefreshCw className="w-2.5 h-2.5 animate-spin-slow" />
                            {t("Renovar Token", "Refresh Token")}
                          </button>
                        </div>

                        <div className="space-y-2">
                          <div className="flex flex-col gap-1">
                            <label className="text-[8px] uppercase font-bold text-slate-450" title="JWT do sistema">EP-CAD (SISTEMA)</label>
                            <input
                              type="text"
                              value={testerProps.epCadToken}
                              onChange={(e) => setTesterProps({ ...testerProps, epCadToken: e.target.value })}
                              className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-1.5 text-[10px] text-slate-600 font-mono truncate"
                            />
                          </div>

                          <div className="flex flex-col gap-1">
                            <label className="text-[8px] uppercase font-bold text-slate-455" title="JWT do usuário">AUTHORIZATION BEARER (USUÁRIO)</label>
                            <input
                              type="text"
                              value={testerProps.userToken}
                              onChange={(e) => setTesterProps({ ...testerProps, userToken: e.target.value })}
                              className="bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded-lg p-1.5 text-[10px] text-slate-600 font-mono truncate"
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    <button
                      onClick={executeSimulatorRequest}
                      disabled={testerLoading}
                      className="w-full bg-blue-600 hover:bg-blue-750 disabled:opacity-50 text-white font-bold py-3 px-4 rounded-xl transition-all text-xs flex items-center justify-center gap-2 shadow-sm cursor-pointer"
                    >
                      {testerLoading ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin" />
                          <span>{t("Executando Requisição...", "Executing Request...")}</span>
                        </>
                      ) : (
                        <>
                          <Send className="w-4 h-4" />
                          <span>{t("Enviar Requisição de Teste", "Send Test Request")}</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* API Logs & Console Output - 7 columns */}
                <div className="lg:col-span-7 space-y-6">
                  
                  {/* Formatted CURL Command */}
                  <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-2.5">
                    <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider flex items-center gap-1.5">
                      <Terminal className="w-4 h-4 text-slate-600" />
                      {t("Comando CURL Correspondente", "Equivalent CURL Command")}
                    </span>
                    <div className="p-3 bg-slate-950 border border-slate-850 rounded-lg font-mono text-[11px] text-emerald-400 relative select-all overflow-x-auto whitespace-pre">
                      {`curl --location --request ${selectedEndpoint === "get_submetas" ? "GET" : "POST"} \\\n`}
                      {`  'https://${testerProps.env === "homologacao" ? "hom4.mandatarias" : "mandatarias"}.transferegov.sistema.gov.br/projeto-basico/api/v1/po?` + 
                       (selectedEndpoint === "login" 
                         ? "" 
                         : selectedEndpoint === "get_submetas"
                           ? `nrproposta=${testerProps.nrproposta}&anoproposta=${testerProps.anoproposta}' \\\n`
                           : `nrproposta=${testerProps.nrproposta}&anoproposta=${testerProps.anoproposta}&nrmeta=${testerProps.nrmeta}&nrsubmeta=${testerProps.nrsubmeta}' \\\n`
                       )}
                      {selectedEndpoint !== "login" && `  --header 'EP-CAD: ${testerProps.epCadToken.substring(0,25)}...' \\\n`}
                      {selectedEndpoint !== "login" && `  --header 'Authorization: Bearer ${testerProps.userToken.substring(0,25)}...' \\\n`}
                      {selectedEndpoint === "post_po" && `  --header 'Content-Type: application/json' \\\n  --data '${testerProps.customBody.substring(0,60).replace(/\n/g,"")}...'`}
                      {selectedEndpoint === "login" && `  --header 'Content-Type: application/json' \\\n  --data '{"cpf":"${testerProps.cpf}","senha":"****"}'`}
                    </div>
                  </div>

                  {/* Sandbox Response Output */}
                  <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm flex flex-col min-h-[300px]">
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block border-b border-slate-100 pb-3 mb-4 shrink-0">
                      {t("Retorno HTTP do Simulador (Sandbox)", "Simulator HTTP Response (Sandbox)")}
                    </span>

                    {testerStatus !== null ? (
                      <div className="flex-grow flex flex-col gap-4">
                        <div className="flex items-center gap-3">
                          <span className={`px-2.5 py-1 rounded text-xs font-mono font-bold ${
                            testerStatus >= 200 && testerStatus < 300
                              ? "bg-green-50 text-green-700 border border-green-200"
                              : "bg-red-50 text-red-700 border border-red-200"
                          }`}>
                            HTTP {testerStatus}
                          </span>
                          <span className="text-xs text-slate-500 font-medium">
                            {testerStatus === 201 ? "Created" : testerStatus === 200 ? "OK" : testerStatus === 400 ? "Bad Request" : testerStatus === 401 ? "Unauthorized" : "Server Error"}
                          </span>
                        </div>

                        {/* Interactive Business explanation of return */}
                        {testerExplain && (
                          <div className="p-3.5 bg-blue-50/50 rounded-xl border border-blue-100 flex gap-2.5 items-start">
                            <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                            <p className="text-xs text-slate-600 leading-relaxed">
                              {testerExplain}
                            </p>
                          </div>
                        )}

                        <div className="flex-grow bg-slate-950 border border-slate-850 rounded-xl p-4 font-mono text-xs text-emerald-400 overflow-y-auto max-h-[300px]">
                          <pre>{JSON.stringify(testerResponse, null, 2)}</pre>
                        </div>
                      </div>
                    ) : (
                      <div className="flex-grow flex flex-col justify-center items-center gap-3 text-slate-400 py-10">
                        <Cpu className="w-10 h-10 animate-pulse text-slate-300" />
                        <p className="text-xs text-slate-400 font-medium">
                          {t(
                            "Configure os parâmetros e envie a chamada de teste para visualizar os logs.",
                            "Set the configurations and click 'Send' to inspect logs here."
                          )}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

              </motion.div>
            )}

            {/* Screen 4: AI Advisor */}
            {activeTab === "advisor" && (
              <motion.div
                key="advisor"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="grid grid-cols-1 lg:grid-cols-12 gap-6"
              >
                {/* Information panel & FAQ helper chips - 4 columns */}
                <div className="lg:col-span-4 space-y-4">
                  <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-4">
                    <span className="text-xs font-bold text-slate-900 uppercase tracking-wider block border-b border-slate-100 pb-2">
                      {t("Dúvidas Frequentes", "Common Inquiries")}
                    </span>
                    <p className="text-xs text-slate-500 leading-relaxed font-medium">
                      {t(
                        "Clique em qualquer uma das dúvidas preparadas abaixo para obter respostas imediatas com base no Manual de Integração v1.3:",
                        "Click any of the questions below to get instant answers based strictly on the integration guidelines:"
                      )}
                    </p>

                    <div className="flex flex-col gap-2">
                      <button
                        onClick={() => sendAdvisorMessage("Como posso obter o token EP-CAD do sistema externo no Transferegov?")}
                        className="text-left p-3 bg-slate-50 hover:bg-blue-50/50 hover:text-blue-600 text-slate-700 border border-slate-100 hover:border-blue-100 rounded-xl text-xs font-semibold leading-relaxed transition-all cursor-pointer"
                      >
                        ❓ {t("Como solicitar meu token EP-CAD?", "How to request EP-CAD token?")}
                      </button>

                      <button
                        onClick={() => sendAdvisorMessage("Qual é a diferença estrutural entre planilhas PLE e planilhas BM?")}
                        className="text-left p-3 bg-slate-50 hover:bg-blue-50/50 hover:text-blue-600 text-slate-700 border border-slate-100 hover:border-blue-100 rounded-xl text-xs font-semibold leading-relaxed transition-all cursor-pointer"
                      >
                        ❓ {t("Diferença no envio de PLE e BM?", "Differences between PLE & BM?")}
                      </button>

                      <button
                        onClick={() => sendAdvisorMessage("O que significa e como resolver o erro: 'Não é possível adicionar a Planilha Orçamentaria via API pois a opção Receber dados não está selecionada'?")}
                        className="text-left p-3 bg-slate-50 hover:bg-blue-50/50 hover:text-blue-600 text-slate-700 border border-slate-100 hover:border-blue-100 rounded-xl text-xs font-semibold leading-relaxed transition-all cursor-pointer"
                      >
                        ❓ {t("Erro da opção 'Receber via API?'", "How to fix 'Receber via API?' error")}
                      </button>

                      <button
                        onClick={() => sendAdvisorMessage("Como funciona a autenticação no IDP do governo para obter o token de usuário convenente?")}
                        className="text-left p-3 bg-slate-50 hover:bg-blue-50/50 hover:text-blue-600 text-slate-700 border border-slate-100 hover:border-blue-100 rounded-xl text-xs font-semibold leading-relaxed transition-all cursor-pointer"
                      >
                        ❓ {t("Fluxo de login de CPF convenente", "User CPF login flow")}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Conversational Window - 8 columns */}
                <div className="lg:col-span-8 flex flex-col bg-white border border-slate-200 rounded-2xl shadow-sm min-h-[500px] overflow-hidden">
                  
                  {/* Chat Header */}
                  <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 shrink-0">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-blue-500" />
                      <div>
                        <h3 className="font-bold text-slate-900 text-xs">{t("Orientação Inteligente de Integração", "Smart Integration Guidance")}</h3>
                        <p className="text-[10px] text-slate-500 mt-0.5">{t("Powered by Gemini 3.5 Flash", "Powered by Gemini 3.5 Flash")}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setAdvisorMessages([
                        {
                          id: "init",
                          role: "assistant",
                          content: "Histórico limpo. Como posso apoiar sua integração hoje?",
                          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                        }
                      ])}
                      className="text-[10px] text-slate-400 hover:text-blue-600 font-bold transition-colors cursor-pointer"
                    >
                      {t("Limpar Chat", "Clear Chat")}
                    </button>
                  </div>

                  {/* Messages list */}
                  <div className="flex-grow p-4 overflow-y-auto space-y-4 max-h-[350px]">
                    {advisorMessages.map((msg, idx) => (
                      <div
                        key={msg.id || idx}
                        className={`flex gap-3 max-w-[85%] ${msg.role === "user" ? "ml-auto flex-row-reverse" : ""}`}
                      >
                        {/* Avatar */}
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border ${
                          msg.role === "user"
                            ? "bg-blue-500 border-blue-600 text-white font-bold"
                            : "bg-slate-100 border-slate-200 text-slate-700"
                        }`}>
                          {msg.role === "user" ? "Dev" : "Gov"}
                        </div>

                        {/* Content text */}
                        <div className={`p-3.5 rounded-xl border ${
                          msg.role === "user"
                            ? "bg-blue-500 border-transparent text-white"
                            : "bg-slate-50 border-slate-100 text-slate-800"
                        }`}>
                          <p className="text-xs leading-relaxed whitespace-pre-wrap font-sans font-medium">
                            {msg.content}
                          </p>
                          <span className={`block text-[8px] mt-1.5 text-right font-mono ${
                            msg.role === "user" ? "text-blue-200" : "text-slate-450"
                          }`}>
                            {msg.timestamp}
                          </span>
                        </div>
                      </div>
                    ))}

                    {advisorLoading && (
                      <div className="flex gap-3 max-w-[80%]">
                        <div className="w-7 h-7 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 flex items-center justify-center animate-pulse">
                          Gov
                        </div>
                        <div className="p-3 bg-slate-50 border border-slate-100 rounded-xl flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                          <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                          <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Input field */}
                  <div className="p-4 border-t border-slate-100 bg-slate-50/50 shrink-0">
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        sendAdvisorMessage();
                      }}
                      className="flex gap-2"
                    >
                      <input
                        type="text"
                        value={advisorInput}
                        onChange={(e) => setAdvisorInput(e.target.value)}
                        placeholder={t("Pergunte sobre BDI, fontes de insumo, PLE, BM, erros...", "Ask about BDI, input sources, PLE, BM, errors...")}
                        className="flex-grow bg-white border border-slate-200 focus:border-blue-500 focus:outline-none rounded-xl px-4 py-2.5 text-xs text-slate-700 font-medium font-semibold"
                        disabled={advisorLoading}
                      />
                      <button
                        type="submit"
                        disabled={advisorLoading || !advisorInput.trim()}
                        className="bg-blue-600 hover:bg-blue-750 disabled:opacity-40 text-white p-2.5 rounded-xl transition-all shadow-sm cursor-pointer"
                      >
                        <Send className="w-4.5 h-4.5" />
                      </button>
                    </form>
                  </div>

                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </div>

      </div>

      {/* Elegant minimalist footer */}
      <footer className="border-t border-slate-100 py-6 px-6 bg-slate-50 select-none text-center">
        <p className="text-[10px] text-slate-400 font-semibold tracking-wide">
          {t(
            "Este é um assistente interativo e simulador local de apoio à integração com o portal Transferegov.br. Desenvolvido para facilitar integrações em sistemas privados.",
            "This is an interactive support helper and local simulator for integrating with Transferegov.br APIs. Built for Brazilian private developers."
          )}
        </p>
      </footer>
    </div>
  );
}
