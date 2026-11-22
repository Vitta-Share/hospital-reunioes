/**
 * @vitest-environment jsdom
 */

/**
 * A verificação de retaliação na tela do caso (issue #1839): a resposta de um
 * clique com observação opcional e, quando houve, o caso novo de retaliação.
 * O servidor decide o que vale; aqui se trava o que a tela pede a ele.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MarcoDaVerificacao, VerificacaoDeRetaliacao as Dados } from "@/lib/conduta/retaliacao";

import { VerificacaoDeRetaliacao } from "./VerificacaoDeRetaliacao";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let chamadas: { url: string; method: string; body: unknown }[];
let resposta: unknown;

beforeEach(() => {
  chamadas = [];
  resposta = { ok: true };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null });
      return { ok: true, status: 200, json: async () => resposta } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function marco(m: 30 | 90 | 180, trocas: Partial<MarcoDaVerificacao> = {}): MarcoDaVerificacao {
  return {
    marco: m,
    data: "2026-12-20",
    situacao: "aguardando",
    houve: null,
    observacao: null,
    verificada_por: null,
    verificada_em: null,
    caso_novo: null,
    pode_abrir_caso_novo: false,
    ...trocas,
  };
}

const PENDENTE: Dados = {
  marcos: [marco(30, { situacao: "pendente" }), marco(90), marco(180)],
  marco_pendente: 30,
  pode_registrar: true,
};

function montar(dados: Dados = PENDENTE, registrando = true) {
  const aoMudar = vi.fn();
  render(<VerificacaoDeRetaliacao casoId="caso-1" dados={dados} registrando={registrando} aoMudar={aoMudar} />);
  return aoMudar;
}

describe("VerificacaoDeRetaliacao", () => {
  it("registra com um clique, sem observação", async () => {
    const aoMudar = montar();

    fireEvent.click(screen.getByRole("button", { name: "Não houve" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas).toEqual([
      {
        url: "/api/comite-de-conduta/casos/caso-1/verificacoes-de-retaliacao",
        method: "POST",
        body: { marco: 30, houve: false, observacao: "" },
      },
    ]);
  });

  it("leva a observação junto do clique em Houve", async () => {
    montar();

    fireEvent.change(screen.getByLabelText("Observação (opcional)"), { target: { value: "Trocada de escala." } });
    fireEvent.click(screen.getByRole("button", { name: "Houve" }));

    await waitFor(() => expect(chamadas).toHaveLength(1));
    expect(chamadas[0].body).toEqual({ marco: 30, houve: true, observacao: "Trocada de escala." });
  });

  it("sem o toque no botão da caixa, ou sem poder registrar, não mostra a resposta", () => {
    montar(PENDENTE, false);
    expect(screen.queryByRole("button", { name: "Houve" })).toBeNull();
    cleanup();

    montar({ ...PENDENTE, pode_registrar: false });
    expect(screen.queryByRole("button", { name: "Houve" })).toBeNull();
  });

  it("quando houve, oferece abrir o caso novo de retaliação e mostra o protocolo dele", async () => {
    resposta = { id: "caso-2", protocolo: "CC-ABCD-EFGH" };
    montar({
      marcos: [
        marco(30, { situacao: "verificada", houve: true, verificada_por: "Ana Coordenadora", pode_abrir_caso_novo: true }),
        marco(90),
        marco(180),
      ],
      marco_pendente: null,
      pode_registrar: false,
    });

    fireEvent.click(screen.getByRole("button", { name: "ABRIR CASO DE RETALIAÇÃO" }));

    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("CC-ABCD-EFGH"));
    expect(chamadas[0]).toEqual({
      url: "/api/comite-de-conduta/casos/caso-1/verificacoes-de-retaliacao/caso-novo",
      method: "POST",
      body: { marco: 30 },
    });
  });

  it("sem a verificação, não mostra nada", () => {
    const { container } = render(
      <VerificacaoDeRetaliacao casoId="caso-1" dados={null} registrando={false} aoMudar={vi.fn()} />
    );

    expect(container.innerHTML).toBe("");
  });
});
