#!/usr/bin/env bash
# Refaz os prints da página de Segurança do Paciente do manual (issue #1780,
# PRD #1764) pelo playwright-cli, contra o app LOCAL e com o seed fictício.
#
# Uso (da pasta hospital-reunioes/frontend, com o app local no ar):
#   bash scripts/manual/seguranca-do-paciente/roteiro.sh
#   BASE=http://localhost:3027 bash scripts/manual/seguranca-do-paciente/roteiro.sh
#
# O roteiro semeia a Presidência de exemplo (semear.py), entra como ela e
# responde no lugar do backend em toda rota do módulo com a tabela do
# respostas.py. Rota do módulo fora da tabela recebe 404, e pedido que grava
# (cadastrar, publicar, validar, convocar) recebe 403: nenhum e-mail sai,
# nenhum envelope vai para assinatura, nenhuma ata chega à IA e nenhum dado
# de verdade entra no print.

set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$(cd "$AQUI/../../.." && pwd)"
SAIDA="$FRONTEND/public/manual/seguranca-do-paciente"
BASE="${BASE:-http://localhost:3000}"
SESSAO="manual-seguranca-do-paciente-1780"
MODULO="$BASE/seguranca-do-paciente"

case "$BASE" in
  http://localhost:*|http://127.0.0.1:*) ;;
  *) echo "recusado: '$BASE' não é o app local." >&2; exit 1 ;;
esac

SEED="$AQUI/seed.json"
seed() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(eval('d'+sys.argv[2]))" "$SEED" "$1"; }
ROTEIRO="$(python3 "$AQUI/respostas.py" --roteiro)"
roteiro() { python3 -c "import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]])" "$ROTEIRO" "$1"; }

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

# Fotografa a tela, a página inteira ou um pedaço dela (um localizador do
# Playwright, a partir de `page.`), e salva o PNG ao lado do Markdown.
print_tela() { pw screenshot --filename="$SAIDA/$1"; echo "  $1"; }
print_pagina() { pw screenshot --full-page --filename="$SAIDA/$1"; echo "  $1"; }
print() {
  pw run-code "async page => { const alvo = page.$1; await page.evaluate(() => document.activeElement?.blur()); await alvo.scrollIntoViewIfNeeded(); await page.waitForTimeout(400); await alvo.screenshot({ path: '$SAIDA/$2' }) }"
  echo "  $2"
}

# A ficha de um membro abre dentro da tabela, que rola de lado: o print é a
# linha dele com a ficha embaixo, cortado na largura do cartão da tabela.
print_ficha() {
  pw run-code "async page => {
    await page.evaluate(() => document.activeElement?.blur());
    const linha = page.getByRole('row').filter({ has: page.getByRole('button', { name: '$1', exact: true }) });
    const ficha = page.getByRole('region', { name: 'Detalhes de $1' });
    const cartao = page.locator('div').filter({ has: page.getByRole('table', { name: 'Membros do Núcleo' }) }).last();
    await linha.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    const [l, f, c] = [await linha.boundingBox(), await ficha.boundingBox(), await cartao.boundingBox()];
    const sobe = await page.evaluate(() => window.scrollY);
    await page.screenshot({ path: '$SAIDA/$2', fullPage: true, clip: { x: c.x, y: l.y + sobe, width: c.width, height: f.y + f.height - l.y + 12 } });
  }"
  echo "  $2"
}

# Só o alto de um pedaço da tela, até a altura dada em pixels.
print_topo() {
  pw run-code "async page => { await page.evaluate(() => document.activeElement?.blur()); const alvo = page.$1; await alvo.scrollIntoViewIfNeeded(); await page.waitForTimeout(400); const b = await alvo.boundingBox(); const sobe = await page.evaluate(() => window.scrollY); await page.screenshot({ path: '$SAIDA/$3', fullPage: true, clip: { x: b.x, y: b.y + sobe, width: b.width, height: Math.min($2, b.height) } }) }"
  echo "  $3"
}

python3 "$AQUI/semear.py"
mkdir -p "$SAIDA"

pw open "$BASE/login"
pw resize 1440 900
pw fill "#email" "$(seed "['presidencia']['email']")"
pw fill "#password" "$(seed "['presidencia']['senha']")" --submit
pw run-code "async page => { await page.waitForURL(u => !u.pathname.startsWith('/login')) }"

# Toda rota do módulo, e a reunião aberta na página geral, respondem pela
# tabela, no lugar do backend.
pw run-code "async page => {
  const tabela = $(python3 "$AQUI/respostas.py");
  const chaveDe = (url) => decodeURIComponent(url.pathname.replace(/^\/api\//, '') + url.search);
  await page.route(u => u.pathname.startsWith('/api/nsp/') || (u.pathname.startsWith('/api/') && chaveDe(u) in tabela), route => {
    const pedido = route.request();
    if (pedido.method() !== 'GET') {
      return route.fulfill({ status: 403, json: { detail: 'O roteiro do manual não grava nada.' } });
    }
    const chave = chaveDe(new URL(pedido.url()));
    if (!(chave in tabela)) {
      return route.fulfill({ status: 404, json: { detail: 'Sem resposta de exemplo para ' + chave } });
    }
    return route.fulfill({ json: tabela[chave] });
  });
}"

echo "prints em $SAIDA:"

# Cadastrar um membro e acompanhar o Termo: a lista, o cadastro e a ficha com o Termo pendente.
pw goto "$MODULO/membros"
esperar "Juliana Prado"
# O submenu chama a página do módulo de Visão geral (#1949). App local
# atrasado, ainda com Início, para aqui em vez de fotografar o menu antigo.
pw run-code "async page => { await page.getByRole('navigation').getByRole('link', { name: 'Visão geral', exact: true }).waitFor({ timeout: 5000 }) }"
print_tela "membros.png"
clicar "getByRole('button', { name: 'Cadastrar membro' })"
pw run-code "async page => {
  await page.locator('#nsp-novo-pessoa').selectOption({ label: '$(seed "['cadastro']['pessoa']")' });
  await page.locator('#nsp-novo-area').fill('$(seed "['cadastro']['area']")');
  await page.locator('#nsp-novo-conselho_profissional').fill('$(seed "['cadastro']['conselho']")');
  await page.locator('#nsp-novo-registro_profissional').fill('$(seed "['cadastro']['registro']")');
  await page.locator('#nsp-novo-registro_uf').fill('$(seed "['cadastro']['uf']")');
  const fim = new Date(); fim.setFullYear(fim.getFullYear() + 2);
  await page.locator('#nsp-novo-vigencia_fim').fill(fim.toISOString().slice(0, 10));
}"
print "getByRole('region', { name: 'Cadastrar membro' })" "cadastrar-membro.png"
clicar "getByRole('region', { name: 'Cadastrar membro' }).getByRole('button', { name: 'Cancelar' })"

clicar "getByRole('button', { name: 'Beatriz Lima', exact: true })"
esperar "Reconsultar status da assinatura"
print_ficha "Beatriz Lima" "termo-do-membro.png"
clicar "getByRole('button', { name: 'Beatriz Lima', exact: true })"

# Renovar ou encerrar: a ficha de um membro ativo e a composição numa data passada.
clicar "getByRole('button', { name: 'Rodrigo Teixeira', exact: true })"
esperar "Histórico de mudanças"
print_ficha "Rodrigo Teixeira" "ficha-do-membro.png"
clicar "getByRole('button', { name: 'Rodrigo Teixeira', exact: true })"
pw run-code "async page => { await page.locator('#nsp-composicao-dia').fill('$(roteiro composicao)'); await page.getByRole('list', { name: /^Composição em/ }).waitFor() }"
print "locator('section').filter({ has: page.locator('#nsp-composicao-dia') })" "composicao-na-data.png"

# Publicar uma revisão do Regimento: os documentos e o formulário da revisão.
pw goto "$MODULO/documentos"
esperar "Aguardando assinatura"
print_pagina "documentos.png"
clicar "getByRole('button', { name: 'Publicar versão nova' })"
pw run-code "async page => {
  await page.locator('#documento-tipo').selectOption('regimento');
  await page.locator('#documento-titulo').fill('$(seed "['regimento']['titulo']")');
  await page.locator('#documento-texto').fill($(python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1]))['regimento']['texto'], ensure_ascii=False))" "$SEED"));
  await page.getByLabel('Material (pede nova assinatura do Termo)').check();
}"
print "locator('form').filter({ has: page.locator('#documento-titulo') })" "publicar-regimento.png"

# Registrar uma capacitação e confirmar presença: a lista e o formulário.
pw goto "$MODULO/capacitacoes"
esperar "Confirmar minha presença"
print_tela "capacitacoes.png"
clicar "getByRole('button', { name: 'Registrar capacitação' })"
pw run-code "async page => {
  const form = page.getByRole('form', { name: 'Nova capacitação' });
  await form.getByLabel('Título').fill('$(seed "['capacitacao_nova']['titulo']")');
  await form.getByLabel('Data').fill(new Date().toISOString().slice(0, 10));
  await form.getByLabel('Carga horária (horas)').fill('$(seed "['capacitacao_nova']['carga']")');
  await form.getByLabel('Instrutor').fill('$(seed "['capacitacao_nova']['instrutor']")');
  for (const nome of $(python3 -c "import json,sys; d=json.load(open(sys.argv[1]))['capacitacao_nova']; print(json.dumps(d['temas'] + d['participantes'], ensure_ascii=False))" "$SEED")) {
    await form.getByLabel(nome, { exact: true }).check();
  }
}"
print "getByRole('form', { name: 'Nova capacitação' })" "registrar-capacitacao.png"

# Acompanhar a agenda regulatória: os eventos, com o lembrete aberto.
pw goto "$MODULO/agenda"
esperar "Envio das notificações ao Notivisa"
print_tela "agenda.png"

# Fazer a reunião: o calendário, a pauta, a presença e as duas atas.
pw goto "$MODULO/reunioes"
esperar "Análise da queda no CTI Adulto"
print_pagina "reunioes.png"
DO_DIA="$(roteiro reuniao_do_dia)"
REUNIAO="getByRole('listitem').filter({ has: page.getByRole('button', { name: 'Pauta de $DO_DIA', exact: true }) })"
clicar "getByRole('button', { name: 'Pauta de $DO_DIA', exact: true })"
esperar "Pendências da reunião anterior"
print "$REUNIAO" "pauta.png"
clicar "getByRole('button', { name: 'Pauta de $DO_DIA', exact: true })"
clicar "$REUNIAO.getByRole('button', { name: 'Presença' })"
esperar "Salvar presença"
print "$REUNIAO" "presenca.png"

pw goto "$BASE/reunioes/exemplo-reuniao-em-validacao"
esperar "Validar a ata"
print "getByRole('region', { name: 'Ata do Núcleo' })" "ata-do-nucleo.png"

pw goto "$BASE/reunioes/exemplo-reuniao-assinada"
esperar "Baixar a ata assinada"
print_topo "getByRole('region', { name: 'Ata do Núcleo' })" 330 "ata-assinada.png"

pw close
