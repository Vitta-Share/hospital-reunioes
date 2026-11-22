/**
 * @vitest-environment jsdom
 */

/**
 * A tela do link de uso único do Núcleo ao setor (issue #1996).
 *
 * O link abre sem senha e mostra o resumo do caso, com o botão "Recebido". O
 * uso único e a validade são do backend (410); aqui se prova que a tela
 * mostra o resumo, que abrir não confirma nada, que o clique chama a rota
 * certa e que o link acabado não oferece o botão.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RecebidoDoSetorPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "token-do-setor" }),
}));

const RESUMO = {
  protocolo: "NSP-2026-0001",
  destino: "Segurança do Trabalho",
  setor_que_recebe: "Segurança do Trabalho",
  destinatario_nome: "Responsável R1",
  setor_do_incidente: "UTI Adulto",
  data_ocorrencia: "2026-11-10",
  turno: "noite",
  motivo: "A técnica se feriu com a agulha ao descartar o material.",
};

const fetchMock = vi.fn();

function resposta(status: number, corpo: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => corpo };
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("o link do Recebido do setor", () => {
  it("abre o resumo do caso e o botão Recebido, sem confirmar nada", async () => {
    fetchMock.mockResolvedValueOnce(resposta(200, RESUMO));

    render(<RecebidoDoSetorPage />);

    expect(await screen.findByText("Notificação NSP-2026-0001")).toBeTruthy();
    expect(screen.getByText(RESUMO.motivo)).toBeTruthy();
    expect(screen.getByText("UTI Adulto")).toBeTruthy();
    expect(screen.getByText("10/11/2026, noite")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Recebido" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/nsp/recebimento/token-do-setor");
  });

  it("o clique em Recebido chama a rota do token e confirma", async () => {
    fetchMock.mockResolvedValueOnce(resposta(200, RESUMO));
    fetchMock.mockResolvedValueOnce(resposta(200, { recebido_em: "2026-11-10T17:30:00+00:00" }));
    render(<RecebidoDoSetorPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Recebido" }));

    expect(await screen.findByTestId("setor-recebido")).toBeTruthy();
    expect(fetchMock.mock.calls[1]).toEqual(["/api/nsp/recebimento/token-do-setor/recebido", { method: "POST" }]);
  });

  it("o link já usado ou vencido mostra a recusa do servidor, sem o botão", async () => {
    fetchMock.mockResolvedValueOnce(
      resposta(410, { detail: "Este link já foi usado: o recebimento deste caso já foi confirmado." })
    );

    render(<RecebidoDoSetorPage />);

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/já foi usado/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Recebido" })).toBeNull();
  });

  it("o segundo clique recusado tira o botão; a falha do servidor o deixa", async () => {
    fetchMock.mockResolvedValueOnce(resposta(200, RESUMO));
    fetchMock.mockResolvedValueOnce(resposta(503, { detail: "Não foi possível abrir o caso agora." }));
    render(<RecebidoDoSetorPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Recebido" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByRole("button", { name: "Recebido" })).toBeTruthy();

    fetchMock.mockResolvedValueOnce(resposta(410, { detail: "Este link já foi usado." }));
    fireEvent.click(screen.getByRole("button", { name: "Recebido" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Recebido" })).toBeNull());
  });
});
