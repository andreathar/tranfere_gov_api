"""Constants for the Redator Oficial feature.

Based on Manual de Redação da Presidência da República, 3ª edição (2018).
"""

MESES = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

TIPOS_DOCUMENTO = [
    "oficio",
    "despacho",
    "portaria",
    "parecer",
    "nota_tecnica",
    "ata",
    "exposicao_motivos",
]

PREFIXOS_DOCUMENTO: dict[str, str] = {
    "oficio": "OFÍCIO",
    "despacho": "Despacho",
    "portaria": "PORTARIA",
    "parecer": "Parecer",
    "nota_tecnica": "Nota Técnica",
    "ata": "Ata",
    "exposicao_motivos": "EM",
    # Legados (abolidos na 3ª edição, mas aceitos para retrocompatibilidade)
    "memorando": "OFÍCIO",
    "aviso": "OFÍCIO",
}

# Pronomes de tratamento — Manual de Redação 3ª edição (2018)
#
# Regra: "Excelentíssimo" é reservado APENAS para os 3 Chefes de Poder.
# Demais autoridades: "Senhor/Senhora + Cargo".
# DD (Digníssimo) e Ilmo. (Ilustríssimo) foram ABOLIDOS.
PRONOMES_TRATAMENTO: dict[str, dict[str, str]] = {
    # --- Chefes de Poder (vocativo "Excelentíssimo") ---
    "presidente da república": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Excelentíssimo Senhor Presidente da República,",
        "abreviatura": "Não se usa",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "presidente do congresso nacional": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Excelentíssimo Senhor Presidente do Congresso Nacional,",
        "abreviatura": "Não se usa",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "presidente do supremo tribunal federal": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Excelentíssimo Senhor Presidente do Supremo Tribunal Federal,",
        "abreviatura": "Não se usa",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    # --- Vossa Excelência (vocativo "Senhor + Cargo") ---
    "vice-presidente da república": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Vice-Presidente da República,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "ministro de estado": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Ministro,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "ministro": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Ministro,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "secretário-executivo": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Secretário-Executivo,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "embaixador": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Embaixador,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "senador": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Senador,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "deputado federal": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Deputado,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "deputado": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Deputado,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "vereador": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Vereador,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "governador": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Governador,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "prefeito": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Prefeito,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "secretário": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Secretário,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "desembargador": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Desembargador,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "juiz": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Juiz,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "procurador-geral": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor Procurador-Geral,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "general": {
        "tratamento": "Vossa Excelência",
        "vocativo": "Senhor General,",
        "abreviatura": "V. Exa.",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    # --- Vossa Senhoria (vocativo "Senhor + Cargo") ---
    "coronel": {
        "tratamento": "Vossa Senhoria",
        "vocativo": "Senhor Coronel,",
        "abreviatura": "V. Sa.",
        "enderecamento": "Ao Senhor",
    },
    "diretor": {
        "tratamento": "Vossa Senhoria",
        "vocativo": "Senhor Diretor,",
        "abreviatura": "V. Sa.",
        "enderecamento": "Ao Senhor",
    },
    "coordenador": {
        "tratamento": "Vossa Senhoria",
        "vocativo": "Senhor Coordenador,",
        "abreviatura": "V. Sa.",
        "enderecamento": "Ao Senhor",
    },
    "chefe": {
        "tratamento": "Vossa Senhoria",
        "vocativo": "Senhor Chefe,",
        "abreviatura": "V. Sa.",
        "enderecamento": "Ao Senhor",
    },
    # --- Vossa Magnificência ---
    "reitor": {
        "tratamento": "Vossa Magnificência",
        "vocativo": "Magnífico Reitor,",
        "abreviatura": "V. Maga.",
        "enderecamento": "Ao Magnífico Senhor Reitor",
    },
}
