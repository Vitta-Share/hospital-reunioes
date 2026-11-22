/**
 * @vitest-environment jsdom
 */

/**
 * A faixa "o que exige ação hoje" no início do módulo (issue #2000).
 *
 * Quem decide o conteúdo é o servidor. A tela mostra os quatro grupos com a
 * contagem e o link de cada item, o destaque do prazo perto do fim, e não
 * aparece (nem pergunta ao servidor) para quem não abre os casos.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AcaoDeHoje } from "./AcaoDeHoje";

const sessao: { participante: { recursos_nsp: string[] } | null } = { participante: null };

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante: sessao.participante, loading: false, error: null }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const CORPO = {
  grupos: [
    {
      chave: "casos_abertos",
      titulo: "Casos A e B abertos",
      link: "/seguranca-do-paciente/notificacoes",
      total: 2,
      ilegivel: false,
      itens: [
        { rotulo: "NSP-2026-0001, faixa A", link: "/seguranca-do-paciente/notificacoes/caso-1", urgente: false },
        { rotulo: "NSP-2026-0002, faixa B", link: "/seguranca-do-paciente/notificacoes/caso-2", urgente: false },
      ],
    },
    {
      chave: "triagens_pendentes",
      titulo: "Triagens pendentes",
      link: "/seguranca-do-paciente/notificacoes/triagem",
      total: 1,
      ilegivel: false,
      itens: [{ rotulo: "1 há mais de 3 dias", link: "/seguranca-do-paciente/notificacoes/triagem", urgente: true }],
    },
    {
      chave: "prazos_legais",
      titulo: "Prazos legais a vencer",
      link: "/seguranca-do-paciente/notificacoes",
      total: 1,
      ilegivel: false,
      itens: [
        {
          rotulo: "NSP-2026-0001, NOTIVISA em 72 horas: vence em 20/11/2026 às 08:00",
          link: "/seguranca-do-paciente/notificacoes/caso-1",
          urgente: true,
        },
      ],
    },
    {
      chave: "termos_pendentes",
      titulo: "Termos pendentes",
      link: "/seguranca-do-paciente/membros",
      total: null,
      ilegivel: true,
      itens: [],
    },
  ],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => CORPO }) as Response)
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessao.participante = null;
});

describe("a faixa o que exige ação hoje", () => {
  it("mostra os quatro grupos com a contagem e o link de cada item", async () => {
    sessao.participante = { recursos_nsp: ["ver_modulo", "casos"] };
    render(<AcaoDeHoje />);

    const faixa = await screen.findByRole("region", { name: "O que exige ação hoje" });
    const grupos = within(faixa).getAllByRole("group");
    expect(grupos.map((g) => g.getAttribute("aria-label"))).toEqual([
      "Casos A e B abertos",
      "Triagens pendentes",
      "Prazos legais a vencer",
      "Termos pendentes",
    ]);

    const casos = within(faixa).getByRole("group", { name: "Casos A e B abertos" });
    expect(within(casos).getByRole("link", { name: /Casos A e B abertos/ }).textContent).toContain("2");
    expect(within(casos).getByRole("link", { name: "NSP-2026-0002, faixa B" }).getAttribute("href")).toBe(
      "/seguranca-do-paciente/notificacoes/caso-2"
    );

    const triagens = within(faixa).getByRole("group", { name: "Triagens pendentes" });
    expect(within(triagens).getByRole("link", { name: /há mais de 3 dias/ }).getAttribute("href")).toBe(
      "/seguranca-do-paciente/notificacoes/triagem"
    );

    const termos = within(faixa).getByRole("group", { name: "Termos pendentes" });
    expect(within(termos).getByText("Não deu para ler agora. Recarregue a página.")).toBeTruthy();
    expect(within(termos).getByRole("link", { name: /Termos pendentes/ }).getAttribute("href")).toBe(
      "/seguranca-do-paciente/membros"
    );
  });

  it("destaca o prazo que vence em menos de 24 horas", async () => {
    sessao.participante = { recursos_nsp: ["ver_modulo", "casos"] };
    render(<AcaoDeHoje />);

    const prazos = await screen.findByRole("group", { name: "Prazos legais a vencer" });
    const prazo = within(prazos).getByRole("link", { name: /NOTIVISA em 72 horas/ });
    expect(within(prazo).getByLabelText("Urgente")).toBeTruthy();
    expect(prazo.getAttribute("href")).toBe("/seguranca-do-paciente/notificacoes/caso-1");

    const casos = screen.getByRole("group", { name: "Casos A e B abertos" });
    expect(within(casos).queryByLabelText("Urgente")).toBeNull();
  });

  it("quem não abre os casos não vê a faixa, e a tela nem pergunta ao servidor", async () => {
    sessao.participante = { recursos_nsp: ["ver_modulo", "painel", "casos_graves"] };
    const { container } = render(<AcaoDeHoje />);

    await new Promise((r) => setTimeout(r, 0));
    expect(fetch).not.toHaveBeenCalled();
    expect(container.textContent).toBe("");
  });
});
