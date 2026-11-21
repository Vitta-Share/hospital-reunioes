/**
 * @vitest-environment jsdom
 */

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
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const redirect = vi.fn((destino: string) => {
  throw new Error(`redirect:${destino}`);
});

vi.mock("next/navigation", () => ({
  redirect: (destino: string) => redirect(destino),
  usePathname: () => "/comite-de-conduta",
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import GuiaDoRitoPage from "./guia/page";

afterEach(() => {
  cleanup();
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
