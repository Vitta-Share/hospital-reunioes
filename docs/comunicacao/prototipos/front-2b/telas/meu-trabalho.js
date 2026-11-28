/* Meu trabalho: Pendências (lista e quadro, com a gaveta de detalhe), Rotinas e Calendário. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I, IC, dia, fmt, curto, est, reunioes, deIso, difDias, HOJE, iso, cap } = N;
  const T = N.telas;
  est.mt = { busca: '', recorte: 'minhas', area: 'todas', sit: 'abertas', pop: null, rot: {} };

  // ------------------------------------------------------------------ dados: as Pendências de Reunião
  const PEND = [
    { id: 'p1', t: 'Revisar a escala de enfermagem do 3º andar', resp: 'Renata Alves', reu: 'r0', off: -12, sit: 'pendente', setor: 'Diretoria Assistencial' },
    { id: 'p4', t: 'Enviar o plano de ação da auditoria de prontuários', resp: 'Renata Alves', reu: 'r3', off: 0, sit: 'andamento', setor: 'Qualidade' },
    { id: 'p7', t: 'Enviar os indicadores de queda ao NSP', resp: 'Renata Alves', reu: 'r4', off: 2, sit: 'pendente', setor: 'Diretoria Assistencial' },
    { id: 'p14', t: 'Atualizar a lista de presença da Diretoria Assistencial', resp: 'Renata Alves', reu: 'r0', off: 3, sit: 'pendente', setor: 'Diretoria Assistencial' },
    { id: 'p10', t: 'Atualizar o protocolo de sepse', resp: 'Renata Alves', reu: 'r3', off: 12, sit: 'andamento', setor: 'Qualidade' },
    { id: 'x1', t: 'Inventário dos medicamentos controlados', resp: 'Rodrigo Sales', reu: 'r0', off: -9, sit: 'pendente', setor: 'Farmácia' },
    { id: 'x2', t: 'Plano de contingência de estoque', resp: 'Rodrigo Sales', reu: 'r0', off: -5, sit: 'andamento', setor: 'Farmácia' },
    { id: 'x3', t: 'Escala de dezembro da UTI', resp: 'Carla Nogueira', reu: 'r0', off: -4, sit: 'pendente', setor: 'Enfermagem' },
    { id: 'x4', t: 'Cotação de EPIs do Centro Cirúrgico', resp: 'Paulo Mendes', reu: 'r0', off: -3, sit: 'contestada', setor: 'Suprimentos' },
    { id: 'x5', t: 'Treinamento de dupla checagem', resp: 'Rodrigo Sales', reu: 'r3', off: -2, sit: 'pendente', setor: 'Farmácia' },
    { id: 'x6', t: 'Checklist de passagem de plantão', resp: 'Carla Nogueira', reu: 'r0', off: -1, sit: 'andamento', setor: 'Enfermagem' },
    { id: 'x7', t: 'Revisar o fluxo de isolamento de contato', resp: 'Fernanda Lima', reu: 'r3', off: 4, sit: 'andamento', setor: 'CCIH' },
    { id: 'x8', t: 'Trocar o enxoval da ala B', resp: 'Juliana Prado', reu: 'r0', off: 6, sit: 'pendente', setor: 'Hotelaria' },
    { id: 'x9', t: 'Relatório de eventos adversos de outubro', resp: 'Renata Alves', reu: 'r4', off: -3, sit: 'concluida', setor: 'Diretoria Assistencial', noPrazo: true },
    { id: 'x10', t: 'Pedido de compra das bombas de infusão', resp: 'Paulo Mendes', reu: 'r3', off: -8, sit: 'concluida', setor: 'Suprimentos', noPrazo: false },
    { id: 'x11', t: 'Campanha de higienização das mãos', resp: 'Fernanda Lima', reu: 'r0', off: -10, sit: 'concluida', setor: 'CCIH', noPrazo: true }
  ];
  const ATIV = {
    p1: [['Carla Nogueira', 'há 17 dias', 'Mandei a proposta da escala com as duas técnicas novas por e-mail.', 'c'], ['Sistema', 'há 15 dias', 'Pendência criada a partir da Ata da Reunião da Diretoria Assistencial.', 'h'], ['Renata Alves', 'há 4 dias', '@Carla Nogueira consegue me mandar a versão com o plantão noturno separado?', 'c']],
    x4: [['Sistema', 'há 20 dias', 'Pendência criada a partir da Ata.', 'h'], ['Paulo Mendes', 'há 3 dias', 'Contestou o prazo: o fornecedor atrasou a entrega dos aventais. Pede mais 15 dias.', 'h']]
  };
  const sitDe = (p) => p.sit === 'concluida' ? 'concluida' : p.off < 0 ? 'atrasada' : p.sit;
  const SIT = { atrasada: ['e-venc', 'Atrasada'], pendente: ['e-sem', 'Pendente'], andamento: ['e-prox', 'Em andamento'], contestada: ['e-hoje', 'Contestada'], concluida: ['e-ok', 'Concluída'] };
  const reu = (id) => reunioes.find((r) => r.id === id);
  const souEu = (p) => p.resp === 'Renata Alves';
  N.PEND = PEND;

  function filtradas() {
    const t = est.mt.busca.trim().toLowerCase();
    return PEND.filter((p) => est.mt.recorte === 'todas' || (est.mt.recorte === 'minhas' ? souEu(p) : !souEu(p)))
      .filter((p) => !t || (p.t + ' ' + p.resp + ' ' + p.setor).toLowerCase().includes(t));
  }

  // ------------------------------------------------------------------ cabeçalho comum de Pendências
  function cabPend(atual) {
    const minhas = PEND.filter((p) => souEu(p) && p.sit !== 'concluida');
    const atr = PEND.filter((p) => p.sit !== 'concluida' && p.off < 0);
    const h48 = PEND.filter((p) => p.sit !== 'concluida' && p.off >= 0 && p.off <= 2);
    const contest = PEND.filter((p) => p.sit === 'contestada');
    return {
      cab: { sobre: 'Meu trabalho', titulo: 'Pendências', frase: `${minhas.length} no seu nome e ${PEND.filter((p) => !souEu(p) && p.sit !== 'concluida').length} das Reuniões que você conduz. ${atr.length} passaram do prazo.`,
        acoes: `<a class="btn claro grande" href="#reunioes">Ver as Reuniões de origem</a>` },
      resumo: [['Passaram do prazo', String(atr.length).padStart(2, '0'), I.alerta, '#pendencias', true], ['Vencem em 48 horas', String(h48.length).padStart(2, '0'), I.relogio, '#pendencias'],
        ['Contestações para você', String(contest.length).padStart(2, '0'), I.agenda, '#pendencias'], ['No prazo em 90 dias', '87%', I.certo, '#dashboard']],
      abas: N.abasModulo([['#pendencias', 'Lista', PEND.filter((p) => p.sit !== 'concluida').length], ['#quadro', 'Quadro', null], ['#concluidas', 'Concluídas', PEND.filter((p) => p.sit === 'concluida').length]], atual)
    };
  }
  function ferramentas() {
    const R = [['minhas', 'No meu nome'], ['equipe', 'Das minhas Reuniões'], ['todas', 'Todas']];
    return `<div class="ferramentas">
      <div class="filtros-linha">${N.filtro({ id: 'mt-recorte', rotulo: 'De quem', opcoes: R, valor: est.mt.recorte, acao: 'mt-recorte' })}</div>
      <label class="busca-lista">${IC.busca}<span class="sr">Buscar</span><input id="mt-busca" data-digita="mt-busca" type="search" placeholder="Buscar por título, pessoa ou setor" value="${esc(est.mt.busca)}"></label>
    </div>`;
  }
  N.digitar['mt-busca'] = (v) => { est.mt.busca = v; };
  N.acoes['mt-recorte'] = (a) => { est.mt.recorte = a.dataset.v; N.desenhar(); };

  // ------------------------------------------------------------------ lista
  function botaoAcao(p) {
    if (p.sit === 'concluida') return '';
    if (p.sit === 'contestada' && !souEu(p)) return `<button class="btn" data-acao="pend-abrir" data-id="${p.id}">Responder</button>`;
    return souEu(p) ? `<button class="btn" data-acao="pend-abrir" data-id="${p.id}">Resolver</button>` : `<button class="btn contorno" data-acao="pend-cobrar" data-id="${p.id}">Cobrar</button>`;
  }
  T.pendencias = { trilha: 'Pendências', menu: 'pendencias', render() {
    const c = cabPend('#pendencias');
    const lista = filtradas().filter((p) => p.sit !== 'concluida').sort((a, b) => a.off - b.off);
    const corpo = `<section class="cartao bloco" style="margin-top:14px">${ferramentas()}
      <div class="tabela-rola"><table class="tab"><thead><tr><th>Situação</th><th>Pendência</th><th>Responsável</th><th>Prazo</th><th></th></tr></thead><tbody>
      ${lista.map((p) => { const [cls, txt] = SIT[sitDe(p)]; const r = reu(p.reu);
        return `<tr><td>${N.estado(cls, txt)}</td>
          <td><a href="#" data-acao="pend-abrir" data-id="${p.id}">${esc(p.t)}</a><div class="sub">${r ? esc(r.titulo) + ', ' + curto(deIso(r.data)) : ''}</div></td>
          <td><span style="display:inline-flex;align-items:center;gap:8px"><span class="ini" style="width:30px;height:30px;border-radius:999px;background:var(--suave2);color:var(--titulo);display:inline-flex;align-items:center;justify-content:center;font-size:11.5px;font-weight:700">${N.ini(p.resp)}</span>${souEu(p) ? 'Você' : esc(p.resp)}</span></td>
          <td class="num" style="${p.off < 0 ? 'color:var(--verm)' : ''}">${fmt(dia(p.off))}${p.off < 0 ? `<div class="sub">${-p.off} ${p.off === -1 ? 'dia' : 'dias'} de atraso</div>` : ''}</td>
          <td style="text-align:right">${botaoAcao(p)}</td></tr>`; }).join('')}
      </tbody></table>${lista.length ? '' : '<p class="vazio">Nada encontrado com esse filtro.</p>'}</div></section>`;
    return N.modulo(c.cab, c.resumo, c.abas, corpo);
  } };

  // ------------------------------------------------------------------ quadro (arrastar de verdade)
  T.quadro = { trilha: 'Pendências', menu: 'pendencias', render() {
    const c = cabPend('#quadro');
    const COLS = [['atrasada', 'Atrasadas'], ['pendente', 'A fazer'], ['andamento', 'Em andamento'], ['contestada', 'Contestadas'], ['concluida', 'Concluídas']];
    const lista = filtradas();
    const corpo = `<section class="cartao bloco" style="margin-top:14px">${ferramentas()}
      <p class="sub" style="margin:4px 0 0">Arraste um cartão para outra coluna: a tela pede só a anotação que aquela mudança exige.</p>
      <div class="quadro">${COLS.map(([k, t]) => { const fs = lista.filter((p) => sitDe(p) === k);
        return `<div class="coluna" data-coluna="${k}"><h3><span>${t}</span><span class="num">${fs.length}</span></h3>
          ${fs.map((p) => `<button type="button" class="ficha-q" draggable="true" data-arrasta="${p.id}" data-acao="pend-abrir" data-id="${p.id}"><b>${esc(p.t)}</b><small>${esc(reu(p.reu) ? reu(p.reu).titulo : '')}</small>
            <span class="rodape-f"><span class="pill">${souEu(p) ? 'Você' : esc(p.resp.split(' ')[0])}</span><span class="num sub" style="${p.off < 0 && p.sit !== 'concluida' ? 'color:var(--verm)' : ''}">${curto(dia(p.off))}</span></span></button>`).join('')}</div>`; }).join('')}</div></section>`;
    return N.modulo(c.cab, c.resumo, c.abas, corpo);
  }, depois() {
    document.querySelectorAll('[data-arrasta]').forEach((el) => el.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/plain', el.dataset.arrasta); }));
    document.querySelectorAll('[data-coluna]').forEach((col) => {
      col.addEventListener('dragover', (e) => { e.preventDefault(); col.style.outline = '2px dashed var(--acento)'; });
      col.addEventListener('dragleave', () => { col.style.outline = ''; });
      col.addEventListener('drop', (e) => { e.preventDefault(); col.style.outline = ''; const p = PEND.find((x) => x.id === e.dataTransfer.getData('text/plain')); if (p) mover(p, col.dataset.coluna); });
    });
  } };
  function mover(p, para) {
    const pede = { concluida: ['Concluir a Pendência', 'O que foi feito?', 'Concluir'], andamento: ['Começar a Pendência', 'Anotação (opcional)', 'Começar'], contestada: ['Contestar o prazo', 'Por que o prazo não serve? Sugira a nova data.', 'Enviar a contestação'], pendente: ['Voltar para A fazer', 'Por que volta?', 'Voltar'], atrasada: null }[para];
    if (!pede) { N.aviso('Atrasada é calculada pelo prazo: não dá para mover um cartão para lá.'); return; }
    N.modal(pede[0], `<p class="sub" style="margin:0 0 12px">${esc(p.t)}</p><div class="campo"><label for="mv-anot">${pede[1]}</label><textarea id="mv-anot"></textarea></div>`,
      `<button type="button" class="btn" data-acao="pend-mover" data-id="${p.id}" data-para="${para}">${pede[2]}</button>`);
  }
  N.acoes['pend-mover'] = (a) => { const p = PEND.find((x) => x.id === a.dataset.id); p.sit = a.dataset.para; if (a.dataset.para === 'concluida') p.noPrazo = p.off >= 0; N.fecharModal(); N.desenhar(); N.aviso('Pendência atualizada.'); };

  T.concluidas = { trilha: 'Pendências', menu: 'pendencias', render() {
    const c = cabPend('#concluidas');
    const lista = filtradas().filter((p) => p.sit === 'concluida');
    const corpo = `<section class="cartao bloco" style="margin-top:14px">${ferramentas()}<div class="tabela-rola"><table class="tab"><thead><tr><th>Pendência</th><th>Responsável</th><th>Prazo</th><th>Entrega</th></tr></thead><tbody>
      ${lista.map((p) => `<tr><td><a href="#" data-acao="pend-abrir" data-id="${p.id}">${esc(p.t)}</a></td><td>${souEu(p) ? 'Você' : esc(p.resp)}</td><td class="num">${fmt(dia(p.off))}</td><td>${N.estado(p.noPrazo ? 'e-ok' : 'e-venc', p.noPrazo ? 'No prazo' : 'Fora do prazo')}</td></tr>`).join('')}
      </tbody></table></div></section>`;
    return N.modulo(c.cab, c.resumo, c.abas, corpo);
  } };

  // ------------------------------------------------------------------ gaveta da Pendência: ações e uma conversa só
  N.acoes['pend-abrir'] = (a) => abrirPend(a.dataset.id);
  N.acoes['pend-cobrar'] = (a) => { const p = PEND.find((x) => x.id === a.dataset.id); N.aviso(`Lembrete enviado para ${p.resp.split(' ')[0]}, no app e por e-mail.`); };
  function abrirPend(id) {
    const p = PEND.find((x) => x.id === id);
    if (!p) return;
    const [cls, txt] = SIT[sitDe(p)];
    const r = reu(p.reu);
    const ativ = ATIV[p.id] || [['Sistema', 'há ' + (12 - p.off) + ' dias', 'Pendência criada a partir da Ata.', 'h']];
    const acoes = p.sit === 'concluida' ? `<button class="btn contorno" data-acao="pend-acao" data-id="${p.id}" data-msg="Pendência reaberta.">Reabrir</button>`
      : p.sit === 'contestada' && !souEu(p) ? `<button class="btn contorno" data-acao="pend-acao" data-id="${p.id}" data-msg="Contestação recusada. O prazo original continua.">Recusar</button><button class="btn" data-acao="pend-acao" data-id="${p.id}" data-msg="Novo prazo aceito." data-sit="andamento">Aceitar o novo prazo</button>`
      : souEu(p) ? `<button class="btn contorno" data-acao="pend-acao" data-id="${p.id}" data-msg="Pedido de novo prazo enviado ao Facilitador." data-sit="contestada">Pedir novo prazo</button><button class="btn" data-acao="pend-acao" data-id="${p.id}" data-msg="Pendência concluída." data-sit="concluida">Concluir</button>`
      : `<button class="btn contorno" data-acao="pend-acao" data-id="${p.id}" data-msg="Pendência cancelada, com a anotação.">Cancelar</button><button class="btn" data-acao="pend-cobrar" data-id="${p.id}">Cobrar ${esc(p.resp.split(' ')[0])}</button>`;
    N.abrirGaveta({
      sobre: `<div style="display:flex;gap:10px;align-items:center">${N.estado(cls, txt)}<span class="pill">Reunião</span></div>`,
      titulo: esc(p.t),
      corpo: `<dl class="pares"><dt>Responsável</dt><dd>${souEu(p) ? 'Você' : esc(p.resp)} · ${esc(p.setor)}</dd><dt>Prazo</dt><dd class="num">${fmt(dia(p.off))}${p.off < 0 && p.sit !== 'concluida' ? ` <span style="color:var(--verm)">(${-p.off} dias de atraso)</span>` : ''}</dd>
        ${r ? `<dt>Origem</dt><dd><a href="#reuniao-${r.id}" data-acao="fechar-gaveta-ir" data-href="#reuniao-${r.id}">${esc(r.titulo)}, ${curto(deIso(r.data))}</a></dd>` : ''}</dl>
        ${p.sit !== 'concluida' ? `<div class="campo"><label for="pd-anot">Anotação</label><textarea id="pd-anot" placeholder="O que foi feito, o que falta, ou por que mudar"></textarea></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap"><label class="btn contorno" style="cursor:pointer">${IC.anexo}Anexar arquivo<input type="file" hidden></label></div>` : ''}
        <h3 class="titulo-bloco" style="font-size:15px;margin-top:6px">Atividade</h3>
        <ul class="tempo">${ativ.map(([q, quando, txt, tipo]) => `<li class="${tipo === 'h' ? 'feito' : ''}"><i aria-hidden="true"></i><b>${esc(q)}</b><span>${quando}</span><p style="margin:4px 0 0;font-size:14.5px">${esc(txt).replace(/@([A-ZÁÉÍÓÚ][a-zà-ú]+ [A-ZÁÉÍÓÚ][a-zà-ú]+)/g, '<b style="display:inline;color:var(--acento)">@$1</b>')}</p></li>`).join('')}</ul>
        <div class="escrever"><label for="pd-msg" class="sr">Comentar</label><textarea id="pd-msg" placeholder="Comente ou marque alguém com @"></textarea><button class="btn" data-acao="pend-comentar" data-id="${p.id}" aria-label="Enviar comentário">${IC.enviar}</button></div>`,
      pe: acoes
    });
  }
  N.abrirPend = abrirPend;
  N.acoes['pend-acao'] = (a) => { const p = PEND.find((x) => x.id === a.dataset.id); if (a.dataset.sit) p.sit = a.dataset.sit; if (a.dataset.sit === 'concluida') p.noPrazo = p.off >= 0; N.acoes['fechar-gaveta'](); N.desenhar(); N.aviso(a.dataset.msg); };
  N.acoes['pend-comentar'] = (a) => { const t = document.getElementById('pd-msg').value.trim(); if (!t) return; (ATIV[a.dataset.id] = ATIV[a.dataset.id] || [['Sistema', 'há 12 dias', 'Pendência criada a partir da Ata.', 'h']]).push(['Renata Alves', 'agora', t, 'c']); abrirPend(a.dataset.id); };
  N.acoes['fechar-gaveta-ir'] = (a) => { N.acoes['fechar-gaveta'](); location.hash = a.dataset.href; };

  // ------------------------------------------------------------------ Rotinas
  const ROT = [
    { id: 'p5', t: 'Ronda de higienização das mãos', freq: 'Semanal', reu: 'r0', resp: 'Renata Alves', ciclo: 0, hist: ['ok', 'ok', 'nao', 'ok', 'ok', 'ok'] },
    { id: 'p15', t: 'Conferência dos psicotrópicos', freq: 'Semanal', reu: 'r0', resp: 'Renata Alves', ciclo: 4, hist: ['ok', 'ok', 'ok', 'ok', 'ok', 'ok'] },
    { id: 'p12', t: 'Checagem do carrinho de emergência', freq: 'Quinzenal', reu: 'r3', resp: 'Renata Alves', ciclo: 9, hist: ['ok', 'ok', 'ok', 'atr'] },
    { id: 'r9', t: 'Validade dos medicamentos da farmácia satélite', freq: 'Mensal', reu: 'r0', resp: 'Rodrigo Sales', ciclo: -2, hist: ['ok', 'nao', 'atr'] },
    { id: 'r10', t: 'Auditoria do checklist de cirurgia segura', freq: 'Mensal', reu: 'r3', resp: 'Carla Nogueira', ciclo: 11, hist: ['ok', 'ok', 'ok'] }
  ];
  T.rotinas = { trilha: 'Rotinas', menu: 'rotinas', render() {
    const minhas = ROT.filter((r) => r.resp === 'Renata Alves');
    const abertas = ROT.filter((r) => !est.mt.rot[r.id]);
    const corpo = `<div class="grade g2">${ROT.map((r) => { const feito = est.mt.rot[r.id]; const eu = r.resp === 'Renata Alves';
      const [cls, txt] = feito ? ['e-ok', feito === 'ok' ? 'Realizada neste ciclo' : 'Não realizada, com anotação'] : r.ciclo < 0 ? ['e-venc', 'Ciclo vencido'] : r.ciclo === 0 ? ['e-hoje', 'Vence hoje'] : ['e-prox', `Verificar até ${curto(dia(r.ciclo))}`];
      return `<section class="cartao bloco">
        <div class="cab"><span class="pill">${r.freq}</span>${N.estado(cls, txt)}</div>
        <h2 class="titulo-bloco" style="margin-top:10px">${esc(r.t)}</h2>
        <p class="sub" style="margin:4px 0 0">${eu ? 'Você é a responsável' : 'Responsável: ' + esc(r.resp)} · ${esc(reu(r.reu).titulo)}</p>
        <div style="display:flex;gap:6px;margin-top:14px" aria-label="Últimos ciclos">${r.hist.map((h) => `<span title="${h === 'ok' ? 'Realizada' : h === 'nao' ? 'Não realizada' : 'Atrasada'}" style="width:26px;height:8px;border-radius:999px;background:${h === 'ok' ? 'var(--verde)' : h === 'nao' ? 'var(--ponto-laranja)' : 'var(--ponto-verm)'}"></span>`).join('')}<span class="sub" style="margin-left:6px">últimos ciclos</span></div>
        ${!feito && eu ? `<div class="acoes-item" style="margin-top:14px"><button class="btn" data-acao="rot-marca" data-id="${r.id}" data-v="ok">Realizada</button><button class="btn contorno" data-acao="rot-nao" data-id="${r.id}">Não realizada</button></div>` : ''}
        ${!feito && !eu ? `<div class="acoes-item" style="margin-top:14px"><button class="btn contorno" data-acao="toast" data-msg="Lembrete enviado para ${esc(r.resp.split(' ')[0])}.">Lembrar ${esc(r.resp.split(' ')[0])}</button><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre a escolha da frequência.">Mudar frequência</button></div>` : ''}
      </section>`; }).join('')}</div>`;
    return N.modulo({ sobre: 'Meu trabalho', titulo: 'Rotinas', frase: `${minhas.length} Rotinas no seu nome e ${ROT.length - minhas.length} das Reuniões que você conduz. ${abertas.filter((r) => r.ciclo <= 0).length} pedem a Verificação hoje.` },
      [['Ciclos vencidos', String(ROT.filter((r) => r.ciclo < 0 && !est.mt.rot[r.id]).length).padStart(2, '0'), I.alerta, '#rotinas', true], ['Vencem hoje', String(ROT.filter((r) => r.ciclo === 0 && !est.mt.rot[r.id]).length).padStart(2, '0'), I.relogio, '#rotinas'], ['Realizadas em 90 dias', '94%', I.certo, '#dashboard']],
      '', corpo);
  } };
  N.acoes['rot-marca'] = (a) => { est.mt.rot[a.dataset.id] = a.dataset.v; N.desenhar(); N.aviso('Verificação marcada como Realizada.'); };
  N.acoes['rot-nao'] = (a) => N.modal('Não realizada', `<div class="campo"><label for="rt-mot">Por que não foi realizada?</label><textarea id="rt-mot"></textarea></div>`, `<button type="button" class="btn" data-acao="rot-nao-ok" data-id="${a.dataset.id}">Registrar</button>`);
  N.acoes['rot-nao-ok'] = (a) => { est.mt.rot[a.dataset.id] = 'nao'; N.fecharModal(); N.desenhar(); N.aviso('Verificação registrada como Não realizada, com a anotação.'); };

  // ------------------------------------------------------------------ Calendário: mês, semana e lista, com a Reunião numa gaveta
  est.mt.calVista = 'mes'; est.mt.calDesloc = 0;
  const COR = { programada: ['pill', 'Programada'], ata: ['pill laranja', 'Ata em validação'], assinatura: ['pill laranja', 'Aguardando assinatura'], assinada: ['pill verde', 'Assinada'], aprovada: ['pill verde', 'Aprovada'] };
  const estadoReu = (r) => difDias(deIso(r.data)) >= 0 ? 'programada' : r.ata.startsWith('Aguardando') ? 'assinatura' : 'assinada';
  T.calendario = { trilha: 'Calendário', menu: 'calendario', render() {
    const base = new Date(HOJE.getFullYear(), HOJE.getMonth() + est.mt.calDesloc, 1);
    const MES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
    const V = [['mes', 'Mês'], ['semana', 'Semana'], ['lista', 'Lista']];
    let miolo = '';
    if (est.mt.calVista === 'lista') {
      const ord = [...reunioes].sort((a, b) => (a.data + a.hora).localeCompare(b.data + b.hora));
      miolo = `<ul class="linhas">${ord.map((r) => { const [c, t] = COR[estadoReu(r)]; return `<li class="linha" style="grid-template-columns:120px minmax(0,1fr) 170px 110px"><span class="num">${curto(deIso(r.data))}, ${r.hora}</span><span class="t">${esc(r.titulo)}<small>${r.papel === 'facilitador' ? 'Você conduz' : 'Você participa'} · ${r.participantes.length} pessoas</small></span><span class="${c}">${t}</span><button class="btn contorno" data-acao="reu-gaveta" data-id="${r.id}" data-previa="${N.previaReuniao(r)}">Ver</button></li>`; }).join('')}</ul>`;
    } else {
      const ini = new Date(base); ini.setDate(1 - ((base.getDay() + 6) % 7));
      let dias = [];
      if (est.mt.calVista === 'semana') { const s = new Date(HOJE); s.setDate(HOJE.getDate() - ((HOJE.getDay() + 6) % 7) + est.mt.calDesloc * 7); for (let i = 0; i < 7; i++) { const d = new Date(s); d.setDate(s.getDate() + i); dias.push(d); } }
      else { for (let i = 0; i < 42; i++) { const d = new Date(ini); d.setDate(ini.getDate() + i); dias.push(d); } if (!dias.slice(35).some((d) => d.getMonth() === base.getMonth())) dias = dias.slice(0, 35); }
      miolo = `<div class="cal">${['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'].map((s) => `<div class="dsem">${s}</div>`).join('')}
        ${dias.map((d) => { const evs = reunioes.filter((r) => r.data === iso(d)).sort((a, b) => a.hora.localeCompare(b.hora));
          return `<div class="dia ${est.mt.calVista === 'mes' && d.getMonth() !== base.getMonth() ? 'fora' : ''} ${iso(d) === iso(HOJE) ? 'hoje' : ''}" style="${est.mt.calVista === 'semana' ? 'min-height:260px' : ''}">
            <button type="button" class="dia-num" data-acao="agendar" data-dia="${iso(d)}" aria-label="Agendar em ${fmt(d)}"><b class="num">${d.getDate()}</b></button>
            ${evs.map((r) => `<a class="ev" href="#" data-acao="reu-gaveta" data-id="${r.id}" data-previa="${N.previaReuniao(r)}" style="${estadoReu(r) !== 'programada' ? 'background:var(--suave);color:var(--texto2)' : ''}">${r.hora} ${esc(r.titulo)}</a>`).join('')}</div>`; }).join('')}</div>`;
    }
    const titulo = est.mt.calVista === 'lista' ? 'Todas as Reuniões' : `${cap(MES[base.getMonth()])} de ${base.getFullYear()}`;
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas"><div style="display:flex;align-items:center;gap:8px">
        ${est.mt.calVista !== 'lista' ? `<button class="pg-btn" data-acao="cal-mover" data-v="-1" aria-label="Anterior"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M15 6l-6 6 6 6"/></svg></button><button class="btn contorno" data-acao="cal-mover" data-v="0">Hoje</button><button class="pg-btn" data-acao="cal-mover" data-v="1" aria-label="Próximo"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M9 6l6 6-6 6"/></svg></button>` : ''}
        <h2 class="titulo-bloco" style="margin-left:6px">${titulo}</h2></div>
        <div class="modelos" role="group" aria-label="Forma de ver">${V.map(([k, t]) => `<button type="button" data-acao="cal-vista" data-v="${k}" aria-pressed="${est.mt.calVista === k}">${t}</button>`).join('')}</div></div>
      ${miolo}
      <div class="legenda" style="flex-wrap:wrap"><span><i style="background:var(--pill-fundo)"></i>Programada</span><span><i style="background:var(--suave);border:1px solid var(--borda)"></i>Já aconteceu</span><span>Passe o mouse numa Reunião para o resumo; clique para a pauta e as Pendências. Clique num dia para agendar.</span></div>
    </section>`;
    return N.modulo({ sobre: 'Meu trabalho', titulo: 'Calendário', frase: 'As Reuniões que você conduz ou participa. Clique numa Reunião para ver o resumo sem sair do mês.',
      acoes: `<button class="btn claro grande" data-acao="agendar">Agendar Reunião</button><button class="btn vidro grande" data-acao="toast" data-msg="No sistema, abre o envio da Transcrição de uma Reunião que já aconteceu.">Importar Transcrição</button>` }, null, '', corpo);
  } };
  N.acoes['cal-vista'] = (a) => { est.mt.calVista = a.dataset.v; est.mt.calDesloc = 0; N.desenhar(); };
  N.acoes['cal-mover'] = (a) => { est.mt.calDesloc = a.dataset.v === '0' ? 0 : est.mt.calDesloc + Number(a.dataset.v); N.desenhar(); };
  N.acoes['reu-gaveta'] = (a) => {
    const r = reu(a.dataset.id); const [c, t] = COR[estadoReu(r)];
    const pend = PEND.filter((p) => p.reu === r.id && p.sit !== 'concluida');
    N.abrirGaveta({ sobre: `<span class="${c}">${t}</span>`, titulo: esc(r.titulo),
      corpo: `<dl class="pares"><dt>Quando</dt><dd>${N.longo(deIso(r.data))}, ${r.hora}</dd><dt>Seu papel</dt><dd>${r.papel === 'facilitador' ? 'Você conduz' : 'Você participa'}</dd><dt>Ata</dt><dd>${esc(r.ata)}</dd></dl>
        <div><h3 class="titulo-bloco" style="font-size:15px">Pauta</h3><ol style="margin:8px 0 0;padding-left:20px">${r.pauta.map((x) => `<li>${esc(x)}</li>`).join('')}</ol></div>
        <div><h3 class="titulo-bloco" style="font-size:15px">Participantes</h3><p style="margin:6px 0 0">${r.participantes.map(esc).join(', ')}</p></div>
        ${pend.length ? `<div><h3 class="titulo-bloco" style="font-size:15px">Pendências em aberto desta Reunião</h3><ul class="linhas">${pend.map((p) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">${esc(p.t)}<small>${esc(p.resp)}</small></span>${N.estado(...SIT[sitDe(p)])}</li>`).join('')}</ul></div>` : ''}`,
      pe: `<a class="btn grande" href="#reuniao-${r.id}" data-acao="fechar-gaveta-ir" data-href="#reuniao-${r.id}">Abrir a Reunião</a>` });
  };
})();
