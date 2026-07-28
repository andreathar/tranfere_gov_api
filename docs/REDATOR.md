# Redator Oficial de Documentos

Geração automatizada de documentos oficiais seguindo o Manual de Redação da
Presidência da República, 3ª edição (2018). Módulo `src/redator_transferegov.py`.

---

## Visão Geral

O Redator Oficial combina dados reais do PostgreSQL (planos de ação, deputados,
municípios) com as normas de redação oficial para produzir documentos formatados.
Os documentos são gerados em texto simples (.txt) e salvos automaticamente na
estrutura de diretórios `src/redator/`.

**Referência normativa**: Manual de Redação da Presidência da República, 3ª
edição (Brasília: Casa Civil, 2018). Todas as regras de formatação, pronomes de
tratamento, fechos e numeração seguem estritamente esse manual.

**Linha de comando**:
```bash
python3 src/redator_transferegov.py <comando> [opções]
```

---

## Tipos de Documento

O sistema suporta 6 comandos principais:

| Comando | Descrição | Subpasta de saída |
|---------|-----------|-------------------|
| `nota-tecnica` | Nota técnica sobre impedimentos de planos de ação | `src/redator/notas_tecnicas/` |
| `oficio` | Ofício oficial com numeração e vocativo | `src/redator/oficios/` |
| `parecer` | Parecer técnico, jurídico ou contábil | `src/redator/pareceres/` |
| `despacho` | Despacho administrativo decisório | `src/redator/despachos/` |
| `validar` | Validação de documento existente contra o manual | (sem saída de arquivo) |
| `listar-tipos` | Lista todos os tipos de documento suportados | (sem saída de arquivo) |

**Tipos internos** (dicionário `TIPOS_DOCUMENTO`):

| Chave | Nome | Prefixo |
|-------|------|---------|
| `oficio` | Ofício | OFÍCIO |
| `despacho` | Despacho | Despacho |
| `portaria` | Portaria | PORTARIA |
| `parecer` | Parecer | Parecer |
| `nota_tecnica` | Nota Técnica | NOTA TÉCNICA |
| `ata` | Ata | ATA |

---

## Comandos e Flags

### nota-tecnica

Gera nota técnica sobre impedimentos de planos de ação, com dados do PostgreSQL.

```bash
python3 src/redator_transferegov.py nota-tecnica [opções]
```

| Flag | Tipo | Obrigatório | Default | Descrição |
|------|------|-------------|---------|-----------|
| `--parlamentar` | str | Não | (geral) | Nome do parlamentar (filtro parcial, case-insensitive) |
| `--ano` | int | Não | (todos) | Ano de exercício (filtro) |
| `--cidade` | str | Não | `Brasília` | Cidade para formatação da data |
| `--orgao` | str | Não | `Secretaria de Planejamento` | Órgão emissor |
| `--autoridade` | str | Não | `Secretário de Planejamento` | Autoridade que assina o documento |
| `--output` / `-o` | str | Não | (automático) | Caminho do arquivo de saída |

**Estrutura do documento gerado**:
1. Cabeçalho (`NOTA TÉCNICA`)
2. Assunto, Data, Órgão
3. Seção 1 - Introdução
4. Seção 2 - Análise (2.1 Panorama Geral, 2.2 Planos do Parlamentar, 2.3 Concentração por UF)
5. Seção 3 - Conclusão e Recomendações (I a IV)
6. Data por extenso + assinatura

### oficio

Gera ofício oficial seguindo o Manual de Redação 3ª edição.

```bash
python3 src/redator_transferegov.py oficio [opções]
```

| Flag | Tipo | Obrigatório | Default | Descrição |
|------|------|-------------|---------|-----------|
| `--dest` | str | Sim | - | Nome do destinatário |
| `--cargo` | str | Sim | - | Cargo do destinatário (usado para pronome de tratamento) |
| `--assunto` | str | Sim | - | Assunto do ofício |
| `--corpo` | str | Sim | - | Corpo do ofício (texto) |
| `--orgao` | str | Não | `Secretaria de Planejamento` | Órgão remetente |
| `--numero` | int | Não | (sequencial) | Número sequencial do ofício |
| `--cidade` | str | Não | `Brasília` | Cidade para data |
| `--output` / `-o` | str | Não | (automático) | Arquivo de saída |

**Estrutura do documento gerado**:
1. Numeração (se informada): `OFÍCIO Nº 143/2026`
2. Data por extenso
3. Vocativo (conforme cargo do destinatário)
4. Corpo do ofício (parágrafos indentados)
5. Fecho: `Respeitosamente,` (ofício é dirigido a superior)
6. Assinatura (linha + órgão)

### parecer

Gera parecer técnico, jurídico ou contábil.

```bash
python3 src/redator_transferegov.py parecer [opções]
```

| Flag | Tipo | Obrigatório | Default | Descrição |
|------|------|-------------|---------|-----------|
| `--processo` | str | Sim | - | Número do processo/referência |
| `--consulta` | str | Sim | - | Pergunta ou tema a ser analisado |
| `--area` | str | Não | `técnico` | Área do parecer (`técnico`, `jurídico`, `contábil`) |
| `--orgao` | str | Não | `Assessoria Técnica` | Órgão emissor |
| `--autoridade` | str | Não | `Assessor Técnico` | Autoridade que assina |
| `--cidade` | str | Não | `Brasília` | Cidade para data |
| `--output` / `-o` | str | Não | (automático) | Arquivo de saída |

**Estrutura do documento gerado**:
1. Cabeçalho: `PARECER TÉCNICO Nº 001/2026`
2. Processo/Referência, Data
3. Ementa
4. I - Do Relatório
5. II - Da Fundamentação (a, b, c)
6. III - Da Conclusão (`s.m.j.`)
7. Data por extenso + assinatura

### despacho

Gera despacho administrativo decisório.

```bash
python3 src/redator_transferegov.py despacho [opções]
```

| Flag | Tipo | Obrigatório | Default | Descrição |
|------|------|-------------|---------|-----------|
| `--assunto` | str | Sim | - | Assunto do despacho |
| `--texto` | str | Sim | - | Texto decisório do despacho |
| `--autoridade` | str | Não | `Secretário de Planejamento` | Autoridade que assina |
| `--orgao` | str | Não | `Secretaria de Planejamento` | Órgão emissor |
| `--cidade` | str | Não | `Brasília` | Cidade para data |
| `--output` / `-o` | str | Não | (automático) | Arquivo de saída |

**Estrutura do documento gerado**:
1. Cabeçalho: `DESPACHO`
2. Data por extenso
3. Referência (`Assunto: ...`)
4. Texto decisório
5. Assinatura (sem fecho obrigatório)

### validar

Valida um documento existente contra as normas do Manual de Redação 3ª edição.

```bash
python3 src/redator_transferegov.py validar --arquivo <caminho> --tipo <tipo>
```

| Flag | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| `--arquivo` | str | Sim | Caminho do arquivo de texto a validar |
| `--tipo` | str | Sim | Tipo do documento (chaves de `TIPOS_DOCUMENTO`) |

**Códigos de retorno**: `0` = válido, `1` = problemas encontrados ou arquivo não encontrado.

### listar-tipos

Lista todos os tipos de documento suportados com seus prefixos.

```bash
python3 src/redator_transfegov.py listar-tipos
```

**Saída exemplo**:
```
Tipos de documento suportados:

  oficio               Ofício          prefixo: OFÍCIO
  despacho             Despacho        prefixo: Despacho
  portaria             Portaria        prefixo: PORTARIA
  parecer              Parecer         prefixo: Parecer
  nota_tecnica         Nota Técnica    prefixo: NOTA TÉCNICA
  ata                  Ata             prefixo: ATA

Nota: Na 3ª edição do Manual, 'memorando' e 'aviso' foram
      abolidos — tudo é 'ofício' agora.
```

---

## Pronomes de Tratamento

Tabela completa de 27 pronomes de tratamento organizados em 4 camadas,
conforme o Manual de Redação 3ª edição (2018).

**Regra fundamental**: `Excelentíssimo` é reservado APENAS aos 3 chefes de poder.
Para todos os demais, utiliza-se `Senhor/Senhora + Cargo`. Os pronomes `DD`,
`Digníssimo`, `Ilmo.` e `Ilustríssimo` foram ABOLIDOS na 3ª edição.

### Tier 1 - Excelentíssimo (3 cargos)

| Cargo | Vocativo | Endereçamento |
|-------|----------|---------------|
| Presidente da República | Excelentíssimo Senhor Presidente da República, | A Sua Excelência o Senhor |
| Presidente do Congresso Nacional | Excelentíssimo Senhor Presidente do Congresso Nacional, | A Sua Excelência o Senhor |
| Presidente do Supremo Tribunal Federal | Excelentíssimo Senhor Presidente do Supremo Tribunal Federal, | A Sua Excelência o Senhor |

### Tier 2 - Sua Excelência (5 cargos)

| Cargo | Vocativo | Endereçamento |
|-------|----------|---------------|
| Deputado Federal | Senhor Deputado, | A Sua Excelência o Senhor |
| Deputado | Senhor Deputado, | A Sua Excelência o Senhor |
| Senador | Senhor Senador, | A Sua Excelência o Senhor |
| Secretário-Executivo | Senhor Secretário-Executivo, | A Sua Excelência o Senhor |
| Ministro | Senhor Ministro, | A Sua Excelência o Senhor |

### Tier 3 - Senhor(a) + Cargo (4 cargos)

| Cargo | Vocativo | Endereçamento |
|-------|----------|---------------|
| Governador | Senhor Governador, | Ao Senhor |
| Prefeito | Senhor Prefeito, | Ao Senhor |
| Secretário | Senhor Secretário, | Ao Senhor |
| Diretor | Senhor Diretor, | Ao Senhor |

### Tier 4 - Senhor(a) + Cargo (1 cargo)

| Cargo | Vocativo | Endereçamento |
|-------|----------|---------------|
| Coordenador | Senhor Coordenador, | Ao Senhor |

### Fallback Genérico

Quando o cargo não é encontrado na tabela, o sistema utiliza:
- Vocativo: `Senhor(a),`
- Endereçamento: `Ao(A) Senhor(a)`

**Busca**: A consulta é case-insensitive e suporta correspondência parcial.
Exemplo: buscar `"governador"` encontra `"governador"`, buscar `"deputado"`
encontra tanto `"deputado"` quanto `"deputado federal"`.

---

## Fechos

A ª edição do Manual de Redação admite APENAS dois fechos:

| Hierarquia | Fecho | Uso |
|------------|-------|-----|
| Superior | `Respeitosamente,` | Documentos dirigidos a autoridades superiores |
| Igual | `Atenciosamente,` | Documentos entre autoridades do mesmo nível |

O Redator Oficial aplica automaticamente:
- **Ofício**: `Respeitosamente,` (sempre, pois é dirigido a destinatário superior)
- **Nota técnica**: Sem fecho (termina com assinatura)
- **Parecer**: Sem fecho (termina com `s.m.j.` + assinatura)
- **Despacho**: Sem fecho obrigatório

---

## Legado - Conversão de memorando e aviso

Na 3ª edição do Manual de Redação (2018), os tipos `memorando` e `aviso` foram
abolidos. Todos os documentos anteriormente classificados como memorando ou aviso
devem ser convertidos para o formato `ofício`.

**Comportamento do sistema**:

| Tipo antigo | Tipo atual | Prefixo gerado |
|-------------|------------|----------------|
| `memorando` | `oficio` | `OFÍCIO` |
| `aviso` | `oficio` | `OFÍCIO` |

A conversão é automática em duas funções:
- `gerar_numeracao()`: converte tipo `memorando` ou `aviso` para `oficio` antes
  de gerar a numeração.
- `validar_documento()`: detecta ocorrências de `MEMORANDO`, `Memorando`, `AVISO`
  ou `Aviso` no texto e emite aviso de que devem ser substituídos por `OFÍCIO`.

---

## Validação

A função `validar_documento()` verifica um texto contra 4 regras do Manual de
Redação 3ª edição:

### 1. Data no formato numérico

**Regra**: Datas no formato `DD/MM/AAAA` não são aceitas. Deve-se utilizar o
formato por extenso (`Brasília, 27 de julho de 2026.`).

**Padrão detectado**: `\d{1,2}/\d{1,2}/\d{4}`

### 2. Pronomes abolidos

**Regra**: Os pronomes `Digníssimo`, `Ilmo.`, `Ilustríssimo` e `D.` foram
abolidos na 3ª edição. Deve-se utilizar `Senhor/Senhora + Cargo`.

**Termos detectados**: `Digníssimo`, `Ilmo.`, `Ilustríssimo`, `D.`

### 3. Gerúndio excessivo

**Regra**: O uso excessivo de gerúndio é desaconselhado. O sistema alerta quando
há mais de 3 ocorrências de terminações `-ando`, `-endo` ou `-indo`.

**Padrão detectado**: `\b\w+ando\b`, `\b\w+endo\b`, `\b\w+indo\b`

### 4. Tipos abolidos

**Regra**: Menções a `MEMORANDO`/`Memorando` e `AVISO`/`Aviso` indicam formato
desatualizado.

**Termos detectados**: `MEMORANDO`, `Memorando`, `AVISO`, `Aviso`

### Saída da validação

A função retorna uma lista de strings com os problemas encontrados. Lista vazia
indica documento válido. Cada problema é precedido de `⚠️` na saída.

**Uso via CLI**:
```bash
python3 src/redator_transferegov.py validar --arquivo "docs/nota.txt" --tipo nota_tecnica
```

**Saída** (caso válido):
```
Documento do tipo 'nota_tecnica' — válido conforme Manual de Redação 3ª edição.
```

**Saída** (caso com problemas):
```
Documento do tipo 'nota_tecnica' — 2 problema(s) encontrado(s):

  ⚠️  Data no formato numérico (DD/MM/AAAA) — usar formato por extenso
  ⚠️  Pronome 'Ilmo.' ABOLIDO na 3ª edição — usar 'Senhor/Senhora + Cargo'
```

---

## Estrutura de Saída

Os documentos gerados são salvos em `src/redator/` com a seguinte organização:

```
src/redator/
├── notas_tecnicas/
│   ├── nota_tecnica_20260725_marcos_pereira.txt
│   └── nota_tecnica_20260727_lidice_da_mata.txt
├── oficios/
│   ├── oficio_20260725_143.txt
│   └── oficio_cachoeira_paulista_impedimento.txt
├── pareceres/
│   └── (documentos gerados)
├── despachos/
│   └── (documentos gerados)
└── validados/
    └── (documentos validados)
```

### Convenções de nomenclatura

| Tipo | Padrão do nome | Exemplo |
|------|----------------|---------|
| `nota-tecnica` | `nota_tecnica_YYYYMMDD_parlamentar.txt` | `nota_tecnica_20260725_marcos_pereira.txt` |
| `oficio` | `oficio_YYYYMMDD_numero.txt` | `oficio_20260725_143.txt` |
| `parecer` | `parecer_YYYYMMDD_processo.txt` | `parecer_20260725_001-2026.txt` |
| `despacho` | `despacho_YYYYMMDD_assunto.txt` | `despacho_20260725_encaminhamento.txt` |
| Outros | `doc_YYYYMMDD_HHMMSS.txt` | `doc_20260725_143022.txt` |

**Caminho automático**: Quando `--output` não é especificado, o sistema gera
o caminho em `src/redator/<subpasta>/` com data + identificador extraído do
conteúdo do documento.

---

## Funções Utilitárias

### --data

Exibe a data atual no formato por extenso, conforme o Manual de Redação.

```bash
python3 src/redator_transferegov.py --data
```

**Saída**:
```
Brasília, 27 de julho de 2026.
```

**Regras de formatação**:
- Nome da cidade (sem sigla da UF na data)
- Dia ordinal se for 1º, cardinal sem zero à esquerda
- Mês com inicial minúscula
- Ponto-final ao término

### --pronomes

Consulta o pronome de tratamento correto para um cargo público.

```bash
python3 src/redator_transfegov.py --pronomes "Governador"
```

**Saída**:
```
Cargo:        Governador
Vocativo:     Senhor Governador,
Endereçamento: Ao Senhor
```

**Busca**: Case-insensitive, com correspondência parcial. Se o cargo não for
encontrado, retorna o fallback genérico (`Senhor(a),` / `Ao(A) Senhor(a)`).

### --numeracao

Gera a numeração oficial de um documento.

```bash
python3 src/redator_transfegov.py --numeracao <TIPO> <NUMERO> <SETOR>
```

**Argumentos posicionais**:
1. `TIPO`: Tipo do documento (`oficio`, `nota_tecnica`, etc.)
2. `NUMERO`: Número sequencial
3. `SETOR`: Siglas do setor (da menor para a maior hierarquia)

**Exemplo**:
```bash
python3 src/redator_transfegov.py --numeracao oficio 142 "SAA/SE/MT"
```

**Saída**:
```
OFÍCIO Nº 142/2026/SAA/SE/MT
```

**Padrão de numeração**: `TIPO Nº NÚMERO/ANO/SIGLAS`

---

## Exemplos de Uso

### Gerar nota técnica para um parlamentar

```bash
python3 src/redator_transferegov.py nota-tecnica \
    --parlamentar "AFONSO FLORENCE" \
    --ano 2026
```

**Resultado**: Documento com análise dos planos de ação impedidos do
parlamentar Afonso Florence, incluindo panorama geral, detalhamento por
plano e concentração de impedimentos por UF.

### Gerar nota técnica geral

```bash
python3 src/redator_transferegov.py nota-tecnica --ano 2026
```

**Resultado**: Panorama geral dos planos de ação impedidos no âmbito das
Transferências Especiais (Programa 25).

### Gerar ofício a um governador

```bash
python3 src/redator_transfegov.py oficio \
    --dest "Governador do Estado" \
    --cargo "Governador" \
    --assunto "Relatório de Emendas Parlamentares" \
    --corpo "Segue em anexo o relatório consolidado das emendas parlamentares..." \
    --numero 143
```

**Resultado**: Ofício com numeração, vocativo `Senhor Governador,`,
corpo indentado e fecho `Respeitosamente,`.

### Gerar parecer técnico

```bash
python3 src/redator_transferegov.py parecer \
    --processo "001/2026" \
    --consulta "Análise de emendas impedidas no estado de SP" \
    --area técnico
```

**Resultado**: Parecer técnico com ementário, relatório, fundamentação
e conclusão (`s.m.j.`).

### Gerar despacho

```bash
python3 src/redator_transferegov.py despacho \
    --assunto "Encaminhamento de relatório" \
    --texto "Encaminho o relatório consolidado para análise de V.Sa."
```

**Resultado**: Despacho administrativo com assunto, texto decisório e
assinatura.

### Validar documento existente

```bash
python3 src/redator_transfegov.py validar \
    --arquivo "src/redator/notas_tecnicas/nota_tecnica_20260725_marcos_pereira.txt" \
    --tipo nota_tecnica
```

**Resultado**: Verificação de 4 regras (data, pronomes abolidos, gerúndio,
tipos abolidos). Retorna código 0 se válido, 1 se houver problemas.

### Consultar pronome de tratamento

```bash
python3 src/redator_transferegov.py --pronomes "Ministro"
```

**Saída**:
```
Cargo:        Ministro
Vocativo:     Senhor Ministro,
Endereçamento: A Sua Excelência o Senhor
```

### Gerar numeração

```bash
python3 src/redator_transferegov.py --numeracao oficio 142 "SAA/SE/MT"
```

**Saída**:
```
OFÍCIO Nº 142/2026/SAA/SE/MT
```

### Acessar via run.sh

```bash
./run.sh redator nota-tecnica --parlamentar "AFONSO FLORENCE" --ano 2026
./run.sh redator oficio --dest "Governador" --cargo "Governador" --assunto "Relatório" --corpo "..."
./run.sh redator parecer --processo "001/2026" --consulta "Análise"
./run.sh redator despacho --assunto "Encaminhamento" --texto "..."
./run.sh redator validar --arquivo "docs/nota.txt" --tipo nota_tecnica
./run.sh redator listar-tipos
```

---

## Funções Utilitárias Internas

### formatar_data_extenso()

Formata a data atual no padrão oficial brasileiro por extenso.

**Parâmetros**:
- `cidade` (str): Nome da cidade. Default: `"Brasília"`
- `estado` (str): Sigla da UF (não utilizada na formatação). Default: `"DF"`

**Retorno**: String no formato `"Cidade, DD de mês de AAAA."`

**Regras do Manual de Redação**:
- Dia 1: ordinal `1º` (sem espaço entre º e de)
- Demais dias: cardinal sem zero à esquerda
- Mês: inicial minúscula
- Ponto-final obrigatório ao término

### gerar_numeracao()

Gera a numeração oficial de um documento.

**Parâmetros**:
- `tipo` (str): Tipo do documento (chave de `PREFIXOS_DOCUMENTO`)
- `numero` (int): Número sequencial
- `ano` (int | None): Ano. Default: ano atual
- `setor` (str): Siglas do setor. Default: vazio

**Retorno**: String no formato `"TIPO Nº NÚMERO/ANO"` ou `"TIPO Nº NÚMERO/ANO/SETOR"`

**Conversão automática**: Tipos `memorando` e `aviso` são convertidos para `oficio`.

### consultar_pronome_tratamento()

Retorna o pronome de tratamento correto para um cargo público.

**Parâmetros**:
- `cargo` (str): Nome do cargo (case-insensitive)

**Retorno**: Dict com chaves `vocativo` e `endereçamento`.

**Busca**: Exata > parcial > fallback genérico.

### obter_fecho()

Retorna o fecho adequado conforme a hierarquia.

**Parâmetros**:
- `nivel` (str): `"superior"` ou `"igual"`. Default: `"igual"`

**Retorno**: `"Respeitosamente,"` ou `"Atenciosamente,"`

### validar_documento()

Valida se um documento segue as normas de redação oficial.

**Parâmetros**:
- `texto` (str): Conteúdo do documento
- `tipo` (str): Tipo do documento

**Retorno**: Lista de strings com problemas encontrados (vazia = válido).

---

## Dependências

- `src/db_utils.py`: Funções de consulta ao PostgreSQL (`query_df`)
- `src/formatters.py`: Formatação de valores (`fmt_brl`, `fmt_num`)
- `pandas`: Manipulação de dados das consultas SQL
- `argparse`: Interface de linha de comando
- `pathlib`: Manipulação de caminhos de arquivo
- `re`: Expressões regulares para validação e extração

---

## Diagrama de Geração

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  CLI (argparse) │────>│  Geradores de    │────>│  Arquivo .txt   │
│  parse_args()   │     │  Documento       │     │  src/redator/   │
└─────────────────┘     │  gerar_*()       │     └─────────────────┘
                        └────────┬─────────┘
                                 │
                        ┌────────▼─────────┐
                        │  Funções Base    │
                        │  - formatar_data │
                        │  - gerar_num     │
                        │  - consultar     │
                        │    pronomes      │
                        │  - obter_fecho   │
                        └────────┬─────────┘
                                 │
                        ┌────────▼─────────┐
                        │  PostgreSQL      │
                        │  (planos_acao,   │
                        │   parlamentares) │
                        └──────────────────┘
```

---

## Notas

1. O sistema NÃO gera portaria nem ata diretamente via CLI. Esses tipos estão
   cadastrados no dicionário `TIPOS_DOCUMENTO` para uso interno e validação.
2. A numeração de ofícios é sequencial por data (`YYYYMMDD` + número).
3. O fecho de ofício é SEMPRE `Respeitosamente,` (superior), pois ofícios são
   dirigidos a autoridades destinatárias.
4. A validação de documento é independente do tipo: as mesmas 4 regras são
   aplicadas a qualquer tipo.
5. O diretório `src/redator/validados/` é destinado a documentos que passaram
   pelo processo de validação.
