/* Contas médicas: Painel, Esteira, Mesa de trabalho, Validação, Coordenação, Contratos,
   Operadoras, Memória da operadora e Habilitação. Pacientes sempre fictícios, só o rótulo. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I, IC, dia, curto, est } = N;
  const T = N.telas;
  const R$ = (v) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const nota = (v) => v.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  est.cm = { busca: '', recorte: 'todas', etapa: 'fila', feitos: {}, vez: null, regra: 'diarias', semana: 'esta', operadoras: [], perms: {}, pessoaBusca: '', arq: {} };

  N.css(`
.cm-faixa{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-top:14px}
.cm-mesa{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:14px;margin-top:14px;align-items:start}
.cm-vez{position:sticky;top:12px}
.cm-dia{margin-top:16px}
.cm-dia h3{display:flex;justify-content:space-between;align-items:center;margin:0 0 6px;font-size:13px;letter-spacing:.05em;text-transform:uppercase;color:var(--texto2)}
.cm-item{display:grid;grid-template-columns:22px minmax(0,1fr) 110px 120px;gap:12px;align-items:center;width:100%;padding:10px 8px;border:0;border-bottom:1px solid var(--linha);background:transparent;text-align:left;cursor:pointer;color:var(--texto);font:inherit;border-radius:6px}
.cm-item:hover{background:var(--suave)}
.cm-item.vez{background:var(--suave2)}
.cm-item .marca{display:block;width:18px;height:18px;border-radius:999px;border:2px solid var(--campo-borda)}
.cm-item .marca.ok{background:var(--verde);border-color:var(--verde)}
.cm-item .marca.nao{background:var(--texto2);border-color:var(--texto2)}
.cm-item .t{font-size:14.5px}
.cm-item .t small{display:block;font-size:12.5px;color:var(--texto2)}
.cm-evid{padding:12px 14px;border-radius:8px;background:var(--suave);font-size:14px;border-left:3px solid var(--acento)}
.cm-rodape{position:sticky;bottom:0;z-index:5;display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:16px;padding:12px 16px;background:var(--cartao);border:1px solid var(--borda);border-radius:10px;box-shadow:var(--sombra-alta)}
.cm-rodape input{flex:1 1 280px;min-height:42px;padding:0 12px;border:1px solid var(--campo-borda);border-radius:8px;background:var(--campo);color:var(--texto)}
.cm-matriz td,.cm-matriz th{text-align:center}
.cm-matriz td:first-child,.cm-matriz th:first-child{text-align:left}
.cm-tog{width:44px;height:26px;border-radius:999px;border:0;background:var(--suave2);position:relative;cursor:pointer}
.cm-tog::after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:999px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:left .15s ease}
.cm-tog[aria-pressed="true"]{background:var(--btn-fundo)}
.cm-tog[aria-pressed="true"]::after{left:21px}
.cm-barra{display:grid;grid-template-columns:150px minmax(0,1fr) 90px;gap:10px;align-items:center;margin-top:10px;font-size:14px}
@media (max-width:1100px){.cm-mesa{grid-template-columns:1fr}.cm-vez{position:static}}
`);

  // ------------------------------------------------------------------ dados de demonstração
  const EU = 'Bruno Araújo';
  const OPER = [
    { s: 'SMS', n: 'Saúde Mais', mem: '2.3', tabelas: 4, situ: 'ok', venc: 210, adit: 1 },
    { s: 'VPL', n: 'Vida Plena', mem: '1.8', tabelas: 4, situ: 'ok', venc: 38, adit: 2 },
    { s: 'UNM', n: 'Unimédica Rio', mem: '3.0', tabelas: 3, situ: 'tabela', venc: 12, adit: 0 },
    { s: 'AMP', n: 'Ampara Saúde', mem: '1.2', tabelas: 4, situ: 'ok', venc: -6, adit: 1 },
    { s: 'CDS', n: 'Cuidar Seguros', mem: null, tabelas: 1, situ: 'sem', venc: 320, adit: 0 }
  ];
  const op = (s) => OPER.find((o) => o.s === s);
  // etapa: envio | fila | analise | concluida | pend (concluída com pendência)
  const CONTAS = [
    { id: 'e1', at: '2791', rot: 'Marcos V.', idade: 54, op: 'SMS', etapa: 'envio', envio: 'Falta o Prontuário', valor: 0, por: 'Jéssica Ramos' },
    { id: 'e2', at: '2790', rot: 'Helena P.', idade: 71, op: 'VPL', etapa: 'envio', envio: 'Processando', valor: 0, por: 'Jéssica Ramos' },
    { id: 'e3', at: '2786', rot: 'Rui C.', idade: 38, op: 'CDS', etapa: 'envio', envio: 'Erro: plano "CUIDAR EXECUTIVO" sem operadora', valor: 0, por: 'Jéssica Ramos' },
    { id: 'c2775', at: '2775', rot: 'Antônia F.', idade: 67, op: 'SMS', etapa: 'analise', com: EU, valor: 18432.9, ini: -9, fim: -4, nota: 6.8 },
    { id: 'c2781', at: '2781', rot: 'José R.', idade: 45, op: 'VPL', etapa: 'fila', valor: 6210.4, ini: -6, fim: -3, nota: 7.9 },
    { id: 'c2779', at: '2779', rot: 'Lúcia M.', idade: 82, op: 'AMP', etapa: 'fila', valor: 31870.0, ini: -15, fim: -5, nota: 5.9 },
    { id: 'c2783', at: '2783', rot: 'Pedro H.', idade: 29, op: 'SMS', etapa: 'fila', valor: 2140.75, ini: -3, fim: -2, nota: 8.6 },
    { id: 'c2784', at: '2784', rot: 'Sandra L.', idade: 61, op: 'UNM', etapa: 'fila', valor: 9988.3, ini: -8, fim: -2, nota: 7.1 },
    { id: 'c2770', at: '2770', rot: 'Wagner S.', idade: 58, op: 'VPL', etapa: 'analise', com: 'Daniela Costa', valor: 12400.0, ini: -12, fim: -7, nota: 7.4 },
    { id: 'c2768', at: '2768', rot: 'Ivone T.', idade: 76, op: 'AMP', etapa: 'analise', com: 'Patrícia Melo', valor: 22750.6, ini: -14, fim: -6, nota: 6.2 },
    { id: 'c2760', at: '2760', rot: 'Caio B.', idade: 33, op: 'SMS', etapa: 'concluida', com: EU, valor: 4310.0, ajuste: 512.4, comp: 'novembro de 2026', nota: 8.1 },
    { id: 'c2757', at: '2757', rot: 'Rosa A.', idade: 69, op: 'VPL', etapa: 'pend', com: 'Daniela Costa', valor: 15020.0, ajuste: 1880.0, comp: 'novembro de 2026', nota: 6.9 },
    { id: 'c2741', at: '2741', rot: 'Elias N.', idade: 50, op: 'UNM', etapa: 'concluida', com: 'Patrícia Melo', valor: 8790.0, ajuste: 230.0, comp: 'outubro de 2026', nota: 8.8 },
    { id: 'c2733', at: '2733', rot: 'Teresa G.', idade: 88, op: 'AMP', etapa: 'concluida', com: EU, valor: 40110.0, ajuste: 3420.15, comp: 'outubro de 2026', nota: 5.4 },
    { id: 'c2702', at: '2702', rot: 'Nilton F.', idade: 47, op: 'SMS', etapa: 'concluida', com: EU, valor: 3900.0, ajuste: 0, comp: 'setembro de 2026', nota: 9.2, arq: true }
  ];
  CONTAS.forEach((c) => { if (c.arq) est.cm.arq[c.id] = true; });
  const conta = (id) => CONTAS.find((c) => c.id === id);
  const ITENS = {
    c2775: [
      { id: 'i1', d: -9, setor: 'Pronto-socorro', t: 'Consulta de emergência', o: 'Código', tipo: 'Conferido', valor: 0, evid: 'Conta, página 1: consulta cobrada uma vez, como a regra da Saúde Mais pede.', dec: 'ok' },
      { id: 'i2', d: -8, setor: 'UTI adulto', t: 'Equipo macrogotas', o: 'IA', tipo: 'Falta na conta', valor: 18.4, evid: 'Prontuário, página 6: "instalado equipo macrogotas em acesso periférico às 03h10". A conta deste dia não traz o equipo.' },
      { id: 'i3', d: -8, setor: 'UTI adulto', t: 'Glicemia capilar (4 no dia, 2 cobradas)', o: 'Código', tipo: 'Falta na conta', valor: 24.0, evid: 'Prontuário, página 7: glicemias às 06h, 12h, 18h e 24h. A conta cobra só duas.' },
      { id: 'i4', d: -7, setor: 'UTI adulto', t: 'Oxigênio, 12 horas', o: 'Código', tipo: 'Falta na conta', valor: 96.0, evid: 'Prescrição de 07/11: O2 por cateter nasal 3 L/min contínuo. O gás não aparece na conta.' },
      { id: 'i5', d: -7, setor: 'UTI adulto', t: 'Diária de UTI cobrada em dobro', o: 'Código', tipo: 'Cobrado a mais', valor: -1450.0, evid: 'Conta, página 3: duas diárias de UTI no mesmo dia. A memória da Saúde Mais (regra 2.1) aceita uma.' },
      { id: 'i6', d: -6, setor: 'Enfermaria', t: 'Dipirona 1 g injetável', o: 'Código', tipo: 'Preço fora da tabela', valor: 3.12, evid: 'Tabela de medicamentos da Saúde Mais, versão de outubro: R$ 7,80. A conta cobra R$ 4,68.' },
      { id: 'i7', d: -5, setor: 'Enfermaria', t: 'Curativo de média complexidade', o: 'IA', tipo: 'Falta na conta', valor: 42.5, evid: 'Evolução de enfermagem, página 11: "realizado curativo em lesão sacral com placa de hidrocoloide".' },
      { id: 'i8', d: -4, setor: 'Enfermaria', t: 'Alta: taxa de sala de observação', o: 'IA', tipo: 'Dúvida', valor: 0, evid: 'A conta cobra a taxa de observação no dia da alta. Na memória da Saúde Mais a taxa só vale até 6 horas de permanência; o prontuário não diz a hora da alta.' }
    ]
  };
  const itensDe = (id) => ITENS[id] || ITENS.c2775.map((x) => ({ ...x }));
  const decisao = (cid, it) => est.cm.feitos[cid + it.id] || it.dec || null;
  // Prévias no hover: ajudam a decidir antes de clicar; o clique continua sendo o caminho.
  function previaConta(c) {
    const e = est.cm.arq[c.id] ? 'Arquivada' : { envio: 'Envio', fila: 'Fila', analise: 'Em análise', concluida: 'Concluída', pend: 'Concluída com pendência' }[c.etapa];
    const its = c.etapa === 'envio' ? [] : itensDe(c.id);
    const faltam = its.filter((it) => !decisao(c.id, it)).length;
    const quem = c.com ? (c.com === EU ? 'com você' : 'com ' + esc(c.com)) : c.etapa === 'fila' ? 'livre, ninguém pegou' : 'enviada por ' + esc(c.por || '');
    const dica = c.etapa === 'fila' ? 'Clique em Pegar para abrir a Mesa' : c.etapa === 'analise' && c.com === EU ? 'Clique em Continuar para voltar à Mesa' : c.etapa === 'envio' ? 'Clique em Resolver para ver o envio' : 'A conta abre pela Mesa de trabalho';
    return esc(`<b>Conta ${c.at} · ${esc(op(c.op).n)}</b><span class="sub">${e} · ${quem}</span><span class="sub">${c.comp ? 'Competência ' + esc(c.comp) : c.ini ? 'Internação de ' + curto(dia(c.ini)) + ' a ' + curto(dia(c.fim)) : 'Guia ainda não pronto'}</span>${c.valor ? `<span class="sub">Valor da conta ${R$(c.valor)}${c.ajuste !== undefined ? ' · ajuste ' + R$(c.ajuste) : ''}</span>` : ''}${its.length ? `<span class="sub">${faltam ? faltam + ' de ' + its.length + ' itens ainda sem decisão' : 'Todos os ' + its.length + ' itens decididos'}</span>` : ''}<span class="dica">${dica}</span>`);
  }
  function previaContrato(o) {
    return esc(`<b>${esc(o.n)}</b><span class="sub">Vigência de ${N.fmt(dia(o.venc - 365))} a ${N.fmt(dia(o.venc))}</span><span class="sub">${o.adit ? o.adit + (o.adit === 1 ? ' aditivo assinado' : ' aditivos assinados') : 'Nenhum aditivo'}</span><span class="sub">${o.venc < 0 ? 'Venceu há ' + -o.venc + ' dias: as contas seguem pela tabela antiga' : 'Faltam ' + o.venc + ' dias para vencer'}</span><span class="dica">${o.venc <= 45 ? 'Clique em Enviar aditivo: a IA preenche e você confirma' : 'Clique em Enviar documento para juntar um anexo'}</span>`);
  }
  function previaOper(o) {
    const naFila = CONTAS.filter((c) => c.op === o.s && c.etapa === 'fila').length;
    return esc(`<b>${esc(o.n)} (${o.s})</b><span class="sub">${o.mem ? 'Memória v' + o.mem : 'Sem memória: as contas param no envio'}</span><span class="sub">${o.tabelas} de 4 tabelas de preço</span><span class="sub">${naFila} ${naFila === 1 ? 'conta' : 'contas'} na Fila · contrato ${o.venc < 0 ? 'vencido' : 'vigente'}</span><span class="dica">Clique para abrir a Memória da operadora</span>`);
  }

  // ------------------------------------------------------------------ cabeçalho e abas
  const ABAS = () => N.abasModulo([
    ['#contas', 'Painel'], ['#contasesteira', 'Esteira', CONTAS.filter((c) => c.etapa === 'fila').length],
    ['#contasvalidacao', 'Validação', 6], ['#contascoordenacao', 'Coordenação', 4],
    ['#contascontratos', 'Contratos', OPER.filter((o) => o.venc < 45).length, OPER.some((o) => o.venc < 0)],
    ['#contasoperadoras', 'Operadoras'], ['#contashabilitacao', 'Habilitação']], ({ '#contasoperadora': '#contasoperadoras', '#contasguia': '#contasesteira' })[location.hash.split('-')[0]] || location.hash.split('-')[0] || '#contas');
  const cab = (titulo, frase, acoes) => ({ sobre: 'Contas médicas', titulo, frase, acoes });

  // ------------------------------------------------------------------ Painel
  T.contas = { trilha: 'Contas médicas', menu: 'contas', mapa: ['Contas médicas', 'Painel'], render() {
    const S = [['esta', 'Esta semana'], ['passada', 'Semana passada'], ['mes', 'Últimas 4 semanas']];
    const O = OPER.map((o) => [o.s, o.n]);
    const selOp = est.cm.operadoras;
    const nomesOp = selOp.length ? OPER.filter((o) => selOp.includes(o.s)).map((o) => o.n).join(', ') : 'todas as operadoras';
    const perda = [['UTI adulto', 9840, 100], ['Centro cirúrgico', 6120, 62], ['Enfermaria', 3310, 34], ['Pronto-socorro', 1270, 13]];
    const faltam = [['Glicemia capilar', 38, 912.0], ['Oxigênio contínuo', 21, 2016.0], ['Equipo macrogotas', 19, 349.6], ['Curativo de média complexidade', 14, 595.0], ['Taxa de sala de observação', 12, 1080.0], ['Dipirona 1 g injetável', 11, 34.32], ['Bomba de infusão, diária', 9, 1170.0], ['Ficha anestésica sem gás', 8, 2240.0], ['Sonda vesical de demora', 6, 222.0], ['Eletrodo descartável', 6, 21.6]];
    const prod = [['Bruno Araújo', 31, 7.6], ['Daniela Costa', 28, 7.9], ['Patrícia Melo', 24, 7.2]];
    const corpo = `<section class="cartao bloco" style="margin-top:14px"><div class="ferramentas">
        <div class="filtros-linha">${N.filtro({ id: 'cm-semana', rotulo: 'Período', opcoes: S, valor: est.cm.semana, acao: 'cm-semana' })}${N.filtro({ id: 'cm-oper', rotulo: 'Operadora', opcoes: O, multi: true, obj: 'cm', campo: 'operadoras', todos: 'Todas as operadoras' })}</div>
        <p class="sub" style="margin:0">Números de ${S.find(([k]) => k === est.cm.semana)[1].toLowerCase()}, ${esc(nomesOp)}.</p></div></section>
      <div class="grade g2">
        <section class="cartao bloco"><h2 class="titulo-bloco">Onde a perda nasce</h2><p class="sub" style="margin:4px 0 0">O que entrou de ajuste, por setor da conta.</p>
          ${perda.map(([s, v, p]) => `<div class="cm-barra"><span>${s}</span><div class="prog"><span style="width:${p}%"></span></div><span class="num" style="text-align:right">${R$(v)}</span></div>`).join('')}</section>
        <section class="cartao bloco"><div class="cab"><h2 class="titulo-bloco">Segundo agente</h2><span class="pill cinza">Custo de IA: ${R$(41.8)} na semana</span></div>
          <p style="margin:10px 0 0">Relê as contas concluídas e aponta o que o primeiro passo deixou passar. Na semana passada achou <b>12 itens</b> em 9 contas, ${R$(1840.0)} a recuperar.</p>
          <div class="acoes-item" style="margin-top:14px"><button class="btn" data-acao="cm-reler">Reler contas concluídas</button><a class="btn contorno" href="#contasvalidacao">Ver o que ele achou</a></div></section>
      </div>
      <div class="duas" style="margin-top:14px">
        <section class="cartao bloco larga"><h2 class="titulo-bloco">Os 10 itens que mais faltam</h2>
          <div class="tabela-rola"><table class="tab"><thead><tr><th>Item</th><th>Vezes</th><th>R$ recuperado</th><th></th></tr></thead><tbody>
          ${faltam.map(([t, n, v]) => `<tr><td>${t}</td><td class="num">${n}</td><td class="num">${R$(v)}</td><td style="text-align:right"><button class="btn contorno" data-acao="cm-item-painel" data-t="${esc(t)}" data-n="${n}">Ver as contas</button></td></tr>`).join('')}
          </tbody></table></div></section>
        <aside class="estreita">
          <section class="cartao bloco"><h2 class="titulo-bloco">Produção por faturista</h2>
            ${prod.map(([n, q, m]) => `<div style="margin-top:12px"><div style="display:flex;justify-content:space-between;font-size:14px"><span>${n === EU ? 'Você' : n}</span><span class="num sub">${q} contas · nota média ${nota(m)}</span></div><div class="prog" style="margin-top:6px"><span style="width:${q / 31 * 100}%"></span></div></div>`).join('')}</section>
          <section class="cartao bloco"><h2 class="titulo-bloco">R$ por evidência</h2>
            <dl class="pares" style="margin-top:10px"><dt>Prescrição</dt><dd class="num">${R$(5820.0)}</dd><dt>Evolução de enfermagem</dt><dd class="num">${R$(3940.5)}</dd><dt>Ficha anestésica</dt><dd class="num">${R$(2240.0)}</dd><dt>Tabela de preço</dt><dd class="num">${R$(1310.2)}</dd><dt>Memória da operadora</dt><dd class="num">${R$(4350.0)}</dd></dl></section>
        </aside>
      </div>`;
    return N.modulo(cab('Painel', 'Esta semana 83 contas foram concluídas e o ajuste somou ' + R$(20540.0) + '. A UTI adulto concentra quase metade da perda.'),
      [['Nota da semana', nota(7.6), I.certo, '#contas'], ['Recuperado na semana', 'R$ 20,5 mil', I.agenda, '#contas'], ['Na Fila agora', String(CONTAS.filter((c) => c.etapa === 'fila').length).padStart(2, '0'), I.relogio, '#contasesteira'], ['Temas para validar', '06', I.alerta, '#contasvalidacao', true]],
      ABAS(), corpo);
  } };
  N.acoes['cm-semana'] = (a) => { est.cm.semana = a.dataset.v; N.desenhar(); };
  N.acoes['cm-reler'] = () => N.modal('Reler contas concluídas', `<p style="margin:0 0 10px">O segundo agente relê as <b>83 contas</b> concluídas nesta semana e aponta o que ficou para trás.</p>
    <dl class="pares"><dt>Custo estimado</dt><dd class="num"><b>${R$(38.9)}</b> de IA</dd><dt>Tempo</dt><dd>cerca de 40 minutos, sem travar a Esteira</dd><dt>Resultado</dt><dd>os achados chegam na Validação</dd></dl>`,
    `<button type="button" class="btn" data-acao="toast" data-msg="Releitura começou. Você recebe um aviso quando os achados chegarem na Validação.">Reler por ${R$(38.9)}</button>`);
  N.acoes['cm-item-painel'] = (a) => N.abrirGaveta({ sobre: '<span class="pill">Item que mais falta</span>', titulo: esc(a.dataset.t),
    corpo: `<p class="sub" style="margin:0">Apareceu em ${a.dataset.n} contas no período.</p><ul class="linhas">${CONTAS.filter((c) => (c.etapa === 'concluida' || c.etapa === 'pend') && N.passa(est.cm.operadoras, c.op)).map((c) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">${c.at} · ${esc(c.rot)}<small>${op(c.op).n} · ${c.com === EU ? 'Você' : esc(c.com)}</small></span><span class="pill">${esc(c.comp)}</span></li>`).join('')}</ul>` });

  // ------------------------------------------------------------------ Esteira
  const ETAPAS = [['envio', 'Envios'], ['fila', 'Fila'], ['analise', 'Em análise'], ['concluida', 'Concluídas'], ['arquivada', 'Arquivadas']];
  const etapaDe = (c) => est.cm.arq[c.id] ? 'arquivada' : c.etapa === 'pend' ? 'concluida' : c.etapa;
  const NOME_ETAPA = { envio: 'Envios', fila: 'Fila', analise: 'Em análise', concluida: 'Concluídas', arquivada: 'Arquivadas' };
  T.contasesteira = { trilha: 'Contas médicas', menu: 'contasesteira', mapa: ['Contas médicas', 'Esteira das contas'], render() {
    const t = est.cm.busca.trim().toLowerCase();
    const base = CONTAS.filter((c) => (est.cm.recorte === 'todas' || c.com === EU || (c.etapa === 'envio')) && N.passa(est.cm.operadoras, c.op));
    const conta_ = (k) => base.filter((c) => etapaDe(c) === k).length;
    const minha = CONTAS.find((c) => c.etapa === 'analise' && c.com === EU);
    let lista;
    if (t) {
      const achadas = CONTAS.filter((c) => (c.at + ' ' + c.rot).toLowerCase().includes(t) && N.passa(est.cm.operadoras, c.op));
      lista = `<p class="sub" style="margin:8px 0 0">${achadas.length ? `${achadas.length} ${achadas.length === 1 ? 'conta encontrada' : 'contas encontradas'} em todas as etapas, inclusive as arquivadas.` : 'Nenhuma conta com esse número ou rótulo.'}</p>
        <ul class="linhas">${achadas.map((c) => `<li class="linha" style=""grid-template-columns:90px minmax(0,1fr) 150px 160px 120px"><b class="num" style="color:var(--titulo)">${c.at}</b><span class="t" tabindex="0" data-previa="${previaConta(c)}">${esc(c.rot)}, ${c.idade} anos<small>${op(c.op).n}</small></span><span class="pill">${NOME_ETAPA[etapaDe(c)]}</span><span class="sub">${c.com ? (c.com === EU ? 'Com você' : 'Com ' + esc(c.com)) : c.etapa === 'fila' ? 'Livre' : 'Enviada por ' + esc(c.por || '')}</span>${acaoConta(c)}</li>`).join('')}</ul>`;
    } else lista = listaEtapa(base.filter((c) => etapaDe(c) === est.cm.etapa));
    const corpo = `${minha ? `<section class="cartao bloco" style="margin-top:14px;display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:space-between">
        <div><span class="rot-mini">Continue de onde parou</span><h2 class="titulo-bloco" style="margin-top:4px">${minha.at} · ${esc(minha.rot)}, ${op(minha.op).n}</h2><p class="sub" style="margin:2px 0 0">${itensDe(minha.id).filter((it) => decisao(minha.id, it)).length} de ${itensDe(minha.id).length} itens decididos</p></div>
        <a class="btn grande" href="#contasguia-${minha.id}">Voltar à conta</a></section>` : ''}
      <section class="cartao bloco" style="margin-top:14px">
        <div class="ferramentas">
          <label class="busca-lista">${IC.busca}<span class="sr">Buscar conta</span><input id="cm-busca" data-digita="cm-busca" type="search" placeholder="Atendimento ou paciente, ex.: 2775" value="${esc(est.cm.busca)}"></label>
          <div class="filtros-linha">${N.filtro({ id: 'cm-recorte', rotulo: 'De quem', opcoes: [['todas', 'Todas'], ['minhas', 'Minhas']], valor: est.cm.recorte, acao: 'cm-recorte' })}${N.filtro({ id: 'cm-oper-est', rotulo: 'Operadora', opcoes: OPER.map((o) => [o.s, o.n]), multi: true, obj: 'cm', campo: 'operadoras', todos: 'Todas as operadoras' })}</div>
        </div>
        ${t ? '' : `<div class="abas" role="tablist" aria-label="Etapas da Esteira">${ETAPAS.map(([k, x]) => `<button type="button" role="tab" aria-selected="${est.cm.etapa === k}" data-acao="cm-etapa" data-v="${k}">${x} (${conta_(k)})</button>`).join('')}</div>`}
        ${lista}
      </section>`;
    return N.modulo(cab('Esteira das contas', `${conta_('fila')} contas livres na Fila, a mais antiga enviada há 5 dias. ${CONTAS.filter((c) => c.etapa === 'envio').length} envios ainda não ficaram prontos.`,
      `<button class="btn claro grande" data-acao="cm-enviar">Enviar contas</button>`),
      [['Livres na Fila', String(conta_('fila')).padStart(2, '0'), I.relogio, '#contasesteira'], ['Com você', String(CONTAS.filter((c) => c.etapa === 'analise' && c.com === EU).length).padStart(2, '0'), I.agenda, '#contasesteira'], ['Envios com problema', '02', I.alerta, '#contasesteira', true], ['Concluídas no mês', '41', I.certo, '#contas']],
      ABAS(), corpo);
  }, depois() {
    // Soltar o PDF em qualquer ponto da Esteira abre o envio.
    const area = document.getElementById('conteudo');
    area.ondragover = (e) => { if (e.dataTransfer && [...e.dataTransfer.types].includes('Files')) e.preventDefault(); };
    area.ondrop = (e) => { if (e.dataTransfer && e.dataTransfer.files.length) { e.preventDefault(); N.acoes['cm-enviar'](null, e.dataTransfer.files.length); } };
  } };
  function acaoConta(c) {
    const e = etapaDe(c);
    if (e === 'fila') return `<a class="btn" href="#contasguia-${c.id}" data-acao="cm-pegar" data-id="${c.id}">Pegar</a>`;
    if (e === 'analise') return c.com === EU ? `<a class="btn" href="#contasguia-${c.id}">Continuar</a>` : `<span class="sub">Só ${esc(c.com.split(' ')[0])} abre</span>`;
    if (e === 'envio') return `<button class="btn contorno" data-acao="cm-envio" data-id="${c.id}">Resolver</button>`;
    if (e === 'arquivada') return `<button class="btn contorno" data-acao="cm-desarq" data-id="${c.id}">Desarquivar</button>`;
    return c.com === EU ? `<button class="btn contorno" data-acao="cm-arq" data-id="${c.id}">Arquivar</button>` : '';
  }
  function listaEtapa(cs) {
    const e = est.cm.etapa;
    if (!cs.length) return `<p class="vazio">${{ envio: 'Nenhum envio esperando. O que você sobe aparece aqui até ficar pronto.', fila: 'A Fila está vazia. Toda conta com Guia pronto entra aqui, por ordem de envio.', analise: 'Ninguém está com conta aberta agora.', concluida: 'Nenhuma conta concluída à vista. As do mês arquivado ficam em Arquivadas.', arquivada: 'Nada arquivado ainda.' }[e]}</p>`;
    if (e === 'envio') return `<ul class="linhas">${cs.map((c) => `<li class="linha" style=""grid-template-columns:90px minmax(0,1fr) 260px 120px"><b class="num" style="color:var(--titulo)">${c.at}</b><span class="t" tabindex="0" data-previa="${previaConta(c)}">${esc(c.rot)}<small>Enviada por ${esc(c.por)}, hoje</small></span>${N.estado(c.envio.startsWith('Erro') ? 'e-venc' : c.envio === 'Processando' ? 'e-prox' : 'e-hoje', esc(c.envio.split(':')[0]))}${acaoConta(c)}</li>`).join('')}</ul>`;
    if (e === 'concluida') {
      const comps = [...new Set(cs.map((c) => c.comp))];
      return comps.map((m) => { const doMes = cs.filter((c) => c.comp === m); const minhas = doMes.filter((c) => c.com === EU);
        return `<div style="margin-top:16px"><div class="cab"><h3 class="titulo-bloco" style="font-size:15px">Competência ${m} <span class="sub" style="font-weight:400">· ${doMes.length} contas</span></h3>${minhas.length ? `<button class="btn contorno" data-acao="cm-arq-mes" data-m="${m}">Arquivar as minhas de ${m.split(' ')[0]}</button>` : ''}</div>
          <ul class="linhas">${doMes.map((c) => `<li class="linha" style=""grid-template-columns:90px minmax(0,1fr) 150px 130px 120px"><b class="num" style="color:var(--titulo)">${c.at}</b><span class="t" tabindex="0" data-previa="${previaConta(c)}">${esc(c.rot)}<small>${op(c.op).n} · ${c.com === EU ? 'Você' : esc(c.com)}</small></span>${N.estado(c.etapa === 'pend' ? 'e-hoje' : 'e-ok', c.etapa === 'pend' ? 'Com pendência' : 'Concluída')}<span class="num" style="text-align:right">${R$(c.ajuste)}</span>${acaoConta(c)}</li>`).join('')}</ul></div>`; }).join('');
    }
    return `<ul class="linhas">${cs.map((c) => `<li class="linha" style=""grid-template-columns:90px minmax(0,1fr) 120px 140px 130px"><b class="num" style="color:var(--titulo)">${c.at}</b><span class="t" tabindex="0" data-previa="${previaConta(c)}">${esc(c.rot)}, ${c.idade} anos<small>${op(c.op).n}${c.ini ? ' · ' + curto(dia(c.ini)) + ' a ' + curto(dia(c.fim)) : ''}${c.com ? ' · ' + (c.com === EU ? 'com você' : 'com ' + esc(c.com)) : ''}</small></span><span class="sub">Nota ${nota(c.nota)}</span><span class="num" style="text-align:right">${R$(c.valor)}</span>${acaoConta(c)}</li>`).join('')}</ul>`;
  }
  N.digitar['cm-busca'] = (v) => { est.cm.busca = v; };
  N.acoes['cm-recorte'] = (a) => { est.cm.recorte = a.dataset.v; N.desenhar(); };
  N.acoes['cm-etapa'] = (a) => { est.cm.etapa = a.dataset.v; N.desenhar(); };
  N.acoes['cm-pegar'] = (a) => { const c = conta(a.dataset.id); c.etapa = 'analise'; c.com = EU; location.hash = '#contasguia-' + c.id; N.aviso(`A conta ${c.at} agora é sua.`); };
  N.acoes['cm-arq'] = (a) => { est.cm.arq[a.dataset.id] = true; N.desenhar(); N.aviso('Conta arquivada. Ela continua na busca.'); };
  N.acoes['cm-desarq'] = (a) => { delete est.cm.arq[a.dataset.id]; N.desenhar(); N.aviso('Conta de volta às Concluídas.'); };
  N.acoes['cm-arq-mes'] = (a) => { const m = a.dataset.m; const cs = CONTAS.filter((c) => c.comp === m && c.com === EU && !est.cm.arq[c.id]); const pend = cs.filter((c) => c.etapa === 'pend').length;
    N.modal(`Arquivar ${m}`, `<p style="margin:0">Arquivar quer dizer que a conta já foi tratada no MV. Vão para Arquivadas <b>${cs.length} ${cs.length === 1 ? 'conta sua' : 'contas suas'}</b>${pend ? `, ${pend} delas com pendência` : ''}. Dá para desarquivar depois.</p>`,
      `<button type="button" class="btn" data-acao="cm-arq-mes-ok" data-m="${m}">Arquivar ${cs.length}</button>`); };
  N.acoes['cm-arq-mes-ok'] = (a) => { CONTAS.filter((c) => c.comp === a.dataset.m && c.com === EU).forEach((c) => { est.cm.arq[c.id] = true; }); N.fecharModal(); N.desenhar(); N.aviso('Competência arquivada.'); };
  N.acoes['cm-envio'] = (a) => { const c = conta(a.dataset.id); const erro = c.envio.startsWith('Erro');
    N.abrirGaveta({ sobre: N.estado(erro ? 'e-venc' : 'e-hoje', erro ? 'Erro no envio' : 'Envio incompleto'), titulo: `Atendimento ${c.at}`,
      corpo: `<dl class="pares"><dt>Paciente</dt><dd>${esc(c.rot)}, ${c.idade} anos</dd><dt>Enviado por</dt><dd>${esc(c.por)}, hoje</dd><dt>Situação</dt><dd>${esc(c.envio)}</dd></dl>
        ${erro ? '<p class="aviso">' + I.info + 'O plano da conta não está ligado a nenhuma operadora. Ligue o plano em Operadoras e a conta é analisada de novo sozinha.</p>' : '<div class="solta"><b>Solte aqui o Prontuário do atendimento ' + c.at + '</b>PDF exportado do MV</div>'}`,
      pe: erro ? `<button class="btn contorno" data-acao="toast" data-msg="Envio descartado.">Descartar</button><a class="btn" href="#contasoperadoras" data-acao="fechar-gaveta-ir" data-href="#contasoperadoras">Ligar o plano</a>` : `<button class="btn contorno" data-acao="toast" data-msg="Envio descartado.">Descartar</button><button class="btn" data-acao="toast" data-msg="Analisando assim mesmo, sem o Prontuário.">Analisar assim mesmo</button>` }); };
  N.acoes['cm-enviar'] = (a, n) => N.modal('Enviar contas', `<p class="sub" style="margin:0 0 12px">A Conta e o Prontuário de cada atendimento, exportados do MV. O app junta os dois pelo número.</p>
    <label class="solta" style="display:block;cursor:pointer"><b>${n ? n + ' arquivos prontos para enviar' : 'Arraste os PDFs para cá'}</b>ou clique para escolher<input type="file" multiple accept="application/pdf" hidden></label>`,
    `<button type="button" class="btn" data-acao="toast" data-msg="Envio recebido. Você é avisado quando as contas entrarem na Fila.">Enviar</button>`);

  // ------------------------------------------------------------------ Mesa de trabalho
  T.contasguia = { trilha: 'Contas médicas', menu: 'contasesteira', mapa: ['Contas médicas', 'Mesa de trabalho (conta 2775)', '#contasguia-c2775'], render(id) {
    const c = conta(id) || conta('c2775');
    const its = itensDe(c.id);
    const vez = its.find((x) => x.id === est.cm.vez) || its.find((x) => !decisao(c.id, x)) || its[0];
    const feitos = its.filter((x) => decisao(c.id, x)).length;
    const ajuste = its.filter((x) => decisao(c.id, x) === 'ok').reduce((s, x) => s + x.valor, 0);
    const dias = [...new Set(its.map((x) => x.d + '|' + x.setor))];
    const dv = decisao(c.id, vez);
    return `<div class="pagina">
      <a class="voltar" href="#contasesteira">${I.voltar}Voltar à Esteira</a>
      <section class="cartao bloco" style="padding:20px 24px">
        <div class="cab"><div><span class="rot-mini">Atendimento ${c.at} · ${op(c.op).n}</span><h1 class="pagina-titulo" style="margin-top:4px">${esc(c.rot)}, ${c.idade} anos</h1>
          <p class="pagina-sub">${c.ini ? `Período de ${curto(dia(c.ini))} a ${curto(dia(c.fim))}` : ''} · conta de ${R$(c.valor)} · com você</p></div>
          <div class="acoes-item"><button class="btn contorno" data-acao="cm-auditor" data-id="${c.id}">${IC.microfone}Falar com o Auditor</button><button class="btn contorno" data-acao="cm-mais-conta" data-id="${c.id}" aria-label="Mais ações da conta">${IC.tres}</button></div></div>
      </section>
      <div class="cm-faixa">
        <div class="cartao bloco"><span class="rot-mini">Nota de entrada</span><p class="numero" style="margin:6px 0 0">${nota(c.nota)}</p><span class="sub">de 0 a 10, antes do seu trabalho</span></div>
        <div class="cartao bloco"><span class="rot-mini">R$ a ajustar</span><p class="numero ${ajuste < 0 ? 'verm' : 'verde'}" style="margin:6px 0 0">${R$(ajuste)}</p><span class="sub">soma dos itens que você incluiu</span></div>
        <div class="cartao bloco"><span class="rot-mini">Itens feitos</span><p class="numero" style="margin:6px 0 0">${feitos} de ${its.length}</p><div class="prog" style="margin-top:8px"><span style="width:${feitos / its.length * 100}%"></span></div></div>
      </div>
      <div class="cm-mesa">
        <section class="cartao bloco"><h2 class="titulo-bloco">Linhas da conta, por dia e setor</h2>
          ${dias.map((k) => { const [d, s] = k.split('|'); const doDia = its.filter((x) => x.d === Number(d) && x.setor === s);
            return `<div class="cm-dia"><h3><span>${curto(dia(Number(d)))} · ${s}</span><button class="btn contorno" style="min-height:32px" data-acao="cm-faltou" data-dia="${curto(dia(Number(d)))}" data-setor="${s}">Faltou isto</button></h3>
              ${doDia.map((x) => { const dx = decisao(c.id, x); return `<button type="button" class="cm-item${x.id === vez.id ? ' vez' : ''}" data-acao="cm-vez" data-id="${x.id}"><span class="marca ${dx === 'ok' ? 'ok' : dx === 'nao' ? 'nao' : ''}" aria-hidden="true"></span><span class="t">${esc(x.t)}<small>${x.tipo} · ${x.o === 'IA' ? 'achado pela IA' : 'conferido pelo código'}</small></span><span class="pill ${x.tipo === 'Cobrado a mais' ? 'verm' : x.tipo === 'Dúvida' ? 'laranja' : x.tipo === 'Conferido' ? 'verde' : ''}">${x.tipo}</span><span class="num" style="text-align:right;${x.valor < 0 ? 'color:var(--verm)' : ''}">${x.valor ? R$(x.valor) : ''}</span></button>`; }).join('')}</div>`; }).join('')}
        </section>
        <aside class="cartao bloco cm-vez" aria-label="Item da vez">
          <span class="rot-mini">Item da vez</span>
          <h2 class="titulo-bloco" style="margin-top:6px;font-size:18px">${esc(vez.t)}</h2>
          <p class="sub" style="margin:4px 0 12px">${curto(dia(vez.d))} · ${vez.setor} · ${vez.o === 'IA' ? 'achado pela IA' : 'conferido pelo código'}</p>
          <div class="cm-evid">${esc(vez.evid)}</div>
          <dl class="pares" style="margin-top:14px"><dt>Tipo</dt><dd>${vez.tipo}</dd><dt>Valor</dt><dd class="num" style="${vez.valor < 0 ? 'color:var(--verm)' : ''}">${vez.valor ? R$(vez.valor) : 'sem valor'}</dd></dl>
          ${dv ? `<p class="aviso">${I.info}${dv === 'ok' ? 'Você incluiu este item no ajuste.' : 'Você marcou como não se aplica.'} <button class="btn contorno" style="min-height:30px;margin-left:auto" data-acao="cm-decide" data-c="${c.id}" data-id="${vez.id}" data-v="">Desfazer</button></p>`
            : `<div class="acoes-item" style="margin-top:16px"><button class="btn grande" data-acao="cm-decide" data-c="${c.id}" data-id="${vez.id}" data-v="ok">${vez.tipo === 'Cobrado a mais' ? 'Tirar da conta' : 'Incluir no ajuste'}</button><button class="btn contorno grande" data-acao="cm-decide" data-c="${c.id}" data-id="${vez.id}" data-v="nao">Não se aplica</button></div>`}
          ${vez.tipo === 'Dúvida' ? `<button class="btn contorno" style="margin-top:10px;width:100%" data-acao="cm-auditor" data-id="${c.id}">Perguntar ao Auditor</button>` : ''}
          <p class="sub" style="margin:14px 0 0">Atalhos: <b>I</b> inclui, <b>N</b> não se aplica, <b>J</b> próximo item.</p>
        </aside>
      </div>
      <div class="cm-rodape"><label for="cm-obs" class="sr">Observação para o MV</label><input id="cm-obs" placeholder="Observação para quem lança no MV (opcional)">
        <button class="btn contorno grande" data-acao="cm-devolver" data-id="${c.id}">Devolver à Fila</button>
        <button class="btn grande" data-acao="cm-concluir" data-id="${c.id}">Concluir e abrir a próxima</button></div>
    </div>`;
  }, depois(id) {
    const c = conta(id) || conta('c2775');
    document.onkeydown = (e) => {
      if (!location.hash.startsWith('#contasguia') || /INPUT|TEXTAREA/.test(e.target.tagName) || !document.getElementById('modal').hidden) return;
      const its = itensDe(c.id); const vez = its.find((x) => x.id === est.cm.vez) || its.find((x) => !decisao(c.id, x)) || its[0];
      const k = e.key.toLowerCase();
      if (k === 'i' || k === 'n') { est.cm.feitos[c.id + vez.id] = k === 'i' ? 'ok' : 'nao'; est.cm.vez = null; N.desenhar(); }
      if (k === 'j') { const i = its.indexOf(vez); est.cm.vez = its[(i + 1) % its.length].id; N.desenhar(); }
    };
  } };
  N.acoes['cm-vez'] = (a) => { est.cm.vez = a.dataset.id; N.desenhar(); };
  N.acoes['cm-decide'] = (a) => { if (a.dataset.v) est.cm.feitos[a.dataset.c + a.dataset.id] = a.dataset.v; else { delete est.cm.feitos[a.dataset.c + a.dataset.id]; const it = itensDe(a.dataset.c).find((x) => x.id === a.dataset.id); if (it) it.dec = null; } est.cm.vez = a.dataset.v ? null : a.dataset.id; N.desenhar(); };
  N.acoes['cm-concluir'] = (a) => { const c = conta(a.dataset.id); const falta = itensDe(c.id).filter((x) => !decisao(c.id, x)).length;
    if (falta) { N.modal('Concluir com pendência?', `<p style="margin:0">Faltam <b>${falta} ${falta === 1 ? 'item' : 'itens'}</b> sem decisão. A conta vai para Concluídas com pendência e a próxima da Fila abre em seguida.</p>`, `<button type="button" class="btn" data-acao="cm-concluir-ok" data-id="${c.id}" data-pend="1">Concluir com pendência</button>`); return; }
    N.acoes['cm-concluir-ok'](a); };
  N.acoes['cm-concluir-ok'] = (a) => { const c = conta(a.dataset.id); c.etapa = a.dataset.pend ? 'pend' : 'concluida'; c.comp = 'novembro de 2026'; c.ajuste = 0; N.fecharModal();
    const prox = CONTAS.find((x) => x.etapa === 'fila'); est.cm.vez = null;
    if (prox) { prox.etapa = 'analise'; prox.com = EU; location.hash = '#contasguia-' + prox.id; N.aviso(`Conta ${c.at} concluída. Abrindo a ${prox.at}, a próxima da Fila.`); } else { location.hash = '#contasesteira'; N.aviso('Conta concluída. A Fila acabou.'); } };
  N.acoes['cm-devolver'] = (a) => N.modal('Devolver à Fila', '<p style="margin:0">A conta volta a ficar livre para qualquer faturista. As suas marcações ficam.</p><div class="campo" style="margin-top:12px"><label for="cm-mot">Por que devolve? (opcional)</label><textarea id="cm-mot"></textarea></div>',
    `<button type="button" class="btn" data-acao="cm-devolver-ok" data-id="${a.dataset.id}">Devolver</button>`);
  N.acoes['cm-devolver-ok'] = (a) => { const c = conta(a.dataset.id); c.etapa = 'fila'; c.com = null; N.fecharModal(); location.hash = '#contasesteira'; N.aviso(`Conta ${c.at} devolvida à Fila.`); };
  N.acoes['cm-mais-conta'] = (a) => N.abrirGaveta({ sobre: '<span class="pill">Conta</span>', titulo: 'Mais ações', corpo: `<div style="display:flex;flex-direction:column;gap:8px">
    <button class="btn contorno" data-acao="toast" data-msg="A conta entrou de novo na análise, com a memória vigente.">Analisar de novo</button>
    <button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o PDF da Conta.">Abrir o PDF da Conta</button>
    <button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o PDF do Prontuário.">Abrir o PDF do Prontuário</button>
    <button class="btn contorno" data-acao="cm-devolver" data-id="${a.dataset.id}">Devolver à Fila</button></div>` });
  function conversaAuditor(titulo, pergunta, resposta) {
    N.abrirGaveta({ sobre: '<span class="pill escuro">Auditor</span>', titulo,
      corpo: `<div class="conversa"><div class="balao eu"><small>Você</small>${pergunta}</div><div class="balao ela"><small>Auditor</small>${resposta}</div></div>
        <div class="escrever"><label for="cm-aud" class="sr">Pergunta ao Auditor</label><textarea id="cm-aud" placeholder="Pergunte, ou ensine uma regra nova"></textarea><button class="btn contorno" data-acao="toast" data-msg="No sistema, começa a ditar pelo microfone." aria-label="Ditar">${IC.microfone}</button><button class="btn" data-acao="toast" data-msg="Pergunta enviada ao Auditor." aria-label="Enviar">${IC.enviar}</button></div>` });
  }
  N.acoes['cm-auditor'] = () => conversaAuditor('Taxa de sala de observação', 'A taxa de observação vale no dia da alta?', 'Pela memória da Saúde Mais (regra 4.3), a taxa vale até 6 horas de permanência. O prontuário não diz a hora da alta. Se a alta foi antes das 12h, a taxa se mantém. Quer que eu deixe como Dúvida para a coordenação?');
  N.acoes['cm-faltou'] = (a) => conversaAuditor(`Faltou isto em ${a.dataset.dia}`, `O que faltou na conta de ${a.dataset.dia}, ${a.dataset.setor}?`, 'Encontrei no prontuário deste dia um item sem cobrança: <b>Equipo macrogotas</b>, página 6, instalado às 03h10. Também chequei glicemias e gases: estão na lista ao lado.');

  // ------------------------------------------------------------------ Validação
  const TEMAS = [
    { id: 'v1', k: 'Regra', t: 'Diária de UTI no dia da transferência', op: 'SMS', contas: 7, rs: 10150.0, sug: 'Cobrar a diária do setor de destino, não as duas.' },
    { id: 'v2', k: 'Código', t: 'Curativo de média complexidade sem código na Vida Plena', op: 'VPL', contas: 4, rs: 170.0, sug: 'Usar o código 40.31.016-0 da tabela de outubro.' },
    { id: 'v3', k: 'Observação', t: 'Oxigênio sem hora de início na prescrição', op: 'AMP', contas: 3, rs: 288.0, sug: 'Contar 12 horas quando a prescrição diz "contínuo" sem hora.' },
    { id: 'v4', k: 'Termo', t: '"Bomba" no prontuário quer dizer bomba de infusão', op: 'UNM', contas: 5, rs: 650.0, sug: 'Aceitar o termo e casar com a diária de bomba de infusão.' },
    { id: 'v5', k: 'Regra', t: 'Kit de punção cobrado junto com o cateter', op: 'SMS', contas: 2, rs: -84.0, sug: 'Não cobrar o kit quando o cateter já traz o kit na tabela.' },
    { id: 'v6', k: 'Código', t: 'Eletrodo descartável por unidade ou por pacote', op: 'VPL', contas: 6, rs: 21.6, sug: 'Por unidade, como a tabela da Vida Plena.' }
  ];
  est.cm.temas = {};
  T.contasvalidacao = { trilha: 'Contas médicas', menu: 'contasoperadoras', mapa: ['Contas médicas', 'Validação dos temas'], render() {
    const abertos = TEMAS.filter((x) => !est.cm.temas[x.id]);
    const corpo = `<section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2 class="titulo-bloco">Temas aguardando decisão</h2>
      <div class="acoes-item"><button class="btn contorno" data-acao="toast" data-msg="O Auditor está lendo os temas. A recomendação aparece em cada um.">Pedir recomendação ao Auditor</button><button class="btn" data-acao="cm-lote" ${abertos.length ? '' : 'disabled'}>Aprovar o lote (${abertos.length})</button></div></div>
      ${abertos.length ? `<div class="grade g2">${abertos.map((x) => `<article class="cartao bloco" style="box-shadow:none"><div class="cab"><span class="pill">${x.k}</span><span class="sub">${op(x.op).n}</span></div>
        <h3 class="titulo-bloco" style="font-size:16px;margin-top:10px">${esc(x.t)}</h3><p class="cm-evid" style="margin:10px 0 0">${esc(x.sug)}</p>
        <p class="sub" style="margin:10px 0 0">${x.contas} contas afetadas · <span class="num">${R$(x.rs)}</span> em jogo</p>
        <div class="acoes-item" style="margin-top:12px"><button class="btn" data-acao="cm-tema" data-id="${x.id}" data-v="ok">Aprovar</button><button class="btn contorno" data-acao="cm-tema" data-id="${x.id}" data-v="nao">Recusar</button><button class="btn contorno" data-acao="cm-tema-editar" data-id="${x.id}">Ajustar</button></div></article>`).join('')}</div>`
      : '<p class="vazio">Nenhum tema esperando. Quando o Auditor ou o segundo agente propuser uma regra, ela aparece aqui antes de valer.</p>'}</section>`;
    return N.modulo(cab('Validação', 'O que o Auditor aprendeu nas contas só vira regra da operadora depois que alguém aprova aqui.'),
      [['Aguardando', String(abertos.length).padStart(2, '0'), I.relogio, '#contasvalidacao'], ['Contas afetadas', String(abertos.reduce((s, x) => s + x.contas, 0)), I.agenda, '#contasvalidacao'], ['R$ em jogo', R$(abertos.reduce((s, x) => s + x.rs, 0)), I.certo, '#contasvalidacao']],
      ABAS(), corpo);
  } };
  N.acoes['cm-tema'] = (a) => { est.cm.temas[a.dataset.id] = a.dataset.v; N.desenhar(); N.aviso(a.dataset.v === 'ok' ? 'Tema aprovado: vira regra na próxima versão da memória.' : 'Tema recusado.'); };
  N.acoes['cm-lote'] = () => N.modal('Aprovar o lote', `<p style="margin:0">Aprovar <b>${TEMAS.filter((x) => !est.cm.temas[x.id]).length} temas</b> de uma vez. Cada um vira regra na próxima versão da memória da operadora.</p>`, '<button type="button" class="btn" data-acao="cm-lote-ok">Aprovar todos</button>');
  N.acoes['cm-lote-ok'] = () => { TEMAS.forEach((x) => { est.cm.temas[x.id] = est.cm.temas[x.id] || 'ok'; }); N.fecharModal(); N.desenhar(); N.aviso('Lote aprovado.'); };
  N.acoes['cm-tema-editar'] = (a) => { const x = TEMAS.find((y) => y.id === a.dataset.id); N.modal('Ajustar o tema', `<div class="campo"><label for="cm-tema-txt">Como a regra deve ficar</label><textarea id="cm-tema-txt">${esc(x.sug)}</textarea></div>`, `<button type="button" class="btn" data-acao="cm-tema" data-id="${x.id}" data-v="ok">Aprovar ajustado</button>`); };

  // ------------------------------------------------------------------ Coordenação
  est.cm.coordAba = 'lembretes'; est.cm.lemb = {};
  const LEMB = [
    { id: 'l1', at: '2757', rot: 'Rosa A.', com: 'Daniela Costa', t: 'Taxa de sala de observação no dia da alta', rs: 180.0 },
    { id: 'l2', at: '2757', rot: 'Rosa A.', com: 'Daniela Costa', t: 'Sonda vesical sem registro de troca', rs: 37.0 },
    { id: 'l3', at: '2733', rot: 'Teresa G.', com: EU, t: 'Ficha anestésica sem gás anestésico', rs: 560.0 },
    { id: 'l4', at: '2741', rot: 'Elias N.', com: 'Patrícia Melo', t: 'Diária de acompanhante para paciente idoso', rs: 95.0 }
  ];
  T.contascoordenacao = { trilha: 'Contas médicas', menu: 'contasesteira', mapa: ['Contas médicas', 'Coordenação'], render() {
    const abertos = LEMB.filter((l) => !est.cm.lemb[l.id]);
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="abas" role="tablist" style="margin-top:0">${[['lembretes', 'Lembretes'], ['cenarios', 'Cenários']].map(([k, x]) => `<button type="button" role="tab" aria-selected="${est.cm.coordAba === k}" data-acao="cm-coord-aba" data-v="${k}">${x}</button>`).join('')}</div>
      ${est.cm.coordAba === 'lembretes' ? (abertos.length ? `<ul class="linhas">${abertos.map((l) => `<li class="linha" style="grid-template-columns:90px minmax(0,1fr) 120px 130px 130px"><b class="num" style="color:var(--titulo)">${l.at}</b><span class="t">${esc(l.t)}<small>${esc(l.rot)} · ${l.com === EU ? 'você' : esc(l.com)}</small></span><span class="num" style="text-align:right">${R$(l.rs)}</span><button class="btn" data-acao="cm-lemb" data-id="${l.id}" data-v="ok">Incluído</button><button class="btn contorno" data-acao="cm-lemb" data-id="${l.id}" data-v="nao">Não se aplica</button></li>`).join('')}</ul>` : '<p class="vazio">Nenhum lembrete aberto. As contas concluídas com pendência trazem os lembretes para cá.</p>')
      : `<div class="cab" style="margin-top:12px"><p class="sub" style="margin:0">Situações que a coordenação ensina ao módulo para virar lembrete na próxima conta.</p><button class="btn" data-acao="toast" data-msg="No sistema, abre o cenário novo com ditado.">Novo cenário</button></div>
        <ul class="linhas">${['Paciente acima de 60 anos: lembrar a diária de acompanhante', 'Cirurgia com anestesia geral: conferir o gás na ficha anestésica', 'UTI com dieta enteral: conferir o frasco e o equipo'].map((x) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">${x}</span><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o cenário para editar.">Editar</button></li>`).join('')}</ul>`}
    </section>`;
    return N.modulo(cab('Coordenação', 'Os lembretes das contas concluídas com pendência, para conferir antes de fechar o mês.'),
      [['Lembretes abertos', String(abertos.length).padStart(2, '0'), I.alerta, '#contascoordenacao', abertos.length > 0], ['Contas com lembrete', String(new Set(abertos.map((l) => l.at)).size).padStart(2, '0'), I.agenda, '#contascoordenacao'], ['R$ a conferir', R$(abertos.reduce((s, l) => s + l.rs, 0)), I.certo, '#contascoordenacao']],
      ABAS(), corpo);
  } };
  N.acoes['cm-coord-aba'] = (a) => { est.cm.coordAba = a.dataset.v; N.desenhar(); };
  N.acoes['cm-lemb'] = (a) => { est.cm.lemb[a.dataset.id] = a.dataset.v; N.desenhar(); N.aviso(a.dataset.v === 'ok' ? 'Marcado como incluído no MV.' : 'Marcado como não se aplica.'); };

  // ------------------------------------------------------------------ Contratos
  T.contascontratos = { trilha: 'Contas médicas', menu: 'contascontratos', mapa: ['Contas médicas', 'Contratos'], render() {
    const sit = (o) => o.venc < 0 ? ['e-venc', 'Vencido'] : o.venc <= 15 ? ['e-venc', 'Vence logo'] : o.venc <= 45 ? ['e-hoje', 'Renovar em breve'] : ['e-ok', 'Vigente'];
    const corpo = `<section class="cartao bloco" style="margin-top:14px"><div class="tabela-rola"><table class="tab"><thead><tr><th>Operadora</th><th>Assinatura</th><th>Aditivos</th><th>Vencimento</th><th>Situação</th><th></th></tr></thead><tbody>
      ${OPER.map((o) => { const [cl, tx] = sit(o); return `<tr><td data-previa="${previaContrato(o)}" tabindex="0"><b style="color:var(--titulo)">${o.n}</b><div class="sub">${o.s}</div></td><td class="num">${curto(dia(o.venc - 365))}/${dia(o.venc - 365).getFullYear()}</td><td class="num">${o.adit}</td>
        <td class="num">${N.fmt(dia(o.venc))}<div class="sub">${o.venc < 0 ? 'há ' + -o.venc + ' dias' : 'faltam ' + o.venc + ' dias'}</div></td><td>${N.estado(cl, tx)}</td>
        <td style="text-align:right;white-space:nowrap"><button class="btn${o.venc <= 45 ? '' : ' contorno'}" data-acao="cm-contrato" data-s="${o.s}">${o.venc <= 45 ? 'Enviar aditivo' : 'Enviar documento'}</button> <button class="btn contorno" data-acao="toast" data-msg="No sistema, baixa o contrato e os aditivos." aria-label="Baixar o contrato da ${o.n}">${IC.baixar}</button></td></tr>`; }).join('')}
      </tbody></table></div></section>`;
    const venc = OPER.filter((o) => o.venc < 0).length;
    return N.modulo(cab('Contratos', venc ? `O contrato da ${OPER.find((o) => o.venc < 0).n} venceu há ${-OPER.find((o) => o.venc < 0).venc} dias. ${OPER.filter((o) => o.venc >= 0 && o.venc <= 45).length} vencem nos próximos 45 dias.` : 'Todos os contratos vigentes.'),
      [['Vencidos', String(venc).padStart(2, '0'), I.alerta, '#contascontratos', venc > 0], ['Vencem em 45 dias', String(OPER.filter((o) => o.venc >= 0 && o.venc <= 45).length).padStart(2, '0'), I.relogio, '#contascontratos'], ['Operadoras', String(OPER.length).padStart(2, '0'), I.certo, '#contasoperadoras']],
      ABAS(), corpo);
  } };
  N.acoes['cm-contrato'] = (a) => { const o = op(a.dataset.s);
    N.modal(`Aditivo da ${o.n}`, `<label class="solta" style="display:block;cursor:pointer"><b>Solte o PDF do aditivo</b>A IA lê as datas e o reajuste; você confere antes de gravar.<input type="file" accept="application/pdf" hidden></label>
      <p class="rot-mini" style="margin:16px 0 8px">O que a IA leu (confira)</p>
      <div class="grade-form"><div class="campo"><label for="ct-ass">Assinatura</label><input id="ct-ass" value="${N.fmt(dia(-3))}"></div><div class="campo"><label for="ct-vig">Vigência até</label><input id="ct-vig" value="${N.fmt(dia(362))}"></div><div class="campo"><label for="ct-rea">Reajuste</label><input id="ct-rea" value="6,2%"></div></div>`,
      '<button type="button" class="btn" data-acao="toast" data-msg="Aditivo gravado. O vencimento foi atualizado.">Confirmar e gravar</button>'); };

  // ------------------------------------------------------------------ Operadoras
  const CATS = ['Diárias e taxas', 'Materiais', 'Medicamentos', 'Gases'];
  T.contasoperadoras = { trilha: 'Contas médicas', menu: 'contasoperadoras', mapa: ['Contas médicas', 'Operadoras'], render() {
    const corpo = `<div class="grade g3">${OPER.map((o) => `<a class="cartao bloco cartao-link" href="#contasoperadora-${o.s}" data-previa="${previaOper(o)}">
        <div class="cab"><span class="pill escuro">${o.s}</span>${o.situ === 'ok' ? N.estado('e-ok', 'Pronta') : o.situ === 'tabela' ? N.estado('e-hoje', 'Falta uma tabela') : N.estado('e-venc', 'Sem memória')}</div>
        <h2 class="titulo-bloco" style="margin-top:10px">${o.n}</h2>
        <p class="sub" style="margin:4px 0 10px">${o.mem ? 'Memória v' + o.mem : 'Nenhuma memória enviada'}</p>
        <div style="display:flex;gap:6px;flex-wrap:wrap">${CATS.map((c, i) => `<span class="pill ${i < o.tabelas ? 'cinza' : 'verm'}">${c}${i < o.tabelas ? '' : ': falta'}</span>`).join('')}</div>
        <span class="ir">Abrir a memória${IC.seta}</span></a>`).join('')}</div>
      <section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2 class="titulo-bloco">Biblioteca de tabelas</h2><button class="btn" data-acao="cm-tabela">Nova versão de tabela</button></div>
        <div class="tabela-rola"><table class="tab"><thead><tr><th>Operadora</th><th>Tabela</th><th>Versão</th><th>Vale desde</th><th></th></tr></thead><tbody>
        ${OPER.filter((o) => o.tabelas > 1).flatMap((o) => CATS.slice(0, Math.min(2, o.tabelas)).map((c, i) => `<tr><td>${o.n}</td><td>${c}</td><td class="num">${i ? 'out/2026' : 'set/2026'}</td><td class="num">${N.fmt(dia(-40 - i * 30))}</td><td style="text-align:right"><button class="btn contorno" data-acao="toast" data-msg="No sistema, baixa o CSV da tabela.">${IC.baixar}Baixar</button></td></tr>`)).join('')}
        </tbody></table></div></section>`;
    return N.modulo(cab('Operadoras', `${OPER.filter((o) => o.situ === 'ok').length} de ${OPER.length} operadoras prontas para análise. A Cuidar Seguros ainda não tem memória, e as contas dela param no envio.`,
      '<button class="btn claro grande" data-acao="cm-tabela">Enviar memória ou tabela</button>'), null, ABAS(), corpo);
  } };
  N.acoes['cm-tabela'] = () => N.modal('Enviar memória ou tabela', `<div class="opcoes-grandes" style="margin-bottom:14px">${[['Memória da operadora', 'arquivo .md com as regras'], ['Tabela de preço', 'CSV, com o mapeamento das colunas'], ['Dicionário', 'termos do prontuário'], ['Planos do MV', 'nome do plano e operadora']].map(([t, s], i) => `<button type="button" class="opcao-g" aria-pressed="${i === 1}"><b>${t}</b><small>${s}</small></button>`).join('')}</div>
    <div class="campo"><label for="cm-tab-op">Operadora</label><select id="cm-tab-op">${OPER.map((o) => `<option>${o.n}</option>`).join('')}</select></div>
    <label class="solta" style="display:block;cursor:pointer;margin-top:14px"><b>Solte o arquivo aqui</b>ou clique para escolher<input type="file" hidden></label>`,
    '<button type="button" class="btn" data-acao="toast" data-msg="Arquivo recebido. A versão nova vale para as contas que entrarem daqui em diante.">Enviar</button>');

  // ------------------------------------------------------------------ Memória da operadora
  const REGRAS = {
    diarias: [['2.1', 'Uma diária por dia, do setor onde o paciente dormiu', 'Código'], ['2.4', 'Diária de acompanhante para maiores de 60 anos', 'Código'], ['4.3', 'Taxa de sala de observação só até 6 horas', 'IA']],
    materiais: [['5.2', 'Equipo cobrado por troca registrada no prontuário', 'IA'], ['5.7', 'Kit de punção não se cobra junto com o cateter', 'Código']],
    medicamentos: [['6.1', 'Preço pela tabela vigente no dia do uso', 'Código'], ['6.3', 'Dose fracionada cobra a ampola inteira', 'Código']],
    gases: [['7.1', 'Oxigênio por hora prescrita; "contínuo" vale 24 horas', 'Código'], ['7.2', 'Gás anestésico pela ficha anestésica', 'IA']]
  };
  T.contasoperadora = { trilha: 'Contas médicas', menu: 'contasoperadoras', mapa: ['Contas médicas', 'Memória da Saúde Mais', '#contasoperadora-SMS'], render(id) {
    const o = op(id) || OPER[0];
    const A = [['diarias', 'Diárias e taxas'], ['materiais', 'Materiais'], ['medicamentos', 'Medicamentos'], ['gases', 'Gases']];
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
        <div class="cab"><div><span class="rot-mini">${o.s} · versão vigente</span><h2 class="titulo-bloco" style="margin-top:4px">${o.mem ? 'Memória v' + o.mem + ', desde ' + N.fmt(dia(-21)) : 'Ainda sem memória'}</h2></div>
          <div class="acoes-item"><button class="btn" data-acao="cm-ensinar">${IC.microfone}Falar com o Auditor</button><button class="btn contorno" data-acao="toast" data-msg="7 contas em análise vão ser relidas com a regra nova.">Reanalisar com a regra nova</button><button class="btn contorno" data-acao="toast" data-msg="No sistema, baixa a memória em .md.">${IC.baixar}Exportar</button></div></div>
        <div class="abas" role="tablist" aria-label="Regras por categoria">${A.map(([k, x]) => `<button type="button" role="tab" aria-selected="${est.cm.regra === k}" data-acao="cm-regra" data-v="${k}">${x} (${REGRAS[k].length})</button>`).join('')}</div>
        <ul class="linhas">${REGRAS[est.cm.regra].map(([n, t, q]) => `<li class="linha" style="grid-template-columns:60px minmax(0,1fr) 150px 110px"><b class="num" style="color:var(--titulo)">${n}</b><span class="t">${esc(t)}</span><span class="pill ${q === 'IA' ? 'laranja' : 'cinza'}">${q === 'IA' ? 'IA julga' : 'Código confere'}</span><button class="btn contorno" data-acao="cm-regra-editar" data-n="${n}" data-t="${esc(t)}">Editar</button></li>`).join('')}</ul>
      </section>
      <section class="cartao bloco" style="margin-top:14px"><h2 class="titulo-bloco">Versões</h2>
        <ul class="tempo" style="margin-top:12px">${[[o.mem || '1.0', 'vigente', -21, 'Validação aprovou 3 temas'], ['2.2', '', -52, 'Tabela de gases de outubro'], ['2.1', '', -90, 'Primeira carga do diretor']].map(([v, at, d, t], i) => `<li class="${i ? 'feito' : 'agora'}"><i aria-hidden="true"></i><b>v${v}${at ? ' (' + at + ')' : ''}</b><span>${N.fmt(dia(d))} · ${t}</span></li>`).join('')}</ul></section>`;
    return N.modulo(cab('Memória da ' + o.n, 'As regras que o código e a IA usam para conferir as contas desta operadora. Regra nova entra pela conversa com o Auditor e vale depois do seu "ok".'), null, ABAS(), corpo);
  } };
  N.acoes['cm-regra'] = (a) => { est.cm.regra = a.dataset.v; N.desenhar(); };
  N.acoes['cm-regra-editar'] = (a) => N.modal(`Regra ${a.dataset.n}`, `<div class="campo"><label for="cm-r-txt">Texto da regra</label><textarea id="cm-r-txt">${a.dataset.t}</textarea></div><p class="sub" style="margin:10px 0 0">A mudança gera uma versão nova da memória.</p>`, '<button type="button" class="btn" data-acao="toast" data-msg="Regra salva. Versão nova da memória criada.">Salvar a regra</button>');
  N.acoes['cm-ensinar'] = () => conversaAuditor('Ensinar uma regra nova', 'Na Saúde Mais, curativo com placa de hidrocoloide entra como média complexidade.', 'Entendi. Proponho a regra <b>5.8: curativo com placa de hidrocoloide cobra o código de média complexidade</b>. Afeta 4 contas em análise. Dê "ok" para ela entrar na Validação.');

  // ------------------------------------------------------------------ Habilitação
  const PERFIS = ['Faturista', 'Coordenadora', 'Gestão de contas médicas', 'Diretoria médica', 'Diretoria executiva', 'Credenciamento', 'Apoio ao faturamento'];
  const PERMS = ['Enviar contas', 'Analisar contas', 'Painel completo', 'Regra contratual e tabelas', 'Validar temas', 'Habilitação'];
  const PADRAO = [[1, 1, 0, 0, 0, 0], [1, 1, 1, 0, 1, 0], [1, 1, 1, 1, 1, 1], [0, 0, 1, 0, 1, 0], [0, 0, 1, 0, 0, 0], [0, 0, 0, 1, 0, 0], [1, 0, 0, 0, 0, 0]];
  PADRAO.forEach((l, i) => l.forEach((v, j) => { est.cm.perms[i + '-' + j] = !!v; }));
  const PESSOAS_CM = [['Bruno Araújo', 'Faturista'], ['Daniela Costa', 'Faturista'], ['Patrícia Melo', 'Faturista'], ['Cláudia Rezende', 'Coordenadora'], ['Jéssica Ramos', 'Apoio ao faturamento'], ['Otávio Lins', 'Diretoria médica']];
  T.contashabilitacao = { trilha: 'Contas médicas', menu: 'contashabilitacao', mapa: ['Contas médicas', 'Habilitação'], render() {
    const pode = N.perfil() === 'admin';
    const t = est.cm.pessoaBusca.trim().toLowerCase();
    const corpo = `<section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2 class="titulo-bloco">O que cada perfil pode fazer</h2>${pode ? '' : '<span class="pill cinza">Só leitura para o seu perfil</span>'}</div>
        <div class="tabela-rola"><table class="tab cm-matriz"><thead><tr><th>Perfil</th>${PERMS.map((p) => `<th>${p}</th>`).join('')}</tr></thead><tbody>
        ${PERFIS.map((p, i) => `<tr><td><b style="color:var(--titulo)">${p}</b></td>${PERMS.map((x, j) => `<td><button type="button" class="cm-tog" aria-pressed="${est.cm.perms[i + '-' + j]}" aria-label="${p}: ${x}" ${pode ? `data-acao="cm-perm" data-k="${i}-${j}"` : 'disabled'}></button></td>`).join('')}</tr>`).join('')}
        </tbody></table></div></section>
      <section class="cartao bloco" style="margin-top:14px"><div class="ferramentas"><h2 class="titulo-bloco">Quem tem perfil no módulo</h2>
        <label class="busca-lista">${IC.busca}<span class="sr">Buscar pessoa</span><input id="cm-pessoa" data-digita="cm-pessoa" type="search" placeholder="Buscar pessoa do hospital" value="${esc(est.cm.pessoaBusca)}"></label></div>
        <ul class="linhas">${PESSOAS_CM.filter(([n]) => !t || n.toLowerCase().includes(t)).map(([n, p]) => `<li class="linha" style="grid-template-columns:42px minmax(0,1fr) 230px 110px"><span class="ini" style="width:36px;height:36px;border-radius:999px;background:var(--suave2);color:var(--titulo);display:inline-flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:700">${N.ini(n)}</span><span class="t">${n}</span><span class="pill">${p}</span>${pode ? `<button class="btn contorno" data-acao="cm-pessoa-perfil" data-n="${n}" data-p="${p}">Trocar</button>` : ''}</li>`).join('')}
        ${t && !PESSOAS_CM.some(([n]) => n.toLowerCase().includes(t)) ? `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">Ninguém do módulo com esse nome.<small>Dê um perfil a quem é do hospital e ainda não está aqui.</small></span>${pode ? '<button class="btn" data-acao="toast" data-msg="No sistema, busca a pessoa no cadastro do hospital.">Dar perfil</button>' : ''}</li>` : ''}</ul></section>`;
    return N.modulo(cab('Habilitação', pode ? 'Os perfis de Contas médicas e o que cada um faz. Um clique liga ou desliga a permissão.' : 'Os perfis de Contas médicas e o que cada um faz. Quem muda é a gestão de contas médicas.'), null, ABAS(), corpo);
  } };
  N.digitar['cm-pessoa'] = (v) => { est.cm.pessoaBusca = v; };
  N.acoes['cm-perm'] = (a) => { est.cm.perms[a.dataset.k] = !est.cm.perms[a.dataset.k]; N.desenhar(); N.aviso('Permissão atualizada.'); };
  N.acoes['cm-pessoa-perfil'] = (a) => N.modal(`Perfil de ${a.dataset.n}`, `<div class="campo"><label for="cm-pp">Perfil em Contas médicas</label><select id="cm-pp">${PERFIS.map((p) => `<option${p === a.dataset.p ? ' selected' : ''}>${p}</option>`).join('')}<option>Sem perfil no módulo</option></select></div>`, '<button type="button" class="btn" data-acao="toast" data-msg="Perfil trocado.">Salvar</button>');
})();
