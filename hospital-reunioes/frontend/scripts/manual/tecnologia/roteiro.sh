#!/usr/bin/env bash
# Refaz os prints da página de Tecnologia do manual (issue #1727, ADR 0094,
# decisão 5) pelo playwright-cli, contra o app LOCAL e com o seed fictício.
#
# Uso (da pasta hospital-reunioes/frontend, com o app local no ar):
#   bash scripts/manual/tecnologia/roteiro.sh
#   BASE=http://localhost:3027 bash scripts/manual/tecnologia/roteiro.sh
#
# O roteiro semeia o diretor de exemplo (semear.py), entra como ele e responde
# no lugar do backend em toda rota da aba Tecnologia com a tabela do
# respostas.py. Desde a issue #2279 (ADR 0113) a aba só lê: o Quadro, o pedido
# aberto e as Entregas. Rota fora da tabela recebe 404, e todo pedido que não
# é GET recebe 403: nenhum card nasce no GitHub e nenhum pedido de verdade
# entra no print. O sino responde vazio, para nenhum aviso de verdade aparecer.

set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$(cd "$AQUI/../../.." && pwd)"
SAIDA="$FRONTEND/public/manual/tecnologia"
BASE="${BASE:-http://localhost:3000}"
SESSAO="manual-tecnologia-1727"
TECNOLOGIA="$BASE/admin/tecnologia"

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

# Fotografa a tela inteira ou um pedaço dela, e salva o PNG ao lado do Markdown.
print_tela() { pw screenshot --filename="$SAIDA/$1"; echo "  $1"; }
print_pagina() { pw screenshot --full-page --filename="$SAIDA/$1"; echo "  $1"; }
print() { pw screenshot "$1" --filename="$SAIDA/$2"; echo "  $2"; }
bloco() { echo "getByRole('region', { name: '$1', exact: true })"; }

python3 "$AQUI/semear.py"
mkdir -p "$SAIDA"

pw open "$BASE/login"
pw resize 1440 900
pw fill "#email" "$(seed "['admin']['email']")"
pw fill "#password" "$(seed "['admin']['senha']")" --submit
pw run-code "async page => { await page.waitForURL(u => !u.pathname.startsWith('/login')) }"

# Toda rota da aba responde pela tabela, no lugar do backend.
pw run-code "async page => {
  const tabela = $(python3 "$AQUI/respostas.py");
  await page.route(u => u.pathname.includes('/api/admin/tecnologia/'), route => {
    const pedido = route.request();
    if (pedido.method() !== 'GET') {
      return route.fulfill({ status: 403, json: { detail: 'O roteiro do manual não grava nada.' } });
    }
    const url = new URL(pedido.url());
    const chave = decodeURIComponent(url.pathname.split('/api/admin/tecnologia/')[1] + url.search);
    if (!(chave in tabela)) {
      return route.fulfill({ status: 404, json: { detail: 'Sem resposta de exemplo para ' + chave } });
    }
    return route.fulfill({ json: tabela[chave] });
  });
  await page.route(u => u.pathname.startsWith('/api/notificacoes'), route => {
    const pedido = route.request();
    if (pedido.method() !== 'GET') {
      return route.fulfill({ status: 403, json: { detail: 'O roteiro do manual não grava nada.' } });
    }
    const contagem = new URL(pedido.url()).pathname.endsWith('/count');
    return route.fulfill({ json: contagem ? { nao_lidas: 0 } : [] });
  });
}"

echo "prints em $SAIDA:"

# Acompanhar o pedido no Quadro: as colunas, o Ver o plano e um card aberto no painel.
pw goto "$TECNOLOGIA"
esperar "Em desenvolvimento"
print_tela "quadro.png"
# O botão Ver o plano no card (issue #2015): o plano já validado, com o check.
# O plano por validar, sem o check, fica no quadro.png, na coluna Planejada.
pw run-code "async page => { await page.getByRole('link', { name: 'Ver o plano, já validado', exact: true }).waitFor() }"
print "$(bloco "Em desenvolvimento")" "ver-o-plano.png"
pw run-code "async page => { await page.getByRole('button', { name: /Painel de Contas médicas por convênio/ }).click() }"
esperar "Onda 3"
print_tela "pedido-no-painel.png"
# As partes do mesmo pedido, agrupadas por Onda, com o número e o Espera a (issue #1903).
pw run-code "async page => { await page.getByRole('region', { name: 'Documento do card', exact: true }).getByText('Onda 3', { exact: true }).scrollIntoViewIfNeeded(); await page.waitForTimeout(400) }"
print "$(bloco "Documento do card")" "partes-por-onda.png"
pw run-code "async page => { await page.getByRole('button', { name: 'Fechar o pedido' }).click() }"

# Ver o que falta para começar a usar (issue #2282, ADR 0113, decisão 9): o
# selo Implantação 1 de 3 no card Em produção e a seção Implantação dele.
pw run-code "async page => { await page.getByText('Implantação 1 de 3', { exact: true }).scrollIntoViewIfNeeded(); await page.waitForTimeout(400) }"
print "$(bloco "Entregue")" "selo-da-implantacao.png"
pw run-code "async page => { await page.getByRole('button', { name: /Checklist da limpeza dos leitos pelo celular/ }).click(); await page.getByRole('region', { name: 'Implantação', exact: true }).scrollIntoViewIfNeeded(); await page.waitForTimeout(600) }"
print "$(bloco "Documento do card")" "implantacao-no-card.png"
pw run-code "async page => { await page.getByRole('button', { name: 'Fechar o pedido' }).click() }"

# Filtrar por Projeto: o campo Projeto em Ana.
pw run-code "async page => { await page.getByRole('combobox', { name: 'Projeto' }).click(); await page.getByRole('option', { name: 'Ana', exact: true }).click() }"
esperar "Ana confirmar o horário do exame por mensagem"
print_tela "filtro-projeto.png"

# Ver as Entregas: o ritmo das 12 semanas e a lista com uma entrega aberta.
pw goto "$TECNOLOGIA"
esperar "Em desenvolvimento"
pw run-code "async page => { await page.getByRole('tab', { name: 'Entregas' }).click() }"
esperar "Ver semanas anteriores"
print "$(bloco "Ritmo das entregas")" "entregas-ritmo.png"
pw run-code "async page => { await page.getByRole('region', { name: 'O que foi entregue' }).getByText('Filtro de Projeto no Quadro da Tecnologia').click(); await page.waitForTimeout(600) }"
print "$(bloco "O que foi entregue")" "entregas-lista.png"

pw close
