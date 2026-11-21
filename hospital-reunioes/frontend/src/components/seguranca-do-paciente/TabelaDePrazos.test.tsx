/**
 * @vitest-environment jsdom
 */

/**
 * A tabela de prazos na Configuração do módulo (issue #1993). Os prazos
 * internos se editam por quem pode; os legais aparecem só para leitura; o
 * histórico diz quem mudou, quando, de e para. Quem recusa é o servidor.
 */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TabelaDePrazos } from "./TabelaDePrazos";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

function tabela(podeEditar: boolean) {
  return {
    faixas: ["A", "B", "C", "D", "E"],
    unidades: [
      { valor: "horas_corridas", rotulo: "horas corridas" },
      { valor: "horas_uteis", rotulo: "horas úteis" },
      { valor: "dias_corridos", rotulo: "dias corridos" },
      { valor: "dias_uteis", rotulo: "dias úteis" },
    ],
    internos: [
      { faixa: "A", marco: "triagem", rotulo: "Triagem e classificação", valor: 4, unidade: "horas_uteis", editavel: podeEditar },
      { faixa: "B", marco: "triagem", rotulo: "Triagem e classificação", valor: 1, unidade: "dias_uteis", editavel: podeEditar },
    ],
    legais: [
      {
        marco: "notificacao_externa",
        rotulo: "Notificação externa à vigilância sanitária",
        celulas: { A: "72 horas corridas do incidente", B: "Até o 15º dia útil do mês seguinte" },
        editavel: false,
      },
    ],
    historico: [
      {
        faixa: "C",
        marco: "triagem",
        rotulo: "Triagem e classificação",
        de: { valor: 2, unidade: "dias_uteis" },
        para: { valor: 1, unidade: "dias_uteis" },
        quem: "Presidência de Teste",
        quando: "2026-11-20T13:30:00+00:00",
      },
    ],
    pode_editar: podeEditar,
  };
}

const enviados: { url: string; corpo: unknown }[] = [];
let podeEditar = true;

beforeEach(() => {
  enviados.length = 0;
  podeEditar = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        const corpo = JSON.parse(String(init.body));
        enviados.push({ url, corpo });
        return { ok: true, status: 200, json: async () => corpo } as Response;
      }
      return { ok: true, status: 200, json: async () => tabela(podeEditar) } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("a tabela de prazos", () => {
  it("grava o prazo interno que a Presidência muda", async () => {
    render(<TabelaDePrazos />);

    const valor = (await screen.findByLabelText("Faixa A, Triagem e classificação")) as HTMLInputElement;
    expect(valor.value).toBe("4");
    fireEvent.change(valor, { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar Faixa A, Triagem e classificação" }));

    expect(await screen.findByText("Prazo salvo. Vale para os casos confirmados daqui para a frente.")).toBeTruthy();
    expect(enviados).toEqual([
      { url: "/api/nsp/configuracao/prazos/A/triagem", corpo: { valor: 2, unidade: "horas_uteis" } },
    ]);
  });

  it("mostra os prazos legais só para leitura", async () => {
    render(<TabelaDePrazos />);

    const legal = (await screen.findByText("Notificação externa à vigilância sanitária")).closest("section") as HTMLElement;
    expect(within(legal).getByText("72 horas corridas do incidente")).toBeTruthy();
    expect(within(legal).getByText(/Fixado pela norma/)).toBeTruthy();
    expect(within(legal).queryByRole("spinbutton")).toBeNull();
    expect(within(legal).queryByRole("button")).toBeNull();
  });

  it("mostra o histórico com quem, quando, de e para", async () => {
    render(<TabelaDePrazos />);

    const registro = (await screen.findByText(/Presidência de Teste/)).closest("li") as HTMLElement;
    expect(registro.textContent).toContain("20/11/2026, 10:30");
    expect(registro.textContent).toContain("Faixa C, Triagem e classificação");
    expect(registro.textContent).toContain("de 2 dias úteis para 1 dia útil");
  });

  it("quem só alcança a configuração lê a tabela sem campo para editar", async () => {
    podeEditar = false;
    render(<TabelaDePrazos />);

    expect(await screen.findAllByText("4 horas úteis")).toBeTruthy();
    expect(screen.queryByRole("spinbutton")).toBeNull();
    expect(screen.queryByRole("button", { name: /Salvar/ })).toBeNull();
  });
});
