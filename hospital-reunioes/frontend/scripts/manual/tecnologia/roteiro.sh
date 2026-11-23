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
# respostas.py. Rota fora da tabela recebe 404, e pedido que grava (mandar
# fala, Criar o card) recebe 403: nenhuma conversa chega à IA, nenhum card
# nasce no GitHub e nenhum pedido de verdade entra no print. Os dois cliques do
# Envio aos desenvolvedores, interpretar e enviar, respondem pelo
# `respostas.py --envio` (issue #2015), e também não chegam à IA nem ao
# GitHub. O Achei um problema do Pedido de implantação (issue #2211) responde
# pela mesma tabela, só quando o POST do chat leva o Pedido: a conversa do bug
# abre com o texto de exemplo, sem IA. O sino responde
# do mesmo jeito, pelo `respostas.py --sino` (issue #1968): nenhum aviso de
# verdade aparece, e marcar como lido não grava nada. A lista Esperando sua
# resposta (issue #2123) só traz as perguntas quando a aba abre pelo aviso, com
# o `?pergunta=` no endereço; nos outros prints ela responde vazia, como no dia
# sem pergunta aberta, e o Quadro fica no alto da tela.

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
  const envio = $(python3 "$AQUI/respostas.py" --envio);
  // A lista Esperando você depois do Achei um problema (issue #2211): o Pedido em
  // que se clicou passa a esperar a Demanda do bug. No app isso vem com o Criar o
  // card; o roteiro não grava nada e troca a lista logo depois do POST do chat.
  const depoisDoProblema = $(python3 "$AQUI/respostas.py" --depois-do-problema);
  let problemaAberto = false;
  await page.route(u => u.pathname.includes('/api/admin/tecnologia/'), route => {
    const pedido = route.request();
    const url = new URL(pedido.url());
    const chave = decodeURIComponent(url.pathname.split('/api/admin/tecnologia/')[1] + url.search);
    if (pedido.method() !== 'GET') {
      let corpo = null;
      try { corpo = pedido.postDataJSON(); } catch {}
      if (pedido.method() === 'POST' && chave in envio && (chave !== 'chat' || corpo?.pedido_id)) {
        if (chave === 'chat') problemaAberto = true;
        return route.fulfill({ json: envio[chave] });
      }
      return route.fulfill({ status: 403, json: { detail: 'O roteiro do manual não grava nada.' } });
    }
    if (!(chave in tabela)) {
      return route.fulfill({ status: 404, json: { detail: 'Sem resposta de exemplo para ' + chave } });
    }
    if (chave === 'perguntas/esperando' && !new URL(page.url()).searchParams.has('pergunta')) {
      return route.fulfill({ json: [] });
    }
    if (chave === 'perguntas/esperando') {
      // Os Pedidos de implantação só entram quando a aba abre num deles (issue #2211):
      // nos outros prints a lista fica como era, sem eles.
      const destaque = new URL(page.url()).searchParams.get('pergunta');
      const lista = problemaAberto ? depoisDoProblema : tabela[chave];
      const deImplantacao = lista.some(i => i.tipo === 'implantacao' && i.id === destaque);
      return route.fulfill({ json: deImplantacao ? lista : lista.filter(i => i.tipo !== 'implantacao') });
    }
    return route.fulfill({ json: tabela[chave] });
  });
  const sino = $(python3 "$AQUI/respostas.py" --sino);
  await page.route(u => u.pathname.startsWith('/api/notificacoes'), route => {
    const pedido = route.request();
    if (pedido.method() !== 'GET') {
      return route.fulfill({ status: 403, json: { detail: 'O roteiro do manual não grava nada.' } });
    }
    const url = new URL(pedido.url());
    const chave = url.pathname.slice('/api/notificacoes'.length) + url.search;
    if (!(chave in sino)) {
      return route.fulfill({ status: 404, json: { detail: 'Sem aviso de exemplo para ' + chave } });
    }
    return route.fulfill({ json: sino[chave] });
  });
}"

echo "prints em $SAIDA:"

# Acompanhar o pedido no Quadro: as colunas, e um card aberto no painel.
pw goto "$TECNOLOGIA"
esperar "Em desenvolvimento"
print_tela "quadro.png"
# O botão Ver o plano no card (issue #2015): o plano já validado, com o check.
# O plano por validar, sem o check, fica no quadro.png, na coluna Planejada.
pw run-code "async page => { await page.getByRole('link', { name: 'Ver o plano, já validado', exact: true }).waitFor() }"
print "$(bloco "Em desenvolvimento")" "ver-o-plano.png"
pw run-code "async page => { await page.getByRole('button', { name: /Painel de Contas médicas por convênio/ }).click() }"
esperar "Henrique, as duas primeiras partes já estão no ar. A próxima traz o filtro de período."
print_tela "pedido-no-painel.png"
# As partes do mesmo pedido, agrupadas por Onda, com o número e o Espera a (issue #1903).
pw run-code "async page => { await page.getByRole('region', { name: 'Documento do card', exact: true }).getByText('Onda 3', { exact: true }).scrollIntoViewIfNeeded(); await page.waitForTimeout(400) }"
print "$(bloco "Documento do card")" "partes-por-onda.png"
pw run-code "async page => { await page.getByRole('button', { name: 'Fechar o pedido' }).click() }"
# O selo Implantação 1 de 3 no card Em produção e a seção Implantação dele (issue #2211).
pw run-code "async page => { await page.getByText('Implantação 1 de 3', { exact: true }).scrollIntoViewIfNeeded(); await page.waitForTimeout(400) }"
print "$(bloco "Entregue")" "selo-da-implantacao.png"
pw run-code "async page => { await page.getByRole('button', { name: /Checklist da limpeza dos leitos pelo celular/ }).click(); await page.getByRole('region', { name: 'Implantação', exact: true }).scrollIntoViewIfNeeded(); await page.waitForTimeout(600) }"
print "$(bloco "Documento do card")" "implantacao-no-card.png"
pw run-code "async page => { await page.getByRole('button', { name: 'Fechar o pedido' }).click() }"

# Responder uma pergunta da Vitta (issues #1968 e #2123): o aviso Pede sua
# resposta no sino, o clique que abre a lista Esperando você no cartão
# da pergunta, o pedido do projeto novo com o Plano do projeto, o cartão da
# pergunta na Conversa da Demanda e o Me explique aberto nele.
pw run-code "async page => { await page.getByRole('button', { name: 'Notificações' }).click() }"
esperar "Pede sua resposta"
print "getByRole('heading', { name: 'Notificações', exact: true }).locator('xpath=../..')" "aviso-pede-resposta.png"
pw run-code "async page => { await page.getByText('Pede sua resposta', { exact: true }).click(); await page.waitForURL(u => u.searchParams.has('pergunta')); await page.getByRole('region', { name: 'Esperando você', exact: true }).locator('li[aria-current=true]').waitFor() }"
esperar "A troca entre dois plantonistas precisa da aprovação da coordenação, ou vale assim que os dois confirmam?"
print "$(bloco "Esperando você")" "esperando-sua-resposta.png"
pw run-code "async page => { await page.getByRole('button', { name: /Troca de plantão pelo aplicativo/ }).click() }"
esperar "Plano do projeto"
print "$(bloco "Documento do card")" "projeto-novo.png"
pw run-code "async page => { const painel = page.getByRole('complementary', { name: 'Pedido aberto' }); await painel.getByRole('button', { name: 'Conversar' }).click(); await painel.getByRole('article', { name: 'Pergunta da Vitta' }).getByRole('button', { name: 'Responder' }).waitFor(); await page.waitForTimeout(600) }"
print "getByRole('complementary', { name: 'Pedido aberto' }).getByRole('article', { name: 'Pergunta da Vitta' })" "cartao-da-pergunta.png"
pw run-code "async page => { await page.getByRole('complementary', { name: 'Pedido aberto' }).getByRole('button', { name: 'Me explique' }).click(); await page.getByRole('region', { name: 'Me explique', exact: true }).getByRole('button', { name: 'Usar este rascunho' }).waitFor(); await page.waitForTimeout(600) }"
print "$(bloco "Me explique")" "me-explique.png"
pw run-code "async page => { await page.getByRole('button', { name: 'Fechar o pedido' }).click() }"

# Mandar o que você escreveu aos desenvolvedores (issue #2015): o Entendi assim
# das mensagens do diretor e a linha Enviado aos desenvolvedores.
pw run-code "async page => { await page.getByRole('button', { name: /Lembrete por e-mail do POP perto de vencer/ }).click() }"
esperar "Plano"
pw run-code "async page => { await page.getByRole('complementary', { name: 'Pedido aberto' }).getByRole('button', { name: 'Conversar' }).click(); await page.waitForTimeout(600) }"
esperar "Enviar para os desenvolvedores"
pw run-code "async page => { await page.getByRole('button', { name: 'Enviar para os desenvolvedores' }).click() }"
esperar "Entendi assim:"
pw run-code "async page => { await page.getByRole('region', { name: 'Conversa da Demanda' }).scrollIntoViewIfNeeded(); await page.waitForTimeout(400) }"
print "$(bloco "Conversa da Demanda")" "entendi-assim.png"
pw run-code "async page => { await page.getByRole('group', { name: 'Entendi assim:' }).getByRole('button', { name: 'Enviar', exact: true }).click(); await page.getByText(/^Enviado aos desenvolvedores em /).waitFor(); await page.waitForTimeout(600) }"
print "$(bloco "Conversa da Demanda")" "enviado-aos-desenvolvedores.png"
pw run-code "async page => { await page.getByRole('button', { name: 'Fechar o pedido' }).click() }"

# Concluir um passo a passo (issue #2184): a aba abre pelo `?pergunta=` do
# aviso Pede sua ação, com o cartão do Passo a passo da Vitta em destaque na
# lista Esperando você. O primeiro passo vem marcado pelo seed e o Concluir
# ainda preso: marcar um check também não grava nada.
pw goto "$TECNOLOGIA?pergunta=$(seed "['passo_a_passo']['id']")"
esperar "Passo a passo da Vitta"
pw run-code "async page => { await page.getByRole('region', { name: 'Esperando você', exact: true }).locator('li[aria-current=true]').scrollIntoViewIfNeeded(); await page.waitForTimeout(400) }"
print "getByRole('region', { name: 'Esperando você', exact: true }).locator('li[aria-current=true]')" "concluir-passo-a-passo.png"

# O Pedido de implantação (issue #2211, ADR 0111): o que espera outro, com os
# checks marcados e o Concluir preso. Depois, o Achei um problema do Pedido do
# teste, que abre a conversa do bug já com o texto dele, e o mesmo Pedido
# esperando a Demanda 63, a do bug.
DESTACADO="getByRole('region', { name: 'Esperando você', exact: true }).locator('li[aria-current=true]')"
pw goto "$TECNOLOGIA?pergunta=$(seed "['implantacao']['pedidos'][2]['id']")"
esperar "Achei um problema"
pw run-code "async page => { await page.$DESTACADO.scrollIntoViewIfNeeded(); await page.waitForTimeout(400) }"
print "$DESTACADO" "pedido-de-implantacao.png"
pw goto "$TECNOLOGIA?pergunta=$(seed "['implantacao']['achei_um_problema_em']")"
esperar "Achei um problema"
pw run-code "async page => { await page.$DESTACADO.getByRole('button', { name: 'Achei um problema' }).click() }"
esperar "$(seed "['implantacao']['falas_do_problema'][0]['texto']")"
# A conversa abre embaixo da lista Esperando você, que fica no alto pelo `?pergunta=`.
print "$(bloco "Conversa aberta")" "problema-no-assistente.png"
pw goto "$TECNOLOGIA?pergunta=$(seed "['implantacao']['achei_um_problema_em']")"
esperar "Espera a Demanda 63"
pw run-code "async page => { await page.$DESTACADO.scrollIntoViewIfNeeded(); await page.waitForTimeout(400) }"
print "$DESTACADO" "espera-a-demanda.png"

# Filtrar por Projeto: o campo Projeto em Ana. A aba abre de novo, sem o
# `?pergunta=` do aviso, e a lista Esperando sua resposta sai do alto.
pw goto "$TECNOLOGIA"
esperar "Em desenvolvimento"
pw run-code "async page => { await page.getByRole('combobox', { name: 'Projeto' }).click(); await page.getByRole('option', { name: 'Ana', exact: true }).click() }"
esperar "Ana confirmar o horário do exame por mensagem"
print_tela "filtro-projeto.png"

# Pedir um bug ou uma melhoria: a conversa nova, a pergunta da melhoria e o resumo do bug.
pw goto "$TECNOLOGIA"
esperar "Novo pedido"
pw run-code "async page => { await page.getByRole('button', { name: 'Novo pedido' }).click() }"
esperar "Isso é um bug, algo que não funciona como deveria, ou uma melhoria?"
print_tela "novo-pedido.png"

# Na tela de 1440 a conversa, o Documento do pedido e a Conversa da Demanda
# dividem a largura, e o cartão da pergunta fica estreito: este print sai mais largo.
pw resize 1920 1080
pw goto "$TECNOLOGIA?demanda=$(seed "['abrir']['melhoria']")"
esperar "Quem recebe o aviso?"
pw run-code "async page => { await page.getByText('Quem recebe o aviso?', { exact: true }).evaluate(e => e.scrollIntoView({ block: 'start' })); await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(400) }"
print_tela "pergunta-da-melhoria.png"
pw resize 1440 900

pw goto "$TECNOLOGIA?demanda=$(seed "['abrir']['bug']")"
esperar "Resumo do bug"
print_pagina "resumo-do-bug.png"

# Ver as Entregas: o ritmo das 12 semanas e a lista com uma entrega aberta.
pw goto "$TECNOLOGIA"
esperar "Novo pedido"
pw run-code "async page => { await page.getByRole('tab', { name: 'Entregas' }).click() }"
esperar "Ver semanas anteriores"
print "$(bloco "Ritmo das entregas")" "entregas-ritmo.png"
pw run-code "async page => { await page.getByRole('region', { name: 'O que foi entregue' }).getByText('Filtro de Projeto no Quadro da Tecnologia').click(); await page.waitForTimeout(600) }"
print "$(bloco "O que foi entregue")" "entregas-lista.png"

pw close
