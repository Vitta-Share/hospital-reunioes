// Botão Validar da Apresentação do PRD: confere o código do link e grava no PRD do GitHub
// a label validado:diretor e um comentário com a data e a observação do diretor.
const crypto = require('crypto');

const REPO = 'pedrorezendefig/hospital-reunioes';
const LABEL = 'validado:diretor';

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

  // Sem menção a ninguém pelo texto livre: o @ ganha um espaço invisível.
  const obs = String(corpo.observacao || '').slice(0, 2000).trim().replace(/@/g, '@​');
  const texto =
    '<!-- validacao-diretor: ' + agora.toISOString() + ' -->\n' +
    'O diretor validou este plano pela Apresentação do PRD em ' + data + ', às ' + hora + '.\n\n' +
    (obs ? 'Observação dele:\n\n> ' + obs.replace(/\r?\n/g, '\n> ') : 'Sem observação.');

  const rl = await gh('/issues/' + prd + '/labels', 'POST', { labels: [LABEL] });
  if (!rl.ok) return res.status(502).json({ ok: false, erro: 'Não deu para gravar a validação.' });
  const rc = await gh('/issues/' + prd + '/comments', 'POST', { body: texto });
  if (!rc.ok) return res.status(502).json({ ok: false, erro: 'A validação entrou, mas a observação não.' });

  return res.status(200).json({ ok: true, data, hora });
};
