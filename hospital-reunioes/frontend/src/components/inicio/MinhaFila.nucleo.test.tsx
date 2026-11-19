/**
 * @vitest-environment jsdom
 */

/**
 * O que o Núcleo espera da pessoa, no Início (issue #1939, PRD #1932).
 *
 * A capacitação com presença a confirmar é a primeira ação de um clique do
 * Início (ADR 0104, decisão 3): o botão chama a rota que o servidor mandou,
 * sem sair da tela, e o Início se recarrega, para a linha sair e a frase e os
 * contadores virem refeitos pelo servidor. Os itens do Núcleo não têm prazo e
 * ficam no grupo Sem prazo, com há quantos dias esperam.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const CAPACITACAO: ItemDoInicio = {
  tipo: "capacitacao",
  id: "CAP1",
  titulo: "Confirmar a presença na capacitação Higiene das mãos",
  origem: "Capacitação do Núcleo de 12/11/2026.",
  prazo: null,
  chegou_em: "2026-11-12",
  area: "Segurança do Paciente",
  acao: "Abrir as Capacitações",
  destino: "/seguranca-do-paciente/capacitacoes",
  acao_de_um_clique: { rotulo: "Confirmar presença", endpoint: "/api/nsp/capacitacoes/CAP1/presenca" },
  grupo: "sem_prazo",
  dias_de_atraso: null,
  dias_esperando: 6,
};

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

const ANTES: InicioDaPessoa = {
  hoje: "2026-11-18",
  frase: { titulo: "Marcos, um prazo seu venceu.", apoio: "Ele espera há 9 dias." },
  contadores: { passou_do_prazo: 1, ate_48_horas: 0, proximos_7_dias: 0 },
  itens: [VENCIDA, CAPACITACAO],
  avisos: [],
  trilho: [],
  filas_do_papel: [],
};

// O que o servidor devolve depois do clique: a capacitação saiu, e a frase e
// os contadores vêm refeitos (aqui, a Pendência também foi entregue em outra aba).
const DEPOIS: InicioDaPessoa = {
  ...ANTES,
  frase: { titulo: "Marcos, você está em dia.", apoio: "Nenhum prazo aberto no seu nome." },
  contadores: { passou_do_prazo: 0, ate_48_horas: 0, proximos_7_dias: 0 },
  itens: [],
};

interface Chamada {
  url: string;
  metodo: string;
  autorizacao: string | null;
}

function servidor({ presenca = 200 }: { presenca?: number } = {}) {
  const chamadas: Chamada[] = [];
  let confirmada = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const metodo = init?.method ?? "GET";
      const cabecalhos = new Headers(init?.headers);
      chamadas.push({ url, metodo, autorizacao: cabecalhos.get("Authorization") });
      if (url === "/api/inicio") {
        return { ok: true, status: 200, json: async () => (confirmada ? DEPOIS : ANTES) } as Response;
      }
      if (presenca < 300) confirmada = true;
      return { ok: presenca < 300, status: presenca, json: async () => ({}) } as Response;
    })
  );
  return chamadas;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Início, o que o Núcleo espera da pessoa", () => {
  it("mostra o item do Núcleo no grupo Sem prazo, com há quantos dias espera", async () => {
    servidor();
    render(<MinhaFila />);

    const grupo = await screen.findByRole("region", { name: "Sem prazo" });
    const linha = within(grupo).getByText(CAPACITACAO.titulo).closest("li")!;
    expect(within(linha).getByText("6")).toBeTruthy();
    expect(within(linha).getByText("dias esperando")).toBeTruthy();
  });

  it("a capacitação tem o botão Confirmar presença, e não o link para outra tela", async () => {
    servidor();
    render(<MinhaFila />);

    const linha = (await screen.findByText(CAPACITACAO.titulo)).closest("li")!;
    expect(within(linha).getByRole("button", { name: /Confirmar presença/ })).toBeTruthy();
    expect(within(linha).queryByRole("link")).toBeNull();
  });

  it("confirmar a presença resolve sem sair do Início: a linha sai e a frase e os contadores se refazem", async () => {
    const chamadas = servidor();
    render(<MinhaFila />);

    fireEvent.click(await screen.findByRole("button", { name: /Confirmar presença/ }));

    await waitFor(() => expect(screen.queryByText(CAPACITACAO.titulo)).toBeNull());
    expect(screen.getByText("Marcos, você está em dia.")).toBeTruthy();
    const resumo = screen.getByRole("list", { name: "Resumo dos prazos" });
    expect(within(resumo).getAllByText("0")).toHaveLength(3);
    expect(chamadas.map((c) => `${c.metodo} ${c.url}`)).toEqual([
      "GET /api/inicio",
      "POST /api/nsp/capacitacoes/CAP1/presenca",
      "GET /api/inicio",
    ]);
    expect(chamadas[1].autorizacao).toBe("Bearer token-de-teste");
  });

  it("se a confirmação falha, a linha fica e a tela diz o que houve", async () => {
    const chamadas = servidor({ presenca: 409 });
    render(<MinhaFila />);

    fireEvent.click(await screen.findByRole("button", { name: /Confirmar presença/ }));

    const linha = (await screen.findByText(CAPACITACAO.titulo)).closest("li")!;
    expect(await within(linha).findByRole("alert")).toBeTruthy();
    expect(within(linha).getByRole("alert").textContent).toBe("Não deu para confirmar agora. Tente de novo.");
    expect(chamadas.filter((c) => c.url === "/api/inicio")).toHaveLength(1);
  });
});
