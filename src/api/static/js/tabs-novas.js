/* ============================================================================
 * Abas Novas — Senadores, Governadores, Financeiro SICONFI, FNDE
 * + sub-abas do deputado: Discursos, Discricionárias, Alertas
 * Carregado sob demanda via `carregarAbasNovas()` (js loader no app.js).
 * Convenções herdadas do app.js: API_BASE, formatBRL, formatNum, estadoGlobal.
 * ==========================================================================*/

/* ---------- Senadores ---------- */
const TabsSenadores = {
  partidosCarregados: false,

  async init() {
    this.carregarPartidos();
    this.carregarRanking();
  },

  async carregarPartidos() {
    try {
      const data = await fetch(`${API_BASE}/senadores/por-partido`).then(r => r.json());
      const sel = document.getElementById('senador-partido-filter');
      if (!sel || this.partidosCarregados) return;
      data.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.sigla_partido;
        opt.textContent = `${p.sigla_partido} (${p.total})`;
        sel.appendChild(opt);
      });
      this.partidosCarregados = true;
      document.getElementById('kpi-senadores-partidos').textContent = data.length;
      const totalUfs = data.reduce((acc, p) => acc + (p.ufs || 0), 0);
      document.getElementById('kpi-senadores-ufs').textContent = totalUfs;
    } catch (e) {
      console.error('Erro ao carregar partidos de senadores:', e);
    }
  },

  async carregarRanking() {
    const tableBody = document.querySelector('#table-senadores tbody');
    if (!tableBody) return;
    const partido = document.getElementById('senador-partido-filter').value;
    const uf = document.getElementById('senador-uf-filter')?.value || '';
    tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:1.5rem;"><div class="spinner" style="margin:0 auto 0.5rem;"></div>Carregando senadores...</td></tr>';
    try {
      const params = new URLSearchParams({ limit: 81 });
      if (partido) params.set('partido', partido);
      if (uf) params.set('uf', uf);
      const data = await fetch(`${API_BASE}/senadores/ranking?${params}`).then(r => r.json());
      document.getElementById('kpi-senadores-total').textContent = data.length;
      this.renderTabela(data);
    } catch (e) {
      tableBody.innerHTML = `<tr><td colspan="6" style="color:var(--danger); text-align:center; padding:1.5rem;">Erro ao carregar senadores: ${e.message}</td></tr>`;
    }
  },

  renderTabela(rows) {
    const tableBody = document.querySelector('#table-senadores tbody');
    if (!tableBody) return;
    if (!rows || rows.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:1.5rem; color:var(--text-muted);">Nenhum senador encontrado.</td></tr>';
      return;
    }
    tableBody.innerHTML = rows.map(r => `
      <tr>
        <td>
          <div style="display:flex; align-items:center; gap:0.75rem;">
            ${r.foto_url ? `<img src="${r.foto_url}" alt="" style="width:38px; height:38px; border-radius:50%; object-fit:cover; border:1px solid var(--border-color);">` : '<div style="width:38px; height:38px; border-radius:50%; background:var(--border-color); display:flex; align-items:center; justify-content:center;">🏛️</div>'}
            <div>
              <strong>${r.nome_parlamentar || '-'}</strong>
              <div style="color:var(--text-muted); font-size:0.8rem;">${r.nome_completo || ''}</div>
            </div>
          </div>
        </td>
        <td><span class="badge badge-default" style="background:#1e293b; border:1px solid #475569; color:#f8fafc;">${r.sigla_partido || 'N/I'}</span></td>
        <td>${r.uf || '-'}</td>
        <td><span class="badge" style="background:rgba(34,197,94,0.12); color:#22c55e; border:1px solid rgba(34,197,94,0.3);">${r.situacao || '-'}</span></td>
        <td>${formatNum(r.atividade_total || 0)} <span style="color:var(--text-muted); font-size:0.8rem;">(${formatNum(r.total_votacoes || 0)} votos · ${formatNum(r.total_relatorias || 0)} rel.)</span></td>
        <td><button class="btn-auditar" style="background:var(--accent-blue); color:#fff; border:none; padding:0.35rem 0.75rem; border-radius:6px; font-weight:600; font-size:0.8rem; cursor:pointer;" onclick="TabsSenadores.abrirPerfil(${r.senador_codigo})">Ver Perfil</button></td>
      </tr>
    `).join('');
  },

  async buscar() {
    const q = document.getElementById('senador-search-input').value.trim();
    if (!q) { this.carregarRanking(); return; }
    const tableBody = document.querySelector('#table-senadores tbody');
    tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:1.5rem;"><div class="spinner" style="margin:0 auto 0.5rem;"></div>Buscando...</td></tr>';
    try {
      const data = await fetch(`${API_BASE}/senadores/search?q=${encodeURIComponent(q)}`).then(r => r.json());
      this.renderTabela(data);
    } catch (e) {
      tableBody.innerHTML = `<tr><td colspan="6" style="color:var(--danger); text-align:center; padding:1.5rem;">Erro: ${e.message}</td></tr>`;
    }
  },

  async abrirPerfil(codigo) {
    const modal = document.getElementById('modal-generico');
    if (!modal) return;
    modal.classList.remove('hidden');
    const body = document.getElementById('modal-generico-body');
    body.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div><p style="text-align:center;">Carregando perfil do senador...</p>';
    try {
      const p = await fetch(`${API_BASE}/senadores/${codigo}/perfil`).then(r => r.json());
      document.getElementById('modal-generico-title').innerText = `🏛️ ${p.nome_parlamentar || 'Senador'}`;
      const campos = [
        ['Nome Completo', p.nome_completo],
        ['Partido', p.sigla_partido],
        ['UF', p.uf],
        ['Situação', p.situacao],
        ['Legislatura', p.legislatura],
        ['Data Nascimento', p.data_nascimento ? String(p.data_nascimento).slice(0, 10) : null],
        ['Naturalidade', p.naturalidade],
        ['Total Votações', p.total_votacoes != null ? formatNum(p.total_votacoes) : null],
        ['Total Relatorias', p.total_relatorias != null ? formatNum(p.total_relatorias) : null],
        ['Atividade Total', p.total_votacoes != null ? formatNum((p.total_votacoes || 0) + (p.total_relatorias || 0)) : null],
      ];
      body.innerHTML = `
        <div style="display:flex; gap:1.5rem; align-items:flex-start; flex-wrap:wrap;">
          ${p.foto_url ? `<img src="${p.foto_url}" style="width:110px; height:110px; border-radius:12px; object-fit:cover; border:1px solid var(--border-color);">` : ''}
          <div style="flex:1; min-width:280px;">
            ${campos.filter(c => c[1] != null && c[1] !== '').map(([k, v]) => `
              <div style="display:flex; justify-content:space-between; padding:0.5rem 0; border-bottom:1px solid var(--border-color);">
                <span style="color:var(--text-muted);">${k}</span><strong>${v}</strong>
              </div>`).join('')}
          </div>
        </div>`;
    } catch (e) {
      body.innerHTML = `<p style="color:var(--danger); text-align:center;">Erro ao carregar perfil: ${e.message}</p>`;
    }
  },
};

/* ---------- Governadores ---------- */
const TabsGovernadores = {
  async init() {
    this.carregarPartidos();
    this.carregarRanking();
    this.carregarTriangulo();
  },

  async carregarPartidos() {
    try {
      const data = await fetch(`${API_BASE}/governadores`).then(r => r.json());
      const sel = document.getElementById('governador-partido-filter');
      if (!sel) return;
      const partidos = new Set((Array.isArray(data) ? data : []).map(g => g.sigla_partido).filter(Boolean));
      [...partidos].sort().forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        opt.textContent = p;
        sel.appendChild(opt);
      });
    } catch (e) { console.error('Erro governadores partidos:', e); }
  },

  async carregarRanking() {
    const tbody = document.querySelector('#table-governadores tbody');
    if (!tbody) return;
    const partido = document.getElementById('governador-partido-filter').value;
    const params = new URLSearchParams({ limit: 27 });
    if (partido) params.set('partido', partido);
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:1.5rem;"><div class="spinner" style="margin:0 auto 0.5rem;"></div>Carregando governadores...</td></tr>';
    try {
      const [emendas, alinhamento] = await Promise.all([
        fetch(`${API_BASE}/governadores/ranking/emendas?${params}`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/governadores/ranking/alinhamento`).then(r => r.json()).catch(() => []),
      ]);
      const alinMap = new Map((Array.isArray(alinhamento) ? alinhamento : []).map(a => [a.uf, a]));
      this.renderTabela(Array.isArray(emendas) ? emendas : [], alinMap);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="color:var(--danger); text-align:center; padding:1.5rem;">Erro: ${e.message}</td></tr>`;
    }
  },

  renderTabela(rows, alinMap) {
    const tbody = document.querySelector('#table-governadores tbody');
    if (!tbody) return;
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:1.5rem; color:var(--text-muted);">Nenhum governador encontrado.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(r => {
      const al = alinMap.get(r.uf);
      const alinPct = al && al.alinhamento_pct != null ? al.alinhamento_pct : null;
      return `
      <tr>
        <td><strong>${r.uf}</strong></td>
        <td>${r.nome_governador || r.governador_nome || '-'}</td>
        <td><span class="badge badge-default" style="background:#1e293b; border:1px solid #475569; color:#f8fafc;">${r.sigla_partido || 'N/I'}</span></td>
        <td><strong style="color:var(--success);">${formatBRL(r.total_emendas_brl != null ? r.total_emendas_brl : r.total_emendas)}</strong> <span style="color:var(--text-muted); font-size:0.8rem;">(${formatNum(r.total_planos || 0)} planos)</span></td>
        <td>${alinPct != null
          ? `<div style="display:flex; align-items:center; gap:0.5rem;"><div style="width:70px; height:6px; background:var(--border-color); border-radius:3px; overflow:hidden;"><div style="width:${alinPct}%; height:100%; background:${alinPct >= 60 ? 'var(--success)' : alinPct >= 40 ? '#f59e0b' : 'var(--danger)'};"></div></div><strong>${Math.round(alinPct)}%</strong></div>`
          : '<span style="color:var(--text-muted);">—</span>'}
        </td>
        <td><button class="btn-auditar" style="background:var(--accent-blue); color:#fff; border:none; padding:0.35rem 0.75rem; border-radius:6px; font-weight:600; font-size:0.8rem; cursor:pointer;" onclick="TabsGovernadores.abrirPerfil('${r.uf}')">Ver Perfil</button></td>
      </tr>`;
    }).join('');
  },

  async carregarTriangulo() {
    const el = document.getElementById('triangulo-container');
    if (!el) return;
    el.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div>';
    try {
      const data = await fetch(`${API_BASE}/governadores/triangulo-politico?limit=8`).then(r => r.json());
      if (!Array.isArray(data) || data.length === 0) { el.innerHTML = ''; return; }
      el.innerHTML = `
        <div class="table-card">
          <h3>🔺 Triângulo Político — Deputado × Prefeito × Governador</h3>
          <div class="table-responsive">
            <table>
              <thead><tr><th>Deputado</th><th>Município</th><th>Prefeito</th><th>Governador</th><th>Emendas</th></tr></thead>
              <tbody>
                ${data.map(t => `
                  <tr>
                    <td><strong>${t.deputado_nome}</strong> <span class="badge badge-default" style="background:#1e293b; border:1px solid #475569; color:#f8fafc;">${t.partido_deputado}</span></td>
                    <td>${t.municipio_nome} <span style="color:var(--text-muted);">(${t.uf})</span></td>
                    <td>${t.prefeito_nome || '-'} <span class="badge badge-default" style="background:#1e293b; border:1px solid #475569; color:#f8fafc;">${t.partido_prefeito || ''}</span></td>
                    <td>${t.nome_governador || '-'} <span class="badge badge-default" style="background:#1e293b; border:1px solid #475569; color:#f8fafc;">${t.partido_governador || ''}</span></td>
                    <td><strong style="color:var(--success);">${formatBRL(t.total_emendas_brl)}</strong></td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>`;
    } catch (e) { el.innerHTML = ''; }
  },

  async abrirPerfil(uf) {
    const modal = document.getElementById('modal-generico');
    if (!modal) return;
    modal.classList.remove('hidden');
    const body = document.getElementById('modal-generico-body');
    body.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div><p style="text-align:center;">Carregando perfil do governador...</p>';
    try {
      const [p, fin] = await Promise.all([
        fetch(`${API_BASE}/governadores/${uf}/perfil`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/governadores/${uf}/financeiro`).then(r => r.json()).catch(() => null),
      ]);
      if (!p) { body.innerHTML = '<p style="color:var(--danger); text-align:center;">Perfil não encontrado.</p>'; return; }
      document.getElementById('modal-generico-title').innerText = `🌎 ${p.nome_governador || uf}`;
      const f = Array.isArray(fin) && fin.length ? fin[0] : (fin && fin.dados ? fin.dados[0] : null);
      const kpis = [];
      if (f) {
        kpis.push(['Receitas Correntes', formatBRL(f.receitas_correntes)]);
        kpis.push(['Despesas Totais', formatBRL(f.despesas_totais)]);
        kpis.push(['Resultado Orçamentário', formatBRL(f.resultado_orcamentario)]);
        kpis.push(['Arrecadação ICMS', formatBRL(f.arrec_icms)]);
        kpis.push(['FPE', formatBRL(f.arrec_cota_fpe)]);
        kpis.push(['FUNDEB', formatBRL(f.arrec_fundeb)]);
      }
      const campos = [
        ['Partido', p.sigla_partido],
        ['Coligação', p.coligacao],
        ['1º Turno', p.votos_1_turno != null ? formatNum(p.votos_1_turno) : null],
        ['2º Turno', p.votos_2_turno != null ? formatNum(p.votos_2_turno) : null],
        ['% 2º Turno', p.pct_2_turno != null ? `${p.pct_2_turno}%` : null],
        ['Ano Eleição', p.ano_eleicao],
        ...kpis,
      ];
      body.innerHTML = `
        <div style="display:flex; gap:1.5rem; align-items:flex-start; flex-wrap:wrap;">
          <div style="flex:1; min-width:280px;">
            ${campos.filter(c => c[1] != null && c[1] !== '').map(([k, v]) => `
              <div style="display:flex; justify-content:space-between; padding:0.5rem 0; border-bottom:1px solid var(--border-color);">
                <span style="color:var(--text-muted);">${k}</span><strong>${v}</strong>
              </div>`).join('')}
          </div>
        </div>`;
    } catch (e) {
      body.innerHTML = `<p style="color:var(--danger); text-align:center;">Erro: ${e.message}</p>`;
    }
  },
};

/* ---------- Financeiro SICONFI ---------- */
const TabsFinanceiro = {
  esferaAtual: 'estados',

  async carregar(esfera) {
    this.esferaAtual = esfera || this.esferaAtual;
    document.querySelectorAll('[data-fin-esfera]').forEach(b => {
      b.classList.toggle('active', b.dataset.finEsfera === this.esferaAtual);
    });
    this.carregarComparativo();
    if (this.esferaAtual === 'estados') {
      this.carregarEstados();
    } else {
      this.carregarMunicipios();
    }
  },

  async carregarComparativo() {
    const tbody = document.querySelector('#table-fin-comparativo tbody');
    if (!tbody) return;
    const uf = document.getElementById('financeiro-uf-filter').value;
    const params = uf ? `?uf=${uf}` : '';
    try {
      const data = await fetch(`${API_BASE}/financeiro/comparativo${params}`).then(r => r.json());
      if (!Array.isArray(data)) return;
      tbody.innerHTML = data.map(r => {
        const razao = r.arrecadacao_propria > 0 ? (r.valor_emendas / r.arrecadacao_propria) * 100 : null;
        return `
        <tr>
          <td><strong>${r.uf}</strong></td>
          <td>${formatNum(r.total_planos)}</td>
          <td><strong style="color:var(--success);">${formatBRL(r.valor_emendas)}</strong></td>
          <td>${formatBRL(r.arrecadacao_propria)}</td>
          <td>${formatBRL(r.arrec_icms)}</td>
          <td>${formatBRL(r.arrec_fpm)}</td>
          <td>${razao != null ? `<span class="badge" style="background:rgba(${razao > 15 ? '239,68,68' : '34,197,94'},0.12); color:${razao > 15 ? '#ef4444' : '#22c55e'}; border:1px solid currentColor;">${razao.toFixed(1)}%</span>` : '—'}</td>
        </tr>`;
      }).join('');
    } catch (e) { tbody.innerHTML = ''; }
  },

  async carregarEstados() {
    const tbody = document.querySelector('#table-financeiro tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:1.5rem;"><div class="spinner" style="margin:0 auto 0.5rem;"></div>Carregando estados...</td></tr>';
    try {
      const data = await fetch(`${API_BASE}/financeiro/estados`).then(r => r.json());
      this.renderTabela(Array.isArray(data) ? data : []);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="8" style="color:var(--danger); text-align:center; padding:1.5rem;">Erro: ${e.message}</td></tr>`;
    }
  },

  async carregarMunicipios() {
    const tbody = document.querySelector('#table-financeiro tbody');
    if (!tbody) return;
    const uf = document.getElementById('financeiro-uf-filter').value;
    const order = document.getElementById('financeiro-order-filter').value;
    const params = new URLSearchParams({ limit: 100, order_by: order });
    if (uf) params.set('uf', uf);
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:1.5rem;"><div class="spinner" style="margin:0 auto 0.5rem;"></div>Carregando municípios...</td></tr>';
    try {
      const data = await fetch(`${API_BASE}/financeiro/municipios?${params}`).then(r => r.json());
      this.renderTabela(Array.isArray(data) ? data : []);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="8" style="color:var(--danger); text-align:center; padding:1.5rem;">Erro: ${e.message}</td></tr>`;
    }
  },

  renderTabela(rows) {
    const tbody = document.querySelector('#table-financeiro tbody');
    if (!tbody) return;
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:1.5rem; color:var(--text-muted);">Nenhum dado financeiro encontrado.</td></tr>';
      return;
    }
    const ehEstado = this.esferaAtual === 'estados';
    tbody.innerHTML = rows.map(r => {
      const resultado = r.resultado_orcamentario;
      const resultadoColor = resultado >= 0 ? 'var(--success)' : 'var(--danger)';
      return `
      <tr>
        <td><strong>${r.uf || r.nome}</strong></td>
        <td>${r.uf ? '' : r.uf}</td>
        <td>${r.populacao != null ? formatNum(r.populacao) + ' hab' : '—'}</td>
        <td>${formatBRL(r.receitas_correntes != null ? r.receitas_correntes : r.receitas_orcamentarias)}</td>
        <td>${formatBRL(r.despesas_totais)}</td>
        <td style="color:${resultadoColor};"><strong>${formatBRL(resultado)}</strong></td>
        <td><strong style="color:var(--accent-blue);">${formatBRL(r.arrec_impostos_geral != null ? r.arrec_impostos_geral : r.arrecadacao_total)}</strong></td>
        <td>${ehEstado
          ? `<button class="btn-auditar" style="background:var(--border-color); color:var(--text-main); border:none; padding:0.35rem 0.75rem; border-radius:6px; font-weight:600; font-size:0.8rem; cursor:pointer;" onclick="TabsGovernadores.abrirPerfil('${r.uf}')">Governador</button>`
          : `<button class="btn-auditar" style="background:var(--accent-blue); color:#fff; border:none; padding:0.35rem 0.75rem; border-radius:6px; font-weight:600; font-size:0.8rem; cursor:pointer;" onclick="TabsMunicipio.abrirModal(${r.municipio_id})">Indicadores</button>`}
        </td>
      </tr>`;
    }).join('');
  },
};

/* ---------- Município (modal indicadores) ---------- */
const TabsMunicipio = {
  async abrirModal(municipioId) {
    const modal = document.getElementById('modal-generico');
    if (!modal) return;
    modal.classList.remove('hidden');
    const body = document.getElementById('modal-generico-body');
    body.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div><p style="text-align:center;">Carregando indicadores do município...</p>';
    try {
      const [dados, fin] = await Promise.all([
        fetch(`${API_BASE}/municipios/${municipioId}/indicadores`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/municipios/${municipioId}/financeiro`).then(r => r.json()).catch(() => null),
      ]);
      const d = dados || fin || {};
      document.getElementById('modal-generico-title').innerText = `🏙️ ${d.nome || 'Município'} (${d.uf || ''})`;
      const secao = (titulo, itens) => itens.some(i => i[1] != null && i[1] !== '')
        ? `<h4 style="margin:1.25rem 0 0.5rem; color:var(--accent-blue);">${titulo}</h4>
           ${itens.filter(i => i[1] != null && i[1] !== '').map(([k, v]) => `
             <div style="display:flex; justify-content:space-between; padding:0.4rem 0; border-bottom:1px solid var(--border-color); font-size:0.9rem;">
               <span style="color:var(--text-muted);">${k}</span><strong>${v}</strong>
             </div>`).join('')}`
        : '';
      body.innerHTML = `
        <div>
          ${secao('📊 Demografia (IBGE)', [
            ['População', d.populacao != null ? formatNum(d.populacao) + ' hab' : null],
            ['PIB per capita', d.pib_per_capita != null ? formatBRL(d.pib_per_capita) : null],
            ['IDHM', d.idhm],
            ['Área (km²)', d.area_km2 != null ? formatNum(d.area_km2) : null],
          ])}
          ${secao('💰 Financeiro (SICONFI)', [
            ['Receitas Correntes', formatBRL(d.receitas_correntes)],
            ['Despesas Totais', formatBRL(d.despesas_totais)],
            ['Resultado Orçamentário', formatBRL(d.resultado_orcamentario)],
            ['Arrecadação Geral', formatBRL(d.arrec_impostos_geral)],
            ['IPTU', formatBRL(d.arrec_iptu)],
            ['ISS', formatBRL(d.arrec_iss)],
            ['FPM', formatBRL(d.arrec_cota_fpm)],
            ['ICMS', formatBRL(d.arrec_cota_icms)],
          ])}
          ${secao('🏥 Saúde (CNES)', [
            ['Estabelecimentos', d.total_estabelecimentos != null ? formatNum(d.total_estabelecimentos) : null],
            ['Hospitais', d.hospitais != null ? formatNum(d.hospitais) : null],
            ['UBS', d.ubs != null ? formatNum(d.ubs) : null],
            ['CAPS', d.caps != null ? formatNum(d.caps) : null],
            ['Leitos SUS', d.leitos_sus != null ? formatNum(d.leitos_sus) : null],
            ['Profissionais', d.total_profissionais != null ? formatNum(d.total_profissionais) : null],
          ])}
          ${secao('🎓 Educação (INEP)', [
            ['IDEB Anos Iniciais', d.ideb_initial_years],
            ['IDEB Anos Finais', d.ideb_final_years],
            ['Taxa Aprovação', d.taxa_aprovacao != null ? d.taxa_aprovacao + '%' : null],
            ['Taxa Abandono', d.taxa_abandono != null ? d.taxa_abandono + '%' : null],
            ['Matrículas', d.matriculas_totais != null ? formatNum(d.matriculas_totais) : null],
          ])}
          ${secao('🛡️ Violência', [
            ['Homicídios', d.homicidios != null ? formatNum(d.homicidios) : null],
            ['Taxa homicídios', d.taxa_homicidios != null ? d.taxa_homicidios + '/100k' : null],
            ['Mortes trânsito', d.mortes_transito != null ? formatNum(d.mortes_transito) : null],
            ['Roubos', d.roubos != null ? formatNum(d.roubos) : null],
          ])}
        </div>`;
    } catch (e) {
      body.innerHTML = `<p style="color:var(--danger); text-align:center;">Erro: ${e.message}</p>`;
    }
  },
};

/* ---------- FNDE ---------- */
const TabsFnde = {
  async init() {
    const tbody = document.querySelector('#table-fnde tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:1.5rem;"><div class="spinner" style="margin:0 auto 0.5rem;"></div>Carregando repasses FNDE...</td></tr>';
    try {
      const [resumo, municipios] = await Promise.all([
        fetch(`${API_BASE}/fnde/resumo`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/fnde/municipios?limit=100`).then(r => r.json()).catch(() => []),
      ]);
      if (Array.isArray(resumo) && resumo.length) {
        const totalMatriculas = resumo.reduce((a, r) => a + (r.total_matriculas || 0), 0);
        const totalAlunos = resumo.reduce((a, r) => a + (r.total_alunos || 0), 0);
        const totalMunicipios = resumo.reduce((a, r) => a + (r.total_municipios || 0), 0);
        document.getElementById('kpi-fnde-count').textContent = formatNum(resumo.length * 100);
        document.getElementById('kpi-fnde-municipios').textContent = formatNum(totalMunicipios);
        document.getElementById('kpi-fnde-exercicio').textContent = String((municipios[0] && municipios[0].ultima_atualizacao || '').slice(0, 4)) || '—';
      }
      const totalRepassado = (Array.isArray(municipios) ? municipios : []).reduce((a, r) => a + (r.total_beneficiados || 0), 0);
      document.getElementById('kpi-fnde-total').textContent = formatNum(totalRepassado) + ' alunos';
      this.renderTabela(Array.isArray(municipios) ? municipios : []);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" style="color:var(--danger); text-align:center; padding:1.5rem;">Erro: ${e.message}</td></tr>`;
    }
  },

  renderTabela(rows) {
    const tbody = document.querySelector('#table-fnde tbody');
    if (!tbody) return;
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:1.5rem; color:var(--text-muted);">Nenhum repasse encontrado.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td><strong>${r.municipio || '-'}</strong></td>
        <td>${r.uf || ''}</td>
        <td><span class="badge" style="background:rgba(56,189,248,0.12); color:#38bdf8; border:1px solid rgba(56,189,248,0.3);">FUNDEB/PNAE/PNLD</span></td>
        <td><strong style="color:var(--success);">${formatNum(r.total_beneficiados || 0)} alunos</strong></td>
        <td>${(r.ultima_atualizacao || '').slice(0, 10) || '-'}</td>
      </tr>`).join('');
  },
};

/* ---------- Sub-abas do Deputado ---------- */
const DeputadoExtra = {
  async discursos(id) {
    const list = document.getElementById('list-discursos');
    if (!list) return;
    list.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div>';
    try {
      const tipo = document.getElementById('discursos-tipo-filter')?.value || '';
      const params = new URLSearchParams({ limit: 100 });
      if (tipo) params.set('tipo', tipo);
      const data = await fetch(`${API_BASE}/deputados/${id}/discursos?${params}`).then(r => r.json());
      if (!Array.isArray(data) || data.length === 0) {
        list.innerHTML = '<div style="padding:2rem; text-align:center; color:var(--text-muted);">Nenhum discurso registrado para este deputado.</div>';
        return;
      }
      list.innerHTML = data.map(d => `
        <div class="timeline-item" style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:10px; padding:1rem; margin-bottom:0.75rem;">
          <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.5rem;">
            <strong style="color:var(--accent-blue);">${d.tipo_discurso || 'Discurso'}</strong>
            <span style="color:var(--text-muted); font-size:0.85rem;">${(d.data_hora_inicio || '').replace('T', ' ').slice(0, 16)}</span>
          </div>
          <div style="color:var(--text-muted); font-size:0.85rem; margin-bottom:0.5rem;">${d.fase_evento || ''}</div>
          ${d.sumario ? `<p style="font-size:0.9rem; margin-bottom:0.5rem;">${d.sumario}</p>` : ''}
          ${d.keywords ? `<div style="display:flex; flex-wrap:wrap; gap:0.35rem;">${String(d.keywords).split(',').slice(0, 12).map(k => `<span class="badge" style="background:rgba(139,92,246,0.12); color:#a78bfa; border:1px solid rgba(139,92,246,0.3); font-size:0.72rem;">${k.trim()}</span>`).join('')}</div>` : ''}
          ${d.url_texto ? `<a href="${d.url_texto}" target="_blank" rel="noopener" style="color:var(--accent-blue); font-size:0.8rem;">📄 Texto integral</a>` : ''}
        </div>`).join('');
    } catch (e) {
      list.innerHTML = `<div style="padding:1.5rem; color:var(--danger); text-align:center;">Erro: ${e.message}</div>`;
    }
  },

  async discricionarias(id) {
    const list = document.getElementById('list-discricionarias');
    if (!list) return;
    list.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div>';
    try {
      const data = await fetch(`${API_BASE}/deputados/${id}/emendas-discricionarias?limit=100`).then(r => r.json());
      if (!Array.isArray(data) || data.length === 0) {
        list.innerHTML = '<div style="padding:2rem; text-align:center; color:var(--text-muted);">Nenhuma emenda discricionária sincronizada para este deputado.</div>';
        return;
      }
      list.innerHTML = data.map(e => `
        <div class="timeline-item" style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:10px; padding:1rem; margin-bottom:0.75rem;">
          <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.5rem;">
            <strong style="color:var(--accent-blue);">${e.codigo_emenda || '-'} <span style="color:var(--text-muted); font-weight:400;">(${e.ano || '-'})</span></strong>
            <span class="badge" style="background:rgba(${e.status_execucao === 'CONCLUIDO' ? '34,197,94' : '245,158,11'},0.12); color:${e.status_execucao === 'CONCLUIDO' ? '#22c55e' : '#f59e0b'}; border:1px solid currentColor;">${e.status_execucao || 'EM ANDAMENTO'}</span>
          </div>
          ${e.objeto ? `<div style="font-size:0.9rem; margin-bottom:0.5rem;">${e.objeto}</div>` : ''}
          <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:0.5rem; font-size:0.85rem;">
            <span style="color:var(--text-muted);">${e.tipo_emenda || ''}</span>
            <strong style="color:var(--success);">${formatBRL(e.valor_total)}</strong>
          </div>
        </div>`).join('');
    } catch (e) {
      list.innerHTML = `<div style="padding:1.5rem; color:var(--danger); text-align:center;">Erro: ${e.message}</div>`;
    }
  },

  async alertas(id) {
    const list = document.getElementById('list-alertas');
    if (!list) return;
    list.innerHTML = '<div class="spinner" style="margin:1rem auto;"></div>';
    try {
      const data = await fetch(`${API_BASE}/deputados/${id}/alertas`).then(r => r.json());
      if (!Array.isArray(data) || data.length === 0) {
        list.innerHTML = '<div style="padding:2rem; text-align:center; color:var(--text-muted);">Nenhum alerta automático para este deputado.</div>';
        return;
      }
      const cores = { 1: '#ef4444', 2: '#f59e0b', 3: '#38bdf8' };
      list.innerHTML = data.map(a => `
        <div class="timeline-item" style="background:var(--bg-card); border:1px solid ${cores[a.nivel_relevancia] || '#475569'}; border-radius:10px; padding:1rem; margin-bottom:0.75rem; border-left:4px solid ${cores[a.nivel_relevancia] || '#475569'};">
          <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.5rem;">
            <strong style="color:${cores[a.nivel_relevancia] || 'var(--text-main)'};">
              ${a.nivel_relevancia === 1 ? '🔴 Crítico' : a.nivel_relevancia === 2 ? '🟠 Atenção' : '🔵 Informativo'}
            </strong>
            <span style="color:var(--text-muted); font-size:0.85rem;">${(a.criado_em || '').replace('T', ' ').slice(0, 16)}</span>
          </div>
          <div style="font-size:0.9rem;">${a.parlamentar_nome || ''} — ato #${a.ato_id || '-'}</div>
          ${a.notificado ? '<div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.3rem;">✓ Notificado</div>' : ''}
        </div>`).join('');
    } catch (e) {
      list.innerHTML = `<div style="padding:1.5rem; color:var(--danger); text-align:center;">Erro: ${e.message}</div>`;
    }
  },
};

/* ---------- Auditoria RAG (Logit Lens) ---------- */
const TabsRagEfficiency = {
  async init() {
    this.carregarDados();
    document.getElementById('btn-load-rag')?.addEventListener('click', () => this.carregarDados());
  },

  async carregarDados() {
    try {
      // 1. Carregar métricas de evolução (hit rate e faithfulness dos runs)
      const runs = await fetch(`${API_BASE}/rag-efficiency/runs?limit=50`).then(r => r.json());
      this.renderEvolucao(runs);

      // 2. Tentar carregar detalhes de métricas com logit lens para o último run
      if (runs && runs.length > 0) {
        const lastRunId = runs[0].id;
        const metrics = await fetch(`${API_BASE}/rag-efficiency/runs/${lastRunId}/metrics`).then(r => {
          if (!r.ok) return [];
          return r.json();
        });
        this.renderMetricsTable(metrics, lastRunId);
        this.renderLogitLens(metrics);
      } else {
        document.getElementById('chart-rag-evolution').innerHTML = '<p style="color:var(--text-muted); text-align:center; padding-top:100px;">Nenhum dado encontrado. Execute o benchmark offline.</p>';
      }
    } catch(e) {
      console.error("Erro ao carregar auditoria RAG:", e);
    }
  },

  renderEvolucao(runs) {
    if (!runs || runs.length === 0) return;
    
    // Sort chronologically
    const sortedRuns = [...runs].sort((a,b) => new Date(a.run_date) - new Date(b.run_date));
    
    const x = sortedRuns.map(r => r.id);
    const hitRates = sortedRuns.map(r => (r.avg_retrieval_hit_rate || 0) * 100);
    const faithfulness = sortedRuns.map(r => (r.avg_generation_faithfulness || 0) * 100);

    const trace1 = {
      x: x, y: hitRates,
      type: 'scatter', mode: 'lines+markers',
      name: 'Hit Rate @ 5 (%)',
      line: {color: '#3498db'}
    };
    
    const trace2 = {
      x: x, y: faithfulness,
      type: 'scatter', mode: 'lines+markers',
      name: 'Faithfulness (%)',
      line: {color: '#2ecc71'}
    };

    const layout = {
      ...plotlyDarkLayout(''),
      margin: {t:40, r:20, l:40, b:40},
      yaxis: { range: [0, 105], gridcolor: '#334155' }
    };
    
    Plotly.newPlot('chart-rag-evolution', [trace1, trace2], layout);
  },

  renderMetricsTable(metrics, runId) {
    const tbody = document.querySelector('#table-rag-metrics tbody');
    if (!tbody) return;
    
    if (!metrics || metrics.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">Sem métricas detalhadas para o último run.</td></tr>';
      return;
    }
    
    tbody.innerHTML = metrics.map(m => {
      // Determine emergence layer badge color
      let emLayerStr = '-';
      if (m.emergence_layer !== null && m.emergence_layer !== undefined) {
        const layer = m.emergence_layer;
        // Layers: 0-10 (green), 11-20 (yellow), >20 (red) for 32-layer Llama-3.2
        let color = layer <= 10 ? '#2ecc71' : (layer <= 20 ? '#f1c40f' : '#e74c3c');
        emLayerStr = `<span class="badge" style="background-color: transparent; border: 1px solid ${color}; color: ${color};">Camada ${layer}</span>`;
      }
      
      return `
        <tr>
          <td>${runId || '-'}</td>
          <td style="font-size: 0.85rem; max-width: 250px; overflow: hidden; text-overflow: ellipsis;" title="${(m.question||'').replace(/"/g, '&quot;')}">${m.question}</td>
          <td style="font-size: 0.85rem; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${(m.expected_answer||'').replace(/"/g, '&quot;')}">${m.expected_answer || '-'}</td>
          <td style="font-size: 0.85rem; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${(m.actual_answer||'').replace(/"/g, '&quot;')}">${m.actual_answer || '-'}</td>
          <td>${emLayerStr}</td>
        </tr>
      `;
    }).join('');
  },

  renderLogitLens(metrics) {
    const container = document.getElementById('chart-logit-lens');
    if (!container) return;
    
    const validMetrics = metrics.filter(m => m.emergence_layer !== null && m.emergence_layer !== undefined);
    
    if (validMetrics.length === 0) {
      container.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding-top:100px;">Nenhum dado de Logit Lens (emergence layer) encontrado no último run.</p>';
      return;
    }
    
    const questions = validMetrics.map(m => 'Q: ' + m.question.substring(0, 40) + '...');
    const layers = validMetrics.map(m => m.emergence_layer);
    
    const MAX_LAYERS = 32;
    const colors = layers.map(l => {
        if (l <= 10) return '#2ecc71';
        if (l <= 20) return '#f1c40f';
        return '#e74c3c';
    });
    
    const trace = {
      y: questions.reverse(),
      x: layers.reverse(),
      type: 'bar',
      orientation: 'h',
      marker: {
        color: colors.reverse(),
        line: { width: 1, color: '#1e293b' }
      },
      text: layers.map(l => `Camada ${l}`),
      textposition: 'auto',
      hoverinfo: 'x+y'
    };
    
    const layout = {
      ...plotlyDarkLayout(''),
      margin: {t:20, r:20, l:350, b:40},
      xaxis: { 
          title: 'Emergence Layer', 
          range: [0, MAX_LAYERS], 
          gridcolor: '#334155' 
      },
      yaxis: { autorange: true }
    };
    
    Plotly.newPlot('chart-logit-lens', [trace], layout);
  }
};

/* Registro global para o loader do app.js */
window.TabsNovos = {
  Senadores: TabsSenadores,
  Governadores: TabsGovernadores,
  Financeiro: TabsFinanceiro,
  Fnde: TabsFnde,
  Municipio: TabsMunicipio,
  DeputadoExtra,
  RagEfficiency: TabsRagEfficiency,
};
