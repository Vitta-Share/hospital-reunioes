/**
 * @vitest-environment jsdom
 */

/**
 * O layout da área /contas-medicas é a casca do módulo.
 *
 * Põe títulos e subtítulos em caixa alta, a pedido do diretor (PR #1411). A
 * regra vive num contêiner com variantes do Tailwind que miram os h1, h2 e h3
 * descendentes; o que se trava aqui é que cada título da página renderizada
 * fica DENTRO desse contêiner, e não só que a classe existe solta.
 *
 * E mostra as abas do módulo (issue #1950): cada uma só para quem tem a
 * permissão que liberava o botão dela na tela de contas, com a da tela atual
 * marcada, e o interruptor "Legendas", que vale para o módulo inteiro e fica
 * guardado num cookie, lido pelo servidor para a escolha valer já no primeiro
 * paint.
 */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Legenda } from "@/components/ui/Legenda";

const sessao = vi.hoisted(() => ({ permissoes: [] as string[] }));
const rota = vi.hoisted(() => ({ atual: "/contas-medicas" }));

vi.mock("@/lib/contas-medicas/guard", () => ({
  requireContasMedicasAccess: async () => ({
    user: { email: "faturista@hsm.test", user_metadata: { nome: "Ana" } },
    permissoes: sessao.permissoes,
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => rota.atual,
}));

// O servidor lê o mesmo cookie que o navegador grava: recarregar a página é
// abrir o layout de novo com o que ficou no `document.cookie`.
vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (nome: string) => {
      const par = document.cookie
        .split("; ")
        .map((c) => c.split("="))
        .find(([n]) => n === nome);
      return par ? { name: nome, value: par[1] } : undefined;
    },
  }),
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import ContasMedicasLayout from "./layout";

const COOKIE_DAS_LEGENDAS = "contas-medicas-legendas";

function cookieDasLegendas(): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${COOKIE_DAS_LEGENDAS}=`))
    ?.split("=")[1];
}

/** Todas as permissões que liberam uma aba, para quem vê o módulo inteiro. */
const TODAS = [
  "painel_completo",
  "decidir_validacao",
  "conferencia_coordenacao",
  "contratos_avisos",
  "regra_contratual_tabelas",
  "habilitar_pessoas",
];

beforeEach(() => {
  sessao.permissoes = [];
  rota.atual = "/contas-medicas";
  document.cookie = `${COOKIE_DAS_LEGENDAS}=; path=/; max-age=0`;
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function abrir(children: React.ReactNode = <h1>Contas médicas</h1>) {
  render(await ContasMedicasLayout({ children }));
}

function abas(): HTMLElement {
  return screen.getByRole("navigation", { name: "Telas de Contas médicas" });
}

function nomesDasAbas(): string[] {
  return within(abas())
    .getAllByRole("link")
    .map((link) => link.textContent ?? "");
}

/** O ancestral mais próximo do elemento que leva a variante, ou null. */
function contemComVariante(elemento: HTMLElement, variante: string): HTMLElement | null {
  let atual = elemento.parentElement;
  while (atual) {
    if (atual.className.split(" ").includes(variante)) return atual;
    atual = atual.parentElement;
  }
  return null;
}

describe("o layout de Contas médicas", () => {
  it("põe o h1, o h2 e o h3 da página dentro do contêiner que os deixa em caixa alta", async () => {
    await abrir(
      <>
        <h1>Contas médicas</h1>
        <h2>Último envio</h2>
        <h3>Pendências</h3>
      </>,
    );

    for (const nivel of [1, 2, 3] as const) {
      const titulo = screen.getByRole("heading", { level: nivel });
      expect(contemComVariante(titulo, `[&_h${nivel}]:uppercase`)).not.toBeNull();
    }
  });
});

describe("as abas do módulo", () => {
  it("quem tem todas as permissões vê as sete abas, na ordem, cada uma com o endereço da tela", async () => {
    sessao.permissoes = TODAS;

    await abrir();

    const links = within(abas()).getAllByRole("link");
    expect(links.map((l) => [l.textContent, l.getAttribute("href")])).toEqual([
      ["Contas", "/contas-medicas"],
      ["Painel", "/contas-medicas/painel"],
      ["Validação", "/contas-medicas/validacao"],
      ["Coordenação", "/contas-medicas/coordenacao"],
      ["Contratos", "/contas-medicas/contratos"],
      ["Operadoras", "/contas-medicas/operadoras"],
      ["Habilitação", "/contas-medicas/habilitacao"],
    ]);
  });

  it.each([
    ["painel_completo", "Painel"],
    ["enviar_corrigir_contas", "Painel"],
    ["decidir_validacao", "Validação"],
    ["conferencia_coordenacao", "Coordenação"],
    ["contratos_avisos", "Contratos"],
    ["regra_contratual_tabelas", "Operadoras"],
    ["habilitar_pessoas", "Habilitação"],
  ])("com só %s, aparecem Contas e %s", async (permissao, aba) => {
    sessao.permissoes = [permissao];

    await abrir();

    expect(nomesDasAbas()).toEqual(["Contas", aba]);
  });

  it("quem não tem nenhuma delas vê só Contas", async () => {
    sessao.permissoes = ["incluir_regra_operacional"];

    await abrir();

    expect(nomesDasAbas()).toEqual(["Contas"]);
  });

  it.each([
    ["/contas-medicas", "Contas"],
    ["/contas-medicas/guia/c-1", "Contas"],
    ["/contas-medicas/painel", "Painel"],
    ["/contas-medicas/validacao", "Validação"],
    ["/contas-medicas/coordenacao", "Coordenação"],
    ["/contas-medicas/contratos", "Contratos"],
    ["/contas-medicas/operadoras", "Operadoras"],
    ["/contas-medicas/operadoras/ASSIM", "Operadoras"],
    ["/contas-medicas/habilitacao", "Habilitação"],
  ])("em %s, a aba marcada é %s, e só ela", async (endereco, marcada) => {
    sessao.permissoes = TODAS;
    rota.atual = endereco;

    await abrir();

    const atuais = within(abas())
      .getAllByRole("link")
      .filter((link) => link.getAttribute("aria-current") === "page");
    expect(atuais.map((link) => link.textContent)).toEqual([marcada]);
  });

  it("cada aba diz para que a tela serve numa dica de uma frase, no foco do teclado", async () => {
    sessao.permissoes = TODAS;

    await abrir();

    for (const link of within(abas()).getAllByRole("link")) {
      fireEvent.focus(link);
      const dica = screen.getByRole("tooltip");
      expect(link.getAttribute("aria-describedby")).toBe(dica.id);
      const texto = dica.textContent ?? "";
      expect(texto.length).toBeGreaterThan(15);
      expect(texto.match(/[.!?]/g)).toEqual(["."]);
      expect(texto.endsWith(".")).toBe(true);
      fireEvent.blur(link);
    }
  });

  it("as abas quebram linha em tela estreita, sem rolagem lateral", async () => {
    sessao.permissoes = TODAS;

    await abrir();

    const lista = within(abas()).getByRole("list");
    expect(lista.className.split(" ")).toContain("flex-wrap");
    expect(lista.className).not.toMatch(/overflow-x-(auto|scroll)/);
  });
});

describe("o interruptor Legendas", () => {
  function interruptor(): HTMLElement {
    return screen.getByRole("switch", { name: "Legendas" });
  }

  const COM_LEGENDA = (
    <>
      <h1>Contas médicas</h1>
      <Legenda>Envie a conta e o prontuário do MV.</Legenda>
    </>
  );

  it("começa ligado e mostra as Legendas da tela", async () => {
    await abrir(COM_LEGENDA);

    expect(interruptor().getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("Envie a conta e o prontuário do MV.")).toBeTruthy();
  });

  it("desligado, nenhuma Legenda aparece, e a escolha fica guardada no navegador", async () => {
    await abrir(COM_LEGENDA);

    fireEvent.click(interruptor());

    expect(interruptor().getAttribute("aria-checked")).toBe("false");
    expect(screen.queryByText("Envie a conta e o prontuário do MV.")).toBeNull();
    expect(cookieDasLegendas()).toBe("0");
  });

  it("a escolha sobrevive a recarregar a página", async () => {
    await abrir(COM_LEGENDA);
    fireEvent.click(interruptor());
    cleanup();

    await abrir(COM_LEGENDA);

    expect(interruptor().getAttribute("aria-checked")).toBe("false");
    expect(screen.queryByText("Envie a conta e o prontuário do MV.")).toBeNull();
  });

  it("desligado e recarregado, o HTML do servidor (o primeiro paint) já vem sem Legenda e com o interruptor desligado", async () => {
    document.cookie = `${COOKIE_DAS_LEGENDAS}=0; path=/`;

    const html = renderToString(await ContasMedicasLayout({ children: COM_LEGENDA }));

    expect(html).not.toContain("Envie a conta e o prontuário do MV.");
    expect(html).toMatch(/role="switch" aria-checked="false"/);
  });

  it("sem escolha gravada, o HTML do servidor vem com as Legendas", async () => {
    const html = renderToString(await ContasMedicasLayout({ children: COM_LEGENDA }));

    expect(html).toContain("Envie a conta e o prontuário do MV.");
    expect(html).toMatch(/role="switch" aria-checked="true"/);
  });

  it("ligar de novo traz as Legendas de volta", async () => {
    document.cookie = `${COOKIE_DAS_LEGENDAS}=0; path=/`;
    await abrir(COM_LEGENDA);

    fireEvent.click(interruptor());

    expect(screen.getByText("Envie a conta e o prontuário do MV.")).toBeTruthy();
    expect(cookieDasLegendas()).toBe("1");
  });

  it("se o navegador não deixa gravar a preferência, as Legendas começam ligadas e o interruptor ainda funciona", async () => {
    vi.spyOn(Document.prototype, "cookie", "set").mockImplementation(() => {
      throw new Error("bloqueado");
    });

    await abrir(COM_LEGENDA);

    expect(interruptor().getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("Envie a conta e o prontuário do MV.")).toBeTruthy();

    fireEvent.click(interruptor());

    expect(screen.queryByText("Envie a conta e o prontuário do MV.")).toBeNull();
  });
});
