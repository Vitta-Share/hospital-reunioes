/**
 * @vitest-environment jsdom
 */

/**
 * Ação, Rotina e Processo na validação da Ata (issue #1872).
 *
 * O Facilitador troca o tipo e a frequência de cada linha do quadro. A troca
 * vai ao backend pelo PATCH da linha, com o valor que o backend aceita
 * (ACAO, ROTINA, PROCESSO; SEMANAL, QUINZENAL, MENSAL), e a frequência só
 * aparece na Rotina.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";
import { TipoDaLinhaInline } from "./TipoDaLinhaInline";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "tok" } } }),
    },
  }),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function responderCom(item: Record<string, unknown>) {
  const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => item }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderizar(valor: { tipo?: string | null; frequencia?: string | null }, onAtualizado = vi.fn()) {
  render(
    <ToastProvider>
      <TipoDaLinhaInline reuniaoId="R1" atribuicaoIndex={2} valorAtual={valor} onAtualizado={onAtualizado} />
    </ToastProvider>,
  );
  return onAtualizado;
}

describe("TipoDaLinhaInline", () => {
  it("linha sem tipo aparece como Ação e sem escolha de frequência", () => {
    renderizar({});

    expect((screen.getByLabelText("Tipo da linha 3") as HTMLSelectElement).value).toBe("ACAO");
    expect(screen.queryByLabelText("Frequência da linha 3")).toBeNull();
  });

  it("trocar para Rotina e escolher a frequência grava cada escolha na linha", async () => {
    const fetchMock = responderCom({ tipo: "ROTINA", frequencia: null });
    const onAtualizado = renderizar({ tipo: "ACAO" });

    fireEvent.change(screen.getByLabelText("Tipo da linha 3"), { target: { value: "ROTINA" } });

    await waitFor(() => expect(onAtualizado).toHaveBeenCalledWith({ tipo: "ROTINA", frequencia: null }));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/reunioes/R1/quadro-atribuicoes/2",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ tipo: "ROTINA" }) }),
    );

    cleanup();
    const fetchFreq = responderCom({ tipo: "ROTINA", frequencia: "QUINZENAL" });
    const onFreq = renderizar({ tipo: "ROTINA", frequencia: null });

    fireEvent.change(screen.getByLabelText("Frequência da linha 3"), { target: { value: "QUINZENAL" } });

    await waitFor(() => expect(onFreq).toHaveBeenCalledWith({ tipo: "ROTINA", frequencia: "QUINZENAL" }));
    expect(fetchFreq).toHaveBeenCalledWith(
      "/api/reunioes/R1/quadro-atribuicoes/2",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ frequencia: "QUINZENAL" }) }),
    );
  });
});
