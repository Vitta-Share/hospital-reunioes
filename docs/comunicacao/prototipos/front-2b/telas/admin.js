/* Administração (só Super admin): Colaboradores e acessos, Cadastros, Dados do atendimento,
   Central de Comando e Tecnologia. Dados de demonstração. */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { esc, I, IC, dia, fmt, curto, est, HOJE } = N;
  const T = N.telas;
  est.adm = { busca: '', chip: 'ativos', cadAba: 'setores', cadVer: 'ativos', cadBusca: '', atAba: 'consultas', atBusca: '', periodo: '28', esp: 'Cardiologia', conv: 'Particular',
    tTipo: 'todos', tOrigem: 'todas', tProjeto: 'todos', tBusca: '', semana: null, atualizado: 'há 6 minutos' };
  const A = est.adm;

  N.css(`
    .gaveta.larga{width:min(780px,100%)}
    .chave{position:relative;display:inline-flex;align-items:center;width:44px;height:26px;border-radius:999px;background:var(--campo-borda);border:0;cursor:pointer;flex:none;transition:background-color .2s ease}
    .chave::after{content:"";position:absolute;left:3px;top:3px;width:20px;height:20px;border-radius:999px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:transform .2s ease}
    .chave[aria-checked="true"]{background:var(--btn-fundo)}
    .chave[aria-checked="true"]::after{transform:translateX(18px)}
    .perm{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 0;border-bottom:1px solid var(--linha)}
    .perm:last-child{border-bottom:0}
    .perm b{display:block;color:var(--titulo);font-size:15px}
    .perm small{display:block;color:var(--texto2);font-size:13px}
    .perm select{min-height:38px;padding:0 10px;border:1px solid var(--campo-borda);border-radius:8px;background:var(--campo);color:var(--texto)}
    .pop .perigo{color:var(--verm)}
    .pop hr{border:0;border-top:1px solid var(--linha);margin:4px 0}
    .frescor{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin-top:14px;padding:10px 14px;border-radius:10px;background:var(--cartao);border:1px solid var(--borda)}
    .aovivo{display:inline-flex;align-items:center;gap:8px;font-weight:700;color:var(--verde);font-size:14px}
    .aovivo i{width:9px;height:9px;border-radius:999px;background:var(--verde);box-shadow:0 0 0 4px rgba(30,123,79,.15)}
    .objetivo .prog{margin-top:10px}
    .objetivo.breve{opacity:.55}
    .partes{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:12.5px;color:var(--texto2)}
    .partes .prog{flex:1;height:6px}
    .play{width:30px;height:30px;border-radius:999px;border:0;background:var(--suave2);color:var(--titulo);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex:none}
    .play:hover{background:var(--btn-fundo);color:#fff}
    .onda{border:1px solid var(--borda);border-radius:8px;padding:10px 12px}
    .onda h4{margin:0 0 6px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--texto2)}
    .onda li{display:flex;justify-content:space-between;gap:10px;padding:5px 0;font-size:14px}
    .semana-bar{cursor:pointer}
    .semana-bar:hover rect{opacity:.8}
    .entrega{display:grid;grid-template-columns:44px minmax(0,1fr) auto auto;gap:14px;align-items:center;padding:12px 4px;border-bottom:1px solid var(--linha)}
    .entrega .tam{width:36px;height:36px;border-radius:8px;background:var(--suave2);color:var(--titulo);font-weight:700;display:flex;align-items:center;justify-content:center}
    .entrega .abre{border:0;background:none;padding:0;text-align:left;cursor:pointer;color:var(--titulo);font-weight:700;font-size:15px}
    .entrega .abre:hover{text-decoration:underline}
    .oqm{grid-column:2 / -1;background:var(--suave);border-radius:8px;padding:12px 14px;font-size:14px}
    .oqm ul{margin:6px 0 10px;padding-left:18px}
  `);

  const restrito = () => N.modulo({ sobre: 'Administração', titulo: 'Acesso restrito', frase: 'A Administração é só do Super admin. Aqui ficam o cadastro das pessoas, os acessos, as tabelas da Ana, os números do Site e o andamento da Tecnologia.' }, null, '',
    `<section class="cartao bloco" style="max-width:720px"><h2 class="titulo-bloco">Você não tem acesso a esta tela.</h2><p class="sub" style="margin:6px 0 14px">Se precisa de alguma coisa daqui (um acesso novo, um setor que falta), peça ao Super admin. No protótipo, troque o perfil para ver a tela.</p>
      <div class="acoes-item"><button class="btn" data-acao="ver-como" data-perfil="admin">Ver como Super admin</button><a class="btn contorno" href="#inicio">Voltar ao Início</a></div></section>`);
  const soAdmin = (fn) => (id) => (N.perfil() === 'admin' ? fn(id) : restrito());
  const pop = (chave, itens) => `<span class="mais-wrap" style="position:relative;display:inline-block"><button type="button" class="mais" data-pop="${chave}" aria-expanded="${est.pop === chave}" aria-label="Mais ações">${I.tres}</button>${est.pop === chave ? `<div class="pop" role="menu">${itens}</div>` : ''}</span>`;
  const fechaPop = () => { est.pop = null; };
  const chips = (acao, opcoes, atual, rot) => `<div class="chips" role="group" aria-label="${rot || 'Filtro'}">${opcoes.map(([k, t]) => `<button type="button" class="chip" data-acao="${acao}" data-v="${k}" aria-pressed="${atual === k}">${t}</button>`).join('')}</div>`;
  const busca = (id, chave, ph, valor) => `<label class="busca-lista">${IC.busca}<span class="sr">Buscar</span><input id="${id}" data-digita="${chave}" type="search" placeholder="${ph}" value="${esc(valor)}"></label>`;
  const dd = (n) => String(n).padStart(2, '0');
  const brl = (v) => 'R$ ' + v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  // ================================================================== Colaboradores e acessos
  const MODULOS = [
    ['reunioes', 'Reuniões e Pendências', ['Sem acesso', 'Colaborador', 'Facilitador', 'Secretária']],
    ['pops', 'POPs', ['Sem acesso', 'Leitor', 'Elaborador', 'Revisor', 'Validador']],
    ['ouvidoria', 'Ouvidoria', ['Sem acesso', 'Responsável do setor', 'Perfil da Ouvidoria']],
    ['nsp', 'Segurança do Paciente', ['Sem acesso', 'Membro do Núcleo', 'Presidência do Núcleo']],
    ['contas', 'Contas médicas', ['Sem acesso', 'Faturista', 'Coordenação', 'Auditor']],
    ['conduta', 'Comitê de Conduta', ['Sem acesso', 'Membro do Comitê', 'Coordenação do Comitê']]
  ];
  const COLAB = [
    { id: 'ra', nome: 'Renata Alves', email: 'renata.alves@exemplo.com', cargo: 'Diretora Assistencial', setor: 'Diretoria Assistencial', role: 'diretor', ativo: true, interno: true, sa: false, acesso: 'hoje', p: { reunioes: 'Facilitador', pops: 'Validador', ouvidoria: 'Responsável do setor', nsp: 'Membro do Núcleo' } },
    { id: 'cn', nome: 'Carla Nogueira', email: 'carla.nogueira@exemplo.com', cargo: 'Coordenadora de Enfermagem', setor: 'Enfermagem', role: 'coordenador', ativo: true, interno: true, sa: false, acesso: 'hoje', p: { reunioes: 'Colaborador', pops: 'Elaborador' } },
    { id: 'rs', nome: 'Rodrigo Sales', email: 'rodrigo.sales@exemplo.com', cargo: 'Farmacêutico responsável', setor: 'Farmácia', role: 'coordenador', ativo: true, interno: true, sa: false, acesso: 'há 11 dias', p: { reunioes: 'Colaborador', pops: 'Revisor' } },
    { id: 'pm', nome: 'Paulo Mendes', email: 'paulo.mendes@exemplo.com', cargo: 'Supervisor de Suprimentos', setor: 'Suprimentos', role: 'gerente', ativo: true, interno: true, sa: false, acesso: 'ontem', p: { reunioes: 'Colaborador' } },
    { id: 'fl', nome: 'Fernanda Lima', email: 'fernanda.lima@exemplo.com', cargo: 'Enfermeira da CCIH', setor: 'CCIH', role: 'coordenador', ativo: true, interno: true, sa: false, acesso: 'hoje', p: { reunioes: 'Colaborador', nsp: 'Presidência do Núcleo', pops: 'Revisor' } },
    { id: 'jp', nome: 'Juliana Prado', email: 'juliana.prado@exemplo.com', cargo: 'Coordenadora de Hotelaria', setor: 'Hotelaria', role: 'coordenador', ativo: true, interno: true, sa: false, acesso: 'há 2 dias', p: { reunioes: 'Colaborador' } },
    { id: 'lf', nome: 'Luana Freitas', email: 'luana.freitas@exemplo.com', cargo: 'Secretária da Diretoria', setor: 'Diretoria Geral', role: 'coordenador', ativo: true, interno: true, sa: false, acesso: 'hoje', p: { reunioes: 'Secretária', ouvidoria: 'Perfil da Ouvidoria' } },
    { id: 'ba', nome: 'Bruno Araújo', email: 'bruno.araujo@exemplo.com', cargo: 'Faturista', setor: 'Faturamento', role: 'coordenador', ativo: true, interno: true, sa: false, acesso: 'hoje', p: { contas: 'Faturista', pops: 'Leitor' } },
    { id: 'mt', nome: 'Marcos Teixeira', email: 'marcos.teixeira@exemplo.com', cargo: 'Tecnologia', setor: 'Tecnologia', role: 'diretor', ativo: true, interno: true, sa: true, acesso: 'agora', p: { reunioes: 'Facilitador' } },
    { id: 'ds', nome: 'Dra. Sílvia Couto', email: '', cargo: 'Consultora externa', setor: '', role: '', ativo: true, interno: false, sa: false, acesso: 'nunca entrou', p: {} },
    { id: 'gm', nome: 'Gustavo Moreira', email: 'gustavo.moreira@exemplo.com', cargo: 'Técnico de Manutenção', setor: 'Manutenção', role: 'coordenador', ativo: false, interno: true, sa: false, acesso: 'há 4 meses', p: { reunioes: 'Colaborador' } }
  ];
  const HIST = {
    _: [['Hoje, 09:12', 'Entrou no app'], ['Há 3 dias', 'Perfil de POPs mudou de Leitor para Validador, por Marcos Teixeira'], ['Há 2 semanas', 'Senha redefinida a pedido, por Marcos Teixeira'], ['Há 3 meses', 'Cadastro criado por Marcos Teixeira, no setor Diretoria Assistencial']]
  };

  function cabColab(atual) {
    const ativos = COLAB.filter((c) => c.ativo);
    const semSetor = COLAB.filter((c) => c.ativo && c.interno && !c.setor).length + 2;
    const nunca = COLAB.filter((c) => c.ativo && c.acesso === 'nunca entrou').length + 4;
    return {
      cab: { sobre: 'Administração', titulo: 'Colaboradores e acessos', frase: `${ativos.length} pessoas ativas. ${nunca} nunca entraram no app e ${semSetor} estão sem setor: comece por elas.`,
        acoes: `<button class="btn claro grande" data-acao="adm-novo">${IC.mais}Novo Colaborador</button>` },
      resumo: [['Pessoas ativas', dd(ativos.length), I.certo, '#adminusuarios'], ['Nunca entraram', dd(nunca), I.relogio, '#adminusuarios'], ['Sem setor', dd(semSetor), I.alerta, '#admincadastros', true], ['Super admins', dd(COLAB.filter((c) => c.sa).length), I.agenda, '#adminusuarios']],
      abas: N.abasModulo([['#adminusuarios', 'Colaboradores', ativos.length], ['#admincadastros', 'Cadastros', null]], atual)
    };
  }
  N.digitar['adm-busca'] = (v) => { A.busca = v; };
  N.acoes['adm-chip'] = (a) => { A.chip = a.dataset.v; N.desenhar(); };
  T.adminusuarios = { trilha: 'Colaboradores e acessos', menu: 'adminusuarios', mapa: ['Administração', 'Colaboradores e acessos'], render: soAdmin(() => {
    const c = cabColab('#adminusuarios');
    const t = A.busca.trim().toLowerCase();
    const lista = COLAB.filter((p) => A.chip === 'todos' || (A.chip === 'ativos' ? p.ativo : A.chip === 'inativos' ? !p.ativo : A.chip === 'externos' ? !p.interno : p.sa))
      .filter((p) => !t || (p.nome + ' ' + p.email + ' ' + p.setor + ' ' + p.cargo).toLowerCase().includes(t));
    const corpo = `<section class="cartao bloco" style="margin-top:14px">
      <div class="ferramentas">${chips('adm-chip', [['ativos', 'Ativos'], ['inativos', 'Desativados'], ['externos', 'Externos'], ['sa', 'Super admin'], ['todos', 'Todos']], A.chip, 'Quem mostrar')}${busca('adm-busca-i', 'adm-busca', 'Buscar por nome, e-mail ou setor', A.busca)}</div>
      <div class="tabela-rola"><table class="tab"><thead><tr><th>Pessoa</th><th>Cargo e setor</th><th>Acessos</th><th>Último acesso</th><th></th></tr></thead><tbody>
      ${lista.map((p) => { const mods = MODULOS.filter(([k]) => p.p[k]).map(([, n]) => n.split(' ')[0]);
        return `<tr style="${p.ativo ? '' : 'opacity:.6'}"><td><span style="display:inline-flex;align-items:center;gap:10px"><span style="width:34px;height:34px;border-radius:999px;background:var(--suave2);color:var(--titulo);display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:700">${N.ini(p.nome.replace('Dra. ', ''))}</span><span><a href="#adminusuario-${p.id}">${esc(p.nome)}</a><span class="sub" style="display:block">${p.email ? esc(p.email) : 'Sem e-mail, só o nome'}</span></span></span></td>
          <td>${esc(p.cargo)}<div class="sub">${p.setor ? esc(p.setor) : '<span style="color:var(--verm)">Sem setor</span>'}</div></td>
          <td>${p.sa ? '<span class="pill escuro" style="margin-right:6px">Super admin</span>' : ''}${!p.interno ? '<span class="pill cinza">Externo</span>' : mods.length ? `<span class="sub">${mods.join(', ')}</span>` : '<span class="sub">Nenhum</span>'}</td>
          <td>${p.ativo ? esc(p.acesso) : '<span class="pill cinza">Desativado</span>'}</td>
          <td style="text-align:right;white-space:nowrap"><a class="btn contorno" href="#adminusuario-${p.id}">Editar</a> ${pop('adm-' + p.id, `
            <button role="menuitem" data-acao="adm-senha" data-id="${p.id}">Redefinir a senha</button>
            ${!p.interno ? `<button role="menuitem" data-acao="adm-externo" data-id="${p.id}">Ligar a um cadastro interno</button>` : ''}
            <button role="menuitem" data-acao="adm-sa" data-id="${p.id}">${p.sa ? 'Tirar o Super admin' : 'Tornar Super admin'}</button>
            <hr><button role="menuitem" class="perigo" data-acao="adm-desativar" data-id="${p.id}">${p.ativo ? 'Desativar' : 'Reativar'}</button>`)}</td></tr>`; }).join('')}
      </tbody></table>${lista.length ? '' : '<p class="vazio">Ninguém com esse filtro. Tente "Todos" ou limpe a busca.</p>'}</div></section>`;
    return N.modulo(c.cab, c.resumo, c.abas, corpo);
  }) };

  const achar = (id) => COLAB.find((p) => p.id === id);
  N.acoes['adm-novo'] = () => N.modal('Novo Colaborador', `<p class="sub" style="margin:0 0 14px">A pessoa recebe por e-mail o link para criar a senha. Os acessos você liga depois, na ficha.</p>
    <div class="grade-form"><div class="campo"><label for="nv-nome">Nome completo</label><input id="nv-nome"></div><div class="campo"><label for="nv-mail">E-mail</label><input id="nv-mail" type="email"></div>
    <div class="campo"><label for="nv-cargo">Cargo</label><input id="nv-cargo" placeholder="Ex.: Enfermeira"></div><div class="campo"><label for="nv-setor">Setor</label><select id="nv-setor">${SETORES.filter((s) => s.ativo).map((s) => `<option>${esc(s.nome)}</option>`).join('')}</select></div></div>`,
    `<button type="button" class="btn" data-acao="toast" data-msg="Colaborador cadastrado. O convite seguiu por e-mail.">Cadastrar e enviar o convite</button>`);
  N.acoes['adm-senha'] = (a) => { fechaPop(); const p = achar(a.dataset.id); N.modal('Redefinir a senha', `<p style="margin:0">${esc(p.nome)} recebe por e-mail um link para criar uma senha nova. A senha atual deixa de valer agora.</p><div class="campo" style="margin-top:14px"><label for="sn-mot">Motivo</label><input id="sn-mot" placeholder="Ex.: pediu por telefone"></div>`, `<button type="button" class="btn" data-acao="toast" data-msg="Link de senha nova enviado para ${esc(p.nome.split(' ')[0])}.">Enviar o link</button>`); };
  N.acoes['adm-externo'] = (a) => { fechaPop(); const p = achar(a.dataset.id); N.modal('Ligar a um cadastro interno', `<p class="sub" style="margin:0 0 12px">${esc(p.nome)} foi citada numa Ata e ficou como externa. Se ela é do hospital, escolha o cadastro dela: as Pendências passam a ser cobradas.</p><div class="campo"><label for="ex-p">Cadastro</label><select id="ex-p">${COLAB.filter((c) => c.interno).map((c) => `<option>${esc(c.nome)}</option>`).join('')}</select></div>`, `<button type="button" class="btn" data-acao="toast" data-msg="Ligação feita. As Pendências dela agora aparecem no Início da pessoa.">Ligar</button>`); };
  N.acoes['adm-sa'] = (a) => { fechaPop(); const p = achar(a.dataset.id); N.modal(p.sa ? 'Tirar o Super admin' : 'Tornar Super admin', `<p style="margin:0">${p.sa ? `${esc(p.nome)} volta a ver só os módulos que os acessos dela ligam.` : `${esc(p.nome)} passa a ver tudo no app, inclusive a Administração e as ações de correção.`}</p><div class="campo" style="margin-top:14px"><label for="sa-mot">Justificativa (fica no histórico)</label><textarea id="sa-mot"></textarea></div>`, `<button type="button" class="btn" data-acao="adm-sa-ok" data-id="${p.id}">${p.sa ? 'Tirar' : 'Tornar Super admin'}</button>`); };
  N.acoes['adm-sa-ok'] = (a) => { const p = achar(a.dataset.id); p.sa = !p.sa; N.fecharModal(); N.desenhar(); N.aviso(p.sa ? `${p.nome} agora é Super admin.` : `${p.nome} não é mais Super admin.`); };
  N.acoes['adm-desativar'] = (a) => { fechaPop(); const p = achar(a.dataset.id); N.modal(p.ativo ? 'Desativar o Colaborador' : 'Reativar o Colaborador', `<p style="margin:0">${p.ativo ? `${esc(p.nome)} não entra mais no app. As Pendências abertas no nome dela continuam e aparecem para o Facilitador de cada Reunião, para repassar.` : `${esc(p.nome)} volta a entrar com a senha de antes.`}</p><div class="campo" style="margin-top:14px"><label for="ds-mot">Motivo</label><input id="ds-mot"></div>`, `<button type="button" class="btn" style="${p.ativo ? 'background:var(--verm);border-color:var(--verm)' : ''}" data-acao="adm-desativar-ok" data-id="${p.id}">${p.ativo ? 'Desativar' : 'Reativar'}</button>`); };
  N.acoes['adm-desativar-ok'] = (a) => { const p = achar(a.dataset.id); p.ativo = !p.ativo; N.fecharModal(); N.desenhar(); N.aviso(p.ativo ? `${p.nome} reativado.` : `${p.nome} desativado.`); };

  T.adminusuario = { trilha: 'Colaboradores e acessos', menu: 'adminusuarios', mapa: ['Administração', 'Ficha do Colaborador'], render: soAdmin((id) => {
    const p = achar(id) || COLAB[0];
    const corpo = `<div class="duas" style="margin-top:0">
      <section class="cartao bloco larga">
        <h2 class="titulo-bloco">Dados</h2>
        <div class="grade-form" style="margin-top:12px"><div class="campo"><label for="fc-nome">Nome</label><input id="fc-nome" value="${esc(p.nome)}"></div><div class="campo"><label for="fc-mail">E-mail</label><input id="fc-mail" value="${esc(p.email)}"></div>
          <div class="campo"><label for="fc-cargo">Cargo (aparece nas telas)</label><input id="fc-cargo" value="${esc(p.cargo)}"></div><div class="campo"><label for="fc-setor">Setor</label><select id="fc-setor"><option${p.setor ? '' : ' selected'}>Escolha</option>${SETORES.map((s) => `<option${s.nome === p.setor ? ' selected' : ''}>${esc(s.nome)}</option>`).join('')}</select></div></div>
        <p class="sub" style="margin:10px 0 0">Faixa interna: <span class="pill cinza">${p.role ? esc(p.role) : 'sem faixa'}</span> Só o Super admin vê; a pessoa nunca vê esta etiqueta.</p>
        <h2 class="titulo-bloco" style="margin-top:24px">Acessos por módulo</h2>
        <p class="sub" style="margin:4px 0 6px">O que a pessoa vê no menu sai daqui. Mudou, vale no próximo clique dela.</p>
        <div>${MODULOS.map(([k, nome, ops]) => `<div class="perm"><span><b>${nome}</b><small>${p.p[k] ? 'Vê o módulo como ' + p.p[k] : 'Não vê o módulo'}</small></span><label class="sr" for="pm-${k}">${nome}</label><select id="pm-${k}" data-acao-mudar="1">${ops.map((o) => `<option${(p.p[k] || 'Sem acesso') === o ? ' selected' : ''}>${o}</option>`).join('')}</select></div>`).join('')}
          <div class="perm"><span><b>Super admin</b><small>Vê tudo, inclusive esta Administração e as ações de correção</small></span><button type="button" class="chave" role="switch" aria-checked="${p.sa}" aria-label="Super admin" data-acao="adm-sa" data-id="${p.id}"></button></div></div>
        <div class="acoes-item" style="margin-top:18px"><button class="btn grande" data-acao="toast" data-msg="Alterações salvas. Ficam no histórico da pessoa.">Salvar as alterações</button><a class="btn contorno grande" href="#adminusuarios">Cancelar</a></div>
      </section>
      <aside class="estreita">
        <section class="cartao bloco"><h2 class="titulo-bloco">Situação</h2>
          <dl class="pares" style="margin-top:10px"><dt>Último acesso</dt><dd>${esc(p.acesso)}</dd><dt>Cadastro</dt><dd>${p.interno ? 'Interno' : 'Externo, só o nome'}</dd><dt>Situação</dt><dd>${p.ativo ? N.estado('e-ok', 'Ativo') : N.estado('e-sem', 'Desativado')}</dd></dl>
          <div class="acoes-item" style="margin-top:14px"><button class="btn contorno" data-acao="adm-senha" data-id="${p.id}">Redefinir a senha</button></div>
          <hr style="border:0;border-top:1px solid var(--linha);margin:16px 0">
          <button class="btn contorno" style="color:var(--verm);border-color:var(--verm)" data-acao="adm-desativar" data-id="${p.id}">${p.ativo ? 'Desativar o Colaborador' : 'Reativar'}</button></section>
        <section class="cartao bloco"><h2 class="titulo-bloco">Histórico</h2>
          <ul class="tempo" style="margin-top:12px">${(HIST[p.id] || HIST._).map(([q, t], i) => `<li class="${i === 0 ? 'agora' : 'feito'}"><i aria-hidden="true"></i><b>${esc(t)}</b><span>${q}</span></li>`).join('')}</ul></section>
      </aside></div>`;
    return `${N.cabModulo({ sobre: 'Administração · Colaboradores', titulo: esc(p.nome), frase: `${esc(p.cargo)}${p.setor ? ', ' + esc(p.setor) : ''}.` })}<div class="corpo-modulo"><a class="voltar" href="#adminusuarios">${IC.voltar}Voltar aos Colaboradores</a>${corpo}<p class="demo">Dados de demonstração.</p></div>`;
  }) };

  // ================================================================== Cadastros
  const SETORES = ['Diretoria Assistencial', 'Diretoria Geral', 'Enfermagem', 'Farmácia', 'Suprimentos', 'CCIH', 'Hotelaria', 'Faturamento', 'Qualidade', 'Manutenção', 'Tecnologia', 'Emergência', 'UTI Adulto', 'Centro Cirúrgico']
    .map((n, i) => ({ id: 's' + i, nome: n, ativo: i !== 9, quando: dia(-(i * 7 + 3)) }));
  SETORES.push({ id: 'sx', nome: 'Lavanderia', ativo: false, quando: dia(-200) });
  const CARGOS = ['Diretora Assistencial', 'Coordenadora de Enfermagem', 'Enfermeira', 'Técnica de Enfermagem', 'Farmacêutico responsável', 'Supervisor de Suprimentos', 'Faturista', 'Secretária da Diretoria', 'Técnico de Manutenção']
    .map((n, i) => ({ id: 'c' + i, nome: n, ativo: true, quando: dia(-(i * 11 + 5)) }));
  const TIPOS = ['Reunião de Diretoria', 'Comissão', 'Reunião operacional', 'Reunião do Núcleo', 'Treinamento', 'Visita de acreditação']
    .map((n, i) => ({ id: 't' + i, nome: n, ativo: i !== 5, quando: dia(-(i * 13 + 9)) }));
  const ACERTOS = {
    reunioes: [['Reunião de alinhamento da Hotelaria', curto(dia(-9))], ['Passagem de turno da Emergência', curto(dia(-4))]],
    pessoas: [['Dra. Sílvia Couto', 'Consultora externa'], ['Tatiane Rocha', 'Técnica de Enfermagem'], ['Igor Batista', 'Maqueiro']],
    pendencias: [['Revisar o contrato de lavanderia', 'Reunião de Hotelaria'], ['Ajustar a escala de férias', 'Reunião de Enfermagem']]
  };
  const CAD = { setores: ['Setores', 'Setor', SETORES], cargos: ['Cargos', 'Cargo', CARGOS], tipos: ['Tipos de Reunião', 'Tipo de Reunião', TIPOS] };
  N.digitar['cad-busca'] = (v) => { A.cadBusca = v; };
  N.acoes['cad-aba'] = (a) => { A.cadAba = a.dataset.v; A.cadBusca = ''; N.desenhar(); };
  N.acoes['cad-ver'] = (a) => { A.cadVer = a.dataset.v; N.desenhar(); };
  T.admincadastros = { trilha: 'Cadastros', menu: 'admincadastros', mapa: ['Administração', 'Cadastros e Acertos de setor'], render: soAdmin(() => {
    const nAcertos = ACERTOS.reunioes.length + ACERTOS.pessoas.length + ACERTOS.pendencias.length;
    const abasInternas = `<div class="abas" role="tablist" style="margin-top:0">${[['setores', `Setores (${SETORES.filter((s) => s.ativo).length})`], ['cargos', `Cargos (${CARGOS.length})`], ['tipos', `Tipos de Reunião (${TIPOS.filter((s) => s.ativo).length})`], ['acertos', `Acertos de setor (${nAcertos})`]].map(([k, t]) => `<button type="button" role="tab" aria-selected="${A.cadAba === k}" data-acao="cad-aba" data-v="${k}">${t}</button>`).join('')}</div>`;
    let miolo;
    if (A.cadAba === 'acertos') {
      const bloco = (tit, sub, linhas, fim) => `<section style="margin-top:16px"><h3 class="titulo-bloco" style="font-size:15.5px">${tit}</h3><p class="sub" style="margin:2px 0 6px">${sub}</p>${linhas.length ? `<ul class="linhas">${linhas.map(fim).join('')}</ul>` : '<p class="vazio">Nada para acertar aqui.</p>'}</section>`;
      const sel = (i) => `<select aria-label="Setor" style="min-height:38px;padding:0 10px;border:1px solid var(--campo-borda);border-radius:8px;background:var(--campo)" id="ac-${i}"><option>Escolha o setor</option>${SETORES.filter((s) => s.ativo).map((s) => `<option>${esc(s.nome)}</option>`).join('')}</select>`;
      miolo = `<p class="aviso">${I.info}Sem setor, a Reunião e a pessoa não entram nos gráficos por setor do Dashboard. Ao salvar, a linha some daqui.</p>
        ${bloco('Reuniões sem setor', 'Escolha o setor da Reunião.', ACERTOS.reunioes, ([t, d], i) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) 220px auto"><span class="t">${esc(t)}<small>Reunião de ${d}</small></span>${sel('r' + i)}<button class="btn" data-acao="cad-acerto" data-tipo="reunioes" data-i="${i}">Salvar</button></li>`)}
        ${bloco('Responsáveis sem setor', 'Pessoas com Pendência no nome e sem setor no cadastro.', ACERTOS.pessoas, ([t, d], i) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) 220px auto"><span class="t">${esc(t)}<small>${esc(d)}</small></span>${sel('p' + i)}<button class="btn" data-acao="cad-acerto" data-tipo="pessoas" data-i="${i}">Salvar</button></li>`)}
        ${bloco('Pendências sem prazo', 'Sem prazo, a Pendência nunca fica atrasada. Abra e combine a data com o responsável.', ACERTOS.pendencias, ([t, d]) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">${esc(t)}<small>${esc(d)}</small></span><a class="btn contorno" href="#pendencias">Abrir a Pendência</a></li>`)}`;
    } else {
      const [titulo, um, dados] = CAD[A.cadAba];
      const t = A.cadBusca.trim().toLowerCase();
      const lista = dados.filter((d) => A.cadVer === 'todos' || (A.cadVer === 'ativos' ? d.ativo : !d.ativo)).filter((d) => !t || d.nome.toLowerCase().includes(t));
      miolo = `<div class="ferramentas" style="margin-top:14px">${chips('cad-ver', [['ativos', 'Ativos'], ['arquivados', 'Arquivados'], ['todos', 'Todos']], A.cadVer, 'Situação')}<div style="display:flex;gap:8px;align-items:center;flex:0 1 560px;justify-content:flex-end">${busca('cad-busca-i', 'cad-busca', 'Buscar ' + titulo.toLowerCase(), A.cadBusca)}<button class="btn" data-acao="cad-editar" data-id="">${IC.mais}Novo ${um.toLowerCase()}</button></div></div>
        <div class="tabela-rola"><table class="tab"><thead><tr><th>${um}</th><th>Situação</th><th>Atualizado</th><th></th></tr></thead><tbody>
        ${lista.map((d) => `<tr><td><b style="color:var(--titulo)">${esc(d.nome)}</b></td><td>${d.ativo ? N.estado('e-ok', 'Ativo') : N.estado('e-sem', 'Arquivado')}</td><td class="num">${fmt(d.quando)}</td>
          <td style="text-align:right;white-space:nowrap"><button class="btn contorno" data-acao="cad-editar" data-id="${d.id}">Editar</button> <button class="btn contorno" data-acao="cad-arquivar" data-id="${d.id}">${d.ativo ? 'Arquivar' : 'Reativar'}</button></td></tr>`).join('')}
        </tbody></table>${lista.length ? '' : `<p class="vazio">Nenhum ${um.toLowerCase()} com esse filtro.</p>`}</div>`;
    }
    const c = cabColab('#admincadastros');
    return N.modulo({ sobre: 'Administração', titulo: 'Cadastros', frase: `As listas que o resto do app usa: setores, cargos e tipos de Reunião. ${nAcertos} itens esperam um setor ou um prazo.` },
      null, c.abas, `<section class="cartao bloco" style="margin-top:14px">${abasInternas}${miolo}</section>`);
  }) };
  const achaCad = (id) => [...SETORES, ...CARGOS, ...TIPOS].find((d) => d.id === id);
  N.acoes['cad-editar'] = (a) => { const d = achaCad(a.dataset.id); const um = CAD[A.cadAba][1]; N.modal(d ? `Editar ${um.toLowerCase()}` : `Novo ${um.toLowerCase()}`, `<div class="campo"><label for="cd-nome">Nome</label><input id="cd-nome" value="${d ? esc(d.nome) : ''}"></div>${d ? '<p class="sub" style="margin:10px 0 0">O nome novo aparece em todas as telas, inclusive nas Reuniões antigas.</p>' : ''}`, `<button type="button" class="btn" data-acao="toast" data-msg="${um} salvo.">Salvar</button>`); };
  N.acoes['cad-arquivar'] = (a) => { const d = achaCad(a.dataset.id); N.modal(d.ativo ? 'Arquivar' : 'Reativar', `<p style="margin:0">${d.ativo ? `"${esc(d.nome)}" some das listas de escolha. O que já usa esse nome continua como está.` : `"${esc(d.nome)}" volta às listas de escolha.`}</p>`, `<button type="button" class="btn" data-acao="cad-arquivar-ok" data-id="${d.id}">${d.ativo ? 'Arquivar' : 'Reativar'}</button>`); };
  N.acoes['cad-arquivar-ok'] = (a) => { const d = achaCad(a.dataset.id); d.ativo = !d.ativo; N.fecharModal(); N.desenhar(); N.aviso(d.ativo ? `${d.nome} reativado.` : `${d.nome} arquivado.`); };
  N.acoes['cad-acerto'] = (a) => { const s = document.getElementById('ac-' + (a.dataset.tipo === 'reunioes' ? 'r' : 'p') + a.dataset.i); if (s && s.selectedIndex === 0) { N.aviso('Escolha o setor antes de salvar.'); return; } ACERTOS[a.dataset.tipo].splice(Number(a.dataset.i), 1); N.desenhar(); N.aviso('Setor salvo.'); };

  // ================================================================== Dados do atendimento (as tabelas da Ana)
  const AT = {
    consultas: { tit: 'Consultas particulares', cols: ['Especialidade', 'Profissional', 'Valor'], linhas: [['Cardiologia', 'Dr. Henrique Lobo', 350], ['Dermatologia', 'Dra. Paula Vieira', 300], ['Ortopedia', 'Dr. Caio Ramos', 320], ['Pediatria', 'Dra. Lívia Torres', 280], ['Ginecologia', 'Dra. Bianca Melo', 300], ['Neurologia', 'Dr. Otávio Sena', 380]] },
    exames: { tit: 'Exames', cols: ['Exame', 'Preparo', 'Valor'], linhas: [['Hemograma completo', 'Jejum de 4 horas', 38], ['Ultrassom de abdome total', 'Jejum de 8 horas', 220], ['Eletrocardiograma', 'Sem preparo', 90], ['Raio X de tórax', 'Sem preparo', 110], ['Tomografia de crânio', 'Sem preparo', 480]] },
    cirurgias: { tit: 'Estimativas de cirurgias', cols: ['Cirurgia', 'Internação', 'Faixa estimada'], linhas: [['Colecistectomia por vídeo', '1 dia', 14500], ['Hernioplastia inguinal', '1 dia', 9800], ['Artroscopia de joelho', 'Sem internação', 12300], ['Cesariana', '2 dias', 11200]] }
  };
  N.digitar['at-busca'] = (v) => { A.atBusca = v; };
  N.acoes['at-aba'] = (a) => { A.atAba = a.dataset.v; A.atBusca = ''; N.desenhar(); };
  N.acoes['at-esp'] = (a) => { A[a.dataset.campo] = a.dataset.v; N.desenhar(); };
  T.atendimento = { trilha: 'Dados do atendimento', menu: 'atendimento', mapa: ['Administração', 'Dados do atendimento (Ana)'], render: soAdmin(() => {
    const abas = `<div class="abas" role="tablist" style="margin-top:0">${[['consultas', 'Consultas particulares'], ['exames', 'Exames'], ['cirurgias', 'Estimativas de cirurgias'], ['espelho', 'Espelho da Global Health']].map(([k, t]) => `<button type="button" role="tab" aria-selected="${A.atAba === k}" data-acao="at-aba" data-v="${k}">${t}</button>`).join('')}</div>`;
    let miolo;
    if (A.atAba === 'espelho') {
      const ESP = ['Cardiologia', 'Ortopedia', 'Pediatria', 'Dermatologia'], CONV = ['Particular', 'Unimed', 'Amil', 'Bradesco Saúde'];
      const horarios = ['08:00', '08:30', '09:30', '10:00', '14:00', '15:30'].map((h, i) => [curto(dia(i < 3 ? 1 : 2)), h, i % 2 ? 'Dra. Lívia Torres' : 'Dr. Henrique Lobo']);
      miolo = `<p class="aviso">${I.info}Só consulta: são os horários que a Global Health mostra agora, para conferir o que a Ana responde. Nada se edita aqui.</p>
        <div class="grade g2" style="margin-top:14px"><div><p class="rot-mini">1. Especialidade</p><div class="chips" style="margin-top:8px">${ESP.map((e) => `<button class="chip" data-acao="at-esp" data-campo="esp" data-v="${e}" aria-pressed="${A.esp === e}">${e}</button>`).join('')}</div></div>
        <div><p class="rot-mini">2. Convênio</p><div class="chips" style="margin-top:8px">${CONV.map((e) => `<button class="chip" data-acao="at-esp" data-campo="conv" data-v="${e}" aria-pressed="${A.conv === e}">${e}</button>`).join('')}</div></div></div>
        <div class="cab" style="margin-top:18px"><p class="rot-mini">3. Horários livres de ${esc(A.esp)}, ${esc(A.conv)}</p><button class="btn contorno" data-acao="toast" data-msg="Espelho atualizado agora.">Atualizar</button></div>
        <ul class="linhas">${horarios.map(([d, h, p]) => `<li class="linha" style="grid-template-columns:120px 80px minmax(0,1fr)"><span class="num">${d}</span><b class="num" style="color:var(--titulo)">${h}</b><span class="t">${p}</span></li>`).join('')}</ul>`;
    } else {
      const tb = AT[A.atAba]; const t = A.atBusca.trim().toLowerCase();
      const lista = tb.linhas.map((l, i) => [l, i]).filter(([l]) => !t || l.join(' ').toLowerCase().includes(t));
      miolo = `<div class="ferramentas" style="margin-top:14px">${busca('at-busca-i', 'at-busca', 'Buscar em ' + tb.tit.toLowerCase(), A.atBusca)}<div style="display:flex;gap:8px;align-items:center"><span class="sub">Atualizado ${fmt(dia(-2))}</span><button class="btn" data-acao="at-editar" data-i="">${IC.mais}Novo registro</button></div></div>
        <div class="tabela-rola"><table class="tab"><thead><tr>${tb.cols.map((c) => `<th>${c}</th>`).join('')}<th>Situação</th><th></th></tr></thead><tbody>
        ${lista.map(([l, i]) => `<tr><td><b style="color:var(--titulo)">${esc(l[0])}</b></td><td>${esc(l[1])}</td><td class="num">${A.atAba === 'cirurgias' ? brl(l[2] * 0.85) + ' a ' + brl(l[2] * 1.15) : brl(l[2])}</td><td>${N.estado('e-ok', 'Ativo')}</td><td style="text-align:right"><button class="btn contorno" data-acao="at-editar" data-i="${i}">Editar</button></td></tr>`).join('')}
        </tbody></table>${lista.length ? '' : '<p class="vazio">Nada com esse texto.</p>'}</div>
        ${A.atAba === 'cirurgias' ? `<p class="aviso">${I.info}A Ana sempre diz que a faixa é estimativa e que o valor final sai da avaliação do cirurgião.</p>` : ''}`;
    }
    return N.modulo({ sobre: 'Administração', titulo: 'Dados do atendimento', frase: 'Os valores e horários que a Ana usa para responder aos pacientes no WhatsApp. O que muda aqui vale na próxima resposta dela.' },
      [['Consultas ativas', dd(AT.consultas.linhas.length), I.certo, '#atendimento'], ['Exames ativos', dd(AT.exames.linhas.length), I.certo, '#atendimento'], ['Cirurgias com estimativa', dd(AT.cirurgias.linhas.length), I.certo, '#atendimento'], ['Sem atualizar há 90 dias', '02', I.alerta, '#atendimento', true]],
      '', `<section class="cartao bloco" style="margin-top:14px">${abas}${miolo}</section>`);
  }) };
  N.acoes['at-editar'] = (a) => {
    const tb = AT[A.atAba]; const l = a.dataset.i === '' ? null : tb.linhas[Number(a.dataset.i)];
    N.abrirGaveta({ sobre: `<span class="pill">${tb.tit}</span>`, titulo: l ? esc(l[0]) : 'Novo registro',
      corpo: `<div class="campo"><label for="ae-1">${tb.cols[0]}</label><input id="ae-1" value="${l ? esc(l[0]) : ''}"></div><div class="campo"><label for="ae-2">${tb.cols[1]}</label><input id="ae-2" value="${l ? esc(l[1]) : ''}"></div>
        <div class="campo"><label for="ae-3">Valor${A.atAba === 'cirurgias' ? ' de referência' : ''} (R$)</label><input id="ae-3" inputmode="decimal" value="${l ? l[2].toFixed(2).replace('.', ',') : ''}"></div>
        <div class="campo"><label for="ae-4">Observação que a Ana pode dizer</label><textarea id="ae-4" placeholder="Ex.: atende só às terças e quintas"></textarea></div>
        <label style="display:flex;align-items:center;gap:10px"><input type="checkbox" checked style="width:18px;height:18px"> Ativo (a Ana usa este registro)</label>`,
      pe: `<button class="btn contorno" data-acao="fechar-gaveta">Cancelar</button><button class="btn" data-acao="at-salvar">Salvar</button>` });
  };
  N.acoes['at-salvar'] = () => { N.acoes['fechar-gaveta'](); N.aviso('Registro salvo. A Ana usa o valor novo a partir de agora.'); };

  // ================================================================== Central de Comando
  const PER = [['7', '7 dias'], ['28', '28 dias'], ['90', '90 dias']];
  N.acoes['cc-periodo'] = (a) => { A.periodo = a.dataset.v; N.desenhar(); };
  N.acoes['cc-atualizar'] = () => { A.atualizado = 'agora'; N.desenhar(); N.aviso('Números atualizados agora.'); };
  const serie = (n, base, var_) => Array.from({ length: n }, (_, i) => Math.round(base + Math.sin(i / 2.3) * var_ + (i % 5) * var_ / 4 + i * base / (n * 6)));
  function grafLinha(vals, alt) {
    const w = 600, h = alt || 120, max = Math.max(...vals) * 1.1, passo = w / (vals.length - 1);
    const pts = vals.map((v, i) => `${(i * passo).toFixed(1)},${(h - v / max * h).toFixed(1)}`);
    return `<svg class="linha-graf" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Evolução no período"><path class="a" d="M0,${h} L${pts.join(' L')} L${w},${h} Z"/><path class="l" d="M${pts.join(' L')}"/></svg>`;
  }
  const OBJ = [
    { id: 'contatos', t: 'Gerar mais contatos pelo site', v: '312', meta: 'meta 400 no mês', p: 78, delta: '+18% contra o período anterior' },
    { id: 'google', t: 'Melhorar a nota no Google', v: '4,3', meta: 'meta 4,6', p: 62, delta: '+0,1 em 30 dias' },
    { id: 'instagram', t: 'Crescer no Instagram', v: '18,4 mil', meta: 'meta 20 mil seguidores', p: 92, delta: '+640 seguidores' },
    { id: 'agendamentos', t: 'Mais agendamentos pela Ana', v: '146', meta: 'meta 200 no mês', p: 73, delta: '+9% contra o período anterior' },
    { id: 'reputacao', t: 'Responder toda avaliação', v: '', meta: 'em construção', p: 0, breve: true },
    { id: 'campanhas', t: 'Medir as campanhas pagas', v: '', meta: 'em construção', p: 0, breve: true }
  ];
  function cabCentral(atual, titulo, frase) {
    return { cab: { sobre: 'Administração · Central de Comando', titulo, frase },
      abas: N.abasModulo([['#central', 'Visão geral'], ['#centralobjetivos', 'Objetivos', 4], ['#centralgoogle', 'Google'], ['#centralinstagram', 'Instagram']], atual) };
  }
  const barraFrescor = () => `<div class="frescor"><div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap"><span class="aovivo"><i aria-hidden="true"></i>Ao vivo: 23 pessoas no Site agora</span><span class="sub">Números de ${A.atualizado}</span></div>
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">${chips('cc-periodo', PER, A.periodo, 'Período')}<button class="btn contorno" data-acao="cc-atualizar">Atualizar agora</button></div></div>`;
  const mult = () => Number(A.periodo) / 28;
  T.central = { trilha: 'Central de Comando', menu: 'central', mapa: ['Administração', 'Central de Comando: Visão geral'], render: soAdmin(() => {
    const vis = Math.round(8420 * mult());
    const c = cabCentral('#central', 'Central de Comando', `Nos últimos ${A.periodo} dias o Site teve ${vis.toLocaleString('pt-BR')} visitantes e gerou ${Math.round(312 * mult())} contatos. O Instagram ganhou ${Math.round(640 * mult())} seguidores.`);
    const corpo = `${barraFrescor()}
      <div class="duas" style="margin-top:14px"><section class="cartao bloco larga"><div class="cab"><h2 class="titulo-bloco">Visitantes do Site</h2><a class="link" href="#centralgoogle">Ver no Google ${IC.seta}</a></div>
        <p class="numero" style="margin-top:8px">${vis.toLocaleString('pt-BR')}</p><p class="sub" style="margin:2px 0 8px">+12% contra os ${A.periodo} dias anteriores</p>${grafLinha(serie(Math.min(Number(A.periodo), 30), 280, 60))}</section>
      <aside class="estreita"><section class="cartao bloco"><div class="cab"><h2 class="titulo-bloco">Instagram num relance</h2><a class="link" href="#centralinstagram">Abrir</a></div>
        <dl class="pares" style="margin-top:10px"><dt>Seguidores</dt><dd class="num"><b>18.412</b> <span class="sub">+${Math.round(640 * mult())}</span></dd><dt>Alcance</dt><dd class="num">${Math.round(52000 * mult()).toLocaleString('pt-BR')}</dd><dt>Interações</dt><dd class="num">${Math.round(3900 * mult()).toLocaleString('pt-BR')}</dd></dl></section>
        <section class="cartao bloco"><h2 class="titulo-bloco">Atalhos</h2><div class="tiles" style="margin-top:12px"><a class="tile" href="#centralobjetivos">${IC.radar}Objetivos</a><a class="tile" href="#atendimento">${N.ic('<path d="M4 5h16v11H10l-5 4v-4H4z"/>', 20)}Tabelas da Ana</a><a class="tile" href="#ouvidoria">${IC.estrela}Avaliações</a><a class="tile" href="#tecnologia">${IC.codigo}Tecnologia</a></div></section></aside></div>
      <section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2 class="titulo-bloco">Objetivos em foco</h2><a class="link" href="#centralobjetivos">Todos os objetivos ${IC.seta}</a></div>
        <div class="grade g4">${OBJ.filter((o) => !o.breve).map(cartaoObj).join('')}</div></section>
      <section class="cartao bloco" style="margin-top:14px"><h2 class="titulo-bloco">O que vem por aí</h2><p class="sub" style="margin:4px 0 0">Avaliações do Google respondidas pelo app e o custo por contato das campanhas pagas entram nas próximas entregas.</p></section>`;
    return N.modulo(c.cab, [['Visitantes', vis.toLocaleString('pt-BR'), I.certo, '#centralgoogle'], ['Contatos gerados', String(Math.round(312 * mult())), I.agenda, '#centralgoogle'], ['Seguidores', '18,4 mil', I.certo, '#centralinstagram'], ['Nota no Google', '4,3', I.alerta, '#centralobjetivo-google']], c.abas, corpo);
  }) };
  function cartaoObj(o) {
    if (o.breve) return `<div class="cartao bloco objetivo breve"><span class="rot-mini">Em construção</span><h3 class="titulo-bloco" style="font-size:15.5px;margin-top:6px">${o.t}</h3><p class="sub" style="margin:6px 0 0">Ainda não tem número. Entra quando o conector chegar.</p></div>`;
    return `<a class="cartao bloco cartao-link objetivo" href="#centralobjetivo-${o.id}"><span class="rot-mini">${o.meta}</span><h3 class="titulo-bloco" style="font-size:15.5px;margin-top:6px">${o.t}</h3><p class="numero" style="margin-top:8px">${o.v}</p><div class="prog"><span style="width:${o.p}%"></span></div><p class="sub" style="margin:8px 0 0">${o.delta}</p><span class="ir">Ver a lente ${IC.seta}</span></a>`;
  }
  T.centralobjetivos = { trilha: 'Central de Comando', menu: 'central', mapa: ['Administração', 'Central de Comando: Objetivos'], render: soAdmin(() => {
    const c = cabCentral('#centralobjetivos', 'Objetivos', 'Cada objetivo junta os números que mostram se o hospital está chegando lá, com sugestões do que fazer.');
    return N.modulo(c.cab, null, c.abas, `${barraFrescor()}<div class="grade g3">${OBJ.map(cartaoObj).join('')}</div>`);
  }) };
  T.centralobjetivo = { trilha: 'Central de Comando', menu: 'central', mapa: ['Administração', 'Central de Comando: lente de um Objetivo'], render: soAdmin((id) => {
    const o = OBJ.find((x) => x.id === id && !x.breve);
    if (!o) return N.modulo({ sobre: 'Central de Comando', titulo: 'Objetivo não encontrado' }, null, '', `<p class="pagina-sub">Esse objetivo não existe ou ainda está em construção. <a href="#centralobjetivos">Ver os objetivos</a></p>`);
    const google = o.id === 'google';
    const SUG = google ? [['Imprimir o cartaz do QR nos 3 pontos sem convite', 'As notas que chegam pelo QR têm média 4,7; os pontos sem cartaz puxam a média para baixo.', '#ouvidoria'], ['Responder as 6 avaliações de 1 e 2 estrelas do mês', 'Avaliação respondida em até 48 horas sobe a nota de volta em média 0,8 ponto.', '#ouvidoria']]
      : [['Revisar a página de Cardiologia', 'É a área com mais visitas e a menor taxa de contato (1,2%).', '#central'], ['Pôr o botão do WhatsApp no topo das páginas de exame', 'No celular, 64% saem antes de rolar até o botão.', '#central']];
    const corpo = `<a class="voltar" href="#centralobjetivos">${IC.voltar}Objetivos</a>${google ? '' : barraFrescor()}
      <div class="duas" style="margin-top:14px"><section class="cartao bloco larga"><span class="rot-mini">${o.meta}</span><p class="numero" style="margin-top:6px">${o.v}</p><p class="sub" style="margin:2px 0 10px">${o.delta}</p><div class="prog"><span style="width:${o.p}%"></span></div>
        <h2 class="titulo-bloco" style="margin-top:20px">${google ? 'Nota da semana, no mês' : 'No período'}</h2>${grafLinha(serie(google ? 5 : 20, google ? 40 : 10, google ? 3 : 4))}
        ${google ? `<p class="aviso">${I.info}A nota do Google chega uma vez por semana, pela Ouvidoria. Por isso aqui não tem "Atualizar agora".</p>` : ''}</section>
      <aside class="estreita"><section class="cartao bloco"><h2 class="titulo-bloco">O que fazer</h2>${SUG.map(([t, p, h]) => `<div style="padding:12px 0;border-bottom:1px solid var(--linha)"><b style="color:var(--titulo)">${t}</b><p class="sub" style="margin:4px 0 8px">Por quê: ${p}</p><a class="link" style="font-weight:700;font-size:13.5px" href="${h}">Abrir ${IC.seta}</a></div>`).join('')}</section>
        ${google ? `<section class="cartao bloco"><h2 class="titulo-bloco">Teste do convite por QR</h2><p class="sub" style="margin:4px 0 8px">Nos pontos com o convite ligado, quem dá nota 5 no QR é chamado a avaliar no Google.</p><dl class="pares"><dt>Convites</dt><dd class="num">84</dd><dt>Viraram avaliação</dt><dd class="num">19 (23%)</dd></dl></section>` : ''}</aside></div>`;
    const c = cabCentral('#centralobjetivos', o.t, `${o.v} hoje, ${o.meta}. ${o.delta}.`);
    return N.modulo(c.cab, null, c.abas, corpo);
  }) };
  T.centralgoogle = { trilha: 'Central de Comando', menu: 'central', mapa: ['Administração', 'Central de Comando: Google'], render: soAdmin(() => {
    const c = cabCentral('#centralgoogle', 'Site, pelo Google', 'Quantas pessoas visitam o Site, de onde vêm, o que leem e quantas viram contato.');
    const AREAS = [['Exames', 31], ['Cardiologia', 18], ['Pronto atendimento', 14], ['Maternidade', 11], ['Convênios', 9]];
    const ORIG = [['Busca no Google', 46], ['Direto', 21], ['Instagram', 17], ['Outros sites', 9], ['Não identificado', 7]];
    const barras = (dados) => dados.map(([n, v]) => `<div style="margin-top:12px"><div style="display:flex;justify-content:space-between;font-size:14px"><span>${n}</span><span class="num sub">${v}%</span></div><div class="prog" style="margin-top:6px"><span style="width:${v * 2}%"></span></div></div>`).join('');
    const corpo = `${barraFrescor()}
      <section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2 class="titulo-bloco">Movimento do Site por dia</h2><span class="legenda" style="margin:0"><span><i style="background:var(--acento)"></i>Este período</span></span></div>${grafLinha(serie(Math.min(Number(A.periodo), 30), 280, 60), 160)}</section>
      <div class="grade g3"><section class="cartao bloco"><h2 class="titulo-bloco">Áreas do Site</h2>${barras(AREAS)}</section><section class="cartao bloco"><h2 class="titulo-bloco">Origem do público</h2>${barras(ORIG)}</section>
        <section class="cartao bloco"><h2 class="titulo-bloco">Por dispositivo</h2>${barras([['Celular', 72], ['Computador', 25], ['Tablet', 3]])}<h2 class="titulo-bloco" style="margin-top:22px">Contatos gerados</h2><dl class="pares" style="margin-top:8px"><dt>WhatsApp</dt><dd class="num">${Math.round(208 * mult())}</dd><dt>Telefone</dt><dd class="num">${Math.round(71 * mult())}</dd><dt>Formulário</dt><dd class="num">${Math.round(33 * mult())}</dd></dl></section></div>`;
    return N.modulo(c.cab, null, c.abas, corpo);
  }) };
  T.centralinstagram = { trilha: 'Central de Comando', menu: 'central', mapa: ['Administração', 'Central de Comando: Instagram'], render: soAdmin(() => {
    const c = cabCentral('#centralinstagram', 'Instagram', 'Seguidores, alcance e o que mais engajou no período.');
    const POSTS = [['Dia do Médico: homenagem à equipe', 'Carrossel', 4120, 612], ['Por dentro da nova UTI', 'Vídeo', 9840, 1180], ['Outubro Rosa: agende a mamografia', 'Imagem', 3310, 401], ['Pergunte ao cardiologista', 'Vídeo', 6200, 734]];
    const corpo = `${barraFrescor()}
      <div class="grade g4">${[['Seguidores', '18.412', '+640'], ['Alcance', Math.round(52000 * mult()).toLocaleString('pt-BR'), '+8%'], ['Visualizações', Math.round(131000 * mult()).toLocaleString('pt-BR'), '+15%'], ['Interações', Math.round(3900 * mult()).toLocaleString('pt-BR'), '+4%']].map(([r, v, d]) => `<div class="cartao bloco"><span class="rot-mini">${r}</span><p class="numero" style="margin-top:6px">${v}</p><p class="sub" style="margin:2px 0 0">${d} no período</p></div>`).join('')}</div>
      <section class="cartao bloco" style="margin-top:14px"><h2 class="titulo-bloco">Principais publicações</h2><div class="tabela-rola"><table class="tab" style="margin-top:8px"><thead><tr><th>Publicação</th><th>Formato</th><th>Alcance</th><th>Interações</th></tr></thead><tbody>
        ${POSTS.sort((a, b) => b[3] - a[3]).map(([t, f, al, i]) => `<tr><td><b style="color:var(--titulo)">${t}</b></td><td><span class="pill">${f}</span></td><td class="num">${al.toLocaleString('pt-BR')}</td><td class="num">${i.toLocaleString('pt-BR')}</td></tr>`).join('')}</tbody></table></div></section>`;
    return N.modulo(c.cab, null, c.abas, corpo);
  }) };

  // ================================================================== Tecnologia
  const ETAPAS = [['registrada', 'Registrada'], ['analise', 'Em análise'], ['planejada', 'Planejada'], ['desenvolvimento', 'Em desenvolvimento'], ['entregue', 'Entregue']];
  const DEM = [
    { n: 118, t: 'Lembrete de Pendência pelo WhatsApp', tipo: 'Melhoria', origem: 'Pedido do diretor', proj: 'Aplicativo do Hospital', etapa: 'desenvolvimento', partes: [3, 5], resp: 'PR', demo: false, plano: true, dias: 12 },
    { n: 121, t: 'Ana confirma consulta na véspera', tipo: 'Melhoria', origem: 'Pedido do diretor', proj: 'Ana', etapa: 'desenvolvimento', partes: [1, 4], resp: 'LC', demo: false, plano: true, dias: 9 },
    { n: 124, t: 'O PDF da Ata corta o quadro de atribuições', tipo: 'Bug', origem: 'Relato no app', proj: 'Aplicativo do Hospital', etapa: 'analise', partes: null, resp: 'PR', dias: 2 },
    { n: 125, t: 'Painel de indicadores do Núcleo', tipo: 'Melhoria', origem: 'Pedido do diretor', proj: 'Aplicativo do Hospital', etapa: 'planejada', partes: [0, 6], resp: 'PR', plano: true, dias: 5 },
    { n: 126, t: 'Filtro por convênio nas Contas médicas', tipo: 'Melhoria', origem: 'Vitta', proj: 'Aplicativo do Hospital', etapa: 'planejada', partes: [0, 3], resp: 'LC', plano: false, dias: 4 },
    { n: 127, t: 'Busca não acha POP pelo código', tipo: 'Bug', origem: 'Relato no app', proj: 'Aplicativo do Hospital', etapa: 'registrada', partes: null, resp: 'PR', dias: 1 },
    { n: 128, t: 'Ana responde preço de exame desativado', tipo: 'Bug', origem: 'Vitta', proj: 'Ana', etapa: 'analise', partes: null, resp: 'LC', dias: 3 },
    { n: 129, t: 'Nova tela inicial no modelo 2B', tipo: 'Melhoria', origem: 'Pedido do diretor', proj: 'Aplicativo do Hospital', etapa: 'registrada', partes: null, resp: 'PR', dias: 0 },
    { n: 112, t: 'Início com a Minha Fila de todos os módulos', tipo: 'Melhoria', origem: 'Pedido do diretor', proj: 'Aplicativo do Hospital', etapa: 'entregue', partes: [7, 7], resp: 'PR', demo: true, plano: true, versao: '0.163', dias: 3, tam: 'G', sem: 0 },
    { n: 115, t: 'Assinatura da Ata pelo celular', tipo: 'Melhoria', origem: 'Vitta', proj: 'Aplicativo do Hospital', etapa: 'entregue', partes: [2, 2], resp: 'LC', demo: true, versao: '0.162', dias: 6, tam: 'M', sem: 0 },
    { n: 117, t: 'Ouvidoria não mostrava o prazo da área', tipo: 'Bug', origem: 'Relato no app', proj: 'Aplicativo do Hospital', etapa: 'entregue', partes: null, resp: 'PR', demo: false, versao: '0.162', dias: 9, tam: 'P', sem: 1 },
    { n: 110, t: 'Ana agenda retorno de exame', tipo: 'Melhoria', origem: 'Pedido do diretor', proj: 'Ana', etapa: 'entregue', partes: [4, 4], resp: 'LC', demo: true, plano: true, versao: 'Ana 2.4', dias: 15, tam: 'G', sem: 2 },
    { n: 114, t: 'Calendário sem a legenda de Aprovada', tipo: 'Bug', origem: 'Vitta', proj: 'Aplicativo do Hospital', etapa: 'entregue', partes: null, resp: 'PR', versao: '0.161', dias: 17, tam: 'P', sem: 2 }
  ];
  const OQM = ['A Pendência atrasada avisa o responsável no WhatsApp, uma vez por dia, às 8h.', 'O aviso leva o link direto para a Pendência.', 'Quem não quer receber desliga no próprio perfil.', 'O Facilitador vê no Início quem já foi avisado.'];
  const filtraDem = () => {
    const t = A.tBusca.trim().toLowerCase();
    return DEM.filter((d) => (A.tTipo === 'todos' || d.tipo === A.tTipo) && (A.tOrigem === 'todas' || d.origem === A.tOrigem) && (A.tProjeto === 'todos' || d.proj === A.tProjeto) && (!t || (d.t + ' ' + d.n).toLowerCase().includes(t)));
  };
  N.digitar['tec-busca'] = (v) => { A.tBusca = v; };
  N.acoes['tec-f'] = (a) => { A[a.dataset.campo] = a.dataset.v; A.semana = null; N.desenhar(); };
  function filtrosTec() {
    const ch = (campo, ops) => `<div class="chips">${ops.map(([k, t]) => `<button class="chip" data-acao="tec-f" data-campo="${campo}" data-v="${k}" aria-pressed="${A[campo] === k}">${t}</button>`).join('')}</div>`;
    return `<div class="ferramentas">${busca('tec-busca-i', 'tec-busca', 'Buscar pelo título ou número', A.tBusca)}</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin:6px 0 2px">${ch('tTipo', [['todos', 'Bug e Melhoria'], ['Bug', 'Bug'], ['Melhoria', 'Melhoria']])}${ch('tOrigem', [['todas', 'Toda origem'], ['Pedido do diretor', 'Pedido do diretor'], ['Vitta', 'Vitta'], ['Relato no app', 'Relato no app']])}${ch('tProjeto', [['todos', 'Os dois projetos'], ['Aplicativo do Hospital', 'Aplicativo'], ['Ana', 'Ana']])}</div>`;
  }
  function cabTec(atual) {
    const em = DEM.filter((d) => d.etapa === 'desenvolvimento').length, ent = DEM.filter((d) => d.etapa === 'entregue' && d.dias <= 30).length;
    return { cab: { sobre: 'Administração', titulo: 'Tecnologia', frase: `${em} Demandas em desenvolvimento e ${ent} entregues nos últimos 30 dias. Esta aba só mostra: o pedido nasce e anda no GitHub.` },
      resumo: [['Registradas e em análise', dd(DEM.filter((d) => ['registrada', 'analise'].includes(d.etapa)).length), I.relogio, '#tecnologia'], ['Planejadas', dd(DEM.filter((d) => d.etapa === 'planejada').length), I.agenda, '#tecnologia'], ['Em desenvolvimento', dd(em), I.alerta, '#tecnologia'], ['Entregues em 30 dias', dd(ent), I.certo, '#tecnologiaentregas']],
      abas: N.abasModulo([['#tecnologia', 'Quadro', DEM.filter((d) => d.etapa !== 'entregue').length], ['#tecnologiaentregas', 'Entregas', ent]], atual) };
  }
  const playBtn = (d, real) => d.demo ? `<${real ? 'button type="button"' : 'span role="button" tabindex="0"'} class="play" data-acao="tec-demo" data-n="${d.n}" title="Ver a Demonstração" aria-label="Ver a Demonstração">${N.ic('<path d="M8 5l11 7-11 7z"/>', 14)}</${real ? 'button' : 'span'}>` : '';
  T.tecnologia = { trilha: 'Tecnologia', menu: 'tecnologia', mapa: ['Administração', 'Tecnologia: Quadro'], render: soAdmin(() => {
    const c = cabTec('#tecnologia'); const lista = filtraDem();
    const corpo = `<section class="cartao bloco" style="margin-top:14px">${filtrosTec()}
      <div class="quadro" style="grid-auto-columns:minmax(188px,1fr)">${ETAPAS.map(([k, t]) => { const fs = lista.filter((d) => d.etapa === k).slice(0, k === 'entregue' ? 8 : 99);
        return `<div class="coluna"><h3><span>${t}</span><span class="num">${fs.length}</span></h3>
          ${fs.map((d) => `<button type="button" class="ficha-q" data-acao="tec-card" data-n="${d.n}"><small style="margin:0 0 4px">Demanda ${d.n}</small><b>${esc(d.t)}</b>
            ${d.partes ? `<span class="partes"><span class="prog"><span style="width:${d.partes[0] / d.partes[1] * 100}%"></span></span>${d.partes[0]} de ${d.partes[1]} partes</span>` : ''}
            <span class="rodape-f"><span style="display:flex;gap:6px;flex-wrap:wrap"><span class="pill ${d.tipo === 'Bug' ? 'verm' : ''}">${d.tipo}</span><span class="pill cinza">${d.proj === 'Ana' ? 'Ana' : 'Aplicativo'}</span></span>${playBtn(d)}</span>
            ${d.versao ? `<small>Em produção desde ${esc(d.versao)}</small>` : ''}</button>`).join('')}
          ${k === 'entregue' ? `<a class="link" style="font-size:13.5px;font-weight:700;margin:4px" href="#tecnologiaentregas">Ver todas nas Entregas ${IC.seta}</a>` : ''}
          ${fs.length || k === 'entregue' ? '' : '<p class="sub" style="margin:6px">Nada nesta etapa com esses filtros.</p>'}</div>`; }).join('')}</div></section>`;
    return N.modulo(c.cab, c.resumo, c.abas, corpo);
  }) };
  N.acoes['tec-demo'] = (a) => N.aviso(`No sistema, abre o vídeo da Demonstração da Demanda ${a.dataset.n}.`);
  N.acoes['tec-card'] = (a, ev) => {
    if (ev && ev.target.closest('[data-acao="tec-demo"]')) { N.acoes['tec-demo'](ev.target.closest('[data-acao="tec-demo"]')); return; }
    const d = DEM.find((x) => x.n === Number(a.dataset.n));
    const et = ETAPAS.find(([k]) => k === d.etapa)[1];
    const ondas = d.partes ? [['Onda 1', [['O aviso diário e o modelo da mensagem', true], ['O link direto para a Pendência', true]]], ['Onda 2', [['Desligar no perfil', d.partes[0] > 2], ['Quem já foi avisado, no Início', false, 'Espera a parte 3']]], ['Onda 3', [['Relatório de avisos enviados', false]]]].slice(0, Math.max(1, Math.ceil(d.partes[1] / 2))) : null;
    N.abrirGaveta({ sobre: `<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center"><span class="rot-mini">Demanda ${d.n}</span><span class="pill ${d.tipo === 'Bug' ? 'verm' : ''}">${d.tipo}</span><span class="pill escuro">${et}</span><span class="pill cinza">${esc(d.origem)}</span></div>`, titulo: esc(d.t),
      corpo: `<div><p class="rot-mini">Em uma frase</p><p style="margin:6px 0 0;font-size:16px">${d.tipo === 'Bug' ? 'Corrige o problema relatado para que a tela volte a funcionar como antes.' : 'Quem tem Pendência atrasada passa a ser lembrado sem ninguém precisar cobrar nos grupos.'}</p></div>
        <div><p class="rot-mini">O que muda</p><ul style="margin:6px 0 0;padding-left:20px;display:flex;flex-direction:column;gap:4px">${OQM.slice(0, d.tipo === 'Bug' ? 2 : 4).map((x) => `<li>${x}</li>`).join('')}</ul></div>
        ${ondas ? `<div><p class="rot-mini">Partes, por Onda</p><div class="grade" style="margin-top:8px">${ondas.map(([o, ps]) => `<div class="onda"><h4>${o}</h4><ul style="list-style:none;margin:0;padding:0">${ps.map(([t, ok, espera]) => `<li><span>${t}${espera ? ` <span class="sub">(${espera})</span>` : ''}</span>${N.estado(ok ? 'e-ok' : 'e-sem', ok ? 'Entregue' : 'A fazer')}</li>`).join('')}</ul></div>`).join('')}</div></div>` : ''}
        <div><p class="rot-mini">Datas</p><dl class="pares" style="margin-top:6px"><dt>Aberta</dt><dd class="num">${fmt(dia(-d.dias - 10))}</dd>${d.etapa === 'entregue' ? `<dt>Entregue</dt><dd class="num">${fmt(dia(-d.dias))}</dd><dt>Em produção</dt><dd>${esc(d.versao)}</dd>` : `<dt>Na etapa desde</dt><dd class="num">${fmt(dia(-d.dias))}</dd>`}<dt>Responsável</dt><dd>${d.resp === 'PR' ? 'Pedro Rezende' : 'Lucas Campos'}</dd></dl></div>
        <div class="grade g2" style="margin-top:0"><div class="cartao bloco" style="box-shadow:none"><p class="rot-mini">Demonstração</p><p class="sub" style="margin:6px 0 10px">${d.demo ? 'Vídeo curto do que mudou.' : 'Sai junto com a entrega.'}</p>${d.demo ? `<button class="btn" data-acao="tec-demo" data-n="${d.n}">${N.ic('<path d="M8 5l11 7-11 7z"/>', 14)}Ver a Demonstração</button>` : ''}</div>
          <div class="cartao bloco" style="box-shadow:none"><p class="rot-mini">Plano</p><p class="sub" style="margin:6px 0 10px">${d.plano ? 'Validado pelo diretor.' : 'Ainda sem plano para validar.'}</p>${d.plano ? `<button class="btn contorno" data-acao="toast" data-msg="No sistema, abre a página do plano em planos-hsm.">${I.certo.replace(/width="26" height="26"/, 'width="16" height="16"')}Ver o plano</button>` : ''}</div></div>`,
      pe: `<button class="btn contorno" data-acao="toast" data-msg="Link da Demanda ${d.n} copiado.">${IC.copiar}Copiar link</button><button class="btn" data-acao="fechar-gaveta">Fechar</button>` });
    const g = document.querySelector('.gaveta'); if (g) g.classList.add('larga');
  };

  T.tecnologiaentregas = { trilha: 'Tecnologia', menu: 'tecnologia', mapa: ['Administração', 'Tecnologia: Entregas'], render: soAdmin(() => {
    const c = cabTec('#tecnologiaentregas');
    const PED = [3, 5, 2, 4, 6, 3, 4, 5, 2, 6, 4, 3], ENT = [2, 3, 4, 2, 3, 5, 3, 4, 3, 4, 5, 3];
    const max = 7, w = 1100, h = 150, larg = w / 12;
    const graf = `<svg viewBox="0 0 ${w} ${h + 22}" style="width:100%;height:auto;display:block" role="img" aria-label="Pedidos e entregas nas últimas 12 semanas">${PED.map((p, i) => { const e = ENT[i]; const x = i * larg + 10; const sem = 11 - i; const on = A.semana === null || A.semana === sem;
      return `<g class="semana-bar" data-acao="tec-semana" data-v="${sem}" style="opacity:${on ? 1 : .35}"><rect x="${x}" y="${h - p / max * h}" width="${larg / 2 - 10}" height="${p / max * h}" rx="3" fill="var(--suave2)"/><rect x="${x + larg / 2 - 8}" y="${h - e / max * h}" width="${larg / 2 - 10}" height="${e / max * h}" rx="3" fill="var(--btn-fundo)"/><text x="${x + larg / 2 - 9}" y="${h + 16}" text-anchor="middle" font-size="11" fill="var(--texto2)">${curto(dia(-sem * 7 - ((HOJE.getDay() + 6) % 7)))}</text></g>`; }).join('')}</svg>`;
    const ents = filtraDem().filter((d) => d.etapa === 'entregue' && (A.semana === null || d.sem === A.semana));
    const semanas = [...new Set(ents.map((d) => d.sem))].sort((a, b) => a - b);
    const corpo = `<div class="grade g2"><section class="cartao bloco"><h2 class="titulo-bloco">Ritmo das últimas 4 semanas</h2>
        <div class="grade" style="margin-top:10px;grid-template-columns:1fr 1fr"><div><span class="rot-mini">Pedidos</span><p class="numero">17</p><p class="sub" style="margin:0">contra 14 nas 4 anteriores</p></div><div><span class="rot-mini">Entregas</span><p class="numero verde">15</p><p class="sub" style="margin:0">contra 12 nas 4 anteriores</p></div></div></section>
      <section class="cartao bloco"><h2 class="titulo-bloco">Tamanho do que saiu</h2>${[['G, grande', 4, 15], ['M, média', 6, 15], ['P, pequena', 5, 15]].map(([t, v, tot]) => `<div style="margin-top:12px"><div style="display:flex;justify-content:space-between;font-size:14px"><span>${t}</span><span class="num sub">${v}</span></div><div class="prog" style="margin-top:6px"><span style="width:${v / tot * 100}%"></span></div></div>`).join('')}</section></div>
      <section class="cartao bloco" style="margin-top:14px"><div class="cab"><h2 class="titulo-bloco">12 semanas</h2><div class="legenda" style="margin:0"><span><i style="background:var(--suave2)"></i>Pedidos</span><span><i style="background:var(--btn-fundo)"></i>Entregas</span>${A.semana !== null ? `<button class="btn contorno" data-acao="tec-semana" data-v="">Mostrar todas as semanas</button>` : '<span>Clique numa semana para filtrar a lista.</span>'}</div></div>${graf}</section>
      <section class="cartao bloco" style="margin-top:14px">${filtrosTec()}<h2 class="titulo-bloco" style="margin-top:10px">O que foi entregue</h2>
        ${semanas.map((s) => { const ds = ents.filter((d) => d.sem === s); return `<h3 class="rot-mini" style="margin:18px 0 4px">Semana de ${curto(dia(-s * 7 - ((HOJE.getDay() + 6) % 7)))}: ${ds.length} ${ds.length === 1 ? 'entrega' : 'entregas'}</h3>
          ${ds.map((d) => `<div class="entrega"><span class="tam" title="Tamanho">${d.tam}</span><span><button class="abre" data-acao="tec-oqm" data-n="${d.n}" aria-expanded="${A.oqm === d.n}">${esc(d.t)}</button><span class="sub" style="display:block">${d.tipo} · ${d.proj === 'Ana' ? 'Ana' : 'Aplicativo'} · ${esc(d.versao)}</span></span><span class="num sub">${fmt(dia(-d.dias))}</span>${playBtn(d, true) || '<span></span>'}
            ${A.oqm === d.n ? `<div class="oqm"><b style="color:var(--titulo)">O que muda</b><ul>${OQM.slice(0, d.tipo === 'Bug' ? 1 : 3).map((x) => `<li>${x}</li>`).join('')}</ul><div class="acoes-item">${d.demo ? `<button class="btn" data-acao="tec-demo" data-n="${d.n}">Ver a Demonstração</button>` : ''}<button class="btn contorno" data-acao="tec-card" data-n="${d.n}">Abrir o card</button><button class="btn contorno" data-acao="toast" data-msg="Link copiado.">${IC.copiar}Copiar link</button></div></div>` : ''}</div>`).join('')}`; }).join('')}
        ${ents.length ? `<div style="margin-top:14px"><button class="btn contorno" data-acao="toast" data-msg="No sistema, carrega as semanas anteriores.">Ver semanas anteriores</button></div>` : '<p class="vazio">Nada entregue nessa semana com esses filtros.</p>'}</section>`;
    return N.modulo(c.cab, c.resumo, c.abas, corpo);
  }), depois() {
    document.querySelectorAll('.semana-bar').forEach((g) => g.addEventListener('click', () => N.acoes['tec-semana'](g)));
  } };
  N.acoes['tec-semana'] = (a) => { A.semana = a.dataset.v === '' || A.semana === Number(a.dataset.v) ? null : Number(a.dataset.v); N.desenhar(); };
  N.acoes['tec-oqm'] = (a) => { A.oqm = A.oqm === Number(a.dataset.n) ? null : Number(a.dataset.n); N.desenhar(); };
})();
