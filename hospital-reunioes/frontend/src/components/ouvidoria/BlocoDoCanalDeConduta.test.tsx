/**
 * @vitest-environment jsdom
 */

/**
 * A sinalização ao Canal de Conduta no Dossiê (issue #1849, ADR 0097 decisão 14).
 *
 * O botão Sinalizar ao Canal de Conduta fica no Dossiê, que só quem tem o
 * Perfil da Ouvidoria abre. Ele pede uma confirmação antes, porque o Comitê
 * recebe o relato integral. Depois de sinalizado, o bloco diz isso e o botão
 * some. A régua é do backend; aqui se prova o que a tela mostra e a rota que o
 * botão chama.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BlocoDoCanalDeConduta } from "./BlocoDoCanalDeConduta";

const fetchMock = vi.fn();

afterEach(() => {
  cleanup();
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

function montar(caso: Record<string, unknown>, onSinalizado = vi.fn()) {
  vi.stubGlobal("fetch", fetchMock);
  render(
    <BlocoDoCanalDeConduta
      caso={{ id: "uuid-31", conduta_sinalizada_em: null, ...caso } as never}
      token="t"
      onSinalizado={onSinalizado}
    />,
  );
  return onSinalizado;
}

describe("a sinalização ao Canal de Conduta no Dossiê", () => {
  it("o botão aparece no caso que ainda não foi sinalizado", () => {
    montar({});

    expect(screen.getByRole("button", { name: "Sinalizar ao Canal de Conduta" })).toBeTruthy();
  });

  it("confirmar chama a rota da manifestação e avisa o Dossiê", async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({}) });
    const onSinalizado = montar({});

    fireEvent.click(screen.getByRole("button", { name: "Sinalizar ao Canal de Conduta" }));
    expect(screen.getByText(/sem o nome nem o contato de quem manifestou/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar sinalização" }));

    await waitFor(() => expect(onSinalizado).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/ouvidoria/manifestacoes/uuid-31/canal-de-conduta",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("o caso já sinalizado mostra o aviso e não mostra o botão", () => {
    montar({ conduta_sinalizada_em: "2026-11-20T14:00:00+00:00" });

    expect(screen.getByTestId("sinalizado-ao-canal").textContent).toContain(
      "Sinalizado ao Canal de Conduta",
    );
    expect(screen.queryByRole("button", { name: "Sinalizar ao Canal de Conduta" })).toBeNull();
  });

  it("a recusa do servidor aparece na tela", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Este caso já foi sinalizado ao Canal de Conduta." }),
    });
    const onSinalizado = montar({});

    fireEvent.click(screen.getByRole("button", { name: "Sinalizar ao Canal de Conduta" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar sinalização" }));

    expect((await screen.findByRole("alert")).textContent).toContain("já foi sinalizado");
    expect(onSinalizado).not.toHaveBeenCalled();
  });
});
