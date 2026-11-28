/* Segurança do Paciente: Visão geral, Notificações, Fila de triagem, Caso, Triagem do caso,
   Reuniões do Núcleo, Núcleo (membros, documentos, capacitações, agenda, notas), Configuração
   e o Notificar incidente de quem está logado. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I, IC, dia, fmt, curto, est, reunioes, deIso, HOJE, quando } = N;
  const T = N.telas;
  const SOBRE = 'Segurança do Paciente';
  const ANO = HOJE.getFullYear();
  est.nsp = { busca: '', faixa: 'todas', sit: 'abertos', lote: {}, conferidos: {}, nucleoAba: 'membros', passo: 1, form: {}, recibo: null, loteLigado: true, ajuste: {}, triados: {} };

  N.css(`
    .nsp-alerta{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px;margin-top:14px;padding:16px 20px;border-radius:10px;background:var(--cartao);border:1px solid var(--borda);border-left:5px solid var(--ponto-verm);box-shadow:var(--sombra)}
    .nsp-alerta b{display:block;color:var(--verm);font-size:15.5px}
    .nsp-alerta span{font-size:14px;color:var(--texto2)}
    .nsp-grupo{display:flex;align-items:center;gap:14px;padding:12px 0;border-top:1px solid var(--linha);text-decoration:none;color:var(--texto)}
    .nsp-grupo:first-of-type{border-top:0}
    .nsp-grupo .q{flex:none;width:44px;height:44px;border-radius:10px;background:var(--suave);color:var(--titulo);display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;font-variant-numeric:tabular-nums}
    .nsp-grupo .q.verm{color:var(--verm);background:#FDECEA}
    .nsp-grupo .tx{flex:1;min-width:0}
    .nsp-grupo .tx b{display:block;font-size:15px;color:var(--titulo)}
    .nsp-grupo .tx small{display:block;font-size:13px;color:var(--texto2)}
    .nsp-grupo:hover .tx b{text-decoration:underline}
    .nsp-faixa{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:8px;font-weight:700;font-size:14px;background:var(--suave2);color:var(--titulo)}
    .nsp-faixa.fA,.nsp-faixa.fB{background:var(--ponto-verm);color:#fff}
    .nsp-faixa.fC{background:var(--ponto-laranja);color:#fff}
    .nsp-faixa.fE{background:var(--suave);color:var(--texto2)}
    .nsp-larga{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:14px;margin-top:14px;align-items:start}
    @media (max-width:1000px){.nsp-larga{grid-template-columns:1fr}}
    .nsp-eixo{padding:12px 14px;border-radius:8px;background:var(--suave);display:flex;flex-direction:column;gap:4px}
    .nsp-eixo .top{display:flex;justify-content:space-between;align-items:center;gap:10px}
    .nsp-eixo .top b{color:var(--titulo);font-size:14.5px}
    .nsp-eixo p{margin:0;font-size:13.5px;color:var(--texto2)}
    .nsp-conf{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--texto2);margin-top:4px;cursor:pointer}
    .nsp-conf input{width:18px;height:18px}
    .nsp-relato{font-size:15.5px;line-height:1.55;margin:0;padding:14px 16px;border-radius:8px;background:var(--suave);color:var(--texto)}
    .nsp-anexo{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--borda);border-radius:8px;font-size:14px}
    .nsp-anexo .ic{width:36px;height:36px;border-radius:8px;background:var(--suave2);color:var(--titulo);display:flex;align-items:center;justify-content:center;flex:none}
    .nsp-prazo{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid var(--linha);font-size:14.5px}
    .nsp-prazo:last-child{border-bottom:0}
    .nsp-prazo small{display:block;font-size:12.5px;color:var(--texto2)}
    .nsp-qr{width:132px;height:132px;flex:none;border-radius:10px;background:var(--suave);display:flex;align-items:center;justify-content:center;color:var(--titulo)}
    .nsp-toggle{display:inline-flex;align-items:center;gap:10px;cursor:pointer;font-size:14.5px;border:0;background:transparent;padding:4px 0;color:var(--texto);margin-top:8px}
    .nsp-toggle i{width:42px;height:24px;border-radius:999px;background:var(--campo-borda);position:relative;transition:background .2s ease}
    .nsp-toggle i::after{content:"";position:absolute;left:3px;top:3px;width:18px;height:18px;border-radius:999px;background:#fff;transition:transform .2s ease}
    .nsp-toggle[aria-pressed="true"] i{background:var(--btn-fundo)}
    .nsp-toggle[aria-pressed="true"] i::after{transform:translateX(18px)}
    .nsp-recibo{font-size:30px;font-weight:700;color:var(--titulo);letter-spacing:.02em;font-variant-numeric:tabular-nums}
    .nsp-naopune{margin-top:14px;padding:14px 16px;border-radius:8px;background:var(--aviso-fundo);border:1px solid var(--aviso-borda);font-size:14px;color:var(--titulo)}
  `);

  // ------------------------------------------------------------------ dados de demonstração
  // h = horas desde o registro; faixa = a confirmada (null enquanto aguarda triagem); sug = a sugestão do agente.
  const CASOS = [
    { id: '0418', h: 20, sug: 'A', faixa: null, sit: 'triagem', origem: 'Formulário logado', setor: 'UTI adulto', local: 'UTI adulto, leito 7', tipo: 'Erro de medicação', atingido: 'Óbito', relato: 'Paciente recebeu dose de heparina dez vezes maior que a prescrita na troca de plantão. Evoluiu com sangramento e foi a óbito na madrugada.', anexos: ['prescricao-leito7.pdf'], notif: 'Identificado', grave: true },
    { id: '0417', h: 30, sug: 'B', faixa: null, sit: 'triagem', origem: 'Ouvidoria', setor: 'Centro Cirúrgico', local: 'Centro Cirúrgico, sala 3', tipo: 'Cirurgia', atingido: 'Com dano', relato: 'Compressa encontrada na reabordagem do paciente dois dias depois da cirurgia. A contagem de compressas estava registrada como conferida.', anexos: [], notif: 'Caso da Ouvidoria', grave: true },
    { id: '0416', h: 52, sug: 'D', faixa: null, sit: 'triagem', origem: 'QR do cartaz', setor: 'Enfermaria 3º andar', local: '3º andar, leito 12', tipo: 'Queda', atingido: 'Sem dano', relato: 'Paciente escorregou ao levantar sozinho para ir ao banheiro. Grade da cama estava abaixada. Sem lesão aparente, avaliado pelo plantonista.', anexos: ['foto-corredor.jpg'], notif: 'Anônimo' },
    { id: '0415', h: 70, sug: 'E', faixa: null, sit: 'triagem', origem: 'Formulário logado', setor: 'Farmácia', local: 'Farmácia satélite', tipo: 'Medicação', atingido: 'Não chegou ao paciente', relato: 'Ampolas de potássio guardadas na mesma gaveta do soro fisiológico. A técnica percebeu antes de separar a medicação.', anexos: [], notif: 'Identificado' },
    { id: '0414', h: 96, sug: 'D', faixa: null, sit: 'triagem', origem: 'Registro rápido', setor: 'Emergência', local: 'Emergência, box 2', tipo: 'Identificação do paciente', atingido: 'Sem dano', relato: 'Pulseira com o nome trocado entre dois pacientes do mesmo box. Corrigido na checagem antes da coleta de exames.', anexos: [], notif: 'Fernanda Lima (ronda)' },
    { id: '0410', h: 240, sug: 'C', faixa: 'C', sit: 'investigacao', origem: 'Formulário logado', setor: 'Enfermaria 2º andar', local: '2º andar, leito 4', tipo: 'Lesão por pressão', atingido: 'Com dano', relato: 'Lesão por pressão estágio 3 identificada na região sacral, sem registro de mudança de decúbito nas últimas 48 horas.', anexos: ['foto-lesao.jpg', 'evolucao.pdf'], notif: 'Identificado' },
    { id: '0407', h: 400, sug: 'D', faixa: 'D', sit: 'investigacao', origem: 'QR do cartaz', setor: 'Hemodiálise', local: 'Hemodiálise', tipo: 'Equipamento', atingido: 'Sem dano', relato: 'Máquina de hemodiálise alarmou sem motivo três vezes no mesmo turno.', anexos: [], notif: 'Anônimo' },
    { id: '0402', h: 600, sug: 'E', faixa: 'E', sit: 'encaminhado', destino: 'Segurança do Trabalho', origem: 'Formulário logado', setor: 'Lavanderia', local: 'Lavanderia', tipo: 'Outro', atingido: 'Não chegou ao paciente', relato: 'Piso molhado sem sinalização na entrada da lavanderia.', anexos: [], notif: 'Identificado' },
    { id: '0398', h: 900, sug: 'D', faixa: 'D', sit: 'encerrado', origem: 'Formulário logado', setor: 'UTI adulto', local: 'UTI adulto', tipo: 'Queda', atingido: 'Sem dano', relato: 'Queda da própria altura durante banho de leito. Sem lesão.', anexos: [], notif: 'Identificado' }
  ];
  const prot = (c) => `NSP-${ANO}-${c.id}`;
  const caso = (id) => CASOS.find((c) => c.id === id);
  const faixaDe = (c) => est.nsp.triados[c.id] || c.faixa;
  const sitDe = (c) => est.nsp.triados[c.id] ? 'investigacao' : c.sit;
  const SIT = { triagem: ['e-hoje', 'Aguardando triagem'], investigacao: ['e-prox', 'Em investigação'], encaminhado: ['e-sem', 'Encaminhado'], encerrado: ['e-ok', 'Encerrado'] };
  const FX = { A: 'Óbito ou evento que nunca deveria ocorrer', B: 'Dano grave', C: 'Dano moderado', D: 'Dano leve ou sem dano', E: 'Quase erro ou circunstância de risco' };
  const faixa = (f) => `<span class="nsp-faixa f${f}" title="Faixa ${f}: ${FX[f]}">${f}</span>`;
  const idade = (h) => h < 24 ? `há ${h} horas` : `há ${Math.round(h / 24)} ${Math.round(h / 24) === 1 ? 'dia' : 'dias'}`;
  const naFila = () => CASOS.filter((c) => sitDe(c) === 'triagem').sort((a, b) => (b.grave ? 1 : 0) - (a.grave ? 1 : 0) || (a.grave && b.grave ? a.sug.localeCompare(b.sug) : 0) || b.h - a.h);
  const graves = () => naFila().filter((c) => c.grave);

  const ABAS = (atual) => N.abasModulo([['#nsp', 'Visão geral'], ['#nspnotificacoes', 'Notificações', naFila().length, graves().length > 0], ['#nspreunioes', 'Reuniões'], ['#nspnucleo', 'Núcleo'], ['#nspconfig', 'Configuração']], atual);
  const resumoNsp = () => [
    ['Aguardando triagem', String(naFila().length).padStart(2, '0'), I.alerta, '#nsptriagem', graves().length > 0],
    ['Prazo legal em 7 dias', '03', I.relogio, '#nspnotificacoes'],
    ['Em investigação', String(CASOS.filter((c) => sitDe(c) === 'investigacao').length).padStart(2, '0'), I.agenda, '#nspnotificacoes'],
    ['Concordância do agente', '93%', I.certo, '#nspconfig']];

  // ------------------------------------------------------------------ Visão geral
  T.nsp = { trilha: 'Segurança do Paciente', menu: 'nsp', mapa: [SOBRE, 'Visão geral'], render() {
    const g = graves();
    const frase = g.length ? `${g.length === 1 ? 'Um caso grave espera' : g.length + ' casos graves esperam'} triagem. O mais antigo chegou ${idade(g[0].h)} e o prazo legal de 72 horas corre sem pausa.` : 'Nenhum caso grave esperando. A fila de triagem está em dia.';
    const p13 = N.itens.find((i) => i.id === 'p13');
    const r4 = reunioes.find((r) => r.id === 'r4');
    const grupo = (n, t, s, href, verm) => `<a class="nsp-grupo" href="${href}"><span class="q${verm && n ? ' verm' : ''}">${n}</span><span class="tx"><b>${t}</b><small>${s}</small></span>${IC.seta}</a>`;
    const corpo = `${ABAS('#nsp')}
      ${[...g].sort((x, y) => x.sug.localeCompare(y.sug)).map((c) => `<div class="nsp-alerta" role="alert"><div><b>Caso ${c.atingido === 'Óbito' ? 'com morte' : 'grave'}: ${prot(c)}</b><span>${esc(c.tipo)} · ${esc(c.setor)} · registrado ${idade(c.h)} · faixa sugerida ${c.sug}</span></div><a class="btn" href="#nsptriar-${c.id}">Triar agora</a></div>`).join('')}
      <div class="duas" style="margin-top:14px">
        <section class="cartao bloco larga"><h2 class="titulo-bloco" style="margin-bottom:6px">O que exige ação hoje</h2>
          ${grupo(naFila().length, 'Notificações aguardando triagem', `${g.length} graves · a mais antiga ${naFila().length ? idade(naFila()[0].h) : 'nenhuma'}`, '#nsptriagem', true)}
          ${grupo(1, 'Notificação externa a preparar', `${prot(CASOS[0])} · VigiMed · prazo legal de 72 horas`, '#nspcaso-0418', true)}
          ${grupo(2, 'Perguntas de esclarecimento sem resposta', 'Não bloqueiam a triagem. Respondidas, o agente sugere de novo.', '#nspnotificacoes')}
          ${grupo(1, 'Investigação com prazo interno vencendo', `${prot(caso('0410'))} · vence ${quando(dia(2))}`, '#nspcaso-0410')}
          ${grupo(1, 'Evento da agenda regulatória', 'Relatório mensal à vigilância sanitária · vence ' + quando(dia(5)), '#nspnucleo')}
        </section>
        <aside class="estreita">
          <section class="cartao bloco"><span class="rot-mini">Termo de Adesão</span><p style="margin:6px 0 0;font-size:20px;font-weight:700;color:var(--titulo)">Assinado</p><p class="sub" style="margin:2px 0 0">Válido até dezembro de ${ANO + 1}, com o Regimento versão 2.</p></section>
          <section class="cartao bloco"><span class="rot-mini">Próxima Reunião do Núcleo</span><p style="margin:6px 0 0;font-size:20px;font-weight:700;color:var(--titulo)">${quando(deIso(r4.data))}, ${r4.hora}</p><p class="sub" style="margin:2px 0 0">${r4.pauta.map(esc).join(' · ')}</p><div class="acoes-item" style="margin-top:12px"><button class="btn contorno" data-acao="nsp-pauta" data-id="r4">Ver a pauta</button></div></section>
          <section class="cartao bloco"><span class="rot-mini">Capacitação</span><p style="margin:6px 0 0;font-size:17px;font-weight:700;color:var(--titulo)">Comunicação de evento adverso</p><p class="sub" style="margin:2px 0 0">${quando(dia(p13.off))}, 15:00, auditório</p>
            ${est.feitos.p13 ? `<p style="margin:10px 0 0">${N.estado('e-ok', 'Presença confirmada')}</p>` : `<div class="acoes-item" style="margin-top:12px"><button class="btn" data-acao="nsp-presenca">Confirmar presença</button></div>`}</section>
          <section class="cartao bloco"><h2 class="titulo-bloco">Viu um incidente?</h2><p class="sub" style="margin:4px 0 12px">Pode ser anônimo e leva menos de 2 minutos. Ninguém é punido por notificar.</p><a class="btn grande" href="#notificar">Notificar incidente</a></section>
        </aside>
      </div>`;
    return N.modulo({ sobre: SOBRE, titulo: 'Núcleo de Segurança do Paciente', frase, acoes: `<a class="btn claro grande" href="#nsptriagem">Abrir a fila de triagem</a><button class="btn vidro grande" data-acao="nsp-rapido">Registro rápido</button>` }, resumoNsp(), '', corpo);
  } };
  N.acoes['nsp-presenca'] = () => { est.feitos.p13 = true; N.desenhar(); N.aviso('Presença confirmada na Capacitação.'); };

  // ------------------------------------------------------------------ Registro rápido (modal)
  N.acoes['nsp-rapido'] = () => N.modal('Registro rápido', `<p class="sub" style="margin:0 0 14px">Para o que o Núcleo encontrou em ronda, busca ativa, auditoria ou reunião rápida de segurança. Notificação de outra pessoa vai pelo Notificar incidente.</p>
    <div class="grade-form"><div class="campo"><label for="rr-origem">Origem</label><select id="rr-origem"><option>Ronda</option><option>Busca ativa</option><option>Auditoria</option><option>Reunião rápida de segurança</option></select></div>
    <div class="campo"><label for="rr-setor">Setor</label><select id="rr-setor"><option>UTI adulto</option><option>Emergência</option><option>Centro Cirúrgico</option><option>Enfermaria 3º andar</option></select></div>
    <div class="campo"><label for="rr-data">Quando</label><input id="rr-data" type="date" value="${N.iso(HOJE)}"></div></div>
    <div class="campo" style="margin-top:14px"><label for="rr-relato">O que foi encontrado</label><textarea id="rr-relato" placeholder="Sem nome de paciente"></textarea></div>`,
    `<button type="button" class="btn" data-acao="toast" data-msg="Registro rápido lançado: NSP-${ANO}-0419. Ele entra na fila de triagem.">Registrar</button>`);

  // ------------------------------------------------------------------ Notificações
  function linhaCaso(c, comBotao) {
    const f = faixaDe(c); const [cls, txt] = SIT[sitDe(c)];
    return `<tr><td>${f ? faixa(f) : `<span class="sub" title="Sugestão do agente">${faixa(c.sug)}</span>`}</td>
      <td><a href="#nspcaso-${c.id}">${prot(c)}</a>${c.grave && sitDe(c) === 'triagem' ? ` <span class="pill verm">Grave ou houve morte</span>` : ''}<div class="sub">${esc(c.tipo)} · ${esc(c.setor)}</div></td>
      <td style="max-width:360px"><span class="sub" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${esc(c.relato)}</span></td>
      <td>${N.estado(cls, c.sit === 'encaminhado' ? 'Encaminhado: ' + c.destino : txt)}<div class="sub">${esc(c.origem)} · ${idade(c.h)}</div></td>
      <td style="text-align:right">${comBotao && sitDe(c) === 'triagem' ? `<a class="btn" href="#nsptriar-${c.id}">Triar</a>` : `<a class="btn contorno" href="#nspcaso-${c.id}">Abrir</a>`}</td></tr>`;
  }
  T.nspnotificacoes = { trilha: 'Notificações do Núcleo', menu: 'nspnotificacoes', mapa: [SOBRE, 'Notificações'], render() {
    const t = est.nsp.busca.trim().toLowerCase();
    const SITS = [['abertos', 'Abertos'], ['triagem', 'Aguardando triagem'], ['investigacao', 'Em investigação'], ['encaminhado', 'Encaminhados'], ['encerrado', 'Encerrados'], ['todos', 'Todos']];
    const lista = CASOS.filter((c) => est.nsp.sit === 'todos' || (est.nsp.sit === 'abertos' ? !['encerrado', 'encaminhado'].includes(sitDe(c)) : sitDe(c) === est.nsp.sit))
      .filter((c) => est.nsp.faixa === 'todas' || (faixaDe(c) || c.sug) === est.nsp.faixa)
      .filter((c) => !t || (prot(c) + ' ' + c.tipo + ' ' + c.setor + ' ' + c.relato).toLowerCase().includes(t));
    const corpo = `${ABAS('#nspnotificacoes')}<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas"><div class="chips" role="group" aria-label="Situação">${SITS.map(([k, x]) => `<button class="chip" data-acao="nsp-sit" data-v="${k}" aria-pressed="${est.nsp.sit === k}">${x}</button>`).join('')}</div>
        <label class="busca-lista">${IC.busca}<span class="sr">Buscar</span><input id="nsp-busca" data-digita="nsp-busca" type="search" placeholder="Protocolo, setor ou palavra do relato" value="${esc(est.nsp.busca)}"></label></div>
      <div class="chips" role="group" aria-label="Faixa" style="margin:4px 0 6px"><span class="rot-mini" style="align-self:center;margin-right:4px">Faixa</span>${['todas', 'A', 'B', 'C', 'D', 'E'].map((f) => `<button class="chip" data-acao="nsp-faixa" data-v="${f}" aria-pressed="${est.nsp.faixa === f}" title="${FX[f] || 'Todas as faixas'}">${f === 'todas' ? 'Todas' : f}</button>`).join('')}</div>
      <div class="tabela-rola"><table class="tab"><thead><tr><th>Faixa</th><th>Protocolo</th><th>Relato</th><th>Situação</th><th></th></tr></thead><tbody>${lista.map((c) => linhaCaso(c, true)).join('')}</tbody></table>
      ${lista.length ? '' : '<p class="vazio">Nenhum caso com esse filtro. Troque a situação ou a faixa, ou limpe a busca.</p>'}</div>
      <p class="sub" style="margin:10px 0 0">A faixa em tom claro é a sugestão do agente; ela só vale depois da triagem da Presidência.</p></section>`;
    return N.modulo({ sobre: SOBRE, titulo: 'Notificações', frase: `${CASOS.length} notificações de incidente. ${naFila().length} esperam a triagem da Presidência.`,
      acoes: `<a class="btn claro grande" href="#nsptriagem">Fila de triagem (${naFila().length})</a><button class="btn vidro grande" data-acao="nsp-rapido">Registro rápido</button>` }, null, '', corpo);
  } };
  N.digitar['nsp-busca'] = (v) => { est.nsp.busca = v; };
  N.acoes['nsp-sit'] = (a) => { est.nsp.sit = a.dataset.v; N.desenhar(); };
  N.acoes['nsp-faixa'] = (a) => { est.nsp.faixa = a.dataset.v; N.desenhar(); };

  // ------------------------------------------------------------------ Fila de triagem
  T.nsptriagem = { trilha: 'Fila de triagem', menu: 'nspnotificacoes', mapa: [SOBRE, 'Fila de triagem'], render() {
    const fila = naFila();
    const marcados = fila.filter((c) => est.nsp.lote[c.id]);
    const corpo = `${ABAS('#nspnotificacoes')}
      ${est.nsp.loteLigado ? `<p class="aviso">${I.info}Aprovação em lote ligada pela Diretoria Executiva em ${curto(dia(-6))}, com concordância de 93% nas últimas 4 semanas. Só as faixas D e E podem ir em lote.</p>` : ''}
      <section class="cartao bloco" style="margin-top:14px">
        <div class="cab"><h2 class="titulo-bloco">Graves primeiro (faixa A antes da B), depois da mais antiga para a mais nova</h2>
          ${est.nsp.loteLigado ? `<button class="btn" data-acao="nsp-lote" ${marcados.length ? '' : 'disabled style="opacity:.5;cursor:default"'}>Confirmar em lote (${marcados.length})</button>` : ''}</div>
        <ul class="linhas">${fila.map((c) => { const podeLote = est.nsp.loteLigado && ['D', 'E'].includes(c.sug);
          return `<li class="linha" style="grid-template-columns:32px 40px minmax(0,1fr) 150px 120px">
            <span>${podeLote ? `<input type="checkbox" aria-label="Incluir ${prot(c)} no lote" data-lote="${c.id}" ${est.nsp.lote[c.id] ? 'checked' : ''} style="width:20px;height:20px">` : ''}</span>
            ${faixa(c.sug)}
            <span class="t">${prot(c)} · ${esc(c.tipo)}${c.grave ? ' <span class="pill verm">Grave ou houve morte</span>' : ''}<small>${esc(c.setor)} · ${esc(c.origem)}</small></span>
            <span class="estado ${c.h > 48 ? 'e-venc' : 'e-hoje'}"><i aria-hidden="true"></i>${idade(c.h)}</span>
            <a class="btn" href="#nsptriar-${c.id}">Triar</a></li>`; }).join('')}</ul>
        ${fila.length ? '' : '<p class="vazio">Fila vazia. Toda notificação já foi triada.</p>'}
      </section>`;
    return N.modulo({ sobre: SOBRE, titulo: 'Fila de triagem', frase: 'O agente sugere a faixa e a Presidência confirma, ajusta ou encaminha. Faixas A, B e C sempre uma a uma.' }, null, '', corpo);
  }, depois() {
    document.querySelectorAll('[data-lote]').forEach((el) => el.addEventListener('change', () => { est.nsp.lote[el.dataset.lote] = el.checked; N.desenhar(); }));
  } };
  N.acoes['nsp-lote'] = () => {
    const m = naFila().filter((c) => est.nsp.lote[c.id]);
    if (!m.length) return;
    N.modal(`Confirmar ${m.length} ${m.length === 1 ? 'triagem' : 'triagens'} em lote`, `<p class="sub" style="margin:0 0 10px">Cada caso fica com a faixa que o agente sugeriu. Os prazos são calculados na hora.</p><ul style="margin:0;padding-left:20px">${m.map((c) => `<li>${prot(c)}, faixa ${c.sug}, ${esc(c.tipo)}</li>`).join('')}</ul>`,
      `<button type="button" class="btn" data-acao="nsp-lote-ok">Confirmar o lote</button>`);
  };
  N.acoes['nsp-lote-ok'] = () => { naFila().filter((c) => est.nsp.lote[c.id]).forEach((c) => { est.nsp.triados[c.id] = c.sug; }); est.nsp.lote = {}; N.fecharModal(); N.desenhar(); N.aviso('Triagens confirmadas em lote. Os prazos já correm.'); };

  // ------------------------------------------------------------------ Caso (leitura)
  function prazos(c) {
    const f = faixaDe(c) || c.sug;
    const legal = ['A'].includes(f) ? ['Notificação à vigilância sanitária', '72 horas corridas', `vence ${quando(dia(2))}, ${c.h < 24 ? '16:00' : '08:00'}`, 'e-venc'] : ['Notificação à vigilância sanitária', '15º dia útil do mês seguinte', `vence ${fmt(dia(21))}`, 'e-prox'];
    return [legal, ['Complementação da notificação', '60 dias corridos', `vence ${fmt(dia(58))}`, 'e-prox'], ['Triagem', 'Prazo interno', sitDe(c) === 'triagem' ? `vence ${quando(dia(c.grave ? 0 : 1))}` : 'cumprido', sitDe(c) === 'triagem' ? 'e-hoje' : 'e-ok'], ['Investigação', 'Prazo interno, aceita pausa com motivo', sitDe(c) === 'investigacao' ? `vence ${quando(dia(c.id === '0410' ? 2 : 12))}` : 'começa na triagem', 'e-prox']];
  }
  function etapas(c) {
    const ordem = ['Recebida', 'Triagem', 'Investigação', 'Plano de ação', 'Encerrada'];
    const i = { triagem: 1, investigacao: 2, encaminhado: 4, encerrado: 4 }[sitDe(c)];
    return `<ol class="etapas">${ordem.map((e, n) => `<li class="${n < i ? 'feito' : n === i ? 'agora' : ''}">${e}</li>`).join('')}</ol>`;
  }
  T.nspcaso = { trilha: (id) => 'Caso ' + (caso(id) ? prot(caso(id)) : ''), menu: 'nspnotificacoes', mapa: [SOBRE, 'Caso'], render(id) {
    const c = caso(id); if (!c) return `<div class="pagina"><h1 class="pagina-titulo">Caso não encontrado.</h1><p class="pagina-sub"><a href="#nspnotificacoes">Voltar às Notificações</a></p></div>`;
    const f = faixaDe(c); const [cls, txt] = SIT[sitDe(c)];
    return `<div class="pagina">
      <a class="voltar" href="#nspnotificacoes">${I.voltar}Voltar às Notificações</a>
      <section class="cartao bloco" style="padding:22px 24px">
        <div class="cab"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">${f ? faixa(f) : faixa(c.sug)}${N.estado(cls, txt)}<span class="pill">${esc(c.origem)}</span>${c.grave ? '<span class="pill verm">Grave ou houve morte</span>' : ''}</div>
          <div class="acoes-item">${sitDe(c) === 'triagem' ? `<a class="btn grande" href="#nsptriar-${c.id}">Triar este caso</a>` : `<button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o envio de mensagem a quem notificou, sem revelar a identidade.">Escrever a quem notificou</button>`}</div></div>
        <h1 class="pagina-titulo" style="margin-top:12px">${prot(c)} · ${esc(c.tipo)}</h1>
        <p class="pagina-sub">${esc(c.local)} · registrado ${idade(c.h)} · ${f ? 'faixa ' + f + ', ' + FX[f].toLowerCase() : 'faixa sugerida ' + c.sug + ', aguardando confirmação'}</p>
        <div style="margin-top:18px">${etapas(c)}</div>
      </section>
      <div class="duas" style="margin-top:14px">
        <section class="cartao bloco larga"><h2 class="titulo-bloco">O que aconteceu</h2><p class="nsp-relato" style="margin-top:10px">${esc(c.relato)}</p>
          <dl class="pares" style="margin-top:14px"><dt>Onde</dt><dd>${esc(c.local)}</dd><dt>O paciente foi atingido?</dt><dd>${esc(c.atingido)}</dd><dt>Quem notificou</dt><dd>${c.notif === 'Anônimo' ? 'Anônimo' : 'Visível só para a Presidência e o Acesso pleno'}</dd>${c.sit === 'encaminhado' ? `<dt>Encaminhado</dt><dd>${esc(c.destino)}, com o protocolo do Núcleo preservado</dd>` : ''}</dl>
          ${c.anexos.length ? `<h3 class="titulo-bloco" style="font-size:15px;margin-top:18px">Anexos</h3><div style="display:flex;flex-direction:column;gap:8px;margin-top:8px">${c.anexos.map((a) => `<div class="nsp-anexo"><span class="ic">${IC.anexo}</span><span style="flex:1">${esc(a)}</span><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o anexo.">Abrir</button></div>`).join('')}</div>` : ''}
          <h3 class="titulo-bloco" style="font-size:15px;margin-top:18px">Linha do tempo</h3>
          <ul class="tempo" style="margin-top:10px"><li class="feito"><i></i><b>Notificação registrada</b><span>${idade(c.h)} · ${esc(c.origem)}</span></li><li class="feito"><i></i><b>Agente sugeriu a faixa ${c.sug}</b><span>logo depois do registro</span></li>${f ? `<li class="feito"><i></i><b>Triagem confirmada na faixa ${f}</b><span>pela Presidência</span></li>` : `<li class="agora"><i></i><b>Aguardando a triagem</b><span>Presidência</span></li>`}</ul>
        </section>
        <aside class="estreita"><section class="cartao bloco"><h2 class="titulo-bloco">Prazos</h2>
          ${prazos(c).map(([t, r, v, e]) => `<div class="nsp-prazo"><span>${t}<small>${r}</small></span>${N.estado(e, v)}</div>`).join('')}
          <p class="sub" style="margin:10px 0 0">Prazo legal não pausa e não muda pela tela.</p></section>
          ${f === 'A' || c.sug === 'A' ? `<section class="cartao bloco"><h2 class="titulo-bloco">Notificação externa</h2><p class="sub" style="margin:6px 0 12px">Destino: VigiMed. O app prepara o texto; quem envia é a Presidência.</p><button class="btn contorno" data-acao="toast" data-msg="Protocolo da vigilância registrado no caso.">Registrar o protocolo</button></section>` : ''}
        </aside>
      </div>
    </div>`;
  } };

  // ------------------------------------------------------------------ Triagem do caso (tela larga)
  T.nsptriar = { trilha: (id) => 'Triagem ' + (caso(id) ? prot(caso(id)) : ''), menu: 'nspnotificacoes', mapa: [SOBRE, 'Triagem do caso'], render(id) {
    const c = caso(id); if (!c) return T.nspcaso.render(id);
    if (sitDe(c) !== 'triagem') return `<div class="pagina"><a class="voltar" href="#nsptriagem">${I.voltar}Voltar à fila de triagem</a><section class="cartao bloco entra" style="padding:26px;max-width:720px">${N.estado('e-ok', 'Triagem confirmada')}<h1 class="pagina-titulo" style="margin-top:10px">${prot(c)} na faixa ${faixaDe(c)}.</h1><p class="pagina-sub">Os prazos legais e internos já correm. ${faixaDe(c) === 'A' ? 'A notificação externa ao VigiMed entrou em O que exige ação hoje.' : ''}</p><div class="acoes-item" style="margin-top:18px"><a class="btn grande" href="#nspcaso-${c.id}">Ver os prazos do caso</a><a class="btn contorno grande" href="#nsptriagem">Próximo da fila</a></div></section></div>`;
    const f = est.nsp.ajuste[c.id] || c.sug;
    const campos = [['tipo', 'Tipo de incidente', c.tipo, 'O relato fala em dose e prescrição.'], ['dano', 'Dano ao paciente', c.atingido, 'Quem notificou marcou "' + c.atingido + '".'], ['faixa', 'Faixa', `${f}, ${FX[f]}`, 'Na dúvida entre duas faixas, vale a mais alta.'], ['externa', 'Notificação externa', f === 'A' ? 'VigiMed, 72 horas' : 'NOTIVISA, 15º dia útil do mês seguinte', 'Calculado pela faixa e pelo tipo.']];
    const conf = est.nsp.conferidos[c.id] || {};
    const falta = c.grave ? campos.filter(([k]) => !conf[k]).length : 0;
    return `<div class="pagina">
      <div class="cab"><a class="voltar" href="#nsptriagem" style="margin:0">${I.voltar}Voltar à fila de triagem</a><span class="sub">${prot(c)} · registrado ${idade(c.h)}</span></div>
      <div class="cab" style="margin-top:10px"><h1 class="pagina-titulo">Triagem de ${prot(c)}</h1>${c.grave ? '<span class="pill verm">Grave ou houve morte: confira cada campo</span>' : ''}</div>
      <div class="nsp-larga">
        <section class="cartao bloco"><h2 class="titulo-bloco">Relato de quem notificou</h2><p class="nsp-relato" style="margin-top:10px">${esc(c.relato)}</p>
          <dl class="pares" style="margin-top:14px"><dt>Onde</dt><dd>${esc(c.local)}</dd><dt>Setor</dt><dd>${esc(c.setor)}</dd><dt>Atingido</dt><dd>${esc(c.atingido)}</dd><dt>Origem</dt><dd>${esc(c.origem)}</dd><dt>Quem notificou</dt><dd>${c.notif === 'Anônimo' ? 'Anônimo' : esc(c.notif)} <span class="sub">(só a Presidência vê)</span></dd></dl>
          ${c.anexos.length ? `<div style="display:flex;flex-direction:column;gap:8px;margin-top:14px">${c.anexos.map((a) => `<div class="nsp-anexo"><span class="ic">${IC.anexo}</span><span style="flex:1">${esc(a)}</span><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o anexo ao lado.">Abrir</button></div>`).join('')}</div>` : '<p class="sub" style="margin-top:14px">Sem anexos.</p>'}
        </section>
        <section class="cartao bloco"><div class="cab"><h2 class="titulo-bloco">Sugestão do agente</h2><span class="pill">${est.nsp.ajuste[c.id] ? 'Ajustada por você' : 'Sugerida'}</span></div>
          <div style="display:flex;flex-direction:column;gap:8px;margin-top:12px">${campos.map(([k, t, v, por]) => `<div class="nsp-eixo"><div class="top"><b>${t}</b>${k === 'faixa' ? faixa(f) : ''}</div><span style="font-size:14.5px">${esc(v)}</span><p>${esc(por)}</p>
            ${c.grave ? `<label class="nsp-conf"><input type="checkbox" data-conf="${c.id}:${k}" ${conf[k] ? 'checked' : ''}>Conferi este campo</label>` : ''}</div>`).join('')}</div>
          <h3 class="titulo-bloco" style="font-size:15px;margin-top:16px">O que o sistema calculou</h3>
          ${prazos({ ...c, faixa: f }).slice(0, 3).map(([t, r, v, e]) => `<div class="nsp-prazo"><span>${t}<small>${r}</small></span>${N.estado(e, v)}</div>`).join('')}
          <div class="acoes-item" style="margin-top:16px;justify-content:flex-end">
            <button class="btn contorno" data-acao="nsp-encaminhar" data-id="${c.id}">Encaminhar</button>
            <button class="btn contorno" data-acao="nsp-ajustar" data-id="${c.id}">Ajustar</button>
            <button class="btn" data-acao="nsp-confirmar" data-id="${c.id}" ${falta ? `disabled style="opacity:.5;cursor:default" title="Falta conferir ${falta} campos"` : ''}>Confirmar faixa ${f}</button>
          </div>${falta ? `<p class="sub" style="text-align:right;margin:8px 0 0">Falta conferir ${falta} ${falta === 1 ? 'campo' : 'campos'} para confirmar.</p>` : ''}
        </section>
      </div>
    </div>`;
  }, depois() {
    document.querySelectorAll('[data-conf]').forEach((el) => el.addEventListener('change', () => { const [id, k] = el.dataset.conf.split(':'); (est.nsp.conferidos[id] = est.nsp.conferidos[id] || {})[k] = el.checked; N.desenhar(); }));
  } };
  N.acoes['nsp-confirmar'] = (a) => { const c = caso(a.dataset.id); est.nsp.triados[c.id] = est.nsp.ajuste[c.id] || c.sug; N.desenhar(true); N.aviso(`Triagem confirmada na faixa ${est.nsp.triados[c.id]}. Os prazos já correm.`); };
  N.acoes['nsp-ajustar'] = (a) => { const c = caso(a.dataset.id); const f = est.nsp.ajuste[c.id] || c.sug;
    N.modal('Ajustar a faixa', `<p class="sub" style="margin:0 0 12px">A sugestão do agente fica registrada ao lado da sua decisão, para medir a concordância.</p><div class="opcoes-grandes">${['A', 'B', 'C', 'D', 'E'].map((x) => `<button type="button" class="opcao-g" data-acao="nsp-ajuste-ok" data-id="${c.id}" data-v="${x}" aria-pressed="${x === f}"><b>Faixa ${x}</b><small>${FX[x]}</small></button>`).join('')}</div>`, ''); };
  N.acoes['nsp-ajuste-ok'] = (a) => { est.nsp.ajuste[a.dataset.id] = a.dataset.v; N.fecharModal(); N.desenhar(); N.aviso(`Faixa ajustada para ${a.dataset.v}. Confirme para gravar os prazos.`); };
  N.acoes['nsp-encaminhar'] = (a) => N.modal('Encaminhar o caso', `<div class="campo"><label for="nsp-dest">Destino</label><select id="nsp-dest"><option>Ouvidoria</option><option>Canal de Conduta (nenhum conteúdo é transferido)</option><option>Segurança do Trabalho</option><option>Queixa técnica</option><option>Encerrar como fora de escopo</option></select></div>
    <div class="campo" style="margin-top:12px"><label for="nsp-mot">Motivo, em uma frase</label><input id="nsp-mot"></div><p class="sub" style="margin:10px 0 0">O protocolo do Núcleo é preservado. O caso pode seguir no Núcleo e em outro destino ao mesmo tempo.</p>`,
    `<button type="button" class="btn" data-acao="toast" data-msg="Caso encaminhado. O protocolo do Núcleo continua valendo.">Encaminhar</button>`);

  // ------------------------------------------------------------------ Reuniões do Núcleo
  const REU = [
    { id: 'n1', off: -27, hora: '08:00', tipo: 'Ordinária', ata: 'Aprovada', pres: 7, total: 8, pauta: ['Indicadores de outubro', 'Notificações do mês', 'Plano de Segurança do Paciente'] },
    { id: 'r4', off: 6, hora: '08:00', tipo: 'Ordinária', ata: 'A Reunião ainda não aconteceu', pres: null, total: 8, pauta: ['Indicadores de queda', 'Notificações do mês', 'Caso NSP-' + ANO + '-0410'] },
    { id: 'n3', off: 2, hora: '13:30', tipo: 'Rápida de segurança', ata: 'A Reunião ainda não aconteceu', pres: null, total: 4, pauta: ['Heparina na UTI adulto: dupla checagem'] },
    { id: 'n4', off: 34, hora: '08:00', tipo: 'Ordinária', ata: 'A Reunião ainda não aconteceu', pres: null, total: 8, pauta: ['Fechamento do ano', 'Calendário do ano que vem'] }
  ];
  T.nspreunioes = { trilha: 'Reuniões do Núcleo', menu: 'nspreunioes', mapa: [SOBRE, 'Reuniões do Núcleo'], render() {
    const ord = [...REU].sort((a, b) => a.off - b.off);
    const corpo = `${ABAS('#nspreunioes')}<section class="cartao bloco" style="margin-top:14px"><ul class="linhas">${ord.map((r) => { const d = dia(r.off); const passada = r.off < 0;
      return `<li class="linha" style="grid-template-columns:130px minmax(0,1fr) 150px 110px 110px"><span class="num">${curto(d)}, ${r.hora}<small class="sub" style="display:block">${quando(d)}</small></span>
        <span class="t">Reunião ${r.tipo === 'Ordinária' ? 'ordinária' : 'rápida de segurança'} do Núcleo<small>${r.pauta.map(esc).join(' · ')}</small></span>
        <span class="pill ${passada ? 'verde' : ''}">${passada ? 'Ata ' + r.ata.toLowerCase() : r.tipo}</span>
        <button class="btn contorno" data-acao="nsp-pauta" data-id="${r.id}">Pauta</button>
        <button class="btn ${passada ? 'contorno' : ''}" data-acao="nsp-presenca-r" data-id="${r.id}">${passada ? 'Presença' : 'Presença'}</button></li>`; }).join('')}</ul></section>`;
    return N.modulo({ sobre: SOBRE, titulo: 'Reuniões do Núcleo', frase: `Próxima: ${quando(dia(2))}, a reunião rápida de segurança sobre a heparina da UTI adulto.`,
      acoes: `<button class="btn claro grande" data-acao="toast" data-msg="No sistema, abre a nova Reunião do Núcleo, comum ou rápida.">Nova Reunião</button><button class="btn vidro grande" data-acao="toast" data-msg="Calendário do ano gerado: 12 Reuniões ordinárias, na primeira quinta de cada mês.">Gerar o calendário do ano</button>` }, null, '', corpo);
  } };
  N.acoes['nsp-pauta'] = (a) => { const r = REU.find((x) => x.id === a.dataset.id);
    N.abrirGaveta({ sobre: `<span class="pill">${r.tipo}</span>`, titulo: `Pauta de ${curto(dia(r.off))}, ${r.hora}`,
      corpo: `<ol style="margin:0;padding-left:20px;display:flex;flex-direction:column;gap:8px">${r.pauta.map((p) => `<li>${esc(p)}</li>`).join('')}</ol><div class="campo"><label for="nsp-item">Incluir item na pauta</label><input id="nsp-item" placeholder="Ex.: caso NSP-${ANO}-0418"></div>`,
      pe: `<button class="btn" data-acao="fechar-gaveta">Salvar a pauta</button>` }); };
  N.acoes['nsp-presenca-r'] = (a) => { const r = REU.find((x) => x.id === a.dataset.id);
    const membros = MEMBROS.filter((m) => m.sit === 'Vigente');
    N.abrirGaveta({ sobre: `<span class="pill">${r.tipo}</span>`, titulo: `Presença em ${curto(dia(r.off))}`,
      corpo: `<p class="sub" style="margin:0">Quórum: maioria dos membros com Participação vigente.</p><ul class="linhas">${membros.map((m, i) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">${esc(m.nome)}<small>${esc(m.papel)}</small></span><label class="nsp-conf" style="margin:0"><input type="checkbox" ${r.off < 0 && i !== 3 ? 'checked' : ''}>Presente</label></li>`).join('')}</ul>`,
      pe: `<button class="btn" data-acao="fechar-gaveta">Salvar a presença</button>` }); };

  // ------------------------------------------------------------------ Núcleo: membros, documentos, capacitações, agenda, notas
  const MEMBROS = [
    { nome: 'Fernanda Lima', papel: 'Presidência', setor: 'CCIH', vig: `01/02/${ANO - 1} a 31/01/${ANO + 1}`, termo: 'Assinado', sit: 'Vigente' },
    { nome: 'Carla Nogueira', papel: 'Suplente da Presidência', setor: 'Enfermagem', vig: `01/02/${ANO - 1} a 31/01/${ANO + 1}`, termo: 'Assinado', sit: 'Vigente' },
    { nome: 'Renata Alves', papel: 'Membro', setor: 'Diretoria Assistencial', vig: `01/02/${ANO - 1} a 31/01/${ANO + 1}`, termo: 'Assinado', sit: 'Vigente' },
    { nome: 'Rodrigo Sales', papel: 'Membro', setor: 'Farmácia', vig: `01/03/${ANO} a 28/02/${ANO + 2}`, termo: 'Aguardando assinatura', sit: 'Vigente' },
    { nome: 'Paulo Mendes', papel: 'Membro', setor: 'Suprimentos', vig: `01/02/${ANO - 1} a 31/01/${ANO + 1}`, termo: 'Assinado', sit: 'Vigente' },
    { nome: 'Juliana Prado', papel: 'Membro', setor: 'Hotelaria', vig: `01/02/${ANO - 2} a 31/01/${ANO}`, termo: 'Assinado', sit: 'Encerrada' }
  ];
  const DOCS = [['Regimento interno', 2, 'Vigente desde ' + curto(dia(-3)), 'Assinado pela Presidência e pelo Responsável técnico'], ['Plano de Segurança do Paciente', 3, 'Vigente desde ' + curto(dia(-90)), 'Assinado'], ['Ato de designação', 1, 'Vigente desde ' + curto(dia(-300)), 'Assinado pelo Responsável técnico'], ['Plano de Segurança do Paciente', 4, 'Em assinatura', '1 de 2 assinaturas']];
  const AGENDA = [['Relatório mensal à vigilância sanitária', 'Mensal', 5, 'Enviado em dia'], ['Autoavaliação das práticas de segurança', 'Anual', 41, 'Nota 82 em ' + (ANO - 1)], ['Revisão do Plano de Segurança do Paciente', 'Anual', 120, 'Revisado']];
  const NOTAS = [[dia(-9), 'O Comitê de Conduta sinaliza um padrão de passagem de plantão incompleta na UTI adulto. Sem nomes, sem conteúdo do relato.'], [dia(-40), 'O Comitê sugere incluir comunicação não violenta na capacitação anual.']];
  T.nspnucleo = { trilha: 'Núcleo', menu: 'nspnucleo', mapa: [SOBRE, 'Núcleo: membros, documentos, capacitações, agenda e notas'], render() {
    const A = [['membros', 'Membros'], ['documentos', 'Documentos'], ['capacitacoes', 'Capacitações'], ['agenda', 'Agenda regulatória'], ['notas', 'Notas do Comitê']];
    const a = est.nsp.nucleoAba;
    let miolo = '';
    if (a === 'membros') miolo = `<div class="ferramentas"><span class="sub">Participação vencida não recebe caso nem conta para quórum. O histórico fica.</span><button class="btn" data-acao="toast" data-msg="No sistema, abre a inclusão de membro com vigência e o envio do Termo de Adesão.">Incluir membro</button></div>
      <div class="tabela-rola"><table class="tab"><thead><tr><th>Membro</th><th>Papel</th><th>Vigência</th><th>Termo de Adesão</th><th>Situação</th><th></th></tr></thead><tbody>${MEMBROS.map((m, i) => `<tr><td><a href="#" data-acao="nsp-membro" data-i="${i}">${esc(m.nome)}</a><div class="sub">${esc(m.setor)}</div></td><td>${esc(m.papel)}</td><td class="num">${m.vig}</td><td>${N.estado(m.termo === 'Assinado' ? 'e-ok' : 'e-hoje', m.termo)}</td><td><span class="pill ${m.sit === 'Vigente' ? 'verde' : 'cinza'}">${m.sit}</span></td><td style="text-align:right"><button class="btn contorno" data-acao="nsp-membro" data-i="${i}">Abrir</button></td></tr>`).join('')}</tbody></table></div>`;
    if (a === 'documentos') miolo = `<div class="ferramentas"><span class="sub">A versão nova vale depois de assinada. As anteriores ficam no histórico.</span><button class="btn" data-acao="toast" data-msg="No sistema, abre o envio da versão nova: publicar ou enviar para assinatura.">Publicar versão nova</button></div>
      <div class="grade g2">${DOCS.map(([t, v, s, ass]) => `<section class="cartao bloco"><div class="cab"><span class="pill ${s.startsWith('Em') ? 'laranja' : 'verde'}">v${v}</span><span class="sub">${s}</span></div><h3 class="titulo-bloco" style="margin-top:10px">${t}</h3><p class="sub" style="margin:4px 0 12px">${ass}</p><div class="acoes-item"><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o PDF.">${IC.baixar}Baixar</button>${s.startsWith('Em') ? '<button class="btn contorno" data-acao="toast" data-msg="Lembrete de assinatura reenviado.">Lembrar quem falta</button>' : ''}</div></section>`).join('')}</div>`;
    if (a === 'capacitacoes') miolo = `<div class="grade g2"><section class="cartao bloco"><h3 class="titulo-bloco">Próximas</h3><ul class="linhas"><li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">Comunicação de evento adverso<small>${quando(dia(1))}, 15:00, auditório · 6 de 8 confirmados</small></span>${est.feitos.p13 ? N.estado('e-ok', 'Confirmada') : '<button class="btn" data-acao="nsp-presenca">Confirmar minha presença</button>'}</li><li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">Análise de causa raiz<small>${fmt(dia(19))}, 14:00 · 3 de 8 confirmados</small></span><button class="btn contorno" data-acao="toast" data-msg="Presença confirmada.">Confirmar</button></li></ul></section>
      <section class="cartao bloco"><div class="cab"><h3 class="titulo-bloco">Temas mínimos por membro</h3><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre a gestão dos temas: incluir, renomear, desativar.">Gerir temas</button></div><div class="tabela-rola"><table class="tab" style="min-width:0"><thead><tr><th>Membro</th><th>Feitos</th><th></th></tr></thead><tbody>${MEMBROS.filter((m) => m.sit === 'Vigente').map((m, i) => { const n = [4, 3, 3, 1, 2][i]; return `<tr><td>${esc(m.nome)}</td><td class="num">${n} de 4</td><td style="width:40%"><div class="prog ${n < 2 ? 'verm' : n === 4 ? 'verde' : ''}"><span style="width:${n * 25}%"></span></div></td></tr>`; }).join('')}</tbody></table></div></section></div>`;
    if (a === 'agenda') miolo = `<div class="ferramentas"><span class="sub">O que a norma pede ao Núcleo com data marcada.</span><button class="btn" data-acao="toast" data-msg="No sistema, abre a inclusão de evento com periodicidade e lembrete.">Incluir evento</button></div><ul class="linhas">${AGENDA.map(([t, p, off, ult]) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) 110px 150px 170px"><span class="t">${t}<small>Último resultado: ${ult}</small></span><span class="pill">${p}</span>${N.estado(off <= 7 ? 'e-hoje' : 'e-prox', 'até ' + curto(dia(off)))}<button class="btn ${off <= 7 ? '' : 'contorno'}" data-acao="toast" data-msg="Resultado registrado. A próxima data já foi calculada.">Registrar resultado</button></li>`).join('')}</ul>`;
    if (a === 'notas') miolo = `<p class="sub" style="margin:0 0 6px">Sinais que o Comitê de Conduta manda ao Núcleo. Só leitura, sem conteúdo dos relatos.</p><ul class="tempo" style="margin-top:12px">${NOTAS.map(([d, t]) => `<li class="feito"><i></i><b>${fmt(d)}</b><p style="margin:4px 0 0;font-size:14.5px">${esc(t)}</p></li>`).join('')}</ul>`;
    const corpo = `${ABAS('#nspnucleo')}<section class="cartao bloco" style="margin-top:14px"><div class="abas" role="tablist" style="margin:0 0 14px">${A.map(([k, t]) => `<button type="button" role="tab" aria-selected="${a === k}" data-acao="nsp-aba" data-v="${k}">${t}</button>`).join('')}</div>${miolo}</section>`;
    return N.modulo({ sobre: SOBRE, titulo: 'Núcleo', frase: `${MEMBROS.filter((m) => m.sit === 'Vigente').length} membros com Participação vigente. ${MEMBROS.filter((m) => m.termo !== 'Assinado').length} Termo de Adesão aguarda assinatura.` }, null, '', corpo);
  } };
  N.acoes['nsp-aba'] = (a) => { est.nsp.nucleoAba = a.dataset.v; N.desenhar(); };
  N.acoes['nsp-membro'] = (a) => { const m = MEMBROS[Number(a.dataset.i)];
    N.abrirGaveta({ sobre: `<span class="pill ${m.sit === 'Vigente' ? 'verde' : 'cinza'}">${m.sit}</span>`, titulo: esc(m.nome),
      corpo: `<dl class="pares"><dt>Papel</dt><dd>${esc(m.papel)}</dd><dt>Setor</dt><dd>${esc(m.setor)}</dd><dt>Vigência</dt><dd>${m.vig}</dd><dt>Termo de Adesão</dt><dd>${N.estado(m.termo === 'Assinado' ? 'e-ok' : 'e-hoje', m.termo)}</dd></dl>
        ${m.termo !== 'Assinado' ? `<div class="acoes-item"><button class="btn contorno" data-acao="toast" data-msg="Situação da assinatura consultada na ClickSign.">Reconsultar</button><button class="btn contorno" data-acao="toast" data-msg="Termo reenviado para assinatura.">Reenviar o Termo</button></div>` : ''}
        ${m.papel === 'Presidência' ? `<div class="aviso" style="margin:0">${I.info}Ausência registrada dá os poderes da Presidência ao suplente só dentro do período.</div><button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o registro de ausência com início e fim.">Registrar ausência da Presidência</button>` : ''}
        <h3 class="titulo-bloco" style="font-size:15px">Histórico</h3><ul class="tempo"><li class="feito"><i></i><b>Participação iniciada</b><span>${m.vig.split(' a ')[0]}</span></li><li class="${m.termo === 'Assinado' ? 'feito' : 'agora'}"><i></i><b>Termo de Adesão ${m.termo === 'Assinado' ? 'assinado' : 'enviado'}</b><span>pela ClickSign</span></li></ul>`,
      pe: m.sit === 'Vigente' ? `<button class="btn contorno" data-acao="toast" data-msg="Participação encerrada hoje. O histórico fica.">Encerrar participação</button><button class="btn" data-acao="toast" data-msg="No sistema, abre a edição do papel e da vigência.">Editar</button>` : '' }); };

  // ------------------------------------------------------------------ Configuração (com a Recalibração)
  T.nspconfig = { trilha: 'Configuração do Núcleo', menu: 'nspconfig', mapa: [SOBRE, 'Configuração e Recalibração'], render() {
    const eixos = [['Tipo de incidente', 96], ['Dano ao paciente', 91], ['Faixa', 93], ['Encaminhamento', 88]];
    const corpo = `${ABAS('#nspconfig')}
      <div class="grade g2">
        <section class="cartao bloco"><h2 class="titulo-bloco">Onde se notifica</h2><div style="display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin-top:12px"><span class="nsp-qr">${IC.qr.replace(/width="18" height="18"/, 'width="72" height="72"')}</span><div style="flex:1 1 200px;min-width:0"><p style="margin:0;font-size:14.5px;overflow-wrap:anywhere">hospitalsaomatheus.com.br/notificar</p><p class="sub" style="margin:4px 0 12px">O formulário não guarda IP de quem notifica.</p><div class="acoes-item"><button class="btn contorno" data-acao="toast" data-msg="Endereço copiado.">${IC.copiar}Copiar</button><button class="btn contorno" data-acao="toast" data-msg="No sistema, baixa o cartaz A4 com o QR.">${IC.baixar}Cartaz A4</button></div></div></div></section>
        <section class="cartao bloco"><h2 class="titulo-bloco">Concordância do agente</h2><p class="sub" style="margin:4px 0 10px">Período de sombra: sugestão do agente contra a decisão da Presidência, eixo por eixo, últimas 4 semanas.</p>${eixos.map(([t, v]) => `<div style="margin-top:10px"><div style="display:flex;justify-content:space-between;font-size:14px"><span>${t}</span><span class="num">${v}%</span></div><div class="prog ${v >= 90 ? 'verde' : ''}" style="margin-top:6px"><span style="width:${v}%"></span></div></div>`).join('')}<p class="sub" style="margin:12px 0 0">Erros para baixo (faixa sugerida mais leve que a confirmada): 2 de 61.</p></section>
        <section class="cartao bloco"><h2 class="titulo-bloco">Prazos</h2><p class="sub" style="margin:4px 0 10px">Legal fica travado. Interno pode ser mais rígido, nunca mais frouxo, e não retroage.</p>
          <div class="nsp-prazo"><span>Óbito e evento que nunca deveria ocorrer<small>Legal</small></span><span class="pill cinza">72 horas corridas</span></div>
          <div class="nsp-prazo"><span>Demais incidentes<small>Legal</small></span><span class="pill cinza">15º dia útil do mês seguinte</span></div>
          ${[['Confirmação a quem notificou', 1], ['Triagem, faixas A e B', 1], ['Triagem, faixas C a E', 3], ['Investigação, faixa C', 15]].map(([t, v]) => `<div class="nsp-prazo"><span>${t}<small>Interno</small></span><span style="display:flex;align-items:center;gap:6px"><input type="number" value="${v}" min="1" aria-label="${t}" style="width:68px;min-height:38px;padding:0 8px;border:1px solid var(--campo-borda);border-radius:8px;background:var(--campo);color:var(--texto)"><span class="sub">dias úteis</span></span></div>`).join('')}
          <div class="acoes-item" style="margin-top:12px;justify-content:flex-end"><button class="btn" data-acao="toast" data-msg="Prazos internos salvos. Valem para os casos triados daqui em diante.">Salvar os prazos</button></div></section>
        <section class="cartao bloco" id="recalibracao"><div class="cab"><h2 class="titulo-bloco">Recalibração</h2><span class="pill laranja">Marco de 30 dias</span></div><p class="sub" style="margin:4px 0 12px">A pendência "Recalibrar o agente do NSP" aponta para cá. Itens que dependem das Fases 3 e 4 aparecem sem dados.</p>
          <ul class="tempo"><li class="feito"><i></i><b>Marco de 30 dias</b><span>${fmt(dia(-6))} · concordância 93%, decisão: ligar a Aprovação em lote</span></li><li class="agora"><i></i><b>Marco de 60 dias</b><span>${fmt(dia(24))} · aguardando</span></li></ul>
          <button type="button" class="nsp-toggle" data-acao="nsp-lote-liga" aria-pressed="${est.nsp.loteLigado}"><i aria-hidden="true"></i>Aprovação em lote das faixas D e E</button>
          <p class="sub" style="margin:8px 0 0">Só a Diretoria Executiva liga, com concordância de 90% ou mais.</p></section>
        <section class="cartao bloco"><h2 class="titulo-bloco">Cortes de frequência</h2><p class="sub" style="margin:4px 0 10px">Quantas notificações do mesmo tipo e setor num mês acendem o sinal de alerta.</p>${[['Queda', 3], ['Erro de medicação', 2], ['Lesão por pressão', 2]].map(([t, v]) => `<div class="nsp-prazo"><span>${t}</span><span class="num">${v} por mês</span></div>`).join('')}</section>
      </div>`;
    return N.modulo({ sobre: SOBRE, titulo: 'Configuração', frase: 'Onde se notifica, os prazos internos, a concordância do agente e a Recalibração, num lugar só.' }, null, '', corpo);
  } };
  N.acoes['nsp-lote-liga'] = () => { est.nsp.loteLigado = !est.nsp.loteLigado; N.desenhar(); N.aviso(est.nsp.loteLigado ? 'Aprovação em lote ligada para as faixas D e E.' : 'Aprovação em lote desligada. Toda triagem volta a ser uma a uma.'); };

  // ------------------------------------------------------------------ Notificar incidente (logado), 4 passos
  const PASSOS = ['O que aconteceu', 'Onde e quando', 'O paciente foi atingido?', 'Quem notifica'];
  const ATING = [['nao', 'Não chegou ao paciente', 'Foi percebido antes'], ['sem', 'Chegou, sem dano', 'Nada aconteceu com o paciente'], ['dano', 'Chegou, com dano', 'O paciente sofreu alguma consequência'], ['obito', 'Houve morte', 'O Núcleo é avisado na hora'], ['naosei', 'Não sei', 'Tudo bem, o Núcleo apura']];
  T.notificar = { trilha: 'Notificar incidente', menu: 'notificar', mapa: [SOBRE, 'Notificar incidente'], render() {
    const p = N.PERFIS[N.perfil()];
    const fm = est.nsp.form;
    if (est.nsp.recibo) {
      const r = est.nsp.recibo;
      return N.modulo({ sobre: SOBRE, titulo: 'Obrigado por notificar.', frase: 'O Núcleo recebeu o relato e vai analisar. Notificar ajuda a evitar que aconteça de novo.' }, null, '', `<section class="cartao bloco entra" style="padding:26px;max-width:760px">
        ${N.estado('e-ok', 'Notificação recebida')}<p class="rot-mini" style="margin:16px 0 4px">Protocolo</p><p class="nsp-recibo" style="margin:0">${r.prot}</p>
        ${r.anon ? `<p class="rot-mini" style="margin:14px 0 4px">Código de acompanhamento</p><p class="nsp-recibo" style="margin:0;font-size:22px">${r.cod}</p><p class="sub">Guarde os dois. Sem eles, ninguém consegue achar a notificação anônima, nem o Núcleo.</p>` : `<p class="sub" style="margin:8px 0 0">Você recebe a confirmação no e-mail da sua conta.</p>`}
        <div style="margin-top:20px;padding:16px;border-radius:10px;background:var(--suave)"><h2 class="titulo-bloco" style="font-size:15.5px">Duas perguntas que podem ajudar</h2><p class="sub" style="margin:4px 0 12px">Opcionais. A notificação já está registrada.</p>
          <div class="campo"><label for="pe1">A dose foi conferida por outra pessoa antes de administrar?</label><input id="pe1"></div><div class="campo" style="margin-top:10px"><label for="pe2">Havia outro paciente com nome parecido no setor?</label><input id="pe2"></div>
          <button class="btn contorno" style="margin-top:12px" data-acao="toast" data-msg="Respostas enviadas ao Núcleo.">Enviar as respostas</button></div>
        <div class="acoes-item" style="margin-top:20px"><a class="btn grande" href="#inicio">Voltar ao Início</a><button class="btn contorno grande" data-acao="toast" data-msg="No sistema, abre o acompanhamento com o protocolo já preenchido.">Acompanhar a notificação</button><button class="btn contorno grande" data-acao="nsp-nova">Notificar outro incidente</button></div>
        <p class="nsp-naopune">Notificar não é denunciar. O Núcleo olha o processo, não procura culpado.</p></section>`);
    }
    const n = est.nsp.passo;
    let miolo = '';
    if (n === 1) miolo = `<div class="campo"><label for="nf-relato">Conte o que aconteceu</label><textarea id="nf-relato" data-nf="relato" style="min-height:150px" placeholder="O que você viu, com as suas palavras. Sem o nome do paciente.">${esc(fm.relato || '')}</textarea></div>
      <div class="grade-form" style="margin-top:14px"><div class="campo"><label for="nf-leito">Leito ou prontuário (opcional)</label><input id="nf-leito" data-nf="leito" value="${esc(fm.leito || '')}" placeholder="Ex.: leito 12"></div></div>
      <label class="solta" style="display:block;margin-top:14px;cursor:pointer"><b>${IC.anexo} Anexar até 3 arquivos</b>Foto, PDF ou documento, somando até 9 MB<input type="file" hidden multiple></label>`;
    if (n === 2) miolo = `<div class="grade-form"><div class="campo"><label for="nf-setor">Setor</label><select id="nf-setor" data-nf="setor">${['', 'UTI adulto', 'Emergência', 'Centro Cirúrgico', 'Enfermaria 2º andar', 'Enfermaria 3º andar', 'Farmácia', 'Outro'].map((s) => `<option ${fm.setor === s ? 'selected' : ''} value="${s}">${s || 'Escolha'}</option>`).join('')}</select></div>
      <div class="campo"><label for="nf-data">Quando</label><input id="nf-data" type="date" data-nf="data" value="${fm.data || N.iso(HOJE)}"></div><div class="campo"><label for="nf-hora">Hora aproximada</label><input id="nf-hora" type="time" data-nf="hora" value="${fm.hora || ''}"></div></div>`;
    if (n === 3) miolo = `<div class="opcoes-grandes">${ATING.map(([k, t, s]) => `<button type="button" class="opcao-g" data-acao="nf-ating" data-v="${k}" aria-pressed="${fm.ating === k}"><b>${t}</b><small>${s}</small></button>`).join('')}</div>`;
    if (n === 4) miolo = `<div class="opcoes-grandes"><button type="button" class="opcao-g" data-acao="nf-anon" data-v="nao" aria-pressed="${!fm.anon}"><b>Como ${esc(p.nome)}</b><small>Só a Presidência do Núcleo vê quem notificou</small></button><button type="button" class="opcao-g" data-acao="nf-anon" data-v="sim" aria-pressed="${!!fm.anon}"><b>Sem me identificar</b><small>Você recebe um código para acompanhar</small></button></div>
      <div style="margin-top:16px;padding:14px 16px;border-radius:8px;background:var(--suave)"><span class="rot-mini">Revisão</span><dl class="pares" style="margin-top:8px"><dt>O que aconteceu</dt><dd>${esc((fm.relato || 'Não preenchido').slice(0, 140))}</dd><dt>Onde</dt><dd>${esc(fm.setor || 'Não preenchido')}</dd><dt>Atingido</dt><dd>${(ATING.find((x) => x[0] === fm.ating) || [0, 'Não preenchido'])[1]}</dd></dl></div>`;
    const corpo = `<section class="cartao bloco" style="padding:24px;max-width:860px">
      <div class="passos-pub" aria-hidden="true">${PASSOS.map((_, i) => `<span class="${i < n ? 'on' : ''}"></span>`).join('')}</div>
      <p class="rot-mini" style="margin:0">Passo ${n} de 4</p><h2 class="titulo-bloco" style="font-size:20px;margin:4px 0 16px">${PASSOS[n - 1]}</h2>${miolo}
      <div class="acoes-item" style="margin-top:22px;justify-content:space-between">${n > 1 ? `<button class="btn contorno grande" data-acao="nf-passo" data-v="-1">Voltar</button>` : '<span></span>'}${n < 4 ? `<button class="btn grande" data-acao="nf-passo" data-v="1">Continuar</button>` : `<button class="btn grande" data-acao="nf-enviar">Enviar a notificação</button>`}</div>
      <p class="nsp-naopune">Ninguém é punido por notificar. O Núcleo olha o processo, não a pessoa.</p></section>`;
    return N.modulo({ sobre: SOBRE, titulo: 'Notificar incidente', frase: 'Quem notifica conta o que viu e não precisa classificar. Leva menos de 2 minutos.' }, null, '', corpo);
  } };
  function guardarForm() { document.querySelectorAll('[data-nf]').forEach((el) => { est.nsp.form[el.dataset.nf] = el.value; }); }
  N.acoes['nf-passo'] = (a) => { guardarForm(); const v = Number(a.dataset.v);
    if (v > 0 && est.nsp.passo === 1 && !(est.nsp.form.relato || '').trim()) { N.aviso('Conte com as suas palavras o que aconteceu para continuar.'); return; }
    est.nsp.passo = Math.min(4, Math.max(1, est.nsp.passo + v)); N.desenhar(true); };
  N.acoes['nf-ating'] = (a) => { est.nsp.form.ating = a.dataset.v; N.desenhar(); };
  N.acoes['nf-anon'] = (a) => { est.nsp.form.anon = a.dataset.v === 'sim'; N.desenhar(); };
  N.acoes['nf-enviar'] = () => { est.nsp.recibo = { prot: `NSP-${ANO}-0${419 + Math.floor(Math.random() * 30)}`, anon: !!est.nsp.form.anon, cod: 'K7Q-' + Math.floor(1000 + Math.random() * 9000) }; N.desenhar(true); };
  N.acoes['nsp-nova'] = () => { est.nsp.recibo = null; est.nsp.form = {}; est.nsp.passo = 1; N.desenhar(true); };
})();
