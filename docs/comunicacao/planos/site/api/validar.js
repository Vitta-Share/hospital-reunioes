// Botão Validar da Apresentação do PRD: confere o código do link e grava no PRD do GitHub
// a label validado:diretor e um comentário com a data e o resumo da observação do diretor.
// Com observação, abre antes o Ajuste do plano: uma sub-issue ready-for-human do Pedro que
// bloqueia as Fatias iniciais até ele rever o plano (CONTEXT.md do PedroOS).
// A observação nunca vai literal para o GitHub (ADR 0108, decisão 5): o texto vai ao app, que
// guarda o original junto da Demanda do PRD e devolve os tópicos interpretados.
const crypto = require('crypto');

const REPO = 'pedrorezendefig/hospital-reunioes';
const LABEL = 'validado:diretor';
const DONO = 'pedrorezendefig';
const APP = 'https://api.hospitalsaomatheus.cloud/api/automacao/tecnologia/validacoes';
const GUARDADA = 'Observação guardada fora do GitHub; leia no app.';
const RECEBIDA = 'Observação recebida; leia no e-mail de aviso.';

// Sem menção a ninguém pelo texto que vai ao GitHub: o @ ganha um espaço invisível.
const semMencao = (t) => t.replace(/@/g, '@​');

// Manda a observação ao app (chave APP_API_KEY). Devolve { guardada, topicos } e nunca lança:
// app fora do ar, erro ou variável faltando viram { guardada: false, topicos: [] }.
async function observacaoNoApp(prd, obs) {
  if (!process.env.APP_API_KEY) return { guardada: false, topicos: [] };
  try {
    const r = await fetch(APP, {
      method: 'POST',
      headers: { 'X-API-Key': process.env.APP_API_KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({ prd, observacao: obs }),
      signal: AbortSignal.timeout(25000),
    });
    if (!r.ok) return { guardada: false, topicos: [] };
    const j = await r.json();
    const topicos = (Array.isArray(j.topicos) ? j.topicos : [])
      .map((t) => semMencao(String(t).replace(/\s+/g, ' ').trim()))
      .filter(Boolean);
    return { guardada: j.guardada === true, topicos };
  } catch (e) {
    return { guardada: false, topicos: [] };
  }
}

// A citação do comentário (o formato que o aviso do PedroOS e a página leem): um tópico por linha.
function citacao(resumo) {
  const linhas = resumo.topicos.length ? resumo.topicos : [resumo.guardada ? GUARDADA : RECEBIDA];
  return linhas.map((l) => '> ' + l).join('\n');
}

function codigoDe(prd) {
  return crypto.createHmac('sha256', process.env.SEGREDO).update(String(prd)).digest('hex').slice(0, 20);
}

function gh(caminho, metodo, corpo) {
  return fetch('https://api.github.com/repos/' + REPO + caminho, {
    method: metodo,
    headers: {
      Authorization: 'Bearer ' + process.env.GITHUB_TOKEN,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'apresentacao-prd',
      'Content-Type': 'application/json',
    },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
}

// Fatias iniciais: abertas, prontas para agente, sem trabalho começado e sem bloqueio aberto.
async function fatiasIniciais(prd) {
  const r = await gh('/issues/' + prd + '/sub_issues?per_page=100', 'GET');
  if (!r.ok) throw new Error('sub_issues ' + r.status);
  const nomes = (i) => (i.labels || []).map((l) => (typeof l === 'string' ? l : l.name));
  const abertas = (await r.json()).filter((i) => i.state === 'open' && nomes(i).includes('ready-for-agent'));
  const emAndamento = abertas.filter((i) => nomes(i).includes('in-progress')).map((i) => i.number);
  const livres = abertas.filter((i) => !nomes(i).includes('in-progress'));
  const presas = await Promise.all(livres.map(async (i) => {
    const b = await gh('/issues/' + i.number + '/dependencies/blocked_by', 'GET');
    if (!b.ok) throw new Error('blocked_by ' + b.status);
    return (await b.json()).some((x) => x.state === 'open');
  }));
  return { iniciais: livres.filter((_, k) => !presas[k]).map((i) => i.number), emAndamento };
}

// O corpo leva só os tópicos que o app interpretou; sem eles, o aviso de onde ler a observação.
function corpoDoAjuste(prd, resumo, iniciais, emAndamento, data, hora) {
  const lista = (ns) => ns.map((n) => '- #' + n).join('\n');
  const observacao = resumo.topicos.length
    ? '## O que o diretor quer mudar\n\n' + resumo.topicos.map((t) => '- ' + t).join('\n') + '\n\n'
    : '## Observação do diretor\n\n' + (resumo.guardada ? GUARDADA : RECEBIDA) + '\n\n';
  return (
    '<!-- ajuste-do-plano: ' + prd + ' -->\n' +
    '## O que é este card\n\n' +
    'O diretor validou o plano deste PRD pela Apresentação em ' + data + ', às ' + hora + ', e escreveu uma observação. ' +
    'Antes de o trabalho começar, o Pedro lê a observação e decide se o plano ou o conteúdo de algum card muda. ' +
    'Enquanto este card estiver aberto, as fatias iniciais ficam bloqueadas.\n\n' +
    observacao +
    '## Fatias bloqueadas por este card\n\n' + (iniciais.length ? lista(iniciais) : 'Nenhuma: o PRD não tinha fatia livre.') + '\n\n' +
    (emAndamento.length ? '## Já em andamento (não param)\n\nConfira se a observação muda alguma destas:\n\n' + lista(emAndamento) + '\n\n' : '') +
    '## Passo a passo\n\n' +
    '1. Abra o Claude Code na pasta do Hospital e rode `/grill-with-docs` com o número deste card.\n' +
    '2. Decida com o agente se a observação muda o plano ou o conteúdo de algum card.\n' +
    '3. Se algum card muda, o agente reescreve o corpo dele.\n' +
    '4. Se a mudança altera alguma Parte que o diretor vê na Apresentação, rode `/apresentar-prd ' + prd + '` e mande o link de novo para ele validar.\n' +
    '5. Feche este card com um comentário de uma linha: o que mudou, ou por que não precisou mudar.\n\n' +
    '## Como saber que acabou\n\n' +
    '- Este card está fechado com o comentário do passo 5.\n' +
    '- As fatias bloqueadas voltam para a fila (`gh issue list --label ready-for-agent --search "-is:blocked"`).\n' +
    '- Se a Apresentação foi publicada de novo, o PRD perdeu o selo `validado:diretor` e espera a nova validação.'
  );
}

async function abrirAjuste(prd, resumo, data, hora) {
  const { iniciais, emAndamento } = await fatiasIniciais(prd);
  const rc = await gh('/issues', 'POST', {
    title: 'Ajuste do plano: observação do diretor no PRD #' + prd,
    body: corpoDoAjuste(prd, resumo, iniciais, emAndamento, data, hora),
    labels: ['ready-for-human'],
    assignees: [DONO],
  });
  if (!rc.ok) throw new Error('issue ' + rc.status);
  const card = await rc.json();
  await gh('/issues/' + prd + '/sub_issues', 'POST', { sub_issue_id: card.id });
  await Promise.all(iniciais.map((n) => gh('/issues/' + n + '/dependencies/blocked_by', 'POST', { issue_id: card.id })));
  return card.number;
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ ok: false, erro: 'Use o botão da página.' });
  if (!process.env.SEGREDO || !process.env.GITHUB_TOKEN) return res.status(500).json({ ok: false, erro: 'A página ainda não está pronta para validar.' });

  const corpo = req.body || {};
  const prd = parseInt(corpo.prd, 10);
  if (!Number.isInteger(prd) || prd <= 0) return res.status(400).json({ ok: false, erro: 'Plano não encontrado.' });

  const c = typeof corpo.c === 'string' ? corpo.c : '';
  const esperado = codigoDe(prd);
  if (c.length !== esperado.length || !crypto.timingSafeEqual(Buffer.from(c), Buffer.from(esperado))) {
    return res.status(403).json({ ok: false, erro: 'Este link não vale para validar.' });
  }

  // Modo teste: só confere que a chave do GitHub lê o PRD, sem gravar nada.
  if (corpo.teste) {
    const r = await gh('/issues/' + prd, 'GET');
    return res.status(r.ok ? 200 : 502).json({ ok: r.ok, teste: true, status: r.status });
  }

  const agora = new Date();
  const fuso = { timeZone: 'America/Sao_Paulo' };
  const data = agora.toLocaleDateString('pt-BR', fuso);
  const hora = agora.toLocaleTimeString('pt-BR', { ...fuso, hour: '2-digit', minute: '2-digit' });

  // O texto do diretor só vai ao app; o GitHub recebe o resumo dele.
  const obs = String(corpo.observacao || '').slice(0, 2000).trim();
  const rl = await gh('/issues/' + prd + '/labels', 'POST', { labels: [LABEL] });
  if (!rl.ok) return res.status(502).json({ ok: false, erro: 'Não deu para gravar a validação.' });

  // O app falhar não desfaz a validação: o resumo diz onde ler a observação.
  const resumo = obs ? await observacaoNoApp(prd, obs) : null;

  // O Ajuste falhar não desfaz a validação: o comentário avisa para abrir à mão.
  let ajuste = '';
  if (resumo) {
    try {
      ajuste = '\n\nAbri o Ajuste do plano #' + (await abrirAjuste(prd, resumo, data, hora)) + ', que segura as fatias iniciais até a observação ser revista.';
    } catch (e) {
      ajuste = '\n\nNão deu para abrir o Ajuste do plano (' + e.message + '): abra o Ajuste do plano à mão.';
    }
  }

  const texto =
    '<!-- validacao-diretor: ' + agora.toISOString() + ' -->\n' +
    'O diretor validou este plano pela Apresentação do PRD em ' + data + ', às ' + hora + '.\n\n' +
    (resumo ? 'Observação dele:\n\n' + citacao(resumo) : 'Sem observação.') + ajuste;
  const rc = await gh('/issues/' + prd + '/comments', 'POST', { body: texto });
  if (!rc.ok) return res.status(502).json({ ok: false, erro: 'A validação entrou, mas a observação não.' });

  return res.status(200).json({ ok: true, data, hora });
};
