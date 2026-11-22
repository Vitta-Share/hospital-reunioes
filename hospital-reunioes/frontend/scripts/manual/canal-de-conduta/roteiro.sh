#!/usr/bin/env bash
# Refaz os prints da página do Canal de Conduta do manual (issue #1851, PRD
# #1786) pelo playwright-cli, contra o app LOCAL e com o seed fictício.
#
# Uso (da pasta hospital-reunioes/frontend, com o app local no ar):
#   bash scripts/manual/canal-de-conduta/roteiro.sh
#   BASE=http://localhost:3011 bash scripts/manual/canal-de-conduta/roteiro.sh
#
# O portão do Comitê roda no servidor do Next e pergunta ao backend local se a
# pessoa está no Comitê: o backend precisa estar no ar com uma chave de cifra
# do Canal (CONDUTA_CHAVE_CIFRA, qualquer chave de teste de 32 bytes em
# base64). O roteiro semeia a coordenação de exemplo (semear.py), entra como
# ela e responde no lugar do backend em toda rota do Comitê com a tabela do
# respostas.py, em que os relatos são os casos fictícios do Anexo B. Rota do
# Comitê fora da tabela recebe 404, e pedido que grava (confirmar, votar,
# enviar) recebe 403: nenhum caso muda, nenhum e-mail sai e nada vai à
# ClickSign. Nenhum botão de confirmar é clicado: preencher o formulário basta
# para o print.

set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$(cd "$AQUI/../../.." && pwd)"
SAIDA="$FRONTEND/public/manual/canal-de-conduta"
BASE="${BASE:-http://localhost:3000}"
SESSAO="manual-canal-de-conduta-1851"
COMITE="$BASE/comite-de-conduta"

case "$BASE" in
  http://localhost:*|http://127.0.0.1:*) ;;
  *) echo "recusado: '$BASE' não é o app local." >&2; exit 1 ;;
esac

SEED="$AQUI/seed.json"
seed() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(eval('d'+sys.argv[2]))" "$SEED" "$1"; }

pw() {
  local saida
  if ! saida="$(playwright-cli -s="$SESSAO" "$@" 2>&1)" || grep -q "^### Error" <<<"$saida"; then
    echo "falhou: playwright-cli $*" >&2
    echo "$saida" | sed -n '/### Error/,/###/p' >&2
    return 1
  fi
}

# Espera um texto aparecer e a tela assentar. O selo do Next, que só existe
# com o app rodando em modo de desenvolvimento, sai do print.
esperar() {
  pw run-code "async page => { await page.getByText('$1', { exact: true }).first().waitFor(); await page.addStyleTag({ content: 'nextjs-portal { display: none !important }' }); await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(1200) }"
}

clicar() { pw run-code "async page => { await page.$1.click(); await page.waitForTimeout(500) }"; }

abrir_caso() {
  pw goto "$COMITE/casos/$(seed "['casos']['$1']['id']")"
  esperar "$(seed "['casos']['$1']['protocolo']")"
}

# Fotografa um pedaço da tela (um localizador do Playwright, a partir de
# `page.`) e salva o PNG ao lado do Markdown.
print() {
  pw run-code "async page => { const alvo = page.$1; await page.evaluate(() => document.activeElement?.blur()); await alvo.scrollIntoViewIfNeeded(); await page.waitForTimeout(400); await alvo.screenshot({ path: '$SAIDA/$2' }) }"
  echo "  $2"
}

# Uma faixa da tela: do alto do primeiro localizador ao pé do segundo, na
# largura do primeiro.
print_faixa() {
  pw run-code "async page => {
    await page.evaluate(() => document.activeElement?.blur());
    const de = page.$1;
    const ate = page.$2;
    await de.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    const sobe = await page.evaluate(() => window.scrollY);
    const [a, b] = [await de.boundingBox(), await ate.boundingBox()];
    await page.screenshot({ path: '$SAIDA/$3', fullPage: true, clip: { x: a.x - 8, y: a.y + sobe - 8, width: a.width + 16, height: b.y + b.height - a.y + 16 } });
  }"
  echo "  $3"
}

python3 "$AQUI/semear.py"
mkdir -p "$SAIDA"

pw open "$BASE/login"
pw resize 1440 1100
pw fill "#email" "$(seed "['coordenacao']['email']")"
pw fill "#password" "$(seed "['coordenacao']['senha']")" --submit
pw run-code "async page => { await page.waitForURL(u => !u.pathname.startsWith('/login')) }"

# Toda rota do Comitê responde pela tabela, no lugar do backend. O GET fora
# da tabela recebe 404; o que grava, 403.
pw run-code "async page => {
  const tabela = $(python3 "$AQUI/respostas.py");
  await page.route(u => u.pathname.startsWith('/api/comite-de-conduta/'), route => {
    const pedido = route.request();
    const chave = decodeURIComponent(new URL(pedido.url()).pathname.replace(/^\/api\//, ''));
    if (pedido.method() !== 'GET') {
      return route.fulfill({ status: 403, json: { detail: 'O roteiro do manual não grava nada.' } });
    }
    if (!(chave in tabela)) {
      return route.fulfill({ status: 404, json: { detail: 'Sem resposta de exemplo para ' + chave } });
    }
    return route.fulfill({ json: tabela[chave] });
  });
}"

echo "prints em $SAIDA:"

# Confirmar a triagem: Minha vez e o formulário da triagem preenchido.
pw goto "$COMITE"
esperar "$(seed "['casos']['triagem']['protocolo']")"
print "getByRole('list', { name: 'O que depende de você' })" "minha-vez.png"
abrir_caso triagem
clicar "getByRole('region', { name: 'O que fazer agora' }).getByRole('button', { name: 'CONFIRMAR TRIAGEM' })"
TRIAGEM="getByRole('form', { name: 'Confirmar a triagem' })"
pw run-code "async page => {
  const triagem = page.$TRIAGEM;
  await triagem.getByRole('radio', { name: '$(seed "['triagem']['escopo']")' }).check();
  await triagem.getByLabel('Categoria').selectOption({ label: '$(seed "['triagem']['categoria']")' });
  await triagem.getByLabel('Rito').selectOption({ label: '$(seed "['triagem']['rito']")' });
}"
print_faixa "getByRole('region', { name: 'O que fazer agora' })" "$TRIAGEM" "confirmar-triagem.png"

# Registrar um depoimento: a pessoa a ouvir e o cartão com os arquivos.
abrir_caso apuracao
clicar "getByRole('region', { name: 'O que fazer agora' }).getByRole('button', { name: 'ADICIONAR PESSOA A OUVIR' })"
NOVA="getByRole('form', { name: 'Adicionar pessoa a ouvir' })"
pw run-code "async page => {
  const nova = page.$NOVA;
  await nova.getByLabel('Nome').fill('$(seed "['nova_pessoa']['nome']")');
  await nova.getByLabel('Cargo').fill('$(seed "['nova_pessoa']['cargo']")');
  await nova.getByRole('radio', { name: '$(seed "['nova_pessoa']['papel']")' }).check();
}"
print "$NOVA" "adicionar-pessoa.png"
CARTAO="getByRole('article', { name: '$(seed "['depoente']['nome']")' })"
print_faixa "$CARTAO" "$CARTAO.getByRole('region', { name: 'Áudio', exact: true })" "cartao-do-depoimento.png"

# Arquivar o papel: o termo assinado anexado e o envelope por marcar.
print_faixa "$CARTAO.getByRole('region', { name: 'Termo assinado', exact: true })" "$CARTAO.getByRole('region', { name: 'Lista de conferência' })" "termo-e-envelope.png"

# Votar: o formulário do voto preenchido.
abrir_caso voto
clicar "getByRole('region', { name: 'O que fazer agora' }).getByRole('button', { name: 'VOTAR' })"
VOTO="getByRole('form', { name: 'Seu voto' })"
pw run-code "async page => {
  const voto = page.$VOTO;
  await voto.getByRole('radio', { name: '$(seed "['voto']['resultado']")', exact: true }).check();
  await voto.getByLabel('Medida da Matriz').selectOption({ label: '$(seed "['voto']['medida']")' });
  await voto.getByLabel('Justificativa, em até três linhas').fill('$(seed "['voto']['justificativa']")');
}"
print "getByRole('region', { name: 'Voto', exact: true })" "votar.png"

# Assinar a ata: a ata gerada, esperando a assinatura dos três.
abrir_caso ata
print "getByRole('region', { name: 'Ata de deliberação' })" "ata-de-deliberacao.png"

# Enviar à Direção: o alto do caso com a caixa O QUE FAZER AGORA.
abrir_caso direcao
print_faixa "getByRole('heading', { name: '$(seed "['casos']['direcao']['protocolo']")', level: 1 })" "getByRole('region', { name: 'O que fazer agora' })" "enviar-a-direcao.png"

pw close
