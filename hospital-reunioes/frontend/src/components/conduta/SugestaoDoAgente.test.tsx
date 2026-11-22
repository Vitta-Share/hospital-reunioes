/**
 * @vitest-environment jsdom
 */

/**
 * A sugestão do agente de triagem na tela do caso (issue #1827): cada item
 * marcado como Sugestão, com a justificativa à vista sem clique, e a
 * discordância que só sai com o motivo.
 */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SugestaoDoAgente as Sugestao } from "@/lib/conduta/sugestao";

import { SugestaoDoAgente } from "./SugestaoDoAgente";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let chamadas: { url: string; method: string; body: unknown }[];

beforeEach(() => {
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null });
      return { ok: true, status: 200, json: async () => ({ caso: {} }) } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ITEM = {
  item: "rito",
  titulo: "Rito",
  rotulo: "Sugestão",
  valor: "Rápido",
  justificativa: "Não há fato que leve a demissão por justa causa.",
  trecho: "grita comigo",
  resposta: null,
  motivo: null,
};

const SUGESTAO: Sugestao = {
  situacao: "sugerida",
  motivo: null,
  itens: [ITEM, { ...ITEM, item: "categoria", titulo: "Categoria", valor: "A. Conduta e relações", justificativa: "Humilhação repetida." }],
  pode_responder: true,
  possivel_impedimento: [],
};

describe("Sugestão do agente", () => {
  it("mostra cada item como Sugestão, com a justificativa e o trecho sem clique", () => {
    render(<SugestaoDoAgente casoId="c1" sugestao={SUGESTAO} aoResponder={() => {}} />);

    const rito = screen.getByRole("listitem", { name: "Rito" });
    expect(within(rito).getByText("Sugestão")).toBeTruthy();
    expect(within(rito).getByText("Rápido")).toBeTruthy();
    expect(within(rito).getByText("Por quê: Não há fato que leve a demissão por justa causa.")).toBeTruthy();
    expect(within(rito).getByText('Trecho do relato: "grita comigo"')).toBeTruthy();
    expect(screen.getAllByText("Sugestão")).toHaveLength(2);
  });

  it("discordar só grava com o motivo, e o motivo vai ao servidor", async () => {
    const aoResponder = vi.fn();
    render(<SugestaoDoAgente casoId="c1" sugestao={SUGESTAO} aoResponder={aoResponder} />);

    const rito = screen.getByRole("listitem", { name: "Rito" });
    fireEvent.click(within(rito).getByRole("button", { name: "DISCORDO" }));
    const gravar = within(rito).getByRole("button", { name: "GRAVAR DISCORDÂNCIA" }) as HTMLButtonElement;
    expect(gravar.disabled).toBe(true);

    fireEvent.change(within(rito).getByLabelText("Motivo da discordância, em uma linha"), {
      target: { value: "Há ameaça de demissão." },
    });
    expect(gravar.disabled).toBe(false);
    fireEvent.click(gravar);

    await vi.waitFor(() => expect(aoResponder).toHaveBeenCalled());
    expect(chamadas).toEqual([
      {
        url: "/api/comite-de-conduta/casos/c1/sugestao",
        method: "POST",
        body: { item: "rito", resposta: "discordo", motivo: "Há ameaça de demissão." },
      },
    ]);
  });

  it("sem a coordenação, não há botão de responder", () => {
    render(<SugestaoDoAgente casoId="c1" sugestao={{ ...SUGESTAO, pode_responder: false }} aoResponder={() => {}} />);

    expect(screen.queryByRole("button", { name: "CONFIRMO" })).toBeNull();
    expect(screen.getByText("Por quê: Humilhação repetida.")).toBeTruthy();
  });

  it("mostra a discordância gravada com o motivo", () => {
    const respondido = { ...SUGESTAO, itens: [{ ...ITEM, resposta: "discordo" as const, motivo: "Há ameaça." }] };
    render(<SugestaoDoAgente casoId="c1" sugestao={respondido} aoResponder={() => {}} />);

    expect(screen.getByText("A coordenação discordou: Há ameaça.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "DISCORDO" })).toBeNull();
  });

  it("sem sugestão, diz por quê", () => {
    const manual: Sugestao = {
      ...SUGESTAO,
      situacao: "manual",
      itens: [],
      motivo: "Sem sugestão do agente: o teto diário de leituras do agente foi atingido.",
    };
    render(<SugestaoDoAgente casoId="c1" sugestao={manual} aoResponder={() => {}} />);

    expect(screen.getByText("Sem sugestão do agente: o teto diário de leituras do agente foi atingido.")).toBeTruthy();
  });

  it("avisa o possível impedimento por nome", () => {
    const comNome = {
      ...SUGESTAO,
      possivel_impedimento: [{ membro: "Beatriz Albuquerque Mendes", motivo: "O nome aparece no relato." }],
    };
    render(<SugestaoDoAgente casoId="c1" sugestao={comNome} aoResponder={() => {}} />);

    const aviso = screen.getByRole("alert");
    expect(within(aviso).getByText("Possível impedimento")).toBeTruthy();
    expect(within(aviso).getByText("Beatriz Albuquerque Mendes: O nome aparece no relato.")).toBeTruthy();
  });
});
