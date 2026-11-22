/**
 * @vitest-environment jsdom
 */

/**
 * Os anexos do relato na tela do caso (issue #1844). Quem não abre o caso nem
 * recebe a lista (o portão do servidor); aqui se trava que cada anexo aparece
 * com o tipo e a data, sem nome de arquivo, e que abrir chama a rota do
 * backend, nunca uma URL do bucket.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AnexoDoRelato } from "@/lib/conduta/anexos";

import { AnexosDoRelato } from "./AnexosDoRelato";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let chamadas: { url: string; init?: RequestInit }[];
let abertos: string[];

beforeEach(() => {
  chamadas = [];
  abertos = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, init });
      return { ok: true, status: 200, blob: async () => new Blob(["x"]) } as Response;
    })
  );
  vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:anexo", revokeObjectURL: () => undefined });
  vi.stubGlobal("open", (endereco: string) => {
    abertos.push(endereco);
    return null;
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ANEXOS: AnexoDoRelato[] = [
  { id: "a1", tipo: "imagem", origem: "relato", enviado_em: "2026-11-20T13:00:00+00:00" },
  { id: "a2", tipo: "audio", origem: "relato", enviado_em: "2026-11-20T13:01:00+00:00" },
];

describe("os anexos do relato", () => {
  it("lista cada anexo com o tipo e a data", () => {
    render(<AnexosDoRelato casoId="c1" anexos={ANEXOS} />);

    const itens = within(screen.getByRole("list", { name: "Anexos do relato" })).getAllByRole("listitem");
    expect(itens).toHaveLength(2);
    expect(itens[0].textContent).toContain("Imagem");
    expect(itens[0].textContent).toContain("20/11/2026");
    expect(itens[1].textContent).toContain("Áudio");
  });

  it("abrir chama a rota do caso no backend, com o login", async () => {
    render(<AnexosDoRelato casoId="c1" anexos={ANEXOS} />);

    fireEvent.click(screen.getAllByRole("button", { name: /Abrir/ })[0]);

    await waitFor(() => expect(abertos).toEqual(["blob:anexo"]));
    expect(chamadas[0].url).toBe("/api/comite-de-conduta/casos/c1/anexos/a1");
    expect((chamadas[0].init?.headers as Record<string, string>).Authorization).toBe("Bearer token-de-teste");
  });

  it("o anexo que veio pelo complemento aparece marcado como complemento (issue #2187)", () => {
    const comComplemento: AnexoDoRelato[] = [
      ...ANEXOS,
      { id: "a3", tipo: "pdf", origem: "complemento", enviado_em: "2026-11-21T13:00:00+00:00" },
    ];

    render(<AnexosDoRelato casoId="c1" anexos={comComplemento} />);

    const itens = within(screen.getByRole("list", { name: "Anexos do relato" })).getAllByRole("listitem");
    expect(itens[2].textContent).toContain("(complemento)");
    expect(itens[0].textContent).not.toContain("complemento");
    expect(itens[1].textContent).not.toContain("complemento");
  });

  it("sem anexo, não mostra nada", () => {
    const { container } = render(<AnexosDoRelato casoId="c1" anexos={[]} />);

    expect(container.textContent).toBe("");
  });
});
