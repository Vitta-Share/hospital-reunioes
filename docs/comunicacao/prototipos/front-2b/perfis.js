/* Perfis do protótipo ("Ver como") e as peças que toda tela nova usa.
   O menu de cada perfil segue o que o app mostra hoje para aquele papel. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I } = N;

  // ------------------------------------------------------------------ perfis
  N.PERFIS = {
    facilitadora: { rot: 'Facilitadora', nome: 'Renata Alves', ini: 'RA', cargo: 'Diretoria Assistencial' },
    colaborador: { rot: 'Colaborador', nome: 'Carla Nogueira', ini: 'CN', cargo: 'Coordenadora de Enfermagem' },
    secretaria: { rot: 'Secretária', nome: 'Luana Freitas', ini: 'LF', cargo: 'Secretaria da Diretoria' },
    faturista: { rot: 'Faturista', nome: 'Bruno Araújo', ini: 'BA', cargo: 'Faturamento' },
    admin: { rot: 'Super admin', nome: 'Marcos Teixeira', ini: 'MT', cargo: 'Tecnologia' }
  };
  try { N.est.perfil = localStorage.getItem('prototipo-perfil') || 'facilitadora'; } catch (e) { N.est.perfil = 'facilitadora'; }
  if (!N.PERFIS[N.est.perfil]) N.est.perfil = 'facilitadora';
  N.perfil = () => N.est.perfil;
  N.eh = (...ps) => ps.includes(N.est.perfil);

  function desenharVerComo() {
    const el = document.getElementById('ver-como');
    if (!el) return;
    el.innerHTML = `<span class="rot">Ver como</span>${Object.entries(N.PERFIS).map(([k, p]) => `<button type="button" data-acao="ver-como" data-perfil="${k}" aria-pressed="${k === N.est.perfil}" title="${p.nome}, ${p.cargo}">${p.rot}</button>`).join('')}<a class="mapa-link" href="#mapa" title="Todas as telas do protótipo">Todas as telas</a>`;
    const p = N.PERFIS[N.est.perfil];
    const q = document.querySelector('.quem');
    if (q) q.innerHTML = `<span class="avatar" aria-hidden="true">${p.ini}</span><div><b>${p.nome}</b><span>${p.cargo}</span></div>`;
  }
  N.acoes['ver-como'] = (alvo) => {
    N.est.perfil = alvo.dataset.perfil;
    try { localStorage.setItem('prototipo-perfil', N.est.perfil); } catch (e) { /* sem armazenamento */ }
    const destino = { secretaria: '#secretaria', faturista: '#contas' }[N.est.perfil];
    if (destino && location.hash !== destino) location.hash = destino; else N.desenhar(true);
    N.aviso(`Agora você vê o app como ${N.PERFIS[N.est.perfil].nome} (${N.PERFIS[N.est.perfil].rot}).`);
  };
  const desenharOriginal = N.desenhar;
  N.desenhar = (f) => { desenharOriginal(f); desenharVerComo(); };
  // Tela pública (sem login): some o menu e o topo. A tela registra { publica: true }.
  function modoPublico() {
    const pag = (location.hash || '#inicio').slice(1).split('-')[0];
    const tl = N.telas[pag];
    document.body.classList.toggle('modo-publico', !!(tl && tl.publica));
  }
  window.addEventListener('hashchange', modoPublico);
  // Trocar de tela fecha a gaveta ou o modal que estava aberto.
  window.addEventListener('hashchange', () => { const m = document.getElementById('modal'); if (!m.hidden) { m.className = 'modal-fundo'; m.hidden = true; m.innerHTML = ''; } });
  document.addEventListener('DOMContentLoaded', modoPublico);
  // CSS próprio de um módulo, sem mexer nas folhas comuns.
  N.css = function (texto) { const s = document.createElement('style'); s.textContent = texto; document.head.appendChild(s); };
  N.css('.modo-publico .menu,.modo-publico .topo,.modo-publico .veu{display:none !important}.modo-publico .lado-direito{width:100%}');
  window.addEventListener('hashchange', () => setTimeout(desenharVerComo, 0));
  document.addEventListener('DOMContentLoaded', () => setTimeout(desenharVerComo, 0));
  document.addEventListener('click', () => setTimeout(desenharVerComo, 0));

  // ------------------------------------------------------------------ ícones extras (traço 1.8, como os do designer)
  const ic = (d, w) => `<svg width="${w || 18}" height="${w || 18}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  N.ic = ic;
  N.IC = {
    fechar: ic('<path d="M6 6l12 12M18 6L6 18"/>', 18),
    busca: ic('<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>', 16),
    mais: ic('<path d="M12 5v14M5 12h14"/>', 16),
    seta: ic('<path d="M5 12h14M13 6l6 6-6 6"/>', 14),
    voltar: ic('<path d="M19 12H5M11 6l-6 6 6 6"/>', 16),
    baixar: ic('<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>', 16),
    enviar: ic('<path d="M4 12l16-8-6 16-3-7z"/>', 16),
    lapis: ic('<path d="M4 20h4L19 9l-4-4L4 16zM14 6l4 4"/>', 16),
    olho: ic('<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>', 16),
    copiar: ic('<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V4H4v12h4"/>', 16),
    microfone: ic('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>', 18),
    anexo: ic('<path d="M20 12l-8 8a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8"/>', 16),
    filtro: ic('<path d="M4 5h16l-6 8v6l-4-2v-4z"/>', 16),
    escudo: ic('<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/>', 18),
    dinheiro: ic('<rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M7 9v.5M17 14.5v.5"/>', 19),
    balanca: ic('<path d="M12 4v16M6 20h12M5 8h14M7 8l-3 7a3 3 0 0 0 6 0zM17 8l-3 7a3 3 0 0 0 6 0z"/>', 19),
    engrenagem: ic('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>', 19),
    usuarios: ic('<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-5.6 6-5.6s6 2.3 6 5.6M16 4.5a3.2 3.2 0 0 1 0 6.3M18 14.5c2 .7 3 2.7 3 5.5"/>', 19),
    radar: ic('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12l6-6"/>', 19),
    codigo: ic('<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>', 19),
    secretaria: ic('<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4M9 15h6M12 12v6"/>', 19),
    predio: ic('<path d="M4 21V5l8-3 8 3v16M9 21v-5h6v5M8 8h1M12 8h1M16 8h0M8 12h1M12 12h1M16 12h0"/>', 19),
    estrela: ic('<path d="M12 3l2.8 5.8 6.2.9-4.5 4.4 1 6.2L12 17.4 6.5 20.3l1-6.2L3 9.7l6.2-.9z"/>', 16),
    qr: ic('<rect x="4" y="4" width="6" height="6"/><rect x="14" y="4" width="6" height="6"/><rect x="4" y="14" width="6" height="6"/><path d="M14 14h2v2h-2zM18 18h2v2h-2zM14 18h2M18 14h2"/>', 18),
    relogio: ic('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', 16),
    tres: I.tres
  };

  // ------------------------------------------------------------------ peças comuns
  // Cabeçalho de módulo: o herói do Início, mais baixo. "resumo" são os cartões que sobem sobre ele.
  N.cabModulo = function ({ sobre, titulo, frase, acoes, resumo }) {
    return `<section class="cab-modulo${resumo ? '' : ' sem-resumo'}" aria-label="${esc(titulo)}">
      <img src="assets/quarto-hsm.jpg" alt=""><div class="veu-foto" aria-hidden="true"></div>
      <div class="dentro">
        <div style="flex:1 1 380px;min-width:0">${sobre ? `<p class="sobre">${sobre}</p>` : ''}<h1>${titulo}</h1>${frase ? `<p class="frase">${frase}</p>` : ''}<div class="risco" aria-hidden="true"></div></div>
        ${acoes ? `<div class="acoes-cab">${acoes}</div>` : ''}
      </div>
    </section>`;
  };
  // Cartões de número, iguais aos do Início. [rótulo, valor, ícone, href, vermelho?]
  N.resumo = function (cartoes) {
    return `<section class="resumo" aria-label="Resumo">${cartoes.map(([rot, valor, icone, href, verm]) => `<a href="${href || '#'}" class="cartao stat"><span><span class="rot">${rot}</span><span class="valor num ${verm ? 'verm' : ''}">${valor}</span></span><span class="ic ${verm ? 'verm' : ''}">${icone || I.certo}</span></a>`).join('')}</section>`;
  };
  // Abas do módulo: [href, texto, número, vermelho?]
  N.abasModulo = function (abas, atual) {
    return `<nav class="abas-modulo" aria-label="Telas do módulo">${abas.map(([href, t, n, verm]) => `<a href="${href}"${href === atual ? ' aria-current="page"' : ''}>${t}${n !== undefined && n !== null ? `<span class="n${verm ? ' verm' : ''}">${n}</span>` : ''}</a>`).join('')}</nav>`;
  };
  N.modulo = function (cab, resumo, abas, corpo) {
    return `${N.cabModulo({ ...cab, resumo: !!resumo })}<div class="corpo-modulo">${resumo ? N.resumo(resumo) : ''}${abas || ''}${corpo}<p class="demo">Dados de demonstração.</p></div>`;
  };
  N.estado = (cls, txt) => `<span class="estado ${cls}"><i aria-hidden="true"></i>${txt}</span>`;
  N.ini = (nome) => nome.split(' ').filter(Boolean).slice(0, 2).map((x) => x[0]).join('');

  // Gaveta: o detalhe abre ao lado da lista.
  N.abrirGaveta = function ({ sobre, titulo, corpo, pe }) {
    const m = document.getElementById('modal');
    m.hidden = false;
    m.className = 'gaveta-fundo';
    m.innerHTML = `<aside class="gaveta" role="dialog" aria-modal="true" aria-labelledby="gv-tit">
      <div class="gaveta-topo"><div>${sobre || ''}<h2 id="gv-tit">${titulo}</h2></div><button type="button" class="fechar" data-acao="fechar-gaveta" aria-label="Fechar">${N.IC.fechar}</button></div>
      <div class="gaveta-corpo">${corpo}</div>
      ${pe ? `<div class="gaveta-pe">${pe}</div>` : ''}
    </aside>`;
    setTimeout(() => { const b = m.querySelector('.fechar'); if (b) b.focus(); }, 30);
  };
  N.acoes['fechar-gaveta'] = () => { const m = document.getElementById('modal'); m.className = 'modal-fundo'; N.fecharModal(); };
  const fecharOriginal = N.fecharModal;
  N.fecharModal = () => { document.getElementById('modal').className = 'modal-fundo'; fecharOriginal(); };
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') document.getElementById('modal').className = 'modal-fundo'; });
  document.getElementById('modal').addEventListener('click', (ev) => { if (ev.target.id === 'modal') ev.target.className = 'modal-fundo'; });

  // Modal simples no padrão do designer.
  N.modal = function (titulo, corpo, acoes, idForm) {
    N.abrirModal(`<form class="modal entra" ${idForm ? `id="${idForm}"` : ''} role="dialog" aria-modal="true" aria-labelledby="md-tit">
      <h2 id="md-tit">${titulo}</h2>${corpo}
      <div class="acoes"><button type="button" class="btn contorno" data-acao="fechar-modal">Cancelar</button>${acoes}</div></form>`);
  };
  N.acoes['fechar-modal'] = () => N.fecharModal();
  N.acoes['toast'] = (alvo) => { N.fecharModal(); N.aviso(alvo.dataset.msg); };
})();
