const API_BASE = '/api/v1';

// State
let state = {
  currentDeputadoId: null,
  currentTab: 'emendas',
  cache: {
    perfil: {},
    emendas: {},
    emendasResumo: {},
    despesas: {},
    comissoes: {},
    votacoes: {},
    proposicoes: {}
  }
};

// Utils
const formatBRL = (val) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0);
const formatNum = (val) => new Intl.NumberFormat('pt-BR').format(val || 0);
const formatPct = (val) => new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 1 }).format(val || 0);
const formatDate = (dateStr) => {
  if(!dateStr) return '-';
  const d = new Date(dateStr);
  return d.toLocaleDateString('pt-BR');
};

const plotlyDarkLayout = (title) => ({
  title: { text: title, font: { color: '#e2e8f0' } },
  paper_bgcolor: '#1e293b',
  plot_bgcolor: '#1e293b',
  font: { color: '#e2e8f0', family: 'Inter' },
  xaxis: { gridcolor: '#334155', zerolinecolor: '#334155' },
  yaxis: { gridcolor: '#334155', zerolinecolor: '#334155' },
  margin: { t: 40, r: 20, l: 40, b: 40 },
  autosize: true
});

const statusColors = {
  'CIENTE': '#3498db',
  'IMPEDIDO': '#e74c3c',
  'IMPEDIDO_REJEICAO_PLANO_TRABALHO': '#e67e22',
  'REPROVADO': '#9b59b6',
  'CANCELADO': '#95a5a6',
  'EM_EXECUCAO': '#2ecc71',
  'CONCLUIDO': '#1abc9c',
  'NAO_CUMPROU': '#34495e'
};

const getBadgeClass = (status) => {
  const norm = status ? status.toUpperCase() : '';
  if(norm.includes('CIENTE')) return 'badge-ciente';
  if(norm.includes('IMPEDIDO_REJEICAO')) return 'badge-impedido-rejeicao';
  if(norm.includes('IMPEDIDO')) return 'badge-impedido';
  if(norm.includes('REPROVADO')) return 'badge-reprovado';
  if(norm.includes('CANCELADO')) return 'badge-cancelado';
  if(norm.includes('EXECUCAO') || norm.includes('EXECUÇÃO')) return 'badge-execucao';
  if(norm.includes('CONCLUIDO') || norm.includes('CONCLUÍDO')) return 'badge-concluido';
  if(norm.includes('NAO_CUMPROU') || norm.includes('CUMPRIU')) return 'badge-nao-cumprou';
  return 'badge-default';
};

// DOM Elements
const searchInput = document.getElementById('search-input');
const searchAutocomplete = document.getElementById('search-autocomplete');
const emptyState = document.getElementById('empty-state');
const loadingState = document.getElementById('loading-state');
const dashboard = document.getElementById('dashboard');
const profileCard = document.getElementById('profile-card');
const tabs = document.querySelectorAll('.tab-btn');

// Events
let searchTimeout;
searchInput.addEventListener('input', (e) => {
  clearTimeout(searchTimeout);
  const q = e.target.value.trim();
  if(q.length < 3) {
    searchAutocomplete.classList.add('hidden');
    return;
  }
  searchTimeout = setTimeout(() => fetchSearch(q), 300);
});

document.addEventListener('click', (e) => {
  if(!searchAutocomplete.contains(e.target) && e.target !== searchInput) {
    searchAutocomplete.classList.add('hidden');
  }
});

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const tabName = tab.dataset.tab;
    switchTab(tabName);
  });
});

document.getElementById('select-ano').addEventListener('change', (e) => {
  if(state.currentDeputadoId) {
    loadDespesas(state.currentDeputadoId, e.target.value);
  }
});

// API Calls
async function fetchSearch(q) {
  try {
    const res = await fetch(`${API_BASE}/deputados/search?q=${encodeURIComponent(q)}`);
    if(!res.ok) throw new Error('Search failed');
    const data = await res.json();
    renderAutocomplete(data);
  } catch (err) {
    console.error(err);
  }
}

function renderAutocomplete(results) {
  searchAutocomplete.innerHTML = '';
  if(results.length === 0) {
    searchAutocomplete.innerHTML = '<div class="search-item"><div class="search-item-info">Nenhum deputado encontrado.</div></div>';
  } else {
    results.forEach(dep => {
      const div = document.createElement('div');
      div.className = 'search-item';
      div.innerHTML = `
        <img src="${dep.url_foto || ''}" alt="${dep.nome_urna}" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PGNpcmNsZSBjeD0iMTIiIGN5PSI4IiByPSI0IiBmaWxsPSIjY2NjIi8+PHBhdGggZD0iTTEyIDE0Yy00LjQyIDAtOCAzLjU4LTggOHYxaDE2di0xYzAtNC40Mi0zLjU4LTgtOC04eiIgZmlsbD0iI2NjYyIvPjwvc3ZnPg=='">
        <div class="search-item-info">
          <strong>${dep.nome_urna || dep.nome}</strong>
          <span>${dep.sigla_partido} - ${dep.uf}</span>
        </div>
      `;
      div.addEventListener('click', () => {
        searchInput.value = dep.nome_urna || dep.nome;
        searchAutocomplete.classList.add('hidden');
        selectDeputado(dep.deputado_id || dep.id);
      });
      searchAutocomplete.appendChild(div);
    });
  }
  searchAutocomplete.classList.remove('hidden');
}

async function selectDeputado(id) {
  state.currentDeputadoId = id;
  emptyState.classList.add('hidden');
  dashboard.classList.add('hidden');
  loadingState.classList.remove('hidden');

  // Highlight top nav
  document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
  const activeNav = document.querySelector(`.nav-btn[data-nav="deputados"]`);
  if (activeNav) activeNav.classList.add('active');

  // Clear caches
  state.cache = { perfil: {}, emendas: {}, emendasResumo: {}, despesas: {}, comissoes: {}, votacoes: {}, proposicoes: {} };

  try {
    const [perfil, resumo] = await Promise.all([
      fetch(`${API_BASE}/deputados/${id}/perfil`).then(r => r.json()),
      fetch(`${API_BASE}/deputados/${id}/emendas/resumo`).then(r => r.json())
    ]);

    state.cache.perfil[id] = perfil;
    state.cache.emendasResumo[id] = resumo;

    renderPerfil(perfil);
    renderResumo(resumo);

    loadingState.classList.add('hidden');
    dashboard.classList.remove('hidden');

    const sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.style.display = 'block';

    const deputadoSubtabs = document.getElementById('deputado-subtabs');
    if (deputadoSubtabs) deputadoSubtabs.style.display = 'flex';

    // Switch to default tab and trigger load
    switchTab('emendas');
  } catch(err) {
    console.error(err);
    loadingState.innerHTML = '<p style="color:var(--danger)">Erro ao carregar dados do deputado.</p>';
  }
}


function renderPerfil(p) {
  const tseBadge = p.situacao_eleitoral ? `<span class="badge" style="background:rgba(139,92,246,0.15); color:#c4b5fd; border:1px solid #8b5cf6; font-size:0.75rem; margin-top:0.25rem; display:inline-block;">${p.situacao_eleitoral}</span>` : '';
  const patrimonioFmt = p.patrimonio_total && p.patrimonio_total > 0 ? formatBRL(p.patrimonio_total) : 'Declarado à Justiça Eleitoral';

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
  `;
}


function renderResumo(r) {
  document.getElementById('kpi-total-plans').textContent = formatNum(r.total_planos);
  document.getElementById('kpi-total-value').textContent = formatBRL(r.valor_total);
  document.getElementById('kpi-municipalities').textContent = formatNum(r.municipios);
  document.getElementById('kpi-success-rate').textContent = formatPct(r.taxa_sucesso);
}

function switchNavMode(mode) {
  // Update top nav active state
  document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
  const activeNav = document.querySelector(`.nav-btn[data-nav="${mode}"]`);
  if (activeNav) activeNav.classList.add('active');

  const emptyState = document.getElementById('empty-state');
  const dashboard = document.getElementById('dashboard');
  const sidebar = document.querySelector('.sidebar');
  const deputadoSubtabs = document.getElementById('deputado-subtabs');
  const searchWrapper = document.getElementById('search-input')?.parentElement;

  if (mode === 'deputados') {
    if (searchWrapper) searchWrapper.style.display = 'block';

    if (state.currentDeputadoId) {
      if (emptyState) {
        emptyState.classList.remove('active');
        emptyState.classList.add('hidden');
      }
      if (dashboard) {
        dashboard.classList.remove('hidden');
        dashboard.classList.remove('no-sidebar');
      }
      if (sidebar) sidebar.style.display = 'block';
      if (deputadoSubtabs) deputadoSubtabs.style.display = 'flex';
      switchTab('emendas');
    } else {
      if (emptyState) {
        emptyState.classList.remove('hidden');
        emptyState.classList.add('active');
      }
      if (dashboard) dashboard.classList.add('hidden');
    }
  } else {
    // Global modes (Prefeitos, Inteligência, Saúde, Diário)
    if (searchWrapper) searchWrapper.style.display = 'none';
    if (emptyState) {
      emptyState.classList.remove('active');
      emptyState.classList.add('hidden');
    }
    if (dashboard) {
      dashboard.classList.remove('hidden');
      dashboard.classList.add('no-sidebar');
    }

    // Hide deputy sidebar and deputy subtabs in global modes
    if (sidebar) sidebar.style.display = 'none';
    if (deputadoSubtabs) deputadoSubtabs.style.display = 'none';

    switchTab(mode);
  }
}


function switchTab(tabName) {
  state.currentTab = tabName;

  tabs.forEach(t => t.classList.remove('active'));
  const activeTabBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
  if (activeTabBtn) activeTabBtn.classList.add('active');

  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  const activePane = document.getElementById(`tab-${tabName}`);
  if (activePane) activePane.classList.add('active');

  loadTabData(tabName);
}



async function loadTabData(tab) {
  const id = state.currentDeputadoId;
  if(!id && tab !== 'inteligencia' && tab !== 'saude-explorer' && tab !== 'diario' && tab !== 'prefeitos') return;


  try {
    if(tab === 'emendas' && !state.cache.emendas[id]) {
      const data = await fetch(`${API_BASE}/deputados/${id}/emendas`).then(r => r.json());
      state.cache.emendas[id] = data;
      renderEmendasTab(data);
    } else if(tab === 'emendas') {
      renderEmendasTab(state.cache.emendas[id]);
    }

    if(tab === 'despesas') {
      const ano = document.getElementById('select-ano').value;
      loadDespesas(id, ano);
    }

    if(tab === 'comissoes' && !state.cache.comissoes[id]) {
      const data = await fetch(`${API_BASE}/deputados/${id}/comissoes`).then(r => r.json());
      state.cache.comissoes[id] = data;
      renderComissoesTab(data);
    } else if(tab === 'comissoes') {
      renderComissoesTab(state.cache.comissoes[id]);
    }

    if(tab === 'votacoes' && !state.cache.votacoes[id]) {
      const data = await fetch(`${API_BASE}/deputados/${id}/votacoes?limit=50`).then(r => r.json());
      state.cache.votacoes[id] = data;
      renderVotacoesTab(data);
    } else if(tab === 'votacoes') {
      renderVotacoesTab(state.cache.votacoes[id]);
    }

    if(tab === 'proposicoes' && !state.cache.proposicoes[id]) {
      const data = await fetch(`${API_BASE}/deputados/${id}/proposicoes`).then(r => r.json());
      state.cache.proposicoes[id] = data;
      renderProposicoesTab(data);
    } else if(tab === 'proposicoes') {
      renderProposicoesTab(state.cache.proposicoes[id]);
    }

    if(tab === 'inteligencia') {
      loadAnalyticsData();
    }
    if(tab === 'saude-explorer') {
      loadSaudeExplorer();
    }
    if(tab === 'diario') {
      loadDiarioOficial();
    }
    if(tab === 'prefeitos') {
      loadPrefeitosTab('');
    }

  } catch(e) {
    console.error(`Error loading tab ${tab}:`, e);
  }
}

// Emendas Tab
function renderEmendasTab(data) {
  if(!data || !data.length) return;

  // Charts
  const statusCounts = {};
  const munSums = {};

  data.forEach(d => {
    const st = d.plano_acao_situacao || 'Outros';
    statusCounts[st] = (statusCounts[st] || 0) + 1;

    if(d.beneficiario_nome) {
      munSums[d.beneficiario_nome] = (munSums[d.beneficiario_nome] || 0) + (d.valor_total || 0);
    }
  });

  const stLabels = Object.keys(statusCounts);
  const stValues = Object.values(statusCounts);
  const stColors = stLabels.map(l => statusColors[l] || '#95a5a6');

  Plotly.newPlot('chart-emendas-status', [{
    type: 'pie', hole: 0.5,
    labels: stLabels, values: stValues,
    marker: { colors: stColors },
    textinfo: 'percent'
  }], plotlyDarkLayout(''));

  const sortedMun = Object.entries(munSums).sort((a,b) => b[1]-a[1]).slice(0, 15);

  Plotly.newPlot('chart-emendas-mun', [{
    type: 'bar', orientation: 'h',
    y: sortedMun.map(m => m[0]).reverse(),
    x: sortedMun.map(m => m[1]).reverse(),
    marker: { color: '#3b82f6' }
  }], { ...plotlyDarkLayout(''), margin: {l:150, r:20, t:20, b:40} });

  // Table
  const tbody = document.querySelector('#table-emendas tbody');
  tbody.innerHTML = data.map(d => `
    <tr>
      <td>${d.emenda_codigo || '-'}</td>
      <td>${d.beneficiario_nome || '-'}</td>
      <td>${d.beneficiario_uf || '-'}</td>
      <td><span class="badge ${getBadgeClass(d.plano_acao_situacao)}">${d.plano_acao_situacao || '-'}</span></td>
      <td>${formatBRL(d.valor_total)}</td>
      <td>
        <button class="btn-auditoria" onclick="openSaudeModal('${d.beneficiario_ibge}')" ${!d.beneficiario_ibge ? 'disabled title="Sem IBGE"' : ''}>Saúde (Rede)</button>
        <button class="btn-auditoria btn-auditoria-tcu" onclick="openJusticaModal('${(d.beneficiario_cnpj || d.beneficiario_nome || '').replace(/'/g,'')}', '${(d.beneficiario_nome||'').replace(/'/g,'')}')">🔍 Integridade</button>
      </td>
    </tr>
  `).join('');
}

// Despesas Tab
async function loadDespesas(id, ano) {
  try {
    const cacheKey = `${id}_${ano}`;
    if(!state.cache.despesas[cacheKey]) {
      const data = await fetch(`${API_BASE}/deputados/${id}/despesas?ano=${ano}`).then(r => r.json());
      state.cache.despesas[cacheKey] = data;
    }
    renderDespesasTab(state.cache.despesas[cacheKey]);
  } catch (err) {
    console.error(err);
  }
}

function renderDespesasTab(data) {
  if(!data || !data.length) {
    document.querySelector('#table-despesas tbody').innerHTML = '<tr><td colspan="4">Sem despesas no período.</td></tr>';
    Plotly.purge('chart-despesas-cat');
    Plotly.purge('chart-despesas-forn');
    return;
  }

  const catSums = {};
  const fornSums = {};

  data.forEach(d => {
    catSums[d.tipoDespesa] = (catSums[d.tipoDespesa] || 0) + (d.valorLiquido || 0);
    fornSums[d.nomeFornecedor] = (fornSums[d.nomeFornecedor] || 0) + (d.valorLiquido || 0);
  });

  const sortedCats = Object.entries(catSums).sort((a,b) => b[1]-a[1]).slice(0, 15);
  Plotly.newPlot('chart-despesas-cat', [{
    type: 'bar', orientation: 'h',
    y: sortedCats.map(c => c[0].substring(0, 20) + (c[0].length > 20 ? '...' : '')).reverse(),
    x: sortedCats.map(c => c[1]).reverse(),
    marker: { color: '#8b5cf6' }
  }], { ...plotlyDarkLayout(''), margin: {l:150, r:20, t:20, b:40} });

  const sortedForn = Object.entries(fornSums).sort((a,b) => b[1]-a[1]).slice(0, 15);
  Plotly.newPlot('chart-despesas-forn', [{
    type: 'bar', orientation: 'h',
    y: sortedForn.map(f => f[0].substring(0, 15) + (f[0].length > 15 ? '...' : '')).reverse(),
    x: sortedForn.map(f => f[1]).reverse(),
    marker: { color: '#10b981' }
  }], { ...plotlyDarkLayout(''), margin: {l:150, r:20, t:20, b:40} });

  document.querySelector('#table-despesas tbody').innerHTML = data.slice(0,100).map(d => `
    <tr>
      <td>${formatDate(d.dataDocumento)}</td>
      <td>${d.tipoDespesa}</td>
      <td>${d.nomeFornecedor}</td>
      <td>${formatBRL(d.valorLiquido)}</td>
    </tr>
  `).join('');
}

// Comissoes Tab
function renderComissoesTab(data) {
  const container = document.getElementById('list-comissoes');
  if(!data || !data.length) {
    container.innerHTML = '<p>Nenhuma participação em comissão registrada.</p>';
    return;
  }

  container.innerHTML = data.map(c => `
    <div class="list-card">
      <div class="list-card-title">${c.siglaOrgao} - ${c.nomeOrgao}</div>
      <div class="list-card-meta">
        <span><strong>Papel:</strong> ${c.titulo || 'Titular'}</span>
        <span><strong>Período:</strong> ${formatDate(c.dataInicio)} até ${formatDate(c.dataFim)}</span>
      </div>
    </div>
  `).join('');
}

// Votacoes Tab
function renderVotacoesTab(data) {
  if(!data || !data.length) {
    document.getElementById('list-votacoes').innerHTML = '<p>Nenhuma votação registrada.</p>';
    Plotly.purge('chart-votacoes');
    return;
  }

  const vCounts = { 'Sim': 0, 'Não': 0, 'Abstenção': 0, 'Obstrução': 0, 'Outros': 0 };
  data.forEach(d => {
    let v = d.voto ? d.voto.trim() : '';
    if(v.toLowerCase() === 'sim') vCounts['Sim']++;
    else if(v.toLowerCase() === 'não' || v.toLowerCase() === 'nao') vCounts['Não']++;
    else if(v.toLowerCase() === 'abstenção') vCounts['Abstenção']++;
    else if(v.toLowerCase() === 'obstrução') vCounts['Obstrução']++;
    else vCounts['Outros']++;
  });

  Plotly.newPlot('chart-votacoes', [{
    type: 'pie', hole: 0.4,
    labels: Object.keys(vCounts),
    values: Object.values(vCounts),
    marker: { colors: ['#2ecc71', '#e74c3c', '#95a5a6', '#f39c12', '#7f8c8d'] }
  }], plotlyDarkLayout(''));

  document.getElementById('list-votacoes').innerHTML = data.map(d => {
    let vClass = 'vote-other';
    let vText = d.voto ? d.voto.substring(0,3).toUpperCase() : '-';
    if(d.voto && d.voto.toLowerCase() === 'sim') vClass = 'vote-sim';
    if(d.voto && (d.voto.toLowerCase() === 'não' || d.voto.toLowerCase() === 'nao')) vClass = 'vote-nao';

    return `
      <div class="timeline-item">
        <div class="vote-badge ${vClass}">${vText}</div>
        <div class="timeline-content">
          <div class="timeline-title">${d.descricao}</div>
          <div class="timeline-date">${formatDate(d.data)}</div>
        </div>
      </div>
    `;
  }).join('');
}

// Proposicoes Tab
function renderProposicoesTab(data) {
  const container = document.getElementById('list-proposicoes');
  if(!data || !data.length) {
    container.innerHTML = '<p>Nenhuma proposição encontrada.</p>';
    return;
  }

  container.innerHTML = data.map(p => `
    <div class="list-card">
      <div class="list-card-title"><span class="badge badge-default">${p.siglaTipo} ${p.numero}/${p.ano}</span></div>
      <p style="font-size: 0.95rem; margin-top: 0.5rem; line-height: 1.4;">${p.ementa}</p>
      <div class="list-card-meta" style="margin-top: 0.5rem;">
        <span><strong>Apresentação:</strong> ${formatDate(p.dataApresentacao)}</span>
      </div>
    </div>
  `).join('');
}

// ==========================================
// Analytics (Inteligência) Tab
// ==========================================

document.getElementById('btn-load-analytics')?.addEventListener('click', loadAnalyticsData);
document.getElementById('tab-inteligencia-btn')?.addEventListener('click', () => {
    // Show the dashboard shell if it was hidden
    document.getElementById('empty-state').classList.remove('active');
    document.getElementById('dashboard').classList.remove('hidden');
    switchTab('inteligencia');
});

async function loadAnalyticsData() {
  document.getElementById('btn-load-analytics').textContent = 'Carregando...';

  try {
    const [partyRes, socioRes, roiRes] = await Promise.all([
      fetch(`${API_BASE}/analytics/party-efficiency`).then(r => r.json()),
      fetch(`${API_BASE}/analytics/socioeconomic`).then(r => r.json()),
      fetch(`${API_BASE}/analytics/deputy-roi`).then(r => r.json())
    ]);

    if (partyRes.data) renderPartyEfficiency(partyRes.data);
    if (socioRes.data) renderSocioeconomic(socioRes.data);
    if (roiRes.data) renderDeputyRoi(roiRes.data);

  } catch(e) {
    console.error('Failed to load analytics', e);
  } finally {
    document.getElementById('btn-load-analytics').textContent = 'Recarregar Dados';
  }
}

function renderPartyEfficiency(data) {
  // data = [{sigla_partido, status_execucao, total_emendas, valor_total}, ...]
  // We want a stacked bar showing Concluido/Em execucao vs Impedido

  const parties = [...new Set(data.map(d => d.sigla_partido))];

  const statusGroups = {
    'Sucesso': ['CONCLUIDO', 'EM_EXECUCAO'],
    'Impedido': ['IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO', 'CANCELADO', 'NAO_CUMPROU'],
    'Em Andamento': ['CIENTE', 'AGUARDANDO_CIENCIA', 'PLANO_TRABALHO_EM_ELABORACAO']
  };

  const traces = [];
  const colors = {'Sucesso': '#2ecc71', 'Impedido': '#e74c3c', 'Em Andamento': '#3498db'};

  for (const [groupName, statuses] of Object.entries(statusGroups)) {
    const yValues = parties.map(p => {
      return data.filter(d => d.sigla_partido === p && statuses.includes(d.status_execucao))
                 .reduce((sum, d) => sum + d.valor_total, 0);
    });

    traces.push({
      x: parties,
      y: yValues,
      name: groupName,
      type: 'bar',
      marker: { color: colors[groupName] }
    });
  }

  const layout = {
    ...plotlyDarkLayout(''),
    barmode: 'stack',
    xaxis: { title: 'Partido', tickangle: -45, gridcolor: '#334155' },
    yaxis: { title: 'Valor Total (R$)', gridcolor: '#334155' }
  };

  Plotly.newPlot('chart-party-efficiency', traces, layout, {responsive: true});
}

function renderSocioeconomic(data) {
  // data = [{municipio, uf, idhm, pib_per_capita, populacao, total_emendas, qtd_emendas}]

  const trace = {
    x: data.map(d => parseFloat(d.idhm)),
    y: data.map(d => d.total_emendas),
    text: data.map(d => `${d.municipio} - ${d.uf}<br>IDHM: ${d.idhm}<br>População: ${formatNum(d.populacao)}<br>Total R$: ${formatBRL(d.total_emendas)}`),
    mode: 'markers',
    marker: {
      size: data.map(d => Math.max(10, Math.min(d.populacao / 20000, 50))), // scale size based on pop
      color: data.map(d => d.total_emendas),
      colorscale: 'Viridis',
      showscale: true,
      sizemode: 'diameter',
      opacity: 0.7
    }
  };

  const layout = {
    ...plotlyDarkLayout(''),
    xaxis: { title: 'IDHM (Índice de Desenvolvimento Humano)', gridcolor: '#334155' },
    yaxis: { title: 'Valor Recebido em Emendas (R$)', gridcolor: '#334155' },
    hovermode: 'closest'
  };

  Plotly.newPlot('chart-socioeconomic', [trace], layout, {responsive: true});
}

function renderDeputyRoi(data) {
  // data = [{nome, sigla_partido, valor_emendas, valor_despesas}]

  const trace = {
    x: data.map(d => d.valor_despesas),
    y: data.map(d => d.valor_emendas),
    text: data.map(d => `<b>${d.nome} (${d.sigla_partido})</b><br>Emendas Trazidas: ${formatBRL(d.valor_emendas)}<br>Despesas de Gabinete: ${formatBRL(d.valor_despesas)}`),
    mode: 'markers+text',
    textposition: 'top center',
    marker: {
      size: 15,
      color: '#e67e22',
      opacity: 0.8
    }
  };

  const layout = {
    ...plotlyDarkLayout(''),
    xaxis: { title: 'Custo do Deputado (Despesas da Cota - R$)', gridcolor: '#334155' },
    yaxis: { title: 'Retorno para o Estado (Emendas - R$)', gridcolor: '#334155' },
    hovermode: 'closest'
  };

  Plotly.newPlot('chart-deputy-roi', [trace], layout, {responsive: true});
}

// ==========================================
// Auditoria Modals
// ==========================================

function closeModal(modalId) {
  document.getElementById(modalId).classList.add('hidden');
}

async function openSaudeModal(ibge) {
  if (!ibge || ibge === 'undefined') return;
  const modal = document.getElementById('modal-saude');
  const body = document.getElementById('modal-saude-body');

  modal.classList.remove('hidden');
  body.innerHTML = '<div class="spinner"></div><p style="text-align:center; margin-top:1rem;">Buscando infraestrutura de saúde via DataSUS (MCP Brasil)...</p>';

  try {
    const res = await fetch(`${API_BASE}/auditoria/saude/${ibge}`).then(r => r.json());
    if(res.status === 'success' && res.data) {
      body.innerHTML = `<pre style="white-space: pre-wrap; font-family: monospace; font-size: 0.9rem; background: #0f172a; padding: 1rem; border-radius: 8px;">${typeof res.data === 'string' ? res.data : JSON.stringify(res.data, null, 2)}</pre>`;
    } else {
      body.innerHTML = '<p>Não foi possível carregar os dados de saúde.</p>';
    }
  } catch (e) {
    body.innerHTML = `<p style="color:var(--danger)">Erro: ${e.message}</p>`;
  }
}

async function openJusticaModal(cnpj, nomeBeneficiario) {
  if (!cnpj || cnpj === 'undefined') return;
  const modal = document.getElementById('modal-justica');
  const tcuBody = document.getElementById('modal-tcu-body');
  const datajudBody = document.getElementById('modal-justica-body');
  const tcuIcon = document.getElementById('tcu-status-icon');
  const datajudIcon = document.getElementById('datajud-status-icon');

  // Reset state
  document.getElementById('modal-justica-cnpj').textContent = `CNPJ: ${cnpj}${nomeBeneficiario ? ' — ' + nomeBeneficiario : ''}`;
  tcuIcon.textContent = '⏳';
  datajudIcon.textContent = '⏳';
  tcuBody.innerHTML = '<div class="spinner"></div><p style="text-align:center;margin-top:0.5rem;font-size:0.85rem;">Consultando Tribunal de Contas da União...</p>';
  datajudBody.innerHTML = '<div class="spinner"></div><p style="text-align:center;margin-top:0.5rem;font-size:0.85rem;">Consultando cache local DataJud...</p>';
  modal.classList.remove('hidden');

  // Fire both requests in parallel
  const [tcuRes, datajudRes] = await Promise.allSettled([
    fetch(`${API_BASE}/auditoria/tcu?cnpj=${encodeURIComponent(cnpj)}`).then(r => r.json()),
    fetch(`${API_BASE}/auditoria/justica?query=${encodeURIComponent(cnpj)}`).then(r => r.json()),
  ]);

  // --- Render TCU panel ---
  try {
    const tcu = tcuRes.value;
    let rawText = '';
    if (tcu && tcu.data && tcu.data.result) {
      rawText = tcu.data.result;
    } else {
      rawText = typeof tcu.data === 'string' ? tcu.data : JSON.stringify(tcu.data, null, 2);
    }

    // Check specific phrases returned by the mcp-brasil TCU tools
    const cleanInidoneo = rawText.includes('Nenhum licitante inidôneo encontrado');
    const cleanInabilitado = rawText.includes('Nenhum inabilitado encontrado');

    const clean = cleanInidoneo && cleanInabilitado;
    const hasAlert = !clean && rawText.length > 0;

    tcuIcon.textContent = hasAlert ? '🚨' : (clean ? '✅' : '⚠️');
    tcuBody.innerHTML = `
      <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;padding:0.5rem;border-radius:6px;background:${hasAlert ? '#7f1d1d33' : (clean ? '#14532d33' : '#78350f33')};">
        <span style="font-size:1.25rem;">${hasAlert ? '🚨' : (clean ? '✅' : 'ℹ️')}</span>
        <strong style="color:${hasAlert ? '#fca5a5' : (clean ? '#86efac' : '#fde68a')};">${hasAlert ? 'ALERTA: Possível sanção encontrada!' : (clean ? 'Sem sanções registradas' : 'Verificação concluída')}</strong>
      </div>
      <pre style="white-space:pre-wrap;font-family:monospace;font-size:0.8rem;line-height:1.5;">${rawText}</pre>`;
  } catch(e) {
    tcuIcon.textContent = '❌';
    tcuBody.innerHTML = `<p style="color:var(--danger)">Erro ao consultar TCU: ${e.message}</p>`;
  }

  // --- Render DataJud panel ---
  try {
    const dj = datajudRes.value;
    const rawText = typeof dj.data === 'string' ? dj.data : JSON.stringify(dj.data, null, 2);
    const hasProcesses = dj.data && typeof dj.data === 'object' && Array.isArray(dj.data) && dj.data.length > 0;

    // Some endpoints return 'message' instead of a list when no processes are found
    const isCleanMessage = rawText.includes('Nenhum processo encontrado');
    const isError = (rawText.includes('Erro') || rawText.includes('timed out') || rawText.includes('Rate limited') || (dj.data?.message && !isCleanMessage));
    const isPending = rawText.includes('ainda não foram extraídos') || rawText.includes('pendente');

    // Status logic
    let icon = '✅';
    let bg = '#14532d33';
    let textTitle = 'Nenhum processo encontrado';
    let textColor = '#86efac';

    if (isError) {
      icon = '❌';
      bg = '#7f1d1d33';
      textTitle = 'Erro na consulta do DataJud';
      textColor = '#fca5a5';
    } else if (hasProcesses) {
      icon = '⚠️';
      bg = '#78350f33';
      textTitle = `${dj.data.length} processo(s) encontrado(s)`;
      textColor = '#fde68a';
    } else if (isPending) {
      icon = '🕐';
      bg = '#1e293b';
      textTitle = 'Extração pendente';
      textColor = 'var(--text-muted)';
    }

    datajudIcon.textContent = icon;
    datajudBody.innerHTML = `
      <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;padding:0.5rem;border-radius:6px;background:${bg};">
        <span style="font-size:1.25rem;">${icon}</span>
        <strong style="color:${textColor};">${textTitle}</strong>
      </div>
      <pre style="white-space:pre-wrap;font-family:monospace;font-size:0.8rem;line-height:1.5;">${rawText}</pre>`;
  } catch(e) {
    datajudIcon.textContent = '❌';
    datajudBody.innerHTML = `<p style="color:var(--danger)">Erro ao consultar DataJud: ${e.message}</p>`;
  }
}


// ==========================================
// Saúde Explorer
// ==========================================

async function loadSaudeExplorer() {
  const grid = document.getElementById('saude-grid');
  grid.innerHTML = '<div class="spinner"></div><p style="grid-column: 1/-1; text-align: center;">Buscando top municípios...</p>';

  try {
    const res = await fetch(`${API_BASE}/analytics/top-municipios`).then(r => r.json());
    if(res.status === 'success' && res.data) {
      grid.innerHTML = res.data.map(m => `
        <div class="saude-card" id="saude-card-${m.ibge}">
          <h3>${m.nome} - ${m.uf}</h3>
          <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">
            Total Emendas: <strong>${formatBRL(m.total)}</strong>
          </p>
          <div class="spinner" style="margin: 1rem auto;"></div>
          <p style="text-align: center; font-size: 0.85rem;">Buscando infraestrutura no DataSUS...</p>
        </div>
      `).join('');

      // Fetch each municipality in parallel
      res.data.forEach(m => fetchSaudeData(m.ibge));
    }
  } catch (e) {
    grid.innerHTML = `<p style="color:var(--danger)">Erro: ${e.message}</p>`;
  }
}

async function fetchSaudeData(ibge) {
  const card = document.getElementById(`saude-card-${ibge}`);
  if (!card) return;

  try {
    const res = await fetch(`${API_BASE}/auditoria/saude/${ibge}`).then(r => r.json());
    if(res.status === 'success' && res.data && res.data.result) {
      const text = res.data.result;

      // Attempt to extract key metrics using regex (mcp-brasil outputs markdown)
      const estabMatch = text.match(/Total de estabelecimentos ativos:\*\*\s*([\d.]+)/);
      const leitosMatch = text.match(/Total de leitos existentes:\*\*\s*([\d.]+)/);
      const susMatch = text.match(/Total de leitos SUS:\*\*\s*([\d.]+)/);

      const estab = estabMatch ? estabMatch[1] : '?';
      const leitos = leitosMatch ? leitosMatch[1] : '?';
      const sus = susMatch ? susMatch[1] : '?';

      // Keep only the table of establishments for the raw data section to save space
      const tableMatch = text.match(/(\| Tipo \| Quantidade \|[\s\S]*?)(\*\*Avisos:|$)/);
      const tableData = tableMatch ? tableMatch[1].trim() : text;

      card.innerHTML = `
        <h3>${card.querySelector('h3').innerText}</h3>
        ${card.querySelector('p').outerHTML}
        <div class="metrics">
          <div class="metric-badge">Estabelecimentos <strong>${estab}</strong></div>
          <div class="metric-badge">Leitos Totais <strong>${leitos}</strong></div>
          <div class="metric-badge">Leitos SUS <strong>${sus}</strong></div>
        </div>
        <div class="raw-data">${tableData}</div>
      `;
    } else {
      card.innerHTML += `<p style="color:var(--warning)">Dados não encontrados.</p>`;
      const spin = card.querySelector('.spinner');
      if (spin) spin.remove();
    }
  } catch (e) {
    card.innerHTML += `<p style="color:var(--danger)">Falha ao carregar.</p>`;
    const spin = card.querySelector('.spinner');
    if (spin) spin.remove();
  }
}

// Diário Oficial Explorer
async function loadDiarioOficial(query) {
  const container = document.getElementById('diario-results');
  if (!container) return;

  const currentDepName = state.currentDeputadoId && state.cache.perfil ? state.cache.perfil.nome_urna || state.cache.perfil.nome : '';
  const q = query || document.getElementById('diario-search-input')?.value || currentDepName || 'Transferência Especial';

  container.innerHTML = '<div class="spinner"></div><p style="text-align:center; margin-top:1rem;">Buscando diários oficiais federais e municipais (DOU + Querido Diário)...</p>';

  try {
    const res = await fetch(`${API_BASE}/diario/buscar?q=${encodeURIComponent(q)}`).then(r => r.json());
    if (res.status === 'success' && res.data) {
      const rawText = typeof res.data === 'string' ? res.data : JSON.stringify(res.data, null, 2);
      container.innerHTML = `
        <div style="margin-bottom:1rem; padding:0.75rem; background:rgba(59,130,246,0.1); border-left:4px solid var(--accent-blue); border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
          <div><strong>Resultados da busca para:</strong> "${q}"</div>
          <span style="font-size:0.8rem; color:var(--text-muted);">DOU (Federal) + Querido Diário (Municipal)</span>
        </div>
        <pre style="white-space: pre-wrap; font-family: monospace; font-size: 0.85rem; line-height: 1.6; background: var(--bg-dark); padding: 1.25rem; border-radius: 8px; border: 1px solid var(--border-color); color: var(--text-main);">${rawText}</pre>
      `;
    } else {
      container.innerHTML = '<p style="color:var(--danger)">Erro ao buscar no Diário Oficial.</p>';
    }
  } catch (e) {
    container.innerHTML = `<p style="color:var(--danger)">Erro: ${e.message}</p>`;
  }
}

// Setup Diário search listeners
document.addEventListener('DOMContentLoaded', () => {
  const btnSearchDiario = document.getElementById('btn-search-diario');
  const inputDiario = document.getElementById('diario-search-input');

  if (btnSearchDiario && inputDiario) {
    btnSearchDiario.addEventListener('click', () => {
      loadDiarioOficial(inputDiario.value);
    });
    inputDiario.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') loadDiarioOficial(inputDiario.value);
    });
  }

  // Prefeitos Listeners
  const btnSearchPrefeit = document.getElementById('btn-search-prefeitos');
  const btnRankingPrefeit = document.getElementById('btn-ranking-prefeitos');
  const inputPrefeito = document.getElementById('prefeito-search-input');

  if (btnSearchPrefeit && inputPrefeito) {
    btnSearchPrefeit.addEventListener('click', () => {
      loadPrefeitosTab(inputPrefeito.value);
    });
    inputPrefeito.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') loadPrefeitosTab(inputPrefeito.value);
    });
  }
  if (btnRankingPrefeit) {
    btnRankingPrefeit.addEventListener('click', () => {
      if (inputPrefeito) inputPrefeito.value = '';
      loadPrefeitosTab('');
    });
  }
});

// Prefeitos Explorer Tab
async function loadPrefeitosTab(query) {
  const tableBody = document.querySelector('#table-prefeitos tbody');
  if (!tableBody) return;

  tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:1.5rem;"><div class="spinner" style="margin:0 auto 0.5rem;"></div>Carregando prefeitos...</td></tr>';

  try {
    const url = query && query.trim() !== ''
      ? `${API_BASE}/prefeitos/search?q=${encodeURIComponent(query.trim())}`
      : `${API_BASE}/prefeitos/ranking?limit=30`;

    const res = await fetch(url).then(r => r.json());
    renderPrefeitosTable(res);
  } catch (e) {
    tableBody.innerHTML = `<tr><td colspan="7" style="color:var(--danger); text-align:center; padding:1.5rem;">Erro ao carregar prefeitos: ${e.message}</td></tr>`;
  }
}

function renderPrefeitosTable(rows) {
  const tableBody = document.querySelector('#table-prefeitos tbody');
  if (!tableBody) return;

  if (!rows || rows.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:1.5rem; color:var(--text-muted);">Nenhum prefeito ou município encontrado.</td></tr>';
    return;
  }

  tableBody.innerHTML = rows.map(r => `
    <tr>
      <td><strong>${r.municipio_nome || '-'}</strong> <span style="color:var(--text-muted);">(${r.uf || ''})</span></td>
      <td>${r.prefeito_nome || '-'}</td>
      <td><span class="badge badge-default" style="background:#1e293b; border:1px solid #475569; color:#f8fafc;">${r.prefeito_partido || 'N/I'}</span></td>
      <td>${formatNum(r.ibge_populacao)} hab</td>
      <td><strong style="color:var(--success);">${formatBRL(r.valor_total_emendas)}</strong></td>
      <td>${r.emendas_per_capita ? formatBRL(r.emendas_per_capita) + '/hab' : '-'}</td>
      <td>
        <button class="btn-auditar" style="background:var(--accent-blue); color:#fff; border:none; padding:0.35rem 0.75rem; border-radius:6px; font-weight:600; font-size:0.8rem; cursor:pointer;" onclick="openPrefeitoModal(${r.municipio_id})">
          Ver Perfil 🏛️
        </button>
      </td>
    </tr>
  `).join('');
}

async function openPrefeitoModal(municipioId, selectedAno = null) {
  const modal = document.getElementById('modal-prefeito');
  const title = document.getElementById('modal-prefeito-title');
  const subtitle = document.getElementById('modal-prefeito-subtitle');
  const body = document.getElementById('modal-prefeito-body');

  if (!modal || !body) return;

  modal.classList.remove('hidden');
  body.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div><p style="text-align:center;">Carregando perfil do prefeito, dados financeiros e emendas indicadas...</p>';

  try {
    const anoParam = selectedAno ? `?ano=${selectedAno}` : '';
    const [p, emendasRes] = await Promise.all([
      fetch(`${API_BASE}/prefeitos/${municipioId}/perfil`).then(r => r.json()),
      fetch(`${API_BASE}/prefeitos/${municipioId}/emendas${anoParam}`).then(r => r.json())
    ]);

    const emendas = emendasRes.emendas || [];
    const anosDisponiveis = emendasRes.anos_disponiveis || [];
    const totalValor = emendasRes.total_valor !== undefined ? emendasRes.total_valor : p.valor_total_emendas;
    const totalPlanos = emendasRes.total_planos !== undefined ? emendasRes.total_planos : p.total_emendas_recebidas;
    const perCapita = p.ibge_populacao > 0 ? (totalValor / p.ibge_populacao) : 0;

    title.innerText = `🏛️ ${p.prefeito_nome || 'Prefeito não cadastrado'} (${p.prefeito_partido || 'N/I'}/${p.uf})`;
    subtitle.innerText = `Prefeitura Municipal de ${p.municipio_nome} (${p.uf}) — Eleição ${p.ano_eleicao || 2024}`;

    // Montar opções de ano
    let anoSelectHtml = `<select id="modal-ano-filter" onchange="openPrefeitoModal(${municipioId}, this.value)" style="background:var(--bg-dark); color:var(--text-main); border:1px solid var(--border-color); padding:0.35rem 0.75rem; border-radius:6px; font-weight:600; cursor:pointer;">`;
    anoSelectHtml += `<option value="" ${!selectedAno ? 'selected' : ''}>Todos os Anos (Acumulado)</option>`;
    anosDisponiveis.forEach(a => {
      anoSelectHtml += `<option value="${a}" ${String(selectedAno) === String(a) ? 'selected' : ''}>Exercício ${a}</option>`;
    });
    anoSelectHtml += `</select>`;

    const emendasRows = emendas.length > 0 ? emendas.map(e => {
      const isNegado = ['IMPEDIDO', 'REPROVADO', 'CANCELADO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO'].includes(e.plano_acao_situacao);
      const sitColor = isNegado ? 'var(--danger)' : 'var(--success)';
      const auditCnpj = e.beneficiario_cnpj || p.prefeitura_cnpj || p.municipio_nome;
      return `
        <tr style="border-bottom: 1px solid var(--border-color);">
          <td style="padding:0.6rem 0.75rem;"><strong style="color:#60a5fa;">${e.parlamentar_nome}</strong></td>
          <td style="padding:0.6rem 0.75rem; font-size:0.85rem; color:var(--text-muted);">${e.emenda_codigo || '-'} (${e.emenda_ano || '-'})</td>
          <td style="padding:0.6rem 0.75rem; font-size:0.85rem; max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${e.objeto_nome}">${e.objeto_nome}</td>
          <td style="padding:0.6rem 0.75rem;"><strong style="color:var(--success);">${formatBRL(e.valor_total)}</strong></td>
          <td style="padding:0.6rem 0.75rem;"><span class="badge" style="background:rgba(255,255,255,0.05); color:${sitColor}; border:1px solid ${sitColor}; font-size:0.75rem;">${e.plano_acao_situacao}</span></td>
          <td style="padding:0.6rem 0.75rem;">
            <button class="btn-auditoria btn-auditoria-tcu" onclick="openJusticaModal('${auditCnpj.replace(/'/g,'')}', '${(e.parlamentar_nome || '').replace(/'/g,'')}')">🔍 Integridade</button>
          </td>
        </tr>
      `;
    }).join('') : '<tr><td colspan="6" style="text-align:center; padding:1rem; color:var(--text-muted);">Nenhuma emenda registrada para este filtro.</td></tr>';


    // Montar seção SICONFI
    const siconfiHtml = p.siconfi_receitas_correntes && p.siconfi_receitas_correntes > 0 ? `
      <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:1rem; font-size:0.9rem;">
        <div><span style="color:var(--text-muted);">Receita Corrente:</span> <strong style="color:var(--text-main);">${formatBRL(p.siconfi_receitas_correntes)}</strong></div>
        <div><span style="color:var(--text-muted);">Despesa Corrente:</span> <strong style="color:var(--text-main);">${formatBRL(p.siconfi_despesas_correntes)}</strong></div>
        <div><span style="color:var(--text-muted);">Autonomia Fiscal:</span> <strong style="color:var(--accent-blue);">${p.siconfi_autonomia_fiscal_pct || 0}%</strong></div>
      </div>
    ` : `
      <div style="color:var(--text-muted); font-size:0.85rem; font-style:italic;">
        ⚠️ Dados orçamentários do SICONFI/Tesouro Nacional pendentes de homologação pública pelo município para o exercício fiscal.
      </div>
    `;

    const prefCnpj = p.prefeitura_cnpj || '';
    const prefRazao = p.prefeitura_razao_social || `MUNICIPIO DE ${p.municipio_nome}`;

    body.innerHTML = `
      <!-- Filtro por Exercício -->
      <div style="display:flex; justify-content:space-between; align-items:center; background:#0f172a; padding:0.75rem 1.25rem; border-radius:8px; border:1px solid var(--border-color); margin-bottom:1.25rem;">
        <span style="font-weight:600; font-size:0.9rem; color:var(--text-main);">📅 Filtrar Exercício Fiscal da Prefeitura:</span>
        ${anoSelectHtml}
      </div>

      <!-- KPIs do Ano Selecionado -->
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:1rem; margin-bottom:1.5rem;">
        <div style="background:#0f172a; padding:1rem; border-radius:8px; border:1px solid var(--border-color);">
          <div style="font-size:0.8rem; color:var(--text-muted);">População Estimada (IBGE)</div>
          <div style="font-size:1.25rem; font-weight:700; margin-top:0.25rem;">${formatNum(p.ibge_populacao)} hab</div>
          <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem;">Região ${p.ibge_regiao || 'N/I'}</div>
        </div>
        <div style="background:#0f172a; padding:1rem; border-radius:8px; border:1px solid var(--border-color);">
          <div style="font-size:0.8rem; color:var(--text-muted);">Emendas Recebidas ${selectedAno ? `(${selectedAno})` : '(Total)'}</div>
          <div style="font-size:1.25rem; font-weight:700; color:var(--success); margin-top:0.25rem;">${formatBRL(totalValor)}</div>
          <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem;">${formatNum(totalPlanos)} planos de ação</div>
        </div>
        <div style="background:#0f172a; padding:1rem; border-radius:8px; border:1px solid var(--border-color);">
          <div style="font-size:0.8rem; color:var(--text-muted);">Valor Per Capita ${selectedAno ? `(${selectedAno})` : ''}</div>
          <div style="font-size:1.25rem; font-weight:700; color:var(--info); margin-top:0.25rem;">${formatBRL(perCapita)}/hab</div>
          <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem;">Repasse por habitante</div>
        </div>
      </div>

      <!-- Card do Perfil Eleitoral TSE -->
      <div style="margin-bottom:1.5rem; background:#0f172a; padding:1.25rem; border-radius:8px; border:1px solid var(--border-color);">
        <h4 style="margin-bottom:0.75rem; color:#8b5cf6; font-size:1rem; display:flex; align-items:center; gap:0.5rem;">
          <span>🗳️ Perfil Eleitoral (TSE — Eleição ${p.ano_eleicao || 2024})</span>
          <span class="badge" style="background:rgba(139,92,246,0.15); color:#c4b5fd; border:1px solid #8b5cf6; font-size:0.75rem;">${p.situacao_candidatura || 'ELEITO'}</span>
        </h4>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:1rem; font-size:0.9rem;">
          <div><span style="color:var(--text-muted);">Prefeito Eleito:</span> <strong style="color:var(--text-main);">${p.prefeito_nome || 'N/I'}</strong></div>
          <div><span style="color:var(--text-muted);">Partido:</span> <strong style="color:#60a5fa;">${p.prefeito_partido || 'N/I'}</strong></div>
          <div><span style="color:var(--text-muted);">Vice-Prefeito(a):</span> <strong style="color:var(--text-main);">${p.vice_prefeito_nome || 'Não informado'}</strong></div>
          <div><span style="color:var(--text-muted);">Votação TSE:</span> <strong style="color:var(--success);">${p.votos_totais && p.votos_totais > 0 ? formatNum(p.votos_totais) + ' votos (' + (p.percentual_votos || 0) + '%)' : 'Eleito (100% Homologado)'}</strong></div>
        </div>
        <div style="margin-top:0.75rem; font-size:0.85rem; padding-top:0.5rem; border-top:1px dashed var(--border-color); display:flex; justify-content:space-between; flex-wrap:wrap; gap:0.5rem;">
          <div><span style="color:var(--text-muted);">Coligação Eleitoral:</span> <strong style="color:#e2e8f0;">${p.coligacao || 'Partido Isolado'}</strong></div>
          <div><span style="color:var(--text-muted);">Patrimônio Declarado (TSE):</span> <strong style="color:var(--info);">${p.patrimonio_total && p.patrimonio_total > 0 ? formatBRL(p.patrimonio_total) : 'Declarado à Justiça Eleitoral'}</strong></div>
        </div>
      </div>

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
        <button class="btn-auditoria btn-auditoria-tcu" style="padding:0.6rem 1.25rem; font-size:0.85rem; font-weight:600; cursor:pointer;" onclick="openJusticaModal('${(prefCnpj || prefRazao).replace(/'/g,'')}', '${prefRazao.replace(/'/g,'')}')">
          🔍 Consultar TCU & DataJud (CNPJ)
        </button>
      </div>

      <!-- Card SICONFI -->
      <div style="margin-bottom:1.5rem; background:#0f172a; padding:1.25rem; border-radius:8px; border:1px solid var(--border-color);">
        <h4 style="margin-bottom:0.75rem; color:var(--accent-blue); font-size:1rem;">📊 Finanças Públicas & Autonomia Fiscal (SICONFI / Tesouro Nacional)</h4>
        ${siconfiHtml}
      </div>

      <div style="background:#0f172a; padding:1.25rem; border-radius:8px; border:1px solid var(--border-color);">
        <h4 style="margin-bottom:1rem; color:#60a5fa; font-size:1.05rem; display:flex; justify-content:space-between; align-items:center;">
          <span>📜 Emendas Destinadas ao Município & Deputados Autores</span>
          <span style="font-size:0.8rem; color:var(--text-muted); font-weight:normal;">Planos de Ação (${totalPlanos})</span>
        </h4>
        <div style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.85rem;">
            <thead>
              <tr style="border-bottom:2px solid var(--border-color); color:var(--text-muted);">
                <th style="padding:0.5rem 0.75rem;">Deputado / Autor</th>
                <th style="padding:0.5rem 0.75rem;">Código / Ano</th>
                <th style="padding:0.5rem 0.75rem;">Objeto / Destinação</th>
                <th style="padding:0.5rem 0.75rem;">Valor Total</th>
                <th style="padding:0.5rem 0.75rem;">Situação</th>
                <th style="padding:0.5rem 0.75rem;">Ações</th>
              </tr>
            </thead>
            <tbody>
              ${emendasRows}
            </tbody>
          </table>
        </div>
      </div>
    `;

  } catch (e) {
    body.innerHTML = `<p style="color:var(--danger); text-align:center;">Erro ao carregar perfil: ${e.message}</p>`;
  }
}
