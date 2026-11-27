/**
 * @vitest-environment jsdom
 */

/**
 * A etapa "ARQUIVAR PAPEL" e a guarda do caso (issue #1838; especificação,
 * 9.3 e 9.4). O servidor decide quem pode o quê; aqui se trava o que a tela
 * mostra: os originais esperados, o IMPRIMIR ETIQUETA que chama a rota do
 * PDF, o lacre com o local padrão já preenchido, o lacre registrado, o
 * CONGELAR CASO só para quem o servidor deixa e o caso eliminado.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { GuardaDoCaso } from "@/lib/conduta/guarda";

import { ArquivarPapel } from "./ArquivarPapel";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let chamadas: { url: string; metodo: string; corpo: unknown }[];

beforeEach(() => {
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, opcoes: RequestInit = {}) => {
      chamadas.push({ url, metodo: opcoes.method ?? "GET", corpo: opcoes.body ? JSON.parse(String(opcoes.body)) : null });
      return { ok: true, status: 200, json: async () => ({}), blob: async () => new Blob(["pdf"]) } as Response;
    })
  );
  vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:etiqueta", revokeObjectURL: () => undefined });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function guarda(trocas: Partial<GuardaDoCaso> = {}): GuardaDoCaso {
  return {
    encerrado: true,
    guardar_ate: "2031-11-10",
    vencida: false,
    originais: [
      { rotulo: "Termo de declaração, Acusado 1", situacao: "Assinado" },
      { rotulo: "Ciência do Código pelo acusado", situacao: "Aguardando" },
    ],
    lacre: null,
    local_padrao: "Cofre da Diretoria",
    pode_lacrar: true,
    pode_imprimir: true,
    congelado_em: null,
    pode_congelar: false,
    eliminado_em: null,
    ...trocas,
  };
}

function montar(dados: GuardaDoCaso, aoMudar = vi.fn()) {
  render(<ArquivarPapel casoId="caso-1" protocolo="CC-AB12-CD34" guarda={dados} aoMudar={aoMudar} />);
  return aoMudar;
}

describe("ArquivarPapel", () => {
  it("lista os originais esperados com a situação e a data da guarda", () => {
    montar(guarda());

    const lista = screen.getByRole("list", { name: "Originais esperados" });
    expect(lista.textContent).toContain("Termo de declaração, Acusado 1");
    expect(lista.textContent).toContain("Aguardando");
    expect(screen.getByText("Guardar até 10/11/2031.")).toBeTruthy();
  });

  it("IMPRIMIR ETIQUETA chama a rota do PDF do caso", async () => {
    montar(guarda());

    fireEvent.click(screen.getByRole("button", { name: "IMPRIMIR ETIQUETA" }));

    await waitFor(() => expect(chamadas.map((c) => c.url)).toEqual(["/api/comite-de-conduta/casos/caso-1/etiqueta"]));
  });

  it("o lacre vem com o local padrão e manda a data e o local", async () => {
    const aoMudar = montar(guarda());

    expect((screen.getByLabelText("Local de guarda") as HTMLInputElement).value).toBe("Cofre da Diretoria");
    fireEvent.change(screen.getByLabelText("Data do lacre"), { target: { value: "2026-11-12" } });
    fireEvent.click(screen.getByRole("button", { name: "REGISTRAR LACRE" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas).toEqual([
      {
        url: "/api/comite-de-conduta/casos/caso-1/lacre",
        metodo: "POST",
        corpo: { data: "2026-11-12", local: "Cofre da Diretoria" },
      },
    ]);
  });

  it("o lacre registrado mostra quem lacrou, a data e o local, sem o formulário", () => {
    montar(guarda({ lacre: { por: "Bruno Membro", em: "2026-11-12", local: "Cofre" }, pode_lacrar: false }));

    expect(screen.getByText("Lacrado por Bruno Membro em 12/11/2026. Local de guarda: Cofre.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "REGISTRAR LACRE" })).toBeNull();
  });

  it("CONGELAR CASO só aparece para quem o servidor deixa", () => {
    montar(guarda());

    expect(screen.queryByRole("button", { name: "CONGELAR CASO" })).toBeNull();
  });

  it("a coordenação congela e descongela", async () => {
    montar(guarda({ pode_congelar: true }));
    fireEvent.click(screen.getByRole("button", { name: "CONGELAR CASO" }));
    await waitFor(() => expect(chamadas.map((c) => c.url)).toEqual(["/api/comite-de-conduta/casos/caso-1/congelamento"]));
    cleanup();

    montar(guarda({ pode_congelar: true, congelado_em: "2026-11-20T12:00:00+00:00" }));
    expect(screen.getByRole("status").textContent).toContain("Caso congelado");
    fireEvent.click(screen.getByRole("button", { name: "DESCONGELAR" }));
    await waitFor(() => expect(chamadas.at(-1)?.url).toBe("/api/comite-de-conduta/casos/caso-1/descongelamento"));
  });

  it("o caso eliminado diz para eliminar o envelope e não oferece etiqueta nem lacre", () => {
    montar(guarda({ eliminado_em: "2031-11-12T10:40:00+00:00", pode_lacrar: false, pode_imprimir: false }));

    expect(screen.getByText(/foi eliminado em 12\/11\/2031, ao fim da guarda. Elimine o envelope/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "IMPRIMIR ETIQUETA" })).toBeNull();
    expect(screen.queryByRole("list", { name: "Originais esperados" })).toBeNull();
  });
});
