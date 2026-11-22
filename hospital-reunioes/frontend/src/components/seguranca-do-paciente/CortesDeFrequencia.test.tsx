/**
 * @vitest-environment jsdom
 */

/**
 * Os cortes de frequência na Configuração do módulo (issue #1992). A tela
 * mostra os cortes que valem e grava os novos; quem confere a ordem é o
 * servidor, e a recusa aparece na tela. Quem edita também é o servidor que
 * diz (`pode_editar`, issue #2154): sem ele, os cortes ficam só para leitura.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CortesDeFrequencia } from "./CortesDeFrequencia";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const PADRAO = { janela_meses: 12, incomum_a_partir: 1, ocasional_a_partir: 2, frequente_a_partir: 4 };
const enviados: unknown[] = [];
let recusar = false;
let podeEditar = true;

beforeEach(() => {
  enviados.length = 0;
  recusar = false;
  podeEditar = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        const corpo = JSON.parse(String(init.body));
        enviados.push(corpo);
        if (recusar) {
          return { ok: false, status: 422, json: async () => ({ detail: "Os cortes crescem." }) } as Response;
        }
        return { ok: true, status: 200, json: async () => corpo } as Response;
      }
      return { ok: true, status: 200, json: async () => ({ ...PADRAO, pode_editar: podeEditar }) } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("os cortes de frequência", () => {
  it("mostram os cortes que valem e gravam os novos", async () => {
    render(<CortesDeFrequencia />);

    const ocasional = (await screen.findByLabelText("Ocasional a partir de")) as HTMLInputElement;
    expect(ocasional.value).toBe("2");
    expect((screen.getByLabelText("Janela, em meses") as HTMLInputElement).value).toBe("12");

    fireEvent.change(ocasional, { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar os cortes" }));

    expect(await screen.findByText("Cortes salvos.")).toBeTruthy();
    expect(enviados).toEqual([{ ...PADRAO, ocasional_a_partir: 3 }]);
  });

  it("mostram a recusa do servidor", async () => {
    recusar = true;
    render(<CortesDeFrequencia />);

    await screen.findByLabelText("Ocasional a partir de");
    fireEvent.click(screen.getByRole("button", { name: "Salvar os cortes" }));

    expect(await screen.findByText("Os cortes crescem.")).toBeTruthy();
  });

  it("ficam só para leitura, sem o Salvar, para quem não pode editar", async () => {
    podeEditar = false;
    render(<CortesDeFrequencia />);

    const ocasional = (await screen.findByLabelText("Ocasional a partir de")) as HTMLInputElement;
    expect(ocasional.value).toBe("2");
    expect(ocasional.readOnly).toBe(true);
    expect(screen.queryByRole("button", { name: "Salvar os cortes" })).toBeNull();
    expect(screen.getByText("Só a Presidência e o Acesso pleno alteram os cortes.")).toBeTruthy();
  });
});
