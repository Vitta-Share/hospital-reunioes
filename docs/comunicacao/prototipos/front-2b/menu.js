/* O menu lateral redesenhado dos modelos 2B, 2C e 2C escuro.
   As mesmas opções do menu de hoje, organizadas em seções curtas, com busca (Ctrl+K),
   contadores ao lado dos itens, "Notificar incidente" em destaque e a opção de recolher. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { I, est, itens, esc } = N;

  const ic = (d, w) => `<svg width="${w || 19}" height="${w || 19}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const ICONES = {
    inicio: ic('<path d="M4 11l8-7 8 7v9h-5v-6H9v6H4z"/>'),
    pendencias: ic('<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 13l2 2 4-4"/>'),
    rotinas: ic('<path d="M4 12a8 8 0 0 1 14-5l2 2M20 12a8 8 0 0 1-14 5l-2-2M20 4v5h-5M4 20v-5h5"/>'),
    calendario: ic('<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4"/>'),
    reunioes: ic('<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-5.6 6-5.6s6 2.3 6 5.6M16 4.5a3.2 3.2 0 0 1 0 6.3M18 14.5c2 .7 3 2.7 3 5.5"/>'),
    dashboard: ic('<path d="M5 20V11M10 20V5M15 20v-7M20 20V8"/>'),
    processos: ic('<path d="M8 3h9l3 3v15H8zM4 7v14h12M11 9h6M11 13h6"/>'),
    pops: ic('<path d="M12 6c-2-1.5-5-2-8-1.5v13c3-.5 6 0 8 1.5 2-1.5 5-2 8-1.5v-13C17 4 14 4.5 12 6zM12 6v13"/>'),
    ouvidoria: ic('<path d="M4 5h16v11H10l-5 4v-4H4z"/>'),
    nsp: ic('<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6zM9 12l2 2 4-4"/>'),
    notificar: ic('<path d="M12 4l9 16H3zM12 10v4M12 17v.5"/>'),
    manual: ic('<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17v.5"/>'),
    busca: ic('<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>', 17),
    recolher: ic('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 10l-2 2 2 2"/>', 18),
    abrir: ic('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M13 10l2 2-2 2"/>', 18),
    seta: ic('<path d="M9 6l6 6-6 6"/>', 14),
    capacitacao: ic('<path d="M2 9l10-5 10 5-10 5zM6 11v5c3 2 9 2 12 0v-5"/>'),
    agenda: ic('<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4M12 13v3l2 1"/>'),
    contas: ic('<rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M7 9v.5M17 14.5v.5"/>'),
    conduta: ic('<path d="M12 4v16M6 20h12M5 8h14M7 8l-3 7a3 3 0 0 0 6 0zM17 8l-3 7a3 3 0 0 0 6 0z"/>'),
    usuarios: ic('<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-5.6 6-5.6s6 2.3 6 5.6M16 4.5a3.2 3.2 0 0 1 0 6.3M18 14.5c2 .7 3 2.7 3 5.5"/>'),
    cadastros: ic('<path d="M4 21V5l8-3 8 3v16M9 21v-5h6v5M8 8h1M12 8h1M15 8h1M8 12h1M12 12h1M15 12h1"/>'),
    central: ic('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12l6-6"/>'),
    tecnologia: ic('<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>'),
    secretaria: ic('<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4M9 15h6M12 12v6"/>'),
    mapa: ic('<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14"/>'),
    atendimento: ic('<path d="M4 5h16v11H10l-5 4v-4H4z"/><path d="M8 9h8M8 12h5"/>')
  };

  // Contadores: o que espera a pessoa em cada área (vermelho quando há atraso).
  function contador(area) {
    const abertos = itens.filter((i) => !est.feitos[i.id] && i.off !== null && i.off <= 7 || (!est.feitos[i.id] && i.off === null));
    const da = (f) => abertos.filter(f);
    if (area === 'pendencias') { const v = da((i) => i.off !== null && i.off < 0).length; return v ? { n: v, verm: true, dica: `${v} atrasadas` } : null; }
    const mapa = { rotinas: 'Rotina', ouvidoria: 'Ouvidoria', pops: 'POP', nsp: 'NSP' };
    const n = da((i) => i.area === mapa[area]).length;
    return n ? { n, verm: false, dica: `${n} esperando você` } : null;
  }

  const SECOES_FACILITADORA = [
    { itens: [{ k: 'inicio', t: 'Início' }] },
    { k: 'trabalho', t: 'Meu trabalho', itens: [{ k: 'pendencias', t: 'Pendências', c: 'pendencias' }, { k: 'rotinas', t: 'Rotinas', c: 'rotinas' }, { k: 'calendario', t: 'Calendário' }] },
    { k: 'metas', t: 'Reuniões e metas', itens: [{ k: 'reunioes', t: 'Reuniões' }, { k: 'dashboard', t: 'Dashboard' }, { k: 'processos', t: 'Definições de processo', ic: 'processos' }] },
    { k: 'qualidade', t: 'Qualidade e segurança', itens: [
      { k: 'pops', t: 'POPs', c: 'pops' }, { k: 'ouvidoria', t: 'Ouvidoria', c: 'ouvidoria' },
      { g: 'nsp', t: 'NSP', nome: 'Núcleo de Segurança do Paciente', c: 'nsp', filhos: [
        { k: 'nsp', t: 'Visão geral', ic: 'inicio' }, { k: 'nspnotificacoes', t: 'Notificações', ic: 'notificar' },
        { k: 'nspreunioes', t: 'Reuniões do Núcleo', ic: 'calendario' }, { k: 'nspnucleo', t: 'Núcleo', ic: 'reunioes' },
        { k: 'nspconfig', t: 'Configuração', ic: 'manual' },
        { breve: 'Auditorias de adesão' }, { breve: 'Gestão de riscos' }, { breve: 'Comissões' }] }] }
  ];
  const NSP_GRUPO = SECOES_FACILITADORA[3].itens[2];
  const CONTAS = { g: 'contas', t: 'Contas médicas', nome: 'Contas médicas', ic: 'contas', filhos: [
    { k: 'contas', t: 'Painel', ic: 'inicio' }, { k: 'contasesteira', t: 'Esteira das contas', ic: 'pendencias' },
    { k: 'contascontratos', t: 'Contratos', ic: 'processos' }, { k: 'contasoperadoras', t: 'Operadoras', ic: 'cadastros' }, { k: 'contashabilitacao', t: 'Habilitação', ic: 'usuarios' }] };
  const CONDUTA = { g: 'conduta', t: 'Comitê de Conduta', nome: 'Comitê de Conduta', ic: 'conduta', filhos: [
    { k: 'comite', t: 'Minha vez', ic: 'inicio' }, { k: 'comitecasos', t: 'Casos', ic: 'pendencias' }, { k: 'comiterecomendacoes', t: 'Recomendações', ic: 'processos' },
    { k: 'comitemembros', t: 'Membros', ic: 'reunioes' }, { k: 'comiteguia', t: 'Guia do Comitê', ic: 'manual' }] };
  const SECOES_POR_PERFIL = {
    facilitadora: SECOES_FACILITADORA,
    colaborador: [
      { itens: [{ k: 'inicio', t: 'Início' }] },
      { k: 'trabalho', t: 'Meu trabalho', itens: [{ k: 'pendencias', t: 'Pendências', c: 'pendencias' }, { k: 'rotinas', t: 'Rotinas', c: 'rotinas' }, { k: 'calendario', t: 'Calendário' }] },
      { k: 'qualidade', t: 'Qualidade e segurança', itens: [{ k: 'pops', t: 'POPs' }] }],
    secretaria: [
      { itens: [{ k: 'secretaria', t: 'Agenda das Reuniões', ic: 'secretaria' }] },
      { k: 'agenda', t: 'Agenda', itens: [{ k: 'secretarianova', t: 'Nova Reunião', ic: 'agenda' }, { k: 'calendario', t: 'Calendário' }] },
      { k: 'qualidade', t: 'Qualidade e segurança', itens: [{ k: 'ouvidoria', t: 'Ouvidoria', c: 'ouvidoria' }] }],
    faturista: [
      { itens: [{ k: 'inicio', t: 'Início' }] },
      { k: 'gestao', t: 'Contas médicas', itens: CONTAS.filhos.map((f) => ({ ...f })) },
      { k: 'qualidade', t: 'Qualidade e segurança', itens: [{ k: 'pops', t: 'POPs' }] }],
    admin: [
      ...SECOES_FACILITADORA,
      { k: 'gestao', t: 'Gestão', itens: [CONTAS, CONDUTA] },
      { k: 'administracao', t: 'Administração', itens: [
        { k: 'adminusuarios', t: 'Usuários e acessos', ic: 'usuarios' }, { k: 'admincadastros', t: 'Cadastros', ic: 'cadastros' },
        { k: 'atendimento', t: 'Dados do atendimento', ic: 'atendimento' },
        { k: 'central', t: 'Central de Comando', ic: 'central' }, { k: 'tecnologia', t: 'Tecnologia', ic: 'tecnologia' }] }]
  };
  void NSP_GRUPO;

  function item(it, ativo) {
    const on = it.k === ativo;
    const c = it.c ? contador(it.c) : null;
    const icone = ICONES[it.ic || it.k] || '';
    return `<li><a href="#${it.k}" class="nv-item${on ? ' on' : ''}"${on ? ' aria-current="page"' : ''} title="${it.t}">${icone}<span class="nv-txt">${it.t}</span>${c ? `<span class="nv-cont${c.verm ? ' verm' : ''}" aria-label="${c.dica}">${c.n}</span>` : ''}</a></li>`;
  }

  N.menuNovo = function (ativo) {
    const pequeno = (svg) => svg.replace(/width="19" height="19"/, 'width="16" height="16"');
    const SECOES = SECOES_POR_PERFIL[est.perfil] || SECOES_FACILITADORA;
    const secoes = SECOES.map((s) => {
      // A seção encolhe pelo título; com o menu recolhido os ícones aparecem sempre.
      const fechada = s.k && est.secoes[s.k] === false && !est.recolhido;
      const titulo = s.t ? `<button type="button" class="nv-titulo" data-secao="${s.k}" aria-expanded="${!fechada}"><span>${s.t}</span>${ICONES.seta}</button>` : '';
      const lista = s.itens.map((it) => {
        if (!it.g) return item(it, ativo);
        const c = it.c ? contador(it.c) : null;
        const gAtivo = it.filhos.some((f) => f.k === ativo);
        const gAberto = est.grupos['m-' + it.g] !== undefined ? est.grupos['m-' + it.g] : gAtivo;
        return `<li><button type="button" class="nv-item nv-grupo${gAtivo ? ' com-ativo' : ''}" data-grupo="m-${it.g}" aria-expanded="${gAberto}" title="${it.nome}">${ICONES[it.ic || it.g] || ICONES.nsp}<span class="nv-txt">${it.t}<span class="nv-chev">${ICONES.seta}</span></span>${c ? `<span class="nv-cont" aria-label="${c.dica}">${c.n}</span>` : ''}</button>
          ${gAberto ? `<ul class="nv-sub">${it.filhos.map((f) => f.breve
            ? `<li><span class="nv-breve"><span class="nv-txt">${f.breve}</span><span class="nv-selo">Em breve</span></span></li>`
            : `<li><a href="#${f.k}" class="${f.k === ativo ? 'on' : ''}"${f.k === ativo ? ' aria-current="page"' : ''}>${pequeno(ICONES[f.ic] || '')}<span class="nv-txt">${f.t}</span></a></li>`).join('')}</ul>` : ''}</li>`;
      }).join('');
      return `<div class="nv-secao">${titulo}<ul${fechada ? ' hidden' : ''}>${lista}</ul></div>`;
    }).join('');
    if (typeof est.busca === 'string') return N.buscaNoMenu();
    return `<button type="button" class="nv-busca" data-acao="paleta" title="Buscar (Ctrl+K)">${ICONES.busca}<span class="nv-txt">Buscar</span><kbd>Ctrl K</kbd></button>${secoes}`;
  };

  N.rodapeNovo = function (ativo) {
    return `<a href="#notificar" class="nv-notificar${ativo === 'notificar' ? ' on' : ''}" title="Notificar incidente"><span class="nv-alerta">${ICONES.notificar}</span><span class="nv-txt">Notificar incidente</span></a>
      <div class="nv-linha-baixo">
        <a href="#manual" class="nv-mini" title="Manual">${ICONES.manual}<span class="nv-txt">Manual</span></a>
        <button type="button" class="nv-mini nv-recolher" data-acao="recolher" aria-pressed="${!!est.recolhido}" title="${est.recolhido ? 'Abrir o menu' : 'Recolher o menu'}">${est.recolhido ? ICONES.abrir : ICONES.recolher}<span class="sr">${est.recolhido ? 'Abrir o menu' : 'Recolher o menu'}</span></button>
      </div>`;
  };

  // ---------- busca no próprio menu (Ctrl+K): telas e itens da fila ----------
  const TELAS = [['inicio', 'Início'], ['pendencias', 'Pendências'], ['rotinas', 'Rotinas'], ['calendario', 'Calendário'], ['reunioes', 'Reuniões'], ['dashboard', 'Dashboard'],
    ['pops', 'POPs'], ['ouvidoria', 'Ouvidoria'], ['nsp', 'NSP'], ['notificar', 'Notificar incidente'], ['pessoas', 'Quem responde a você']];
  const norm = (s) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  N.resultadosBusca = function (txt) {
    const t = norm(txt.trim());
    const telas = TELAS.filter(([, n]) => !t || norm(n).includes(t)).map(([k, n]) => ({ href: '#' + k, t: n, ic: ICONES[k] || ICONES.inicio }));
    const fila = t ? itens.filter((i) => !est.feitos[i.id] && norm(i.titulo + ' ' + i.origem).includes(t)).slice(0, 6).map((i) => ({ href: '#item-' + i.id, t: i.titulo, s: i.origem })) : [];
    return { telas, fila };
  };
  N.buscaNoMenu = function () {
    const r = N.resultadosBusca(est.busca);
    const link = (x, n) => `<li><a href="${x.href}" class="nv-item nv-res${n === 0 ? ' primeiro' : ''}" data-fecha-busca="1">${x.ic || ''}<span class="nv-txt">${esc(x.t)}${x.s ? `<small>${esc(x.s)}</small>` : ''}</span></a></li>`;
    let n = 0;
    const telas = r.telas.length ? `<p class="nv-res-tit">Telas</p><ul>${r.telas.map((x) => link(x, n++)).join('')}</ul>` : '';
    const fila = r.fila.length ? `<p class="nv-res-tit">Na sua fila</p><ul>${r.fila.map((x) => link(x, n++)).join('')}</ul>` : '';
    return `<div class="nv-busca-campo">${ICONES.busca}<label for="nv-busca-input" class="sr">Buscar telas e pendências</label><input id="nv-busca-input" type="search" autocomplete="off" placeholder="Buscar" value="${esc(est.busca)}"><button type="button" class="nv-busca-fechar" data-acao="fechar-busca" aria-label="Fechar a busca"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
      <div class="nv-resultados" aria-live="polite">${telas}${fila}${n ? '' : '<p class="nv-res-nada">Nada encontrado com esse texto.</p>'}</div>
      <p class="nv-busca-dica">Enter abre o primeiro · Esc volta ao menu</p>`;
  };
})();
