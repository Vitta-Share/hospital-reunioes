/* Reuniões e metas: a lista de Reuniões, a Reunião por estado, a Ata Guiada, o Dashboard e as Definições de processo. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I, IC, dia, fmt, curto, est, reunioes, deIso, difDias, HOJE, iso } = N;
  const T = N.telas;
  const PEND = N.PEND || [];
  N.css('.faixa-verde{display:flex;gap:8px;align-items:flex-start;margin:0 0 10px;padding:10px 12px;border-radius:8px;background:#E3F4EA;color:var(--verde);font-weight:700;font-size:13.5px;line-height:1.35}.faixa-verde svg{flex:none;margin-top:1px}');
  est.rm = { aba: {}, busca: '', estados: [], chipPapel: 'todas', periodo: '90', tirados: {}, estado: {}, sig: {}, resolvidos: {}, guiada: {} };

  // ------------------------------------------------------------------ dados extras: Reuniões em outros estados
  const EXTRA = [
    { id: 'rv', off: -1, hora: '10:00', titulo: 'Comissão de Farmácia e Terapêutica', papel: 'facilitador', ata: 'Ata pronta para validar',
      participantes: ['Renata Alves', 'Rodrigo Sales', 'Carla Nogueira', 'Fernanda Lima'], pauta: ['Padronização de antimicrobianos', 'Desabastecimento de dipirona injetável'] },
    { id: 'rr', off: -2, hora: '15:30', titulo: 'Reunião do Centro Cirúrgico', papel: 'facilitador', ata: 'Faltam nomes para casar',
      participantes: ['Renata Alves', 'Paulo Mendes', 'Carla Nogueira'], pauta: ['Atraso no primeiro tempo cirúrgico', 'EPIs do Centro Cirúrgico'] },
    { id: 'rh', off: -4, hora: '11:00', titulo: 'Reunião de Hotelaria', papel: 'participante', facil: 'Juliana Prado', ata: 'Aguardando a sua assinatura',
      participantes: ['Juliana Prado', 'Renata Alves', 'Paulo Mendes', 'Carla Nogueira'], pauta: ['Troca do enxoval da ala B', 'Contrato da lavanderia'] },
    { id: 'ra', off: -2, hora: '07:30', titulo: 'Passagem de plantão da UTI', papel: 'facilitador', ata: 'Aprovada sem assinatura', guiada: true,
      participantes: ['Renata Alves', 'Carla Nogueira', 'Fernanda Lima'], pauta: ['Leitos bloqueados', 'Pacientes em isolamento'] }
  ];
  EXTRA.forEach((r) => { if (!reunioes.find((x) => x.id === r.id)) reunioes.push({ ...r, data: iso(dia(r.off)) }); });

  const ESTADO_INICIAL = { r0: 'ASSINADA', rm1: 'AGUARDANDO_ASSINATURA', rv: 'AGUARDANDO_VALIDACAO', rr: 'AGUARDANDO_RESOLUCAO', rh: 'AGUARDANDO_ASSINATURA', ra: 'APROVADA' };
  const estadoDe = (r) => est.rm.estado[r.id] || ESTADO_INICIAL[r.id] || (difDias(deIso(r.data)) >= 0 ? 'PROGRAMADA' : 'PROGRAMADA');
  const NOME = { PROGRAMADA: ['pill', 'Programada'], PROCESSANDO: ['pill laranja', 'Processando a Ata'], AGUARDANDO_RESOLUCAO: ['pill laranja', 'Resolução de nomes'],
    AGUARDANDO_VALIDACAO: ['pill laranja', 'Ata para validar'], CORRIGINDO: ['pill laranja', 'Corrigindo a Ata'], AGUARDANDO_ASSINATURA: ['pill laranja', 'Aguardando assinatura'],
    ASSINADA: ['pill verde', 'Assinada'], APROVADA: ['pill verde', 'Aprovada'], CANCELADA: ['pill cinza', 'Desmarcada'], ERRO: ['pill verm', 'Erro na Ata'] };
  const facil = (r) => r.facil || (r.papel === 'facilitador' ? 'Renata Alves' : r.participantes[0]);
  const souSecretaria = () => N.perfil() === 'secretaria';
  const conduzo = (r) => r.papel === 'facilitador' && !souSecretaria();
  const reu = (id) => reunioes.find((r) => r.id === id);

  const SIG_INICIAL = { r0: ['Renata Alves', 'Carla Nogueira', 'Rodrigo Sales', 'Paulo Mendes', 'Juliana Prado'], rm1: ['Fernanda Lima', 'Carla Nogueira', 'Rodrigo Sales'], rh: ['Juliana Prado', 'Carla Nogueira'] };
  // Quando cada Signatário assinou: [dias depois da Reunião, hora]. A última assinatura fecha a Ata.
  const SIG_QUANDO = {
    r0: { 'Renata Alves': [0, '17:12'], 'Carla Nogueira': [1, '08:40'], 'Rodrigo Sales': [1, '14:05'], 'Paulo Mendes': [2, '09:31'], 'Juliana Prado': [2, '16:48'] },
    rm1: { 'Fernanda Lima': [0, '18:02'], 'Carla Nogueira': [1, '10:15'], 'Rodrigo Sales': [3, '11:47'] },
    rh: { 'Juliana Prado': [0, '13:20'], 'Carla Nogueira': [1, '09:05'] }
  };
  const APROVADA_EM = { ra: [0, '09:10'] };
  const INFO = { r0: ['Diretoria', 'Diretoria Assistencial, quinzenal', 'Acompanhar escalas, insumos e indicadores da Diretoria Assistencial.'],
    r1: ['Diretoria', 'Diretoria Assistencial, quinzenal', 'Acompanhar escalas, insumos e indicadores da Diretoria Assistencial.'],
    r5: ['Diretoria', 'Diretoria Assistencial, quinzenal', 'Fechamento do mês da Diretoria Assistencial.'],
    rm1: ['Comissão', '', 'Indicadores de infecção e campanhas da CCIH.'], r2: ['Comissão', '', 'Resultado da ronda de higienização e protocolo de isolamento.'],
    r3: ['Comissão', '', 'Preparação para a acreditação.'], r4: ['Núcleo', '', 'Indicadores de queda e notificações do mês.'],
    rv: ['Comissão', '', 'Padronização de medicamentos.'], rr: ['Operacional', '', 'Primeiro tempo cirúrgico e EPIs.'], rh: ['Operacional', '', 'Enxoval e lavanderia.'], ra: ['Operacional', '', 'Passagem de plantão da UTI.'] };
  const dataHora = (r, d) => { const x = deIso(r.data); x.setDate(x.getDate() + d[0]); return `${fmt(x)} às ${d[1]}`; };
  N.quandoAssinou = (r, nome) => { if (est.rm.agora && est.rm.agora[r.id + nome]) return est.rm.agora[r.id + nome]; const q = (SIG_QUANDO[r.id] || {})[nome]; return q ? dataHora(r, q) : ''; };
  const ultimaAssinatura = (r) => { const nomes = est.rm.sig[r.id] || SIG_INICIAL[r.id] || []; const ds = nomes.map((n) => N.quandoAssinou(r, n)).filter(Boolean);
    const ord = ds.map((t) => { const [d, h] = t.split(' às '); const [dd, mm, aa] = d.split('/'); return [aa + mm + dd + h, t]; }).sort((a, b) => a[0].localeCompare(b[0])); return ord.length ? ord[ord.length - 1][1] : ''; };
  // Uma linha para o calendário, a gaveta e a página: o que aconteceu com a Ata e quando.
  N.infoAssinatura = (r) => { const e = estadoDe(r), n = (est.rm.sig[r.id] || SIG_INICIAL[r.id] || []).length;
    if (e === 'ASSINADA') return `Assinada por todos em ${ultimaAssinatura(r)}, pela ClickSign`;
    if (e === 'AGUARDANDO_ASSINATURA') return `${n} de ${r.participantes.length} assinaram${n ? `, a última em ${ultimaAssinatura(r)}` : ''}`;
    if (e === 'APROVADA') return APROVADA_EM[r.id] ? `Aprovada sem assinatura em ${dataHora(r, APROVADA_EM[r.id])}` : 'Aprovada sem assinatura';
    return NOME[e] ? NOME[e][1] : esc(r.ata); };
  N.estadoReuniao = (r) => estadoDe(r);
  const assinou = (r, nome) => (est.rm.sig[r.id] || SIG_INICIAL[r.id] || []).includes(nome);
  const faltaMinha = (r) => estadoDe(r) === 'AGUARDANDO_ASSINATURA' && r.participantes.includes('Renata Alves') && !assinou(r, 'Renata Alves');

  // O que pede alguma coisa da Renata nesta Reunião, em uma frase e um botão.
  function pedido(r) {
    const e = estadoDe(r);
    if (souSecretaria()) return e === 'PROGRAMADA' ? ['Editar', `#reuniao-${r.id}`] : ['Abrir', `#reuniao-${r.id}`];
    if (e === 'AGUARDANDO_VALIDACAO' && conduzo(r)) return ['Validar a Ata', `#reuniao-${r.id}`, true];
    if (e === 'AGUARDANDO_RESOLUCAO' && conduzo(r)) return ['Casar os nomes', `#reuniao-${r.id}`, true];
    if (faltaMinha(r)) return ['Assinar a Ata', `#reuniao-${r.id}`, true];
    if (e === 'PROGRAMADA' && conduzo(r) && difDias(deIso(r.data)) === 0) return ['Começar a Ata', `#ataguiada-${r.id}`, true];
    return ['Abrir', `#reuniao-${r.id}`];
  }

  N.css(`
    .datinha{display:flex;flex-direction:column;align-items:center;justify-content:center;width:64px;height:58px;border-radius:10px;background:var(--suave);color:var(--titulo);line-height:1.1}
    .datinha b{font-size:21px;font-variant-numeric:tabular-nums}
    .datinha small{font-size:11.5px;color:var(--texto2);text-transform:uppercase;letter-spacing:.04em}
    .datinha.hoje{background:var(--btn-fundo);color:#fff}.datinha.hoje small{color:rgba(255,255,255,.8)}
    .linha-reu{grid-template-columns:72px minmax(0,1fr) 120px 170px 150px !important;gap:16px}
    .grupo-tit{margin:18px 0 2px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--texto2);display:flex;align-items:center;gap:8px}
    .grupo-tit .n{min-width:20px;height:20px;padding:0 6px;border-radius:999px;background:var(--suave2);color:var(--titulo);font-size:11.5px;display:inline-flex;align-items:center;justify-content:center}
    .abas-int{display:flex;flex-wrap:wrap;gap:2px;border-bottom:1px solid var(--borda);margin:0 0 14px}
    .abas-int button{min-height:44px;padding:0 14px;border:0;border-bottom:3px solid transparent;margin-bottom:-1px;background:transparent;color:var(--texto2);font-size:14px;cursor:pointer}
    .abas-int button:hover{color:var(--titulo)}
    .abas-int button[aria-selected="true"]{border-bottom-color:var(--titulo);color:var(--titulo);font-weight:700}
    .agora-card{border:1px solid var(--titulo);box-shadow:var(--sombra-alta)}
    .agora-card .titulo-bloco{font-size:16px}
    .agora-card .btn{width:100%}
    .acoes-col{display:flex;flex-direction:column;gap:8px;margin-top:14px}
    .nome-res{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid var(--linha)}
    .nome-res:last-child{border-bottom:0}
    .nome-res select{min-height:42px;padding:0 10px;border:1px solid var(--campo-borda);border-radius:8px;background:var(--campo);color:var(--texto);width:100%}
    .guiada-barra{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:12px clamp(16px,2.4vw,36px);background:var(--cartao);border-bottom:1px solid var(--borda);box-shadow:var(--sombra)}
    .guiada-barra h1{margin:0;font-size:19px;color:var(--titulo)}
    .guiada{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(340px,1fr);gap:14px;padding:18px clamp(16px,2.4vw,36px) 40px;align-items:start}
    .guiada .chat{position:sticky;top:76px;display:flex;flex-direction:column;height:calc(100vh - 150px);min-height:460px}
    .guiada .chat .conversa{flex:1;overflow:auto;padding:4px 2px 10px}
    .apontar{border:1px dashed var(--campo-borda);background:transparent;border-radius:7px;color:var(--texto2);font-size:12.5px;min-height:30px;padding:0 10px;cursor:pointer}
    .apontar:hover,.apontar[aria-pressed="true"]{border-color:var(--acento);color:var(--acento);background:var(--suave)}
    .sec-viva{padding:14px;border-radius:10px;border:1px solid var(--linha);transition:background-color .4s ease}
    .sec-viva.mexeu{background:var(--suave)}
    .respostas{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
    .resp-rapida{display:inline-flex;align-items:center;min-height:34px;padding:0 12px;border:1px solid var(--campo-borda);border-radius:999px;background:var(--cartao);color:var(--titulo);font-size:13px;cursor:pointer}.resp-rapida:hover{background:var(--suave);border-color:var(--acento)}
    .barra-setor{display:grid;grid-template-columns:150px minmax(0,1fr) 90px;gap:12px;align-items:center;padding:8px 6px;border-radius:8px;text-decoration:none;color:var(--texto)}
    .barra-setor:hover{background:var(--suave);color:var(--texto)}
    .barra-setor .trilho{display:flex;height:12px;border-radius:999px;overflow:hidden;background:var(--suave2)}
    .barra-setor .trilho span{display:block;height:100%}
    .var-sem{display:block;font-size:12.5px;margin-top:2px;color:var(--texto2)}
    .var-sem.bom{color:var(--verde)}.var-sem.ruim{color:var(--verm)}
    .citacao{margin:10px 0 0;padding:10px 14px;border-left:3px solid var(--heroi-risco);background:var(--suave);border-radius:0 8px 8px 0;font-size:14.5px;color:var(--texto)}
    @media (max-width:1100px){.linha-reu{grid-template-columns:64px minmax(0,1fr) 150px !important}.linha-reu .x-papel,.linha-reu .x-est{display:none}.guiada{grid-template-columns:1fr}.guiada .chat{position:static;height:auto}}
  `);

  // ------------------------------------------------------------------ lista de Reuniões
  function precisa(r) { const p = pedido(r); return !!p[2]; }
  // Categoria do estado para o filtro: Programadas, Ata em andamento, Assinadas e aprovadas, Desmarcadas ou com erro.
  function catEst(e) { return e === 'PROGRAMADA' ? 'programadas' : /AGUARDANDO|PROCESSANDO|CORRIGINDO/.test(e) ? 'ata' : /ASSINADA|APROVADA/.test(e) ? 'fechadas' : 'outras'; }
  function linhaReu(r) {
    const d = deIso(r.data); const hoje = difDias(d) === 0;
    const [cls, txt] = NOME[estadoDe(r)]; const [rot, href, forte] = pedido(r);
    const MES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
    return `<li class="linha linha-reu entra">
      <span class="datinha${hoje ? ' hoje' : ''}"><b>${d.getDate()}</b><small>${hoje ? 'hoje' : MES[d.getMonth()]}</small></span>
      <span class="t"><a href="#reuniao-${r.id}" data-previa="${N.previaReuniao(r)}" style="color:var(--texto);text-decoration:none;font-weight:700">${esc(r.titulo)}</a><small>${r.hora} · ${conduzo(r) ? 'Você conduz' : 'Conduz: ' + esc(facil(r))} · ${r.participantes.length} Participantes</small></span>
      <span class="x-papel"><span class="pill ${conduzo(r) ? 'escuro' : ''}">${souSecretaria() ? N.ini(facil(r)) + ', Facilitador' : conduzo(r) ? 'Conduzo' : 'Participo'}</span></span>
      <span class="x-est"><span class="${cls}">${txt}</span></span>
      <a class="btn${forte ? '' : ' contorno'}" href="${href}">${rot}</a>
    </li>`;
  }
  T.reunioes = { trilha: 'Reuniões', menu: 'reunioes', mapa: ['Reuniões e metas', 'Reuniões'], render() {
    const t = est.rm.busca.trim().toLowerCase();
    const todas = reunioes.filter((r) => !t || (r.titulo + ' ' + r.participantes.join(' ') + ' ' + r.pauta.join(' ')).toLowerCase().includes(t))
      .filter((r) => est.rm.chipPapel === 'todas' || (est.rm.chipPapel === 'conduzo' ? conduzo(r) : !conduzo(r)))
      .filter((r) => N.passa(est.rm.estados, catEst(estadoDe(r))));
    const ord = (a, b) => (a.data + a.hora).localeCompare(b.data + b.hora);
    const urg = todas.filter(precisa).sort(ord);
    const prox = todas.filter((r) => !precisa(r) && difDias(deIso(r.data)) >= 0).sort(ord);
    const pass = todas.filter((r) => !precisa(r) && difDias(deIso(r.data)) < 0).sort((a, b) => -ord(a, b));
    const grupo = (tit, lista, vazio) => `<p class="grupo-tit">${tit}<span class="n">${lista.length}</span></p>${lista.length ? `<ul class="linhas">${lista.map(linhaReu).join('')}</ul>` : `<p class="vazio">${vazio}</p>`}`;
    const CE = [['programadas', 'Programadas'], ['ata', 'Ata em andamento'], ['fechadas', 'Assinadas e aprovadas'], ['outras', 'Desmarcadas ou com erro']];
    const CP = [['todas', 'Todos os papéis'], ['conduzo', 'Conduzo'], ['participo', 'Participo']];
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas">
        <div class="filtros-linha">${N.filtro({ id: 'rm-estado', rotulo: 'Estado', opcoes: CE, multi: true, obj: 'rm', campo: 'estados', todos: 'Todos' })}${souSecretaria() ? '' : N.filtro({ id: 'rm-papel', rotulo: 'Papel', opcoes: CP, valor: est.rm.chipPapel, acao: 'rm-chip', dados: { g: 'chipPapel' } })}</div>
        <label class="busca-lista">${IC.busca}<span class="sr">Buscar Reunião</span><input id="rm-busca" data-digita="rm-busca" type="search" placeholder="Buscar por título, pauta ou Participante" value="${esc(est.rm.busca)}"></label>
      </div>
      ${todas.length ? grupo('Precisam de você', urg, 'Nada esperando você nas Reuniões. Bom sinal.') + grupo('Próximas', prox, 'Nenhuma Reunião marcada com esse filtro. Use Agendar Reunião para marcar a próxima.') + grupo('Já aconteceram', pass, 'Nenhuma Reunião passada com esse filtro.')
        : `<p class="vazio">Nenhuma Reunião encontrada com "${esc(est.rm.busca)}". Tente o nome de um Participante ou um item da pauta.</p>`}
    </section>`;
    const hoje = reunioes.filter((r) => difDias(deIso(r.data)) === 0);
    const semana = reunioes.filter((r) => { const n = difDias(deIso(r.data)); return n >= 0 && n <= 7; });
    const paradas = reunioes.filter((r) => /AGUARDANDO_VALIDACAO|AGUARDANDO_RESOLUCAO/.test(estadoDe(r)));
    const nUrg = reunioes.filter(precisa).length;
    const frase = nUrg ? `${nUrg === 1 ? 'Uma Reunião espera' : N.cap(N.ext(nUrg)) + ' Reuniões esperam'} uma ação sua. ${hoje.length ? `Hoje tem ${hoje.length === 1 ? 'uma' : hoje.length}, às ${hoje[0].hora}.` : ''}` : 'Nenhuma Reunião espera por você agora.';
    return N.modulo({ sobre: 'Reuniões e metas', titulo: 'Reuniões', frase,
      acoes: souSecretaria() ? `<a class="btn claro grande" href="#secretarianova">Marcar Reunião</a>` : `<button class="btn claro grande" data-acao="agendar">Agendar Reunião</button><a class="btn vidro grande" href="#calendario">Ver no Calendário</a>` },
    [['Precisam de você', String(nUrg).padStart(2, '0'), I.alerta, '#reunioes', nUrg > 0], ['Hoje', String(hoje.length).padStart(2, '0'), I.relogio, hoje[0] ? '#reuniao-' + hoje[0].id : '#reunioes'],
      ['Próximos 7 dias', String(semana.length).padStart(2, '0'), I.agenda, '#calendario'], ['Atas paradas', String(paradas.length).padStart(2, '0'), I.lista.replace('width="22" height="22"', 'width="26" height="26"'), '#dashboard']],
    '', corpo);
  } };
  N.digitar['rm-busca'] = (v) => { est.rm.busca = v; };
  N.acoes['rm-chip'] = (a) => { est.rm[a.dataset.g] = a.dataset.v; N.desenhar(); };

  // ------------------------------------------------------------------ a Ata de demonstração
  const QUADRO_EXTRA = {
    rv: [['Publicar a lista de antimicrobianos padronizados', 'Rodrigo Sales', 7, 'Ação'], ['Conferir o estoque de dipirona injetável', 'Rodrigo Sales', null, 'Rotina'], ['Pedido urgente à farmácia fora do horário', 'Carla Nogueira', null, 'Processo']],
    rr: [['Começar o primeiro tempo cirúrgico às 7h', 'Paulo (a casar)', 10, 'Ação'], ['Levantar os EPIs que faltam na sala 3', 'Carla do CC (a casar)', 5, 'Ação'], ['Ouvir a equipe de anestesia', 'Dr. Henrique (externo?)', 14, 'Ação']],
    rh: [['Trocar o enxoval da ala B', 'Juliana Prado', 6, 'Ação'], ['Renegociar o contrato da lavanderia', 'Paulo Mendes', 20, 'Ação']],
    ra: [['Liberar os 2 leitos bloqueados da UTI', 'Carla Nogueira', 1, 'Ação'], ['Conferir o isolamento de contato a cada plantão', 'Fernanda Lima', null, 'Rotina']],
    r1: [], r2: [], r3: [], r4: [], r5: []
  };
  function quadro(r) {
    const daPend = PEND.filter((p) => p.reu === r.id).map((p) => [p.t, p.resp, p.off, 'Ação']);
    return daPend.length ? daPend : (QUADRO_EXTRA[r.id] || []);
  }
  const RESUMO = {
    r0: 'A Diretoria Assistencial fechou as escalas de dezembro e cobrou a entrega dos EPIs do Centro Cirúrgico. Os indicadores de outubro ficaram dentro da meta, menos quedas, que subiram no 3º andar.',
    rm1: 'A Comissão revisou a taxa de infecção de corrente sanguínea, que caiu pelo segundo mês, e aprovou a nova campanha de higienização das mãos para dezembro.',
    rv: 'A Comissão aprovou a lista de antimicrobianos padronizados e definiu como lidar com a falta de dipirona injetável até o fornecedor normalizar.',
    rr: 'A reunião tratou do atraso no primeiro tempo cirúrgico, que passou de 40 minutos na média de novembro, e da falta de EPIs na sala 3.',
    rh: 'A Hotelaria apresentou o plano de troca do enxoval da ala B e o estudo para renegociar o contrato da lavanderia.',
    ra: 'Plantão com dois leitos bloqueados por manutenção e três pacientes em isolamento de contato.'
  };
  const RESOLVER = [
    { k: 'n1', citado: 'Paulo', opcoes: ['Paulo Mendes (Suprimentos)', 'Paulo Sérgio Dias (Manutenção)'] },
    { k: 'n2', citado: 'Carla do CC', opcoes: ['Carla Nogueira (Enfermagem)', 'Carla Menezes (Centro Cirúrgico)'] },
    { k: 'n3', citado: 'Dr. Henrique', opcoes: [] }
  ];

  function etapas(r) {
    const e = estadoDe(r);
    const guiada = r.guiada || est.rm.guiada[r.id + 'feita'];
    const passos = guiada || e === 'APROVADA'
      ? [['PROGRAMADA', 'Programada'], ['GUIADA', guiada ? 'Ata Guiada' : 'Transcrição'], ['AGUARDANDO_VALIDACAO', 'Validação'], ['APROVADA', 'Aprovada']]
      : [['PROGRAMADA', 'Programada'], ['PROCESSANDO', 'Processando'], ['AGUARDANDO_RESOLUCAO', 'Resolução de nomes'], ['AGUARDANDO_VALIDACAO', 'Validação'], ['AGUARDANDO_ASSINATURA', 'Assinaturas'], ['ASSINADA', 'Assinada']];
    const ordem = passos.map((p) => p[0]);
    let i = ordem.indexOf(e === 'CORRIGINDO' ? 'AGUARDANDO_VALIDACAO' : e);
    if (e === 'APROVADA') i = ordem.length - 1;
    const fim = e === 'ASSINADA' || e === 'APROVADA';
    return `<ol class="etapas" aria-label="Caminho da Ata">${passos.map(([, t], n) => `<li class="${n < i || (fim && n === i) ? 'feito' : n === i ? 'agora' : ''}">${t}</li>`).join('')}</ol>`;
  }

  // ------------------------------------------------------------------ "O que fazer agora" por estado
  function agora(r) {
    const e = estadoDe(r);
    const card = (tit, txt, botoes) => `<section class="cartao bloco agora-card"><p class="rot-mini" style="margin:0">O que fazer agora</p><h2 class="titulo-bloco" style="margin-top:6px">${tit}</h2><p class="sub" style="margin:6px 0 0">${txt}</p><div class="acoes-col">${botoes}</div></section>`;
    if (e === 'CANCELADA') return card('Reunião desmarcada', 'Os Participantes foram avisados. Nada mais a fazer aqui.', `<button class="btn" data-acao="agendar">Agendar outra</button>`);
    if (souSecretaria()) return card(e === 'PROGRAMADA' ? 'Ajustar a agenda' : 'A Ata é do Facilitador', e === 'PROGRAMADA' ? `Você pode mudar data, hora, pauta e Participantes. A Ata fica com ${esc(facil(r))}.` : 'A Secretária não vê a Ata nem as Pendências.',
      e === 'PROGRAMADA' ? `<button class="btn" data-acao="rm-editar" data-id="${r.id}">Editar a Reunião</button><button class="btn contorno" data-acao="rm-part" data-id="${r.id}">Incluir Participante</button><button class="btn contorno" data-acao="rm-desmarcar" data-id="${r.id}" style="color:var(--verm)">Desmarcar</button>` : '');
    if (!conduzo(r)) {
      if (faltaMinha(r)) return card('Falta a sua assinatura', `${esc(facil(r))} enviou a Ata. ${(est.rm.sig[r.id] || SIG_INICIAL[r.id] || []).length} de ${r.participantes.length} já assinaram.`, `<button class="btn" data-acao="rm-assinar" data-id="${r.id}">Assinar a Ata</button><button class="btn contorno" data-acao="rm-aba" data-id="${r.id}" data-v="resumo">Ler antes de assinar</button>`);
      return card('Nada para você agora', e === 'PROGRAMADA' ? `Quem conduz é ${esc(facil(r))}. A Ata chega para você depois da Reunião.` : 'A Ata seguiu. As Pendências no seu nome aparecem no Início.', `<a class="btn contorno" href="#inicio">Ir para o Início</a>`);
    }
    if (e === 'PROGRAMADA') return card(difDias(deIso(r.data)) === 0 ? `Hoje, às ${r.hora}` : `Em ${N.quando(deIso(r.data))}, às ${r.hora}`, 'Monte a Ata conversando, durante ou logo depois da Reunião. Se ela foi gravada, envie a Transcrição.',
      `<a class="btn" href="#ataguiada-${r.id}">${IC.microfone}Começar a Ata Guiada</a><button class="btn contorno" data-acao="rm-transcricao" data-id="${r.id}">Enviar a Transcrição</button><button class="btn contorno" data-acao="rm-editar" data-id="${r.id}">Editar a Reunião</button><button class="btn contorno" data-acao="rm-desmarcar" data-id="${r.id}" style="color:var(--verm)">Desmarcar</button>`);
    if (e === 'PROCESSANDO') return card('A IA está montando a Ata', 'Leva um ou dois minutos. Esta tela atualiza sozinha quando terminar.', `<span class="estado e-hoje"><i aria-hidden="true"></i>Processando a Transcrição</span>`);
    if (e === 'AGUARDANDO_RESOLUCAO') return card('Três nomes não casaram com o cadastro', 'Diga quem é cada um para a Pendência nascer no nome certo. Quem não está no cadastro fica como externo, sem cobrança.', `<button class="btn" data-acao="rm-aba" data-id="${r.id}" data-v="resolucao">Casar os nomes</button>`);
    if (e === 'AGUARDANDO_VALIDACAO' || e === 'CORRIGINDO') return card('A Ata está pronta para você validar', 'Leia o Resumo e o Quadro de atribuições. Depois escolha: assinatura digital ou finalizar sem assinatura.',
      `<button class="btn" data-acao="rm-enviar" data-id="${r.id}">Enviar para assinatura</button><button class="btn contorno" data-acao="rm-aprovar" data-id="${r.id}">Finalizar sem assinatura</button><button class="btn contorno" data-acao="rm-corrigir" data-id="${r.id}">${IC.lapis}Pedir correção</button>`);
    if (e === 'AGUARDANDO_ASSINATURA') { const n = (est.rm.sig[r.id] || SIG_INICIAL[r.id] || []).length;
      return card(`${n} de ${r.participantes.length} assinaram`, 'A Ata está na ClickSign. As Pendências nascem quando a última assinatura chegar.', `${faltaMinha(r) ? `<button class="btn" data-acao="rm-assinar" data-id="${r.id}">Assinar a Ata</button>` : `<button class="btn" data-acao="rm-lembrar" data-id="${r.id}">Lembrar quem falta</button>`}<button class="btn contorno" data-acao="rm-aba" data-id="${r.id}" data-v="signatarios">Ver os Signatários</button>`); }
    const daPend = PEND.filter((p) => p.reu === r.id);
    const abertas = daPend.length ? daPend.filter((p) => p.sit !== 'concluida').length : quadro(r).filter((q) => q[3] === 'Ação').length;
    return card(e === 'ASSINADA' ? 'Ata assinada por todos' : 'Ata aprovada sem assinatura', `<span class="faixa-verde">${IC.escudo}<span>${N.infoAssinatura(r)}.</span></span>${abertas ? `${abertas === 1 ? 'Uma Pendência desta Reunião segue aberta' : N.cap(N.ext(abertas)) + ' Pendências desta Reunião seguem abertas'}.` : 'Todas as Pendências desta Reunião foram entregues.'}`,
      `<a class="btn" href="#pendencias">Ver as Pendências</a><button class="btn contorno" data-acao="toast" data-msg="No sistema, baixa o PDF ${e === 'ASSINADA' ? 'assinado' : 'da Ata'}.">${IC.baixar}${e === 'ASSINADA' ? 'PDF assinado' : 'Baixar o PDF'}</button><button class="btn contorno" data-acao="agendar">Agendar a próxima</button>`);
  }

  // ------------------------------------------------------------------ seções da Ata (abas internas)
  function secoes(r) {
    const e = estadoDe(r);
    const temAta = !/PROGRAMADA|PROCESSANDO|CANCELADA/.test(e);
    const ABAS = temAta ? [['resumo', 'Resumo'], ['pauta', 'Pauta e discussão'], ['quadro', 'Quadro de atribuições'], ['participantes', 'Participantes']] : [['pauta', 'Pauta'], ['participantes', 'Participantes']];
    if (e === 'AGUARDANDO_RESOLUCAO') ABAS.unshift(['resolucao', 'Resolução de nomes']);
    if (/AGUARDANDO_ASSINATURA|ASSINADA/.test(e)) ABAS.push(['signatarios', 'Signatários']);
    let aba = est.rm.aba[r.id];
    if (!ABAS.find((a) => a[0] === aba)) aba = ABAS[0][0];
    if (souSecretaria() && temAta) return `<p class="aviso">${I.info}A Ata e as Pendências ficam com o Facilitador. Você vê a pauta e os Participantes.</p>${conteudo(r, 'participantes')}`;
    return `<div class="abas-int" role="tablist">${ABAS.map(([k, t]) => `<button type="button" role="tab" aria-selected="${aba === k}" data-acao="rm-aba" data-id="${r.id}" data-v="${k}">${t}</button>`).join('')}</div><div role="tabpanel">${conteudo(r, aba)}</div>`;
  }
  function conteudo(r, aba) {
    const e = estadoDe(r);
    if (aba === 'resumo') return `<p style="margin:0;max-width:72ch;font-size:15.5px">${esc(RESUMO[r.id] || 'Resumo da Reunião.')}</p>
      <dl class="ficha"><div><dt>Decisões</dt><dd class="num">${r.pauta.length}</dd></div><div><dt>Itens no Quadro</dt><dd class="num">${quadro(r).length}</dd></div><div><dt>Participantes</dt><dd class="num">${r.participantes.length}</dd></div></dl>`;
    if (aba === 'pauta') return `<ol style="margin:0;padding-left:20px;display:flex;flex-direction:column;gap:12px">${r.pauta.map((p, n) => `<li><b style="color:var(--titulo)">${esc(p)}</b>${/PROGRAMADA/.test(e) ? '' : `<p class="sub" style="margin:4px 0 0;font-size:14.5px">${n === 0 ? 'Ficou decidido seguir com a proposta apresentada, com revisão em 30 dias.' : 'O grupo pediu o levantamento antes de decidir. Volta na próxima Reunião.'}</p>`}</li>`).join('')}</ol>
      ${/PROGRAMADA/.test(e) && conduzo(r) && !souSecretaria() ? `<button class="btn contorno" style="margin-top:14px" data-acao="rm-editar" data-id="${r.id}">${IC.mais}Incluir item na pauta</button>` : ''}`;
    if (aba === 'quadro') { const q = quadro(r);
      return q.length ? `<div class="tabela-rola"><table class="tab"><thead><tr><th>Ação</th><th>Responsável</th><th>Prazo</th><th>Tipo</th></tr></thead><tbody>${q.map(([a, resp, off, tipo]) => `<tr><td>${esc(a)}</td><td>${/a casar|externo/.test(resp) ? `<span class="pill laranja">${esc(resp)}</span>` : esc(resp)}</td><td class="num">${off === null ? 'Sem prazo' : fmt(dia(off))}</td><td><span class="pill">${tipo}</span></td></tr>`).join('')}</tbody></table></div>
        ${e === 'AGUARDANDO_VALIDACAO' ? `<p class="aviso">${I.info}As Pendências nascem quando você enviar para assinatura (na última assinatura) ou finalizar sem assinatura (na hora).</p>` : ''}` : '<p class="vazio">Nenhuma ação registrada nesta Ata.</p>'; }
    if (aba === 'participantes') return `<ul class="linhas">${r.participantes.map((n) => `<li class="linha" style="grid-template-columns:42px minmax(0,1fr) auto"><span class="ini" style="width:36px;height:36px;border-radius:999px;background:var(--suave2);color:var(--titulo);display:inline-flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:700">${N.ini(n)}</span><span class="t">${esc(n)}${n === 'Renata Alves' ? ' (você)' : ''}<small>${n === facil(r) ? 'Facilitador' : 'Participante'}</small></span>${e === 'PROGRAMADA' && conduzo(r) && n !== 'Renata Alves' ? `<button class="btn contorno" data-acao="rm-tirar" data-id="${r.id}" data-nome="${esc(n)}">Tirar</button>` : ''}</li>`).join('')}</ul>
      ${e === 'PROGRAMADA' && (conduzo(r) || souSecretaria()) ? `<button class="btn contorno" style="margin-top:12px" data-acao="rm-part" data-id="${r.id}">${IC.mais}Incluir Participante</button>` : ''}`;
    if (aba === 'signatarios') return `<ul class="linhas">${r.participantes.map((n) => { const ok = assinou(r, n); return `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto auto"><span class="t">${esc(n)}${n === 'Renata Alves' ? ' (você)' : ''}</span>${N.estado(ok ? 'e-ok' : 'e-hoje', ok ? `Assinou em ${N.quandoAssinou(r, n) || 'data não registrada'}` : 'Falta assinar')}${!ok && n !== 'Renata Alves' && e === 'AGUARDANDO_ASSINATURA' && conduzo(r) ? `<button class="btn contorno" data-acao="toast" data-msg="Lembrete enviado para ${esc(n.split(' ')[0])} pela ClickSign.">Lembrar</button>` : '<span></span>'}</li>`; }).join('')}</ul>`;
    if (aba === 'resolucao') return `<p class="sub" style="margin:0 0 6px">A IA encontrou estes nomes na Transcrição e não teve certeza de quem são.</p>
      ${RESOLVER.map((x) => `<div class="nome-res"><span><b style="color:var(--titulo)">"${esc(x.citado)}"</b><span class="sub" style="display:block">citado no Quadro de atribuições</span></span>
        <label><span class="sr">Quem é ${esc(x.citado)}</span><select data-res="${x.k}">${x.opcoes.map((o) => `<option>${esc(o)}</option>`).join('')}<option>Externo, só o nome (sem cobrança)</option><option>Ignorar este nome</option></select></label></div>`).join('')}
      <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap"><button class="btn grande" data-acao="rm-resolver" data-id="${r.id}">Confirmar e seguir para a validação</button></div>`;
    return '';
  }

  // ------------------------------------------------------------------ a Reunião
  T.reuniao = { trilha: 'Reuniões', menu: 'reunioes', mapa: ['Reuniões e metas', 'Reunião (por estado)'], render(id) {
    const r = reu(id);
    if (!r) return `<div class="pagina"><a class="voltar" href="#reunioes">${I.voltar}Voltar às Reuniões</a><h1 class="pagina-titulo">Não encontramos essa Reunião.</h1><p class="pagina-sub">Ela pode ter sido desmarcada. <a href="#reunioes">Ver todas as Reuniões</a></p></div>`;
    const e = estadoDe(r); const [cls, txt] = NOME[e];
    return `<div class="pagina">
      <a class="voltar" href="#reunioes">${I.voltar}Voltar às Reuniões</a>
      <section class="cartao bloco" style="padding:22px 24px">
        <div class="cab"><div style="display:flex;gap:8px;flex-wrap:wrap"><span class="${cls}">${txt}</span>${r.guiada || est.rm.guiada[r.id + 'feita'] ? '<span class="pill cinza">Ata Guiada</span>' : ''}</div>
          ${!/PROGRAMADA|CANCELADA/.test(e) && !souSecretaria() ? `<button class="btn contorno" data-acao="toast" data-msg="No sistema, baixa o PDF da Ata.">${IC.baixar}PDF da Ata</button>` : ''}</div>
        <h1 class="pagina-titulo" style="margin-top:10px">${esc(r.titulo)}</h1>
        <p class="pagina-sub">${N.longo(deIso(r.data))}, ${r.hora} · ${conduzo(r) ? 'Você conduz esta Reunião' : 'Conduz: ' + esc(facil(r))}</p>
        <div style="margin-top:18px">${etapas(r)}</div>
      </section>
      <div class="duas" style="margin-top:14px">
        <section class="cartao bloco larga">${secoes(r)}</section>
        <aside class="estreita">${agora(r)}
          <section class="cartao bloco"><h2 class="titulo-bloco" style="font-size:15px">Sobre a Reunião</h2>
            <dl class="pares" style="margin-top:10px"><dt>Quando</dt><dd>${curto(deIso(r.data))}, ${r.hora}</dd><dt>Facilitador</dt><dd>${esc(facil(r))}</dd><dt>Participantes</dt><dd>${r.participantes.length} pessoas</dd><dt>Pendências</dt><dd>${/ASSINADA|APROVADA/.test(e) ? (PEND.filter((p) => p.reu === r.id).length || quadro(r).length) + ' geradas' : /PROGRAMADA|PROCESSANDO|CANCELADA/.test(e) ? 'nascem da Ata' : quadro(r).length + ' no Quadro, ainda não nasceram'}</dd></dl>
          </section>
        </aside>
      </div>
    </div>`;
  } };
  N.acoes['rm-aba'] = (a) => { est.rm.aba[a.dataset.id] = a.dataset.v; N.desenhar(); };

  // ações da Reunião
  const set = (id, e, msg) => { est.rm.estado[id] = e; N.fecharModal(); N.desenhar(); if (msg) N.aviso(msg); };
  N.acoes['rm-resolver'] = (a) => set(a.dataset.id, 'AGUARDANDO_VALIDACAO', 'Nomes casados. A Ata está pronta para você validar.');
  N.acoes['rm-enviar'] = (a) => N.modal('Enviar para assinatura', `<p class="sub" style="margin:0">A Ata vai para a ClickSign e cada Participante recebe o link por e-mail. As Pendências nascem quando a última assinatura chegar.</p>`, `<button type="button" class="btn" data-acao="rm-enviar-ok" data-id="${a.dataset.id}">Enviar</button>`);
  N.acoes['rm-enviar-ok'] = (a) => { est.rm.sig[a.dataset.id] = []; set(a.dataset.id, 'AGUARDANDO_ASSINATURA', 'Ata enviada para assinatura.'); };
  N.acoes['rm-aprovar'] = (a) => N.modal('Finalizar sem assinatura', `<p class="sub" style="margin:0">A Ata fica APROVADA e as Pendências nascem agora. Depois não dá para pedir assinatura desta Ata.</p>`, `<button type="button" class="btn" data-acao="rm-aprovar-ok" data-id="${a.dataset.id}">Finalizar sem assinatura</button>`);
  N.acoes['rm-aprovar-ok'] = (a) => set(a.dataset.id, 'APROVADA', 'Ata aprovada. As Pendências já estão com os responsáveis.');
  N.acoes['rm-corrigir'] = (a) => N.modal('Pedir correção', `<div class="campo"><label for="rm-sec">Qual parte</label><select id="rm-sec"><option>Resumo</option><option>Pauta e discussão</option><option>Quadro de atribuições</option><option>Participantes</option></select></div>
    <div class="campo" style="margin-top:12px"><label for="rm-pedido">O que está errado</label><textarea id="rm-pedido" placeholder="Ex.: o prazo da escala é 05/12, não 30/11"></textarea></div>`, `<button type="button" class="btn" data-acao="rm-corrigir-ok" data-id="${a.dataset.id}">Pedir correção</button>`);
  N.acoes['rm-corrigir-ok'] = (a) => { set(a.dataset.id, 'CORRIGINDO', 'A IA está corrigindo a parte apontada.'); setTimeout(() => { est.rm.estado[a.dataset.id] = 'AGUARDANDO_VALIDACAO'; N.desenhar(); N.aviso('Correção feita. Confira e valide.'); }, 2200); };
  N.acoes['rm-assinar'] = (a) => N.modal('Assinar a Ata', `<p class="sub" style="margin:0">Você vai para a ClickSign assinar com o seu e-mail. Leva menos de um minuto.</p>`, `<button type="button" class="btn" data-acao="rm-assinar-ok" data-id="${a.dataset.id}">Assinar agora</button>`);
  N.acoes['rm-assinar-ok'] = (a) => { const r = reu(a.dataset.id); est.rm.sig[r.id] = [...(est.rm.sig[r.id] || SIG_INICIAL[r.id] || []), 'Renata Alves'];
    const agora = new Date(); est.rm.agora = est.rm.agora || {}; est.rm.agora[r.id + 'Renata Alves'] = `${fmt(HOJE)} às ${String(agora.getHours()).padStart(2, '0')}:${String(agora.getMinutes()).padStart(2, '0')}`;
    const todos = r.participantes.every((n) => assinou(r, n)); set(r.id, todos ? 'ASSINADA' : 'AGUARDANDO_ASSINATURA', todos ? 'Assinatura registrada. A Ata está assinada por todos.' : 'Assinatura registrada.'); };
  N.acoes['rm-lembrar'] = (a) => { const r = reu(a.dataset.id); const faltam = r.participantes.filter((n) => !assinou(r, n)); N.aviso(`Lembrete enviado para ${faltam.map((n) => n.split(' ')[0]).join(', ')}.`); };
  N.acoes['rm-desmarcar'] = (a) => N.modal('Desmarcar a Reunião', `<p class="sub" style="margin:0">Os Participantes recebem o aviso por e-mail. A Reunião some do Calendário.</p><div class="campo" style="margin-top:12px"><label for="rm-mot">Motivo (vai no aviso)</label><textarea id="rm-mot"></textarea></div>`,
    `<button type="button" class="btn" style="background:var(--verm);border-color:var(--verm)" data-acao="rm-desmarcar-ok" data-id="${a.dataset.id}">Desmarcar</button>`);
  N.acoes['rm-desmarcar-ok'] = (a) => set(a.dataset.id, 'CANCELADA', 'Reunião desmarcada. Os Participantes foram avisados.');
  N.acoes['rm-transcricao'] = (a) => N.modal('Enviar a Transcrição', `<div class="solta"><b>Arraste o arquivo da Transcrição aqui</b>.txt, .docx ou o texto do Fireflies</div><div class="campo" style="margin-top:12px"><label for="rm-tx">Ou cole o texto</label><textarea id="rm-tx"></textarea></div>`,
    `<button type="button" class="btn" data-acao="rm-transcricao-ok" data-id="${a.dataset.id}">Processar com IA</button>`);
  N.acoes['rm-transcricao-ok'] = (a) => { const id = a.dataset.id; set(id, 'PROCESSANDO', 'Transcrição recebida. A IA começou a Ata.'); setTimeout(() => { est.rm.estado[id] = 'AGUARDANDO_RESOLUCAO'; N.desenhar(); N.aviso('Ata montada. Faltam três nomes para casar.'); }, 2600); };
  N.acoes['rm-editar'] = (a) => { const r = reu(a.dataset.id);
    N.modal('Editar a Reunião', `<div class="grade-form"><div class="campo"><label for="ed-t">Título</label><input id="ed-t" value="${esc(r.titulo)}"></div><div class="campo"><label for="ed-d">Data</label><input id="ed-d" type="date" value="${r.data}"></div><div class="campo"><label for="ed-h">Hora</label><input id="ed-h" type="time" value="${r.hora}"></div></div>
      <div class="campo" style="margin-top:12px"><label for="ed-p">Pauta, um item por linha</label><textarea id="ed-p">${esc(r.pauta.join('\n'))}</textarea></div>`, `<button type="button" class="btn" data-acao="rm-editar-ok" data-id="${r.id}">Salvar</button>`); };
  N.acoes['rm-editar-ok'] = (a) => { const r = reu(a.dataset.id); r.titulo = document.getElementById('ed-t').value || r.titulo; r.hora = document.getElementById('ed-h').value || r.hora; r.data = document.getElementById('ed-d').value || r.data;
    r.pauta = document.getElementById('ed-p').value.split('\n').map((s) => s.trim()).filter(Boolean); N.fecharModal(); N.desenhar(); N.aviso('Reunião atualizada. Os Participantes recebem o aviso da mudança.'); };
  N.acoes['rm-part'] = (a) => N.modal('Incluir Participante', `<div class="campo"><label for="pt-n">Nome</label><input id="pt-n" list="pt-lista" placeholder="Comece a digitar"><datalist id="pt-lista">${N.pessoas.map((p) => `<option value="${esc(p.nome)}">`).join('')}</datalist></div>`, `<button type="button" class="btn" data-acao="rm-part-ok" data-id="${a.dataset.id}">Incluir</button>`, null);
  N.acoes['rm-part-ok'] = (a) => { const n = document.getElementById('pt-n').value.trim(); const r = reu(a.dataset.id); if (n && !r.participantes.includes(n)) r.participantes.push(n); N.fecharModal(); N.desenhar(); if (n) N.aviso(`${n} incluída na Reunião.`); };
  N.acoes['rm-tirar'] = (a) => N.modal('Tirar da Reunião', `<p class="sub" style="margin:0">${esc(a.dataset.nome)} deixa de receber os avisos desta Reunião.</p>`, `<button type="button" class="btn" data-acao="rm-tirar-ok" data-id="${a.dataset.id}" data-nome="${esc(a.dataset.nome)}">Tirar</button>`);
  N.acoes['rm-tirar-ok'] = (a) => { const r = reu(a.dataset.id); r.participantes = r.participantes.filter((n) => n !== a.dataset.nome); N.fecharModal(); N.desenhar(); N.aviso(`${a.dataset.nome} saiu da Reunião.`); };

  // ------------------------------------------------------------------ Ata Guiada
  function guiada(id) {
    if (!est.rm.guiada[id]) est.rm.guiada[id] = { resumo: '', quadro: [], conversa: [['ela', 'Pode contar como foi a Reunião, do seu jeito. Eu organizo o Resumo e o Quadro de atribuições e pergunto o que faltar, principalmente quem faz e até quando.']], passo: 0, ponto: null, gravando: false };
    return est.rm.guiada[id];
  }
  const ROTEIRO = [
    (g) => { g.resumo = 'A Diretoria tratou do plano de ação da auditoria de prontuários e da escala do 3º andar.'; g.quadro.push(['Enviar o plano de ação da auditoria', 'Renata Alves', 3, 'Ação', true]); return ['Anotei o plano de ação no seu nome, com prazo em 3 dias. Quem fica com a escala do 3º andar: Carla Nogueira (Enfermagem) ou Carla Menezes (Centro Cirúrgico)?', ['Carla Nogueira', 'Carla Menezes']]; },
    (g, txt) => { g.quadro.push(['Refazer a escala do 3º andar', /menezes/i.test(txt) ? 'Carla Menezes' : 'Carla Nogueira', null, 'Ação', true]); return ['Certo. Qual o prazo da escala?', ['Sexta-feira', 'Em 7 dias', 'Sem prazo']]; },
    (g, txt) => { const q = g.quadro[g.quadro.length - 1]; q[2] = /sexta/i.test(txt) ? 4 : /7/.test(txt) ? 7 : null; g.resumo += ' Ficou combinado revisar os casos da Ouvidoria da semana toda sexta.'; g.quadro.push(['Revisar os casos da Ouvidoria da semana', 'Todos os participantes', null, 'Rotina', true]); return ['Prazo anotado. Também entendi que a revisão da Ouvidoria vira uma Rotina semanal para todos os Participantes. Quer mudar alguma coisa ou posso deixar assim?', ['Pode deixar assim']]; },
    () => ['Tudo certo. Quando quiser, use Concluir e gerar pendências no alto da tela.', []]
  ];
  T.ataguiada = { trilha: 'Ata Guiada', menu: 'reunioes', mapa: ['Reuniões e metas', 'Ata Guiada'], render(id) {
    const r = reu(id) || reu('r1');
    if (souSecretaria()) return `<div class="pagina"><a class="voltar" href="#reuniao-${r.id}">${I.voltar}Voltar à Reunião</a><h1 class="pagina-titulo">A Ata Guiada é do Facilitador.</h1><p class="pagina-sub">A Secretária agenda e cuida dos Participantes. <a href="#reuniao-${r.id}">Voltar à Reunião</a></p></div>`;
    if (estadoDe(r) !== 'PROGRAMADA') return `<div class="pagina"><a class="voltar" href="#reuniao-${r.id}">${I.voltar}Voltar à Reunião</a><h1 class="pagina-titulo">Esta Reunião já tem Ata.</h1><p class="pagina-sub">A Ata Guiada só começa numa Reunião programada. <a href="#reuniao-${r.id}">Ver a Ata</a></p></div>`;
    const g = guiada(r.id);
    const ultimas = g.conversa.length && g.conversa[g.conversa.length - 1][2];
    const vazio = !g.resumo && !g.quadro.length;
    return `<div class="guiada-barra"><div style="display:flex;align-items:center;gap:14px;min-width:0"><a class="voltar" style="margin:0" href="#reuniao-${r.id}">${I.voltar}Reunião</a><div style="min-width:0"><p class="rot-mini" style="margin:0">Ata Guiada · ${curto(deIso(r.data))}, ${r.hora}</p><h1>${esc(r.titulo)}</h1></div></div>
        <div style="display:flex;gap:10px;align-items:center"><span class="sub">${g.quadro.length} ${g.quadro.length === 1 ? 'item' : 'itens'} no Quadro</span><button class="btn grande" data-acao="ag-concluir" data-id="${r.id}"${g.quadro.length ? '' : ' disabled style="opacity:.5;cursor:default"'}>Concluir e gerar pendências</button></div></div>
      <div class="guiada">
        <section class="cartao bloco" aria-label="Ata viva">
          <p class="rot-mini" style="margin:0 0 10px">Ata viva, igual à Ata final</p>
          ${vazio ? `<div class="solta" style="margin-bottom:14px"><b>A Ata aparece aqui enquanto você conta</b>Comece pelo chat ao lado, por texto ou voz. Se tiver anotações ou slides, anexe como documento de apoio.</div>` : ''}
          <div class="sec-viva${g.mexeu === 'resumo' ? ' mexeu' : ''}"><div class="cab"><h2 class="titulo-bloco" style="font-size:16px">Resumo Executivo</h2><button class="apontar" data-acao="ag-apontar" data-id="${r.id}" data-v="Resumo Executivo" aria-pressed="${g.ponto === 'Resumo Executivo'}">Apontar e corrigir</button></div>
            <p style="margin:8px 0 0;${g.resumo ? '' : 'color:var(--texto2)'}">${esc(g.resumo || 'Ainda vazio.')}</p></div>
          <div class="sec-viva${g.mexeu === 'quadro' ? ' mexeu' : ''}" style="margin-top:12px"><div class="cab"><h2 class="titulo-bloco" style="font-size:16px">Quadro de atribuições</h2><button class="apontar" data-acao="ag-apontar" data-id="${r.id}" data-v="Quadro de atribuições" aria-pressed="${g.ponto === 'Quadro de atribuições'}">Apontar e corrigir</button></div>
            ${g.quadro.length ? `<div class="tabela-rola"><table class="tab" style="min-width:520px"><thead><tr><th>Ação</th><th>Responsável</th><th>Prazo</th><th>Tipo</th></tr></thead><tbody>${g.quadro.map(([a, resp, off, tipo]) => `<tr><td>${esc(a)}</td><td>${esc(resp)}</td><td class="num">${off === null ? '<span class="sub">Sem prazo</span>' : fmt(dia(off))}</td><td><span class="pill">${tipo}</span></td></tr>`).join('')}</tbody></table></div>` : '<p class="sub" style="margin:8px 0 0">Ainda vazio.</p>'}</div>
        </section>
        <section class="cartao bloco chat" aria-label="Conversa com o agente">
          <div class="cab"><h2 class="titulo-bloco" style="font-size:16px">Conversa</h2>${g.ponto ? `<span class="pill laranja">Corrigindo: ${esc(g.ponto)}</span>` : ''}</div>
          <div class="conversa" id="ag-conversa" aria-live="polite" style="margin-top:10px">${g.conversa.map(([q, t]) => `<div class="balao ${q}"><small>${q === 'eu' ? 'Você' : 'Agente da Ata'}</small>${esc(t)}</div>`).join('')}
            ${ultimas && ultimas.length ? `<div class="respostas">${ultimas.map((o) => `<button type="button" class="resp-rapida" data-acao="ag-resp" data-id="${r.id}" data-v="${esc(o)}">${esc(o)}</button>`).join('')}</div>` : ''}</div>
          <form class="escrever" id="ag-form" data-id="${r.id}"><label class="btn contorno" style="cursor:pointer;padding:0 12px" title="Anexar documento de apoio">${IC.anexo}<span class="sr">Anexar documento de apoio</span><input type="file" hidden></label>
            <label for="ag-txt" class="sr">Mensagem</label><textarea id="ag-txt" placeholder="${g.gravando ? 'Ouvindo... fale normalmente' : 'Conte o que foi decidido'}"></textarea>
            <button type="button" class="btn ${g.gravando ? '' : 'contorno'}" data-acao="ag-voz" data-id="${r.id}" aria-pressed="${g.gravando}" aria-label="Falar">${IC.microfone}</button><button class="btn" type="submit" aria-label="Enviar">${IC.enviar}</button></form>
        </section>
      </div>`;
  }, depois() { const c = document.getElementById('ag-conversa'); if (c) c.scrollTop = c.scrollHeight; } };
  function falar(id, txt) {
    const g = guiada(id); if (!txt.trim()) return;
    g.conversa.push(['eu', txt]);
    if (g.ponto) { g.conversa.push(['ela', `Corrigi ${g.ponto} como você pediu.`, []]); g.mexeu = g.ponto === 'Resumo Executivo' ? 'resumo' : 'quadro'; g.ponto = null; }
    else { const passo = ROTEIRO[Math.min(g.passo, ROTEIRO.length - 1)]; const [resp, ops] = passo(g, txt); g.conversa.push(['ela', resp, ops]); g.passo += 1; g.mexeu = 'quadro'; }
    N.desenhar(); setTimeout(() => { g.mexeu = null; }, 900);
  }
  N.envios['ag-form'] = (f) => { const t = document.getElementById('ag-txt'); falar(f.dataset.id, t.value); };
  N.acoes['ag-resp'] = (a) => falar(a.dataset.id, a.dataset.v);
  N.acoes['ag-apontar'] = (a) => { const g = guiada(a.dataset.id); g.ponto = g.ponto === a.dataset.v ? null : a.dataset.v; N.desenhar(); const t = document.getElementById('ag-txt'); if (t) t.focus(); };
  N.acoes['ag-voz'] = (a) => { const g = guiada(a.dataset.id); g.gravando = !g.gravando; N.desenhar();
    if (!g.gravando) falar(a.dataset.id, g.passo === 0 ? 'A gente fechou o plano de ação da auditoria comigo, para esta semana, e a escala do 3º andar fica com a Carla.' : 'Pode seguir.'); else N.aviso('Gravando. Toque de novo para parar e mandar.'); };
  N.acoes['ag-concluir'] = (a) => { const g = guiada(a.dataset.id);
    N.modal('Concluir a Ata Guiada', `<p class="sub" style="margin:0">${g.quadro.length} ${g.quadro.length === 1 ? 'item vira Pendência ou Rotina' : 'itens viram Pendências e Rotinas'} agora, no nome de cada responsável. A Reunião fica APROVADA, sem assinatura.</p>`, `<button type="button" class="btn" data-acao="ag-concluir-ok" data-id="${a.dataset.id}">Concluir</button>`); };
  N.acoes['ag-concluir-ok'] = (a) => { const id = a.dataset.id; const g = guiada(id); est.rm.estado[id] = 'APROVADA'; est.rm.guiada[id + 'feita'] = true; QUADRO_EXTRA[id] = g.quadro.map((q) => q.slice(0, 4)); RESUMO[id] = g.resumo;
    est.rm.aba[id] = 'quadro'; N.fecharModal(); location.hash = '#reuniao-' + id; N.aviso(`Ata aprovada. ${g.quadro.length} itens já estão com os responsáveis.`); };

  // ------------------------------------------------------------------ Dashboard
  const SEMANAS = [74, 76, 75, 79, 78, 80, 79, 82];
  T.dashboard = { trilha: 'Dashboard', menu: 'dashboard', mapa: ['Reuniões e metas', 'Dashboard'], render() {
    const abertas = PEND.filter((p) => p.sit !== 'concluida');
    const v3 = abertas.filter((p) => p.off >= 0 && p.off <= 3);
    const paradas = reunioes.filter((r) => /AGUARDANDO_VALIDACAO|AGUARDANDO_RESOLUCAO/.test(estadoDe(r)));
    const assin = reunioes.filter((r) => estadoDe(r) === 'AGUARDANDO_ASSINATURA');
    const setores = {};
    abertas.forEach((p) => { const s = setores[p.setor] = setores[p.setor] || { ok: 0, atr: 0 }; if (p.off < 0) s.atr += 1; else s.ok += 1; });
    const lista = Object.entries(setores).sort((a, b) => b[1].atr - a[1].atr || (b[1].ok + b[1].atr) - (a[1].ok + a[1].atr));
    const maxS = Math.max(...lista.map(([, s]) => s.ok + s.atr));
    const pior = lista[0];
    const conf = SEMANAS[SEMANAS.length - 1], dif = conf - SEMANAS[SEMANAS.length - 2];
    const frase = `Conformidade de ${conf}% nas Pendências das suas Reuniões, ${dif >= 0 ? dif + ' pontos acima' : -dif + ' pontos abaixo'} da semana passada.${pior && pior[1].atr ? ` ${pior[0]} concentra ${pior[1].atr} dos ${abertas.filter((p) => p.off < 0).length} atrasos.` : ''}`;
    const stat = (rot, val, varTxt, bom, icone, attrs, verm) => `<a ${attrs} class="cartao stat"><span><span class="rot">${rot}</span><span class="valor num ${verm ? 'verm' : ''}">${val}</span><span class="var-sem ${bom === null ? '' : bom ? 'bom' : 'ruim'}">${varTxt}</span></span><span class="ic ${verm ? 'verm' : ''}">${icone}</span></a>`;
    const W = 560, H = 120, P = 8; const mn = 70, mx = 85;
    const pts = SEMANAS.map((v, n) => [P + n * (W - 2 * P) / (SEMANAS.length - 1), H - P - (v - mn) / (mx - mn) * (H - 2 * P)]);
    const linha = pts.map((p, n) => `${n ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
    const ranking = [...N.pessoas].map((p) => ({ ...p, pct: Math.round(p.np / (p.np + p.fp) * 100) })).sort((a, b) => b.pct - a.pct);
    const PER = [['30', '30 dias'], ['90', '90 dias'], ['ano', 'Este ano']];
    const corpo = `
      <p class="aviso" style="margin-top:14px">${I.info}<span>Este painel olha as Reuniões e os setores. O que depende de você está no <a href="#inicio">Início</a>.</span></p>
      <div class="ferramentas" style="margin-top:14px"><div class="filtros-linha">${N.filtro({ id: 'rm-periodo', rotulo: 'Período', opcoes: PER, valor: est.rm.periodo, acao: 'rm-chip', dados: { g: 'periodo' } })}</div></div>
      <div class="duas" style="margin-top:6px">
        <section class="cartao bloco larga"><div class="cab"><h2 class="titulo-bloco">Pendências abertas por setor</h2><span class="sub">Clique num setor para ver as Pendências dele</span></div>
          <div style="margin-top:10px">${lista.map(([s, v]) => `<a class="barra-setor" href="#pendencias" data-acao="rm-setor" data-v="${esc(s)}" data-previa="${esc(`<b>${esc(s)}</b><span class="sub">${v.ok + v.atr} Pendências abertas</span><span class="sub">${v.ok} no prazo, ${v.atr} atrasada${v.atr === 1 ? '' : 's'}</span><span class="dica">Clique para ver as Pendências do setor</span>`)}"><span>${esc(s)}</span><span class="trilho" style="width:${(v.ok + v.atr) / maxS * 100}%"><span style="width:${v.ok / (v.ok + v.atr) * 100}%;background:var(--btn-fundo)"></span><span style="width:${v.atr / (v.ok + v.atr) * 100}%;background:var(--ponto-verm)"></span></span><span class="num sub" style="text-align:right">${v.atr ? `<b style="color:var(--verm)">${v.atr} atrasada${v.atr > 1 ? 's' : ''}</b>` : `${v.ok} no prazo`}</span></a>`).join('')}</div>
          <div class="legenda"><span><i style="background:var(--btn-fundo)"></i>No prazo</span><span><i style="background:var(--ponto-verm)"></i>Atrasadas</span></div></section>
        <section class="cartao bloco estreita"><h2 class="titulo-bloco">Evolução semanal</h2><p class="sub" style="margin:4px 0 0">Conformidade das últimas 8 semanas</p>
          <svg class="linha-graf" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Conformidade por semana: ${SEMANAS.join(', ')} por cento"><path class="a" d="${linha} L${pts[pts.length - 1][0]},${H} L${pts[0][0]},${H} Z"/><path class="l" d="${linha}"/></svg>
          <div style="display:flex;justify-content:space-between" class="sub num"><span>${SEMANAS[0]}%</span><span>hoje ${conf}%</span></div></section>
      </div>
      ${N.perfil() === 'admin' ? `<section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2 class="titulo-bloco">Ranking de 90 dias</h2><span class="sub">Só o Super admin vê esta tabela</span></div>
        <div class="tabela-rola"><table class="tab"><thead><tr><th>#</th><th>Pessoa</th><th>Setor</th><th>No prazo</th><th>Entregas</th></tr></thead><tbody>${ranking.map((p, n) => `<tr><td class="num">${n + 1}</td><td><a href="#pessoa-${p.id}">${esc(p.nome)}</a></td><td>${esc(p.setor)}</td><td style="min-width:180px"><div style="display:flex;align-items:center;gap:10px"><div class="prog ${p.pct < 80 ? 'verm' : ''}" style="flex:1"><span style="width:${p.pct}%"></span></div><span class="num">${p.pct}%</span></div></td><td class="num">${p.np + p.fp}</td></tr>`).join('')}</tbody></table></div></section>` : ''}`;
    return `${N.cabModulo({ sobre: 'Reuniões e metas', titulo: 'Dashboard', frase, resumo: true })}<div class="corpo-modulo"><section class="resumo" aria-label="Resumo">
        ${stat('Conformidade', conf + '%', `${dif >= 0 ? '+' : ''}${dif} pontos na semana`, dif >= 0, I.certo, 'href="#pendencias"')}
        ${stat('Vencem em 3 dias', String(v3.length).padStart(2, '0'), 'mesmo número da semana passada', null, I.relogio, 'href="#pendencias"')}
        ${stat('Atas paradas', String(paradas.length).padStart(2, '0'), 'esperam validação ou nomes', paradas.length ? false : true, I.alerta, 'href="#" data-acao="rm-lista" data-v="paradas"', paradas.length > 0)}
        ${stat('Aguardam assinatura', String(assin.length).padStart(2, '0'), '1 a mais que na semana passada', false, I.agenda, 'href="#" data-acao="rm-lista" data-v="assinatura"')}
      </section>${corpo}<p class="demo">Dados de demonstração.</p></div>`;
  } };
  N.acoes['rm-setor'] = (a) => { if (est.mt) { est.mt.busca = a.dataset.v; est.mt.recorte = 'todas'; } location.hash = '#pendencias'; };
  N.acoes['rm-lista'] = (a) => {
    const lista = reunioes.filter((r) => a.dataset.v === 'paradas' ? /AGUARDANDO_VALIDACAO|AGUARDANDO_RESOLUCAO/.test(estadoDe(r)) : estadoDe(r) === 'AGUARDANDO_ASSINATURA');
    N.abrirGaveta({ sobre: `<span class="rot-mini">Dashboard</span>`, titulo: a.dataset.v === 'paradas' ? 'Atas paradas' : 'Atas aguardando assinatura',
      corpo: lista.length ? `<ul class="linhas">${lista.map((r) => { const [c, t] = NOME[estadoDe(r)]; return `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t"><a href="#reuniao-${r.id}" data-acao="fechar-gaveta-ir" data-href="#reuniao-${r.id}" style="font-weight:700;text-decoration:none">${esc(r.titulo)}</a><small>${curto(deIso(r.data))} · ${esc(facil(r))}</small></span><span class="${c}">${t}</span></li>`; }).join('')}</ul>` : '<p class="vazio">Nenhuma Ata parada. Tudo andando.</p>' });
  };

  // ------------------------------------------------------------------ Definições de processo
  const PROC = [
    { id: 'd1', setor: 'Farmácia', t: 'Pedido urgente à farmácia fora do horário', obj: 'Garantir o medicamento em até 30 minutos à noite e no fim de semana.', trecho: 'Fica definido que o pedido urgente fora do horário vai por telefone ao farmacêutico de sobreaviso e é registrado no sistema em seguida.', reu: 'rv' },
    { id: 'd2', setor: 'Farmácia', t: 'Dupla checagem de medicamentos de alta vigilância', obj: 'Evitar erro na administração de insulina, heparina e potássio.', trecho: 'Toda dose de alta vigilância passa pela conferência de um segundo profissional antes de ir ao leito.', reu: 'r0' },
    { id: 'd3', setor: 'Enfermagem', t: 'Passagem de plantão à beira do leito', obj: 'Reduzir informação perdida entre turnos.', trecho: 'A passagem de plantão da UTI passa a ser feita à beira do leito, com o checklist impresso.', reu: 'ra' },
    { id: 'd4', setor: 'CCIH', t: 'Isolamento de contato na admissão', obj: 'Isolar na entrada o paciente que vem transferido de outro hospital.', trecho: 'Paciente transferido entra em isolamento de contato até o resultado do swab.', reu: 'rm1' },
    { id: 'd5', setor: 'Suprimentos', t: 'Estoque mínimo de EPIs do Centro Cirúrgico', obj: 'Não faltar avental nem máscara N95 nas salas.', trecho: 'Suprimentos mantém 15 dias de estoque mínimo e avisa a Diretoria quando cair para 7.', reu: 'r0' }
  ];
  est.rm.setores = [];
  T.processos = { trilha: 'Definições de processo', menu: 'processos', mapa: ['Reuniões e metas', 'Definições de processo'], render() {
    const ativos = PROC.filter((d) => !est.rm.tirados[d.id]);
    const setores = [...new Set(PROC.map((d) => d.setor))];
    const lista = ativos.filter((d) => N.passa(est.rm.setores, d.setor));
    const porSetor = setores.map((s) => [s, lista.filter((d) => d.setor === s)]).filter(([, l]) => l.length);
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas"><div class="filtros-linha">${N.filtro({ id: 'rm-setores', rotulo: 'Setor', opcoes: setores.map((x) => [x, esc(x)]), multi: true, obj: 'rm', campo: 'setores', todos: 'Todos os setores' })}</div></div>
      ${porSetor.length ? porSetor.map(([s, l]) => `<p class="grupo-tit">${esc(s)}<span class="n">${l.length}</span></p>
        <div class="grade g2" style="margin-top:6px">${l.map((d) => { const r = reu(d.reu); return `<article class="cartao bloco" style="box-shadow:none;background:var(--cartao)">
          <h3 class="titulo-bloco" style="font-size:16px">${esc(d.t)}</h3>
          <p class="sub" style="margin:6px 0 0"><b style="color:var(--texto)">Objetivo:</b> ${esc(d.obj)}</p>
          <blockquote class="citacao">${esc(d.trecho)}</blockquote>
          <div class="cab" style="margin-top:12px"><a class="sub" href="#reuniao-${r.id}" style="color:var(--acento);text-decoration:none;font-weight:700">Da Ata: ${esc(r.titulo)}, ${curto(deIso(r.data))}</a>
            <button class="btn contorno" data-acao="rm-tirar-proc" data-id="${d.id}">Tirar da lista</button></div>
        </article>`; }).join('')}</div>`).join('')
        : '<p class="vazio">Nenhuma Definição de processo aqui. Elas nascem quando a Ata marca um item do Quadro como Processo.</p>'}
    </section>`;
    return N.modulo({ sobre: 'Reuniões e metas', titulo: 'Definições de processo', frase: `${ativos.length} combinados de como o trabalho deve ser feito, tirados das Atas, em ${setores.length} setores.` },
      [['Processos definidos', String(ativos.length).padStart(2, '0'), I.certo, '#processos'], ['Setores', String(setores.length).padStart(2, '0'), I.agenda, '#processos'], ['Novos em 30 dias', '03', I.relogio, '#processos']], '', corpo);
  } };
  N.acoes['rm-tirar-proc'] = (a) => { const d = PROC.find((x) => x.id === a.dataset.id);
    N.modal('Tirar da lista', `<p class="sub" style="margin:0 0 12px">${esc(d.t)}</p><div class="campo"><label for="tp-anot">Por que sai da lista</label><textarea id="tp-anot" placeholder="Ex.: virou POP, ou o combinado mudou"></textarea></div>`, `<button type="button" class="btn" data-acao="rm-tirar-proc-ok" data-id="${d.id}">Tirar da lista</button>`); };
  N.acoes['rm-tirar-proc-ok'] = (a) => { est.rm.tirados[a.dataset.id] = true; N.fecharModal(); N.desenhar(); N.aviso('Definição tirada da lista, com a anotação.'); };

  // ------------------------------------------------------------------ cartão do calendário (hover), igual ao do app de hoje e com a assinatura
  N.previaReuniao = (r) => {
    const e = estadoDe(r), [tipo, serie, objetivo] = INFO[r.id] || ['', '', ''];
    const f = facil(r), nomes = r.participantes.slice(0, 4);
    const fim = (() => { const [h, m] = r.hora.split(':').map(Number); return `${String(h + 1).padStart(2, '0')}:${String(m).padStart(2, '0')}`; })();
    return esc(`<b>${esc(r.titulo)}</b>
      <span class="pv-estado"><i class="${/ASSINADA|APROVADA/.test(e) ? 'ok' : /AGUARDANDO|PROCESS|CORRIG/.test(e) ? 'meio' : ''}"></i>${NOME[e] ? NOME[e][1] : ''}${tipo ? ` <em>|</em> ${tipo}` : ''}</span>
      ${serie ? `<span class="pv-serie">Série: ${esc(serie)}</span>` : ''}
      <span class="sub">${N.longo(deIso(r.data))}, ${r.hora} às ${fim}</span>
      ${objetivo ? `<span class="sub pv-obj">${esc(objetivo)}</span>` : ''}
      ${/ASSINADA|APROVADA|AGUARDANDO_ASSINATURA/.test(e) ? `<span class="pv-assin">${N.infoAssinatura(r)}</span>` : ''}
      <span class="pv-part"><span class="rot-mini">Participantes</span>${nomes.map((n) => `<span class="${n === f ? 'pv-fac' : ''}">${esc(n)}${n === f ? ' · Facilitador' : ''}</span>`).join('')}${r.participantes.length > 4 ? `<span class="sub">+${r.participantes.length - 4} mais</span>` : ''}</span>
      <span class="pv-links"><a href="#reuniao-${r.id}">Ver detalhe</a>${e === 'ASSINADA' ? `<a href="#" data-acao="toast" data-msg="No sistema, baixa o PDF assinado.">PDF assinado</a>` : e === 'APROVADA' ? `<a href="#" data-acao="toast" data-msg="No sistema, baixa o PDF da Ata.">PDF da Ata</a>` : ''}${serie && e === 'PROGRAMADA' ? `<a href="#" class="pv-excluir" data-acao="rm-excluir-serie" data-id="${r.id}">Excluir toda a série recorrente</a>` : ''}</span>`);
  };
  N.acoes['rm-excluir-serie'] = (a) => { const r = reu(a.dataset.id); const [, serie] = INFO[r.id] || [];
    N.modal('Excluir toda a série?', `<p>Saem do calendário todas as Reuniões programadas da série <b>${esc(serie)}</b>. As que já aconteceram ficam, com as Atas.</p>`, `<button type="button" class="btn" style="background:var(--verm);border-color:var(--verm)" data-acao="toast" data-msg="Série excluída. Os Participantes foram avisados.">Excluir a série</button>`); };
  N.css(`.previa .pv-estado{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--texto2);margin:2px 0 6px}
    .previa .pv-estado i{width:7px;height:7px;border-radius:999px;background:var(--ponto-azul)}.previa .pv-estado i.ok{background:var(--verde)}.previa .pv-estado i.meio{background:var(--ponto-laranja)}
    .previa .pv-estado em{font-style:normal;opacity:.4}
    .previa .pv-serie{display:inline-block;margin:0 0 6px;padding:2px 8px;border-radius:6px;background:var(--suave2);color:var(--titulo);font-size:12px;font-weight:700}
    .previa .pv-obj{margin-top:4px}
    .previa .pv-assin{display:block;margin-top:8px;padding:7px 10px;border-radius:7px;background:#E3F4EA;color:var(--verde);font-weight:700;font-size:12.5px;line-height:1.35}
    .previa .pv-part{display:flex;flex-direction:column;gap:1px;margin-top:8px;padding-top:8px;border-top:1px solid var(--linha);font-size:13px}
    .previa .pv-part .rot-mini{margin-bottom:2px}.previa .pv-fac{color:var(--laranja);font-weight:700}
    .previa .pv-links{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:10px;padding-top:8px;border-top:1px solid var(--linha)}
    .previa .pv-links a{font-size:12.5px;font-weight:700;color:var(--acento);text-decoration:none}.previa .pv-links a:hover{text-decoration:underline}
    .previa .pv-links a.pv-excluir{color:var(--verm)}`);
})();
