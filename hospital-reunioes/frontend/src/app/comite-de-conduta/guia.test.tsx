/**
 * @vitest-environment jsdom
 */
/// <reference types="vite/client" />

/**
 * O Guia do rito e o primeiro acesso do Comitê de Conduta (issue #1842,
 * seção 5.4 da especificação do PRD #1786).
 *
 * * o guia descreve os quatro ritos e o que cada pessoa faz em cada um;
 * * ele abre de qualquer tela do Comitê;
 * * o membro sem o Termo assinado também abre o guia;
 * * os cinco cartões aparecem só no primeiro acesso de cada pessoa.
 *
 * Os layouts e o portão rodam de verdade: só o Supabase do servidor, o fetch
 * e o AppShell são de mentira.
 */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const redirect = vi.fn((destino: string) => {
  throw new Error(`redirect:${destino}`);
});

vi.mock("next/navigation", () => ({
  redirect: (destino: string) => redirect(destino),
  usePathname: () => "/comite-de-conduta",
  useParams: () => ({ id: "c1" }),
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const metadados = vi.hoisted(() => ({ atual: {} as Record<string, unknown> }));
const updateUser = vi.hoisted(() => vi.fn(async () => ({ data: {}, error: null })));

vi.mock("@/lib/supabase/server", () => ({
  createClient: async () => ({
    auth: {
      getUser: async () => ({ data: { user: { email: "membro@hsm.test", user_metadata: metadados.atual } } }),
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { updateUser, getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

import GuiaDoRitoLayout from "./guia/layout";
import GuiaDoRitoPage from "./guia/page";

/** O que cada rota do portão responde: 200 ou a recusa. */
let portao: Record<string, number>;

beforeEach(() => {
  metadados.atual = { conduta_apresentacao_vista_em: "2026-11-01T10:00:00Z" };
  updateUser.mockClear();
  redirect.mockClear();
  portao = {};
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const rota = Object.keys(portao).find((r) => url.endsWith(r));
      const status = rota ? portao[rota] : 403;
      return { ok: status === 200, status, json: async () => ({}) } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CONTEUDO = "o conteúdo do guia";

describe("quem abre o guia", () => {
  it("o membro sem o Termo assinado abre o guia, que o portão dos casos recusaria", async () => {
    portao = { "/comite-de-conduta/minha-vez": 403, "/comite-de-conduta/membros": 200 };

    render(await GuiaDoRitoLayout({ children: <p>{CONTEUDO}</p> }));

    expect(screen.getByText(CONTEUDO)).toBeTruthy();
    expect(redirect).not.toHaveBeenCalled();
  });

  it("o apurador designado, que não é membro, também abre", async () => {
    portao = { "/comite-de-conduta/minha-vez": 200, "/comite-de-conduta/membros": 403 };

    render(await GuiaDoRitoLayout({ children: <p>{CONTEUDO}</p> }));

    expect(screen.getByText(CONTEUDO)).toBeTruthy();
  });

  it("quem não é do Comitê volta ao início sem receber o guia", async () => {
    portao = { "/comite-de-conduta/minha-vez": 403, "/comite-de-conduta/membros": 403 };

    await expect(GuiaDoRitoLayout({ children: <p>{CONTEUDO}</p> })).rejects.toThrow("redirect:/dashboard");
  });
});

describe("o Guia do rito", () => {
  it("descreve os quatro ritos, com o prazo e o que cada pessoa faz", () => {
    render(<GuiaDoRitoPage />);

    const ritos = screen.getAllByRole("article");
    expect(ritos.map((r) => within(r).getByRole("heading").textContent)).toEqual([
      "Encaminhamento",
      "Rito rápido",
      "Rito completo",
      "Rota Especial",
    ]);
    expect(within(ritos[0]).getByText(/5 dias úteis/)).toBeTruthy();
    expect(within(ritos[1]).getByText(/20 dias corridos/)).toBeTruthy();
    expect(within(ritos[2]).getByText(/30 dias corridos/)).toBeTruthy();
    expect(within(ritos[3]).getByText(/60 dias corridos/)).toBeTruthy();
    for (const rito of ritos) {
      expect(within(rito).getAllByRole("listitem").length, rito.textContent ?? "").toBeGreaterThanOrEqual(2);
    }
    expect(within(ritos[1]).getByText(/Os três membros/)).toBeTruthy();
    expect(within(ritos[3]).getByText(/CIPA/)).toBeTruthy();
  });
});

/** Toda tela do Comitê, menos o próprio guia. */
const TELAS = Object.entries(
  import.meta.glob<{ default: () => React.ReactElement }>("./**/page.tsx", { eager: true })
).filter(([caminho]) => !caminho.startsWith("./guia/"));

describe("o guia abre de qualquer tela do Comitê", () => {
  it("o detector acha as telas do Comitê (piso)", () => {
    expect(TELAS.length).toBeGreaterThanOrEqual(5);
  });

  it.each(TELAS)("%s leva ao Guia do rito", (_caminho, modulo) => {
    const Tela = modulo.default;
    render(<Tela />);

    const link = screen.getByRole("link", { name: "Guia do rito" });
    expect(link.getAttribute("href")).toBe("/comite-de-conduta/guia");
  });
});

/** Toda área do Comitê, cada uma com o seu layout e o seu portão. */
const AREAS = Object.entries(
  import.meta.glob<{ default: (p: { children: React.ReactNode }) => Promise<React.ReactElement> }>("./**/layout.tsx", {
    eager: true,
  })
);

const TUDO_ABRE = {
  "/comite-de-conduta/minha-vez": 200,
  "/comite-de-conduta/membros": 200,
  "/comite-de-conduta/configuracoes": 200,
};

describe("os cinco cartões do primeiro acesso", () => {
  it("o detector acha as áreas do Comitê (piso)", () => {
    expect(AREAS.length).toBeGreaterThanOrEqual(4);
  });

  it.each(AREAS)("%s mostra os cinco cartões no primeiro acesso e marca a pessoa", async (_caminho, modulo) => {
    metadados.atual = { nome: "Ana" };
    portao = TUDO_ABRE;
    const Layout = modulo.default;

    render(await Layout({ children: <p>{CONTEUDO}</p> }));

    const dialogo = screen.getByRole("dialog", { name: "Bem-vindo ao Comitê de Conduta" });
    const titulos: string[] = [];
    for (let n = 1; n <= 5; n++) {
      expect(within(dialogo).getByText(`${n} de 5`)).toBeTruthy();
      titulos.push(within(dialogo).getByRole("heading", { level: 3 }).textContent ?? "");
      if (n < 5) fireEvent.click(within(dialogo).getByRole("button", { name: "Próximo" }));
    }
    expect(new Set(titulos).size).toBe(5);
    expect(within(dialogo).queryByRole("button", { name: "Próximo" })).toBeNull();

    expect(updateUser).toHaveBeenCalledTimes(1);
    expect(updateUser).toHaveBeenCalledWith({ data: { conduta_apresentacao_vista_em: expect.any(String) } });

    fireEvent.click(within(dialogo).getByRole("button", { name: "Começar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByText(CONTEUDO)).toBeTruthy();
  });

  it.each(AREAS)("%s não mostra os cartões a quem já os viu", async (_caminho, modulo) => {
    portao = TUDO_ABRE;
    const Layout = modulo.default;

    render(await Layout({ children: <p>{CONTEUDO}</p> }));

    expect(screen.getByText(CONTEUDO)).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(updateUser).not.toHaveBeenCalled();
  });
});
