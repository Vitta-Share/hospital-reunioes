/* Secretaria, Perfil, Configurações, Manual, o Mapa do protótipo e a busca Ctrl+K completa. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I, IC, dia, fmt, curto, est, reunioes, deIso, difDias, HOJE, iso } = N;
  const T = N.telas;

  // os mapas das telas de Meu trabalho
  T.pendencias.mapa = ['Meu trabalho', 'Pendências: lista'];
  T.quadro.mapa = ['Meu trabalho', 'Pendências: quadro'];
  T.concluidas.mapa = ['Meu trabalho', 'Pendências concluídas'];
  T.rotinas.mapa = ['Meu trabalho', 'Rotinas'];
  T.calendario.mapa = ['Meu trabalho', 'Calendário'];

  // ------------------------------------------------------------------ Secretaria
  est.sec = { editar: null };
  const FACILIT = ['Renata Alves', 'Felipe Duarte', 'Marina Couto', 'Sílvia Ramos', 'Teresa Lopes'];
  const marcadas = () => reunioes.filter((r) => difDias(deIso(r.data)) >= 0).sort((a, b) => (a.data + a.hora).localeCompare(b.data + b.hora));
  T.secretaria = { trilha: 'Agenda das Reuniões', menu: 'secretaria', mapa: ['Secretaria', 'Agenda das Reuniões'], render() {
    const lista = marcadas();
    const semana = lista.filter((r) => difDias(deIso(r.data)) <= 7);
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="cab"><h2 class="titulo-bloco">Próximas Reuniões</h2><a class="btn" href="#secretarianova">${IC.mais}Marcar Reunião</a></div>
      <ul class="linhas" style="margin-top:6px">${lista.map((r) => `<li class="linha" style="grid-template-columns:130px minmax(0,1fr) 190px auto 32px">
        <span class="num"><b style="display:block;color:var(--titulo)">${curto(deIso(r.data))}</b><span class="sub">${r.hora}</span></span>
        <span class="t">${esc(r.titulo)}<small>Facilitadora: Renata Alves · ${r.participantes.length} Participantes</small></span>
        <span class="sub">Marcada por você</span>
        <button class="btn contorno" data-acao="sec-ver" data-id="${r.id}">Ver</button>
        <span class="mais-wrap"><button class="mais" data-pop="sec-${r.id}" aria-expanded="${est.pop === 'sec-' + r.id}" aria-label="Mais opções">${I.tres}</button>${est.pop === 'sec-' + r.id ? `<div class="pop" role="menu"><a role="menuitem" href="#secretarianova-${r.id}">Editar</a><button role="menuitem" data-acao="sec-cancelar" data-id="${r.id}" style="color:var(--verm)">Desmarcar</button></div>` : ''}</span></li>`).join('')}</ul>
    </section>`;
    return N.modulo({ sobre: 'Secretaria', titulo: 'Agenda das Reuniões', frase: `${lista.length} Reuniões marcadas, ${semana.length} nos próximos 7 dias. Você marca e inclui Participantes; a Ata fica com o Facilitador.`,
      acoes: `<a class="btn claro grande" href="#secretarianova">Marcar Reunião</a><a class="btn vidro grande" href="#calendario">Ver no Calendário</a>` },
    [['Esta semana', String(semana.length).padStart(2, '0'), I.agenda, '#secretaria'], ['Marcadas por você', String(lista.length).padStart(2, '0'), I.certo, '#secretaria'], ['Sem Participantes', '00', I.alerta, '#secretaria']], '', corpo);
  } };
  N.acoes['sec-ver'] = (a) => { const r = reunioes.find((x) => x.id === a.dataset.id);
    N.abrirGaveta({ sobre: '<span class="pill">Programada</span>', titulo: esc(r.titulo), corpo: `<dl class="pares"><dt>Quando</dt><dd>${N.longo(deIso(r.data))}, ${r.hora}</dd><dt>Facilitadora</dt><dd>Renata Alves</dd><dt>Participantes</dt><dd>${r.participantes.map(esc).join(', ')}</dd></dl><div><h3 class="titulo-bloco" style="font-size:15px">Pauta</h3><ol style="padding-left:20px">${r.pauta.map((x) => `<li>${esc(x)}</li>`).join('')}</ol></div><p class="aviso">${I.info}A Ata e as Pendências desta Reunião ficam com o Facilitador.</p>`,
      pe: `<button class="btn contorno" data-acao="sec-cancelar" data-id="${r.id}">Desmarcar</button><a class="btn" href="#secretarianova-${r.id}" data-acao="fechar-gaveta-ir" data-href="#secretarianova-${r.id}">Editar</a>` }); };
  N.acoes['sec-cancelar'] = (a) => { N.acoes['fechar-gaveta'](); N.modal('Desmarcar a Reunião?', '<p>Os Participantes recebem o aviso de que a Reunião foi desmarcada.</p><div class="campo"><label for="sc-mot">Motivo (vai no aviso)</label><textarea id="sc-mot"></textarea></div>', `<button type="button" class="btn" style="background:var(--verm);border-color:var(--verm)" data-acao="toast" data-msg="Reunião desmarcada. Os Participantes foram avisados.">Desmarcar</button>`); };
  T.secretarianova = { trilha: (id) => id ? 'Editar Reunião' : 'Nova Reunião', menu: 'secretarianova', mapa: ['Secretaria', 'Marcar Reunião'], render(id) {
    const r = id ? reunioes.find((x) => x.id === id) : null;
    return `<div class="pagina"><a class="voltar" href="#secretaria">${I.voltar}Voltar à Agenda</a>
      <form class="cartao bloco" id="form-sec" style="padding:24px;max-width:900px;display:flex;flex-direction:column;gap:16px">
        <h1 class="pagina-titulo">${r ? 'Editar a Reunião' : 'Marcar Reunião'}</h1><p class="pagina-sub" style="margin-top:-8px">O Facilitador recebe o convite e passa a conduzir a Reunião.</p>
        <div class="campo"><label for="sc-tit">Título</label><input id="sc-tit" required value="${r ? esc(r.titulo) : ''}" placeholder="Ex.: Reunião da Diretoria Assistencial"></div>
        <div class="grade-form"><div class="campo"><label for="sc-data">Data</label><input id="sc-data" type="date" required value="${r ? r.data : iso(dia(1))}"></div><div class="campo"><label for="sc-ini">Início</label><input id="sc-ini" type="time" value="${r ? r.hora : '09:00'}"></div><div class="campo"><label for="sc-fim">Término</label><input id="sc-fim" type="time" value="10:00"></div></div>
        <div class="grade-form"><div class="campo"><label for="sc-fac">Facilitador</label><select id="sc-fac" required>${FACILIT.map((f) => `<option>${f}</option>`).join('')}</select></div><div class="campo"><label for="sc-tipo">Tipo de Reunião</label><select id="sc-tipo"><option>Diretoria</option><option>Comissão</option><option>Operacional</option></select></div><div class="campo"><label for="sc-setor">Setor</label><select id="sc-setor"><option>Diretoria Assistencial</option><option>Enfermagem</option><option>Farmácia</option></select></div></div>
        <div class="campo"><label for="sc-part">Participantes</label><input id="sc-part" value="${r ? esc(r.participantes.join(', ')) : ''}" placeholder="Digite um nome e escolha na lista"></div>
        <div class="campo"><label for="sc-pauta">Pauta, um assunto por linha</label><textarea id="sc-pauta">${r ? esc(r.pauta.join('\n')) : ''}</textarea></div>
        <div style="display:flex;gap:10px;justify-content:flex-end"><a class="btn contorno grande" href="#secretaria">Cancelar</a><button class="btn grande" type="submit">${r ? 'Salvar alterações' : 'Marcar Reunião'}</button></div>
      </form></div>`;
  } };
  N.envios['form-sec'] = () => { N.aviso('Reunião marcada. O Facilitador e os Participantes receberam o convite.'); location.hash = '#secretaria'; };

  // ------------------------------------------------------------------ Perfil (os números ficam no Início; aqui é a conta)
  T.perfil = { trilha: 'Meu perfil', menu: 'perfil', mapa: ['Conta', 'Meu perfil'], render() {
    const p = N.PERFIS[N.perfil()];
    return `${N.cabModulo({ sobre: 'Conta', titulo: esc(p.nome), frase: `${esc(p.cargo)} · ativo desde março de 2025`, acoes: `<a class="btn claro grande" href="#configuracoes">Configurações</a>` })}
    <div class="corpo-modulo"><div class="grade g2">
      <section class="cartao bloco"><h2 class="titulo-bloco">Dados</h2><dl class="pares" style="margin-top:12px"><dt>E-mail</dt><dd>${esc(p.nome.toLowerCase().replace(/ /g, '.').normalize('NFD').replace(/[̀-ͯ]/g, ''))}@exemplo.com</dd><dt>Cargo</dt><dd>${esc(p.cargo)}</dd><dt>Setor</dt><dd>Diretoria Assistencial</dd><dt>Acessos</dt><dd>Reuniões, POPs, Ouvidoria do setor, Núcleo</dd></dl></section>
      <section class="cartao bloco"><h2 class="titulo-bloco">Seus números</h2><p class="sub" style="margin:8px 0 12px">Os números de 90 dias moram no Início, junto do que você tem para entregar.</p><a class="btn contorno" href="#inicio">Ver no Início</a></section>
    </div><p class="demo">Dados de demonstração.</p></div>`;
  } };

  // ------------------------------------------------------------------ Configurações
  est.cfg = { aba: 'notificacoes' };
  T.configuracoes = { trilha: 'Configurações', menu: 'configuracoes', mapa: ['Conta', 'Configurações'], render() {
    const ABAS = [['notificacoes', 'Notificações'], ['seguranca', 'Segurança'], ['aparencia', 'Aparência']];
    const tg = (id, t, s, on) => `<label style="display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 0;border-bottom:1px solid var(--linha)"><span><b style="display:block;color:var(--titulo);font-size:15px">${t}</b><span class="sub">${s}</span></span><input type="checkbox" id="${id}" ${on ? 'checked' : ''} style="width:22px;height:22px;accent-color:var(--btn-fundo)"></label>`;
    const miolo = {
      notificacoes: tg('n1', 'Pendência perto do prazo', 'E-mail 48 horas antes do prazo', true) + tg('n2', 'Menção num comentário', 'No sino e por e-mail', true) + tg('n3', 'Ata pronta para assinar', 'No sino e por e-mail', true) + tg('n4', 'Resumo da semana', 'Segunda de manhã, por e-mail', false),
      seguranca: `<div class="grade-form" style="margin-top:12px"><div class="campo"><label for="s1">Senha atual</label><input id="s1" type="password"></div><div class="campo"><label for="s2">Nova senha</label><input id="s2" type="password"></div></div><button class="btn" style="margin-top:14px" data-acao="toast" data-msg="Senha trocada.">Trocar a senha</button>`,
      aparencia: tg('a1', 'Menos movimento', 'Desliga as animações de entrada', false) + tg('a2', 'Menu recolhido ao abrir', 'Só os ícones na lateral', false)
    }[est.cfg.aba];
    return `${N.cabModulo({ sobre: 'Conta', titulo: 'Configurações', frase: 'Como o app avisa você e como ele se comporta.' })}
    <div class="corpo-modulo">${N.abasModulo(ABAS.map(([k, t]) => ['#configuracoes-' + k, t]), '#configuracoes-' + est.cfg.aba)}
      <section class="cartao bloco" style="margin-top:14px;max-width:820px">${miolo}</section><p class="demo">Dados de demonstração.</p></div>`;
  } };
  const renderCfg = T.configuracoes.render;
  T.configuracoes.render = (id) => { if (id) est.cfg.aba = id; return renderCfg(); };

  // ------------------------------------------------------------------ Manual
  T.manual = { trilha: 'Manual', menu: 'manual', mapa: ['Conta', 'Manual'], render() {
    const S = [['Início', 'O que depende de você, de todos os módulos, numa fila só.'], ['Pendências', 'Concluir, pedir novo prazo, contestar e comentar.'], ['Reuniões', 'Agendar, gerar a Ata pela Transcrição ou pela Ata Guiada, e assinar.'], ['Rotinas', 'Marcar a Verificação do ciclo.'], ['POPs', 'Elaborar, revisar, validar e ler na Biblioteca.'], ['Ouvidoria', 'Responder os casos do seu setor no prazo.'], ['Notificar incidente', 'Qualquer pessoa notifica, com ou sem identificação.']];
    return `${N.cabModulo({ sobre: 'Ajuda', titulo: 'Manual', frase: 'Cada tela explicada em poucas linhas, com o caminho para fazer.' })}
    <div class="corpo-modulo"><div class="grade g3">${S.map(([t, s]) => `<a class="cartao bloco cartao-link" href="#manual"><h2 class="titulo-bloco">${t}</h2><p class="sub" style="margin:6px 0 0">${s}</p><span class="ir">Ler${IC.seta}</span></a>`).join('')}</div><p class="demo">Dados de demonstração.</p></div>`;
  } };

  // ------------------------------------------------------------------ Mapa de todas as telas do protótipo
  T.mapa = { trilha: 'Mapa do protótipo', menu: 'mapa', render() {
    const grupos = {};
    Object.entries(T).forEach(([k, t]) => { if (!t.mapa) return; (grupos[t.mapa[0]] = grupos[t.mapa[0]] || []).push([k, t.mapa[1], t]); });
    const ordem = ['Meu trabalho', 'Reuniões e metas', 'POPs', 'Ouvidoria', 'Segurança do Paciente', 'Contas médicas', 'Comitê de Conduta', 'Administração', 'Secretaria', 'Conta', 'Telas públicas'];
    const nomes = Object.keys(grupos).sort((a, b) => (ordem.indexOf(a) + 99) % 99 - (ordem.indexOf(b) + 99) % 99);
    const total = Object.values(grupos).reduce((n, g) => n + g.length, 0) + 1;
    const exemplo = { reuniao: 'r1', ouvcaso: '482', popversao: 'pop1', popelaboracao: 'pop6', nspcaso: '1', nsptriar: '1', contasguia: '1', contasoperadora: 'UNI', comitecaso: '12', comiterecomendacao: '12', adminusuario: 'cn', centralobjetivo: 'google', responder: 'demo', aceite: 'demo', minhaspendencias: 'demo', ataguiada: 'r1', secretarianova: '' };
    return `${N.cabModulo({ sobre: 'Protótipo 2B', titulo: 'Todas as telas', frase: `${total} telas no modelo 2B, a partir do Início do designer. Troque o perfil em "Ver como" no topo para ver o menu de cada papel.` })}
    <div class="corpo-modulo"><div class="mapa-mod">
      <section class="cartao bloco"><h2 class="titulo-bloco">Início</h2><ul><li><a href="#inicio">Início <small>fiel ao designer</small></a></li></ul></section>
      ${nomes.map((g) => `<section class="cartao bloco"><h2 class="titulo-bloco">${g}</h2><ul>${grupos[g].map(([k, nome, t]) => `<li><a href="#${k}${exemplo[k] ? '-' + exemplo[k] : ''}">${esc(nome)}${t.publica ? ' <small>sem login</small>' : ''}</a></li>`).join('')}</ul></section>`).join('')}
    </div><p class="demo">Dados de demonstração.</p></div>`;
  } };

  // ------------------------------------------------------------------ Ctrl+K: telas, pessoas, Reuniões, fila e ações
  const norm = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const original = N.resultadosBusca;
  N.resultadosBusca = function (txt) {
    const r = original(txt);
    const t = norm(txt.trim());
    if (!t) return r;
    const telas = Object.entries(T).filter(([, x]) => x.mapa && !x.publica && norm(x.mapa.join(' ')).includes(t)).slice(0, 6).map(([k, x]) => ({ href: '#' + k, t: x.mapa[1], s: x.mapa[0] }));
    const pessoas = N.pessoas.filter((p) => norm(p.nome + ' ' + p.setor).includes(t)).slice(0, 4).map((p) => ({ href: '#pessoa-' + p.id, t: p.nome, s: p.cargo }));
    const reus = reunioes.filter((x) => norm(x.titulo).includes(t)).slice(0, 4).map((x) => ({ href: '#reuniao-' + x.id, t: x.titulo, s: fmt(deIso(x.data)) + ', ' + x.hora }));
    const vistos = new Set(r.telas.map((x) => x.href));
    r.telas = [...r.telas, ...telas.filter((x) => !vistos.has(x.href))];
    r.fila = [...r.fila, ...pessoas, ...reus];
    return r;
  };
})();
