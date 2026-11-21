// Os prints da página de Contas médicas do manual (issues #1724 e #1959). Quem
// roda é o roteiro.sh, pelo `playwright-cli run-code`, depois de trocar
// __BASE__, __SAIDA__ (uma pasta de rascunho) e __SEED__ (o seed.json). Cada
// `foto` grava um print citado em public/manual/contas-medicas/pagina.md, e o
// teste do roteiro confere que as duas listas batem. O texto de cada print
// volta para o roteiro, que passa pela guarda antes de levar o PNG para a
// página.
//
// Nada é confirmado: nem Feito, nem Concluir, nem Perguntar ao auditor, que
// chamaria a IA, nem Arquivar. Só pegar a conta da Fila muda o banco, e o
// semear.py a devolve à Fila na próxima rodada.
async (page) => {
  const base = "__BASE__";
  const saida = "__SAIDA__";
  const seed = __SEED__;
  const primeira = seed.contas.na_fila.numero_atendimento;
  const doSeed = Object.values(seed.contas).map((conta) => conta.numero_atendimento);
  const semProntuario = seed.contas.falta_o_prontuario.numero_atendimento;
  const concluida = seed.contas.concluida.numero_atendimento;
  const arquivada = seed.contas.arquivada.numero_atendimento;
  const textos = [];

  // Uma moldura em volta do que o passo manda clicar. É a única marcação
  // sobre a tela, e quem desenha é este roteiro.
  const marcar = async (alvo) => {
    await alvo.first().waitFor({ state: "visible", timeout: 15000 });
    await alvo.first().evaluate((el) => {
      el.setAttribute("data-marca-do-manual", "");
      el.style.outline = "3px solid #F59E0B";
      el.style.outlineOffset = "2px";
    });
  };
  const limpar = () =>
    page.evaluate(() =>
      document.querySelectorAll("[data-marca-do-manual]").forEach((el) => {
        el.style.outline = "";
        el.removeAttribute("data-marca-do-manual");
      })
    );
  // Sem foco, sem mouse em cima de nada e sem o selo do `next dev` no canto.
  const semFoco = async () => {
    await page.evaluate(() => {
      if (document.activeElement) document.activeElement.blur();
      document.querySelectorAll("nextjs-portal").forEach((selo) => selo.remove());
    });
    await page.mouse.move(1439, 899);
    await page.waitForTimeout(400);
  };
  // O print de um pedaço da tela, ou da tela inteira sem `alvo`. Com `ate`, o
  // print vai do alto de `alvo` ao pé de `ate`. O texto do que foi
  // fotografado vai junto para a guarda.
  const foto = async (arquivo, alvo, ate) => {
    await semFoco();
    const fotografado = alvo ?? page.locator("body");
    let texto = await fotografado.innerText();
    if (ate) {
      texto += `\n${await ate.innerText()}`;
      const de = await alvo.boundingBox();
      const fim = await ate.boundingBox();
      const clip = { x: de.x - 8, y: de.y - 8, width: de.width + 16, height: fim.y + fim.height - de.y + 16 };
      await page.screenshot({ path: `${saida}/${arquivo}`, clip });
    } else if (alvo) await alvo.screenshot({ path: `${saida}/${arquivo}` });
    else await page.screenshot({ path: `${saida}/${arquivo}` });
    textos.push({ arquivo, texto });
    await limpar();
  };
  // O banco local tem contas de outros trabalhos: cada lista do print fica só
  // com as do seed, e o grupo de mês que fica vazio some junto.
  const soOSeed = (lista) =>
    lista.evaluate((raiz, numeros) => {
      raiz.querySelectorAll("li").forEach((li) => {
        if (!numeros.some((n) => li.textContent.includes(n))) li.style.display = "none";
      });
      raiz.querySelectorAll("section").forEach((grupo) => {
        const linhas = Array.from(grupo.querySelectorAll("li"));
        if (linhas.length > 0 && linhas.every((li) => li.style.display === "none")) grupo.style.display = "none";
      });
    }, doSeed);
  const etapa = (nome) =>
    page.getByRole("region", { name: "Esteira" }).getByRole("tab", { name: new RegExp(`^${nome}`, "i") });
  const lista = () => page.getByRole("region", { name: "Lista de contas" });
  const linhaDa = (numero) => lista().getByRole("listitem").filter({ hasText: numero });

  // Entrar com a faturista de exemplo.
  await page.goto(`${base}/login`);
  await page.locator("#email").fill(seed.faturista.email);
  await page.locator("#password").fill(seed.faturista.senha);
  await page.locator("#password").press("Enter");
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 30000 });

  // O caminho de uma conta: a Esteira com as cinco etapas.
  await page.goto(`${base}/contas-medicas`);
  const esteira = page.getByRole("region", { name: "Esteira" });
  await esteira.waitFor({ timeout: 60000 });
  await linhaDa(primeira).waitFor({ timeout: 30000 });
  await foto("esteira.png", esteira);

  // Ligar e desligar as legendas: o interruptor ao lado das abas, ligado, com
  // a Legenda da tela logo abaixo.
  const abas = page.getByRole("navigation", { name: "Telas de Contas médicas" }).locator("..");
  const barra = page.locator("[data-barra]");
  await marcar(page.getByRole("switch", { name: "Legendas" }));
  await foto("legendas.png", abas, barra);

  // Enviar uma conta: o botão Enviar contas abre a área de envio.
  await page.getByRole("button", { name: "Enviar contas" }).click();
  const envio = page.getByRole("region", { name: "Envio de contas" });
  await envio.waitFor();
  await marcar(envio.getByRole("button", { name: "Selecionar arquivos" }));
  await foto("enviar.png", envio);
  await page.getByRole("button", { name: "Enviar contas" }).click();

  await etapa("Envios").click();
  const cartao = page.locator("article").filter({ hasText: semProntuario }).first();
  await marcar(cartao.getByRole("button", { name: "Enviar o prontuário" }));
  await foto("envios.png", cartao);

  // Pegar uma conta da Fila.
  await etapa("Fila").click();
  await linhaDa(primeira).waitFor();
  await soOSeed(lista());
  await marcar(linhaDa(primeira).getByRole("link", { name: "Pegar" }));
  await foto("fila.png", lista());

  // O rodapé do Guia gruda no pé da janela e cobre a Mesa de trabalho numa
  // tela de 900 px: com a janela alta, a conta inteira cabe e o rodapé fica
  // no lugar dele.
  await page.setViewportSize({ width: 1440, height: 1800 });
  await linhaDa(primeira).getByRole("link", { name: "Pegar" }).click();
  await page.getByRole("region", { name: "Mesa de trabalho" }).waitFor({ timeout: 30000 });
  await page.waitForTimeout(800);
  await marcar(page.getByRole("button", { name: "Devolver à fila" }));
  await foto("guia.png", page.locator("[data-guia] > header"), page.getByRole("region", { name: "Números do guia" }));

  // Analisar a conta no Guia: a Mesa de trabalho, com a lista e o Item da vez.
  const mesa = page.getByRole("region", { name: "Mesa de trabalho" });
  await marcar(page.getByRole("region", { name: "Item da vez" }).getByRole("button", { name: "Feito", exact: true }));
  await foto("linha-do-guia.png", mesa);

  const rodape = page.locator("footer").filter({ hasText: "Concluir e abrir a próxima" });
  await marcar(rodape.getByRole("button", { name: "Concluir e abrir a próxima" }));
  await foto("concluir.png", rodape);
  await page.setViewportSize({ width: 1440, height: 900 });

  // Pedir o que faltou: o Faltou isto do dia abre a conversa ao lado,
  // preenchida e sem enviar.
  const dia = page.getByRole("region", { name: "Itens da conta" }).getByRole("region", { name: /^03\/11/ });
  await dia.getByRole("button", { name: "Faltou isto" }).click();
  const conversa = page.getByRole("dialog", { name: "Falar com o auditor" });
  await conversa.getByLabel("Item que faltou", { exact: true }).fill(seed.faltou_isto.item);
  await conversa.getByLabel("Página do prontuário", { exact: true }).fill(seed.faltou_isto.pagina);
  await conversa.getByLabel("Mensagem para o auditor", { exact: true }).fill(seed.faltou_isto.texto);
  await marcar(conversa.getByRole("button", { name: "Perguntar ao auditor" }));
  await foto("faltou-isto.png", conversa.locator("h2").locator(".."), conversa.locator("fieldset"));

  // Achar uma conta: o número na busca e a conta em destaque, com onde está e
  // com quem.
  await page.goto(`${base}/contas-medicas`);
  const busca = page.getByRole("searchbox", { name: "Buscar conta" });
  await busca.fill(primeira);
  const achada = page.getByRole("article", { name: "Conta encontrada" });
  await achada.waitFor({ timeout: 15000 });
  await marcar(busca);
  const telaDaBusca = page.locator("div.relative.space-y-6").first();
  await foto("busca.png", telaDaBusca);
  await busca.fill("");

  // Arquivar as contas do mês: uma a uma, o mês inteiro e o desarquivar.
  await etapa("Concluídas").click();
  await linhaDa(concluida).waitFor();
  await soOSeed(lista());
  await marcar(linhaDa(concluida).getByRole("button", { name: "Arquivar", exact: true }));
  await foto("arquivar.png", lista());

  const mes = lista().locator("section").filter({ has: page.getByRole("listitem").filter({ hasText: concluida }) });
  await mes.getByRole("button", { name: "Arquivar o mês" }).click();
  const confirmar = mes.getByRole("group", { name: "Confirmar o arquivar do mês" });
  await marcar(confirmar.getByRole("button", { name: /^Arquivar \d/ }));
  await foto("arquivar-o-mes.png", mes);
  await confirmar.getByRole("button", { name: "Cancelar" }).click();

  await etapa("Arquivadas").click();
  await linhaDa(arquivada).waitFor({ timeout: 15000 });
  await soOSeed(lista());
  await marcar(linhaDa(arquivada).getByRole("button", { name: "Desarquivar" }));
  await foto("desarquivar.png", lista());

  return JSON.stringify(textos);
}
