/* Telas públicas (sem login): entrar no app, Ouvidoria, Notificar pelo QR, acompanhamento,
   Tela do responsável, aceite da Ata, Pendências por link e o Canal de Conduta.
   Todas usam a casca pública: o herói do Início em página aberta, com o cartão subindo sobre a foto. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I, IC, est, dia, fmt, curto, deIso, reunioes } = N;
  const T = N.telas;

  N.css(`
    .pub-pe{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-top:24px;padding-top:18px;border-top:1px solid var(--linha)}
    .pub-pe .btn.grande{min-width:150px}
    .pub-passo{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--texto2);margin:0 0 4px}
    .pub-tit{margin:0 0 6px;font-size:22px;line-height:1.25;color:var(--titulo)}
    .pub-texto{margin:0 0 18px;color:var(--texto2);max-width:60ch}
    .pub-campos{display:flex;flex-direction:column;gap:16px}
    .pub-check{display:flex;align-items:flex-start;gap:12px;font-size:15px;line-height:1.4;cursor:pointer;padding:12px 14px;border:1px solid var(--campo-borda);border-radius:10px;background:var(--cartao)}
    .pub-check input{width:22px;height:22px;flex:none;margin:0;accent-color:var(--btn-fundo)}
    .pub-codigo{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:16px 18px;border-radius:10px;background:var(--suave)}
    .pub-codigo b{display:block;font-size:26px;letter-spacing:.04em;color:var(--titulo);font-variant-numeric:tabular-nums}
    .pub-codigo span{font-size:12.5px;color:var(--texto2);text-transform:uppercase;letter-spacing:.06em}
    .pub-canais{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-top:14px}
    .pub-canais a{display:flex;align-items:center;gap:10px;min-height:52px;padding:10px 14px;border-radius:8px;background:var(--cartao);border:1px solid var(--borda);color:var(--titulo);text-decoration:none;font-size:14px;line-height:1.25}
    .pub-canais a:hover{background:var(--suave);color:var(--titulo)}
    .pub-ok{width:56px;height:56px;border-radius:999px;background:#E3F4EA;color:var(--verde);display:flex;align-items:center;justify-content:center;margin-bottom:14px}
    .pub-regressivo{display:flex;align-items:center;gap:14px;padding:14px 16px;border-radius:10px;background:#FEF3E2;color:var(--laranja)}
    .pub-regressivo b{display:block;font-size:22px;color:var(--laranja);font-variant-numeric:tabular-nums}
    .pub-regressivo span{font-size:13px}
    .pub-bloco{padding:14px 16px;border-radius:10px;background:var(--suave);font-size:15px;line-height:1.5}
    .pub-bloco h3{margin:0 0 6px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--texto2)}
    .pub-bloco p{margin:0}
    .pub-portas{max-width:760px;margin:0 auto;padding:0 16px 20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
    .pub-portas button,.pub-portas a{display:flex;flex-direction:column;gap:2px;text-align:left;padding:12px 14px;border:1px solid var(--borda);border-radius:10px;background:var(--cartao);color:var(--texto);font-size:13.5px;text-decoration:none;cursor:pointer}
    .pub-portas button:hover,.pub-portas a:hover{background:var(--suave);color:var(--texto)}
    .pub-portas b{color:var(--titulo);font-size:14.5px}
    .pub-anexo{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    .pub-anexo .sub{font-size:13px}
    .pub-nota{display:flex;gap:8px;flex-wrap:wrap}
    .pub-nota button{width:48px;height:48px;border-radius:10px;border:1px solid var(--campo-borda);background:var(--cartao);color:var(--titulo);font-size:17px;font-weight:700;cursor:pointer}
    .pub-nota button[aria-pressed="true"]{background:var(--btn-fundo);color:var(--btn-texto);border-color:var(--btn-fundo)}
    .pub-pend{padding:16px 0;border-bottom:1px solid var(--linha)}
    .pub-pend:last-child{border-bottom:0}
    .pub-pend h3{margin:8px 0 2px;font-size:16.5px;color:var(--titulo)}
    .pub-erro{margin:6px 0 0;color:var(--verm);font-size:13.5px}
    .pub-topo-link{display:flex;justify-content:flex-end;margin:-8px 0 10px}
    .pub-topo-link a{display:inline-flex;align-items:center;min-height:36px;padding:0 12px;border-radius:999px;font-size:13.5px;font-weight:700;text-decoration:none;color:#fff;background:var(--reuniao-fundo);border:1px solid var(--reuniao-borda)}
    .pub-topo-link a:hover{color:#fff;background:rgba(255,255,255,.22)}
    @media (max-width:640px){
      .pub-pe{flex-direction:column-reverse;align-items:stretch}
      .pub-pe .btn{width:100%}
      .publica .miolo .cartao.bloco{padding:18px 16px !important}
      .pub-tit{font-size:20px}
    }
  `);

  // ------------------------------------------------------------------ estado e peças
  est.pub = {
    login: { modo: 'entrar', d: {}, ver: false },
    man: { passo: 0, d: {}, fim: null },
    notif: { passo: 0, d: {}, fim: null },
    acomp: { d: { prot: '', jeito: 'anonimo' }, res: null, erro: '' },
    resp: { d: {}, fim: null },
    aceite: { li: false, fim: false },
    mp: { feitas: {}, conta: false },
    cond: { passo: 0, d: {}, fim: null, nota: 0 },
    cacomp: { d: {}, res: false, msgs: [] }
  };
  const P = est.pub;

  // Lê todo campo marcado com data-campo para o objeto da tela, antes de redesenhar.
  function colher(obj) {
    document.querySelectorAll('#conteudo [data-campo]').forEach((el) => { obj[el.dataset.campo] = el.type === 'checkbox' ? el.checked : el.value; });
  }
  const val = (obj, k) => esc(obj[k] || '');

  function casca({ titulo, frase, corpo, depois }) {
    return `<div class="publica">
      <section class="faixa"><img class="foto" src="${N.fotoDaTela()}" alt=""><div class="veu-foto" aria-hidden="true"></div>
        <div class="dentro"><img class="logo" src="assets/logo-hsm-branco.png" alt="Hospital São Matheus" width="112" height="58"><h1>${titulo}</h1>${frase ? `<p>${frase}</p>` : ''}</div></section>
      <div class="miolo">${corpo}</div>
      ${depois || ''}
      <footer class="rodape-pub">Hospital São Matheus, Bangu, Rio de Janeiro · Dados de demonstração</footer>
    </div>`;
  }
  // Cartão de um passo: progresso, título, campos e o pé com Voltar e o botão principal.
  function passo({ n, total, rotulo, titulo, texto, campos, voltar, principal }) {
    return `<section class="cartao bloco entra" style="padding:26px">
      ${total ? `<div class="passos-pub" aria-hidden="true">${Array.from({ length: total }, (_, i) => `<span class="${i < n ? 'on' : ''}"></span>`).join('')}</div><p class="pub-passo">Passo ${n} de ${total} · ${rotulo}</p>` : ''}
      <h2 class="pub-tit">${titulo}</h2>${texto ? `<p class="pub-texto">${texto}</p>` : ''}
      <div class="pub-campos">${campos}</div>
      <div class="pub-pe">${voltar || '<span></span>'}${principal || ''}</div>
    </section>`;
  }
  const opcoes = (grupo, rotulo, lista, atual) => `<div role="group" aria-label="${rotulo}"><p class="pub-passo" style="margin-bottom:8px">${rotulo}</p><div class="opcoes-grandes">${lista.map(([v, t, s]) => `<button type="button" class="opcao-g" data-acao="pub-opcao" data-grupo-pub="${grupo}" data-v="${v}" aria-pressed="${atual === v}"><b>${t}</b>${s ? `<small>${s}</small>` : ''}</button>`).join('')}</div></div>`;
  const campo = (k, rot, obj, extra = {}) => {
    const id = 'pub-' + k;
    const base = `id="${id}" data-campo="${k}"${extra.obrig ? ' required aria-required="true"' : ''}${extra.ph ? ` placeholder="${extra.ph}"` : ''}`;
    let entrada;
    if (extra.area) entrada = `<textarea ${base}>${val(obj, k)}</textarea>`;
    else if (extra.opcoes) entrada = `<select ${base}><option value="">Escolha</option>${extra.opcoes.map((o) => `<option${obj[k] === o ? ' selected' : ''}>${o}</option>`).join('')}</select>`;
    else entrada = `<input ${base} type="${extra.tipo || 'text'}" value="${val(obj, k)}"${extra.auto ? ` autocomplete="${extra.auto}"` : ''}>`;
    return `<div class="campo"><label for="${id}">${rot}${extra.obrig ? '' : ' <span style="text-transform:none;letter-spacing:0;font-weight:400">(opcional)</span>'}</label>${entrada}${extra.ajuda ? `<span class="sub">${extra.ajuda}</span>` : ''}</div>`;
  };
  const anexo = (k, txt) => `<div class="pub-anexo"><label class="btn contorno" style="cursor:pointer">${IC.anexo}${txt || 'Anexar foto ou documento'}<input type="file" hidden multiple data-anexo="${k}"></label><span class="sub" id="anexo-${k}">Até 3 arquivos. Opcional.</span></div>`;
  const check = (k, txt, obj) => `<label class="pub-check"><input type="checkbox" data-campo="${k}"${obj[k] ? ' checked' : ''}><span>${txt}</span></label>`;
  const btn = (acao, txt, cls, extra) => `<button type="button" class="btn grande ${cls || ''}" data-acao="${acao}"${extra || ''}>${txt}</button>`;
  const okIcone = `<div class="pub-ok" aria-hidden="true"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M5 12l5 5 9-10"/></svg></div>`;
  function codigo(rot, valor) {
    return `<div class="pub-codigo"><div><span>${rot}</span><b>${valor}</b></div><button type="button" class="btn contorno" data-acao="pub-copiar" data-v="${valor}">${IC.copiar}Copiar</button></div>`;
  }
  function falta(obj, chaves) {
    const vazio = chaves.find((k) => !obj[k]);
    if (!vazio) return false;
    N.aviso('Falta preencher um campo obrigatório.');
    setTimeout(() => { const el = document.getElementById('pub-' + vazio); if (el) el.focus(); }, 40);
    return true;
  }

  // Ações comuns
  const estadoDe = { man: P.man, notif: P.notif, cond: P.cond, resp: P.resp, login: P.login, acomp: P.acomp, cacomp: P.cacomp };
  N.acoes['pub-opcao'] = (a) => {
    const [tela, k] = a.dataset.grupoPub.split('.');
    const alvo = estadoDe[tela];
    colher(alvo.d);
    alvo.d[k] = a.dataset.v;
    N.desenhar();
  };
  N.acoes['pub-copiar'] = (a) => {
    try { navigator.clipboard.writeText(a.dataset.v); } catch (e) { /* sem área de transferência */ }
    N.aviso(`Copiado: ${a.dataset.v}`);
  };
  document.addEventListener('change', (ev) => {
    const k = ev.target.dataset && ev.target.dataset.anexo;
    if (!k) return;
    const nomes = [...ev.target.files].slice(0, 3).map((f) => f.name);
    const s = document.getElementById('anexo-' + k);
    if (s) s.textContent = nomes.length ? nomes.join(', ') : 'Até 3 arquivos. Opcional.';
  });
  function irPasso(tela, delta) {
    const s = estadoDe[tela];
    colher(s.d);
    s.passo = Math.max(0, s.passo + delta);
    N.desenhar(true);
  }

  // ================================================================== Entrar no app
  T.login = { publica: true, trilha: 'Entrar', menu: 'inicio', mapa: ['Telas públicas', 'Entrar no app'], render() {
    const s = P.login;
    let corpo;
    if (s.modo === 'esqueci') {
      corpo = `<form id="pub-esqueci">${passo({ titulo: 'Criar uma senha nova', texto: 'Informe o e-mail que você usa no hospital. Mandamos um link para criar a senha nova.',
        campos: campo('email', 'E-mail', s.d, { obrig: true, tipo: 'email', auto: 'email', ph: 'nome@saomatheus.com.br' }),
        voltar: btn('pub-login-modo', 'Voltar', 'contorno', ' data-v="entrar"'), principal: `<button type="submit" class="btn grande">Enviar o link</button>` })}</form>`;
    } else if (s.modo === 'enviado') {
      corpo = passo({ titulo: 'Confira o seu e-mail', texto: `Se ${val(s.d, 'email') || 'o e-mail'} estiver cadastrado, o link chega em alguns minutos. Olhe também a caixa de spam.`,
        campos: okIcone, principal: btn('pub-login-modo', 'Voltar para entrar', '', ' data-v="entrar"') });
    } else {
      corpo = `<form id="pub-login">${passo({ titulo: 'Entre no app', texto: 'Use o e-mail e a senha do hospital.',
        campos: `${campo('email', 'E-mail', s.d, { obrig: true, tipo: 'email', auto: 'username', ph: 'nome@saomatheus.com.br' })}
          <div class="campo"><label for="pub-senha">Senha</label><div style="display:flex;gap:8px"><input id="pub-senha" data-campo="senha" type="${s.ver ? 'text' : 'password'}" autocomplete="current-password" value="${val(s.d, 'senha')}" required style="flex:1;min-width:0">
            <button type="button" class="btn contorno" data-acao="pub-ver-senha" aria-pressed="${s.ver}" aria-label="${s.ver ? 'Esconder a senha' : 'Mostrar a senha'}" style="min-height:44px">${IC.olho}${s.ver ? 'Esconder' : 'Mostrar'}</button></div></div>`,
        voltar: `<a href="#" data-acao="pub-login-modo" data-v="esqueci" style="font-weight:700;font-size:14.5px;text-decoration:none">Esqueci minha senha</a>`,
        principal: `<button type="submit" class="btn grande">Entrar</button>` })}</form>
        <section class="cartao bloco" style="margin-top:14px"><h2 class="titulo-bloco" style="font-size:15px">Não trabalha no hospital?</h2>
          <div class="pub-canais">
            <a href="#manifestacao">${N.ic('<path d="M4 5h16v11H10l-5 4v-4H4z"/>', 20)}Falar com a Ouvidoria</a>
            <a href="#notificarpublico">${N.ic('<path d="M12 4l9 16H3zM12 10v4M12 17v.5"/>', 20)}Notificar um incidente</a>
            <a href="#acompanhar">${IC.busca}Acompanhar um protocolo</a>
            <a href="#conduta">${N.ic('<path d="M12 4v16M6 20h12M5 8h14M7 8l-3 7a3 3 0 0 0 6 0zM17 8l-3 7a3 3 0 0 0 6 0z"/>', 20)}Canal de Conduta</a>
          </div></section>`;
    }
    return casca({ titulo: 'Hospital Reuniões', frase: 'Reuniões, Pendências, POPs e a Ouvidoria do Hospital São Matheus num lugar só.', corpo });
  } };
  N.acoes['pub-ver-senha'] = () => { colher(P.login.d); P.login.ver = !P.login.ver; N.desenhar(); const c = document.getElementById('pub-senha'); if (c) c.focus(); };
  N.acoes['pub-login-modo'] = (a) => { colher(P.login.d); P.login.modo = a.dataset.v; N.desenhar(true); };
  N.envios['pub-login'] = () => {
    colher(P.login.d);
    if (falta(P.login.d, ['email', 'senha'])) return;
    P.login.d.senha = '';
    location.hash = '#inicio';
    N.aviso('Bem-vinda de volta, Renata.');
  };
  N.envios['pub-esqueci'] = () => { colher(P.login.d); if (falta(P.login.d, ['email'])) return; P.login.modo = 'enviado'; N.desenhar(true); };

  // ================================================================== Ouvidoria: manifestação guiada
  T.manifestacao = { publica: true, trilha: 'Ouvidoria', menu: 'inicio', mapa: ['Telas públicas', 'Manifestação à Ouvidoria'], render() {
    const s = P.man; const d = s.d;
    const total = 5;
    const voltar = btn('pub-man-passo', 'Voltar', 'contorno', ' data-v="-1"');
    const seguir = (t) => btn('pub-man-seguir', t || 'Continuar');
    let corpo;
    if (s.fim) {
      const anon = d.ident === 'anonimo';
      corpo = passo({ titulo: 'Recebemos a sua manifestação', texto: anon ? 'Guarde o protocolo e o código. Sem eles não dá para acompanhar, porque não sabemos quem você é.' : `Vamos responder pelo contato que você deixou (${val(d, 'contatoPref') || 'telefone ou e-mail'}).`,
        campos: `${okIcone}${codigo('Protocolo', 'OUV-2026-0519')}${anon ? codigo('Código de acompanhamento', 'K7P-42Q') : ''}
          <p class="pub-bloco" style="margin:0">A Ouvidoria lê a manifestação, encaminha para a área responsável e acompanha a resposta. Você pode consultar o andamento a qualquer momento.</p>`,
        voltar: btn('pub-man-nova', 'Fazer outra manifestação', 'contorno'),
        principal: `<a class="btn grande" href="#acompanhar" data-acao="pub-ir-acomp" data-prot="OUV-2026-0519">Acompanhar o caso</a>` });
    } else if (s.passo === 0) {
      corpo = passo({ titulo: 'Fale com a Ouvidoria', texto: 'Reclamação, elogio, sugestão ou pedido sobre o atendimento no hospital. Leva uns 3 minutos.',
        campos: `<ul style="margin:0;padding-left:20px;display:flex;flex-direction:column;gap:6px;font-size:15px"><li>Você pode se identificar ou fazer anônimo.</li><li>No fim, recebe um protocolo para acompanhar.</li><li>A Ouvidoria responde depois de ouvir a área envolvida.</li></ul>`,
        voltar: `<a href="#acompanhar" style="font-weight:700;font-size:14.5px;text-decoration:none">Já fiz uma: acompanhar</a>`, principal: btn('pub-man-passo', 'Começar', '', ' data-v="1"') });
    } else if (s.passo === 1) {
      corpo = passo({ n: 1, total, rotulo: 'Identificação', titulo: 'Como você quer falar com a gente?', texto: 'Com identificação, a Ouvidoria pode te ligar para entender melhor e te dar a resposta.',
        campos: `${opcoes('man.ident', 'Escolha uma opção', [['ident', 'Com identificação', 'Recebo a resposta pelo meu contato'], ['anonimo', 'Anônimo', 'Acompanho só pelo código']], d.ident)}
          <div class="pub-bloco"><h3>Trabalha no hospital?</h3><p>Para relatar a conduta de um colega ou da liderança, use o <a href="#conduta">Canal de Conduta</a>. Ele é sigiloso e vai direto ao Comitê.</p></div>`,
        voltar: btn('pub-man-passo', 'Voltar', 'contorno', ' data-v="-1"'), principal: seguir() });
    } else if (s.passo === 2) {
      corpo = passo({ n: 2, total, rotulo: 'Sobre o quê', titulo: 'O que você quer registrar?',
        campos: `${opcoes('man.tipo', 'Tipo', [['reclamacao', 'Reclamação', 'Algo não saiu como deveria'], ['elogio', 'Elogio', 'Reconhecer alguém ou uma equipe'], ['sugestao', 'Sugestão', 'Uma ideia para melhorar'], ['solicitacao', 'Pedido', 'Informação ou documento']], d.tipo)}
          ${campo('area', 'Sobre qual área', d, { obrig: true, opcoes: ['Emergência', 'Internação', 'Centro Cirúrgico', 'Exames e imagem', 'Recepção e cadastro', 'Faturamento e convênios', 'Hotelaria e limpeza', 'Alimentação', 'Outra'] })}`,
        voltar, principal: seguir() });
    } else if (s.passo === 3) {
      corpo = passo({ n: 3, total, rotulo: 'Quando e onde', titulo: 'Quando e onde aconteceu?', texto: 'Se não lembrar a hora exata, coloque a aproximada.',
        campos: `<div class="grade-form">${campo('data', 'Dia', d, { obrig: true, tipo: 'date' })}${campo('hora', 'Hora aproximada', d, { tipo: 'time' })}</div>
          ${campo('local', 'Onde', d, { ph: 'Ex.: recepção da Emergência' })}
          ${campo('paciente', 'Nome do paciente', d, { ajuda: 'Ajuda a encontrar o atendimento. Fica só com a Ouvidoria.' })}`,
        voltar, principal: seguir() });
    } else if (s.passo === 4) {
      corpo = passo({ n: 4, total, rotulo: 'O que aconteceu', titulo: 'Conte o que aconteceu', texto: 'Escreva do seu jeito. Quanto mais detalhe, mais fácil apurar.',
        campos: `${campo('relato', 'O que aconteceu', d, { obrig: true, area: true, ph: 'O que você viu, quem estava, o que foi dito' })}
          ${campo('espera', 'O que você espera que aconteça', d, { area: true })}${anexo('man')}`,
        voltar, principal: seguir() });
    } else {
      const anon = d.ident === 'anonimo';
      corpo = passo({ n: 5, total, rotulo: 'Contato', titulo: anon ? 'Antes de enviar' : 'Como falamos com você?',
        texto: anon ? 'No anônimo, a Ouvidoria não consegue te procurar. Você recebe um código para acompanhar a resposta.' : 'Usamos o contato só para este caso.',
        campos: anon ? `<div class="pub-bloco"><h3>Resumo</h3><p>${esc(({ reclamacao: 'Reclamação', elogio: 'Elogio', sugestao: 'Sugestão', solicitacao: 'Pedido' })[d.tipo] || 'Manifestação')} sobre ${val(d, 'area') || 'o atendimento'}${d.data ? ', em ' + fmt(deIso(d.data)) : ''}.</p></div>`
          : `${campo('nome', 'Seu nome', d, { obrig: true, auto: 'name' })}<div class="grade-form">${campo('tel', 'Telefone ou WhatsApp', d, { tipo: 'tel', auto: 'tel' })}${campo('emailc', 'E-mail', d, { tipo: 'email', auto: 'email' })}</div>
             ${campo('contatoPref', 'Prefere que a gente fale por', d, { opcoes: ['Telefone', 'WhatsApp', 'E-mail'] })}`,
        voltar, principal: btn('pub-man-enviar', 'Enviar manifestação') });
    }
    return casca({ titulo: 'Ouvidoria', frase: 'A sua opinião chega a quem pode resolver.', corpo });
  } };
  N.acoes['pub-man-passo'] = (a) => irPasso('man', Number(a.dataset.v));
  N.acoes['pub-man-seguir'] = () => {
    const s = P.man; colher(s.d);
    if (s.passo === 1 && !s.d.ident) { N.aviso('Escolha com identificação ou anônimo.'); return; }
    if (s.passo === 2 && (!s.d.tipo || falta(s.d, ['area']))) { if (!s.d.tipo) N.aviso('Escolha o tipo.'); return; }
    if (s.passo === 3 && falta(s.d, ['data'])) return;
    if (s.passo === 4 && falta(s.d, ['relato'])) return;
    s.passo += 1; N.desenhar(true);
  };
  N.acoes['pub-man-enviar'] = () => { const s = P.man; colher(s.d); if (s.d.ident !== 'anonimo' && falta(s.d, ['nome'])) return; s.fim = true; N.desenhar(true); };
  N.acoes['pub-man-nova'] = () => { P.man.passo = 0; P.man.d = {}; P.man.fim = null; N.desenhar(true); };
  N.acoes['pub-ir-acomp'] = (a) => { P.acomp.d.prot = a.dataset.prot; P.acomp.res = null; P.acomp.erro = ''; location.hash = '#acompanhar'; };

  // ================================================================== Acompanhar (Ouvidoria e NSP numa página só)
  const tipoProt = (p) => /^OUV/i.test(p) ? 'ouv' : /^NSP/i.test(p) ? 'nsp' : null;
  T.acompanhar = { publica: true, trilha: 'Acompanhar', menu: 'inicio', mapa: ['Telas públicas', 'Acompanhar um protocolo'], render() {
    const s = P.acomp; const d = s.d;
    const tipo = tipoProt(d.prot || '');
    let corpo;
    if (s.res) {
      const ouv = s.res === 'ouv';
      const etapas = ouv ? ['Recebida', 'Com a área', 'Respondida', 'Encerrada'] : ['Recebida', 'Em análise', 'Em ação', 'Concluída'];
      const agora = 1;
      corpo = `<section class="cartao bloco entra" style="padding:26px">
        <p class="pub-passo">${ouv ? 'Ouvidoria' : 'Notificação ao Núcleo de Segurança do Paciente'}</p>
        <h2 class="pub-tit">${esc(d.prot.toUpperCase())}</h2>
        <ol class="etapas" style="margin:16px 0 22px;padding:0">${etapas.map((e, i) => `<li class="${i < agora ? 'feito' : i === agora ? 'agora' : ''}">${e}</li>`).join('')}</ol>
        <div class="pub-campos">
          <div class="pub-bloco"><h3>Última movimentação, ${curto(dia(-1))}</h3><p>${ouv ? 'A Ouvidoria encaminhou o seu relato à coordenação da Emergência, que tem prazo para responder. Assim que a resposta chegar, ela aparece aqui.' : 'O Núcleo leu a notificação e está conversando com o setor. Obrigado por notificar: é assim que o hospital fica mais seguro.'}</p></div>
          ${ouv ? '' : `<div class="pub-bloco" style="background:#FEF3E2"><h3 style="color:var(--laranja)">O Núcleo tem uma pergunta para você</h3><p>Você lembra se a pulseira de identificação estava no braço do paciente na hora?</p></div>
            ${campo('respNsp', 'Sua resposta', d, { area: true })}`}
        </div>
        <div class="pub-pe">${btn('pub-acomp-outro', 'Consultar outro protocolo', 'contorno')}${ouv ? btn('pub-acomp-compl', 'Enviar um complemento') : btn('pub-acomp-resp', 'Enviar a resposta')}</div>
      </section>`;
    } else {
      corpo = `<form id="pub-acomp">${passo({ titulo: 'Acompanhe o seu protocolo', texto: 'Serve para a Ouvidoria (começa com OUV) e para as notificações de incidente (começa com NSP).',
        campos: `<div class="campo"><label for="pub-prot">Protocolo</label><input id="pub-prot" data-campo="prot" data-digita="pub-prot" value="${val(d, 'prot')}" placeholder="OUV-2026-0519 ou NSP-2026-0233" autocomplete="off" required>
            <span class="sub">${tipo === 'ouv' ? 'Protocolo da Ouvidoria.' : tipo === 'nsp' ? 'Notificação ao Núcleo de Segurança do Paciente.' : 'O tipo aparece aqui quando você digitar.'}</span></div>
          ${opcoes('acomp.jeito', 'Como você registrou', [['anonimo', 'Fiz anônimo', 'Tenho o código de acompanhamento'], ['ident', 'Me identifiquei', 'Uso o e-mail ou telefone que deixei']], d.jeito)}
          ${d.jeito === 'ident' ? campo('contato', 'E-mail ou telefone usado', d, { obrig: true }) : campo('codigo', 'Código de acompanhamento', d, { obrig: true, ph: 'K7P-42Q' })}
          ${s.erro ? `<p class="pub-erro" role="alert">${s.erro}</p>` : ''}`,
        voltar: `<a href="#manifestacao" style="font-weight:700;font-size:14.5px;text-decoration:none">Não tenho protocolo</a>`,
        principal: `<button type="submit" class="btn grande">Consultar</button>` })}</form>`;
    }
    return casca({ titulo: 'Acompanhar', frase: 'Veja em que pé está a sua manifestação ou notificação.', corpo });
  } };
  N.digitar['pub-prot'] = (v) => { colher(P.acomp.d); P.acomp.d.prot = v; P.acomp.erro = ''; };
  N.envios['pub-acomp'] = () => {
    const s = P.acomp; colher(s.d);
    const tipo = tipoProt(s.d.prot || '');
    if (!tipo) { s.erro = 'Não reconhecemos esse protocolo. Ele começa com OUV ou NSP.'; N.desenhar(); document.getElementById('pub-prot').focus(); return; }
    if (falta(s.d, [s.d.jeito === 'ident' ? 'contato' : 'codigo'])) return;
    s.res = tipo; N.desenhar(true);
  };
  N.acoes['pub-acomp-outro'] = () => { P.acomp.res = null; P.acomp.d = { prot: '', jeito: 'anonimo' }; N.desenhar(true); };
  N.acoes['pub-acomp-compl'] = () => N.modal('Enviar um complemento', `<p class="sub" style="margin:0 0 12px">O complemento entra no caso e a Ouvidoria é avisada.</p><div class="campo"><label for="ac-compl">O que você quer acrescentar</label><textarea id="ac-compl"></textarea></div>`, `<button type="button" class="btn" data-acao="toast" data-msg="Complemento enviado. A Ouvidoria foi avisada.">Enviar</button>`);
  N.acoes['pub-acomp-resp'] = () => { colher(P.acomp.d); N.aviso('Resposta enviada ao Núcleo. Obrigado.'); };

  // ================================================================== Notificar incidente pelo QR
  T.notificarpublico = { publica: true, trilha: 'Notificar incidente', menu: 'inicio', mapa: ['Telas públicas', 'Notificar incidente (QR)'], render() {
    const s = P.notif; const d = s.d; const total = 4;
    const voltar = btn('pub-notif-passo', 'Voltar', 'contorno', ' data-v="-1"');
    const seguir = btn('pub-notif-seguir', 'Continuar');
    let corpo;
    if (s.fim) {
      const anon = d.ident === 'anonimo';
      corpo = passo({ titulo: 'Obrigado por notificar', texto: 'O Núcleo de Segurança do Paciente recebeu o relato. Ele usa a notificação para corrigir o processo, nunca para punir quem relatou.',
        campos: `${okIcone}${codigo('Protocolo', 'NSP-2026-0233')}${anon ? codigo('Código de acompanhamento', 'M2X-81T') : ''}
          ${d.dano === 'grave' ? '<div class="pub-bloco" style="background:#FDECEA"><h3 style="color:var(--verm)">Caso grave</h3><p>O Núcleo foi avisado agora. Se o paciente ainda precisa de cuidado, chame a equipe do setor.</p></div>' : ''}
          <p class="pub-bloco" style="margin:0">O Núcleo pode deixar perguntas para você no acompanhamento. Vale olhar daqui a alguns dias.</p>`,
        voltar: btn('pub-notif-nova', 'Notificar outro incidente', 'contorno'),
        principal: `<a class="btn grande" href="#acompanhar" data-acao="pub-ir-acomp" data-prot="NSP-2026-0233">Acompanhar a notificação</a>` });
    } else if (s.passo === 0) {
      corpo = passo({ titulo: 'Viu algo que podia machucar um paciente?', texto: 'Queda, erro de medicação, troca de paciente, equipamento com defeito, quase erro. Tudo conta.',
        campos: `<div class="pub-bloco"><h3>Notificar não é denunciar</h3><p>O Núcleo olha para o processo, não para a pessoa. Você pode notificar sem se identificar, e ninguém é punido por notificar.</p></div>
          <p class="sub" style="margin:0">Leva uns 2 minutos. Não escreva o nome completo do paciente.</p>`,
        principal: btn('pub-notif-passo', 'Começar', '', ' data-v="1"') });
    } else if (s.passo === 1) {
      corpo = passo({ n: 1, total, rotulo: 'O que aconteceu', titulo: 'O que aconteceu?',
        campos: `${campo('relato', 'Conte com as suas palavras', d, { obrig: true, area: true, ph: 'Ex.: paciente do leito 12 recebeu a dose da noite duas vezes' })}${campo('leito', 'Leito', d, { ph: 'Ex.: 3º andar, leito 12' })}${anexo('notif', 'Anexar foto')}`,
        voltar, principal: seguir });
    } else if (s.passo === 2) {
      corpo = passo({ n: 2, total, rotulo: 'Onde e quando', titulo: 'Onde e quando?',
        campos: `${campo('setor', 'Setor', d, { obrig: true, opcoes: ['Emergência', 'UTI adulto', 'Internação 2º andar', 'Internação 3º andar', 'Centro Cirúrgico', 'Maternidade', 'Farmácia', 'Imagem', 'Outro'] })}
          <div class="grade-form">${campo('data', 'Dia', d, { obrig: true, tipo: 'date' })}${campo('hora', 'Hora aproximada', d, { tipo: 'time' })}</div>`,
        voltar, principal: seguir });
    } else if (s.passo === 3) {
      corpo = passo({ n: 3, total, rotulo: 'O paciente', titulo: 'O paciente foi atingido?', texto: 'Escolha o que mais se aproxima. Na dúvida, marque "Não sei".',
        campos: opcoes('notif.dano', 'Resultado para o paciente', [['nao', 'Não chegou ao paciente', 'Foi percebido antes'], ['semdano', 'Chegou, sem dano', 'Não houve consequência'], ['dano', 'Chegou, com dano', 'Precisou de cuidado a mais'], ['grave', 'Dano grave ou morte', 'O Núcleo é avisado na hora'], ['naosei', 'Não sei', '']], d.dano),
        voltar, principal: seguir });
    } else {
      const anon = d.ident === 'anonimo';
      corpo = passo({ n: 4, total, rotulo: 'Identificação', titulo: 'Quer se identificar?', texto: 'Com identificação, o Núcleo pode te procurar para entender melhor. Você continua protegido.',
        campos: `${opcoes('notif.ident', 'Escolha uma opção', [['ident', 'Com identificação', 'O Núcleo pode falar comigo'], ['anonimo', 'Anônimo', 'Acompanho só pelo código']], d.ident)}
          ${d.ident === 'ident' ? `${campo('nome', 'Seu nome', d, { obrig: true, auto: 'name' })}<div class="grade-form">${campo('funcao', 'Função', d, { ph: 'Ex.: técnica de enfermagem' })}${campo('contato', 'Ramal ou telefone', d, { tipo: 'tel' })}</div>` : ''}
          ${anon ? '<p class="sub" style="margin:0">No anônimo, guarde o código que aparece no fim.</p>' : ''}`,
        voltar, principal: btn('pub-notif-enviar', 'Enviar a notificação') });
    }
    return casca({ titulo: 'Notificar incidente', frase: 'Núcleo de Segurança do Paciente. Toda notificação ajuda a evitar o próximo erro.', corpo });
  } };
  N.acoes['pub-notif-passo'] = (a) => irPasso('notif', Number(a.dataset.v));
  N.acoes['pub-notif-seguir'] = () => {
    const s = P.notif; colher(s.d);
    if (s.passo === 1 && falta(s.d, ['relato'])) return;
    if (s.passo === 2 && falta(s.d, ['setor', 'data'])) return;
    if (s.passo === 3 && !s.d.dano) { N.aviso('Escolha uma opção. Na dúvida, "Não sei".'); return; }
    s.passo += 1; N.desenhar(true);
  };
  N.acoes['pub-notif-enviar'] = () => { const s = P.notif; colher(s.d); if (!s.d.ident) { N.aviso('Escolha com identificação ou anônimo.'); return; } if (s.d.ident === 'ident' && falta(s.d, ['nome'])) return; s.fim = true; N.desenhar(true); };
  N.acoes['pub-notif-nova'] = () => { P.notif.passo = 0; P.notif.d = {}; P.notif.fim = null; N.desenhar(true); };

  // ================================================================== Tela do responsável do setor (link da Ouvidoria)
  const PRAZO_RESP = new Date(Date.now() + ((2 * 24 + 5) * 60 + 12) * 60000);
  function faltaPrazo() {
    const m = Math.max(0, Math.round((PRAZO_RESP - Date.now()) / 60000));
    const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mi = m % 60;
    return `${d} ${d === 1 ? 'dia' : 'dias'}, ${h} h e ${mi} min`;
  }
  setInterval(() => { const el = document.getElementById('pub-regressivo'); if (el) el.textContent = faltaPrazo(); }, 30000);
  T.responder = { publica: true, trilha: 'Responder à Ouvidoria', menu: 'inicio', mapa: ['Telas públicas', 'Tela do responsável (link)'], render(id) {
    const s = P.resp; const d = s.d;
    const prot = 'OUV-2026-' + (id && /^\d+$/.test(id) ? id.padStart(4, '0') : '0482');
    const entrar = `<div class="pub-topo-link"><a href="#login">Tem login? Entrar no app</a></div>`;
    let corpo;
    if (id === 'encerrado') {
      corpo = passo({ titulo: 'Este caso não espera mais resposta', texto: 'A Ouvidoria já encerrou ou mudou o caso de área. Se você ainda tem algo a dizer, fale com a Ouvidoria.',
        campos: '', voltar: `<a class="btn grande contorno" href="#login">Entrar no app</a>`, principal: `<a class="btn grande" href="#manifestacao">Falar com a Ouvidoria</a>` });
    } else if (s.fim === 'resposta') {
      corpo = passo({ titulo: 'Resposta enviada', texto: `A Ouvidoria recebeu o que o setor fez no caso ${prot}. Ela lê, fala com o manifestante e encerra o caso. Se precisar de mais alguma coisa, você recebe outro link.`,
        campos: `${okIcone}<div class="pub-bloco"><h3>No app você vê todos os casos do seu setor</h3><p>Com login, os casos chegam no seu Início junto com as Pendências, sem depender do e-mail.</p></div>`,
        voltar: btn('pub-resp-ver', 'Ver o que enviei', 'contorno'), principal: `<a class="btn grande" href="#login">Entrar no app</a>` });
    } else if (s.fim === 'devolvido') {
      corpo = passo({ titulo: 'Devolvido à Ouvidoria', texto: 'Obrigado por avisar. A Ouvidoria vai mandar o caso para a área certa, e este link deixa de valer.',
        campos: okIcone, principal: `<a class="btn grande" href="#login">Entrar no app</a>` });
    } else {
      corpo = `${entrar}<section class="cartao bloco entra" style="padding:26px">
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center"><span class="pill laranja">Gravidade alta</span><span class="pill">Reclamação</span></div>
        <h2 class="pub-tit" style="margin-top:12px">Demora no atendimento da recepção da Emergência</h2>
        <div class="pub-regressivo" role="timer" aria-live="off">${I.relogio}<div><span>Tempo para responder</span><b id="pub-regressivo">${faltaPrazo()}</b><span>Prazo: ${fmt(dia(2))}, às 17:00</span></div></div>
        <dl class="pares" style="margin-top:18px"><dt>Protocolo</dt><dd>${prot}</dd><dt>Setor</dt><dd>Emergência, recepção</dd><dt>Quem manifestou</dt><dd>Acompanhante, com identificação</dd><dt>Paciente</dt><dd>M. S. O., 67 anos</dd><dt>Quando</dt><dd>${fmt(dia(-3))}, por volta das 22:00</dd></dl>
        <div class="pub-campos" style="margin-top:18px">
          <div class="pub-bloco"><h3>Resumo da Ouvidoria</h3><p>Acompanhante relata espera de 2 horas para a primeira avaliação, sem nenhuma informação da recepção nesse tempo.</p></div>
          <div class="pub-bloco"><h3>Relato</h3><p>"Cheguei com a minha mãe com falta de ar no domingo à noite. Fizeram a ficha e ninguém mais falou com a gente por duas horas. Perguntei três vezes e só diziam para aguardar."</p></div>
          <div class="pub-bloco"><h3>Nota da Ouvidoria para o setor</h3><p>Precisamos saber o que aconteceu na classificação de risco naquela noite e o que muda na comunicação com quem espera.</p></div>
        </div>
        <form id="pub-resp" style="margin-top:20px">
          <div class="pub-campos">${campo('feito', 'O que foi feito', d, { obrig: true, area: true, ph: 'O que o setor apurou e o que vai mudar', ajuda: 'A Ouvidoria usa este texto para responder ao manifestante.' })}${anexo('resp')}</div>
          <div class="pub-pe"><a href="#" data-acao="pub-resp-devolver" style="font-size:14px;text-decoration:none">Este caso não é do meu setor?</a><button type="submit" class="btn grande">Responder à Ouvidoria</button></div>
        </form>
      </section>
      <section class="cartao bloco" style="margin-top:14px;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px">
        <div><h2 class="titulo-bloco" style="font-size:15.5px">Precisa de mais prazo?</h2><p class="sub" style="margin:4px 0 0">Peça antes de vencer. A Ouvidoria aprova ou nega e te avisa.</p></div>
        ${btn('pub-resp-prazo', 'Pedir mais prazo', 'contorno')}
      </section>`;
    }
    return casca({ titulo: 'Demanda da Ouvidoria', frase: 'A Ouvidoria precisa da resposta do seu setor sobre este caso.', corpo });
  } };
  N.envios['pub-resp'] = () => { colher(P.resp.d); if (falta(P.resp.d, ['feito'])) return; P.resp.fim = 'resposta'; N.desenhar(true); };
  N.acoes['pub-resp-ver'] = () => N.modal('O que você enviou', `<div class="pub-bloco"><p>${val(P.resp.d, 'feito')}</p></div>`, '');
  N.acoes['pub-resp-prazo'] = () => N.modal('Pedir mais prazo', `<div class="pub-campos"><div class="campo"><label for="rp-data">Nova data</label><input id="rp-data" type="date" value="${N.iso(dia(7))}"></div><div class="campo"><label for="rp-mot">Por que precisa de mais tempo</label><textarea id="rp-mot"></textarea></div></div>`,
    `<button type="button" class="btn" data-acao="toast" data-msg="Pedido de prazo enviado. A Ouvidoria responde por e-mail.">Enviar o pedido</button>`);
  N.acoes['pub-resp-devolver'] = () => N.modal('Este caso não é do meu setor', `<div class="pub-campos"><div class="campo"><label for="rd-mot">Por que não é do seu setor</label><textarea id="rd-mot"></textarea></div><div class="campo"><label for="rd-setor">Sabe qual é o setor certo? (opcional)</label><input id="rd-setor"></div></div>`,
    `<button type="button" class="btn" data-acao="pub-resp-devolvido">Devolver à Ouvidoria</button>`);
  N.acoes['pub-resp-devolvido'] = () => { N.fecharModal(); P.resp.fim = 'devolvido'; N.desenhar(true); };

  // ================================================================== Aceite interno da Ata
  T.aceite = { publica: true, trilha: 'Aceite da Ata', menu: 'inicio', mapa: ['Telas públicas', 'Aceite da Ata (link)'], render(id) {
    const r = reunioes.find((x) => x.id === id) || reunioes.find((x) => x.id === 'r0');
    const s = P.aceite;
    const quadro = [['Revisar a escala de enfermagem do 3º andar', 'Renata Alves', -12], ['Inventário dos medicamentos controlados', 'Rodrigo Sales', -9], ['Cotação de EPIs do Centro Cirúrgico', 'Paulo Mendes', -3], ['Checklist de passagem de plantão', 'Carla Nogueira', -1]];
    let corpo;
    if (s.fim) {
      corpo = passo({ titulo: 'Aceite registrado', texto: `Obrigado, Paulo. O seu aceite da Ata de ${curto(deIso(r.data))} ficou registrado com data e hora. As Pendências no seu nome aparecem no app e no seu e-mail.`,
        campos: okIcone, voltar: `<a class="btn grande contorno" href="#minhaspendencias-pm">Ver minhas Pendências</a>`, principal: `<a class="btn grande" href="#login">Entrar no app</a>` });
    } else {
      corpo = `<section class="cartao bloco entra" style="padding:26px">
        <p class="pub-passo">Ata para o seu aceite</p><h2 class="pub-tit">${esc(r.titulo)}</h2>
        <dl class="pares" style="margin-top:12px"><dt>Quando</dt><dd>${N.longo(deIso(r.data))}, ${r.hora}</dd><dt>Facilitadora</dt><dd>Renata Alves</dd><dt>Participantes</dt><dd>${r.participantes.map(esc).join(', ')}</dd></dl>
        <h3 class="titulo-bloco" style="margin-top:22px;font-size:16px">Pauta</h3><ol style="margin:8px 0 0;padding-left:20px">${r.pauta.map((p) => `<li>${esc(p)}</li>`).join('')}</ol>
        <h3 class="titulo-bloco" style="margin-top:22px;font-size:16px">Discussão</h3>
        <p style="margin:8px 0 0">A diretoria revisou as escalas de dezembro. O 3º andar fica com duas técnicas novas a partir do dia 5. A cotação dos EPIs do Centro Cirúrgico atrasou porque o fornecedor não entregou os aventais, e o Paulo apresenta duas opções na próxima Reunião.</p>
        <h3 class="titulo-bloco" style="margin-top:22px;font-size:16px">Quadro de atribuições</h3>
        <div class="tabela-rola"><table class="tab" style="min-width:480px"><thead><tr><th>Ação</th><th>Responsável</th><th>Prazo</th></tr></thead><tbody>${quadro.map(([a, p, o]) => `<tr><td>${esc(a)}</td><td>${p === 'Paulo Mendes' ? '<b>Você</b>' : esc(p)}</td><td class="num">${fmt(dia(o + 15))}</td></tr>`).join('')}</tbody></table></div>
        <div class="pub-campos" style="margin-top:22px">${check('li', 'Li a Ata completa e concordo com o que foi registrado.', s)}</div>
        <div class="pub-pe"><button type="button" class="btn grande contorno" data-acao="pub-aceite-duvida">Tenho uma correção</button><button type="button" class="btn grande" data-acao="pub-aceite-ok">Li e aceito</button></div>
      </section>`;
    }
    return casca({ titulo: 'Olá, Paulo', frase: 'A Facilitadora pede o seu aceite na Ata da Reunião em que você participou.', corpo });
  } };
  N.acoes['pub-aceite-ok'] = () => { const s = P.aceite; colher(s); if (!s.li) { N.aviso('Marque que leu a Ata completa.'); return; } s.fim = true; N.desenhar(true); };
  N.acoes['pub-aceite-duvida'] = () => N.modal('Pedir uma correção', `<p class="sub" style="margin:0 0 12px">A mensagem vai para a Facilitadora, Renata Alves.</p><div class="campo"><label for="ac-corr">O que precisa ser corrigido</label><textarea id="ac-corr"></textarea></div>`,
    `<button type="button" class="btn" data-acao="toast" data-msg="Pedido de correção enviado para a Renata.">Enviar</button>`);

  // ================================================================== Pendências pelo link pessoal
  const MP = [
    { id: 'm1', t: 'Cotação de EPIs do Centro Cirúrgico', reu: 'Reunião da Diretoria Assistencial', off: -3 },
    { id: 'm2', t: 'Levantar o estoque de luvas de procedimento', reu: 'Reunião da Diretoria Assistencial', off: 2 },
    { id: 'm3', t: 'Enviar o contrato de manutenção das bombas de infusão', reu: 'Qualidade e Acreditação', off: 9 }
  ];
  T.minhaspendencias = { publica: true, trilha: 'Minhas Pendências', menu: 'inicio', mapa: ['Telas públicas', 'Pendências pelo link'], render() {
    const s = P.mp;
    const abertas = MP.filter((p) => s.feitas[p.id] !== 'concluida');
    const corpo = `<section class="cartao bloco entra" style="padding:22px 26px">
        <p class="aviso" style="margin:0 0 6px">${I.info}Este link é só seu. Não encaminhe: quem abrir pode atualizar as suas Pendências.</p>
        ${abertas.length ? MP.map((p) => { const f = s.feitas[p.id];
          const [cls, txt] = f === 'concluida' ? ['e-ok', 'Concluída'] : f === 'prazo' ? ['e-hoje', 'Novo prazo pedido'] : p.off < 0 ? ['e-venc', `Atrasada há ${-p.off} dias`] : ['e-prox', `Prazo ${fmt(dia(p.off))}`];
          return `<div class="pub-pend">${N.estado(cls, txt)}<h3>${esc(p.t)}</h3><p class="sub" style="margin:0">${esc(p.reu)}</p>
            ${f === 'concluida' ? '' : `<div class="acoes-item" style="margin-top:12px"><button class="btn" data-acao="pub-mp" data-id="${p.id}" data-v="concluida">Concluir</button><button class="btn contorno" data-acao="pub-mp" data-id="${p.id}" data-v="prazo">Pedir novo prazo</button><button class="btn contorno" data-acao="pub-mp" data-id="${p.id}" data-v="nota">Só anotar</button></div>`}</div>`; }).join('')
          : `<div style="padding:18px 0">${okIcone}<h2 class="pub-tit">Você não tem Pendências em aberto</h2><p class="pub-texto">Tudo entregue. Quando uma Reunião gerar algo no seu nome, você recebe outro e-mail.</p></div>`}
      </section>
      <section class="cartao bloco" style="margin-top:14px;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px">
        <div style="flex:1 1 300px"><h2 class="titulo-bloco" style="font-size:15.5px">${s.conta ? 'Conta pedida' : 'Crie a sua conta'}</h2><p class="sub" style="margin:4px 0 0">${s.conta ? 'Você recebe um e-mail para criar a senha.' : 'Com login você vê as suas Pendências, as Reuniões e os avisos num lugar só, sem depender deste link.'}</p></div>
        ${s.conta ? `<a class="btn grande contorno" href="#login">Ir para o login</a>` : btn('pub-mp-conta', 'Criar minha conta')}
      </section>`;
    return casca({ titulo: 'Olá, Paulo', frase: `Estas são as Pendências no seu nome${abertas.length ? `: ${abertas.length} em aberto` : ''}. Atualize por aqui, sem senha.`, corpo });
  } };
  N.acoes['pub-mp'] = (a) => {
    const p = MP.find((x) => x.id === a.dataset.id); const v = a.dataset.v;
    const cfg = { concluida: ['Concluir a Pendência', 'O que foi feito', 'Concluir'], prazo: ['Pedir novo prazo', 'Por que o prazo não serve', 'Enviar o pedido'], nota: ['Anotar', 'Anotação', 'Registrar'] }[v];
    N.modal(cfg[0], `<p class="sub" style="margin:0 0 12px">${esc(p.t)}</p><div class="pub-campos">${v === 'prazo' ? `<div class="campo"><label for="mp-data">Nova data</label><input id="mp-data" type="date" value="${N.iso(dia(p.off + 15))}"></div>` : ''}<div class="campo"><label for="mp-anot">${cfg[1]}</label><textarea id="mp-anot"></textarea></div></div>`,
      `<button type="button" class="btn" data-acao="pub-mp-ok" data-id="${p.id}" data-v="${v}">${cfg[2]}</button>`, 'mp-form');
    setTimeout(() => { const t = document.getElementById('mp-anot'); if (t) t.focus(); }, 40);
  };
  N.acoes['pub-mp-ok'] = (a) => {
    const t = document.getElementById('mp-anot');
    if (!t.value.trim()) { N.aviso('A anotação é obrigatória.'); t.focus(); return; }
    if (a.dataset.v !== 'nota') P.mp.feitas[a.dataset.id] = a.dataset.v;
    N.fecharModal(); N.desenhar();
    N.aviso({ concluida: 'Pendência concluída. A Facilitadora foi avisada.', prazo: 'Pedido de novo prazo enviado à Facilitadora.', nota: 'Anotação registrada.' }[a.dataset.v]);
  };
  N.acoes['pub-mp-conta'] = () => { P.mp.conta = true; N.desenhar(); N.aviso('Pedido de conta enviado para paulo.mendes@saomatheus.com.br.'); };

  // ================================================================== Canal de Conduta
  function portas() {
    return `<nav class="pub-portas" aria-label="Outros caminhos">
      <button type="button" data-acao="pub-porta" data-v="dp"><b>Não é aqui: Departamento Pessoal</b>Salário, férias, ponto e benefícios.</button>
      <a href="#manifestacao"><b>Não é aqui: Ouvidoria</b>Atendimento a paciente e acompanhante.</a>
      <button type="button" data-acao="pub-porta" data-v="protecao"><b>Proteção contra retaliação</b>O que o hospital garante a quem relata.</button>
      <button type="button" data-acao="pub-porta" data-v="codigo"><b>Código de Conduta</b>A versão que vale hoje.</button>
    </nav>`;
  }
  N.acoes['pub-porta'] = (a) => {
    const t = { dp: ['Departamento Pessoal', 'Questões de salário, férias, ponto e benefícios são com o DP. Procure o DP no ramal do setor ou pelo e-mail interno. Se o problema é como você foi tratado, volte aqui e relate.'],
      protecao: ['Proteção contra retaliação', 'Ninguém pode ser punido, transferido ou prejudicado por relatar de boa-fé. Retaliação contra quem relata é, ela mesma, uma falta grave, e o Comitê verifica se ela aconteceu depois de cada caso.'],
      codigo: ['Código de Conduta', 'No sistema, abre o PDF da versão vigente do Código de Conduta, com a data em que passou a valer.'] }[a.dataset.v];
    N.modal(t[0], `<p style="margin:0">${t[1]}</p>`, '');
  };
  const ASSUNTOS = [['moral', 'Assédio moral', 'Humilhação, ameaça, perseguição'], ['sexual', 'Assédio sexual', 'Toque, insinuação, chantagem'], ['discriminacao', 'Discriminação', 'Raça, gênero, religião, orientação'], ['desrespeito', 'Desrespeito', 'Grito, ofensa, exposição'], ['interesse', 'Conflito de interesse', 'Favorecimento, vantagem'], ['outro', 'Outro assunto', '']];
  T.conduta = { publica: true, trilha: 'Canal de Conduta', menu: 'inicio', mapa: ['Telas públicas', 'Canal de Conduta'], render() {
    const s = P.cond; const d = s.d; const total = 5;
    const voltar = btn('pub-cond-passo', 'Voltar', 'contorno', ' data-v="-1"');
    const seguir = btn('pub-cond-seguir', 'Continuar');
    let corpo;
    if (s.fim) {
      corpo = passo({ titulo: 'Relato registrado', texto: 'O Comitê de Conduta recebeu o relato com sigilo. Guarde o protocolo e o código: são o único jeito de acompanhar e de responder às perguntas do Comitê.',
        campos: `${okIcone}${codigo('Protocolo', 'CND-2026-0012')}${codigo('Código', 'R4V-9JQ')}
          <div role="group" aria-label="Nota para o canal"><p class="pub-passo" style="margin-bottom:8px">Como foi relatar por aqui? (opcional)</p><div class="pub-nota">${[1, 2, 3, 4, 5].map((n) => `<button type="button" data-acao="pub-cond-nota" data-v="${n}" aria-pressed="${s.nota === n}" aria-label="Nota ${n}">${n}</button>`).join('')}</div></div>`,
        voltar: `<a class="btn grande contorno" href="#conduta" data-acao="pub-cond-novo">Fazer outro relato</a>`,
        principal: `<a class="btn grande" href="#condutaacompanhar">Acompanhar o relato</a>` });
    } else if (s.passo === 0) {
      corpo = passo({ titulo: 'Relate uma conduta que fere o Código', texto: 'Assédio, discriminação, desrespeito ou conflito de interesse envolvendo quem trabalha no hospital.',
        campos: `<ul style="margin:0;padding-left:20px;display:flex;flex-direction:column;gap:6px;font-size:15px"><li>O relato vai só para o Comitê de Conduta.</li><li>Você pode relatar sem se identificar.</li><li>Quem relata de boa-fé está protegido contra retaliação.</li></ul>`,
        voltar: `<a href="#condutaacompanhar" style="font-weight:700;font-size:14.5px;text-decoration:none">Já relatei: acompanhar</a>`, principal: btn('pub-cond-passo', 'Começar', '', ' data-v="1"') });
    } else if (s.passo === 1) {
      corpo = passo({ n: 1, total, rotulo: 'Antes de começar', titulo: 'Como o seu relato é tratado',
        campos: `<div class="pub-bloco"><h3>Sigilo</h3><p>Só os membros do Comitê leem o relato. Quem é citado não sabe quem relatou. Os anexos ficam guardados com criptografia.</p></div>
          <div class="pub-bloco"><h3>Privacidade</h3><p>Os dados servem só para apurar este caso, e são apagados quando o caso termina, como diz a política do Comitê.</p></div>
          ${check('ciencia', 'Li e entendi como o relato é tratado.', d)}`,
        voltar, principal: seguir });
    } else if (s.passo === 2) {
      corpo = passo({ n: 2, total, rotulo: 'Como relatar', titulo: 'Como você quer relatar?',
        campos: `${opcoes('cond.ident', 'Escolha uma opção', [['anonimo', 'Anônimo', 'Acompanho só pelo código'], ['ident', 'Com identificação', 'O Comitê pode falar comigo']], d.ident)}
          ${d.ident === 'ident' ? `${campo('nome', 'Seu nome', d, { obrig: true, auto: 'name' })}${campo('contato', 'Contato preferido', d, { ph: 'E-mail pessoal ou telefone' })}` : ''}`,
        voltar, principal: seguir });
    } else if (s.passo === 3) {
      corpo = passo({ n: 3, total, rotulo: 'Sobre o quê', titulo: 'Sobre o que é o relato?',
        campos: `${opcoes('cond.assunto', 'Assunto', ASSUNTOS, d.assunto)}
          ${opcoes('cond.direcao', 'Envolve alguém da Direção?', [['nao', 'Não', ''], ['sim', 'Sim', 'O caso segue uma rota especial, sem a Direção']], d.direcao)}`,
        voltar, principal: seguir });
    } else if (s.passo === 4) {
      corpo = passo({ n: 4, total, rotulo: 'O que aconteceu', titulo: 'Conte o que aconteceu', texto: 'Escreva o que você viu ou viveu. Datas e lugares ajudam o Comitê a apurar.',
        campos: `${campo('relato', 'O que aconteceu', d, { obrig: true, area: true })}
          <div class="grade-form">${campo('quando', 'Quando', d, { ph: 'Ex.: semana passada, no plantão da noite' })}${campo('onde', 'Onde', d, { ph: 'Ex.: posto do 3º andar' })}</div>
          ${campo('quem', 'Quem estava envolvido', d, { ph: 'Nome ou função' })}${campo('testemunhas', 'Alguém mais viu', d)}
          ${opcoes('cond.lider', 'A sua liderança sabe?', [['sim', 'Sim', ''], ['nao', 'Não', ''], ['ela', 'A liderança está envolvida', '']], d.lider)}
          ${anexo('cond', 'Anexar prova (print, áudio, foto)')}`,
        voltar, principal: seguir });
    } else {
      const assunto = (ASSUNTOS.find((x) => x[0] === d.assunto) || [0, 'Não escolhido'])[1];
      corpo = passo({ n: 5, total, rotulo: 'Revisão', titulo: 'Confira antes de enviar',
        campos: `<dl class="pares"><dt>Identificação</dt><dd>${d.ident === 'ident' ? esc(d.nome || 'Com identificação') : 'Anônimo'}</dd><dt>Assunto</dt><dd>${assunto}</dd><dt>Envolve a Direção</dt><dd>${d.direcao === 'sim' ? 'Sim, rota especial' : 'Não'}</dd><dt>Relato</dt><dd>${val(d, 'relato')}</dd></dl>
          ${d.assunto === 'outro' ? `<div class="pub-bloco" style="background:#FEF3E2"><h3 style="color:var(--laranja)">Parece ser de outro canal</h3><p>Se for sobre salário, férias ou ponto, o DP resolve mais rápido. Se for sobre atendimento a paciente, use a Ouvidoria. Se é mesmo conduta, pode registrar.</p></div>` : ''}`,
        voltar, principal: btn('pub-cond-enviar', d.assunto === 'outro' ? 'Registrar mesmo assim' : 'Registrar o relato') });
    }
    return casca({ titulo: 'Canal de Conduta', frase: 'Sigiloso, com proteção contra retaliação. Vai direto ao Comitê de Conduta.', corpo, depois: portas() });
  } };
  N.acoes['pub-cond-passo'] = (a) => irPasso('cond', Number(a.dataset.v));
  N.acoes['pub-cond-seguir'] = () => {
    const s = P.cond; colher(s.d);
    if (s.passo === 1 && !s.d.ciencia) { N.aviso('Marque que leu como o relato é tratado.'); return; }
    if (s.passo === 2 && (!s.d.ident || (s.d.ident === 'ident' && falta(s.d, ['nome'])))) { if (!s.d.ident) N.aviso('Escolha anônimo ou com identificação.'); return; }
    if (s.passo === 3 && (!s.d.assunto || !s.d.direcao)) { N.aviso('Escolha o assunto e se envolve a Direção.'); return; }
    if (s.passo === 4 && falta(s.d, ['relato'])) return;
    s.passo += 1; N.desenhar(true);
  };
  N.acoes['pub-cond-enviar'] = () => { P.cond.fim = true; N.desenhar(true); };
  N.acoes['pub-cond-nota'] = (a) => { P.cond.nota = Number(a.dataset.v); N.desenhar(); N.aviso('Obrigado pela nota.'); };
  N.acoes['pub-cond-novo'] = () => { P.cond.passo = 0; P.cond.d = {}; P.cond.fim = null; P.cond.nota = 0; N.desenhar(true); };

  T.condutaacompanhar = { publica: true, trilha: 'Acompanhar relato', menu: 'inicio', mapa: ['Telas públicas', 'Acompanhar relato de conduta'], render() {
    const s = P.cacomp; const d = s.d;
    let corpo;
    if (!s.res) {
      corpo = `<form id="pub-cacomp">${passo({ titulo: 'Acompanhe o seu relato', texto: 'Use o protocolo e o código que você recebeu ao registrar.',
        campos: `${campo('prot', 'Protocolo', d, { obrig: true, ph: 'CND-2026-0012' })}${campo('cod', 'Código', d, { obrig: true, ph: 'R4V-9JQ' })}`,
        voltar: `<a href="#conduta" style="font-weight:700;font-size:14.5px;text-decoration:none">Fazer um relato</a>`, principal: `<button type="submit" class="btn grande">Consultar</button>` })}</form>`;
    } else {
      const msgs = [['ela', 'Comitê de Conduta', curto(dia(-4)), 'Recebemos o seu relato e ele está em apuração. Pode nos dizer se o fato se repetiu depois daquela semana?'], ...s.msgs];
      corpo = `<section class="cartao bloco entra" style="padding:26px">
        <p class="pub-passo">Relato ${esc((d.prot || 'CND-2026-0012').toUpperCase())}</p><h2 class="pub-tit">Em apuração</h2>
        <ol class="etapas" style="margin:16px 0 22px;padding:0">${['Recebido', 'Em triagem', 'Em apuração', 'Concluído'].map((e, i) => `<li class="${i < 2 ? 'feito' : i === 2 ? 'agora' : ''}">${e}</li>`).join('')}</ol>
        <h3 class="titulo-bloco" style="font-size:15.5px;margin-bottom:10px">Mensagens</h3>
        <div class="conversa">${msgs.map(([q, nome, quando, txt]) => `<div class="balao ${q}"><small>${nome} · ${quando}</small>${esc(txt)}</div>`).join('')}</div>
        <div class="pub-campos" style="margin-top:18px">${campo('compl', 'Responder ou complementar', d, { area: true })}${anexo('cacomp')}</div>
        <div class="pub-pe">${btn('pub-cacomp-sair', 'Sair', 'contorno')}${btn('pub-cacomp-enviar', 'Enviar')}</div>
      </section>`;
    }
    return casca({ titulo: 'Canal de Conduta', frase: 'Acompanhe o seu relato e responda ao Comitê, com o mesmo sigilo.', corpo, depois: portas() });
  } };
  N.envios['pub-cacomp'] = () => { colher(P.cacomp.d); if (falta(P.cacomp.d, ['prot', 'cod'])) return; P.cacomp.res = true; N.desenhar(true); };
  N.acoes['pub-cacomp-enviar'] = () => {
    const s = P.cacomp; colher(s.d);
    if (!s.d.compl || !s.d.compl.trim()) { N.aviso('Escreva a mensagem antes de enviar.'); return; }
    s.msgs.push(['eu', 'Você', 'agora', s.d.compl.trim()]); s.d.compl = ''; N.desenhar(); N.aviso('Mensagem enviada ao Comitê.');
  };
  N.acoes['pub-cacomp-sair'] = () => { P.cacomp.res = false; P.cacomp.d = {}; P.cacomp.msgs = []; location.hash = '#conduta'; };
})();
