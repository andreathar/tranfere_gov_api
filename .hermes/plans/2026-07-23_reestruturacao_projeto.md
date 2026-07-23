# Plano de Reestruturação — tranfere_gov_api

**Data:** 2026-07-23
**Objetivo:** Separar código-fonte de saídas, criar config centralizada, arquivar código morto.

## Auditoria Atual

### Contagens
| Categoria | Qtd | Status |
|-----------|-----|--------|
| Scripts Python ativos | 3 | `transferegov_extract.py`, `extract_cemiterios_2026_plano_acao.py`, `extract_cemiterios_2026_negados.py` |
| Scripts Python obsoletos | 4 | `extract_cemiterios.py`, `extract_cemiterios_2026.py`, `extract_full_normalized.py`, `extract_by_parlamentar.py` |
| Arquivos de saída (xlsx/json) | 6 | Devem ser gitignored |
| Logs | 6 | Devem ser gitignored |
| Docs/Ref | 4 | `swagger.yaml`, `strategy.md`, `manual.pdf`, `manual.txt` |
| Config | 3 | `requirements.txt`, `.env.example`, `.gitignore` |
| App React (incompleta) | 4 | `package.json`, `vite.config.ts`, `tsconfig.json`, `metadata.json` |

### Problemas
1. **Tudo no root** — scripts, outputs, logs, docs, app React misturados
2. **Outputs no git** — xlsx/json/logs não estão no .gitignore
3. **Código obsoleta** — 4 scripts usam API antiga (PostgREST), não funcionam com a nova
4. **Config duplicada** — cada script repete URL, headers, timeouts
5. **App React solta** — scaffold de AI Studio sem src/ nem componentes

---

## Estrutura Alvo

```
tranfere_gov_api/
├── src/                          # Scripts Python ativos
│   ├── transferegov_extract.py   # CLI genérico (PRINCIPAL)
│   ├── extract_cemiterios_2026_plano_acao.py
│   └── extract_cemiterios_2026_negados.py
│
├── config/                       # Config centralizada
│   ├── __init__.py               # Expõe constantes como módulo
│   ├── settings.py               # API_URL, HEADERS, TIMEOUTS, SITUACOES
│   └── .env.example              # Variáveis de ambiente
│
├── data/                         # Dados de referência
│   ├── swagger.yaml              # Spec da API
│   └── objetos_2026.json         # Lista de objetos (gerado por --discover)
│
├── output/                       # Saídas (TUDO gitignored)
│   ├── xlsx/
│   ├── csv/
│   ├── json/
│   └── logs/
│
├── archive/                      # Scripts obsoletos (referência)
│   ├── extract_cemiterios.py
│   ├── extract_cemiterios_2026.py
│   ├── extract_full_normalized.py
│   └── extract_by_parlamentar.py
│
├── docs/                         # Documentação
│   ├── strategy.md
│   ├── manual.pdf
│   └── manual.txt
│
├── app/                          # App React (AI Studio scaffold)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── metadata.json
│
├── requirements.txt              # Dependências Python
├── .gitignore                    # Atualizado
├── README.md                     # Documentação principal
└── run.sh                        # Atalhos para comuns
```

---

## Fases de Execução

### Fase A: Preparação (Baixo risco)
1. Criar scaffold de diretórios
2. Atualizar `.gitignore` para ignorar `output/`, `__pycache__/`, `*.pyc`, `*.log`, `*.xlsx`, `*.csv`

**Verificação:**
```bash
find . -maxdepth 2 -type d | sort  # Todos os dirs criados
git status                          # output/ não aparece
```

### Fase B: Config Centralizada (Baixo risco)
3. Criar `config/settings.py` com constantes extraídas dos scripts
4. Criar `config/__init__.py`
5. Atualizar scripts para importar de `config`

**Verificação:**
```bash
cd src && python3 -c "from config.settings import API_URL; print(API_URL)"
python3 -c "from config.settings import SITUACOES_NEGADAS; print(SITUACOES_NEGADAS)"
```

### Fase C: Mover Scripts Ativos (Médio risco)
6. Mover 3 scripts de root → `src/`
7. Atualizar paths de log/outputs nos scripts para `../output/`

**Verificação:**
```bash
cd src && python3 transferegov_extract.py --help  # Funciona?
```

### Fase D: Mover Saídas e Logs (Baixo risco)
8. Mover `*.xlsx`, `*.json` (dados), `*.csv` → `output/`
9. Mover `*.log` → `output/logs/`
10. Mover `objetos_disponiveis_*.json` → `data/`

**Verificação:**
```bash
ls output/xlsx/ output/json/ output/logs/  # Arquivos movidos
ls data/objetos_2026.json                   # Existe
```

### Fase E: Mover Objetos e Docs (Baixo risco)
11. Mover scripts obsoletos → `archive/`
12. Mover `swagger.yaml` → `data/`
13. Mover `strategy.md`, `manual.*` → `docs/`
14. Mover arquivos React → `app/`

**Verificação:**
```bash
ls archive/        # 4 scripts obsoletos
ls data/           # swagger.yaml + objetos_2026.json
ls docs/           # strategy.md + manual.*
ls app/            # package.json + vite.config.ts + tsconfig.json + metadata.json
```

### Fase F: Limpeza (Baixo risco)
15. Remover `__pycache__/`
16. Mover `assets/.aistudio/` → `app/.aistudio/` (ou remover se inútil)
17. Criar `run.sh` com atalhos

**Verificação:**
```bash
find . -name "__pycache__" -type d        # 0 results
find . -name "*.pyc" -delete              # Limpo
```

### Fase G: Documentação
18. Criar `README.md` com:
    - Descrição do projeto
    - Estrutura de diretórios
    - Como instalar e rodar
    - Lista de objetos disponíveis
    - Exemplos de uso

**Verificação:**
```bash
cat README.md  # Documentação completa
```

---

## Variáveis de Ambiente (config/settings.py)

```python
# Endpoints
API_URL_LISTAGEM = "https://especiais.transferegov.sistema.gov.br/maisbrasil-transferencia-especial-backend/api/public/plano-acao/listagem"

# Request defaults
DEFAULT_PAGE_SIZE = 100
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0
SLEEP_BETWEEN_PAGES = 1.0

# Situações
SITUACOES_NEGADAS = {"REPROVADO", "IMPEDIDO", "CANCELADO", "NAO_CUMPROU"}
SITUACOES_CONHECIDAS = {
    "CIENTE", "APROVADO", "REPROVADO", "IMPEDIDO", "CANCELADO",
    "EM_EXECUCAO", "CONCLUIDO", "NAO_CUMPROU",
}

# Output paths (relative to project root)
OUTPUT_DIR = "output"
OUTPUT_XLSX = f"{OUTPUT_DIR}/xlsx"
OUTPUT_CSV = f"{OUTPUT_DIR}/csv"
OUTPUT_JSON = f"{OUTPUT_DIR}/json"
OUTPUT_LOGS = f"{OUTPUT_DIR}/logs"
```

---

## .gitignore Atualizado

```gitignore
# Dependencies
node_modules/
.venv/
__pycache__/
*.pyc

# Build
build/
dist/

# Outputs (gerados por scripts)
output/
*.xlsx
*.csv
*.log

# Environment
.env
!.env.example

# IDE
.DS_Store
.vscode/

# Misc
*.pyc
__pycache__/
```

---

## Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Scripts quebram ao mover para src/ | Atualizar imports e paths ANTES de mover |
| Output paths hardcoded | Usar `config.settings.OUTPUT_*` em todos os scripts |
| Gitignore remove tracking de arquivos que devem ficar | Testar `git status` após cada mudança |
| App React quebra com path relativo | app/ é self-contained, não depende do root |

## Checklist Final

- [ ] Todos os scripts importam de `config/settings.py`
- [ ] Nenhum `.xlsx`, `.csv`, `.log` no root
- [ ] Nenhum script obsoleta no root (só em `archive/`)
- [ ] `output/` completamente gitignored
- [ ] `README.md` documenta tudo
- [ ] `run.sh` funciona
- [ ] `python3 src/transferegov_extract.py --help` OK
- [ ] `python3 src/transferegov_extract.py --objeto 301 --ano 2026 --negados` OK
