/**
 * @vitest-environment jsdom
 */

/**
 * A fila de triagem do Núcleo (issue #1992).
 *
 * A ordem é a do servidor (da mais antiga para a mais nova). A tela mostra o
 * protocolo, a faixa sugerida, o setor e o assunto, e leva à tela do caso. A
 * notificação sem sugestão aparece como "Classificar manualmente".
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FilaDeTriagem } from "./FilaDeTriagem";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

let corpo: unknown;

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => corpo }) as Response)
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const BASE = {
  criado_em: "2026-11-10T13:00:00+00:00",
  data_ocorrencia: "2026-11-09",
  setor: "UTI Adulto",
  grave_ou_morte: null,
  classificar_manualmente: false,
  cabe_no_lote: false,
};

describe("a fila de triagem", () => {
  it("mostra cada caso na ordem do servidor, com a faixa sugerida, e leva à tela do caso", async () => {
    corpo = {
      fila: [
        { ...BASE, id: "a", protocolo: "NSP-2026-0002", faixa: "A", assunto: "Queda com óbito" },
        { ...BASE, id: "b", protocolo: "NSP-2026-0005", faixa: "C", assunto: "Erro de dose" },
      ],
    };
    render(<FilaDeTriagem />);

    const itens = await screen.findAllByRole("listitem");
    expect(itens.map((i) => within(i).getByRole("link").textContent)).toEqual([
      expect.stringContaining("NSP-2026-0002"),
      expect.stringContaining("NSP-2026-0005"),
    ]);
    expect(within(itens[0]).getByText("Faixa A")).toBeTruthy();
    expect(within(itens[0]).getByText("Queda com óbito")).toBeTruthy();
    expect(within(itens[0]).getByText(/UTI Adulto/)).toBeTruthy();
    expect(within(itens[0]).getByRole("link").getAttribute("href")).toBe(
      "/seguranca-do-paciente/notificacoes/a/triagem"
    );
  });

  it("a notificação sem sugestão aparece para classificar manualmente", async () => {
    corpo = {
      fila: [{ ...BASE, id: "m", protocolo: "NSP-2026-0003", faixa: null, assunto: null, classificar_manualmente: true }],
    };
    render(<FilaDeTriagem />);

    expect(await screen.findByText("Classificar manualmente")).toBeTruthy();
  });

  it("sem nada esperando, diz que a fila está vazia", async () => {
    corpo = { fila: [] };
    render(<FilaDeTriagem />);

    expect(await screen.findByText("Nenhuma notificação esperando a triagem.")).toBeTruthy();
  });
});

describe("a aprovação em lote (issue #2002)", () => {
  const LEVES = [
    { ...BASE, id: "d", protocolo: "NSP-2026-0011", faixa: "D", assunto: "Alarme sem resposta", cabe_no_lote: true },
    { ...BASE, id: "e", protocolo: "NSP-2026-0012", faixa: "E", assunto: "Quase erro de dose", cabe_no_lote: true },
    { ...BASE, id: "c", protocolo: "NSP-2026-0013", faixa: "C", assunto: "Erro de dose", cabe_no_lote: false },
  ];

  it("com o lote desligado, a fila não mostra a confirmação em lote", async () => {
    corpo = { fila: LEVES, lote_ligado: false };
    render(<FilaDeTriagem />);

    await screen.findAllByRole("listitem");
    expect(screen.queryByRole("button", { name: /Confirmar em lote/ })).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("ligado, marca só os casos D e E e confirma os marcados de uma vez", async () => {
    corpo = { fila: LEVES, lote_ligado: true };
    render(<FilaDeTriagem />);

    await screen.findAllByRole("listitem");
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
    expect(screen.queryByRole("checkbox", { name: /NSP-2026-0013/ })).toBeNull();
    const botao = screen.getByRole("button", { name: /Confirmar em lote/ }) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);

    fireEvent.click(screen.getByRole("checkbox", { name: /NSP-2026-0011/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /NSP-2026-0012/ }));
    vi.mocked(fetch).mockImplementation(async (url) => {
      const resposta =
        url === "/api/nsp/triagem/lote"
          ? { confirmados: [{ id: "d", estado: "em_analise_agregada" }, { id: "e", estado: "em_analise_agregada" }] }
          : { fila: [LEVES[2]], lote_ligado: true };
      return { ok: true, status: 201, json: async () => resposta } as Response;
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar em lote (2)" }));

    expect(await screen.findByText("2 casos confirmados.")).toBeTruthy();
    const chamada = vi.mocked(fetch).mock.calls.find(([url]) => url === "/api/nsp/triagem/lote");
    expect(chamada?.[1]?.method).toBe("POST");
    expect(JSON.parse(String(chamada?.[1]?.body))).toEqual({ ids: ["d", "e"] });
    await waitFor(() => expect(screen.queryByText("NSP-2026-0011")).toBeNull());
  });

  it("a recusa do servidor aparece na fila e nada sai da lista", async () => {
    corpo = { fila: LEVES, lote_ligado: true };
    render(<FilaDeTriagem />);

    fireEvent.click(await screen.findByRole("checkbox", { name: /NSP-2026-0011/ }));
    vi.mocked(fetch).mockImplementation(
      async () =>
        ({
          ok: false,
          status: 422,
          json: async () => ({ detail: "O lote aceita só casos das faixas D e E. Confirme na tela de cada um: NSP-2026-0011." }),
        }) as Response
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirmar em lote (1)" }));

    expect((await screen.findByRole("alert")).textContent).toContain("NSP-2026-0011");
    expect(screen.getByText("NSP-2026-0011")).toBeTruthy();
  });
});
