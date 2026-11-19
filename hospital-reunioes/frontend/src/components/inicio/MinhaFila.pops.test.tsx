/**
 * @vitest-environment jsdom
 */

/**
 * O POP na etapa da pessoa, no Início (issue #1938, PRD #1932).
 *
 * O recorte e os dias vêm do servidor (`backend/tests/test_inicio_pops.py`).
 * Aqui se trava o que a pessoa vê: o POP no grupo "Sem prazo", no fim da
 * lista, com há quantos dias espera na etapa, e o botão que abre a etapa.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MinhaFila, type InicioDaPessoa, type ItemDoInicio } from "./MinhaFila";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const PENDENCIA: ItemDoInicio = {
  tipo: "pendencia",
  id: "A003",
  titulo: "Assinar a escala",
  origem: "Reunião de Atendimento, de 28/10/2026.",
  prazo: "2026-11-19",
  chegou_em: "2026-10-28",
  area: "Reuniões",
  acao: "Abrir a Pendência",
  destino: "/pendencias/kanban?highlight=A003",
  acao_de_um_clique: null,
  grupo: "ate_48_horas",
  dias_de_atraso: null,
};

const POP_EM_REVISAO: ItemDoInicio = {
  tipo: "pop",
  id: "POP002",
  titulo: "Higiene das mãos",
  origem: "HSM_ENF-002, versão 1.0, em revisão.",
  prazo: null,
  chegou_em: "2026-11-16",
  area: "POPs",
  acao: "Revisar",
  destino: "/pops/POP002/versao",
  acao_de_um_clique: null,
  grupo: "sem_prazo",
  dias_de_atraso: null,
  dias_esperando: 2,
};

const COM_POP: InicioDaPessoa = {
  hoje: "2026-11-18",
  frase: { titulo: "Rui, nada atrasado.", apoio: "Um prazo vence em até 48 horas." },
  contadores: { passou_do_prazo: 0, ate_48_horas: 1, proximos_7_dias: 0 },
  itens: [PENDENCIA, POP_EM_REVISAO],
  avisos: [],
  trilho: [],
  filas_do_papel: [],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(corpo: InicioDaPessoa) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => corpo }) as Response)
  );
  render(<MinhaFila />);
  await screen.findByText(corpo.frase.titulo);
}

describe("o POP na etapa da pessoa", () => {
  it("fica em Sem prazo, no fim, com os dias que espera e o botão da etapa", async () => {
    await abrir(COM_POP);

    const grupos = screen.getAllByRole("region").map((s) => s.getAttribute("aria-label"));
    expect(grupos).toEqual(["Vence em até 48 horas", "Sem prazo"]);

    const semPrazo = screen.getByRole("region", { name: "Sem prazo" });
    const linha = within(semPrazo).getByText("Higiene das mãos").closest("li") as HTMLElement;
    expect(within(linha).getByText("2").textContent).toBe("2");
    expect(within(linha).getByText("dias esperando")).toBeTruthy();
    expect(within(linha).getByText("HSM_ENF-002, versão 1.0, em revisão.")).toBeTruthy();
    expect(within(linha).getByRole("link", { name: "Revisar" }).getAttribute("href")).toBe("/pops/POP002/versao");
  });

  it("um dia só fica no singular", async () => {
    await abrir({ ...COM_POP, itens: [{ ...POP_EM_REVISAO, dias_esperando: 1 }] });

    expect(screen.getByText("dia esperando")).toBeTruthy();
  });
});
