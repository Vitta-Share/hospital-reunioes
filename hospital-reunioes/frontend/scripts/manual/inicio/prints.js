// Os prints da página do Início do manual (issue #1947). Quem roda é o
// roteiro.sh, pelo `playwright-cli run-code`, depois de trocar __BASE__,
// __SAIDA__ (uma pasta de rascunho) e __SEED__ (o seed.json). Cada `foto` grava
// um print citado em public/manual/inicio/pagina.md, e o teste do roteiro
// confere que as duas listas batem. O texto de cada print volta para o
// roteiro, que passa pela guarda antes de levar o PNG para a página.
//
// Nada é clicado que mude o banco: o botão da linha não é seguido, e abrir a
// lista de quem responde é só da tela.
async (page) => {
  const base = "__BASE__";
  const saida = "__SAIDA__";
  const seed = __SEED__;
  const textos = [];

  // O balão numerado que a página cita, "(1)", "(2)": um `div` por cima da
  // tela, sem clique, que some na próxima navegação. Nada disto fica no app.
  const balao = async (alvo, numero) => {
    await alvo.first().waitFor({ state: "visible", timeout: 15000 });
    await alvo.first().scrollIntoViewIfNeeded();
    const caixa = await alvo.first().boundingBox();
    await page.evaluate(
      ([x, y, n]) => {
        const b = document.createElement("div");
        b.className = "balao-do-manual";
        b.textContent = String(n);
        Object.assign(b.style, {
          position: "absolute",
          left: `${x + window.scrollX}px`,
          top: `${y + window.scrollY}px`,
          width: "28px",
          height: "28px",
          borderRadius: "9999px",
          background: "#2B2E7E",
          color: "#fff",
          font: "700 15px/28px system-ui, sans-serif",
          textAlign: "center",
          boxShadow: "0 2px 6px rgba(0,0,0,0.35)",
          pointerEvents: "none",
          zIndex: "2147483647",
        });
        document.body.appendChild(b);
      },
      [Math.max(0, caixa.x - 22), Math.max(0, caixa.y - 22), numero]
    );
  };
  const limpar = () => page.evaluate(() => document.querySelectorAll(".balao-do-manual").forEach((b) => b.remove()));
  // Sem foco e sem o selo do `next dev` no canto.
  const semFoco = async () => {
    await page.evaluate(() => {
      if (document.activeElement) document.activeElement.blur();
      document.querySelectorAll("nextjs-portal").forEach((selo) => selo.remove());
    });
    await page.waitForTimeout(400);
  };
  // O print de um pedaço da tela, ou da janela inteira sem `alvo`. O texto do
  // que foi fotografado vai junto para a guarda.
  const foto = async (arquivo, alvo) => {
    await semFoco();
    const fotografado = alvo ?? page.locator("body");
    textos.push({ arquivo, texto: await fotografado.innerText() });
    if (alvo) await alvo.screenshot({ path: `${saida}/${arquivo}` });
    else await page.screenshot({ path: `${saida}/${arquivo}` });
    await limpar();
  };

  // Entrar com a Facilitadora de exemplo: o login tem de cair no Início.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${base}/login`);
  await page.locator("#email").fill(seed.facilitadora.email);
  await page.locator("#password").fill(seed.facilitadora.senha);
  await page.locator("#password").press("Enter");
  await page.waitForURL((url) => url.pathname === "/inicio", { timeout: 30000 });

  // Ver o que tenho para entregar: o Início inteiro, numa janela alta o
  // bastante para a Minha Fila caber, sem Quem responde a você.
  const minhaFila = page.getByTestId("abertura").locator("xpath=..");
  const vencidas = page.getByRole("region", { name: "Passou do prazo" });
  await vencidas.waitFor({ timeout: 30000 });
  await page.getByRole("region", { name: "Quem responde a você" }).waitFor({ timeout: 30000 });
  await page.waitForTimeout(1200);
  await balao(page.getByTestId("abertura").locator("p").first(), 1);
  await balao(page.getByRole("list", { name: "Resumo dos prazos" }), 2);
  await balao(vencidas.getByRole("heading"), 3);
  await balao(page.getByRole("complementary", { name: "Próximas Reuniões" }), 4);
  await page.evaluate(() => window.scrollTo(0, 0));
  await foto("inicio.png", minhaFila);

  // Abrir um item da Minha Fila: a linha vencida com o mouse em cima, o
  // contexto à vista e o botão preenchido.
  const linha = vencidas.getByRole("listitem").filter({ hasText: seed.pendencias[0].descricao });
  await linha.hover();
  await page.waitForTimeout(300);
  await balao(linha.locator("p.text-primary"), 1);
  await balao(linha.getByRole("link", { name: /^Abrir a Pendência/ }), 2);
  await linha.hover();
  await page.waitForTimeout(300);
  await foto("abrir-um-item.png", vencidas);
  await page.mouse.move(0, 0);

  // Acompanhar quem responde a você: a linha da pessoa com mais vencidos,
  // aberta, com a lista do que venceu.
  const quem = page.getByRole("region", { name: "Quem responde a você" });
  const maisAtrasada = seed.pessoas[2].nome;
  const linhaDaPessoa = quem.getByRole("row").filter({ hasText: maisAtrasada });
  await linhaDaPessoa.click();
  const lista = quem.getByRole("list", { name: `O que venceu e não foi entregue por ${maisAtrasada}` });
  await lista.waitFor();
  await page.mouse.move(0, 0);
  await balao(linhaDaPessoa.locator("td").first(), 1);
  await balao(lista, 2);
  await foto("quem-responde.png", quem);

  return JSON.stringify(textos);
}
