/**
 * @vitest-environment jsdom
 */

/**
 * O destaque de caso grave no início do módulo (issue #1989).
 *
 * Quem decide quem vê é o servidor: o início só manda os casos graves a quem
 * abre os casos. A tela mostra o que vier, com protocolo, setor e hora, e o
 * caminho para Notificações. Sem caso grave, nada aparece.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CasosGraves } from "./CasosGraves";

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

describe("o destaque de caso grave", () => {
  it("mostra cada caso grave com protocolo, setor, hora e o caminho para Notificações", async () => {
    corpo = {
      casos_graves: [{ protocolo: "NSP-2026-0007", setor: "UTI Adulto", criado_em: "2026-11-14T06:00:00+00:00" }],
    };
    render(<CasosGraves />);

    const alerta = await screen.findByRole("alert");
    expect(within(alerta).getByText(/Caso grave ou com morte/)).toBeTruthy();
    const caso = within(alerta).getByRole("link", { name: /NSP-2026-0007/ });
    expect(caso.getAttribute("href")).toBe("/seguranca-do-paciente/notificacoes");
    expect(caso.textContent).toContain("UTI Adulto");
    expect(caso.textContent).toContain("14/11/2026 às 03:00");
  });

  it("sem caso grave, não mostra nada", async () => {
    corpo = { casos_graves: [] };
    const { container } = render(<CasosGraves />);

    await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
    expect(container.textContent).toBe("");
  });
});
