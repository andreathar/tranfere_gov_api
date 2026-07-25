# Diário Oficial — Botão Contextual nos Perfis

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Adicionar botão "📰 Diário Oficial" nos perfis de deputado e prefeito que busca citações do nome no DOU (federal) e Querido Diário (municipal), exibindo os resultados em um modal dedicado.

**Architecture:** 
- Backend: endpoint `POST /api/v1/diario/buscar-perfil` que aceita `{q, escopo, uf_municipio?}` e chama o MCP tool `diario_oficial_buscar_diario_unificado`. Para prefeitos com UF, usar `diario_oficial_buscar_diarios` (Querido Diário) quando `escopo=municipal`.
- Frontend: botão no profile card do deputado (sidebar) e no modal do prefeito. Ao clicar, abre `modal-diario-perfil` com resultados parseados do MCP (JSON → cards legíveis).
- Reutiliza o MCP client existente em `src/api/services/mcp_service.py` e o client `MCPBrasilClient` com cache TTL.

**Tech Stack:** FastAPI, JavaScript vanilla, Plotly dark theme, MCP-brasil (Querido Diário + DOU tools), sem dependências novas.

---

## Contexto Atual

| Componente | Status |
|---|---|
| Rota `/api/v1/diario/buscar` | ✅ Existe — busca genérica, sem contexto de perfil |
| MCP tool `diario_oficial_buscar_diario_unificado` | ✅ Disponível — 11 tools mcp-brasil |
| Tab global "📰 Diário Oficial" | ✅ Existe — busca standalone na nav |
| Botão no profile do deputado | ❌ Não existe |
| Botão no modal do prefeito | ❌ Não existe |
| Modal para resultados do perfil | ❌ Não existe |

---

## Task 1: Criar novo endpoint backend `POST /api/v1/diario/buscar-perfil`

**Objective:** Endpoint que recebe o nome de um político e busca no Diário Oficial, retornando JSON estruturado (não texto bruto do MCP).

**Files:**
- Modify: `src/api/routes/diario.py:11-27` (adicionar rota nova)
- Modify: `src/api/services/mcp_service.py` (adicionar wrapper `buscar_diario_perfil`)

**Step 1: Adicionar wrapper no mcp_service.py**

Adicionar função `buscar_diario_perfil` após `executar_lote` (linha 131):

```python
async def buscar_diario_perfil(
    nome: str,
    escopo: str = "ambos",
    uf_municipio: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> dict:
    """Busca citações de um nome no Diário Oficial (DOU + Querido Diário).
    
    Returns dict com keys:
      - federal: list de publicações DOU
      - municipal: list de publicações Querido Diário
      - query: termo buscado
      - total: soma de resultados
    """
    import json as _json
    
    results = {"federal": [], "municipal": [], "query": nome, "total": 0}
    
    # Busca DOU federal
    if escopo in ("ambos", "federal"):
        try:
            dou_args = {"texto": nome, "secao": "DOU-e"}
            if data_inicio:
                dou_args["data_inicio"] = data_inicio
            if data_fim:
                dou_args["data_fim"] = data_fim
            
            res = await _mcp_client.call_tool(
                "diario_oficial_dou_buscar", dou_args
            )
            if res:
                parsed = _json.loads(res) if isinstance(res, str) else res
                if isinstance(parsed, list):
                    results["federal"] = parsed[:20]  # limitar a 20
                elif isinstance(parsed, dict) and "items" in parsed:
                    results["federal"] = parsed["items"][:20]
        except Exception as e:
            log.warning(f"Erro busca DOU federal para '{nome}': {e}")
            results["federal_error"] = str(e)
    
    # Busca Querido Diário (municipal)
    if escopo in ("ambos", "municipal"):
        try:
            qd_args = {"texto": nome}
            if uf_municipio:
                qd_args["uf"] = uf_municipio
            
            res = await _mcp_client.call_tool(
                "diario_oficial_buscar_diarios", qd_args
            )
            if res:
                parsed = _json.loads(res) if isinstance(res, str) else res
                if isinstance(parsed, list):
                    results["municipal"] = parsed[:20]
                elif isinstance(parsed, dict) and "items" in parsed:
                    results["municipal"] = parsed["items"][:20]
        except Exception as e:
            log.warning(f"Erro busca Querido Diário para '{nome}': {e}")
            results["municipal_error"] = str(e)
    
    results["total"] = len(results["federal"]) + len(results["municipal"])
    return results
```

**Step 2: Adicionar rota POST em diario.py**

Adicionar após a rota existente `/buscar`:

```python
@router.post("/buscar-perfil", response_model=Dict[str, Any])
async def buscar_diario_perfil(payload: dict):
    """Busca citações de um político no Diário Oficial (DOU + Querido Diário).
    
    Body: {q: str, escopo: str, uf_municipio?: str, data_inicio?: str, data_fim?: str}
    """
    q = payload.get("q", "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Campo 'q' é obrigatório")
    
    escopo = payload.get("escopo", "ambos")
    uf = payload.get("uf_municipio")
    data_inicio = payload.get("data_inicio")
    data_fim = payload.get("data_fim")
    
    try:
        result = await mcp_service.buscar_diario_perfil(
            nome=q, escopo=escopo, uf_municipio=uf,
            data_inicio=data_inicio, data_fim=data_fim,
        )
        return {"status": "success", "data": result}
    except Exception as e:
        log.error(f"Erro ao buscar diário para perfil '{q}': {e}")
        raise HTTPException(status_code=500, detail=f"Falha: {str(e)}")
```

**Step 3: Verificar**

```bash
cd /mnt/data/Projects_SSD/tranfere_gov_api && source .venv/bin/activate
python3 -m py_compile src/api/services/mcp_service.py && echo "mcp_service OK"
python3 -m py_compile src/api/routes/diario.py && echo "diario OK"
ruff check src/api/services/mcp_service.py src/api/routes/diario.py --select E402,F821
```

Expected: 0 errors, syntax OK.

---

## Task 2: Criar modal `modal-diario-perfil` no HTML

**Objective:** Modal dedicado para exibir resultados do Diário Oficial vinculados ao perfil de um político.

**Files:**
- Modify: `src/api/static/index.html` (adicionar modal após `modal-prefeito`)

**Step 1: Adicionar modal após o modal-prefeito (após linha 342)**

```html
<!-- Modal Diário Oficial do Perfil -->
<div id="modal-diario-perfil" class="modal hidden">
    <div class="modal-content" style="max-width: 900px; max-height: 90vh;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
            <h2 id="modal-diario-perfil-title" style="margin-bottom: 0.25rem;">📰 Diário Oficial</h2>
            <span class="close-modal" onclick="closeModal('modal-diario-perfil')">&times;</span>
        </div>
        <p id="modal-diario-perfil-subtitle" style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1rem;"></p>
        
        <!-- Filtros internos -->
        <div style="display: flex; gap: 0.75rem; margin-bottom: 1rem; flex-wrap: wrap;">
            <select id="diario-escopo-select" style="background: var(--bg-dark); color: var(--text-main); border: 1px solid var(--border-color); padding: 0.4rem 0.75rem; border-radius: 6px; font-size: 0.85rem;">
                <option value="ambos">Ambos (Federal + Municipal)</option>
                <option value="federal">Apenas DOU (Federal)</option>
                <option value="municipal">Apenas Municipal (Querido Diário)</option>
            </select>
            <input type="date" id="diario-data-inicio" style="background: var(--bg-dark); color: var(--text-main); border: 1px solid var(--border-color); padding: 0.4rem 0.75rem; border-radius: 6px; font-size: 0.85rem;" placeholder="Data início">
            <input type="date" id="diario-data-fim" style="background: var(--bg-dark); color: var(--text-main); border: 1px solid var(--border-color); padding: 0.4rem 0.75rem; border-radius: 6px; font-size: 0.85rem;" placeholder="Data fim">
            <button id="btn-buscar-diario-perfil" style="background: var(--accent-blue); color: #fff; border: none; padding: 0.4rem 1rem; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.85rem;">🔍 Buscar</button>
        </div>
        
        <div id="diario-perfil-results" class="modal-body" style="min-height: 120px; background: #0f172a; border-radius: 8px; padding: 1rem; max-height: 55vh; overflow-y: auto;">
            <p style="color: var(--text-muted); text-align: center; padding: 2rem;">Clique em "Buscar" para consultar o Diário Oficial.</p>
        </div>
    </div>
</div>
```

**Step 2: Verificar HTML syntax**

```bash
python3 -c "
with open('src/api/static/index.html') as f:
    content = f.read()
assert 'modal-diario-perfil' in content, 'Modal not found'
assert 'btn-buscar-diario-perfil' in content, 'Button not found'
assert 'diario-perfil-results' in content, 'Results container not found'
print('HTML OK: modal-diario-perfil elements present')
"
```

---

## Task 3: Adicionar botão ao profile card do deputado

**Objective:** Incluir botão "📰 Diário Oficial" no card do perfil do deputado (sidebar), que abre o modal com o nome do deputado pré-preenchido.

**Files:**
- Modify: `src/api/static/app.js` — função `renderPerfil()` (linha 185-204)

**Step 1: Adicionar botão no profileCard.innerHTML**

Dentro de `renderPerfil(p)`, adicionar botão após a div de informações. Substituir o final de `profileCard.innerHTML` (após `</div>\n  `; na linha ~203):

```javascript
  profileCard.innerHTML = `
    <img class="profile-photo" src="${p.url_foto || ''}" alt="${p.nome_urna}">
    <div class="profile-name">${p.nome_urna || p.nome}</div>
    <div class="badge-party">${p.sigla_partido} - ${p.uf}</div>
    ${tseBadge}
    <div class="profile-info" style="margin-top:1rem;">
      <p><span>Nome Completo</span> ${p.nome || '-'}</p>
      <p><span>Eleição (TSE)</span> <strong>${p.ano_eleicao || 2022} (${p.situacao_eleitoral || 'ELEITO'})</strong></p>
      <p><span>Coligação TSE</span> ${p.coligacao || 'Partido Isolado'}</p>
      <p><span>Patrimônio (TSE)</span> <strong style="color:var(--info);">${patrimonioFmt}</strong></p>
      <p><span>Gabinete</span> ${p.gabinete_telefone || '-'}</p>
      <p><span>Email</span> <a href="mailto:${p.gabinete_email}" style="color:var(--accent-blue);text-decoration:none;">${p.gabinete_email ? 'Enviar' : '-'}</a></p>
      <p><span>Escolaridade</span> ${p.escolaridade || '-'}</p>
    </div>
    <button onclick="openDiarioPerfil('${(p.nome_urna || p.nome || '').replace(/'/g, "\\'")}', '${p.uf || ''}')"
      style="width:100%; margin-top:1rem; background: linear-gradient(135deg, #3b82f6, #8b5cf6); color:#fff; border:none; padding:0.65rem; border-radius:8px; font-weight:700; font-size:0.85rem; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:0.5rem;">
      📰 Diário Oficial
    </button>
  `;
```

**Step 2: Verificar**

```bash
source .venv/bin/activate && python3 -c "
with open('src/api/static/app.js') as f:
    c = f.read()
assert 'openDiarioPerfil' in c, 'Function call not in renderPerfil'
print('app.js OK: openDiarioPerfil button in renderPerfil')
"
```

---

## Task 4: Adicionar botão ao modal do prefeito

**Objective:** Incluir botão "📰 Diário Oficial" no modal de perfil do prefeito (modal-prefeito), ao lado do botão "🔍 Integridade".

**Files:**
- Modify: `src/api/static/app.js` — função `openPrefeitoModal()` (linha 1088-1101)

**Step 1: Adicionar botão no card de Integridade do prefeito**

Na seção "Painel de Integridade" (linha 1088-1101), adicionar botão ao lado do existente:

```javascript
      <!-- Card do Painel de Integridade (TCU & DataJud) -->
      <div style="margin-bottom:1.5rem; background:#0f172a; padding:1.25rem; border-radius:8px; border:1px solid var(--border-color); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
        <div>
          <h4 style="margin-bottom:0.35rem; color:#f59e0b; font-size:1.05rem; display:flex; align-items:center; gap:0.5rem;">
            <span>⚖️ Painel de Integridade & Compliance (TCU / DataJud)</span>
          </h4>
          <div style="font-size:0.85rem; color:var(--text-muted);">
            CNPJ da Prefeitura: <strong style="color:var(--text-main);">${prefCnpj || 'Não cadastrado'}</strong> — ${prefRazao}
          </div>
        </div>
        <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
          <button class="btn-auditoria btn-auditoria-tcu" style="padding:0.6rem 1.25rem; font-size:0.85rem; font-weight:600; cursor:pointer;" onclick="openJusticaModal('${(prefCnpj || prefRazao).replace(/'/g, '')}', '${prefRazao.replace(/'/g, '')}')">
            🔍 TCU & DataJud
          </button>
          <button onclick="openDiarioPerfil('${(p.prefeito_nome || p.municipio_nome || '').replace(/'/g, "\\'")}', '${p.uf || ''}')"
            style="padding:0.6rem 1.25rem; font-size:0.85rem; font-weight:600; cursor:pointer; background:linear-gradient(135deg, #3b82f6, #8b5cf6); color:#fff; border:none; border-radius:6px;">
            📰 Diário Oficial
          </button>
        </div>
      </div>
```

**Step 2: Verificar**

```bash
python3 -c "
with open('src/api/static/app.js') as f:
    c = f.read()
count = c.count('openDiarioPerfil')
assert count >= 2, f'Expected 2+ calls, got {count}'
print(f'app.js OK: openDiarioPerfil called {count} times (deputado + prefeito)')
"
```

---

## Task 5: Implementar `openDiarioPerfil()` e renderização no JS

**Objective:** Função JS que busca no backend e renderiza resultados em cards legíveis dentro do modal.

**Files:**
- Modify: `src/api/static/app.js` — adicionar função + event listeners

**Step 1: Adicionar função `openDiarioPerfil` e `renderDiarioPerfilResults`**

Adicionar após a função `loadDiarioOficial` (após linha 892):

```javascript
// Diário Oficial — Busca Contextual do Perfil
let currentDiarioQuery = '';

async function openDiarioPerfil(nome, uf) {
  currentDiarioQuery = nome;
  const modal = document.getElementById('modal-diario-perfil');
  const title = document.getElementById('modal-diario-perfil-title');
  const subtitle = document.getElementById('modal-diario-perfil-subtitle');
  const results = document.getElementById('diario-perfil-results');

  if (!modal || !results) return;

  modal.classList.remove('hidden');
  title.innerText = `📰 Diário Oficial — "${nome}"`;
  subtitle.innerText = `Buscando citações de "${nome}" no DOU e Querido Diário...`;
  results.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div><p style="text-align:center; color:var(--text-muted);">Consultando Diário Oficial da União e diários municipais...</p>';

  // Set escopo default based on context
  const escopoSelect = document.getElementById('diario-escopo-select');
  if (escopoSelect) escopoSelect.value = 'ambos';

  await fetchDiarioPerfilResults(nome, uf);
}

async function fetchDiarioPerfilResults(nome, uf) {
  const container = document.getElementById('diario-perfil-results');
  if (!container) return;

  const escopo = document.getElementById('diario-escopo-select')?.value || 'ambos';
  const dataInicio = document.getElementById('diario-data-inicio')?.value || '';
  const dataFim = document.getElementById('diario-data-fim')?.value || '';

  container.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div><p style="text-align:center; color:var(--text-muted);">Buscando...</p>';

  try {
    const body = { q: nome, escopo };
    if (uf) body.uf_municipio = uf;
    if (dataInicio) body.data_inicio = dataInicio;
    if (dataFim) body.data_fim = dataFim;

    const res = await fetch(`${API_BASE}/diario/buscar-perfil`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(r => r.json());

    if (res.status === 'success' && res.data) {
      renderDiarioPerfilResults(container, res.data, nome);
    } else {
      container.innerHTML = `<p style="color:var(--danger); text-align:center;">Erro: ${res.detail || 'Resposta inválida do servidor'}</p>`;
    }
  } catch (e) {
    container.innerHTML = `<p style="color:var(--danger); text-align:center;">Erro de conexão: ${e.message}</p>`;
  }
}

function renderDiarioPerfilResults(container, data, nome) {
  const federal = data.federal || [];
  const municipal = data.municipal || [];
  const total = federal.length + municipal.length;

  if (total === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:2rem;">
        <div style="font-size:2rem; margin-bottom:0.5rem;">🔍</div>
        <p style="color:var(--text-muted); font-size:1rem;">Nenhuma citação encontrada para "<strong>${nome}</strong>"</p>
        <p style="color:var(--text-muted); font-size:0.85rem;">Tente ampliar o período ou alterar o escopo da busca.</p>
      </div>`;
    return;
  }

  let html = `<div style="margin-bottom:0.75rem; font-size:0.85rem; color:var(--text-muted);">
    <strong>${total}</strong> resultado(s) — <span style="color:#60a5fa;">${federal.length} DOU</span> | <span style="color:#34d399;">${municipal.length} Municipal</span>
  </div>`;

  // Federal results
  if (federal.length > 0) {
    html += `<h4 style="color:#60a5fa; margin:1rem 0 0.5rem; font-size:0.95rem;">🏛️ Diário Oficial da União (DOU)</h4>`;
    federal.forEach(item => {
      const titulo = item.titulo || item.title || item.nome || 'Publicação DOU';
      const dataPub = item.data || item.dataPublicacao || item.date || '';
      const secao = item.secao || item.section || '';
      const resumo = item.resumo || item摘要 || item.texto || item.summary || '';
      const link = item.url || item.link || '';

      html += `
        <div style="background:#1e293b; padding:0.85rem 1rem; border-radius:8px; margin-bottom:0.6rem; border-left:3px solid #60a5fa;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:1rem;">
            <div style="flex:1;">
              <div style="font-weight:600; color:#e2e8f0; font-size:0.9rem;">${titulo}</div>
              <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.25rem;">
                ${secao ? `<span style="color:#60a5fa;">${secao}</span> · ` : ''}
                ${dataPub ? formatDate(dataPub) : ''}
              </div>
              ${resumo ? `<div style="font-size:0.82rem; color:#94a3b8; margin-top:0.4rem; line-height:1.5; max-height:3.6em; overflow:hidden;">${resumo.substring(0, 200)}${resumo.length > 200 ? '...' : ''}</div>` : ''}
            </div>
            ${link ? `<a href="${link}" target="_blank" rel="noopener" style="color:#60a5fa; text-decoration:none; font-size:0.8rem; white-space:nowrap;">↗ Ver publicação</a>` : ''}
          </div>
        </div>`;
    });
  }

  // Municipal results
  if (municipal.length > 0) {
    html += `<h4 style="color:#34d399; margin:1rem 0 0.5rem; font-size:0.95rem;">🏙️ Diários Municipais (Querido Diário)</h4>`;
    municipal.forEach(item => {
      const titulo = item.titulo || item.title || item.nome || 'Publicação Municipal';
      const municipio = item.municipio || item.cidade || item.nomeMunicipio || '';
      const dataPub = item.data || item.dataPublicacao || item.date || '';
      const resumo = item.resumo || item摘要 || item.texto || item.summary || '';
      const link = item.url || item.link || '';

      html += `
        <div style="background:#1e293b; padding:0.85rem 1rem; border-radius:8px; margin-bottom:0.6rem; border-left:3px solid #34d399;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:1rem;">
            <div style="flex:1;">
              <div style="font-weight:600; color:#e2e8f0; font-size:0.9rem;">${titulo}</div>
              <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.25rem;">
                ${municipio ? `<span style="color:#34d399;">${municipio}</span> · ` : ''}
                ${dataPub ? formatDate(dataPub) : ''}
              </div>
              ${resumo ? `<div style="font-size:0.82rem; color:#94a3b8; margin-top:0.4rem; line-height:1.5; max-height:3.6em; overflow:hidden;">${resumo.substring(0, 200)}${resumo.length > 200 ? '...' : ''}</div>` : ''}
            </div>
            ${link ? `<a href="${link}" target="_blank" rel="noopener" style="color:#34d399; text-decoration:none; font-size:0.8rem; white-space:nowrap;">↗ Ver publicação</a>` : ''}
          </div>
        </div>`;
    });
  }

  container.innerHTML = html;
}
```

**Step 2: Adicionar event listeners no DOMContentLoaded**

Após os listeners de Diário (linha 905), adicionar:

```javascript
  // Diário Perfil Modal — botão de busca dentro do modal
  const btnBuscarDiarioPerfil = document.getElementById('btn-buscar-diario-perfil');
  if (btnBuscarDiarioPerfil) {
    btnBuscarDiarioPerfil.addEventListener('click', () => {
      if (currentDiarioQuery) {
        fetchDiarioPerfilResults(currentDiarioQuery, '');
      }
    });
  }
```

**Step 3: Verificar**

```bash
python3 -c "
with open('src/api/static/app.js') as f:
    c = f.read()
assert 'async function openDiarioPerfil' in c, 'openDiarioPerfil not found'
assert 'async function fetchDiarioPerfilResults' in c, 'fetchDiarioPerfilResults not found'
assert 'function renderDiarioPerfilResults' in c, 'renderDiarioPerfilResults not found'
assert 'currentDiarioQuery' in c, 'currentDiarioQuery state not found'
print('app.js OK: all diario perfil functions present')
"
```

---

## Task 6: Teste integrado end-to-end

**Objective:** Verificar que o servidor inicia, a rota responde, e o frontend carrega sem erros.

**Step 1: Verificar imports e syntax**

```bash
cd /mnt/data/Projects_SSD/tranfere_gov_api && source .venv/bin/activate

# Syntax check
python3 -m py_compile src/api/routes/diario.py && echo "diario.py OK"
python3 -m py_compile src/api/services/mcp_service.py && echo "mcp_service.py OK"

# Ruff check (critical only)
ruff check src/api/routes/diario.py src/api/services/mcp_service.py --select E402,F821

# Frontend assertions
python3 -c "
with open('src/api/static/app.js') as f: c = f.read()
assert c.count('openDiarioPerfil') >= 3, f'Expected 3+ refs, got {c.count(\"openDiarioPerfil\")}'
assert 'modal-diario-perfil' in c
print('app.js: all checks passed')

with open('src/api/static/index.html') as f: c = f.read()
assert c.count('modal-diario-perfil') >= 2, 'Modal HTML missing'
print('index.html: modal present')
"
```

**Step 2: Verificar endpoint com curl (quando servidor rodar)**

```bash
# Iniciar servidor em background
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!
sleep 3

# Testar rota
curl -s -X POST http://localhost:8000/api/v1/diario/buscar-perfil \
  -H "Content-Type: application/json" \
  -d '{"q": "JOAO SILVA", "escopo": "federal"}' | python3 -m json.tool

kill $SERVER_PID
```

Expected: JSON com `status: success` e `data.federal: [...]` (mesmo que vazio se MCP não estiver disponível).

---

## Arquivos Alterados (resumo)

| Arquivo | Tipo | Descrição |
|---|---|---|
| `src/api/routes/diario.py` | MODIFY | +POST `/buscar-perfil` |
| `src/api/services/mcp_service.py` | MODIFY | +`buscar_diario_perfil()` wrapper |
| `src/api/static/index.html` | MODIFY | +`modal-diario-perfil` HTML |
| `src/api/static/app.js` | MODIFY | +`openDiarioPerfil()`, +`fetchDiarioPerfilResults()`, +`renderDiarioPerfilResults()`, +botões no renderPerfil e openPrefeitoModal |

---

## Riscos e Notas

1. **MCP Server indisponível:** O `MCPBrasilClient` usa `uvx --from mcp-brasil` que precisa estar instalado. Se o MCP server não estiver rodando, o endpoint retornará erro 500. Solução: o frontend já trata isso com mensagem de erro amigável.

2. **Rate limiting MCP:** O Querido Diário e DOU têm rate limits. O cache TTL de 3600s do `MCPBrasilClient` mitiga isso para buscas repetidas.

3. **Resposta do MCP pode ser texto bruto:** O MCP retorna strings JSON ou texto puro. O `renderDiarioPerfilResults` já lida com ambos os formatos (verifica `titulo`, `title`, `nome` como chaves alternativas).

4. **Nomes com acentos/aspas:** O `replace(/'/g, "\\'")` no onclick previne XSS via nomes com aspas. Nomes com acentos funcionam normalmente em URLs POST.

5. **Escopo municipal sem UF:** Quando o usuário busca um prefeito, o `uf` é passado automaticamente. Para deputados federais, o `uf` do partido é usado como hint para buscas municipais.

---

## Ordem de Implementação

1. **Task 1** — Backend (mcp_service + rota) — sem dependências
2. **Task 2** — HTML modal — sem dependências
3. **Task 3** — Botão deputado — depende de Task 5 (openDiarioPerfil)
4. **Task 4** — Botão prefeito — depende de Task 5 (openDiarioPerfil)
5. **Task 5** — JS functions — sem dependências (pode ir em paralelo com 2)
6. **Task 6** — Verificação final — depende de todas

Recomendação: implementar 1+2 em paralelo, depois 5, depois 3+4,最后 6.
