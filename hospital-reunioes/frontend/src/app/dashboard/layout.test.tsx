/**
 * @vitest-environment jsdom
 */

/**
 * O painel de Reuniões depois que o login passou a cair no Início (issue
 * #1942, ADR 0104 decisão 1). O endereço continua `/dashboard` e as guardas de
 * hoje continuam: a Secretária vai para a tela dela e quem só tem POPs vai
 * para a lista de POPs.
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

import DashboardLayout from "./layout";

const PAINEL = "os cards do painel";

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

describe("o painel de Reuniões no endereço de hoje", () => {
  it("abre para o facilitador", async () => {
    comSessaoDe({ access_profile: "regular" });

    render(await DashboardLayout({ children: <p>{PAINEL}</p> }));

    expect(screen.getByText(PAINEL)).not.toBeNull();
    expect(redirect).not.toHaveBeenCalled();
  });

  it("segue mandando a Secretária para a tela dela", async () => {
    comSessaoDe({ access_profile: "secretaria" });

    await expect(DashboardLayout({ children: <p>{PAINEL}</p> })).rejects.toThrow(
      "redirect:/secretaria"
    );
  });

  it("segue mandando quem só tem POPs para a lista de POPs", async () => {
    comSessaoDe({ access_profile: null, perfil_pop: "coordenador" });

    await expect(DashboardLayout({ children: <p>{PAINEL}</p> })).rejects.toThrow(
      "redirect:/pops"
    );
  });
});
