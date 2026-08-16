"""Prompts: agentes especializados por tipo de documento.

Cada prompt é um "agente virtual" que instrui o LLM sobre:
- Qual tipo de documento redigir
- Quais normas seguir (Manual de Redação 3ª edição, 2018)
- Qual estrutura obrigatória
- Como usar as tools disponíveis

Na 3ª edição do Manual, "memorando" e "aviso" foram abolidos.
Tudo é "ofício" agora (padrão ofício).
"""

from __future__ import annotations

from fastmcp.prompts import Message


def redator_oficio(
    destinatario: str,
    cargo_destinatario: str,
    assunto: str,
    orgao_remetente: str = "",
) -> list[Message]:
    """Redator de Ofício — comunicação oficial (padrão ofício, 3ª edição).

    Na 3ª edição do Manual de Redação (2018), memorando e aviso foram
    ABOLIDOS. O ofício é agora o ÚNICO tipo de comunicação oficial,
    usado tanto para comunicação interna quanto externa.

    Args:
        destinatario: Nome do destinatário.
        cargo_destinatario: Cargo (ex: "Secretário de Fazenda").
        assunto: Tema do ofício.
        orgao_remetente: Órgão que envia (opcional).
    """
    return [
        Message(
            f"""Preciso redigir um OFÍCIO oficial (padrão ofício — Manual de Redação 3ª edição).

Para: {destinatario} — {cargo_destinatario}
De: {orgao_remetente if orgao_remetente else "[informar órgão remetente]"}
Assunto: {assunto}

Instruções (Manual de Redação da Presidência, 3ª edição, 2018):
1. Consulte o template de ofício (resource template://oficio)
2. Consulte as normas de redação oficial (resource normas://manual_redacao)
3. Numeração: OFÍCIO Nº X/ANO/SIGLAS (siglas da menor para a maior hierarquia)
4. Use a tool consultar_pronome_tratamento() para o vocativo correto
   - "Excelentíssimo" APENAS para Presidente da República, do Congresso e do STF
   - Demais autoridades: "Senhor/Senhora + Cargo"
   - NUNCA usar "Digníssimo" ou "Ilustríssimo" (abolidos)
5. Use a tool formatar_data_extenso() para a data
   - Formato: "Cidade, dia de mês de ano." (sem sigla da UF)
6. Estrutura: identificação > endereçamento > vocativo > texto > fecho > assinatura
7. Fecho (resource normas://fechos):
   - "Respeitosamente," — para autoridade superior
   - "Atenciosamente," — para mesma hierarquia ou inferior
   - São os ÚNICOS dois fechos admitidos
8. Fonte: Calibri ou Carlito, tamanho 12
9. Margens: esquerda 3cm, direita 1,5cm, superior e inferior 2cm
10. Linguagem impessoal, concisa, objetiva — evitar gerúndio excessivo"""
        ),
        Message(
            "Entendido. Vou redigir o ofício seguindo rigorosamente o Manual de "
            "Redação da Presidência da República, 3ª edição. "
            "Consultando template, pronomes e normas...",
            role="assistant",
        ),
    ]


def redator_despacho(assunto: str, contexto: str = "") -> list[Message]:
    """Redator de Despacho — decisão administrativa sobre processo ou requerimento.

    Use este prompt para redigir despachos que aprovam, indeferem,
    encaminham ou determinam providências sobre processos administrativos.

    Args:
        assunto: O que o despacho deve decidir/encaminhar.
        contexto: Informações adicionais (número do processo, setor, etc.).
    """
    return [
        Message(
            f"""Preciso redigir um DESPACHO oficial sobre: {assunto}

Contexto adicional: {contexto if contexto else "Nenhum fornecido."}

Instruções (Manual de Redação da Presidência, 3ª edição, 2018):
1. Consulte o template de despacho (resource template://despacho)
2. Consulte as normas de redação oficial (resource normas://manual_redacao)
3. Use a tool formatar_data_extenso() para a data atual
   - Formato: "Cidade, dia de mês de ano." (sem sigla da UF)
4. Estrutura: cabeçalho > referência ao processo > fundamentação > decisão
5. O despacho é DECISÓRIO — deve conter determinação clara
6. Verbos diretos: "Aprovo", "Indefiro", "Encaminho", "Determino"
7. Evitar gerúndio: "Encaminho" (NÃO "Encaminhando")
8. Linguagem impessoal, concisa, objetiva
9. Parágrafos curtos (3-5 linhas)
10. Despacho NÃO tem fecho obrigatório"""
        ),
        Message(
            "Entendido. Vou redigir o despacho seguindo as normas do Manual de "
            "Redação da Presidência da República. Consultando o template e as normas...",
            role="assistant",
        ),
    ]


def redator_portaria(
    assunto: str,
    autoridade: str = "",
    fundamentacao: str = "",
) -> list[Message]:
    """Redator de Portaria — ato normativo de autoridade administrativa.

    Use este prompt para redigir portarias que nomeiam, designam,
    regulamentam ou determinam providências administrativas.

    Args:
        assunto: O que a portaria determina.
        autoridade: Autoridade que assina (ex: "Secretário de Administração").
        fundamentacao: Base legal (ex: "Lei nº 8.112/1990, art. 67").
    """
    return [
        Message(
            f"""Preciso redigir uma PORTARIA oficial.

Autoridade: {autoridade if autoridade else "[informar autoridade]"}
Assunto: {assunto}
Fundamentação legal: {fundamentacao if fundamentacao else "[informar base legal]"}

Instruções (Manual de Redação da Presidência, 3ª edição, 2018):
1. Consulte o template de portaria (resource template://portaria)
2. Epígrafe em CAIXA ALTA: "PORTARIA Nº X, DE [DATA EM MAIÚSCULAS]"
3. Preâmbulo: "O [AUTORIDADE], no uso das atribuições que lhe confere..."
4. CONSIDERANDO (se necessário): justificativas — cada um seguido de ";"
5. RESOLVE:
6. Artigos numerados: Art. 1º, Art. 2º, Art. 3º...
   - Cada artigo = uma disposição
   - Parágrafos: § 1º, § 2º... (parágrafo único quando for só um)
   - Incisos: I, II, III... (alíneas: a), b), c)...)
7. Último artigo: vigência ("entra em vigor na data de sua publicação")
8. Portaria NÃO tem fecho (sem "Atenciosamente")
9. Linguagem imperativa e normativa
10. Use a tool formatar_data_extenso() para a data"""
        ),
        Message(
            "Vou redigir a portaria com a estrutura normativa obrigatória. "
            "Consultando template e fundamentação...",
            role="assistant",
        ),
    ]


def redator_parecer(
    processo: str,
    consulta: str,
    area: str = "jurídico",
) -> list[Message]:
    """Redator de Parecer — manifestação técnica ou jurídica sobre consulta.

    Use este prompt para redigir pareceres técnicos, jurídicos ou
    administrativos em resposta a consultas formais.

    Args:
        processo: Número do processo ou referência.
        consulta: Pergunta ou tema a ser analisado.
        area: Área do parecer: "jurídico", "técnico", "contábil" (default: jurídico).
    """
    return [
        Message(
            f"""Preciso redigir um PARECER {area.upper()} oficial.

Processo/Referência: {processo}
Consulta: {consulta}
Área: {area}

Instruções (Manual de Redação da Presidência, 3ª edição, 2018):
1. Consulte o template de parecer (resource template://parecer)
2. Estrutura obrigatória:
   - EMENTA: resumo em 2-3 linhas
   - I — DO RELATÓRIO: fatos e histórico
   - II — DA FUNDAMENTAÇÃO: análise técnica/jurídica
   - III — DA CONCLUSÃO: resposta objetiva à consulta
3. Cite legislação relevante
4. Mantenha objetividade — parecer OPINA, não decide
5. Fecho: "É o parecer, s.m.j." (salvo melhor juízo)
6. Use a tool formatar_data_extenso()
7. Data: "Cidade, dia de mês de ano." (sem sigla da UF)"""
        ),
        Message(
            f"Vou redigir o parecer {area} com a estrutura técnica adequada. "
            "Consultando template e normas...",
            role="assistant",
        ),
    ]


def redator_nota_tecnica(
    assunto: str,
    dados: str = "",
) -> list[Message]:
    """Redator de Nota Técnica — análise técnica com dados e evidências.

    Use este prompt para redigir notas técnicas que fundamentam
    decisões com dados, análises e recomendações. Pode consultar
    dados em tempo real do IBGE, Bacen e Portal da Transparência.

    Args:
        assunto: Tema da nota técnica.
        dados: Dados ou fontes a serem consultadas (opcional).
    """
    return [
        Message(
            f"""Preciso redigir uma NOTA TÉCNICA.

Assunto: {assunto}
Dados/fontes disponíveis: {dados if dados else "Consultar APIs disponíveis (IBGE, Bacen, etc.)"}

Instruções (Manual de Redação da Presidência, 3ª edição, 2018):
1. Consulte o template de nota técnica (resource template://nota_tecnica)
2. Se houver dados relevantes, use as tools do mcp-brasil para consultar:
   - IBGE: indicadores, população, PIB
   - Bacen: câmbio, Selic, inflação
   - Transparência: contratos, despesas
3. Estrutura:
   - ASSUNTO
   - 1. INTRODUÇÃO: contextualização
   - 2. ANÁLISE: dados e argumentos (com números reais se possível)
   - 3. CONCLUSÃO E RECOMENDAÇÕES
4. Inclua dados concretos sempre que possível
5. Cite fontes de dados utilizadas
6. Nota técnica NÃO tem fecho obrigatório
7. Use a tool formatar_data_extenso()"""
        ),
        Message(
            "Vou redigir a nota técnica. Posso consultar dados em tempo real do "
            "IBGE, Banco Central e Portal da Transparência para fundamentar a análise. "
            "Vou verificar quais dados estão disponíveis...",
            role="assistant",
        ),
    ]
