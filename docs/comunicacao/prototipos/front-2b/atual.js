/* Modelo Atual: o Início como ele é hoje no hospital-reunioes.
   Reproduz components/inicio/MinhaFila.tsx, Trilho.tsx, MeusNumeros.tsx e
   QuemRespondeAVoce.tsx, com o menu de components/layout/Sidebar.tsx.
   Recebe os dados e as funções de datas do app.js (window.NOVIDADES). */
(function () {
  'use strict';
  const N = window.NOVIDADES;
  const { itens, reunioes, pessoas, est, dia, deIso, difDias, curto, longo, esc, ext, cap } = N;
  const SEM = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];

  // Os grupos do servidor (services/inicio/regras.py): vencido, até 48 horas, próximos 7 dias e sem prazo.
  const grupoAt = (i) => i.off === null ? 'sem_prazo' : i.off < 0 ? 'passou_do_prazo' : i.off <= 2 ? 'ate_48_horas' : i.off <= 7 ? 'proximos_7_dias' : null;
  const GRUPOS = [['passou_do_prazo', 'Passou do prazo'], ['ate_48_horas', 'Vence em até 48 horas'], ['proximos_7_dias', 'Próximos 7 dias'], ['sem_prazo', 'Sem prazo']];
  // O texto da ação de cada fonte (services/inicio/fonte_*.py).
  const ACAO = { pendencia: 'Abrir a Pendência', ata: 'Assinar a Ata', contestacao: 'Ajustar ou recusar', ouvidoria: 'Responder', pop: 'Revisar' };
  const UM_CLIQUE = { rotina: ['Realizada', 'Não realizada'], capacitacao: ['Confirmar presença', null] };
  const ESPERANDO = { p9: 4 };
  const CONTEXTO = { p1: 'Última Anotação, em ' + curto(dia(-14)) + ': aguardando o retorno do RH.', p3: 'O Paulo pede mais 15 dias porque o fornecedor atrasou os aventais.' };

  function quando(i) {
    const g = grupoAt(i);
    if (g === 'passou_do_prazo') { const n = -i.off; return `<div class="at-q venc"><b>${n}</b><span>${n === 1 ? 'dia de atraso' : 'dias de atraso'}</span></div>`; }
    if (g === 'sem_prazo') { const n = ESPERANDO[i.id] || 1; return `<div class="at-q"><b>${n}</b><span>${n === 1 ? 'dia esperando' : 'dias esperando'}</span></div>`; }
    const d = dia(i.off);
    return `<div class="at-q data"><b>${i.off === 0 ? 'Hoje' : SEM[d.getDay()]}</b><span>${curto(d)}</span></div>`;
  }

  function linha(i, entrada) {
    const venc = grupoAt(i) === 'passou_do_prazo';
    const clique = UM_CLIQUE[i.tipo];
    const rot = i.tipo === 'pop' && i.titulo.startsWith('Validar') ? 'Validar' : ACAO[i.tipo];
    const cls = 'at-btn' + (venc ? ' cheio' : '');
    return `<li class="at-linha${entrada !== null ? ' entra' : ''}"${entrada !== null ? ` style="animation-delay:${entrada * 70}ms"` : ''}>
      ${quando(i)}
      <div style="min-width:0"><p class="at-t">${esc(i.titulo)}</p><p class="at-o">${esc(i.origem)}</p>${CONTEXTO[i.id] ? `<p class="at-ctx">${esc(CONTEXTO[i.id])}</p>` : ''}</div>
      <div class="at-acoes">
        <span class="at-etq">${i.area === 'NSP' ? 'Segurança do Paciente' : i.area === 'Reunião' || i.area === 'Rotina' ? 'Reuniões' : i.area === 'POP' ? 'POPs' : i.area}</span>
        ${clique ? `<button type="button" class="${cls}" data-concluir="${i.id}" data-ficar="1" data-msg="${clique[0] === 'Realizada' ? 'Verificação marcada como Realizada.' : 'Presença confirmada.'}">${clique[0]}</button>` : `<a class="${cls}" href="#item-${i.id}" aria-label="${rot}: ${esc(i.titulo)}">${rot}</a>`}
        ${clique && clique[1] ? `<a class="at-sec" href="#item-${i.id}" aria-label="${clique[1]}: ${esc(i.titulo)}">${clique[1]}</a>` : ''}
      </div>
    </li>`;
  }

  function frase(lista) {
    const v = lista.filter((i) => grupoAt(i) === 'passou_do_prazo');
    const q = lista.filter((i) => grupoAt(i) === 'ate_48_horas').length;
    const nome = N.EU.primeiro;
    if (v.length) {
      const max = Math.max(...v.map((i) => -i.off));
      let apoio = v.length === 1 ? `Ele espera há ${max} ${max === 1 ? 'dia' : 'dias'}.` : `O mais antigo espera há ${max} dias.`;
      if (q === 1) apoio += ' Mais um vence em até 48 horas.'; else if (q > 1) apoio += ` Mais ${ext(q)} vencem em até 48 horas.`;
      return [v.length === 1 ? `${nome}, um prazo seu venceu.` : `${nome}, ${ext(v.length)} prazos seus venceram.`, apoio];
    }
    if (q) return [`${nome}, nada atrasado.`, q === 1 ? 'Um prazo vence em até 48 horas.' : `${cap(ext(q))} prazos vencem em até 48 horas.`];
    const prox = lista.filter((i) => i.off !== null).sort((a, b) => a.off - b.off)[0];
    return [`${nome}, você está em dia.`, prox ? `O próximo prazo é ${curto(dia(prox.off))}.` : 'Nenhum prazo aberto no seu nome.'];
  }

  function quandoReuniao(r) {
    const d = deIso(r.data);
    const s = `${difDias(d) === 0 ? 'Hoje' : SEM[d.getDay()]}, ${curto(d)}`;
    return r.hora ? `${s}, ${r.hora}` : s;
  }

  N.pInicioAtual = function () {
    const lista = itens.filter((i) => !est.feitos[i.id] && grupoAt(i) !== null);
    const conta = (g) => lista.filter((i) => grupoAt(i) === g).length;
    const venc = conta('passou_do_prazo');
    const [tit, apoio] = frase(lista);
    const emDia = venc === 0 && conta('ate_48_horas') === 0;
    const proximas = reunioes.filter((r) => difDias(deIso(r.data)) >= 0).sort((a, b) => (a.data + a.hora).localeCompare(b.data + b.hora)).slice(0, 5);
    const rotinas = itens.filter((i) => i.area === 'Rotina' && i.off !== null && i.off <= 7);
    const marcadas = rotinas.filter((r) => est.feitos[r.id]).length;
    const cont = [
      ['passou_do_prazo', venc, venc === 1 ? 'prazo vencido' : 'prazos vencidos'],
      ['ate_48_horas', conta('ate_48_horas'), conta('ate_48_horas') === 1 ? 'vence em até 48 horas' : 'vencem em até 48 horas'],
      ['proximos_7_dias', conta('proximos_7_dias'), 'nos próximos 7 dias']
    ];
    const grupos = GRUPOS.map(([k, t]) => [k, t, lista.filter((i) => grupoAt(i) === k).sort((a, b) => (a.off ?? 999) - (b.off ?? 999))]).filter((g) => g[2].length);
    const entregues = [{ t: 'Relatório de eventos adversos de outubro', d: dia(-3), np: true }, { t: 'Ata da Reunião de Qualidade assinada', d: dia(-6), np: true }];

    return `<div class="at-pagina"><div class="at-wrap">
      <div class="at-card">
        <section class="at-abertura${venc ? ' escura' : ''}">
          <div class="at-top"><h1>Início</h1><span>${longo(N.HOJE).toLowerCase()}</span></div>
          <div aria-live="polite"><p class="at-frase">${tit}</p><p class="at-apoio">${apoio}</p></div>
          <ul class="at-cont" aria-label="Resumo dos prazos">${cont.map(([k, n, r]) => `<li style="display:flex">${n > 0 ? `<a href="#grupo-${k}" data-ancora="grupo-${k}"><b>${n}</b>${r}</a>` : `<span class="cx"><b>${n}</b>${r}</span>`}</li>`).join('')}</ul>
        </section>
        <div class="at-corpo">
          <div class="at-col">
            ${grupos.length === 0 ? '<p style="margin:0">Nada vencido e nada para os próximos 7 dias.</p>' : grupos.map(([k, t, its]) => `<section class="at-grupo" id="grupo-${k}" aria-label="${t}">
              <h2 class="${k === 'passou_do_prazo' ? 'venc' : ''}">${t}<span style="font-variant-numeric:tabular-nums">${its.length}</span></h2>
              <ul class="at-lista">${its.map((i, n) => linha(i, k === 'passou_do_prazo' && !est.jaEntrou ? n : null)).join('')}</ul>
            </section>`).join('')}
            <p class="at-reg">O dia em que você abre o Início fica registrado.</p>
          </div>
          <div class="at-col at-trilho">
            <aside aria-label="Próximas Reuniões">
              <p class="at-rot"><span class="etq-at">Próximas Reuniões</span></p>
              ${proximas.length ? `<ul>${proximas.map((r) => `<li><a href="#reuniao-${r.id}"><small>${quandoReuniao(r)}</small><span class="tt">${esc(r.titulo)}</span><small style="margin-top:2px">${r.papel === 'facilitador' ? 'Você conduz' : 'Você participa'}</small></a></li>`).join('')}</ul>` : '<p style="padding:14px 0;font-size:14.9px;color:#64748B;margin:0">Nenhuma Reunião marcada.</p>'}
            </aside>
            ${rotinas.length ? `<aside aria-label="Rotinas do ciclo">
              <p class="at-rot"><span class="etq-at">Rotinas do ciclo</span><span style="font-variant-numeric:tabular-nums">${marcadas} de ${rotinas.length} ${rotinas.length === 1 ? 'marcada' : 'marcadas'}</span></p>
              <ul>${rotinas.map((r) => `<li><a href="#rotinas"><span class="tt" style="margin:0">${esc(r.titulo)}</span><small style="margin-top:2px">Até ${curto(dia(r.off))}, ${est.feitos[r.id] ? 'Realizada' : 'falta marcar'}</small></a></li>`).join('')}</ul>
            </aside>` : ''}
          </div>
        </div>
      </div>

      <section class="at-card at-bloco" aria-label="Seus últimos 90 dias">
        <h2>Seus últimos 90 dias</h2>
        <div class="at-nums"><p><b>41</b><span>entregas no prazo</span></p><p><b>6</b><span>entregas fora do prazo</span></p></div>
        ${emDia ? `<h3 style="margin:25px 0 0;padding-bottom:8px;border-bottom:1px solid #E2E8F0;font-size:12.75px;font-weight:400;color:#64748B;text-transform:uppercase;letter-spacing:.02em">Entregue nos últimos 7 dias</h3><ul class="at-venc-lista">${entregues.map((e) => `<li style="display:block"><p style="margin:0;font-size:17px">${e.t}</p><p style="margin:2px 0 0;font-size:12.75px;color:#64748B">Entregue em ${curto(e.d)}, ${e.np ? 'no prazo' : 'fora do prazo'}</p></li>`).join('')}</ul>` : ''}
      </section>

      <section class="at-card at-bloco" aria-label="Quem responde a você">
        <h2>Quem responde a você</h2>
        <div class="at-rola"><table class="at-tab">
          <thead><tr><th>Pessoa</th><th class="d">Vencidos agora</th><th class="d">Em aberto</th><th>Entregas em 90 dias</th><th>Último acesso</th></tr></thead>
          <tbody>${pessoas.map((p) => `<tr class="pes" tabindex="0" aria-expanded="${est.pessoaAberta === p.id}" data-pessoa-at="${p.id}">
              <td><p class="nome">${p.nome}</p><p class="cargo">${p.cargo}</p></td>
              <td class="d big" style="color:${p.vencidos.length ? '#B91C1C' : '#1E293B'}">${p.vencidos.length}</td>
              <td class="d big">${p.abertos}</td>
              <td class="sm">${p.np} no prazo, ${p.fp} fora</td>
              <td class="sm" style="color:#64748B">${p.acesso}</td>
            </tr>${est.pessoaAberta === p.id ? `<tr class="abre"><td colspan="5">${p.vencidos.length ? `<ul class="at-venc-lista" aria-label="O que venceu e não foi entregue por ${p.nome}">${p.vencidos.map(([t, n]) => `<li><span style="font-size:14.9px">${t}</span><span style="font-size:12.75px;color:#B91C1C;white-space:nowrap">${n === 1 ? 'há 1 dia' : `há ${n} dias`}</span></li>`).join('')}</ul>` : '<p style="margin:8px 0 0;font-size:14.9px;color:#64748B">Nada vencido e não entregue.</p>'}</td></tr>` : ''}`).join('')}
          </tbody>
        </table></div>
      </section>
    </div></div>`;
  };

})();
