/**
 * @vitest-environment jsdom
 */

/**
 * A tela da Pendência mostra o histórico e pede anotação em toda ação
 * (issue #1862, ADR 0098, decisão 5).
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AcoesDaPendencia } from "./AcoesDaPendencia";

const HISTORICO = {
  eventos: [
    {
      id: 1,
      comando: "iniciar",
      anotacao: "Comecei a cotação",
      autor_nome: "Rita Souza",
      criado_em: "2026-11-10T13:05:00+00:00",
      conta_atraso: false,
    },
    {
      id: 2,
      comando: "repactuar",
      anotacao: "Fornecedor atrasou",
      autor_nome: "Fábio Lima",
      prazo_antes: "2026-11-12",
      prazo_depois: "2026-11-30",
      criado_em: "2026-11-14T18:40:00+00:00",
      conta_atraso: true,
    },
  ],
  acoes_permitidas: ["anotar", "concluir", "repactuar"],
};

let chamadas: { url: string; init?: RequestInit }[] = [];

beforeEach(() => {
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, init });
      if (init?.method === "POST") {
        return new Response(JSON.stringify({ id_acao: "A001", status: "CONCLUIDO" }), { status: 200 });
      }
      return new Response(JSON.stringify(HISTORICO), { status: 200 });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function montar(onAtualizada = vi.fn()) {
  render(<AcoesDaPendencia idAcao="A001" token="tk" onAtualizada={onAtualizada} />);
  return onAtualizada;
}

describe("histórico da pendência", () => {
  it("mostra cada evento em ordem, com quem, quando e a anotação", async () => {
    montar();

    const lista = await screen.findByRole("list", { name: "Histórico da pendência" });
    const itens = within(lista).getAllByRole("listitem");
    expect(itens).toHaveLength(2);
    expect(itens[0].textContent).toContain("Iniciou");
    expect(itens[0].textContent).toContain("Rita Souza");
    expect(itens[0].textContent).toContain("10/11/2026");
    expect(itens[0].textContent).toContain("Comecei a cotação");
    expect(itens[1].textContent).toContain("Repactuou");
    expect(itens[1].textContent).toContain("30/11/2026");
    expect(itens[1].textContent).toContain("Depois do vencimento");
  });

  it("mostra só as ações que quem olha pode fazer", async () => {
    montar();

    await screen.findByRole("button", { name: "Concluir" });
    expect(screen.queryByRole("button", { name: "Cancelar pendência" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reabrir" })).toBeNull();
  });
});

describe("toda ação pede anotação", () => {
  it.each(["Anotar", "Concluir", "Repactuar"])("%s só confirma com anotação escrita", async (rotulo) => {
    montar();

    fireEvent.click(await screen.findByRole("button", { name: rotulo }));
    const confirmar = screen.getByRole("button", { name: "Confirmar" });
    expect((confirmar as HTMLButtonElement).disabled).toBe(true);

    // Com o prazo preenchido (quando a ação pede), ainda falta a anotação.
    const prazo = screen.queryByLabelText("Prazo novo");
    if (prazo) fireEvent.change(prazo, { target: { value: "2026-12-20" } });
    expect((confirmar as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(screen.getByLabelText("Anotação (obrigatória)"), { target: { value: "   " } });
    expect((confirmar as HTMLButtonElement).disabled).toBe(true);
  });

  it("concluir manda a anotação e devolve a pendência atualizada", async () => {
    const onAtualizada = montar();

    fireEvent.click(await screen.findByRole("button", { name: "Concluir" }));
    fireEvent.change(screen.getByLabelText("Anotação (obrigatória)"), { target: { value: "Entregue ao setor" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(onAtualizada).toHaveBeenCalledWith({ id_acao: "A001", status: "CONCLUIDO" }));
    const post = chamadas.find((c) => c.init?.method === "POST");
    expect(post?.url).toBe("/api/pendencias/A001/acoes");
    expect(JSON.parse(String(post?.init?.body))).toEqual({ comando: "concluir", anotacao: "Entregue ao setor" });
  });

  it("repactuar pede o prazo novo além da anotação", async () => {
    montar();

    fireEvent.click(await screen.findByRole("button", { name: "Repactuar" }));
    fireEvent.change(screen.getByLabelText("Anotação (obrigatória)"), { target: { value: "Fornecedor" } });
    const confirmar = screen.getByRole("button", { name: "Confirmar" }) as HTMLButtonElement;
    expect(confirmar.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText("Prazo novo"), { target: { value: "2026-12-20" } });
    expect(confirmar.disabled).toBe(false);
    fireEvent.click(confirmar);

    await waitFor(() => expect(chamadas.some((c) => c.init?.method === "POST")).toBe(true));
    const post = chamadas.find((c) => c.init?.method === "POST");
    expect(JSON.parse(String(post?.init?.body))).toEqual({
      comando: "repactuar",
      anotacao: "Fornecedor",
      prazo: "2026-12-20",
    });
  });
});
