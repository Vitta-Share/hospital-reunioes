/**
 * @vitest-environment jsdom
 */

/**
 * A guarda da área do Comitê de Conduta sem sessão (issue #1825, revisão do
 * PR #2111).
 *
 * O convidado (apurador ou membro da CIPA) chega pelo link do e-mail do
 * convite e não tem item no menu. Se o login o jogasse no Início, ele não
 * teria como chegar ao caso. Então, sem sessão, o layout devolve o mesmo
 * encaminhador da Ouvidoria e do admin, que leva o endereço pedido ao login.
 *
 * O que não pode afrouxar: sem sessão, nada do Comitê chega ao navegador, e
 * com sessão quem decide quem entra segue sendo o portão do módulo.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getUser = vi.fn();
const getSession = vi.fn();
const replace = vi.fn();
const redirecionamentos: string[] = [];

/** O `redirect` do Next interrompe o fluxo lançando; o dublê faz o mesmo. */
class RedirecionouError extends Error {}

vi.mock("next/navigation", () => ({
  redirect: (destino: string) => {
    redirecionamentos.push(destino);
    throw new RedirecionouError(destino);
  },
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/supabase/server", () => ({
  createClient: async () => ({ auth: { getUser, getSession } }),
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/conduta/ApresentacaoDoComite", () => ({
  ApresentacaoDoComite: () => null,
}));

import ComiteDeCondutaLayout from "./layout";

const SEGREDO = "a lista de casos do Comitê";

async function montarEm(url: string) {
  window.history.replaceState({}, "", url);
  render(await ComiteDeCondutaLayout({ children: <p>{SEGREDO}</p> }));
}

beforeEach(() => {
  getUser.mockReset();
  getSession.mockReset();
  getSession.mockResolvedValue({ data: { session: { access_token: "token-de-teste" } } });
  replace.mockReset();
  redirecionamentos.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }))
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("a área do Comitê de Conduta sem sessão", () => {
  it("leva o link do e-mail do convite ao login com o retorno ao Comitê", async () => {
    getUser.mockResolvedValue({ data: { user: null } });

    await montarEm("/comite-de-conduta");

    expect(screen.queryByText(SEGREDO)).toBeNull();
    expect(redirecionamentos).toEqual([]);
    expect(replace).toHaveBeenCalledWith("/login?redirect=%2Fcomite-de-conduta");
  });

  it("leva o link de um caso ao login com o retorno ao caso", async () => {
    getUser.mockResolvedValue({ data: { user: null } });

    await montarEm("/comite-de-conduta/casos/c-1");

    expect(screen.queryByText(SEGREDO)).toBeNull();
    expect(replace).toHaveBeenCalledWith("/login?redirect=%2Fcomite-de-conduta%2Fcasos%2Fc-1");
  });

  it("com usuário mas sem token, também vai ao login com o retorno", async () => {
    getUser.mockResolvedValue({ data: { user: { id: "u1", email: "a@hsm.test" } } });
    getSession.mockResolvedValue({ data: { session: null } });

    await montarEm("/comite-de-conduta");

    expect(screen.queryByText(SEGREDO)).toBeNull();
    expect(replace).toHaveBeenCalledWith("/login?redirect=%2Fcomite-de-conduta");
  });
});

describe("a área do Comitê de Conduta com sessão", () => {
  beforeEach(() => {
    getUser.mockResolvedValue({
      data: { user: { id: "u1", email: "apurador@hsm.test", user_metadata: { nome: "Ana" } } },
    });
  });

  it("monta a área quando o portão do módulo deixa entrar", async () => {
    // Controle positivo: sem ele, uma guarda quebrada para o lado restritivo
    // deixaria os testes de cima verdes por motivo errado.
    await montarEm("/comite-de-conduta");

    expect(screen.getByText(SEGREDO)).not.toBeNull();
    expect(replace).not.toHaveBeenCalled();
  });

  it("devolve ao início quem o portão do módulo recusa", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 403, json: async () => ({}) }))
    );

    await expect(montarEm("/comite-de-conduta")).rejects.toBeInstanceOf(RedirecionouError);
    expect(redirecionamentos).toEqual(["/dashboard"]);
    expect(replace).not.toHaveBeenCalled();
  });
});
