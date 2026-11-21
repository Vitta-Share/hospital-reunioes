/**
 * @vitest-environment jsdom
 */

/**
 * As notas do Comitê de Conduta em Segurança do Paciente (issue #1850).
 *
 * Quem decide quem lê é o servidor (só a Presidência e o Acesso pleno). A
 * tela mostra o texto e a data do envio, da forma que vierem, e nada mais.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NotasDoComite } from "./NotasDoComite";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let corpo: unknown;
let urls: string[];

beforeEach(() => {
  urls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      urls.push(url);
      return { ok: true, status: 200, json: async () => corpo } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("as notas do Comitê de Conduta", () => {
  it("mostra cada nota com o texto e a data do envio, na ordem do servidor", async () => {
    corpo = {
      notas: [
        { id: "n2", texto: "Piso molhado sem sinalização na ala B.", enviada_em: "2026-11-21T13:00:00+00:00" },
        { id: "n1", texto: "Bomba de infusão com alarme desligado.", enviada_em: "2026-11-10T12:00:00+00:00" },
      ],
    };
    render(<NotasDoComite />);

    const lista = await screen.findByRole("list", { name: "Notas do Comitê de Conduta" });
    expect(within(lista).getAllByRole("listitem").map((l) => l.textContent)).toEqual([
      "Enviada em 21/11/2026Piso molhado sem sinalização na ala B.",
      "Enviada em 10/11/2026Bomba de infusão com alarme desligado.",
    ]);
    expect(urls).toEqual(["/api/nsp/notas-do-comite"]);
  });

  it("sem nota, diz que o Comitê ainda não mandou nenhuma", async () => {
    corpo = { notas: [] };
    render(<NotasDoComite />);

    expect(await screen.findByText("O Comitê de Conduta ainda não mandou nenhuma nota.")).toBeTruthy();
  });
});
