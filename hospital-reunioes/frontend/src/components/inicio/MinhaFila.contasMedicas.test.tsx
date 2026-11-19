/**
 * @vitest-environment jsdom
 */

/**
 * As contas médicas no Início (issue #1940, PRD #1932, ADR 0104).
 *
 * A conta com a faturista não tem prazo no módulo: vem do servidor no grupo
 * Sem prazo, que fica no fim da fila e mostra há quantos dias a conta espera.
 * As contas sem dono são de um papel, não da pessoa: aparecem como uma linha
 * da Fila do papel, num bloco à parte, fora dos grupos. A regra de quem vê o
 * quê mora em `backend/tests/test_inicio_contas_medicas.py`.
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

const VENCIDA: ItemDoInicio = {
  tipo: "pendencia",
  id: "A001",
  titulo: "Treinar a equipe da noite",
  origem: "Reunião de Atendimento, de 28/10/2026.",
  prazo: "2026-11-09",
  chegou_em: "2026-10-28",
  area: "Reuniões",
  acao: "Abrir a Pendência",
  destino: "/pendencias/kanban?highlight=A001",
  acao_de_um_clique: null,
  grupo: "passou_do_prazo",
  dias_de_atraso: 9,
};

const CONTA: ItemDoInicio = {
  tipo: "conta_medica",
  id: "C001",
  titulo: "Atendimento 123456, conta 9001",
  origem: "Contas médicas, em correção.",
  prazo: null,
  chegou_em: "2026-11-13",
  area: "Contas médicas",
  acao: "Abrir o Guia",
  destino: "/contas-medicas/guia/C001",
  acao_de_um_clique: null,
  grupo: "sem_prazo",
  dias_de_atraso: null,
  dias_esperando: 5,
};

const FILA_DE_CONTAS = {
  fila: "contas_medicas",
  titulo: "Fila de contas",
  esperam: 3,
  vencidas: 0,
  resumo: "3 contas sem dono esperam na Fila.",
  destino: "/contas-medicas",
};

const DA_FATURISTA: InicioDaPessoa = {
  hoje: "2026-11-18",
  frase: { titulo: "Fátima, um prazo seu venceu.", apoio: "Ele espera há 9 dias." },
  contadores: { passou_do_prazo: 1, ate_48_horas: 0, proximos_7_dias: 0 },
  itens: [VENCIDA, CONTA],
  avisos: [],
  trilho: [],
  filas_do_papel: [FILA_DE_CONTAS],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(corpo: InicioDaPessoa = DA_FATURISTA) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => corpo }) as Response)
  );
  const tela = render(<MinhaFila />);
  await screen.findByText(corpo.frase.titulo);
  return tela;
}

describe("a conta com a faturista (issue #1940)", () => {
  it("aparece em Sem prazo, no fim, com os dias de espera e o botão para o Guia", async () => {
    await abrir();

    const grupos = screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"));
    expect(grupos.indexOf("Sem prazo")).toBeGreaterThan(grupos.indexOf("Passou do prazo"));
    const semPrazo = screen.getByRole("region", { name: "Sem prazo" });
    const linha = within(semPrazo).getByText("Atendimento 123456, conta 9001").closest("li") as HTMLElement;
    // O número tem elemento próprio, ao lado do rótulo: o 5 do título não conta.
    const numero = within(linha).getByText("5");
    expect(numero.nextElementSibling?.textContent).toBe("dias esperando");
    expect(within(linha).getByRole("link", { name: "Abrir o Guia" }).getAttribute("href")).toBe(
      "/contas-medicas/guia/C001"
    );
  });
});

describe("a Fila do papel (issue #1940)", () => {
  it("mostra a linha das contas sem dono num bloco à parte, com o link para a fila", async () => {
    await abrir();

    const bloco = screen.getByRole("region", { name: "Fila do papel" });
    const [linha] = within(bloco).getAllByRole("listitem");
    expect(linha.textContent).toContain("Fila de contas");
    expect(linha.textContent).toContain("3 contas sem dono esperam na Fila.");
    expect(within(linha).getByRole("link", { name: "Abrir a fila" }).getAttribute("href")).toBe("/contas-medicas");
  });

  it("a linha não entra nos grupos da Minha Fila", async () => {
    await abrir();

    for (const nome of ["Passou do prazo", "Sem prazo"]) {
      expect(within(screen.getByRole("region", { name: nome })).queryByText("Fila de contas")).toBeNull();
    }
  });

  it("sem fila do papel, o bloco não aparece", async () => {
    await abrir({ ...DA_FATURISTA, filas_do_papel: [] });

    expect(screen.queryByRole("region", { name: "Fila do papel" })).toBeNull();
  });
});
