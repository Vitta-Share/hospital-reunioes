/* Qualidade e segurança: POPs (Gestão, Biblioteca, Elaboração e Versão) e Ouvidoria
   (Fila, Painel, Dossiê, Avaliações, Triagem de e-mail, Pontos de escuta, Responsáveis e Prazos). */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I, IC, dia, fmt, curto, est, HOJE } = N;
  const T = N.telas;
  est.pops2 = { chip: 'todos', busca: '', bibBusca: '', chat: [], secFeitas: 7 };
  est.ouv = { chip: 'todos', busca: '', arquivados: false, aba: 'resumo', painelSel: null, email: 'e1', emailAba: 'pendentes', avPeriodo: 30, avFiltro: 'todas', resp: 'aresponder', prazosMudou: false };

  N.css(`
  .q-mais{position:relative;display:inline-flex}
  .q-acoes-linha{display:flex;align-items:center;justify-content:flex-end;gap:6px}
  .ouv-grupo{margin-top:14px}
  .ouv-grupo .cab{padding-bottom:10px;border-bottom:1px solid var(--linha)}
  .ouv-grupo h2 .n{font-size:13px;font-weight:700;color:var(--texto2);background:var(--suave);border-radius:999px;padding:2px 9px}
  .ouv-grade{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-top:12px}
  .ouv-card{position:relative;display:flex;flex-direction:column;gap:8px;padding:14px 16px;border:1px solid var(--borda);border-radius:10px;background:var(--cartao)}
  .ouv-card .topo-c{display:flex;align-items:center;justify-content:space-between;gap:8px}
  .ouv-card .prot{font-size:12.5px;font-weight:700;letter-spacing:.03em;color:var(--texto2)}
  .ouv-card h3{margin:0;font-size:15.5px;line-height:1.3;color:var(--titulo)}
  .ouv-card h3 a{color:inherit;text-decoration:none}
  .ouv-card h3 a:hover{text-decoration:underline}
  .ouv-card .meta{font-size:13px;color:var(--texto2)}
  .ouv-card .pe-c{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:4px}
  .ouv-card .novo{position:absolute;top:12px;right:12px;width:8px;height:8px;border-radius:999px;background:var(--ponto-azul)}
  .faixa-g{height:4px;border-radius:4px;margin:-14px -16px 4px;border-radius:10px 10px 0 0}
  .dossie{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:14px;align-items:start;margin-top:14px}
  .dossie .lado{display:flex;flex-direction:column;gap:14px;position:sticky;top:14px}
  .faz-agora{border:1px solid var(--titulo);box-shadow:inset 0 0 0 1px var(--titulo)}
  .faz-agora .btn{width:100%}
  .q-relato{white-space:pre-line;font-size:15px;line-height:1.55;background:var(--suave);border-radius:8px;padding:14px 16px;margin:0}
  .q-anexo{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--borda);border-radius:8px;font-size:14px;color:var(--texto)}
  .q-anexo span{margin-left:auto;font-size:12.5px;color:var(--texto2)}
  .email-duas{display:grid;grid-template-columns:360px minmax(0,1fr);gap:14px;margin-top:14px;align-items:start}
  .email-lista{list-style:none;margin:10px 0 0;padding:0;display:flex;flex-direction:column;gap:4px}
  .email-lista button{display:block;width:100%;text-align:left;padding:10px 12px;border:0;border-radius:8px;background:transparent;cursor:pointer;color:var(--texto)}
  .email-lista button:hover{background:var(--suave)}
  .email-lista button[aria-current="true"]{background:var(--suave2)}
  .email-lista b{display:block;font-size:14.5px;color:var(--titulo)}
  .email-lista small{display:block;font-size:12.5px;color:var(--texto2);margin-top:2px}
  .qr{display:block;width:104px;height:104px;border-radius:8px;background:#fff;padding:6px;border:1px solid var(--borda)}
  .ponto{display:flex;gap:16px;align-items:flex-start}
  .estrelas{color:var(--ponto-laranja);letter-spacing:1px;font-size:15px}
  .estrelas .apag{color:var(--suave2)}
  .barra-h{display:grid;grid-template-columns:70px 1fr 40px;gap:10px;align-items:center;font-size:13.5px;margin-top:8px}
  .grade-prazos{width:100%;border-collapse:separate;border-spacing:0 6px}
  .grade-prazos th{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--texto2);text-align:left;padding:4px 10px}
  .grade-prazos td{padding:6px 10px;background:var(--suave)}
  .grade-prazos td:first-child{border-radius:8px 0 0 8px;font-weight:700;color:var(--titulo)}
  .grade-prazos td:last-child{border-radius:0 8px 8px 0}
  .grade-prazos input{width:70px;min-height:38px;padding:6px 8px;border:1px solid var(--campo-borda);border-radius:7px;background:var(--campo);color:var(--texto);font-variant-numeric:tabular-nums}
  .grade-prazos input.mudou{border-color:var(--ponto-laranja);box-shadow:0 0 0 2px rgba(245,158,11,.2)}
  .pop-vivo{display:flex;flex-direction:column;gap:4px}
  .pop-sec{padding:14px 4px;border-bottom:1px solid var(--linha)}
  .pop-sec:last-child{border-bottom:0}
  .pop-sec h3{margin:0;font-size:15px;color:var(--titulo);display:flex;align-items:center;gap:10px}
  .pop-sec h3 .nsec{flex:none;width:24px;height:24px;border-radius:999px;background:var(--suave2);color:var(--titulo);font-size:12px;display:inline-flex;align-items:center;justify-content:center}
  .pop-sec.feita h3 .nsec{background:var(--btn-fundo);color:#fff}
  .pop-sec p,.pop-sec ol,.pop-sec ul{margin:8px 0 0 34px;font-size:14.5px;line-height:1.5}
  .pop-sec .falta{margin:8px 0 0 34px;padding:10px 12px;border:1px dashed var(--campo-borda);border-radius:8px;color:var(--texto2);font-size:13.5px}
  .pop-sec.nova{animation:entra .4s ease both;background:var(--suave)}
  .fluxo{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:10px 0 0 34px}
  .fluxo span{padding:6px 10px;border-radius:7px;background:var(--suave2);color:var(--titulo);font-size:13px}
  .fluxo i{font-style:normal;color:var(--texto2)}
  .elab{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:14px;align-items:start;margin-top:14px}
  .elab .chat{position:sticky;top:14px;display:flex;flex-direction:column;gap:12px;max-height:calc(100vh - 40px)}
  .elab .chat .conversa{overflow:auto;flex:1;min-height:200px;padding-right:4px}
  .barra-topo{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px}
  .devol{border-left:3px solid var(--ponto-laranja);background:var(--suave);border-radius:0 8px 8px 0;padding:10px 14px;font-size:14px}
  .devol b{display:block;color:var(--titulo)}
  @media (max-width:1100px){.dossie,.elab,.email-duas{grid-template-columns:1fr}.dossie .lado,.elab .chat{position:static}}
  `);

  const pill = (cls, t) => `<span class="pill ${cls}">${t}</span>`;
  const mais = (chave, itens) => `<span class="q-mais"><button type="button" class="mais" data-pop="${chave}" aria-expanded="${est.pop === chave}" aria-label="Mais opções">${I.tres}</button>${est.pop === chave ? `<div class="pop" role="menu">${itens.join('')}</div>` : ''}</span>`;
  const fecharPop = () => { est.pop = null; N.desenhar(); };

  // ================================================================== POPs
  const ESTADOS = { elaborar: ['cinza', 'A elaborar'], elaboracao: ['laranja', 'Em elaboração'], revisao: ['laranja', 'Em revisão'], validacao: ['laranja', 'Em validação'], assinatura: ['', 'Em assinatura'], publicada: ['verde', 'Publicada'] };
  const POPS = [
    { id: 'pop1', cod: 'POP-ASS-014', nome: 'Identificação do paciente', setor: 'Diretoria Assistencial', crit: 'Alta', v: 3, est: 'revisao', com: 'Renata Alves', papel: 'Revisora', el: 'Carla Nogueira', rev: 'Renata Alves', val: 'Fernanda Lima', prazo: 5, item: 'p8' },
    { id: 'pop2', cod: 'POP-CCI-007', nome: 'Coleta de hemocultura', setor: 'CCIH', crit: 'Alta', v: 2, est: 'validacao', com: 'Renata Alves', papel: 'Validadora', el: 'Fernanda Lima', rev: 'Carla Nogueira', val: 'Renata Alves', prazo: 8, item: 'p9' },
    { id: 'pop6', cod: 'POP-ASS-021', nome: 'Administração de hemocomponentes', setor: 'Diretoria Assistencial', crit: 'Alta', v: 1, est: 'elaboracao', com: 'Renata Alves', papel: 'Elaboradora', el: 'Renata Alves', rev: 'Carla Nogueira', val: 'Fernanda Lima', prazo: 12 },
    { id: 'pop7', cod: 'POP-FAR-003', nome: 'Dupla checagem de medicamentos de alta vigilância', setor: 'Farmácia', crit: 'Alta', v: 2, est: 'elaboracao', com: 'Rodrigo Sales', papel: 'Elaborador', el: 'Rodrigo Sales', rev: 'Renata Alves', val: 'Fernanda Lima', prazo: -3 },
    { id: 'pop8', cod: 'POP-HOT-002', nome: 'Troca de enxoval', setor: 'Hotelaria', crit: 'Baixa', v: 1, est: 'elaborar', com: 'Juliana Prado', papel: 'Elaboradora', el: 'Juliana Prado', rev: 'Renata Alves', val: 'Renata Alves', prazo: 20 },
    { id: 'pop9', cod: 'POP-ASS-009', nome: 'Prevenção de lesão por pressão', setor: 'Enfermagem', crit: 'Média', v: 3, est: 'assinatura', com: 'ClickSign', papel: 'Assinaturas', el: 'Carla Nogueira', rev: 'Renata Alves', val: 'Fernanda Lima', prazo: 2 },
    { id: 'pop3', cod: 'POP-CCI-001', nome: 'Higienização das mãos', setor: 'CCIH', crit: 'Alta', v: 5, est: 'publicada', pub: -40, revisao: 325, el: 'Fernanda Lima', rev: 'Carla Nogueira', val: 'Renata Alves' },
    { id: 'pop4', cod: 'POP-ASS-011', nome: 'Prevenção de quedas', setor: 'Diretoria Assistencial', crit: 'Alta', v: 4, est: 'publicada', pub: -120, revisao: 22, el: 'Carla Nogueira', rev: 'Renata Alves', val: 'Fernanda Lima' },
    { id: 'pop5', cod: 'POP-ENF-004', nome: 'Passagem de plantão', setor: 'Enfermagem', crit: 'Média', v: 2, est: 'publicada', pub: -200, revisao: 165, el: 'Carla Nogueira', rev: 'Renata Alves', val: 'Renata Alves' },
    { id: 'pop10', cod: 'POP-FAR-001', nome: 'Dispensação de psicotrópicos', setor: 'Farmácia', crit: 'Alta', v: 3, est: 'publicada', pub: -60, revisao: 305, el: 'Rodrigo Sales', rev: 'Renata Alves', val: 'Fernanda Lima' },
    { id: 'pop11', cod: 'POP-SUP-002', nome: 'Recebimento de materiais estéreis', setor: 'Suprimentos', crit: 'Média', v: 1, est: 'publicada', pub: -15, revisao: 350, el: 'Paulo Mendes', rev: 'Renata Alves', val: 'Renata Alves' },
    { id: 'pop12', cod: 'POP-HOT-001', nome: 'Limpeza terminal do leito', setor: 'Hotelaria', crit: 'Alta', v: 2, est: 'publicada', pub: -90, revisao: 275, el: 'Juliana Prado', rev: 'Fernanda Lima', val: 'Renata Alves' }
  ];
  const popDe = (id) => POPS.find((p) => p.id === id);
  const comigo = (p) => p.com === 'Renata Alves' && N.perfil() === 'facilitadora';
  const ACAO_POP = { Elaboradora: ['Elaborar', (p) => `#popelaboracao-${p.id}`], Revisora: ['Revisar', (p) => `#popversao-${p.id}`], Validadora: ['Validar', (p) => `#popversao-${p.id}`] };

  function cabPops(atual) {
    const abertos = POPS.filter((p) => p.est !== 'publicada');
    const meus = POPS.filter(comigo);
    const venc = POPS.filter((p) => p.est === 'publicada' && p.revisao <= 30);
    return {
      cab: { sobre: 'Qualidade e segurança', titulo: atual === '#popsbiblioteca' ? 'Biblioteca de POPs' : 'POPs',
        frase: atual === '#popsbiblioteca' ? `${POPS.filter((p) => p.est === 'publicada').length} procedimentos publicados, sempre na versão vigente e assinada.` : `${meus.length} POPs esperam você agora e ${abertos.length - meus.length} seguem com outras pessoas. ${venc.length} precisa de revisão nos próximos 30 dias.`,
        acoes: atual === '#pops' ? `<button class="btn claro grande" data-acao="pop-novo">Criar novo POP</button>` : `<a class="btn claro grande" href="#pops">Ir para a Gestão</a>` },
      resumo: atual === '#pops' ? [['Com você agora', String(meus.length).padStart(2, '0'), I.alerta, '#pops', meus.length > 0], ['Em andamento', String(abertos.length).padStart(2, '0'), I.relogio, '#pops'], ['Revisão em 30 dias', String(venc.length).padStart(2, '0'), I.agenda, '#popsbiblioteca'], ['Publicados', String(POPS.filter((p) => p.est === 'publicada').length).padStart(2, '0'), I.certo, '#popsbiblioteca']] : null,
      abas: N.abasModulo([['#pops', 'Gestão', abertos.length], ['#popsbiblioteca', 'Biblioteca', POPS.filter((p) => p.est === 'publicada').length]], atual)
    };
  }

  T.pops = { trilha: 'POPs', menu: 'pops', mapa: ['POPs', 'Gestão de POPs'], render() {
    const c = cabPops('#pops');
    const CH = [['todos', 'Todos'], ['comigo', 'Com você'], ['elaboracao', 'Em elaboração'], ['revisao', 'Em revisão'], ['validacao', 'Em validação'], ['assinatura', 'Em assinatura'], ['publicada', 'Publicados']];
    const t = est.pops2.busca.trim().toLowerCase();
    const lista = POPS.filter((p) => est.pops2.chip === 'todos' || (est.pops2.chip === 'comigo' ? comigo(p) : p.est === est.pops2.chip || (est.pops2.chip === 'elaboracao' && p.est === 'elaborar')))
      .filter((p) => !t || (p.nome + ' ' + p.cod + ' ' + p.setor).toLowerCase().includes(t))
      .sort((a, b) => (comigo(b) - comigo(a)) || ((a.est === 'publicada') - (b.est === 'publicada')) || ((a.prazo ?? 99) - (b.prazo ?? 99)));
    const linha = (p) => {
      const [cls, txt] = ESTADOS[p.est];
      const minha = comigo(p) && ACAO_POP[p.papel];
      const principal = minha ? `<a class="btn" href="${ACAO_POP[p.papel][1](p)}">${ACAO_POP[p.papel][0]}</a>` : p.est === 'publicada' ? `<button class="btn contorno" data-acao="pop-ficha" data-id="${p.id}">Ler</button>` : `<a class="btn contorno" href="#popversao-${p.id}">Ver</a>`;
      const menu = mais('popm-' + p.id, [
        `<button type="button" data-acao="pop-papeis" data-id="${p.id}">Ver e trocar papéis</button>`,
        `<button type="button" data-acao="pop-pdf" data-id="${p.id}">Baixar o PDF ${p.est === 'publicada' ? 'assinado' : 'de rascunho'}</button>`,
        `<a href="#popversao-${p.id}">Abrir a versão ${p.v}</a>`,
        p.com && p.com !== 'Renata Alves' && p.com !== 'ClickSign' ? `<button type="button" data-acao="pop-lembrar" data-id="${p.id}">Lembrar ${esc(p.com.split(' ')[0])}</button>` : '',
        N.perfil() === 'admin' ? `<button type="button" data-acao="pop-excluir" data-id="${p.id}" style="color:var(--verm);border-top:1px solid var(--linha);border-radius:0 0 7px 7px">Excluir o POP</button>` : ''
      ]);
      const etapa = p.est === 'publicada' ? `<span class="sub">Revisão em ${p.revisao} dias</span>` : `${p.com === 'Renata Alves' && N.perfil() === 'facilitadora' ? '<b style="color:var(--titulo)">Com você</b>' : esc(p.com)}<div class="sub">${p.papel || ''}${p.prazo !== undefined ? ` · ${p.prazo < 0 ? `<span style="color:var(--verm)">prazo passou há ${-p.prazo} dias</span>` : 'até ' + curto(dia(p.prazo))}` : ''}</div>`;
      return `<tr><td class="num" style="white-space:nowrap;color:var(--texto2);font-size:13px">${p.cod}</td>
        <td><a href="#" data-acao="pop-ficha" data-id="${p.id}">${esc(p.nome)}</a><div class="sub">${esc(p.setor)}</div></td>
        <td>${pill(p.crit === 'Alta' ? 'verm' : p.crit === 'Média' ? 'laranja' : 'cinza', p.crit)}</td>
        <td><span class="num" style="font-weight:700;color:var(--titulo)">v${p.v}</span> ${pill(cls, txt)}</td>
        <td>${etapa}</td>
        <td><div class="q-acoes-linha">${principal}${menu}</div></td></tr>`;
    };
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas"><div class="chips" role="group" aria-label="Filtrar por estado">${CH.map(([k, t2]) => `<button type="button" class="chip" data-acao="pop-chip" data-v="${k}" aria-pressed="${est.pops2.chip === k}">${t2}</button>`).join('')}</div>
        <label class="busca-lista">${IC.busca}<span class="sr">Buscar POP</span><input id="pop-busca" data-digita="pop-busca" type="search" placeholder="Buscar por nome, código ou setor" value="${esc(est.pops2.busca)}"></label></div>
      <div class="tabela-rola"><table class="tab"><thead><tr><th>Código</th><th>POP</th><th>Criticidade</th><th>Versão</th><th>Com quem está</th><th></th></tr></thead><tbody>${lista.map(linha).join('')}</tbody></table>
      ${lista.length ? '' : '<p class="vazio">Nenhum POP neste filtro. Troque o filtro ou crie um POP novo pelo botão no alto.</p>'}</div></section>`;
    return N.modulo(c.cab, c.resumo, c.abas, corpo);
  } };
  N.digitar['pop-busca'] = (v) => { est.pops2.busca = v; };
  N.acoes['pop-chip'] = (a) => { est.pops2.chip = a.dataset.v; N.desenhar(); };
  N.acoes['pop-lembrar'] = (a) => { const p = popDe(a.dataset.id); fecharPop(); N.aviso(`Lembrete enviado para ${p.com.split(' ')[0]}.`); };
  N.acoes['pop-pdf'] = (a) => { const p = popDe(a.dataset.id); fecharPop(); N.aviso(`No sistema, baixa o PDF de ${p.cod} v${p.v}.`); };
  N.acoes['pop-papeis'] = (a) => {
    const p = popDe(a.dataset.id); fecharPop();
    const PESSOAS = ['Renata Alves', 'Carla Nogueira', 'Fernanda Lima', 'Rodrigo Sales', 'Paulo Mendes', 'Juliana Prado'];
    const sel = (id, rot, v) => `<div class="campo"><label for="${id}">${rot}</label><select id="${id}">${PESSOAS.map((x) => `<option${x === v ? ' selected' : ''}>${x}</option>`).join('')}</select></div>`;
    N.modal(`Papéis de ${esc(p.nome)}`, `<p class="sub" style="margin:0 0 14px">${p.cod} · versão ${p.v}. Trocar um papel avisa a pessoa nova e a antiga.</p><div class="grade-form">${sel('pp-el', 'Elaborador', p.el)}${sel('pp-rev', 'Revisor', p.rev)}${sel('pp-val', 'Validador', p.val)}</div>`,
      `<button type="button" class="btn" data-acao="toast" data-msg="Papéis salvos. Quem mudou foi avisado.">Salvar papéis</button>`);
  };
  N.acoes['pop-excluir'] = (a) => {
    const p = popDe(a.dataset.id); fecharPop();
    N.modal('Excluir o POP?', `<p style="margin:0 0 12px">${esc(p.nome)} (${p.cod}) sai da Gestão e da Biblioteca. As versões assinadas ficam guardadas para auditoria.</p><div class="campo"><label for="px-mot">Motivo</label><textarea id="px-mot" required></textarea></div>`,
      `<button type="submit" class="btn" style="background:var(--verm);border-color:var(--verm)">Excluir</button>`, 'form-pop-excluir');
    N.envios['form-pop-excluir'] = () => { POPS.splice(POPS.indexOf(p), 1); N.fecharModal(); N.desenhar(); N.aviso('POP excluído, com o motivo registrado.'); };
  };
  N.acoes['pop-novo'] = () => {
    const PESSOAS = ['Carla Nogueira', 'Renata Alves', 'Fernanda Lima', 'Rodrigo Sales', 'Paulo Mendes', 'Juliana Prado'];
    const sel = (id, rot, i) => `<div class="campo"><label for="${id}">${rot}</label><select id="${id}" required><option value="">Escolha</option>${PESSOAS.map((x, n) => `<option${n === i ? ' selected' : ''}>${x}</option>`).join('')}</select></div>`;
    N.modal('Criar novo POP', `<div style="display:flex;flex-direction:column;gap:14px">
      <div class="campo"><label for="pn-nome">Nome do POP</label><input id="pn-nome" required placeholder="Ex.: Contenção mecânica do paciente agitado"></div>
      <div class="grade-form"><div class="campo"><label for="pn-setor">Setor</label><select id="pn-setor" required><option>Diretoria Assistencial</option><option>Enfermagem</option><option>CCIH</option><option>Farmácia</option><option>Hotelaria</option><option>Suprimentos</option></select></div>
        <div class="campo"><label for="pn-crit">Criticidade</label><select id="pn-crit"><option>Alta</option><option selected>Média</option><option>Baixa</option></select></div></div>
      <div class="grade-form">${sel('pn-el', 'Elaborador', 0)}${sel('pn-rev', 'Revisor', 1)}${sel('pn-val', 'Validador', 2)}</div>
      <div class="grade-form"><div class="campo"><label for="pn-prazo">Prazo da elaboração</label><input id="pn-prazo" type="date" value="${N.iso(dia(21))}"></div>
        <div class="campo"><label for="pn-per">Revisão a cada</label><select id="pn-per"><option>12 meses</option><option>24 meses</option><option>6 meses</option></select></div></div>
      <div class="campo"><label for="pn-norma">Base normativa (opcional)</label><input id="pn-norma" placeholder="Ex.: RDC 36/2013, Protocolo do Ministério da Saúde"></div></div>`,
    `<button type="submit" class="btn">Criar e avisar o Elaborador</button>`, 'form-pop-novo');
  };
  N.envios['form-pop-novo'] = () => {
    const nome = document.getElementById('pn-nome').value.trim(); const setor = document.getElementById('pn-setor').value; const el = document.getElementById('pn-el').value;
    POPS.unshift({ id: 'popn' + Date.now(), cod: 'POP-NOV-' + String(POPS.length + 1).padStart(3, '0'), nome, setor, crit: document.getElementById('pn-crit').value, v: 1, est: 'elaborar', com: el, papel: 'Elaborador', el, rev: document.getElementById('pn-rev').value, val: document.getElementById('pn-val').value, prazo: 21 });
    N.fecharModal(); est.pops2.chip = 'todos'; N.desenhar(); N.aviso(`POP criado. ${el.split(' ')[0]} recebeu o aviso para começar a elaboração.`);
  };

  // Ficha em gaveta (Biblioteca e Gestão)
  N.acoes['pop-ficha'] = (a) => {
    const p = popDe(a.dataset.id); if (!p) return; fecharPop();
    const [cls, txt] = ESTADOS[p.est];
    const pub = p.est === 'publicada';
    const marcos = pub ? [['Elaborada', p.el, p.pub - 30], ['Revisada', p.rev, p.pub - 20], ['Validada', p.val, p.pub - 12], ['Assinada e publicada', 'ClickSign', p.pub]] : [['Criada', 'Renata Alves', -30], ['Em ' + txt.toLowerCase().replace('em ', ''), p.com, -2]];
    N.abrirGaveta({ sobre: `<div style="display:flex;gap:8px">${pill(cls, txt)}${pill(p.crit === 'Alta' ? 'verm' : 'cinza', 'Criticidade ' + p.crit.toLowerCase())}</div>`, titulo: esc(p.nome),
      corpo: `<dl class="pares"><dt>Código</dt><dd class="num">${p.cod} · versão ${p.v}</dd><dt>Setor</dt><dd>${esc(p.setor)}</dd><dt>Elaborador</dt><dd>${esc(p.el)}</dd><dt>Revisor</dt><dd>${esc(p.rev)}</dd><dt>Validador</dt><dd>${esc(p.val)}</dd>
        ${pub ? `<dt>Vigente desde</dt><dd class="num">${fmt(dia(p.pub))}</dd><dt>Próxima revisão</dt><dd class="num">${fmt(dia(p.revisao))}${p.revisao <= 30 ? ' <span style="color:var(--laranja)">(em breve)</span>' : ''}</dd>` : ''}</dl>
        <div><h3 class="titulo-bloco" style="font-size:15px;margin-bottom:10px">Etapas desta versão</h3><ul class="tempo">${marcos.map(([e, q, d]) => `<li class="feito"><i aria-hidden="true"></i><b>${e}</b><span>${esc(q)} · ${fmt(dia(d))}</span></li>`).join('')}</ul></div>
        ${pub ? '<div class="aviso" style="margin:0">' + I.info + 'Esta é a versão assinada que vale hoje. As versões anteriores ficam no histórico.</div>' : ''}`,
      pe: `${pub ? `<button class="btn contorno" data-acao="toast" data-msg="No sistema, abre o histórico de versões.">Versões anteriores</button><button class="btn" data-acao="toast" data-msg="No sistema, baixa o PDF assinado de ${p.cod} v${p.v}.">${IC.baixar}Baixar o PDF assinado</button>` : `<a class="btn" href="#popversao-${p.id}" data-acao="fechar-gaveta-ir" data-href="#popversao-${p.id}">Abrir a versão</a>`}` });
  };

  // Biblioteca
  T.popsbiblioteca = { trilha: 'POPs', menu: 'pops', mapa: ['POPs', 'Biblioteca'], render() {
    const c = cabPops('#popsbiblioteca');
    const t = est.pops2.bibBusca.trim().toLowerCase();
    const pubs = POPS.filter((p) => p.est === 'publicada').filter((p) => !t || (p.nome + ' ' + p.cod + ' ' + p.setor).toLowerCase().includes(t));
    const setores = [...new Set(pubs.map((p) => p.setor))].sort();
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas"><p class="sub" style="margin:0">Clique num POP para ver a ficha e baixar o PDF assinado.</p>
        <label class="busca-lista">${IC.busca}<span class="sr">Buscar na Biblioteca</span><input id="bib-busca" data-digita="bib-busca" type="search" placeholder="Buscar por nome, código ou setor" value="${esc(est.pops2.bibBusca)}"></label></div>
      ${setores.map((s) => `<h2 class="titulo-bloco" style="margin-top:18px;font-size:15px">${esc(s)} <span class="sub" style="font-weight:400">${pubs.filter((p) => p.setor === s).length}</span></h2>
        <ul class="linhas">${pubs.filter((p) => p.setor === s).map((p) => `<li class="linha" style="grid-template-columns:110px minmax(0,1fr) 150px 160px"><span class="num sub">${p.cod}</span><span class="t"><a href="#" data-acao="pop-ficha" data-id="${p.id}" style="color:var(--texto);font-weight:700;text-decoration:none">${esc(p.nome)}</a><small>Versão ${p.v} · vigente desde ${fmt(dia(p.pub))}</small></span>
          <span>${p.revisao <= 30 ? pill('laranja', 'Revisão em ' + p.revisao + ' dias') : pill('verde', 'Em dia')}</span>
          <button class="btn contorno" data-acao="toast" data-msg="No sistema, baixa o PDF assinado de ${p.cod} v${p.v}.">${IC.baixar}PDF assinado</button></li>`).join('')}</ul>`).join('')}
      ${pubs.length ? '' : '<p class="vazio">Nenhum POP publicado com esse texto. Tente o código (ex.: POP-CCI) ou o nome do setor.</p>'}
    </section>`;
    return N.modulo(c.cab, null, c.abas, corpo);
  } };
  N.digitar['bib-busca'] = (v) => { est.pops2.bibBusca = v; };

  // Seções do POP vivo
  const SECOES = ['Objetivo', 'Abrangência', 'Responsáveis', 'Definições e siglas', 'Materiais e recursos', 'Descrição das atividades', 'Fluxograma', 'Pontos críticos e riscos', 'Indicadores', 'Referências normativas', 'Anexos e registros'];
  const CONTEUDO = {
    pop6: [
      '<p>Garantir que todo hemocomponente seja administrado ao paciente certo, na hora certa e com a vigilância das reações transfusionais.</p>',
      '<p>UTI adulto, enfermarias clínicas e cirúrgicas, Centro Cirúrgico e Emergência.</p>',
      '<ul><li>Médico: prescreve e assina o termo de consentimento.</li><li>Enfermeiro: confere, instala e acompanha os primeiros 15 minutos.</li><li>Técnico de enfermagem: verifica os sinais vitais nos tempos previstos.</li></ul>',
      '<p>CH: concentrado de hemácias. CP: concentrado de plaquetas. PFC: plasma fresco congelado. RT: reação transfusional.</p>',
      '<ul><li>Equipo com filtro de 170 a 260 micra.</li><li>Pulseira de identificação com QR code.</li><li>Ficha de acompanhamento transfusional.</li></ul>',
      '<ol><li>Conferir a prescrição e o consentimento.</li><li>Fazer a dupla checagem à beira do leito, com dois profissionais.</li><li>Verificar os sinais vitais antes de instalar.</li><li>Instalar e permanecer ao lado do paciente nos primeiros 15 minutos.</li></ol>',
      '<div class="fluxo"><span>Prescrição</span><i>›</i><span>Dupla checagem</span><i>›</i><span>Sinais vitais</span><i>›</i><span>Instalação</span><i>›</i><span>15 min ao lado</span><i>›</i><span>Registro</span></div>',
      '<ul><li>Troca de bolsa entre pacientes de nomes parecidos.</li><li>Reação nos primeiros 15 minutos sem ninguém ao lado.</li></ul>',
      '<p>Taxa de dupla checagem registrada (meta: 100%). Reações transfusionais notificadas ao NSP por 1.000 transfusões.</p>',
      '<p>RDC 34/2014 da Anvisa. Guia para uso de hemocomponentes do Ministério da Saúde.</p>',
      '<p>Ficha de acompanhamento transfusional (anexo 1). Termo de consentimento (anexo 2).</p>'
    ],
    pop1: [
      '<p>Assegurar a identificação correta do paciente em todos os cuidados, do registro na recepção até a alta.</p>',
      '<p>Todas as unidades de internação, Emergência, Centro Cirúrgico e serviços de diagnóstico.</p>',
      '<ul><li>Recepção: emite a pulseira com nome completo, data de nascimento e QR code.</li><li>Equipe assistencial: confere dois identificadores antes de qualquer cuidado.</li></ul>',
      '<p>Identificadores: nome completo e data de nascimento. Nunca o número do leito.</p>',
      '<ul><li>Pulseira branca com QR code. Pulseira vermelha para alergia.</li></ul>',
      '<ol><li>Colocar a pulseira na admissão, no punho dominante livre.</li><li>Perguntar o nome e a data de nascimento antes de medicar, coletar ou transportar.</li><li><b>Novo na versão 3:</b> ler o QR code antes de hemocomponentes.</li></ol>',
      '<div class="fluxo"><span>Admissão</span><i>›</i><span>Pulseira</span><i>›</i><span>Pergunta ativa</span><i>›</i><span>Leitura do QR</span><i>›</i><span>Cuidado</span></div>',
      '<ul><li>Paciente sedado ou que não fala: conferir com o acompanhante e a pulseira.</li></ul>',
      '<p>Adesão à pergunta ativa nas auditorias mensais (meta: 95%).</p>',
      '<p>Protocolo de identificação do paciente, Ministério da Saúde e Anvisa, 2013.</p>',
      '<p>Modelo da pulseira (anexo 1).</p>'
    ]
  };

  function etapasPop(p) {
    const ord = ['elaborar', 'elaboracao', 'revisao', 'validacao', 'assinatura', 'publicada'];
    const nomes = ['A elaborar', 'Elaboração', 'Revisão técnica', 'Validação final', 'Assinatura', 'Publicada'];
    const i = ord.indexOf(p.est);
    return `<ol class="etapas">${nomes.map((n, k) => `<li class="${k < i ? 'feito' : k === i ? 'agora' : ''}">${n}</li>`).join('')}</ol>`;
  }

  // Elaboração: POP vivo à esquerda, conversa com o agente à direita
  T.popelaboracao = { trilha: 'POPs', menu: 'pops', mapa: ['POPs', 'Elaboração de um POP'], render(id) {
    const p = popDe(id || 'pop6') || popDe('pop6');
    const cont = CONTEUDO.pop6;
    const feitas = est.pops2.secFeitas;
    if (!est.pops2.chat.length) est.pops2.chat = [
      ['ela', 'Agente', 'Oi, Renata. Já montei as seções de 1 a 7 com o que você me mandou ontem. Faltam Pontos críticos, Indicadores, Referências e Anexos.'],
      ['ela', 'Agente', 'Para os Pontos críticos: quais erros já aconteceram aqui com hemocomponentes? Pode contar do seu jeito, eu organizo.']
    ];
    return `<div class="pagina">
      <a class="voltar" href="#pops">${I.voltar}Voltar aos POPs</a>
      <div class="cartao bloco" style="padding:20px 24px">
        <div class="barra-topo"><div><span class="sub num">${p.cod} · versão ${p.v} · prazo ${fmt(dia(p.prazo || 12))}</span><h1 class="pagina-titulo" style="margin-top:4px">${esc(p.nome)}</h1></div>
          <div class="acoes-item"><button class="btn contorno grande" data-acao="toast" data-msg="No sistema, abre a prévia do PDF com o layout oficial.">${IC.olho}Prévia do PDF</button><button class="btn grande" data-acao="pop-aprovar-final" data-id="${p.id}"${feitas < 11 ? ' title="Ainda faltam seções"' : ''}>Aprovar versão final</button></div></div>
        ${etapasPop({ est: 'elaboracao' })}
      </div>
      <div class="elab">
        <section class="cartao bloco" aria-label="POP vivo">
          <div class="cab"><h2>POP vivo</h2><span class="sub num">${feitas} de 11 seções prontas</span></div>
          <div class="prog" style="margin:10px 0 4px"><span style="width:${feitas / 11 * 100}%"></span></div>
          <div class="pop-vivo">${SECOES.map((s, k) => `<div class="pop-sec ${k < feitas ? 'feita' : ''} ${k === feitas - 1 && feitas > 7 ? 'nova' : ''}" id="sec-${k + 1}"><h3><span class="nsec">${k + 1}</span>${s}${k < feitas ? `<button class="mais" style="margin-left:auto;width:auto;padding:0 8px;font-size:12.5px;font-weight:700;gap:6px;color:var(--acento)" data-acao="pop-apontar" data-sec="${s}">${IC.lapis}Corrigir pela conversa</button>` : ''}</h3>
            ${k < feitas ? cont[k] : '<p class="falta">O agente vai perguntar o que falta para esta seção.</p>'}</div>`).join('')}</div>
        </section>
        <aside class="cartao bloco chat" aria-label="Conversa com o agente">
          <div class="cab"><h2>Conversa com o agente</h2><span class="pill">Rascunho salvo</span></div>
          <div class="conversa" id="pop-conversa">${est.pops2.chat.map(([q, nome, t]) => `<div class="balao ${q}"><small>${nome}</small>${esc(t)}</div>`).join('')}</div>
          <div class="q-anexo">${IC.anexo}Materiais: protocolo-transfusao-2024.pdf<span>usado só quando você pede</span></div>
          <div class="escrever"><label for="pop-msg" class="sr">Mensagem para o agente</label><textarea id="pop-msg" placeholder="Responda ou peça uma mudança numa seção"></textarea>
            <button class="btn" data-acao="toast" data-msg="No sistema, grava a sua voz e transcreve." aria-label="Falar">${IC.microfone}</button><button class="btn" data-acao="pop-enviar" aria-label="Enviar">${IC.enviar}</button></div>
        </aside>
      </div>
      <p class="demo">Dados de demonstração.</p>
    </div>`;
  }, depois() { const c = document.getElementById('pop-conversa'); if (c) c.scrollTop = c.scrollHeight; } };
  N.acoes['pop-apontar'] = (a) => { const m = document.getElementById('pop-msg'); m.value = `Na seção ${a.dataset.sec}: `; m.focus(); };
  N.acoes['pop-enviar'] = () => {
    const t = document.getElementById('pop-msg').value.trim(); if (!t) return;
    est.pops2.chat.push(['eu', 'Você', t]);
    if (est.pops2.secFeitas < 11) { est.pops2.secFeitas += 1; est.pops2.chat.push(['ela', 'Agente', `Anotei. Preenchi a seção ${est.pops2.secFeitas}, ${SECOES[est.pops2.secFeitas - 1]}. Confere ali do lado.${est.pops2.secFeitas < 11 ? ' Próxima: ' + SECOES[est.pops2.secFeitas] + '.' : ' Agora todas as seções estão prontas: pode aprovar a versão final.'}`]); }
    else est.pops2.chat.push(['ela', 'Agente', 'Ajustei o texto. Quando estiver de acordo, aprove a versão final no alto.']);
    N.desenhar();
  };
  N.acoes['pop-aprovar-final'] = (a) => {
    const p = popDe(a.dataset.id);
    if (est.pops2.secFeitas < 11) { N.aviso(`Ainda faltam ${11 - est.pops2.secFeitas} seções. O agente está perguntando por elas na conversa.`); return; }
    N.modal('Aprovar a versão final?', `<p style="margin:0">A versão ${p.v} de ${esc(p.nome)} segue para a Revisão técnica de ${esc(p.rev)}. Você não edita mais, a não ser que ela devolva.</p>`, `<button type="button" class="btn" data-acao="pop-aprovar-final-ok" data-id="${p.id}">Aprovar e enviar à Revisão</button>`);
  };
  N.acoes['pop-aprovar-final-ok'] = (a) => { const p = popDe(a.dataset.id); p.est = 'revisao'; p.com = p.rev; p.papel = 'Revisor'; N.fecharModal(); location.hash = '#pops'; N.aviso(`Versão final aprovada. ${p.rev.split(' ')[0]} recebeu o POP para a Revisão técnica.`); };

  // Leitura da Versão, com Revisão técnica ou Validação final
  T.popversao = { trilha: 'POPs', menu: 'pops', mapa: ['POPs', 'Versão de um POP (revisar ou validar)'], render(id) {
    const p = popDe(id || 'pop1') || popDe('pop1');
    const cont = CONTEUDO[p.id] || CONTEUDO.pop1;
    const papel = comigo(p) && (p.papel === 'Revisora' || p.papel === 'Validadora') ? p.papel : null;
    const [cls, txt] = ESTADOS[p.est];
    const devol = p.id === 'pop1' ? [['Fernanda Lima, na Validação da versão 2', 'há 5 meses', 'Faltava dizer o que fazer com paciente sem acompanhante e que não fala.']] : [];
    return `<div class="pagina">
      <a class="voltar" href="#pops">${I.voltar}Voltar aos POPs</a>
      <div class="cartao bloco" style="padding:20px 24px">
        <div class="barra-topo"><div><span class="sub num">${p.cod} · ${esc(p.setor)}</span><h1 class="pagina-titulo" style="margin-top:4px">${esc(p.nome)} <span class="pill escuro" style="font-size:13px;vertical-align:middle">v${p.v}</span> ${pill(cls, txt)}</h1></div>
          <button class="btn contorno grande" data-acao="toast" data-msg="No sistema, baixa o PDF desta versão.">${IC.baixar}PDF desta versão</button></div>
        ${etapasPop(p)}
      </div>
      <div class="duas" style="margin-top:14px">
        <section class="cartao bloco larga"><div class="cab"><h2>Conteúdo da versão ${p.v}</h2><button class="btn contorno" data-acao="toast" data-msg="No sistema, mostra esta versão lado a lado com a versão ${p.v - 1 || 1}, com as mudanças marcadas.">Comparar com a versão ${Math.max(1, p.v - 1)}</button></div>
          <div class="pop-vivo">${SECOES.map((s, k) => `<div class="pop-sec feita"><h3><span class="nsec">${k + 1}</span>${s}</h3>${cont[k]}</div>`).join('')}</div></section>
        <aside class="estreita">
          ${papel ? `<section class="cartao bloco faz-agora"><p class="rot-mini" style="margin:0">${papel === 'Revisora' ? 'Revisão técnica' : 'Validação final'}</p>
            <h2 class="titulo-bloco" style="margin-top:6px">Com você até ${fmt(dia(p.prazo))}</h2>
            <p class="sub" style="margin:6px 0 14px">${papel === 'Revisora' ? `Leia o conteúdo técnico. Se aprovar, segue para a Validação de ${esc(p.val)}.` : 'Se aprovar, a versão vai para a assinatura na ClickSign e depois para a Biblioteca.'}</p>
            <div style="display:flex;flex-direction:column;gap:8px"><button class="btn grande" data-acao="pop-aprovar" data-id="${p.id}">Aprovar ${papel === 'Revisora' ? 'a revisão' : 'e enviar para assinatura'}</button><button class="btn contorno grande" data-acao="pop-devolver" data-id="${p.id}">Devolver com comentários</button></div></section>`
          : `<section class="cartao bloco"><p class="rot-mini" style="margin:0">Com quem está</p><p style="margin:6px 0 0;font-size:16px;color:var(--titulo);font-weight:700">${esc(p.com || 'Publicada')}</p><p class="sub" style="margin:4px 0 0">${p.papel || 'Versão vigente'}</p></section>`}
          <section class="cartao bloco"><h2 class="titulo-bloco" style="font-size:15px">Papéis</h2><dl class="pares" style="margin-top:10px"><dt>Elaborador</dt><dd>${esc(p.el)}</dd><dt>Revisor</dt><dd>${esc(p.rev)}</dd><dt>Validador</dt><dd>${esc(p.val)}</dd></dl></section>
          <section class="cartao bloco"><h2 class="titulo-bloco" style="font-size:15px">Devoluções</h2>${devol.length ? devol.map(([q, d, t]) => `<div class="devol" style="margin-top:10px"><b>${q}</b><span class="sub">${d}</span><p style="margin:6px 0 0">${t}</p></div>`).join('') : '<p class="vazio" style="margin:8px 0 0">Nenhuma devolução nesta versão.</p>'}</section>
        </aside>
      </div>
      <p class="demo">Dados de demonstração.</p></div>`;
  } };
  N.acoes['pop-devolver'] = (a) => {
    const p = popDe(a.dataset.id);
    N.modal('Devolver com comentários', `<p class="sub" style="margin:0 0 12px">${esc(p.nome)} volta para ${esc(p.el)}, com o seu comentário em destaque no POP vivo.</p><div class="campo"><label for="dv-mot">O que precisa mudar</label><textarea id="dv-mot" required placeholder="Diga a seção e o que falta"></textarea></div>`,
      `<button type="submit" class="btn">Devolver</button>`, 'form-pop-devolver');
    N.envios['form-pop-devolver'] = () => { p.est = 'elaboracao'; p.com = p.el; p.papel = 'Elaborador'; N.fecharModal(); location.hash = '#pops'; N.aviso(`POP devolvido para ${p.el.split(' ')[0]}, com o seu comentário.`); };
  };
  N.acoes['pop-aprovar'] = (a) => {
    const p = popDe(a.dataset.id); const rev = p.est === 'revisao';
    N.modal(rev ? 'Aprovar a revisão?' : 'Aprovar e enviar para assinatura?', `<p style="margin:0">${rev ? `A versão ${p.v} segue para a Validação final de ${esc(p.val)}.` : `A versão ${p.v} vai para a ClickSign. Quando todos assinarem, entra na Biblioteca e substitui a versão ${p.v - 1}.`}</p>`,
      `<button type="button" class="btn" data-acao="pop-aprovar-ok" data-id="${p.id}">Aprovar</button>`);
  };
  N.acoes['pop-aprovar-ok'] = (a) => {
    const p = popDe(a.dataset.id); const rev = p.est === 'revisao';
    if (rev) { p.est = 'validacao'; p.com = p.val; p.papel = 'Validador'; } else { p.est = 'assinatura'; p.com = 'ClickSign'; p.papel = 'Assinaturas'; }
    if (p.item) N.est.feitos[p.item] = true;
    N.fecharModal(); location.hash = '#pops'; N.aviso(rev ? 'Revisão aprovada. O POP seguiu para a Validação.' : 'Validação aprovada. O POP seguiu para a assinatura.');
  };

  // ================================================================== OUVIDORIA
  const OUV_EST = { triagem: 'Aguardando validação', area: 'Com a área', resposta: 'Resposta recebida', encerrado: 'Encerrado', arquivado: 'Arquivado' };
  const CASOS = [
    { n: '0479', tit: 'Cobrança de exame que o convênio cobre', tipo: 'Reclamação', grav: 'Moderada', setor: 'Faturamento', resp: null, est: 'triagem', off: 0, canal: 'Formulário do site', novo: true, quem: 'Marta Ribeiro', ponto: null, dias: 1,
      relato: 'Fui cobrada pela ultrassonografia do meu filho, mas o convênio cobre o exame. Liguei duas vezes e me mandaram aguardar. Quero o estorno.' },
    { n: '0484', tit: 'Barulho na maternidade durante a madrugada', tipo: 'Reclamação', grav: 'Leve', setor: 'Hotelaria', resp: null, est: 'triagem', off: 2, canal: 'QR do quarto 214', novo: true, quem: 'Anônimo', ponto: 'Maternidade, 2º andar', dias: 0,
      relato: 'A equipe de limpeza passa com o carrinho às 3 da manhã e acorda todos os bebês do corredor.' },
    { n: '0483', tit: 'Sugestão: vagas de estacionamento para gestantes', tipo: 'Sugestão', grav: 'Leve', setor: 'Administração', resp: null, est: 'triagem', off: 4, canal: 'Presencial', novo: false, quem: 'Joana Lopes', ponto: null, dias: 2,
      relato: 'Seria bom ter vagas reservadas para gestantes perto da entrada da maternidade.' },
    { n: '0482', tit: 'Demora no atendimento da recepção da Emergência', tipo: 'Reclamação', grav: 'Moderada', setor: 'Diretoria Assistencial', resp: 'Renata Alves', est: 'area', off: 1, canal: 'Telefone', novo: false, quem: 'Antônio Faria (acompanhante)', ponto: null, dias: 4, item: 'p6',
      relato: 'Cheguei com meu pai no domingo à noite, com dor no peito. Esperamos 2 horas para a primeira avaliação. Ninguém explicou nada e a recepção dizia só para aguardar.' },
    { n: '0481', tit: 'Atendimento grosseiro no balcão da farmácia', tipo: 'Reclamação', grav: 'Grave', setor: 'Farmácia', resp: 'Rodrigo Sales', est: 'area', off: -4, canal: 'E-mail', novo: false, quem: 'Sílvia Mattos', ponto: null, dias: 11,
      relato: 'Fui buscar a medicação do meu marido e a atendente gritou comigo na frente de todos porque a receita estava sem carimbo.' },
    { n: '0475', tit: 'Falta de informação sobre a alta', tipo: 'Reclamação', grav: 'Moderada', setor: 'Enfermagem', resp: 'Carla Nogueira', est: 'area', off: -2, canal: 'QR da enfermaria 3', novo: true, quem: 'Paulo Henrique', ponto: 'Enfermaria 3', dias: 9,
      relato: 'Minha mãe recebeu alta e ninguém explicou como tomar os remédios novos. Tive que ligar para o médico particular.' },
    { n: '0477', tit: 'Elogio à equipe da UTI adulto', tipo: 'Elogio', grav: 'Leve', setor: 'Diretoria Assistencial', resp: 'Renata Alves', est: 'area', off: 9, canal: 'Formulário do site', novo: false, quem: 'Família Duarte', ponto: null, dias: 3, item: 'p11',
      relato: 'Queremos agradecer o cuidado da equipe da noite da UTI com o nosso pai. Pedimos que o elogio chegue a todos.' },
    { n: '0480', tit: 'Comida fria no almoço da enfermaria', tipo: 'Reclamação', grav: 'Leve', setor: 'Nutrição', resp: 'Juliana Prado', est: 'resposta', off: 3, canal: 'QR da enfermaria 2', novo: true, quem: 'Anônimo', ponto: 'Enfermaria 2', dias: 6,
      relato: 'O almoço chegou frio três dias seguidos.', resposta: 'Trocamos o carrinho térmico da ala B e passamos a sair com as bandejas 10 minutos depois, direto da cozinha. Conferimos a temperatura por uma semana e ficou acima de 60 graus.' },
    { n: '0478', tit: 'Demora para trocar o curativo', tipo: 'Reclamação', grav: 'Moderada', setor: 'Enfermagem', resp: 'Carla Nogueira', est: 'resposta', off: 1, canal: 'Telefone', novo: false, quem: 'Lúcia Campos', ponto: null, dias: 8,
      relato: 'O curativo do meu irmão ficou sujo por uma manhã inteira.', resposta: 'Conversamos com a equipe da manhã e ajustamos a escala para ter um técnico a mais no horário dos curativos.' },
    { n: '0470', tit: 'Barulho no corredor da maternidade à noite', tipo: 'Reclamação', grav: 'Leve', setor: 'Diretoria Assistencial', resp: 'Renata Alves', est: 'encerrado', off: -12, canal: 'QR do quarto 210', novo: false, quem: 'Anônimo', ponto: 'Maternidade, 2º andar', dias: 20,
      relato: 'Conversas altas no posto de enfermagem durante a madrugada.', resposta: 'Fizemos uma roda de conversa com as equipes da noite e colocamos um aviso de silêncio no posto.' },
    { n: '0466', tit: 'Elogio à recepção do ambulatório', tipo: 'Elogio', grav: 'Leve', setor: 'Recepção', resp: 'Juliana Prado', est: 'encerrado', off: -20, canal: 'Presencial', novo: false, quem: 'Rosa Amaral', ponto: null, dias: 25, relato: 'Atendimento muito gentil.' },
    { n: '0455', tit: 'Ar-condicionado quebrado na sala de espera', tipo: 'Reclamação', grav: 'Leve', setor: 'Manutenção', resp: 'Paulo Mendes', est: 'arquivado', off: -40, canal: 'Formulário do site', novo: false, quem: 'Anônimo', ponto: null, dias: 50, relato: 'Calor insuportável.' }
  ];
  const caso = (n) => CASOS.find((c) => c.n === n);
  const prot = (c) => `OUV-2026-${c.n}`;
  const GRAV = { Leve: 'cinza', Moderada: 'laranja', Grave: 'verm' };
  const ehOuvidor = () => N.eh('secretaria', 'admin');
  function semaforo(c) {
    if (c.est === 'encerrado' || c.est === 'arquivado') return N.estado('e-ok', 'Encerrado em ' + curto(dia(c.off + 2)));
    if (c.off < 0) return N.estado('e-venc', `Prazo estourou há ${-c.off} ${c.off === -1 ? 'dia' : 'dias'}`);
    if (c.off === 0) return N.estado('e-hoje', 'Vence hoje');
    if (c.off <= 2) return N.estado('e-hoje', `Vence em ${c.off} ${c.off === 1 ? 'dia útil' : 'dias úteis'}`);
    return N.estado('e-prox', 'No prazo, até ' + curto(dia(c.off)));
  }
  function acaoPrincipal(c) {
    if (c.est === 'triagem') return `<button class="btn" data-acao="ouv-validar" data-n="${c.n}">Validar e acionar</button>`;
    if (c.est === 'area') return `<button class="btn${c.off < 0 ? '' : ' contorno'}" data-acao="ouv-cobrar" data-n="${c.n}">Cobrar ${esc((c.resp || 'a área').split(' ')[0])}</button>`;
    if (c.est === 'resposta') return `<button class="btn" data-acao="ouv-encerrar" data-n="${c.n}">Encerrar</button>`;
    if (c.est === 'encerrado') return `<button class="btn contorno" data-acao="ouv-arquivar" data-n="${c.n}">Arquivar</button>`;
    return `<button class="btn contorno" data-acao="ouv-desarquivar" data-n="${c.n}">Desarquivar</button>`;
  }
  function cardCaso(c) {
    return `<article class="ouv-card">${c.novo ? '<span class="novo" title="Novidade desde a sua última visita"></span>' : ''}
      <div class="topo-c"><span class="prot num">${prot(c)}</span></div>
      <h3><a href="#ouvcaso-${c.n}">${esc(c.tit)}</a></h3>
      <div style="display:flex;flex-wrap:wrap;gap:6px">${pill('', c.tipo)}${pill(GRAV[c.grav], c.grav)}</div>
      <p class="meta" style="margin:0">${esc(c.setor)}${c.resp ? ' · ' + esc(c.resp) : ' · área a definir'} · ${esc(c.canal)}</p>
      ${semaforo(c)}
      <div class="pe-c">${acaoPrincipal(c)}${mais('ouvm-' + c.n, [`<a href="#ouvcaso-${c.n}">Abrir o dossiê</a>`, c.est !== 'encerrado' && c.est !== 'arquivado' ? `<button type="button" data-acao="ouv-redirecionar" data-n="${c.n}">Redirecionar para outra área</button>` : '', c.est === 'area' ? `<button type="button" data-acao="ouv-encerrar" data-n="${c.n}">Encerrar sem resposta da área</button>` : ''])}</div>
    </article>`;
  }

  const ABAS_OUV = () => N.abasModulo([
    ['#ouvidoria', 'Fila', CASOS.filter((c) => !['encerrado', 'arquivado'].includes(c.est)).length],
    ['#ouvpainel', 'Painel', CASOS.filter((c) => c.off < 0 && ['area', 'triagem'].includes(c.est)).length, true],
    ['#ouvavaliacoes', 'Avaliações', AVAL.filter((a) => a.revisar && !a.feito).length],
    ['#ouvemail', 'Triagem de e-mail', EMAILS.filter((e) => !e.decidido).length],
    ['#ouvpontos', 'Pontos de escuta', null], ['#ouvresponsaveis', 'Responsáveis', null], ['#ouvprazos', 'Prazos', null]], '#' + (location.hash.slice(1).split('-')[0] || 'ouvidoria'));
  const subOuv = (titulo, frase, corpo, acoes) => N.modulo({ sobre: 'Ouvidoria', titulo, frase, acoes }, null, ABAS_OUV(), corpo);
  const semAcesso = () => N.modulo({ sobre: 'Ouvidoria', titulo: 'Ouvidoria', frase: 'Esta área é da equipe da Ouvidoria.' }, null, '', `<section class="cartao bloco" style="margin-top:14px"><p class="vazio" style="margin:6px 0">Quando um caso da Ouvidoria chegar ao seu setor, ele aparece no seu Início com o botão Responder. <a href="#inicio">Voltar ao Início</a></p></section>`);

  // ---------- Fila
  T.ouvidoria = { trilha: 'Ouvidoria', menu: 'ouvidoria', mapa: ['Ouvidoria', 'Fila (ou Ouvidoria do setor)'], render() {
    if (N.perfil() === 'facilitadora') return filaDoSetor();
    if (!ehOuvidor()) return semAcesso();
    const ativos = CASOS.filter((c) => c.est !== 'arquivado' && (est.ouv.arquivados || c.est !== 'arquivado'));
    const estour = CASOS.filter((c) => c.off < 0 && ['area', 'triagem'].includes(c.est));
    const triagem = CASOS.filter((c) => c.est === 'triagem');
    const h2 = CASOS.filter((c) => c.off >= 0 && c.off <= 2 && ['area', 'triagem'].includes(c.est));
    const CH = [['todos', 'Todos'], ['estourado', 'Prazo estourado'], ['grave', 'Graves'], ['novos', 'Com novidade']];
    const t = est.ouv.busca.trim().toLowerCase();
    const filtra = (c) => (est.ouv.chip === 'todos' || (est.ouv.chip === 'estourado' && c.off < 0 && ['area', 'triagem'].includes(c.est)) || (est.ouv.chip === 'grave' && c.grav === 'Grave') || (est.ouv.chip === 'novos' && c.novo))
      && (!t || (prot(c) + c.tit + c.setor + (c.resp || '') + c.quem).toLowerCase().includes(t));
    const ordem = est.ouv.arquivados ? ['resposta', 'triagem', 'area', 'encerrado', 'arquivado'] : ['resposta', 'triagem', 'area', 'encerrado'];
    const TIT = { resposta: 'Aguardando o seu encerramento', triagem: 'Aguardando validação', area: 'Com a área', encerrado: 'Encerrados', arquivado: 'Arquivados' };
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas"><div class="chips" role="group" aria-label="Filtrar">${CH.map(([k, t2]) => `<button type="button" class="chip" data-acao="ouv-chip" data-v="${k}" aria-pressed="${est.ouv.chip === k}">${t2}</button>`).join('')}
        <button type="button" class="chip" data-acao="ouv-arq" aria-pressed="${est.ouv.arquivados}">Mostrar arquivados</button></div>
        <label class="busca-lista">${IC.busca}<span class="sr">Buscar caso</span><input id="ouv-busca" data-digita="ouv-busca" type="search" placeholder="Protocolo, assunto, setor ou pessoa" value="${esc(est.ouv.busca)}"></label></div>
      ${ordem.map((k) => { const cs = CASOS.filter((c) => c.est === k).filter(filtra).sort((a, b) => a.off - b.off); if (!cs.length) return '';
        return `<div class="ouv-grupo"><div class="cab"><h2>${TIT[k]} <span class="n num">${cs.length}</span></h2>${k === 'encerrado' ? `<button class="btn contorno" data-acao="ouv-arquivar-todos">Arquivar todos os encerrados</button>` : ''}</div>
          <div class="ouv-grade">${cs.map(cardCaso).join('')}</div></div>`; }).join('') || '<p class="vazio">Nenhum caso neste filtro. Limpe a busca ou troque o filtro.</p>'}
    </section>`;
    void ativos;
    return N.modulo({ sobre: 'Qualidade e segurança', titulo: 'Ouvidoria', frase: `${CASOS.filter((c) => ['triagem', 'area', 'resposta'].includes(c.est)).length} casos em andamento. ${estour.length} com o prazo estourado e ${triagem.length} esperam a sua validação.`,
      acoes: `<button class="btn claro grande" data-acao="ouv-nova">Nova manifestação</button><a class="btn vidro grande" href="#ouvemail">Triagem de e-mail</a>` },
    [['Aguardando validação', String(triagem.length).padStart(2, '0'), I.lista, '#ouvidoria'], ['Prazo estourado', String(estour.length).padStart(2, '0'), I.alerta, '#ouvpainel', estour.length > 0], ['Vencem em 2 dias úteis', String(h2.length).padStart(2, '0'), I.relogio, '#ouvpainel'], ['Respondidos no prazo em 90 dias', '91%', I.certo, '#ouvpainel']],
    ABAS_OUV(), corpo);
  } };
  N.digitar['ouv-busca'] = (v) => { est.ouv.busca = v; };
  N.acoes['ouv-chip'] = (a) => { est.ouv.chip = a.dataset.v; N.desenhar(); };
  N.acoes['ouv-arq'] = () => { est.ouv.arquivados = !est.ouv.arquivados; N.desenhar(); };

  // ---------- visão do Responsável do setor
  function filaDoSetor() {
    const meus = CASOS.filter((c) => c.resp === 'Renata Alves');
    const aResp = meus.filter((c) => c.est === 'area');
    const resps = meus.filter((c) => c.est !== 'area');
    const lista = est.ouv.resp === 'aresponder' ? aResp : resps;
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="chips" role="tablist" aria-label="Casos do setor"><button class="chip" data-acao="ouv-resp" data-v="aresponder" aria-pressed="${est.ouv.resp === 'aresponder'}">A responder (${aResp.length})</button><button class="chip" data-acao="ouv-resp" data-v="respondidos" aria-pressed="${est.ouv.resp === 'respondidos'}">Respondidos (${resps.length})</button></div>
      <div class="ouv-grade">${lista.map((c) => `<article class="ouv-card"><div class="topo-c"><span class="prot num">${prot(c)}</span>${pill(GRAV[c.grav], c.grav)}</div>
        <h3>${esc(c.tit)}</h3><div>${pill('', c.tipo)}</div>${semaforo(c)}
        <div class="pe-c">${c.est === 'area' ? `<button class="btn" data-acao="ouv-responder" data-n="${c.n}">${c.tipo === 'Elogio' ? 'Ver o elogio' : 'Responder'}</button>` : `<button class="btn contorno" data-acao="ouv-responder" data-n="${c.n}">Ver a resposta</button>`}</div></article>`).join('')}</div>
      ${lista.length ? '' : '<p class="vazio">Nada por aqui. Quando a Ouvidoria enviar um caso ao seu setor, ele aparece nesta lista e no seu Início.</p>'}
    </section>`;
    return N.modulo({ sobre: 'Qualidade e segurança', titulo: 'Ouvidoria do setor', frase: aResp.length ? `${aResp.length} ${aResp.length === 1 ? 'caso espera' : 'casos esperam'} a resposta da Diretoria Assistencial. O mais urgente vence ${N.quando(dia(Math.min(...aResp.map((c) => c.off))))}.` : 'Nenhum caso esperando a resposta do seu setor.' },
      [['A responder', String(aResp.length).padStart(2, '0'), I.lista, '#ouvidoria'], ['Prazo estourado', String(aResp.filter((c) => c.off < 0).length).padStart(2, '0'), I.alerta, '#ouvidoria', aResp.some((c) => c.off < 0)], ['Respondidos no prazo', '100%', I.certo, '#ouvidoria']], '', corpo);
  }
  N.acoes['ouv-resp'] = (a) => { est.ouv.resp = a.dataset.v; N.desenhar(); };
  N.acoes['ouv-responder'] = (a) => {
    const c = caso(a.dataset.n);
    const elogio = c.tipo === 'Elogio';
    const aberto = c.est === 'area';
    N.abrirGaveta({ sobre: `<div style="display:flex;gap:8px;align-items:center"><span class="prot num sub">${prot(c)}</span>${pill(GRAV[c.grav], c.grav)}</div>`, titulo: esc(c.tit),
      corpo: `${aberto ? semaforo(c) : ''}
        <dl class="pares"><dt>Tipo</dt><dd>${c.tipo}</dd><dt>Quem manifestou</dt><dd>${esc(c.quem)}</dd><dt>Chegou por</dt><dd>${esc(c.canal)}</dd></dl>
        <div><p class="rot-mini" style="margin:0 0 6px">Relato</p><p class="q-relato">${esc(c.relato)}</p></div>
        <div class="devol"><b>Nota da Ouvidoria</b>${elogio ? 'Repasse o elogio à equipe da noite da UTI e confirme aqui.' : 'Precisamos saber o que aconteceu e o que muda para não se repetir.'}</div>
        ${aberto && !elogio ? `<div class="campo"><label for="or-txt">O que foi feito</label><textarea id="or-txt" placeholder="O que o setor apurou e o que vai mudar"></textarea></div><label class="btn contorno" style="cursor:pointer;align-self:flex-start">${IC.anexo}Anexar arquivo<input type="file" hidden></label>
          <div class="cartao bloco" style="background:var(--suave);box-shadow:none"><b style="color:var(--titulo)">Precisa de mais prazo?</b><p class="sub" style="margin:4px 0 10px">A Ouvidoria decide e você recebe a resposta aqui.</p><button class="btn contorno" data-acao="toast" data-msg="Pedido de prorrogação enviado à Ouvidoria.">Pedir prorrogação</button></div>
          <button class="btn contorno" style="align-self:flex-start;border-color:transparent;color:var(--texto2)" data-acao="toast" data-msg="Caso devolvido à Ouvidoria como fora do seu setor.">Este caso não é do meu setor</button>` : ''}
        ${!aberto && c.resposta ? `<div><p class="rot-mini" style="margin:0 0 6px">Sua resposta</p><p class="q-relato">${esc(c.resposta)}</p></div>` : ''}`,
      pe: aberto ? (elogio ? `<button class="btn" data-acao="ouv-responder-ok" data-n="${c.n}" data-msg="Elogio recebido. A Ouvidoria foi avisada.">Elogio recebido</button>` : `<button class="btn" data-acao="ouv-responder-ok" data-n="${c.n}" data-msg="Resposta enviada à Ouvidoria.">Responder à Ouvidoria</button>`) : '' });
  };
  N.acoes['ouv-responder-ok'] = (a) => {
    const c = caso(a.dataset.n); const t = document.getElementById('or-txt');
    if (t && !t.value.trim()) { t.focus(); N.aviso('Escreva o que foi feito antes de responder.'); return; }
    c.est = 'resposta'; c.resposta = t ? t.value.trim() : 'Elogio repassado à equipe.'; if (c.item) N.est.feitos[c.item] = true;
    N.acoes['fechar-gaveta'](); N.desenhar(); N.aviso(a.dataset.msg);
  };

  // ---------- ações da fila e do dossiê
  const AREAS = [['Diretoria Assistencial', 'Renata Alves'], ['Enfermagem', 'Carla Nogueira'], ['Farmácia', 'Rodrigo Sales'], ['Suprimentos', 'Paulo Mendes'], ['CCIH', 'Fernanda Lima'], ['Hotelaria', 'Juliana Prado'], ['Nutrição', 'Juliana Prado'], ['Faturamento', 'Bruno Araújo']];
  N.acoes['ouv-validar'] = (a) => {
    const c = caso(a.dataset.n); fecharPop();
    N.modal('Validar e acionar a área', `<p class="sub" style="margin:0 0 14px">${prot(c)} · ${esc(c.tit)}</p><div style="display:flex;flex-direction:column;gap:14px">
      <div class="grade-form"><div class="campo"><label for="ov-tipo">Tipo</label><select id="ov-tipo">${['Reclamação', 'Elogio', 'Sugestão', 'Solicitação', 'Denúncia'].map((x) => `<option${x === c.tipo ? ' selected' : ''}>${x}</option>`).join('')}</select></div>
        <div class="campo"><label for="ov-grav">Gravidade</label><select id="ov-grav">${['Leve', 'Moderada', 'Grave'].map((x) => `<option${x === c.grav ? ' selected' : ''}>${x}</option>`).join('')}</select></div></div>
      <div class="campo"><label for="ov-area">Área que responde</label><select id="ov-area">${AREAS.map(([s, r]) => `<option value="${s}"${s === c.setor ? ' selected' : ''}>${s} (${r})</option>`).join('')}</select></div>
      <div class="campo"><label for="ov-nota">Nota para a área</label><textarea id="ov-nota" placeholder="O que você espera da resposta"></textarea></div>
      <label style="display:flex;gap:10px;align-items:center;font-size:14.5px"><input type="checkbox" style="width:18px;height:18px"> Também envolve a segurança do paciente (avisa o NSP)</label>
      <p class="aviso" style="margin:0">${I.info}Prazo da área calculado pela gravidade: 5 dias úteis, até ${fmt(dia(7))}.</p></div>`,
    `<button type="button" class="btn" data-acao="ouv-validar-ok" data-n="${c.n}">Validar e enviar à área</button>`);
  };
  N.acoes['ouv-validar-ok'] = (a) => {
    const c = caso(a.dataset.n); const area = document.getElementById('ov-area').value; const ar = AREAS.find(([s]) => s === area);
    c.setor = area; c.resp = ar[1]; c.est = 'area'; c.off = 7; c.novo = false; c.grav = document.getElementById('ov-grav').value; c.tipo = document.getElementById('ov-tipo').value;
    N.fecharModal(); N.desenhar(); N.aviso(`Caso validado. ${ar[1].split(' ')[0]} recebeu o link para responder até ${curto(dia(7))}.`);
  };
  N.acoes['ouv-cobrar'] = (a) => { const c = caso(a.dataset.n); N.aviso(`Cobrança enviada para ${(c.resp || 'a área').split(' ')[0]}, por e-mail e no app.${c.off < -3 ? ' Como passou de 3 dias, a chefia também foi avisada.' : ''}`); };
  N.acoes['ouv-redirecionar'] = (a) => {
    const c = caso(a.dataset.n); fecharPop();
    N.modal('Redirecionar para outra área', `<p class="sub" style="margin:0 0 14px">${prot(c)} sai de ${esc(c.setor)} e vai para a área escolhida, num ato só. O prazo recomeça.</p>
      <div class="campo"><label for="rd-area">Nova área</label><select id="rd-area">${AREAS.filter(([s]) => s !== c.setor).map(([s, r]) => `<option value="${s}">${s} (${r})</option>`).join('')}</select></div>
      <div class="campo" style="margin-top:14px"><label for="rd-mot">Motivo</label><textarea id="rd-mot" required placeholder="Por que esta área"></textarea></div>`,
    `<button type="submit" class="btn">Redirecionar</button>`, 'form-ouv-redir');
    N.envios['form-ouv-redir'] = () => { const area = document.getElementById('rd-area').value; const ar = AREAS.find(([s]) => s === area); c.setor = area; c.resp = ar[1]; c.est = 'area'; c.off = 7; N.fecharModal(); N.desenhar(); N.aviso(`Caso redirecionado para ${area}. ${ar[1].split(' ')[0]} foi avisado.`); };
  };
  N.acoes['ouv-encerrar'] = (a) => {
    const c = caso(a.dataset.n); fecharPop();
    N.modal('Encerrar o caso', `<p class="sub" style="margin:0 0 14px">${prot(c)} · ${esc(c.tit)}</p>
      ${c.resposta ? `<p class="rot-mini" style="margin:0 0 6px">Resposta da área</p><p class="q-relato" style="margin-bottom:14px">${esc(c.resposta)}</p>` : '<p class="aviso" style="margin:0 0 14px">' + I.info + 'A área ainda não respondeu. Encerrar agora fica registrado no dossiê.</p>'}
      <div class="campo"><label for="en-txt">Resposta ao manifestante</label><textarea id="en-txt" required>${c.resposta ? 'Olá. Obrigado por nos avisar. ' + esc(c.resposta) : ''}</textarea></div>
      <div class="campo" style="margin-top:14px"><label for="en-desf">Desfecho</label><select id="en-desf"><option>Procedente, com melhoria feita</option><option>Procedente, sem melhoria possível</option><option>Não procedente</option><option>Elogio repassado</option></select></div>`,
    `<button type="submit" class="btn">Encerrar e responder</button>`, 'form-ouv-enc');
    N.envios['form-ouv-enc'] = () => { c.est = 'encerrado'; c.off = -1; c.novo = false; N.fecharModal(); N.desenhar(); N.aviso(`Caso encerrado. ${c.quem === 'Anônimo' ? 'A resposta fica disponível pelo código de acompanhamento.' : 'A resposta foi enviada ao manifestante.'}`); };
  };
  N.acoes['ouv-arquivar'] = (a) => { const c = caso(a.dataset.n); c.est = 'arquivado'; fecharPop(); N.aviso(`${prot(c)} arquivado. Ele continua na busca.`); };
  N.acoes['ouv-desarquivar'] = (a) => { const c = caso(a.dataset.n); c.est = 'encerrado'; N.desenhar(); N.aviso(`${prot(c)} voltou para Encerrados.`); };
  N.acoes['ouv-arquivar-todos'] = () => {
    const n = CASOS.filter((c) => c.est === 'encerrado').length;
    N.modal('Arquivar todos os encerrados?', `<p style="margin:0">${n} casos saem da fila e continuam na busca e no Painel.</p>`, `<button type="button" class="btn" data-acao="ouv-arquivar-todos-ok">Arquivar ${n} casos</button>`);
  };
  N.acoes['ouv-arquivar-todos-ok'] = () => { CASOS.forEach((c) => { if (c.est === 'encerrado') c.est = 'arquivado'; }); N.fecharModal(); N.desenhar(); N.aviso('Encerrados arquivados.'); };
  N.acoes['ouv-nova'] = (a) => {
    const pre = a && a.dataset && a.dataset.email ? EMAILS.find((e) => e.id === a.dataset.email) : null;
    N.modal('Nova manifestação', `<div style="display:flex;flex-direction:column;gap:14px">
      <div class="grade-form"><div class="campo"><label for="nm-canal">Chegou por</label><select id="nm-canal">${['Telefone', 'Presencial', 'E-mail', 'WhatsApp', 'Carta'].map((x) => `<option${pre && x === 'E-mail' ? ' selected' : ''}>${x}</option>`).join('')}</select></div>
        <div class="campo"><label for="nm-tipo">Tipo</label><select id="nm-tipo"><option>Reclamação</option><option>Elogio</option><option>Sugestão</option><option>Solicitação</option><option>Denúncia</option></select></div></div>
      <div class="grade-form"><div class="campo"><label for="nm-quem">Quem manifestou</label><input id="nm-quem" value="${pre ? esc(pre.de) : ''}" placeholder="Nome, ou deixe vazio se for anônimo"></div>
        <div class="campo"><label for="nm-cont">Contato</label><input id="nm-cont" value="${pre ? esc(pre.email) : ''}" placeholder="Telefone ou e-mail"></div></div>
      <div class="campo"><label for="nm-tit">Assunto</label><input id="nm-tit" required value="${pre ? esc(pre.assunto) : ''}"></div>
      <div class="campo"><label for="nm-rel">Relato</label><textarea id="nm-rel" required>${pre ? esc(pre.corpo) : ''}</textarea></div></div>`,
    `<button type="submit" class="btn">Registrar manifestação</button>`, 'form-ouv-nova');
    N.envios['form-ouv-nova'] = () => {
      const n = String(485 + CASOS.filter((c) => +c.n >= 485).length).padStart(4, '0');
      CASOS.unshift({ n, tit: document.getElementById('nm-tit').value.trim(), tipo: document.getElementById('nm-tipo').value, grav: 'Leve', setor: 'A definir', resp: null, est: 'triagem', off: 2, canal: document.getElementById('nm-canal').value, novo: true, quem: document.getElementById('nm-quem').value.trim() || 'Anônimo', relato: document.getElementById('nm-rel').value.trim(), dias: 0 });
      if (pre) pre.decidido = 'Virou ' + 'OUV-2026-' + n;
      N.fecharModal(); if (location.hash !== '#ouvidoria') location.hash = '#ouvidoria'; else N.desenhar(); N.aviso(`Manifestação registrada: OUV-2026-${n}. Ela entrou em Aguardando validação.`);
    };
  };

  // ---------- Dossiê
  T.ouvcaso = { trilha: (id) => 'Ouvidoria · ' + (caso(id) ? prot(caso(id)) : 'Caso'), menu: 'ouvidoria', mapa: ['Ouvidoria', 'Dossiê de um caso'], render(id) {
    const c = caso(id) || caso('0481');
    if (!ehOuvidor()) return semAcesso();
    const ordem = ['triagem', 'area', 'resposta', 'encerrado'];
    const i = Math.min(ordem.indexOf(c.est), 3);
    const marcos = ['Recebida', 'Validada', 'Com a área', 'Resposta recebida', 'Encerrada'];
    const k = c.est === 'arquivado' ? 5 : i + 1;
    const ABAS = [['resumo', 'Resumo'], ['relato', 'Relato e anexos'], ['resposta', 'Resposta da área'], ['manifestante', 'Manifestante'], ['tempo', 'Linha do tempo']];
    let miolo = '';
    if (est.ouv.aba === 'resumo') miolo = `<dl class="ficha"><div><dt>Tipo</dt><dd>${c.tipo}</dd></div><div><dt>Gravidade</dt><dd>${c.grav}</dd></div><div><dt>Área</dt><dd>${esc(c.setor)}</dd></div><div><dt>Responsável</dt><dd>${esc(c.resp || 'A definir')}</dd></div><div><dt>Chegou por</dt><dd>${esc(c.canal)}</dd></div><div><dt>Aberto há</dt><dd class="num">${c.dias} dias</dd></div></dl>
        <h3 class="titulo-bloco" style="font-size:15px;margin-top:20px">Resumo da Ouvidoria</h3><p style="margin:8px 0 0;max-width:70ch">${esc(c.relato.split('.')[0])}. ${c.est === 'triagem' ? 'Ainda não validado.' : `Enviado a ${esc(c.setor)}${c.off < 0 ? ', que está com o prazo estourado.' : '.'}`}</p>
        <h3 class="titulo-bloco" style="font-size:15px;margin-top:20px">Classificação e sigilo</h3><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">${pill('', 'Atendimento')}${pill('', 'Comunicação')}${pill('cinza', 'Sem sigilo')}</div>`;
    if (est.ouv.aba === 'relato') miolo = `<p class="q-relato">${esc(c.relato)}</p>
        <h3 class="titulo-bloco" style="font-size:15px;margin-top:20px">Contado no formulário</h3><dl class="pares" style="margin-top:10px"><dt>Quando</dt><dd>${fmt(dia(-c.dias - 1))}, à noite</dd><dt>Onde</dt><dd>${esc(c.ponto || c.setor)}</dd><dt>Paciente</dt><dd>${c.quem === 'Anônimo' ? 'Não informado' : 'Familiar de quem manifestou'}</dd></dl>
        <h3 class="titulo-bloco" style="font-size:15px;margin-top:20px">Anexos</h3><div style="display:flex;flex-direction:column;gap:8px;margin-top:10px"><div class="q-anexo">${IC.anexo}foto-recepcao.jpg<span>240 KB</span></div><div class="q-anexo">${IC.anexo}comprovante.pdf<span>88 KB</span></div></div>`;
    if (est.ouv.aba === 'resposta') miolo = c.resposta ? `<p class="q-relato">${esc(c.resposta)}</p><p class="sub" style="margin:8px 0 0">Respondido por ${esc(c.resp)} em ${fmt(dia(-1))}.</p>
        <div class="acoes-item" style="margin-top:14px"><button class="btn contorno" data-acao="ouv-devolver" data-n="${c.n}">Devolver por insuficiência</button></div>`
      : `<p class="vazio">${esc(c.resp || 'A área')} ainda não respondeu. ${c.est === 'area' ? 'O link de resposta foi enviado em ' + fmt(dia(-c.dias + 1)) + '.' : ''}</p>
        <h3 class="titulo-bloco" style="font-size:15px;margin-top:16px">Avisos enviados</h3><ul class="linhas">${[['Link de resposta', -c.dias + 1], ['Lembrete', -2]].map(([t2, d]) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) 120px auto"><span class="t">${t2}<small>Para ${esc(c.resp || 'a área')} · e-mail</small></span><span class="num sub">${fmt(dia(d))}</span><button class="btn contorno" data-acao="toast" data-msg="Aviso reenviado.">Reenviar</button></li>`).join('')}</ul>`;
    if (est.ouv.aba === 'manifestante') miolo = `<dl class="pares"><dt>Nome</dt><dd>${esc(c.quem)}</dd><dt>Contato</dt><dd>${c.quem === 'Anônimo' ? 'Acompanha pelo código' : '(21) 9 8877-1234'}</dd><dt>Relógio</dt><dd>Correndo</dd></dl>
        <div class="acoes-item" style="margin-top:14px"><button class="btn contorno" data-acao="toast" data-msg="Relógio parado. O prazo fica congelado até a resposta do manifestante.">Parar o relógio</button><button class="btn contorno" data-acao="toast" data-msg="Tentativa de contato registrada.">Registrar tentativa de contato</button><button class="btn contorno" data-acao="toast" data-msg="Caso reaberto por reincidência.">Reabrir por reincidência</button></div>
        <h3 class="titulo-bloco" style="font-size:15px;margin-top:20px">Tentativas de contato</h3><p class="vazio" style="margin:8px 0 0">Nenhuma tentativa registrada.</p>`;
    if (est.ouv.aba === 'tempo') miolo = `<ul class="tempo">${[['Manifestação recebida', esc(c.canal), -c.dias], ['Validada pela Ouvidoria', 'Luana Freitas', -c.dias + 1], ['Enviada à área', esc(c.setor), -c.dias + 1], ['Lembrete à área', 'automático', -2]].slice(0, c.est === 'triagem' ? 1 : 4).map(([t2, q, d]) => `<li class="feito"><i aria-hidden="true"></i><b>${t2}</b><span>${q} · ${fmt(dia(d))}</span></li>`).join('')}${c.resposta ? `<li class="feito"><i aria-hidden="true"></i><b>Resposta da área</b><span>${esc(c.resp)} · ${fmt(dia(-1))}</span></li>` : ''}<li class="agora"><i aria-hidden="true"></i><b>Agora</b><span>${OUV_EST[c.est]}</span></li></ul>`;
    const faz = c.est === 'triagem' ? ['Validar e acionar a área', `<button class="btn grande" data-acao="ouv-validar" data-n="${c.n}">Validar e acionar</button>`]
      : c.est === 'area' ? [c.off < 0 ? `A área estourou o prazo há ${-c.off} dias` : 'Esperando a resposta da área', `<button class="btn grande" data-acao="ouv-cobrar" data-n="${c.n}">Cobrar ${esc((c.resp || 'a área').split(' ')[0])}</button>`]
      : c.est === 'resposta' ? ['A área respondeu. Leia e encerre.', `<button class="btn grande" data-acao="ouv-encerrar" data-n="${c.n}">Encerrar e responder</button>`]
      : ['Caso encerrado', `<button class="btn contorno grande" data-acao="ouv-arquivar" data-n="${c.n}">Arquivar</button>`];
    return `<div class="pagina">
      <a class="voltar" href="#ouvidoria">${I.voltar}Voltar à fila</a>
      <div class="cartao bloco" style="padding:20px 24px">
        <div class="barra-topo"><div><span class="sub num" style="font-weight:700">${prot(c)}</span><h1 class="pagina-titulo" style="margin-top:4px">${esc(c.tit)}</h1>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">${pill('', c.tipo)}${pill(GRAV[c.grav], c.grav)}${pill('escuro', OUV_EST[c.est])}</div></div>${c.est !== 'encerrado' && c.est !== 'arquivado' ? semaforo(c) : ''}</div>
        <ol class="etapas">${marcos.map((m, j) => `<li class="${j < k ? 'feito' : j === k ? 'agora' : ''}">${m}</li>`).join('')}</ol>
      </div>
      <div class="dossie">
        <section class="cartao bloco"><div class="abas" role="tablist" style="margin-top:0">${ABAS.map(([kk, t2]) => `<button type="button" role="tab" aria-selected="${est.ouv.aba === kk}" data-acao="ouv-aba" data-v="${kk}">${t2}</button>`).join('')}</div><div style="padding-top:16px">${miolo}</div></section>
        <aside class="lado">
          <section class="cartao bloco faz-agora"><p class="rot-mini" style="margin:0">O que fazer agora</p><h2 class="titulo-bloco" style="margin:6px 0 14px">${faz[0]}</h2>
            <div style="display:flex;flex-direction:column;gap:8px">${faz[1]}${['triagem', 'area'].includes(c.est) ? `<button class="btn contorno grande" data-acao="ouv-redirecionar" data-n="${c.n}">Redirecionar</button>` : ''}${c.est === 'area' ? `<button class="btn contorno grande" data-acao="ouv-encerrar" data-n="${c.n}">Encerrar sem resposta</button>` : ''}</div></section>
          ${c.n === '0481' ? `<section class="cartao bloco"><p class="rot-mini" style="margin:0">Prorrogação pedida</p><p style="margin:6px 0 12px">${esc(c.resp)} pede mais 5 dias úteis: a atendente está de férias.</p><div class="acoes-item"><button class="btn" data-acao="toast" data-msg="Prorrogação aprovada. Novo prazo avisado à área.">Aprovar</button><button class="btn contorno" data-acao="toast" data-msg="Prorrogação negada. O prazo continua.">Negar</button></div></section>` : ''}
          <section class="cartao bloco"><p class="rot-mini" style="margin:0">Segurança do paciente</p><p class="sub" style="margin:6px 0 12px">Se o caso envolve dano ou risco ao paciente, o Núcleo recebe só o necessário, sem o relato.</p><button class="btn contorno" data-acao="toast" data-msg="Caso enviado ao NSP. O Núcleo confirma o recebimento pelo link.">Enviar ao NSP</button></section>
          <button class="btn contorno" style="color:var(--verm);border-color:transparent;align-self:flex-start" data-acao="ouv-apagar" data-n="${c.n}">Apagar o caso</button>
        </aside>
      </div><p class="demo">Dados de demonstração.</p></div>`;
  } };
  N.acoes['ouv-aba'] = (a) => { est.ouv.aba = a.dataset.v; N.desenhar(); };
  N.acoes['ouv-devolver'] = (a) => {
    const c = caso(a.dataset.n);
    N.modal('Devolver por insuficiência', `<p class="sub" style="margin:0 0 12px">A resposta volta para ${esc(c.resp)} com o seu pedido. O prazo recomeça.</p><div class="campo"><label for="di-mot">O que faltou na resposta</label><textarea id="di-mot" required></textarea></div>`, `<button type="submit" class="btn">Devolver à área</button>`, 'form-ouv-devol');
    N.envios['form-ouv-devol'] = () => { c.est = 'area'; c.resposta = null; c.off = 5; N.fecharModal(); N.desenhar(); N.aviso('Resposta devolvida à área, com o seu pedido.'); };
  };
  N.acoes['ouv-apagar'] = (a) => {
    const c = caso(a.dataset.n);
    N.modal('Apagar o caso?', `<p style="margin:0 0 12px">Só a diretoria apaga um caso, e o motivo fica registrado. Use para duplicatas e testes.</p><div class="campo"><label for="ap-mot">Motivo</label><textarea id="ap-mot" required></textarea></div>`,
      `<button type="submit" class="btn" style="background:var(--verm);border-color:var(--verm)">Apagar</button>`, 'form-ouv-apagar');
    N.envios['form-ouv-apagar'] = () => { CASOS.splice(CASOS.indexOf(c), 1); N.fecharModal(); location.hash = '#ouvidoria'; N.aviso(`${prot(c)} apagado, com o motivo registrado.`); };
  };

  // ---------- Painel
  T.ouvpainel = { trilha: 'Ouvidoria', menu: 'ouvidoria', mapa: ['Ouvidoria', 'Painel'], render() {
    if (!ehOuvidor()) return semAcesso();
    const abertos = CASOS.filter((c) => ['triagem', 'area'].includes(c.est));
    const NUM = [['atrasados', 'Atrasados', abertos.filter((c) => c.off < 0), true], ['dois', 'Vencem em até 2 dias úteis', abertos.filter((c) => c.off >= 0 && c.off <= 2)], ['triagem', 'Aguardando validação', CASOS.filter((c) => c.est === 'triagem')]];
    const sel = NUM.find((x) => x[0] === est.ouv.painelSel);
    const criticos = CASOS.filter((c) => c.grav === 'Grave' && ['triagem', 'area', 'resposta'].includes(c.est));
    const areas = {};
    CASOS.forEach((c) => { const a2 = areas[c.setor] = areas[c.setor] || { ab: 0, atr: 0, tot: 0, np: 0 }; a2.tot++; if (['area', 'triagem'].includes(c.est)) a2.ab++; if (c.off < 0 && c.est === 'area') a2.atr++; if (['encerrado', 'arquivado', 'resposta'].includes(c.est)) a2.np++; });
    const h = new Date(); const hora = `${String(h.getHours()).padStart(2, '0')}:${String(h.getMinutes()).padStart(2, '0')}`;
    const corpo = `
      ${criticos.length ? `<section class="cartao bloco" style="margin-top:14px;border-color:var(--verm);box-shadow:inset 4px 0 0 var(--ponto-verm)"><div class="cab"><h2>Críticos</h2><span class="sub">casos graves em andamento</span></div>
        <ul class="linhas">${criticos.map((c) => `<li class="linha" style="grid-template-columns:130px minmax(0,1fr) 220px auto"><span class="num sub" style="font-weight:700">${prot(c)}</span><span class="t"><a href="#ouvcaso-${c.n}" style="color:var(--texto);font-weight:700;text-decoration:none">${esc(c.tit)}</a><small>${esc(c.setor)} · ${esc(c.resp || 'a definir')}</small></span>${semaforo(c)}${acaoPrincipal(c)}</li>`).join('')}</ul></section>` : ''}
      <section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2>Números de agora</h2><span class="sub">Atualizado às ${hora} · atualiza sozinho</span></div>
        <div class="grade g3">${NUM.map(([k, t2, l, v]) => `<button type="button" class="cartao bloco" data-acao="ouv-painel-sel" data-v="${k}" style="text-align:left;cursor:pointer;${est.ouv.painelSel === k ? 'border-color:var(--titulo);box-shadow:inset 0 0 0 1px var(--titulo)' : ''}"><span class="rot-mini">${t2}</span><span class="numero ${v && l.length ? 'verm' : ''}" style="display:block;margin-top:6px">${String(l.length).padStart(2, '0')}</span><span class="sub">${est.ouv.painelSel === k ? 'Mostrando a lista abaixo' : 'Clique para ver os casos'}</span></button>`).join('')}</div>
        ${sel ? `<ul class="linhas" style="margin-top:10px">${sel[2].map((c) => `<li class="linha" style="grid-template-columns:130px minmax(0,1fr) 220px auto"><span class="num sub" style="font-weight:700">${prot(c)}</span><span class="t"><a href="#ouvcaso-${c.n}" style="color:var(--texto);font-weight:700;text-decoration:none">${esc(c.tit)}</a><small>${esc(c.setor)}</small></span>${semaforo(c)}${acaoPrincipal(c)}</li>`).join('') || '<li class="vazio">Nenhum caso aqui agora.</li>'}</ul>` : ''}</section>
      <div class="grade g2">
        <section class="cartao bloco"><div class="cab"><h2>Atrasos das áreas</h2></div><ul class="linhas">${CASOS.filter((c) => c.est === 'area' && c.off < 0).map((c) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto auto"><span class="t">${esc(c.resp)}<small>${esc(c.setor)} · ${prot(c)}</small></span><span class="estado e-venc"><i></i>${-c.off} dias</span><button class="btn" data-acao="ouv-cobrar" data-n="${c.n}">Cobrar</button></li>`).join('')}</ul></section>
        <section class="cartao bloco"><div class="cab"><h2>Atrasos da Ouvidoria</h2></div><p class="sub" style="margin:8px 0 0">Validação dentro de 1 dia útil.</p><ul class="linhas">${CASOS.filter((c) => c.est === 'triagem' && c.dias > 1).map((c) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">${prot(c)}<small>${esc(c.tit)}</small></span><button class="btn" data-acao="ouv-validar" data-n="${c.n}">Validar</button></li>`).join('') || '<li class="vazio">Tudo validado no prazo.</li>'}</ul></section>
      </div>
      <div class="grade g2">
        <section class="cartao bloco"><h2 class="titulo-bloco">No prazo em 90 dias</h2><p class="numero verde" style="margin:10px 0 4px">91%</p><div class="prog verde"><span style="width:91%"></span></div><p class="sub" style="margin:10px 0 0">48 de 53 casos respondidos dentro do prazo. <a href="#ouvavaliacoes">${AVAL.filter((x) => x.revisar && !x.feito).length} avaliações para revisar</a>.</p></section>
        <section class="cartao bloco"><h2 class="titulo-bloco">Notas externas</h2><dl class="pares" style="margin-top:12px"><dt>Google</dt><dd><b style="color:var(--titulo)">4,3</b> <span class="estrelas">★★★★<span class="apag">★</span></span> <span class="sub">atualizado toda semana</span></dd><dt>Reclame Aqui</dt><dd><b style="color:var(--titulo)">7,8</b> <span class="sub">registrado em ${fmt(dia(-5))}</span> <button class="btn contorno" style="min-height:32px;margin-left:6px" data-acao="ouv-ra">Registrar nova nota</button></dd></dl></section>
      </div>
      <section class="cartao bloco" style="margin-top:14px"><h2 class="titulo-bloco">Por área</h2><div class="tabela-rola"><table class="tab" style="margin-top:8px"><thead><tr><th>Área</th><th>Em aberto</th><th>Atrasados</th><th>Total em 90 dias</th><th>Respondidos</th></tr></thead><tbody>
        ${Object.entries(areas).sort((a2, b) => b[1].ab - a2[1].ab).map(([s, v]) => `<tr><td>${esc(s)}</td><td class="num">${v.ab}</td><td class="num" style="${v.atr ? 'color:var(--verm);font-weight:700' : ''}">${v.atr}</td><td class="num">${v.tot}</td><td><div class="prog" style="width:140px"><span style="width:${v.np / v.tot * 100}%"></span></div></td></tr>`).join('')}</tbody></table></div></section>`;
    return subOuv('Painel da Ouvidoria', `${abertos.filter((c) => c.off < 0).length} casos atrasados agora. ${criticos.length} ${criticos.length === 1 ? 'caso grave' : 'casos graves'} em andamento.`, corpo, `<a class="btn claro grande" href="#ouvidoria">Ir para a fila</a>`);
  } };
  N.acoes['ouv-painel-sel'] = (a) => { est.ouv.painelSel = est.ouv.painelSel === a.dataset.v ? null : a.dataset.v; N.desenhar(); };
  N.acoes['ouv-ra'] = () => N.modal('Nota do Reclame Aqui', `<div class="campo"><label for="ra-n">Nota de 0 a 10</label><input id="ra-n" type="number" min="0" max="10" step="0.1" value="7.8" required></div>`, `<button type="submit" class="btn">Registrar</button>`, 'form-ouv-ra');
  N.envios['form-ouv-ra'] = () => { N.fecharModal(); N.aviso('Nota do Reclame Aqui registrada.'); };

  // ---------- Avaliações do QR
  const AVAL = [
    { id: 'a1', nota: 2, ponto: 'Emergência, recepção', txt: 'Fiquei 2 horas esperando sem ninguém explicar nada.', d: 0, revisar: true },
    { id: 'a2', nota: 5, ponto: 'UTI adulto', txt: 'Equipe maravilhosa, muito atenciosa com o meu pai.', d: -1 },
    { id: 'a3', nota: 1, ponto: 'Enfermaria 3', txt: 'Ninguém explicou a medicação da alta.', d: -1, revisar: true },
    { id: 'a4', nota: 4, ponto: 'Maternidade, 2º andar', txt: '', d: -2 },
    { id: 'a5', nota: 5, ponto: 'Ambulatório', txt: 'Rápido e organizado.', d: -3 },
    { id: 'a6', nota: 3, ponto: 'Enfermaria 2', txt: 'Comida chegou fria.', d: -4, revisar: true },
    { id: 'a7', nota: 5, ponto: 'Maternidade, 2º andar', txt: 'Parto tranquilo, obrigada!', d: -5 },
    { id: 'a8', nota: 4, ponto: 'Emergência, recepção', txt: '', d: -6 }
  ];
  T.ouvavaliacoes = { trilha: 'Ouvidoria', menu: 'ouvidoria', mapa: ['Ouvidoria', 'Avaliações do QR'], render() {
    if (!ehOuvidor()) return semAcesso();
    const F = [['todas', 'Todas'], ['comentario', 'Só com comentário'], ['revisar', `Para revisar (${AVAL.filter((a2) => a2.revisar && !a2.feito).length})`]];
    const lista = AVAL.filter((a2) => est.ouv.avFiltro === 'todas' || (est.ouv.avFiltro === 'comentario' ? a2.txt : a2.revisar && !a2.feito));
    const media = (AVAL.reduce((s, a2) => s + a2.nota, 0) / AVAL.length).toFixed(1).replace('.', ',');
    const dist = [5, 4, 3, 2, 1].map((n) => [n, AVAL.filter((a2) => a2.nota === n).length]);
    const pontos = [...new Set(AVAL.map((a2) => a2.ponto))].map((p) => [p, AVAL.filter((a2) => a2.ponto === p)]);
    const est5 = (n) => `<span class="estrelas" aria-label="${n} de 5">${'★'.repeat(n)}<span class="apag">${'★'.repeat(5 - n)}</span></span>`;
    const corpo = `<div class="ferramentas" style="margin-top:14px"><div class="chips">${[7, 30, 90].map((p) => `<button class="chip" data-acao="ouv-av-per" data-v="${p}" aria-pressed="${est.ouv.avPeriodo === p}">Últimos ${p} dias</button>`).join('')}</div></div>
      <div class="grade g4"><div class="cartao bloco"><span class="rot-mini">Avaliações</span><span class="numero" style="display:block;margin-top:6px">${AVAL.length * (est.ouv.avPeriodo / 7) | 0}</span></div><div class="cartao bloco"><span class="rot-mini">Nota média</span><span class="numero" style="display:block;margin-top:6px">${media}</span></div><div class="cartao bloco"><span class="rot-mini">Notas 4 e 5</span><span class="numero verde" style="display:block;margin-top:6px">63%</span></div><div class="cartao bloco"><span class="rot-mini">Para revisar</span><span class="numero ${AVAL.some((a2) => a2.revisar && !a2.feito) ? 'verm' : ''}" style="display:block;margin-top:6px">${AVAL.filter((a2) => a2.revisar && !a2.feito).length}</span></div></div>
      <div class="grade g2"><section class="cartao bloco"><h2 class="titulo-bloco">Por nota</h2>${dist.map(([n, q]) => `<div class="barra-h"><span>${est5(n).replace('aria-label', 'title')}</span><div class="prog ${n <= 2 ? 'verm' : n >= 4 ? 'verde' : ''}"><span style="width:${q / AVAL.length * 100}%"></span></div><span class="num sub">${q}</span></div>`).join('')}</section>
        <section class="cartao bloco"><h2 class="titulo-bloco">Por ponto de escuta</h2>${pontos.map(([p, l]) => { const m = l.reduce((s, a2) => s + a2.nota, 0) / l.length; return `<div class="barra-h" style="grid-template-columns:170px 1fr 40px"><span>${esc(p)}</span><div class="prog ${m < 3 ? 'verm' : m >= 4 ? 'verde' : ''}"><span style="width:${m / 5 * 100}%"></span></div><span class="num sub">${m.toFixed(1).replace('.', ',')}</span></div>`; }).join('')}</section></div>
      <section class="cartao bloco" style="margin-top:14px"><div class="ferramentas"><div class="chips">${F.map(([k, t2]) => `<button class="chip" data-acao="ouv-av-f" data-v="${k}" aria-pressed="${est.ouv.avFiltro === k}">${t2}</button>`).join('')}</div></div>
        <ul class="linhas">${lista.map((a2) => `<li class="linha" style="grid-template-columns:110px minmax(0,1fr) auto"><span>${est5(a2.nota)}</span><span class="t">${a2.txt ? esc(a2.txt) : '<span class="sub">Sem comentário</span>'}<small>${esc(a2.ponto)} · ${N.quando(dia(a2.d))}${a2.feito ? ' · ' + a2.feito : ''}</small></span>
          <span class="acoes-item">${a2.revisar && !a2.feito ? `<button class="btn" data-acao="ouv-av-conv" data-id="${a2.id}">Converter em manifestação</button><button class="btn contorno" data-acao="ouv-av-arq" data-id="${a2.id}">Arquivar revisão</button>` : ''}</span></li>`).join('') || '<li class="vazio">Nenhuma avaliação neste filtro.</li>'}</ul></section>`;
    return subOuv('Avaliações do QR', `Nota média ${media} nos últimos ${est.ouv.avPeriodo} dias. Notas 1 e 2 com comentário entram em Para revisar.`, corpo);
  } };
  N.acoes['ouv-av-per'] = (a) => { est.ouv.avPeriodo = +a.dataset.v; N.desenhar(); };
  N.acoes['ouv-av-f'] = (a) => { est.ouv.avFiltro = a.dataset.v; N.desenhar(); };
  N.acoes['ouv-av-conv'] = (a) => {
    const av = AVAL.find((x) => x.id === a.dataset.id);
    N.modal('Converter em manifestação?', `<p style="margin:0">A avaliação de ${av.nota} estrelas do ponto ${esc(av.ponto)} vira um caso em Aguardando validação, com o comentário como relato.</p>`, `<button type="button" class="btn" data-acao="ouv-av-conv-ok" data-id="${av.id}">Converter</button>`);
  };
  N.acoes['ouv-av-conv-ok'] = (a) => {
    const av = AVAL.find((x) => x.id === a.dataset.id); const n = String(490 + CASOS.length).padStart(4, '0');
    CASOS.unshift({ n, tit: av.txt.slice(0, 60), tipo: 'Reclamação', grav: 'Leve', setor: 'A definir', resp: null, est: 'triagem', off: 2, canal: 'QR: ' + av.ponto, novo: true, quem: 'Anônimo', relato: av.txt, dias: 0, ponto: av.ponto });
    av.feito = `virou OUV-2026-${n}`; N.fecharModal(); N.desenhar(); N.aviso(`Avaliação convertida em OUV-2026-${n}.`);
  };
  N.acoes['ouv-av-arq'] = (a) => { const av = AVAL.find((x) => x.id === a.dataset.id); av.feito = 'revisada sem caso'; N.desenhar(); N.aviso('Revisão arquivada.'); };

  // ---------- Triagem de e-mail
  const EMAILS = [
    { id: 'e1', de: 'Marcelo Duarte', email: 'marcelo.duarte@exemplo.com', assunto: 'Reclamação sobre o estacionamento', corpo: 'Bom dia. Paguei o estacionamento por 6 horas e a cancela não abriu na saída. Fiquei 40 minutos esperando alguém da segurança.', d: 0, anexos: ['ticket.jpg'] },
    { id: 'e2', de: 'Sílvia Mattos', email: 'silvia.mattos@exemplo.com', assunto: 'Re: Protocolo OUV-2026-0481', corpo: 'Olá, quero acrescentar que a mesma atendente já tinha sido grosseira com a minha vizinha no mês passado.', d: -1, anexos: [] },
    { id: 'e3', de: 'promocoes@lojaexemplo.com', email: 'promocoes@lojaexemplo.com', assunto: 'Ofertas de material hospitalar', corpo: 'Confira as nossas ofertas da semana em luvas e máscaras.', d: -1, anexos: [] },
    { id: 'e4', de: 'Família Duarte', email: 'familia.duarte@exemplo.com', assunto: 'Agradecimento', corpo: 'Escrevemos de novo para agradecer à equipe da UTI. Nosso pai teve alta ontem.', d: -2, anexos: [], decidido: 'Juntado a OUV-2026-0477' }
  ];
  T.ouvemail = { trilha: 'Ouvidoria', menu: 'ouvidoria', mapa: ['Ouvidoria', 'Triagem de e-mail'], render() {
    if (!ehOuvidor()) return semAcesso();
    const lista = EMAILS.filter((e) => (est.ouv.emailAba === 'pendentes') === !e.decidido);
    const atual = EMAILS.find((e) => e.id === est.ouv.email) || lista[0];
    const corpo = `<div class="email-duas">
      <section class="cartao bloco"><div class="chips"><button class="chip" data-acao="ouv-email-aba" data-v="pendentes" aria-pressed="${est.ouv.emailAba === 'pendentes'}">Pendentes (${EMAILS.filter((e) => !e.decidido).length})</button><button class="chip" data-acao="ouv-email-aba" data-v="decididos" aria-pressed="${est.ouv.emailAba === 'decididos'}">Decididos</button></div>
        <ul class="email-lista">${lista.map((e) => `<li><button data-acao="ouv-email" data-id="${e.id}" aria-current="${atual && e.id === atual.id}"><b>${esc(e.de)}</b>${esc(e.assunto)}<small>${N.quando(dia(e.d))}${e.decidido ? ' · ' + esc(e.decidido) : ''}</small></button></li>`).join('') || '<li class="vazio">Caixa em dia. Nenhum e-mail esperando decisão.</li>'}</ul></section>
      <section class="cartao bloco">${atual ? `<div class="cab"><div><h2>${esc(atual.assunto)}</h2><p class="sub" style="margin:4px 0 0">${esc(atual.de)} &lt;${esc(atual.email)}&gt; · ${fmt(dia(atual.d))}</p></div></div>
        <p class="q-relato" style="margin-top:14px">${esc(atual.corpo)}</p>
        ${atual.anexos.length ? `<div style="margin-top:12px">${atual.anexos.map((x) => `<div class="q-anexo">${IC.anexo}${esc(x)}<span>anexo</span></div>`).join('')}</div>` : ''}
        ${atual.decidido ? `<p class="aviso">${I.info}${esc(atual.decidido)}.</p>` : `<div class="acoes-item" style="margin-top:18px"><button class="btn grande" data-acao="ouv-nova" data-email="${atual.id}">Virar manifestação</button><button class="btn contorno grande" data-acao="ouv-juntar" data-id="${atual.id}">Juntar a um caso</button><button class="btn contorno grande" data-acao="ouv-descartar" data-id="${atual.id}">Descartar</button></div>`}` : '<p class="vazio">Escolha um e-mail na lista.</p>'}</section>
    </div>`;
    return subOuv('Triagem de e-mail', `${EMAILS.filter((e) => !e.decidido).length} e-mails da caixa da Ouvidoria esperam decisão. Cada um vira caso, junta a um caso ou é descartado.`, corpo);
  } };
  N.acoes['ouv-email'] = (a) => { est.ouv.email = a.dataset.id; N.desenhar(); };
  N.acoes['ouv-email-aba'] = (a) => { est.ouv.emailAba = a.dataset.v; est.ouv.email = null; N.desenhar(); };
  N.acoes['ouv-juntar'] = (a) => {
    const e = EMAILS.find((x) => x.id === a.dataset.id);
    N.modal('Juntar a um caso', `<p class="sub" style="margin:0 0 12px">O e-mail entra no dossiê do caso, na Linha do tempo.</p><div class="campo"><label for="jn-c">Caso</label><select id="jn-c">${CASOS.filter((c) => c.est !== 'arquivado').map((c) => `<option value="${c.n}"${e.assunto.includes(c.n) ? ' selected' : ''}>${prot(c)} · ${esc(c.tit)}</option>`).join('')}</select></div>`,
      `<button type="button" class="btn" data-acao="ouv-juntar-ok" data-id="${e.id}">Juntar</button>`);
  };
  N.acoes['ouv-juntar-ok'] = (a) => { const e = EMAILS.find((x) => x.id === a.dataset.id); const n = document.getElementById('jn-c').value; e.decidido = 'Juntado a OUV-2026-' + n; est.ouv.email = null; N.fecharModal(); N.desenhar(); N.aviso(`E-mail juntado a OUV-2026-${n}.`); };
  N.acoes['ouv-descartar'] = (a) => {
    const e = EMAILS.find((x) => x.id === a.dataset.id);
    N.modal('Descartar o e-mail?', `<p style="margin:0">"${esc(e.assunto)}" sai da triagem e fica em Decididos, como descartado.</p>`, `<button type="button" class="btn" data-acao="ouv-descartar-ok" data-id="${e.id}">Descartar</button>`);
  };
  N.acoes['ouv-descartar-ok'] = (a) => { const e = EMAILS.find((x) => x.id === a.dataset.id); e.decidido = 'Descartado'; est.ouv.email = null; N.fecharModal(); N.desenhar(); N.aviso('E-mail descartado.'); };

  // ---------- Pontos de escuta
  const PONTOS = [
    { id: 'pt1', nome: 'Emergência, recepção', setor: 'Emergência', cod: 'EMG-01', google: true, ativo: true },
    { id: 'pt2', nome: 'UTI adulto, sala de espera', setor: 'UTI', cod: 'UTI-01', google: false, ativo: true },
    { id: 'pt3', nome: 'Maternidade, 2º andar', setor: 'Maternidade', cod: 'MAT-02', google: true, ativo: true },
    { id: 'pt4', nome: 'Enfermaria 2', setor: 'Internação', cod: 'ENF-02', google: false, ativo: true },
    { id: 'pt5', nome: 'Enfermaria 3', setor: 'Internação', cod: 'ENF-03', google: false, ativo: true },
    { id: 'pt6', nome: 'Ambulatório, recepção', setor: 'Ambulatório', cod: 'AMB-01', google: true, ativo: true },
    { id: 'pt7', nome: 'Antiga recepção do bloco B', setor: 'Ambulatório', cod: 'AMB-00', google: false, ativo: false }
  ];
  function qr(cod) {
    let h = 0; for (const ch of cod) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    let cel = '';
    for (let y = 0; y < 21; y++) for (let x = 0; x < 21; x++) {
      const canto = (x < 7 && y < 7) || (x > 13 && y < 7) || (x < 7 && y > 13);
      let on;
      if (canto) { const cx = x > 13 ? x - 14 : x; const cy = y > 13 ? y - 14 : y; on = cx === 0 || cy === 0 || cx === 6 || cy === 6 || (cx >= 2 && cx <= 4 && cy >= 2 && cy <= 4); }
      else { h = (h * 1103515245 + 12345) >>> 0; on = (h >> 16) % 2 === 0; }
      if (on) cel += `<rect x="${x}" y="${y}" width="1" height="1"/>`;
    }
    return `<svg class="qr" viewBox="0 0 21 21" fill="#1E1D57" role="img" aria-label="QR do ponto ${cod}">${cel}</svg>`;
  }
  T.ouvpontos = { trilha: 'Ouvidoria', menu: 'ouvidoria', mapa: ['Ouvidoria', 'Pontos de escuta'], render() {
    if (!ehOuvidor()) return semAcesso();
    const setores = [...new Set(PONTOS.map((p) => p.setor))];
    const corpo = `<section class="cartao bloco" style="margin-top:14px;display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:space-between"><div><h2 class="titulo-bloco">Convite ao Google</h2><p class="sub" style="margin:4px 0 0">Quem dá nota 4 ou 5 no QR recebe o convite para avaliar o hospital no Google. Em teste em 3 pontos; a chave geral é da diretoria.</p></div>${pill('verde', 'Em teste')}</section>
      ${setores.map((s) => `<h2 class="titulo-bloco" style="margin-top:20px;font-size:15px">${esc(s)}</h2><div class="grade g2" style="margin-top:10px">${PONTOS.filter((p) => p.setor === s).map((p) => `<article class="cartao bloco ponto" style="${p.ativo ? '' : 'opacity:.6'}">${qr(p.cod)}
        <div style="flex:1;min-width:0"><div class="cab"><b style="color:var(--titulo);font-size:15.5px">${esc(p.nome)}</b>${mais('ptm-' + p.id, [`<button type="button" data-acao="ouv-ponto-editar" data-id="${p.id}">Editar o nome público</button>`, `<button type="button" data-acao="ouv-ponto-ativo" data-id="${p.id}">${p.ativo ? 'Aposentar o ponto' : 'Reativar o ponto'}</button>`])}</div>
          <p class="sub" style="margin:2px 0 10px">Código ${p.cod} · ${p.ativo ? (p.google ? 'convite ao Google ligado' : 'convite ao Google desligado') : 'aposentado'}</p>
          ${p.ativo ? `<div class="acoes-item"><button class="btn" data-acao="toast" data-msg="No sistema, baixa o cartaz A4 de ${esc(p.nome)}.">Cartaz A4</button><button class="btn contorno" data-acao="toast" data-msg="No sistema, baixa o cartaz A5.">A5</button><button class="btn contorno" data-acao="toast" data-msg="No sistema, baixa o QR em PNG.">PNG</button></div>` : ''}</div></article>`).join('')}</div>`).join('')}`;
    return subOuv('Pontos de escuta', `${PONTOS.filter((p) => p.ativo).length} pontos com QR no hospital. Cada cartaz leva para a avaliação do lugar onde está colado.`, corpo, `<button class="btn claro grande" data-acao="ouv-ponto-novo">Novo ponto de escuta</button>`);
  } };
  N.acoes['ouv-ponto-novo'] = () => N.modal('Novo ponto de escuta', `<div class="campo"><label for="np-nome">Nome público (aparece para o paciente)</label><input id="np-nome" required placeholder="Ex.: Centro Cirúrgico, sala de espera"></div><div class="campo" style="margin-top:14px"><label for="np-setor">Setor</label><select id="np-setor"><option>Emergência</option><option>UTI</option><option>Maternidade</option><option>Internação</option><option>Ambulatório</option><option>Centro Cirúrgico</option></select></div>`, `<button type="submit" class="btn">Criar e gerar o cartaz</button>`, 'form-ouv-ponto');
  N.envios['form-ouv-ponto'] = () => { const nome = document.getElementById('np-nome').value.trim(); const setor = document.getElementById('np-setor').value; PONTOS.push({ id: 'pt' + Date.now(), nome, setor, cod: setor.slice(0, 3).toUpperCase() + '-0' + (PONTOS.length + 1), google: false, ativo: true }); N.fecharModal(); N.desenhar(); N.aviso('Ponto criado. O cartaz A4 está pronto para baixar.'); };
  N.acoes['ouv-ponto-ativo'] = (a) => { const p = PONTOS.find((x) => x.id === a.dataset.id); p.ativo = !p.ativo; fecharPop(); N.aviso(p.ativo ? 'Ponto reativado.' : 'Ponto aposentado. O QR antigo passa a mostrar um aviso.'); };
  N.acoes['ouv-ponto-editar'] = (a) => { const p = PONTOS.find((x) => x.id === a.dataset.id); fecharPop(); N.modal('Editar o nome público', `<div class="campo"><label for="pe-nome">Nome público</label><input id="pe-nome" required value="${esc(p.nome)}"></div>`, `<button type="submit" class="btn">Salvar</button>`, 'form-ouv-pe'); N.envios['form-ouv-pe'] = () => { p.nome = document.getElementById('pe-nome').value.trim(); N.fecharModal(); N.desenhar(); N.aviso('Nome salvo. Os cartazes novos já saem com ele.'); }; };

  // ---------- Responsáveis
  const RESP = [
    { id: 'rp1', setor: 'Diretoria Assistencial', nome: 'Renata Alves', papel: 'Titular', ate: null, login: true },
    { id: 'rp2', setor: 'Enfermagem', nome: 'Carla Nogueira', papel: 'Titular', ate: null, login: true },
    { id: 'rp3', setor: 'Enfermagem', nome: 'Beatriz Souza', papel: 'Substituta', ate: 60, login: false },
    { id: 'rp4', setor: 'Farmácia', nome: 'Rodrigo Sales', papel: 'Titular', ate: null, login: true },
    { id: 'rp5', setor: 'Hotelaria', nome: 'Juliana Prado', papel: 'Titular', ate: null, login: true },
    { id: 'rp6', setor: 'Nutrição', nome: 'Juliana Prado', papel: 'Titular', ate: 30, login: true },
    { id: 'rp7', setor: 'Faturamento', nome: 'Bruno Araújo', papel: 'Substituto', ate: null, login: true },
    { id: 'rp8', setor: 'Manutenção', nome: 'Paulo Mendes', papel: 'Titular', ate: null, login: true }
  ];
  T.ouvresponsaveis = { trilha: 'Ouvidoria', menu: 'ouvidoria', mapa: ['Ouvidoria', 'Responsáveis por setor'], render() {
    if (!ehOuvidor()) return semAcesso();
    const setores = [...new Set(RESP.map((r) => r.setor))].sort();
    const semTit = setores.filter((s) => !RESP.some((r) => r.setor === s && r.papel === 'Titular'));
    const corpo = `<section class="cartao bloco" style="margin-top:14px"><div class="tabela-rola"><table class="tab"><thead><tr><th>Setor</th><th>Responsável</th><th>Papel</th><th>Vigência</th><th>Acesso</th><th></th></tr></thead><tbody>
      ${setores.map((s) => RESP.filter((r) => r.setor === s).map((r, i) => `<tr><td>${i === 0 ? `<b style="color:var(--titulo)">${esc(s)}</b>${semTit.includes(s) ? `<div>${pill('verm', 'Sem titular vigente')}</div>` : ''}` : ''}</td><td>${esc(r.nome)}</td><td>${r.papel}</td><td class="num">${r.ate ? 'até ' + fmt(dia(r.ate)) : 'Sem data de fim'}</td><td>${r.login ? pill('verde', 'Tem login') : pill('cinza', 'Sem login, responde pelo link')}</td>
        <td style="text-align:right">${mais('rpm-' + r.id, [`<button type="button" data-acao="ouv-resp-encerrar" data-id="${r.id}">Encerrar a vigência hoje</button>`, `<button type="button" data-acao="ouv-resp-remover" data-id="${r.id}" style="color:var(--verm)">Remover do cadastro</button>`])}</td></tr>`).join('')).join('')}
      </tbody></table></div></section>`;
    return subOuv('Responsáveis por setor', `Quem responde a Ouvidoria em cada setor. ${semTit.length ? semTit.length + ' setor está sem titular vigente.' : 'Todos os setores têm titular.'}`, corpo, `<button class="btn claro grande" data-acao="ouv-resp-novo">Cadastrar responsável</button>`);
  } };
  N.acoes['ouv-resp-novo'] = () => N.modal('Cadastrar responsável', `<div style="display:flex;flex-direction:column;gap:14px"><div class="grade-form"><div class="campo"><label for="nr-setor">Setor</label><select id="nr-setor"><option>Emergência</option><option>UTI</option><option>Faturamento</option><option>Enfermagem</option></select></div><div class="campo"><label for="nr-papel">Papel</label><select id="nr-papel"><option>Titular</option><option>Substituto</option></select></div></div>
    <div class="grade-form"><div class="campo"><label for="nr-nome">Nome</label><input id="nr-nome" required></div><div class="campo"><label for="nr-email">E-mail</label><input id="nr-email" type="email" required></div></div>
    <div class="campo"><label for="nr-ate">Vigente até (opcional)</label><input id="nr-ate" type="date"></div></div>`, `<button type="submit" class="btn">Cadastrar</button>`, 'form-ouv-resp');
  N.envios['form-ouv-resp'] = () => { RESP.push({ id: 'rp' + Date.now(), setor: document.getElementById('nr-setor').value, nome: document.getElementById('nr-nome').value.trim(), papel: document.getElementById('nr-papel').value, ate: null, login: false }); N.fecharModal(); N.desenhar(); N.aviso('Responsável cadastrado. Os próximos casos do setor vão para ele.'); };
  N.acoes['ouv-resp-encerrar'] = (a) => { const r = RESP.find((x) => x.id === a.dataset.id); fecharPop(); N.modal('Encerrar a vigência hoje?', `<p style="margin:0">${esc(r.nome)} deixa de receber os casos de ${esc(r.setor)} a partir de amanhã. Os casos abertos continuam com ele.</p>`, `<button type="button" class="btn" data-acao="ouv-resp-encerrar-ok" data-id="${r.id}">Encerrar hoje</button>`); };
  N.acoes['ouv-resp-encerrar-ok'] = (a) => { const r = RESP.find((x) => x.id === a.dataset.id); RESP.splice(RESP.indexOf(r), 1); N.fecharModal(); N.desenhar(); N.aviso('Vigência encerrada.'); };
  N.acoes['ouv-resp-remover'] = (a) => { const r = RESP.find((x) => x.id === a.dataset.id); fecharPop(); N.modal('Remover do cadastro?', `<p style="margin:0">${esc(r.nome)} sai do cadastro de ${esc(r.setor)}. Use só para cadastro errado; para quem saiu do cargo, encerre a vigência.</p>`, `<button type="button" class="btn" style="background:var(--verm);border-color:var(--verm)" data-acao="ouv-resp-encerrar-ok" data-id="${r.id}">Remover</button>`); };

  // ---------- Prazos
  const PRAZOS = { 'Validação pela Ouvidoria': [2, 1, 1, 'dias úteis'], 'Resposta da área': [10, 7, 3, 'dias úteis'], 'Resposta ao manifestante': [15, 10, 5, 'dias úteis'], 'Ciência do NSP': [72, 48, 24, 'horas'] };
  const FERIADOS = [['2026-12-25', 'Natal', 'Nacional'], ['2027-01-01', 'Confraternização Universal', 'Nacional'], ['2027-01-20', 'São Sebastião', 'Municipal (Rio de Janeiro)'], ['2027-04-23', 'São Jorge', 'Estadual (RJ)']];
  T.ouvprazos = { trilha: 'Ouvidoria', menu: 'ouvidoria', mapa: ['Ouvidoria', 'Tabela de prazos'], render() {
    if (!ehOuvidor()) return semAcesso();
    const pode = N.perfil() === 'admin';
    const corpo = `<section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2>Prazo por marco e gravidade</h2>${est.ouv.prazosMudou ? pill('laranja', 'Mudanças não salvas') : pill('verde', 'Tudo salvo')}</div>
      ${pode ? '' : `<p class="aviso">${I.info}Só a diretoria executiva muda os prazos. Você vê a tabela que vale hoje.</p>`}
      <div class="tabela-rola"><table class="grade-prazos" style="margin-top:10px"><thead><tr><th>Marco</th><th>Leve</th><th>Moderada</th><th>Grave</th><th>Unidade</th></tr></thead><tbody>
      ${Object.entries(PRAZOS).map(([m, v]) => `<tr><td>${m}</td>${[0, 1, 2].map((i) => `<td><input type="number" min="1" value="${v[i]}" aria-label="${m}, ${['Leve', 'Moderada', 'Grave'][i]}" data-prazo="1"${pode ? '' : ' disabled'}></td>`).join('')}<td class="sub">${v[3]}</td></tr>`).join('')}</tbody></table></div>
      ${pode ? `<div class="acoes-item" style="margin-top:14px;justify-content:flex-end"><button class="btn contorno" data-acao="ouv-prazos-desfazer"${est.ouv.prazosMudou ? '' : ' disabled'}>Desfazer</button><button class="btn" data-acao="ouv-prazos-salvar"${est.ouv.prazosMudou ? '' : ' disabled'}>Salvar os prazos</button></div>` : ''}
      <p class="sub" style="margin:10px 0 0">A mudança vale para os casos que entrarem depois de salvar. Os abertos mantêm o prazo que tinham.</p></section>
      <section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2>Feriados</h2>${pode ? `<button class="btn contorno" data-acao="ouv-feriado-novo">${IC.mais}Adicionar feriado</button>` : ''}</div><p class="sub" style="margin:6px 0 0">Dia útil não conta feriado. Entre aqui os municipais e estaduais.</p>
        <ul class="linhas">${FERIADOS.map(([d, n, ab], i) => `<li class="linha" style="grid-template-columns:120px minmax(0,1fr) auto"><span class="num">${fmt(N.deIso(d))}</span><span class="t">${esc(n)}<small>${esc(ab)}</small></span>${pode ? `<button class="btn contorno" data-acao="ouv-feriado-rem" data-i="${i}">Remover</button>` : '<span></span>'}</li>`).join('')}</ul></section>`;
    return subOuv('Tabela de prazos', 'Os prazos de cada marco do caso, por gravidade, e os feriados que não contam como dia útil.', corpo);
  }, depois() { document.querySelectorAll('[data-prazo]').forEach((el) => el.addEventListener('input', () => { el.classList.add('mudou'); if (!est.ouv.prazosMudou) { est.ouv.prazosMudou = true; document.querySelectorAll('[data-acao="ouv-prazos-salvar"],[data-acao="ouv-prazos-desfazer"]').forEach((b) => { b.disabled = false; }); const p2 = document.querySelector('.cab .pill.verde'); if (p2) { p2.className = 'pill laranja'; p2.textContent = 'Mudanças não salvas'; } } })); } };
  N.acoes['ouv-prazos-salvar'] = () => {
    document.querySelectorAll('[data-prazo]').forEach((el) => { const tr = el.closest('tr'); const m = tr.firstElementChild.textContent; const i = [...tr.querySelectorAll('input')].indexOf(el); PRAZOS[m][i] = +el.value; });
    est.ouv.prazosMudou = false; N.desenhar(); N.aviso('Prazos salvos. Valem para os casos novos.');
  };
  N.acoes['ouv-prazos-desfazer'] = () => { est.ouv.prazosMudou = false; N.desenhar(); N.aviso('Mudanças desfeitas.'); };
  N.acoes['ouv-feriado-novo'] = () => N.modal('Adicionar feriado', `<div class="grade-form"><div class="campo"><label for="fe-d">Data</label><input id="fe-d" type="date" required></div><div class="campo"><label for="fe-ab">Abrangência</label><select id="fe-ab"><option>Municipal (Rio de Janeiro)</option><option>Estadual (RJ)</option><option>Nacional</option></select></div></div><div class="campo" style="margin-top:14px"><label for="fe-n">Nome</label><input id="fe-n" required></div>`, `<button type="submit" class="btn">Adicionar</button>`, 'form-ouv-fer');
  N.envios['form-ouv-fer'] = () => { FERIADOS.push([document.getElementById('fe-d').value, document.getElementById('fe-n').value.trim(), document.getElementById('fe-ab').value]); FERIADOS.sort((a, b) => a[0].localeCompare(b[0])); N.fecharModal(); N.desenhar(); N.aviso('Feriado adicionado.'); };
  N.acoes['ouv-feriado-rem'] = (a) => { const f = FERIADOS[+a.dataset.i]; N.modal('Remover o feriado?', `<p style="margin:0">${esc(f[1])}, ${fmt(N.deIso(f[0]))}, volta a contar como dia útil.</p>`, `<button type="button" class="btn" data-acao="ouv-feriado-rem-ok" data-i="${a.dataset.i}">Remover</button>`); };
  N.acoes['ouv-feriado-rem-ok'] = (a) => { FERIADOS.splice(+a.dataset.i, 1); N.fecharModal(); N.desenhar(); N.aviso('Feriado removido.'); };

  void HOJE;
})();
