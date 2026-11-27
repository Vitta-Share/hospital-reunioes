// Estado da validação da Apresentação do PRD (ADR 0108, decisão 1): a página chama esta
// função quando abre e mostra o cartão "Plano validado" para qualquer pessoa, em qualquer
// navegador. Só leitura, sem o código do link. Validado é a label validado:diretor no PRD;
// data, hora e observação vêm do último comentário com o marcador <!-- validacao-diretor -->.
// Sem a label, o plano não está validado, mesmo com comentário antigo: a validação vale só
// para a versão que o diretor viu.
const REPO = 'Vitta-Share/hospital-reunioes';
const LABEL = 'validado:diretor';
const MARCADOR = /<!-- validacao-diretor: (\S+) -->/;
const DE_DENTRO = ['OWNER', 'MEMBER', 'COLLABORATOR'];

function gh(caminho) {
  return fetch('https://api.github.com/repos/' + REPO + caminho, {
    headers: {
      Authorization: 'Bearer ' + process.env.GITHUB_TOKEN,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'apresentacao-prd',
    },
  });
}

// "Observação dele:" seguida das linhas citadas; "Sem observação." vira null.
function observacaoDe(corpo) {
  const m = corpo.match(/Observação dele:\r?\n\r?\n((?:> .*(?:\r?\n|$))+)/);
  if (!m) return null;
  return m[1].trimEnd().split(/\r?\n/).map((l) => l.slice(2)).join('\n');
}

module.exports = async (req, res) => {
  if (req.method !== 'GET') return res.status(405).json({ ok: false, erro: 'Só leitura.' });
  if (!process.env.GITHUB_TOKEN) return res.status(500).json({ ok: false, erro: 'A página ainda não está pronta.' });

  const prd = Number((req.query || {}).prd);
  if (!Number.isInteger(prd) || prd <= 0) return res.status(400).json({ ok: false, erro: 'Plano não encontrado.' });

  try {
    const ri = await gh('/issues/' + prd);
    if (!ri.ok) return res.status(ri.status === 404 ? 404 : 502).json({ ok: false, erro: 'Não deu para ler o plano.' });
    const issue = await ri.json();
    const nomes = (issue.labels || []).map((l) => (typeof l === 'string' ? l : l.name));
    if (!nomes.includes(LABEL)) return res.status(200).json({ ok: true, validado: false, data: null, hora: null, observacao: null });

    const rc = await gh('/issues/' + prd + '/comments?per_page=100');
    if (!rc.ok) return res.status(502).json({ ok: false, erro: 'Não deu para ler a validação.' });
    const validacoes = (await rc.json()).filter((c) => DE_DENTRO.includes(c.author_association) && MARCADOR.test(c.body || ''));
    const ultima = validacoes[validacoes.length - 1];
    if (!ultima) return res.status(200).json({ ok: true, validado: true, data: null, hora: null, observacao: null });

    const quando = new Date(ultima.body.match(MARCADOR)[1]);
    const fuso = { timeZone: 'America/Sao_Paulo' };
    return res.status(200).json({
      ok: true,
      validado: true,
      data: quando.toLocaleDateString('pt-BR', fuso),
      hora: quando.toLocaleTimeString('pt-BR', { ...fuso, hour: '2-digit', minute: '2-digit' }),
      observacao: observacaoDe(ultima.body),
    });
  } catch (e) {
    return res.status(502).json({ ok: false, erro: 'Não deu para ler o plano.' });
  }
};
