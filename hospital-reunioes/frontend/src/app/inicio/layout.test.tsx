/**
 * @vitest-environment jsdom
 */

/**
 * Quem o Início recebe e quem ele devolve (issue #1942, ADR 0104 decisão 1).
 *
 * O login sem destino agora cai aqui, para todo mundo. A Secretária não tem
 * Início: ela volta para a tela dela, também quando digita o endereço. Quem só
 * tem POPs, Ouvidoria, Núcleo ou Contas médicas fica no Início, e não é
 * empurrado para o painel de Reuniões nem para a lista de POPs, como o
 * layout do `/dashboard` faz.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getUser = vi.fn();
const getSession = vi.fn();
const redirect = vi.fn((destino: string) => {
  throw new Error(`redirect:${destino}`);
});

vi.mock("next/navigation", () => ({
  redirect: (destino: string) => redirect(destino),
}));

vi.mock("@/lib/supabase/server", () => ({
  createClient: async () => ({ auth: { getUser, getSession } }),
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import InicioLayout from "./layout";

const FILA = "a Minha Fila";

function comSessaoDe(me: Record<string, unknown>) {
  getUser.mockResolvedValue({
    data: { user: { email: "pessoa@hsm.test", user_metadata: { nome: "Ana" } } },
  });
  getSession.mockResolvedValue({ data: { session: { access_token: "t" } } });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => me }))
  );
}

beforeEach(() => {
  getUser.mockReset();
  getSession.mockReset();
  redirect.mockClear();
  vi.unstubAllGlobals();
});

afterEach(() => {
  cleanup();
});

describe("o Início de quem chega pelo login", () => {
  it("devolve a Secretária à tela dela", async () => {
    comSessaoDe({ access_profile: "secretaria" });

    await expect(InicioLayout({ children: <p>{FILA}</p> })).rejects.toThrow(
      "redirect:/secretaria"
    );
  });

  it.each([
    ["quem só tem POPs", { access_profile: null, perfil_pop: "coordenador" }],
    ["quem só tem Ouvidoria", { access_profile: null, perfil_ouvidoria: "ouvidor" }],
    ["quem só tem o Núcleo", { access_profile: null, recursos_nsp: ["ver_modulo"] }],
    ["quem só tem Contas médicas", { access_profile: null, perfil_contas_medicas: "faturista" }],
    ["o facilitador", { access_profile: "regular" }],
  ])("deixa %s no Início", async (_quem, me) => {
    comSessaoDe(me);

    render(await InicioLayout({ children: <p>{FILA}</p> }));

    expect(screen.getByText(FILA)).not.toBeNull();
    expect(redirect).not.toHaveBeenCalled();
  });

  it("manda ao login quem não tem sessão", async () => {
    getUser.mockResolvedValue({ data: { user: null } });

    await expect(InicioLayout({ children: <p>{FILA}</p> })).rejects.toThrow(
      "redirect:/login"
    );
  });
});
