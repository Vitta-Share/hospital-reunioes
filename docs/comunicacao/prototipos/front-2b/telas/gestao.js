/* Comitê de Conduta (lado logado): Minha vez, Casos, o caso em página própria, Recomendações,
   Membros, Guia dos ritos e Configurações. O sigilo manda: a lista mostra só metadados
   (protocolo, rito, etapa, prazo, categoria) e o relato só aparece dentro do caso, numa aba própria. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I, IC, dia, fmt, curto, est } = N;
  const T = N.telas;
  let introVisto = false;
  try { introVisto = localStorage.getItem('prototipo-comite-intro') === '1'; } catch (e) { /* sem armazenamento */ }
  est.cd = { aba: 'triagem', casosFiltro: 'abertos', rito: 'todos', termo: true, intro: 0, introVisto, data: 'hoje', triagem: {}, medida: null, decisao: {} };

  N.css(`
    .cd-aviso-sigilo{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;border-radius:8px;background:var(--suave);border:1px solid var(--borda);font-size:13.5px;color:var(--texto2)}
    .cd-aviso-sigilo svg{flex:none;color:var(--acento);margin-top:1px}
    .cd-agora{border:1px solid var(--titulo);box-shadow:var(--sombra-alta)}
    .cd-agora .prazo{font-size:26px;font-weight:700;color:var(--titulo);line-height:1.1;font-variant-numeric:tabular-nums}
    .cd-agora .prazo.verm{color:var(--verm)}
    .cd-acoes-sec{display:flex;flex-direction:column;gap:8px}
    .cd-acoes-sec .btn{justify-content:flex-start;width:100%}
    .cd-especial{display:flex;gap:12px;align-items:center;padding:12px 16px;border-radius:10px;background:var(--titulo);color:#fff;margin-top:14px;font-size:14px}
    .cd-especial b{display:block;font-size:15px}
    .cd-voto{display:flex;align-items:center;gap:12px;padding:12px 0;border-top:1px solid var(--linha)}
    .cd-voto:first-child{border-top:0}
    .cd-check{display:flex;align-items:center;gap:10px;padding:8px 0;font-size:14.5px}
    .cd-check input{width:18px;height:18px}
    .cd-intro{display:flex;flex-direction:column;gap:10px;min-height:180px}
    .cd-intro .num-intro{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--texto2);font-weight:700}
    .cd-intro p{margin:0;font-size:15.5px;line-height:1.5}
    .cd-rito{display:flex;flex-direction:column;gap:10px}
    .cd-rito ol{margin:0;padding-left:20px;display:flex;flex-direction:column;gap:4px;font-size:14.5px}
    .btn[disabled]{opacity:.45;cursor:not-allowed}
    table.tab a.btn{color:var(--btn-texto);font-weight:700}table.tab a.btn:hover{color:var(--btn-texto)}table.tab a.btn.contorno{color:var(--titulo)}
    table.tab a.num{white-space:nowrap}
    .cd-tiles{grid-template-columns:1fr}.cd-guia{grid-template-columns:repeat(auto-fit,minmax(420px,1fr))}
    .cd-texto-v{white-space:pre-wrap;font-size:14.5px;line-height:1.5;padding:12px 14px;border-radius:8px;background:var(--suave);margin:10px 0 0}
  `);

  // ------------------------------------------------------------------ dados de demonstração (metadados em claro, conteúdo só no caso)
  const RITOS = {
    Encaminhamento: { prazo: 10, etapas: ['Triagem', 'Encaminhamento', 'Retorno a quem relatou', 'Arquivado'] },
    Rápido: { prazo: 30, etapas: ['Triagem', 'Orientação', 'Retorno a quem relatou', 'Arquivado'] },
    Completo: { prazo: 60, etapas: ['Triagem', 'Depoimentos', 'Relatório', 'Voto e ata', 'Medida', 'Retorno e verificação'] },
    Especial: { prazo: 60, etapas: ['Triagem', 'Grupo Especial', 'Depoimentos', 'Relatório', 'Voto e ata', 'Recomendação à Direção'] }
  };
  const CASOS = [
    { id: 'c12', prot: 'CND-2026-0412', rito: 'Completo', etapa: 3, cat: 'Assédio moral', envio: -41, acao: 'Votar', anonimo: false },
    { id: 'c07', prot: 'CND-2026-7731', rito: 'Rápido', etapa: 0, cat: 'Conduta inadequada', envio: -3, acao: 'Confirmar a triagem', anonimo: true },
    { id: 'c19', prot: 'CND-2026-0958', rito: 'Completo', etapa: 1, cat: 'Discriminação', envio: -22, acao: 'Assinar o Termo de declaração', anonimo: false },
    { id: 'c21', prot: 'CND-2026-5203', rito: 'Especial', etapa: 2, cat: 'Assédio moral', envio: -18, acao: null, anonimo: false, especial: true },
    { id: 'c03', prot: 'CND-2026-3307', rito: 'Encaminhamento', etapa: 2, cat: 'Fora do canal: escala', envio: -8, acao: 'Responder a quem relatou', anonimo: true },
    { id: 'c15', prot: 'CND-2026-6620', rito: 'Completo', etapa: 5, cat: 'Fraude', envio: -95, acao: 'Verificar retaliação (60 dias)', anonimo: false, recomendacao: 'r1' },
    { id: 'c02', prot: 'CND-2026-1184', rito: 'Rápido', etapa: 3, cat: 'Conduta inadequada', envio: -70, acao: null, anonimo: true, arquivado: true }
  ];
  const prazoDe = (c) => c.envio + RITOS[c.rito].prazo; // dias a partir de hoje
  const abertos = () => CASOS.filter((c) => !c.arquivado);
  const minhaVez = () => abertos().filter((c) => c.acao).sort((a, b) => prazoDe(a) - prazoDe(b));
  const caso = (id) => CASOS.find((c) => c.id === id);
  const etapaNome = (c) => RITOS[c.rito].etapas[c.etapa];
  const prazoTxt = (c) => { const p = prazoDe(c); return p < 0 ? `venceu há ${-p} ${p === -1 ? 'dia' : 'dias'}` : p === 0 ? 'vence hoje' : `${p} ${p === 1 ? 'dia' : 'dias'}`; };
  const prazoEstado = (c) => { const p = prazoDe(c); return c.arquivado ? ['e-ok', 'Arquivado'] : p < 0 ? ['e-venc', 'Prazo vencido'] : p <= 7 ? ['e-hoje', 'Vence em ' + p + ' dias'] : ['e-prox', 'No prazo']; };

  const MEMBROS = [
    { id: 'm1', nome: 'Helena Duarte', cadeira: 'Coordenação', diretor: false, desde: -300, ate: 430, termo: 'Assinado' },
    { id: 'm2', nome: 'Sérgio Bastos', cadeira: 'Votante', diretor: true, desde: -300, ate: 430, termo: 'Assinado' },
    { id: 'm3', nome: 'Patrícia Moura', cadeira: 'Votante e Segundo leitor', diretor: false, desde: -300, ate: 430, termo: 'Assinado' },
    { id: 'm4', nome: 'Eduardo Lins', cadeira: 'Suplente', diretor: false, desde: -40, ate: 690, termo: 'Aguardando na ClickSign' },
    { id: 'm5', nome: 'Aline Rocha', cadeira: 'Suplente', diretor: true, desde: -300, ate: -12, termo: 'Assinado', encerrado: true }
  ];
  const REGISTRO = [['há 40 dias', 'Eduardo Lins incluído como Suplente. Termo enviado à ClickSign.'], ['há 12 dias', 'Participação de Aline Rocha encerrada (fim da vigência).'], ['há 300 dias', 'Composição inicial do Comitê registrada, com 5 membros.']];

  const RECOS = [
    { id: 'r1', caso: 'c15', medida: 'Advertência por escrito e treinamento obrigatório', enviada: -9, sit: 'Aguardando a decisão da Direção' },
    { id: 'r2', caso: null, prot: 'CND-2026-2049', cat: 'Assédio moral', medida: 'Suspensão de 3 dias', enviada: -48, sit: 'Decidida: medida acatada', comunicada: true },
    { id: 'r3', caso: null, prot: 'CND-2026-8815', cat: 'Conduta inadequada', medida: 'Orientação formal da liderança', enviada: -31, sit: 'Decidida: acatada com ajuste', comunicada: false }
  ];
  const recoProt = (r) => r.caso ? caso(r.caso).prot : r.prot;
  const recoCat = (r) => r.caso ? caso(r.caso).cat : r.cat;

  // ------------------------------------------------------------------ cabeçalho e abas comuns
  const CAB = { sobre: 'Comitê de Conduta' };
  function abas(atual) {
    return N.abasModulo([
      ['#comite', 'Minha vez', minhaVez().length, minhaVez().some((c) => prazoDe(c) < 0)],
      ['#comitecasos', 'Casos', abertos().length], ['#comiterecomendacoes', 'Recomendações', RECOS.filter((r) => !r.comunicada).length],
      ['#comitemembros', 'Membros', null], ['#comiteguia', 'Guia dos ritos', null], ['#comiteconfig', 'Configurações', null]], atual);
  }
  const avisoAdmin = () => N.eh('admin') ? `<p class="aviso" style="margin-top:14px">${I.info}Demonstração: o Super admin não abre casos do Comitê (ADR 0097). Esta tela mostra o que a Coordenação vê.</p>` : '';
  const sigilo = (txt) => `<div class="cd-aviso-sigilo">${IC.escudo}<span>${txt}</span></div>`;

  function linhaCaso(c, comAcao) {
    const [cls, txt] = prazoEstado(c);
    return `<tr>
      <td><a href="#comitecaso-${c.id}" class="num">${c.prot}</a>${c.especial ? '<div class="sub">Rota Especial</div>' : ''}</td>
      <td><span class="pill">${c.rito}</span></td>
      <td>${esc(etapaNome(c))}<div class="sub">${esc(c.cat)}</div></td>
      <td>${N.estado(cls, txt)}<div class="sub num">${c.arquivado ? '' : 'até ' + fmt(dia(prazoDe(c)))}</div></td>
      <td style="text-align:right">${comAcao && c.acao ? `<a class="btn" href="#comitecaso-${c.id}">${esc(c.acao)}</a>` : `<a class="btn contorno" href="#comitecaso-${c.id}">Abrir</a>`}</td></tr>`;
  }
  const tabelaCasos = (lista, comAcao) => `<div class="tabela-rola"><table class="tab"><thead><tr><th>Protocolo</th><th>Rito</th><th>Etapa e categoria</th><th>Prazo do rito</th><th></th></tr></thead><tbody>${lista.map((c) => linhaCaso(c, comAcao)).join('')}</tbody></table></div>`;

  // ------------------------------------------------------------------ Minha vez (a capa do módulo)
  T.comite = { trilha: 'Comitê de Conduta', menu: 'comite', mapa: ['Comitê de Conduta', 'Minha vez'], render() {
    if (!est.cd.termo) {
      const corpo = `<section class="cartao bloco" style="margin-top:14px;padding:24px;max-width:760px">
        ${N.estado('e-hoje', 'Termo pendente')}
        <h2 class="titulo-bloco" style="margin-top:10px;font-size:20px">Assine o Termo de sigilo para ver os casos</h2>
        <p class="pagina-sub">Você foi incluída no Comitê de Conduta. Os casos aparecem aqui depois que o Termo estiver assinado na ClickSign. Até lá, nenhum protocolo fica visível para você.</p>
        <div class="acoes-item" style="margin-top:16px"><button class="btn grande" data-acao="cd-termo-assinar">Assinar o Termo na ClickSign</button><a class="btn contorno grande" href="#comiteguia">Ler o Guia dos ritos</a></div>
      </section>`;
      return N.modulo({ ...CAB, titulo: 'Minha vez', frase: 'Falta o seu Termo de sigilo. Sem ele, o Comitê não mostra nenhum caso.' }, null, abas('#comite'), corpo);
    }
    const mv = minhaVez();
    const urg = mv[0];
    const vencidos = mv.filter((c) => prazoDe(c) < 0).length;
    const frase = mv.length ? `${mv.length === 1 ? 'Um caso espera' : mv.length + ' casos esperam'} uma ação sua.${vencidos ? ` ${vencidos === 1 ? 'Um passou' : vencidos + ' passaram'} do prazo do rito.` : ' Todos dentro do prazo do rito.'}` : 'Nenhum caso espera você agora.';
    const corpo = `
      ${avisoAdmin()}
      <div class="duas" style="margin-top:14px">
        <section class="cartao bloco larga">
          <div class="cab"><h2>${I.lista}Esperando você</h2><a class="link" href="#comitecasos">Ver todos os casos${I.seta}</a></div>
          ${mv.length ? tabelaCasos(mv, true) : '<p class="vazio">Nada espera você. Quando um caso chegar à sua etapa, ele aparece aqui com o prazo do rito.</p>'}
          ${sigilo('A lista mostra só o protocolo, o rito, a etapa e o prazo. O relato aparece dentro do caso, e cada leitura fica na Trilha do caso.')}
        </section>
        <aside class="estreita">
          ${urg ? `<section class="cartao bloco cd-agora">
            <span class="rot-mini">O que fazer agora</span>
            <p style="margin:8px 0 0;font-size:17px;font-weight:700;color:var(--titulo)">${esc(urg.acao)}</p>
            <p class="sub" style="margin:4px 0 0"><span class="num">${urg.prot}</span> · ${urg.rito} · ${esc(etapaNome(urg))}</p>
            <p class="prazo ${prazoDe(urg) < 0 ? 'verm' : ''}" style="margin:12px 0 0">${prazoTxt(urg)}</p>
            <p class="sub" style="margin:2px 0 0">${prazoDe(urg) < 0 ? 'o prazo do rito já passou' : 'até o fim do prazo do rito'}</p>
            <a class="btn grande" style="width:100%;margin-top:14px" href="#comitecaso-${urg.id}">Abrir o mais urgente</a>
          </section>` : ''}
          <section class="cartao bloco">
            <h2 class="titulo-bloco" style="font-size:16px;margin-bottom:10px">Atalhos</h2>
            <div class="tiles cd-tiles">
              <a class="tile" href="#comitecasos">${I.pendCheio}Casos</a>
              <a class="tile" href="#comiterecomendacoes">${I.lista}Recomendações</a>
              <a class="tile" href="#comitemembros">${N.IC.usuarios}Membros</a>
              <a class="tile" href="#comiteguia">${I.popCheio}Guia dos ritos</a>
            </div>
          </section>
          <p class="sub" style="margin:0"><a href="#" data-acao="cd-sem-termo">Demonstração: ver como membro que ainda não assinou o Termo</a></p>
        </aside>
      </div>`;
    return N.modulo({ ...CAB, titulo: 'Minha vez', frase, acoes: `<a class="btn claro grande" href="#comiteguia">Guia dos ritos</a>` },
      [['Esperando você', String(mv.length).padStart(2, '0'), I.alerta, '#comite', vencidos > 0], ['Casos abertos', String(abertos().length).padStart(2, '0'), I.agenda, '#comitecasos'],
        ['Na Rota Especial', String(abertos().filter((c) => c.especial).length).padStart(2, '0'), N.IC.escudo, '#comitecasos'], ['Recomendações sem decisão', String(RECOS.filter((r) => r.sit.startsWith('Aguardando')).length).padStart(2, '0'), I.relogio, '#comiterecomendacoes']],
      abas('#comite'), corpo);
  }, depois() { if (!est.cd.introVisto && est.cd.termo) abrirIntro(); } };

  N.acoes['cd-sem-termo'] = () => { est.cd.termo = false; N.desenhar(true); };
  N.acoes['cd-termo-assinar'] = () => { est.cd.termo = true; N.desenhar(true); N.aviso('Termo assinado na ClickSign. Os casos do Comitê já aparecem para você.'); };

  // ------------------------------------------------------------------ apresentação na primeira entrada (5 cartões)
  const INTRO = [
    ['O que é o Comitê', 'O Comitê de Conduta trata os relatos de conduta grave que chegam pelo Canal de Conduta: assédio, discriminação, violência, fraude e desvio. São três membros votantes e até dois suplentes.'],
    ['Sigilo', 'O conteúdo dos casos é cifrado. A lista mostra só protocolo, rito, etapa e prazo. Cada vez que alguém lê um caso, a leitura entra na Trilha do caso, que não se edita nem se apaga.'],
    ['Ritos e prazos', 'Cada caso segue um Rito: Encaminhamento, Rápido, Completo ou Especial. O prazo conta do envio do relato, não da triagem.'],
    ['O seu papel', 'A Coordenação confirma a triagem e conduz o rito rápido. O Segundo leitor vê a mesma fila e pode contestar a triagem. Os votantes votam e assinam a Ata de deliberação.'],
    ['Impedimento', 'Se você conhece as pessoas de um caso ou pode estar envolvida, declare impedimento dentro do caso. O Citado nunca vê o caso, em nenhum perfil.']
  ];
  function abrirIntro() {
    const i = est.cd.intro;
    N.abrirModal(`<div class="modal entra" role="dialog" aria-modal="true" aria-labelledby="cd-intro-tit">
      <div class="passos-pub" aria-hidden="true">${INTRO.map((_, k) => `<span class="${k <= i ? 'on' : ''}"></span>`).join('')}</div>
      <div class="cd-intro"><span class="num-intro">${i + 1} de ${INTRO.length}</span><h2 id="cd-intro-tit">${INTRO[i][0]}</h2><p>${INTRO[i][1]}</p></div>
      <div class="acoes" style="justify-content:space-between;align-items:center">
        <label class="cd-check" style="padding:0"><input type="checkbox" id="cd-intro-nao"> Não mostrar de novo</label>
        <div style="display:flex;gap:10px">${i > 0 ? '<button type="button" class="btn contorno" data-acao="cd-intro" data-v="-1">Voltar</button>' : '<button type="button" class="btn contorno" data-acao="cd-intro-fim">Pular</button>'}
        ${i < INTRO.length - 1 ? '<button type="button" class="btn" data-acao="cd-intro" data-v="1">Próximo</button>' : '<button type="button" class="btn" data-acao="cd-intro-fim">Começar</button>'}</div>
      </div></div>`);
  }
  N.acoes['cd-intro'] = (a) => { est.cd.intro += Number(a.dataset.v); abrirIntro(); };
  N.acoes['cd-intro-fim'] = () => {
    const nao = document.getElementById('cd-intro-nao');
    est.cd.introVisto = true; est.cd.intro = 0;
    if (nao && nao.checked) { try { localStorage.setItem('prototipo-comite-intro', '1'); } catch (e) { /* sem armazenamento */ } }
    N.fecharModal();
  };

  // ------------------------------------------------------------------ Casos
  T.comitecasos = { trilha: 'Comitê de Conduta', menu: 'comite', mapa: ['Comitê de Conduta', 'Casos'], render() {
    const F = [['abertos', 'Abertos'], ['vencidos', 'Prazo vencido'], ['especial', 'Rota Especial'], ['arquivados', 'Arquivados']];
    const R = ['todos', 'Encaminhamento', 'Rápido', 'Completo', 'Especial'];
    let lista = est.cd.casosFiltro === 'arquivados' ? CASOS.filter((c) => c.arquivado) : abertos();
    if (est.cd.casosFiltro === 'vencidos') lista = lista.filter((c) => prazoDe(c) < 0);
    if (est.cd.casosFiltro === 'especial') lista = lista.filter((c) => c.especial);
    if (est.cd.rito !== 'todos') lista = lista.filter((c) => c.rito === est.cd.rito);
    lista = [...lista].sort((a, b) => prazoDe(a) - prazoDe(b));
    const corpo = `${avisoAdmin()}<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas"><div class="chips" role="group" aria-label="Situação">${F.map(([k, t]) => `<button class="chip" data-acao="cd-filtro" data-v="${k}" aria-pressed="${est.cd.casosFiltro === k}">${t}</button>`).join('')}</div>
        <div class="chips" role="group" aria-label="Rito">${R.map((r) => `<button class="chip" data-acao="cd-rito" data-v="${r}" aria-pressed="${est.cd.rito === r}">${r === 'todos' ? 'Todos os ritos' : r}</button>`).join('')}</div></div>
      ${lista.length ? tabelaCasos(lista, false) : '<p class="vazio">Nenhum caso com esse filtro. Troque a situação ou o rito acima.</p>'}
      ${sigilo('Não há busca por texto do relato: o conteúdo é cifrado. Ache casos parecidos pelo rito, pela categoria e pelas datas.')}
    </section>
    <section class="cartao bloco" style="margin-top:14px">
      <div class="cab"><h2>Pedidos de afastamento cautelar</h2><span class="pill">1 aguardando o DP</span></div>
      <p class="sub" style="margin:6px 0 10px">O afastamento é remunerado, não é punição, e nunca recai sobre quem relatou.</p>
      <ul class="linhas"><li class="linha" style="grid-template-columns:150px minmax(0,1fr) 180px 120px"><span class="num">CND-2026-5203</span><span class="t">Rota Especial · pedido do Grupo Especial<small>Pedido ao DP e ao Jurídico: só quem afastar e o motivo</small></span>${N.estado('e-hoje', 'Aguardando o DP')}<a class="btn contorno" href="#comitecaso-c21">Abrir o caso</a></li></ul>
    </section>`;
    return N.modulo({ ...CAB, titulo: 'Casos', frase: `${abertos().length} casos abertos, ${abertos().filter((c) => prazoDe(c) < 0).length} com o prazo do rito vencido. ${CASOS.filter((c) => c.arquivado).length} arquivado neste ano.` }, null, abas('#comitecasos'), corpo);
  } };
  N.acoes['cd-filtro'] = (a) => { est.cd.casosFiltro = a.dataset.v; N.desenhar(); };
  N.acoes['cd-rito'] = (a) => { est.cd.rito = a.dataset.v; N.desenhar(); };

  // ------------------------------------------------------------------ o caso: etapas no topo, "O que fazer agora" ao lado, o resto em abas
  const ABAS_CASO = [['triagem', 'Triagem'], ['depoimentos', 'Depoimentos e relatório'], ['voto', 'Voto e ata'], ['medida', 'Medida e retorno'], ['relato', 'Relato original e anexos'], ['trilha', 'Mensagens e trilha']];
  const ABA_DA_ETAPA = { Triagem: 'triagem', Depoimentos: 'depoimentos', Relatório: 'depoimentos', 'Voto e ata': 'voto', Medida: 'medida', 'Retorno e verificação': 'medida', 'Grupo Especial': 'triagem', 'Recomendação à Direção': 'medida', Orientação: 'trilha', Encaminhamento: 'trilha', 'Retorno a quem relatou': 'trilha', Arquivado: 'trilha' };

  T.comitecaso = { trilha: (id) => (caso(id) ? caso(id).prot : 'Caso'), menu: 'comite', mapa: ['Comitê de Conduta', 'Caso (página própria)'], render(id) {
    const c = caso(id) || CASOS[0];
    if (est.cd.casoAtual !== c.id) { est.cd.casoAtual = c.id; est.cd.aba = ABA_DA_ETAPA[etapaNome(c)] || 'triagem'; }
    const [cls, txt] = prazoEstado(c);
    const etapas = RITOS[c.rito].etapas;
    const p = prazoDe(c);
    return `<div class="pagina">
      <a class="voltar" href="#comitecasos">${I.voltar}Voltar aos casos</a>
      <section class="cartao bloco" style="padding:22px 24px">
        <div class="cab"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><span class="pill escuro">Rito ${c.rito}</span><span class="pill">${esc(c.cat)}</span>${N.estado(cls, txt)}${c.anonimo ? '<span class="pill cinza">Relato anônimo</span>' : ''}</div>
          <a class="link" href="#comiteguia">Como funciona o rito ${c.rito}${I.seta}</a></div>
        <h1 class="pagina-titulo num" style="margin-top:12px">${c.prot}</h1>
        <p class="pagina-sub">Relato enviado em ${fmt(dia(c.envio))} · prazo do rito até ${fmt(dia(p))}</p>
        <ol class="etapas" aria-label="Etapas do rito">${etapas.map((e, k) => `<li class="${k < c.etapa ? 'feito' : k === c.etapa ? 'agora' : ''}">${esc(e)}</li>`).join('')}</ol>
      </section>
      ${c.especial ? `<div class="cd-especial">${IC.escudo}<span><b>Rota Especial</b>O relato envolve a Direção. Quem apura é o Grupo Especial, sem nenhum diretor. O caso fica invisível para quem ele pode envolver.</span></div>` : ''}
      <div class="duas" style="margin-top:14px">
        <div class="larga">
          <nav class="abas-modulo" aria-label="Partes do caso" style="margin-top:0">${ABAS_CASO.map(([k, t]) => `<a href="#" data-acao="cd-aba" data-v="${k}"${est.cd.aba === k ? ' aria-current="page"' : ''}>${t}</a>`).join('')}</nav>
          <section class="cartao bloco" style="margin-top:14px">${abaCaso(c)}</section>
        </div>
        <aside class="estreita">
          <section class="cartao bloco cd-agora">
            <span class="rot-mini">O que fazer agora</span>
            ${c.acao ? `<p style="margin:8px 0 0;font-size:17px;font-weight:700;color:var(--titulo)">${esc(c.acao)}</p>
              <p class="sub" style="margin:4px 0 0">Etapa: ${esc(etapaNome(c))}</p>
              <p class="prazo ${p < 0 ? 'verm' : ''}" style="margin:12px 0 0">${prazoTxt(c)}</p><p class="sub" style="margin:2px 0 0">prazo do rito, contado do envio</p>
              <button class="btn grande" style="width:100%;margin-top:14px" data-acao="cd-acao-etapa" data-id="${c.id}">${esc(c.acao)}</button>`
              : `<p style="margin:8px 0 0;font-size:16px;color:var(--titulo)">Nada depende de você nesta etapa.</p><p class="sub" style="margin:4px 0 0">${c.especial ? 'O Grupo Especial conduz os depoimentos.' : 'O caso segue com outro membro.'}</p>`}
          </section>
          <section class="cartao bloco">
            <h2 class="titulo-bloco" style="font-size:15px;margin-bottom:10px">Outras ações do caso</h2>
            <div class="cd-acoes-sec">
              <button class="btn contorno" data-acao="cd-prorrogar">${IC.relogio}Prorrogar o prazo</button>
              <button class="btn contorno" data-acao="cd-convidar">${N.IC.usuarios}Convidar ao caso</button>
              <button class="btn contorno" data-acao="cd-nsp">${I.notifCheio.replace('width="22" height="22"', 'width="16" height="16"')}Sinalizar ao NSP</button>
              <button class="btn contorno" data-acao="cd-afastar">${IC.escudo}Pedir afastamento cautelar</button>
              <button class="btn contorno" data-acao="toast" data-msg="Dossiê do caso gerado. O download passa pelo app e fica na Trilha do caso.">${IC.baixar}Baixar o Dossiê do caso</button>
            </div>
            <hr style="border:0;border-top:1px solid var(--linha);margin:14px 0">
            <button class="btn contorno" style="width:100%;color:var(--verm)" data-acao="cd-impedimento">Declarar impedimento</button>
          </section>
        </aside>
      </div>
      <p class="demo">Dados de demonstração. Protocolos e pessoas são fictícios.</p>
    </div>`;
  } };
  N.acoes['cd-aba'] = (a) => { est.cd.aba = a.dataset.v; N.desenhar(); };

  function abaCaso(c) {
    const a = est.cd.aba;
    if (a === 'triagem') {
      const itens = [['Do canal?', 'Sim, é conduta grave'], ['Categoria', c.cat], ['Rito', c.rito], ['Envolve a Direção?', c.especial ? 'Sim, vai para a Rota Especial' : 'Não']];
      const conf = est.cd.triagem[c.id] || {};
      const fechada = c.etapa > 0;
      return `<div class="cab"><h2>Triagem</h2>${fechada ? N.estado('e-ok', 'Confirmada pela Coordenação') : N.estado('e-hoje', 'Aguardando a Coordenação')}</div>
        <p class="sub" style="margin:6px 0 12px">O agente sugere, a Coordenação decide. Confirme ou discorde de cada item. O Segundo leitor vê a mesma fila e pode contestar.</p>
        <ul class="linhas">${itens.map(([k, v], i) => `<li class="linha" style="grid-template-columns:170px minmax(0,1fr) auto">
          <span class="rot-mini">${k}</span><span class="t">${esc(v)}<small>Sugestão do agente</small></span>
          ${fechada || conf[i] ? N.estado(conf[i] === 'nao' ? 'e-hoje' : 'e-ok', conf[i] === 'nao' ? 'Você discordou' : 'Confirmado') : `<span class="acoes-item"><button class="btn contorno" data-acao="cd-tri" data-id="${c.id}" data-i="${i}" data-v="nao">Discordar</button><button class="btn" data-acao="cd-tri" data-id="${c.id}" data-i="${i}" data-v="sim">Confirmar</button></span>`}</li>`).join('')}</ul>
        ${fechada ? `<p class="aviso">${I.info}Triagem confirmada em ${fmt(dia(c.envio + 2))}. Patrícia Moura (Segundo leitor) conferiu sem contestar.</p>` : ''}`;
    }
    if (a === 'depoimentos') {
      const termos = [['Quem relatou', 'Assinado à caneta', true], ['Testemunha 1', 'Assinado à caneta', true], ['Testemunha 2', c.acao && c.acao.includes('Termo') ? 'Falta a sua assinatura' : 'Agendado para ' + curto(dia(3)), false], ['Citado', 'Depoimento marcado', false]];
      const trava = [['Pelo menos um depoimento além do relato', true], ['Evidência documental ou testemunhal', true], ['Ouvido o Citado', false], ['Relato não é só anônimo', !c.anonimo]];
      return `<div class="cab"><h2>Termos de declaração</h2><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o envio do áudio do depoimento (até 300 MB), cifrado e entregue só pelo app.">${IC.anexo}Anexar áudio de depoimento</button></div>
        <p class="sub" style="margin:6px 0 10px">Cada depoimento é reduzido a escrito e assinado à caneta pelo depoente e por quem conduziu. Os nomes aparecem só aqui dentro.</p>
        <ul class="linhas">${termos.map(([q, s, ok]) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto auto"><span class="t">${q}<small>Termo de declaração</small></span>${N.estado(ok ? 'e-ok' : 'e-hoje', s)}<button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o Termo de declaração em PDF.">Abrir</button></li>`).join('')}</ul>
        <h3 class="titulo-bloco" style="font-size:15.5px;margin-top:22px">Relatório e Trava de robustez</h3>
        <p class="sub" style="margin:4px 0 8px">Para concluir como procedente, a lista precisa estar completa.</p>
        ${trava.map(([t, ok]) => `<div class="cd-check">${N.estado(ok ? 'e-ok' : 'e-sem', ok ? 'Cumprido' : 'Falta')}<span>${t}</span></div>`).join('')}
        <div class="acoes-item" style="margin-top:12px"><button class="btn" data-acao="toast" data-msg="No sistema, o agente redige o relatório com os nomes trocados por marcadores. Ele roda depois do seu clique.">Redigir o relatório com o agente</button></div>`;
    }
    if (a === 'voto') {
      const votou = c.acao !== 'Votar';
      const votos = [['Helena Duarte', 'Coordenação', true], ['Sérgio Bastos', 'Votante', true], ['Patrícia Moura (você)', 'Votante', votou]];
      return `<div class="cab"><h2>Voto</h2>${N.estado(votou ? 'e-ok' : 'e-hoje', votou ? 'Três votos registrados' : 'Falta o seu voto')}</div>
        <p class="sub" style="margin:6px 0 10px">Os votos só aparecem quando os três votantes votarem.</p>
        <div>${votos.map(([n, cad, ok]) => `<div class="cd-voto"><span class="ini" style="width:36px;height:36px;border-radius:999px;background:var(--suave2);color:var(--titulo);display:inline-flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:700">${N.ini(n)}</span><span style="flex:1"><b style="color:var(--titulo)">${n}</b><span class="sub" style="display:block">${cad}</span></span>${N.estado(ok ? 'e-ok' : 'e-hoje', ok ? 'Votou' : 'Aguardando')}</div>`).join('')}</div>
        ${!votou ? `<div class="acoes-item" style="margin-top:12px"><button class="btn" data-acao="cd-acao-etapa" data-id="${c.id}">Votar</button></div>` : ''}
        <h3 class="titulo-bloco" style="font-size:15.5px;margin-top:22px">Ata de deliberação</h3>
        <p class="sub" style="margin:4px 0 10px">A decisão e o fundamento, assinados pelos três votantes na ClickSign. Antes, a Reunião do Comitê se conclui com os quatro itens conferidos, e a transcrição é eliminada.</p>
        <div class="acoes-item"><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o envio da transcrição da Reunião do Comitê.">${IC.anexo}Anexar a transcrição</button><button class="btn contorno" ${votou ? '' : 'disabled'} data-acao="toast" data-msg="O agente redigiu a Ata de deliberação. Revise antes de enviar à ClickSign.">Gerar a Ata</button><button class="btn" ${votou ? '' : 'disabled'} data-acao="toast" data-msg="Ata enviada à ClickSign para os três votantes.">Enviar para assinatura</button></div>`;
    }
    if (a === 'medida') {
      const M = ['Orientação formal da liderança', 'Advertência por escrito', 'Advertência por escrito e treinamento obrigatório', 'Suspensão', 'Desligamento', 'Arquivamento por improcedência'];
      const reco = RECOS.find((r) => r.caso === c.id);
      return `<div class="cab"><h2>Medida recomendada</h2>${reco ? N.estado('e-ok', 'Enviada à Direção') : N.estado('e-sem', 'A escolher')}</div>
        <p class="sub" style="margin:6px 0 10px">Só valem as medidas da Matriz de Consequências. A Direção recebe a Recomendação do Comitê: a página de conclusão e a Ata de deliberação, nunca o Dossiê do caso.</p>
        ${reco ? `<p style="font-size:16px;color:var(--titulo);font-weight:700;margin:0">${esc(reco.medida)}</p><p class="sub">Enviada em ${fmt(dia(reco.enviada))} · ${esc(reco.sit)}</p><a class="btn contorno" style="margin-top:8px" href="#comiterecomendacao-${reco.id}">Ver a Recomendação</a>`
          : `<div class="opcoes-grandes">${M.map((m) => `<button type="button" class="opcao-g" data-acao="cd-medida" data-v="${esc(m)}" aria-pressed="${est.cd.medida === m}"><b>${esc(m)}</b></button>`).join('')}</div>
          <div class="acoes-item" style="margin-top:12px"><button class="btn" ${est.cd.medida ? '' : 'disabled'} data-acao="toast" data-msg="Recomendação enviada à Direção.">Enviar a Recomendação à Direção</button></div>`}
        <h3 class="titulo-bloco" style="font-size:15.5px;margin-top:22px">Verificação de retaliação</h3>
        <p class="sub" style="margin:4px 0 8px">Depois da medida, o Comitê confere se quem relatou sofreu retaliação.</p>
        <ul class="tempo"><li class="feito"><i aria-hidden="true"></i><b>30 dias</b><span>Sem sinal de retaliação</span></li><li class="${c.acao && c.acao.includes('retaliação') ? 'agora' : ''}"><i aria-hidden="true"></i><b>60 dias</b><span>${c.acao && c.acao.includes('retaliação') ? 'Verificação pedida agora' : 'Ainda não chegou'}</span></li><li><i aria-hidden="true"></i><b>90 dias</b><span>Ainda não chegou</span></li></ul>`;
    }
    if (a === 'relato') {
      return `${sigilo('Esta leitura fica registrada na Trilha do caso, com o seu nome e a hora. O Citado nunca vê esta página.')}
        <h2 class="titulo-bloco" style="margin-top:16px">Relato original</h2>
        <p class="sub" style="margin:4px 0 10px">${c.anonimo ? 'Enviado sem identificação' : 'Enviado com identificação'} em ${fmt(dia(c.envio))}, pelo Canal de Conduta.</p>
        <div class="cd-texto-v">Na passagem de plantão da noite, a coordenação do setor falou comigo aos gritos na frente da equipe, pela terceira vez neste mês. Disse que eu "não servia para nada" e que ia me colocar na escala pior. Duas colegas viram. Tenho medo de represália se eu falar com o RH direto.</div>
        <dl class="pares" style="margin-top:16px"><dt>Quando</dt><dd>Nas três últimas semanas, sempre no plantão noturno</dd><dt>Onde</dt><dd>Posto de enfermagem do 3º andar</dd><dt>Testemunhas</dt><dd>Duas, indicadas no relato</dd><dt>A liderança sabe?</dt><dd>Não</dd></dl>
        <h3 class="titulo-bloco" style="font-size:15.5px;margin-top:18px">Anexos</h3>
        <ul class="linhas"><li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">print-mensagem.png<small>Imagem · 214 KB · cifrada</small></span><button class="btn contorno" data-acao="toast" data-msg="O app decifrou e entregou o anexo. A leitura entrou na Trilha do caso.">Abrir</button></li></ul>`;
    }
    return `<div class="cab"><h2>Mensagens com quem relatou</h2><span class="pill">${c.anonimo ? 'Pelo protocolo e código' : 'Pelo protocolo'}</span></div>
      <div class="conversa" style="margin-top:12px">
        <div class="balao ela"><small>Quem relatou · há ${-c.envio - 2} dias</small>Consigo acompanhar se alguém vai falar comigo antes?</div>
        <div class="balao eu"><small>Comitê · há ${-c.envio - 3} dias</small>Sim. Vamos marcar uma conversa reservada. Você recebe a data por aqui.</div>
      </div>
      <div class="escrever" style="margin-top:12px"><label for="cd-msg" class="sr">Mensagem</label><textarea id="cd-msg" placeholder="Escreva a quem relatou. Ela lê pelo protocolo."></textarea><button class="btn" data-acao="toast" data-msg="Mensagem enviada. Quem relatou lê pelo acompanhamento do protocolo." aria-label="Enviar">${IC.enviar}</button></div>
      <h3 class="titulo-bloco" style="font-size:15.5px;margin-top:22px">Trilha do caso</h3>
      <p class="sub" style="margin:4px 0 10px">Não se edita nem se apaga. Correção entra como nova versão.</p>
      <ul class="tempo">
        <li class="feito"><i aria-hidden="true"></i><b>Relato recebido</b><span>${fmt(dia(c.envio))} · Canal de Conduta</span></li>
        <li class="feito"><i aria-hidden="true"></i><b>Triagem confirmada pela Coordenação</b><span>${fmt(dia(c.envio + 2))} · Helena Duarte</span></li>
        <li class="feito"><i aria-hidden="true"></i><b>Relato lido</b><span>${fmt(dia(c.envio + 2))} · Patrícia Moura</span></li>
        <li class="${c.etapa > 1 ? 'feito' : 'agora'}"><i aria-hidden="true"></i><b>${esc(etapaNome(c))}</b><span>etapa atual</span></li>
      </ul>`;
  }
  N.acoes['cd-tri'] = (a) => { const m = est.cd.triagem[a.dataset.id] = est.cd.triagem[a.dataset.id] || {}; m[a.dataset.i] = a.dataset.v; if (a.dataset.v === 'nao') N.aviso('Discordância registrada. O item volta à Coordenação com a sua anotação.'); N.desenhar(); };
  N.acoes['cd-medida'] = (a) => { est.cd.medida = a.dataset.v; N.desenhar(); };

  // ações da coluna lateral
  N.acoes['cd-acao-etapa'] = (a) => {
    const c = caso(a.dataset.id);
    if (c.acao === 'Votar') {
      N.modal('Votar', `<p class="sub" style="margin:0 0 12px"><span class="num">${c.prot}</span> · o seu voto fica oculto até os três votarem.</p>
        <div class="opcoes-grandes"><button type="button" class="opcao-g" data-acao="cd-voto-esc" aria-pressed="false"><b>Procedente</b><small>A Trava de robustez está completa</small></button><button type="button" class="opcao-g" data-acao="cd-voto-esc" aria-pressed="false"><b>Improcedente</b><small>Arquiva o caso</small></button></div>
        <div class="campo" style="margin-top:12px"><label for="cd-fund">Fundamento</label><textarea id="cd-fund"></textarea></div>`,
      `<button type="button" class="btn" data-acao="cd-feito" data-id="${c.id}" data-msg="Voto registrado. A Ata pode ser gerada quando os três votarem.">Registrar o voto</button>`);
      return;
    }
    if (c.acao === 'Confirmar a triagem') { est.cd.aba = 'triagem'; N.desenhar(); N.aviso('Confirme ou discorde de cada item da sugestão.'); return; }
    N.modal(esc(c.acao), `<p class="sub" style="margin:0 0 12px"><span class="num">${c.prot}</span> · ${esc(etapaNome(c))}</p><div class="campo"><label for="cd-anot">Anotação</label><textarea id="cd-anot"></textarea></div>`,
      `<button type="button" class="btn" data-acao="cd-feito" data-id="${c.id}" data-msg="Registrado na Trilha do caso.">Confirmar</button>`);
  };
  N.acoes['cd-voto-esc'] = (a) => { a.parentNode.querySelectorAll('.opcao-g').forEach((b) => b.setAttribute('aria-pressed', String(b === a))); };
  N.acoes['cd-feito'] = (a) => { const c = caso(a.dataset.id); c.acao = null; N.fecharModal(); N.desenhar(); N.aviso(a.dataset.msg); };
  N.acoes['cd-prorrogar'] = () => N.modal('Prorrogar o prazo', `<div class="grade-form"><div class="campo"><label for="cd-dias">Mais quantos dias</label><select id="cd-dias"><option>10</option><option>15</option><option>30</option></select></div></div><div class="campo" style="margin-top:12px"><label for="cd-mot">Motivo</label><textarea id="cd-mot"></textarea></div>`, '<button type="button" class="btn" data-acao="toast" data-msg="Prazo prorrogado. A mudança entrou na Trilha do caso.">Prorrogar</button>');
  N.acoes['cd-convidar'] = () => N.modal('Convidar ao caso', `<p class="sub" style="margin:0 0 12px">O Apurador designado e o membro da CIPA entram por convite e só abrem este caso depois do termo assinado.</p><div class="grade-form"><div class="campo"><label for="cd-quem">Nome</label><input id="cd-quem"></div><div class="campo"><label for="cd-papel">Papel</label><select id="cd-papel"><option>Apurador designado</option><option>Membro da CIPA</option></select></div></div>`, '<button type="button" class="btn" data-acao="toast" data-msg="Convite enviado com o termo para assinar na ClickSign.">Enviar o convite</button>');
  N.acoes['cd-nsp'] = () => N.modal('Sinalizar ao NSP', `<p class="sub" style="margin:0 0 12px">O Núcleo recebe só uma nota do Comitê, nunca o relato. A Coordenação envia a nota que um membro escreveu.</p><div class="campo"><label for="cd-nota">Nota ao Núcleo</label><textarea id="cd-nota" placeholder="O que o Núcleo precisa saber, sem nomes"></textarea></div>`, '<button type="button" class="btn" data-acao="toast" data-msg="Nota salva. A Coordenação revisa e envia ao Núcleo.">Salvar a nota</button>');
  N.acoes['cd-afastar'] = () => N.modal('Pedir afastamento cautelar', `<p class="sub" style="margin:0 0 12px">Afastamento remunerado durante o caso. Não é punição e nunca recai sobre quem relatou. O DP e o Jurídico recebem só quem afastar e o motivo.</p><div class="campo"><label for="cd-af-q">Quem afastar</label><input id="cd-af-q"></div><div class="campo" style="margin-top:12px"><label for="cd-af-m">Motivo</label><textarea id="cd-af-m"></textarea></div>`, '<button type="button" class="btn" data-acao="toast" data-msg="Pedido de afastamento enviado à Coordenação.">Enviar o pedido</button>');
  N.acoes['cd-impedimento'] = () => N.modal('Declarar impedimento', `<p class="sub" style="margin:0 0 12px">Você deixa de ver este caso na hora. Um suplente é convocado no seu lugar. Não dá para desfazer.</p><div class="campo"><label for="cd-imp">Motivo (fica só na Trilha do caso)</label><textarea id="cd-imp"></textarea></div>`, '<button type="button" class="btn" style="background:var(--verm);border-color:var(--verm)" data-acao="cd-impedido">Declarar e sair do caso</button>');
  N.acoes['cd-impedido'] = () => { N.fecharModal(); location.hash = '#comitecasos'; N.aviso('Impedimento declarado. O caso saiu da sua lista e um suplente foi convocado.'); };

  // ------------------------------------------------------------------ Recomendações
  T.comiterecomendacoes = { trilha: 'Comitê de Conduta', menu: 'comiterecomendacoes', mapa: ['Comitê de Conduta', 'Recomendações'], render() {
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <p class="sub" style="margin:0 0 10px">O que a Direção lê de cada caso: a página de conclusão e a Ata de deliberação. O Presidente só lê; a diretoria executiva registra a decisão sobre a medida.</p>
      <div class="tabela-rola"><table class="tab"><thead><tr><th>Protocolo</th><th>Medida recomendada</th><th>Enviada em</th><th>Situação</th><th></th></tr></thead><tbody>
      ${RECOS.map((r) => `<tr><td><a href="#comiterecomendacao-${r.id}" class="num">${recoProt(r)}</a><div class="sub">${esc(recoCat(r))}</div></td><td>${esc(r.medida)}</td><td class="num">${fmt(dia(r.enviada))}</td>
        <td>${N.estado(r.sit.startsWith('Aguardando') ? 'e-hoje' : r.comunicada ? 'e-ok' : 'e-prox', r.sit.startsWith('Aguardando') ? 'Aguardando decisão' : r.comunicada ? 'Medida comunicada' : 'Falta comunicar')}</td>
        <td style="text-align:right"><a class="btn${r.sit.startsWith('Aguardando') || !r.comunicada ? '' : ' contorno'}" href="#comiterecomendacao-${r.id}">${r.sit.startsWith('Aguardando') ? 'Decidir' : !r.comunicada ? 'Anexar a comunicação' : 'Ler'}</a></td></tr>`).join('')}
      </tbody></table></div></section>`;
    return N.modulo({ ...CAB, titulo: 'Recomendações', frase: `${RECOS.filter((r) => r.sit.startsWith('Aguardando')).length} Recomendação espera a decisão da Direção e ${RECOS.filter((r) => !r.sit.startsWith('Aguardando') && !r.comunicada).length} espera a comunicação da medida.` }, null, abas('#comiterecomendacoes'), corpo);
  } };

  T.comiterecomendacao = { trilha: 'Recomendação do Comitê', menu: 'comiterecomendacoes', mapa: ['Comitê de Conduta', 'Recomendação (página própria)'], render(id) {
    const r = RECOS.find((x) => x.id === id) || RECOS[0];
    const aguardando = r.sit.startsWith('Aguardando') && !est.cd.decisao[r.id];
    const D = ['Acatar a medida', 'Acatar com ajuste', 'Não acatar'];
    return `<div class="pagina">
      <a class="voltar" href="#comiterecomendacoes">${I.voltar}Voltar às Recomendações</a>
      <div class="duas">
        <section class="cartao bloco larga" style="padding:24px">
          <div style="display:flex;gap:10px;flex-wrap:wrap"><span class="pill">${esc(recoCat(r))}</span>${N.estado(aguardando ? 'e-hoje' : 'e-ok', aguardando ? 'Aguardando a decisão da Direção' : 'Decidida')}</div>
          <h1 class="pagina-titulo num" style="margin-top:12px">${recoProt(r)}</h1>
          <p class="pagina-sub">Recomendação do Comitê enviada em ${fmt(dia(r.enviada))}</p>
          <h2 class="titulo-bloco" style="margin-top:20px">Conclusão do Comitê</h2>
          <p style="max-width:70ch">O Comitê concluiu, por três votos, que a conduta relatada aconteceu e se repetiu. Os depoimentos e a evidência documental confirmam o relato. A Trava de robustez está completa.</p>
          <dl class="ficha"><div><dt>Medida recomendada</dt><dd>${esc(r.medida)}</dd></div><div><dt>Votos</dt><dd>3 de 3, procedente</dd></div><div><dt>Ata de deliberação</dt><dd>Assinada pelos três</dd></div></dl>
          <div class="acoes-item" style="margin-top:16px"><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre a Ata de deliberação assinada (PDF entregue pelo app).">${IC.olho}Ler a Ata de deliberação</button></div>
        </section>
        <aside class="estreita">
          <section class="cartao bloco cd-agora">
            <span class="rot-mini">${aguardando ? 'Decisão da Direção' : 'Comunicação da medida'}</span>
            ${aguardando ? `<p class="sub" style="margin:6px 0 10px">Só a diretoria executiva registra. O Presidente lê.</p>
              <div class="cd-acoes-sec">${D.map((d) => `<button type="button" class="opcao-g" data-acao="cd-decisao-esc" data-v="${d}" aria-pressed="${est.cd.decEsc === d}"><b>${d}</b></button>`).join('')}</div>
              <div class="campo" style="margin-top:12px"><label for="cd-dec-f">Fundamento</label><textarea id="cd-dec-f"></textarea></div>
              <button class="btn grande" style="width:100%;margin-top:12px" ${est.cd.decEsc ? '' : 'disabled'} data-acao="cd-decidir" data-id="${r.id}">Registrar a decisão</button>`
              : `<p style="margin:8px 0 0;color:var(--titulo);font-weight:700">${r.comunicada ? 'Medida comunicada' : 'Anexe a comunicação feita à pessoa'}</p>
              ${r.comunicada ? '<p class="sub">Comunicação anexada e registrada na Trilha do caso.</p>' : `<div class="solta" style="margin-top:12px"><b>Solte o PDF aqui</b>ou <label style="color:var(--acento);cursor:pointer;font-weight:700">escolha o arquivo<input type="file" hidden></label></div><button class="btn grande" style="width:100%;margin-top:12px" data-acao="toast" data-msg="Comunicação anexada. O caso segue para a verificação de retaliação.">Anexar a comunicação</button>`}`}
          </section>
        </aside>
      </div>
      <p class="demo">Dados de demonstração.</p>
    </div>`;
  } };
  N.acoes['cd-decisao-esc'] = (a) => { est.cd.decEsc = a.dataset.v; N.desenhar(); };
  N.acoes['cd-decidir'] = (a) => { est.cd.decisao[a.dataset.id] = est.cd.decEsc; const r = RECOS.find((x) => x.id === a.dataset.id); r.sit = 'Decidida: ' + est.cd.decEsc.toLowerCase(); est.cd.decEsc = null; N.desenhar(true); N.aviso('Decisão registrada. Falta anexar a comunicação da medida.'); };

  // ------------------------------------------------------------------ Membros
  T.comitemembros = { trilha: 'Comitê de Conduta', menu: 'comitemembros', mapa: ['Comitê de Conduta', 'Membros'], render() {
    const vigentes = MEMBROS.filter((m) => est.cd.data === 'hoje' ? !m.encerrado : true);
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas"><div class="chips" role="group" aria-label="Composição"><button class="chip" data-acao="cd-data" data-v="hoje" aria-pressed="${est.cd.data === 'hoje'}">Composição de hoje</button><button class="chip" data-acao="cd-data" data-v="passada" aria-pressed="${est.cd.data === 'passada'}">Composição em ${fmt(dia(-30))}</button></div>
        <button class="btn" data-acao="cd-incluir">${IC.mais}Incluir membro</button></div>
      <div class="tabela-rola"><table class="tab"><thead><tr><th>Membro</th><th>Cadeira</th><th>Vigência</th><th>Termo de sigilo</th><th></th></tr></thead><tbody>
      ${vigentes.map((m) => `<tr><td><b style="color:var(--titulo)">${m.nome}</b>${m.diretor ? '<div class="sub">Diretor: fica fora da Rota Especial</div>' : ''}</td><td>${m.cadeira}</td>
        <td class="num">${fmt(dia(m.desde))} a ${fmt(dia(m.ate))}${m.encerrado ? '<div class="sub">Encerrada</div>' : ''}</td>
        <td>${N.estado(m.termo === 'Assinado' ? 'e-ok' : 'e-hoje', m.termo)}</td>
        <td style="text-align:right"><button class="btn contorno" data-acao="cd-membro" data-id="${m.id}">Ver</button></td></tr>`).join('')}
      </tbody></table></div></section>
      <section class="cartao bloco" style="margin-top:14px"><h2 class="titulo-bloco" style="margin-bottom:10px">Registro das mudanças</h2>
        <ul class="tempo">${REGISTRO.map(([q, t]) => `<li class="feito"><i aria-hidden="true"></i><b>${t}</b><span>${q}</span></li>`).join('')}</ul></section>`;
    return N.modulo({ ...CAB, titulo: 'Membros', frase: `${MEMBROS.filter((m) => !m.encerrado).length} membros com Participação vigente. ${MEMBROS.filter((m) => !m.encerrado && m.termo !== 'Assinado').length} ainda sem o Termo assinado.` }, null, abas('#comitemembros'), corpo);
  } };
  N.acoes['cd-data'] = (a) => { est.cd.data = a.dataset.v; N.desenhar(); };
  N.acoes['cd-membro'] = (a) => {
    const m = MEMBROS.find((x) => x.id === a.dataset.id);
    N.abrirGaveta({ sobre: N.estado(m.termo === 'Assinado' ? 'e-ok' : 'e-hoje', 'Termo: ' + m.termo), titulo: m.nome,
      corpo: `<dl class="pares"><dt>Cadeira</dt><dd>${m.cadeira}</dd><dt>Vigência</dt><dd class="num">${fmt(dia(m.desde))} a ${fmt(dia(m.ate))}</dd><dt>Diretor</dt><dd>${m.diretor ? 'Sim, nunca entra no Grupo Especial' : 'Não'}</dd></dl>
        <div><h3 class="titulo-bloco" style="font-size:15px">Termo de sigilo na ClickSign</h3><p class="sub" style="margin:4px 0 10px">${m.termo === 'Assinado' ? 'Assinado em ' + fmt(dia(m.desde + 2)) + '. Cópia do PDF guardada no app.' : 'Enviado há 3 dias. Até assinar, a pessoa não vê nenhum caso.'}</p>
        <div class="acoes-item"><button class="btn contorno" data-acao="toast" data-msg="Status reconsultado na ClickSign: ${m.termo.toLowerCase()}.">Reconsultar a ClickSign</button>${m.termo !== 'Assinado' ? '<button class="btn contorno" data-acao="toast" data-msg="Termo reenviado por e-mail pela ClickSign.">Reenviar o Termo</button>' : ''}</div></div>`,
      pe: m.encerrado ? '' : `<button class="btn contorno" style="color:var(--verm)" data-acao="cd-encerrar" data-id="${m.id}">Encerrar participação</button>` });
  };
  N.acoes['cd-encerrar'] = (a) => { const m = MEMBROS.find((x) => x.id === a.dataset.id); N.acoes['fechar-gaveta'](); N.modal('Encerrar participação', `<p class="sub" style="margin:0 0 12px">${m.nome} deixa de ver os casos hoje. O Comitê é avisado e a mudança entra no registro.</p><div class="campo"><label for="cd-enc">Motivo</label><textarea id="cd-enc"></textarea></div>`, `<button type="button" class="btn" style="background:var(--verm);border-color:var(--verm)" data-acao="cd-encerrado" data-id="${m.id}">Encerrar hoje</button>`); };
  N.acoes['cd-encerrado'] = (a) => { const m = MEMBROS.find((x) => x.id === a.dataset.id); m.encerrado = true; m.ate = 0; REGISTRO.unshift(['agora', `Participação de ${m.nome} encerrada.`]); N.fecharModal(); N.desenhar(); N.aviso('Participação encerrada. O Comitê foi avisado.'); };
  N.acoes['cd-incluir'] = () => N.modal('Incluir membro', `<div class="grade-form"><div class="campo"><label for="cd-nm">Pessoa</label><input id="cd-nm" placeholder="Buscar no cadastro"></div><div class="campo"><label for="cd-cad">Cadeira</label><select id="cd-cad"><option>Votante</option><option>Suplente</option><option>Coordenação</option></select></div><div class="campo"><label for="cd-vig">Vigência até</label><input id="cd-vig" type="date"></div></div><p class="sub" style="margin:12px 0 0">O Termo de sigilo segue para a ClickSign. A pessoa só vê casos depois de assinar.</p>`, '<button type="button" class="btn" data-acao="toast" data-msg="Membro incluído. O Termo seguiu para a ClickSign.">Incluir e enviar o Termo</button>');

  // ------------------------------------------------------------------ Guia dos ritos
  T.comiteguia = { trilha: 'Comitê de Conduta', menu: 'comiteguia', mapa: ['Comitê de Conduta', 'Guia dos ritos'], render() {
    const G = {
      Encaminhamento: ['O relato não é conduta grave e tem outro destino (DP, Ouvidoria, liderança).', 'A Coordenação orienta quem relatou e encaminha. Ninguém é ouvido.'],
      Rápido: ['Conduta leve, com fato claro e sem necessidade de ouvir testemunhas.', 'A Coordenação conduz sozinha a orientação e o retorno.'],
      Completo: ['Conduta grave que pede apuração: depoimentos, relatório, voto e ata.', 'Os três votantes decidem. Um Apurador designado pode ser convidado.'],
      Especial: ['O relato envolve a Direção, a Presidência ou a família proprietária.', 'O Grupo Especial apura, sem nenhum diretor. O grupo não muda com o caso aberto.']
    };
    const corpo = `<div class="grade g2 cd-guia">${Object.entries(RITOS).map(([r, d]) => `<section class="cartao bloco cd-rito">
      <div class="cab"><h2>Rito ${r}</h2><span class="pill">${d.prazo} dias</span></div>
      <p style="margin:0"><b style="color:var(--titulo)">Quando:</b> ${G[r][0]}</p><p style="margin:0"><b style="color:var(--titulo)">Quem faz:</b> ${G[r][1]}</p>
      <ol>${d.etapas.map((e) => `<li>${e}</li>`).join('')}</ol>
      <a class="link" href="#comitecasos" data-acao="cd-ver-rito" data-v="${r}" style="font-size:13.5px;font-weight:700;text-decoration:none">Ver os casos deste rito${I.seta}</a>
    </section>`).join('')}</div>
    <p class="aviso">${I.info}O prazo de todo rito conta do envio do relato, não da triagem.</p>`;
    return N.modulo({ ...CAB, titulo: 'Guia dos ritos', frase: 'Os quatro caminhos que um caso pode seguir, com o prazo e quem faz o quê.', acoes: `<a class="btn claro grande" href="#comite">Ir para Minha vez</a>` }, null, abas('#comiteguia'), corpo);
  } };
  N.acoes['cd-ver-rito'] = (a) => { est.cd.rito = a.dataset.v; est.cd.casosFiltro = 'abertos'; location.hash = '#comitecasos'; };

  // ------------------------------------------------------------------ Configurações
  const TEXTOS = [
    ['Entrada da página pública', 3, 'Este canal é para relatar conduta grave no trabalho. Você pode relatar sem dizer quem é.'],
    ['Aviso de privacidade', 2, 'O relato é cifrado e só o Comitê de Conduta lê. Ninguém de fora do Comitê, nem a liderança, recebe o seu nome.'],
    ['Página de Proteção', 1, 'Quem relata de boa-fé está protegido contra retaliação. O Comitê verifica isso em 30, 60 e 90 dias.'],
    ['Resposta automática ao relatar', 2, 'Recebemos o seu relato. Guarde o protocolo e o código para acompanhar.']
  ];
  T.comiteconfig = { trilha: 'Comitê de Conduta', menu: 'comite', mapa: ['Comitê de Conduta', 'Configurações'], render() {
    const corpo = `<div class="grade g2">${TEXTOS.map(([t, v, txt], i) => `<section class="cartao bloco"><div class="cab"><h2 style="font-size:16px">${t}</h2><span class="pill">versão ${v}</span></div>
      <p class="cd-texto-v">${esc(txt)}</p><div class="acoes-item" style="margin-top:12px"><button class="btn contorno" data-acao="cd-editar-texto" data-i="${i}">${IC.lapis}Editar</button><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre as versões anteriores deste texto.">Versões anteriores</button></div></section>`).join('')}</div>
      <section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2>Código de Conduta</h2><button class="btn" data-acao="cd-codigo">Publicar nova versão</button></div>
        <ul class="linhas" style="margin-top:6px"><li class="linha" style="grid-template-columns:minmax(0,1fr) auto auto"><span class="t">Versão 2<small>Vigente desde ${fmt(dia(-120))}</small></span><span class="pill verde">Vigente</span><button class="btn contorno" data-acao="toast" data-msg="Download do Código de Conduta, versão 2.">${IC.baixar}Baixar</button></li>
        <li class="linha" style="grid-template-columns:minmax(0,1fr) auto auto"><span class="t">Versão 1<small>De ${fmt(dia(-400))} a ${fmt(dia(-121))}</small></span><span class="pill cinza">Arquivada</span><button class="btn contorno" data-acao="toast" data-msg="Download do Código de Conduta, versão 1.">${IC.baixar}Baixar</button></li></ul></section>`;
    return N.modulo({ ...CAB, titulo: 'Configurações', frase: 'Os textos que quem relata lê e o Código de Conduta. Só a Coordenação edita, e cada mudança vira uma versão nova.' }, null, abas('#comiteconfig'), corpo);
  } };
  N.acoes['cd-editar-texto'] = (a) => { const [t, v, txt] = TEXTOS[a.dataset.i]; N.modal('Editar: ' + t, `<div class="campo"><label for="cd-txt">Texto</label><textarea id="cd-txt" style="min-height:160px">${esc(txt)}</textarea></div><p class="sub" style="margin:8px 0 0">Ao salvar, nasce a versão ${v + 1}. A versão ${v} fica no histórico.</p>`, `<button type="button" class="btn" data-acao="cd-salvar-texto" data-i="${a.dataset.i}">Salvar a versão ${v + 1}</button>`); };
  N.acoes['cd-salvar-texto'] = (a) => { const t = TEXTOS[a.dataset.i]; const novo = document.getElementById('cd-txt').value.trim(); if (novo) t[2] = novo; t[1] += 1; N.fecharModal(); N.desenhar(); N.aviso('Texto salvo como versão ' + t[1] + '.'); };
  N.acoes['cd-codigo'] = () => N.modal('Publicar nova versão do Código', `<div class="solta"><b>Solte o PDF do Código de Conduta aqui</b>ou <label style="color:var(--acento);cursor:pointer;font-weight:700">escolha o arquivo<input type="file" hidden></label></div><div class="campo" style="margin-top:12px"><label for="cd-vig2">Vale a partir de</label><input id="cd-vig2" type="date"></div>`, '<button type="button" class="btn" data-acao="toast" data-msg="Versão 3 do Código publicada. A versão 2 foi arquivada.">Publicar</button>');
})();
