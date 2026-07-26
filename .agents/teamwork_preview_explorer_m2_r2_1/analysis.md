# Analysis & Fix Specifications: README.md Port Fix & Root LICENSE

**Milestone**: M2 (Iteration 2 - Remediation of Reviewer Feedback)
**Agent**: Explorer (`teamwork_preview_explorer_m2_r2_1`)
**Working Directory**: `/mnt/data/Projects_SSD/tranfere_gov_api/.agents/teamwork_preview_explorer_m2_r2_1`
**Target Files**:
- `/mnt/data/Projects_SSD/tranfere_gov_api/README.md`
- `/mnt/data/Projects_SSD/tranfere_gov_api/LICENSE`

---

## 1. Executive Summary

During Milestone M2 Iteration 1 review, `reviewer_m2_2` raised a request for changes regarding documentation discrepancies and missing files:
1. `README.md` stated that `./run.sh web` runs on port 8000 (`http://localhost:8000`), whereas `run.sh` line 85 launches uvicorn on port 8080 (`$PYTHON -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8080`). Direct execution of uvicorn without `run.sh` runs on port 8000 by default or as configured.
2. `README.md` line 250 references a root `LICENSE` file, but `/mnt/data/Projects_SSD/tranfere_gov_api/LICENSE` does not exist on disk.

This document provides exact, verified observations, logical justification, full text for the new `LICENSE` file, and step-by-step instructions for the Worker agent to implement these remediations cleanly.

---

## 2. Technical Evidence & Observations

### 2.1 Web Application Port Configuration
- **Script Definition (`run.sh:83-86`)**:
  ```bash
  web)
      echo "🌐 Iniciando Painel Web do Deputado em http://localhost:8080 ..."
      $PYTHON -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8080
      ;;
  ```
  Executing `./run.sh web` binds to host `0.0.0.0` and port `8080`.
- **Direct Uvicorn Execution**:
  Running `uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000` manually runs on port `8000`.
- **Existing `README.md` Inconsistencies**:
  - Line 25: `- **Painel REST & Web App (FastAPI)**: Inteligência parlamentar e municipal na porta 8000.`
  - Line 33: `[ Enriquecimento: IBGE/Câmara/SICONFI ]      [ FastAPI Web App (Porta 8000) ]            [ Plotly Dash + MCP (Porta 8050) ]`
  - Line 55: `│   ├── api/                      # Aplicação Web FastAPI (Porta 8000)`
  - Lines 184–189:
    ```bash
    ./run.sh web
    # Ou diretamente:
    # uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
    ```
    - **Interface Web**: [http://localhost:8000](http://localhost:8000)
    - **Documentação Swagger/ReDoc**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2.2 Root `LICENSE` File Status
- **Existence Check**: `/mnt/data/Projects_SSD/tranfere_gov_api/LICENSE` is missing.
- **`README.md:250`**:
  `Distribuído sob a licença MIT. Veja LICENSE para mais informações.`

---

## 3. Step-by-Step Fix Specifications for Worker

### Fix Specification 1: Update `README.md` Port References

The Worker must update lines 25, 33, 55, 184–190, and 250 in `/mnt/data/Projects_SSD/tranfere_gov_api/README.md`.

#### Replacement Chunk 1 (Lines 24–26):
**Target Content**:
```markdown
5. **Visualização & Servidor MCP**:
   - **Painel REST & Web App (FastAPI)**: Inteligência parlamentar e municipal na porta `8000`.
   - **Plotly Dash & Servidor MCP Hub**: 31 gráficos analíticos interativos e endpoint MCP nativo (`/_mcp`) na porta `8050`.
```
**Replacement Content**:
```markdown
5. **Visualização & Servidor MCP**:
   - **Painel REST & Web App (FastAPI)**: Inteligência parlamentar e municipal na porta `8080` (via `./run.sh web`) ou `8000` (via `uvicorn` direto).
   - **Plotly Dash & Servidor MCP Hub**: 31 gráficos analíticos interativos e endpoint MCP nativo (`/_mcp`) na porta `8050`.
```

#### Replacement Chunk 2 (Lines 31–35):
**Target Content**:
```markdown
   ┌──────────────────────────────────────────────────────┴──────────────────────────────────────────────────────┐
   ▼                                                      ▼                                                      ▼
[ Enriquecimento: IBGE/Câmara/SICONFI ]      [ FastAPI Web App (Porta 8000) ]            [ Plotly Dash + MCP (Porta 8050) ]
```
**Replacement Content**:
```markdown
   ┌──────────────────────────────────────────────────────┴──────────────────────────────────────────────────────┐
   ▼                                                      ▼                                                      ▼
[ Enriquecimento: IBGE/Câmara/SICONFI ]      [ FastAPI Web App (Porta 8080/8000) ]       [ Plotly Dash + MCP (Porta 8050) ]
```

#### Replacement Chunk 3 (Line 55):
**Target Content**:
```markdown
│   ├── api/                      # Aplicação Web FastAPI (Porta 8000)
```
**Replacement Content**:
```markdown
│   ├── api/                      # Aplicação Web FastAPI (Porta 8080 via run.sh / 8000 via uvicorn)
```

#### Replacement Chunk 4 (Lines 181–190):
**Target Content**:
```markdown
### 1. Painel Web de Inteligência Parlamentar (FastAPI)
Interface RESTful e SPA para consulta de deputados, emendas, despesas CEAP e proposições.
```bash
./run.sh web
# Ou diretamente:
# uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```
- **Interface Web**: [http://localhost:8000](http://localhost:8000)
- **Documentação Swagger/ReDoc**: [http://localhost:8000/docs](http://localhost:8000/docs)
```
**Replacement Content**:
```markdown
### 1. Painel Web de Inteligência Parlamentar (FastAPI)
Interface RESTful e SPA para consulta de deputados, emendas, despesas CEAP e proposições.
```bash
./run.sh web                          # Executa na porta 8080 (http://localhost:8080)
# Ou diretamente via uvicorn na porta 8000:
# uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```
- **Interface Web (via `./run.sh web`)**: [http://localhost:8080](http://localhost:8080)
- **Interface Web (via uvicorn direto)**: [http://localhost:8000](http://localhost:8000)
- **Documentação Swagger/ReDoc**: [http://localhost:8080/docs](http://localhost:8080/docs) (ou `http://localhost:8000/docs`)
```

#### Replacement Chunk 5 (Lines 249–251):
**Target Content**:
```markdown
## 📄 Licença
Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.
```
**Replacement Content**:
```markdown
## 📄 Licença
Distribuído sob a licença MIT. Veja [LICENSE](LICENSE) para mais informações.
```

---

### Fix Specification 2: Create Root `LICENSE` File

The Worker must create `/mnt/data/Projects_SSD/tranfere_gov_api/LICENSE` with the following exact text:

```text
MIT License

Copyright (c) 2026 TransfereGov API Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 4. Verification Protocol for Worker

1. **Verify `README.md` Changes**:
   - Check `git diff README.md` to confirm all 5 sections were correctly updated.
   - Verify links and port descriptions match `run.sh` (8080) and direct uvicorn (8000).

2. **Verify `LICENSE` File**:
   - Check file existence at `/mnt/data/Projects_SSD/tranfere_gov_api/LICENSE`.
   - Confirm file contains valid MIT license text.

3. **Pre-Commit Verification**:
   - Run `pre-commit run --all-files` to ensure no linting/formatting issues (e.g. trailing whitespace in `README.md` or `LICENSE`).
