/**
 * @vitest-environment jsdom
 */

/**
 * A trilha do caso com as gavetas e o Dossiê (issue #1837; especificação, 9.1
 * e 9.2). O servidor decide quem baixa e o que vale; aqui se trava o que a
 * tela mostra: cada ato e documento com autor, data, origem e código, as
 * gavetas com a situação, a conferência da cadeia e o BAIXAR DOSSIÊ só para
 * quem pode, que chama a rota do pacote.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TrilhaDoCaso as Trilha } from "@/lib/conduta/trilha";

import { TrilhaDoCaso } from "./TrilhaDoCaso";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let chamadas: string[];

beforeEach(() => {
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      chamadas.push(url);
      return { ok: true, status: 200, blob: async () => new Blob(["zip"]) } as Response;
    })
  );
  vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:dossie", revokeObjectURL: () => undefined });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CODIGO = "a".repeat(64);

function trilha(trocas: Partial<Trilha> = {}): Trilha {
  return {
    linha_do_tempo: [
      {
        tipo: "ato",
        acao: "adicionou_pessoa_a_ouvir",
        titulo: "pessoa a ouvir: Acusado",
        autor: "Ana Coordenadora",
        data: "2026-11-20T13:00:00+00:00",
        origem: "Aplicação",
        codigo: "b".repeat(64),
        versao: null,
      },
      {
        tipo: "ato",
        acao: "leitura",
        titulo: "abriu o caso",
        autor: "Lia Leitora",
        data: "2026-11-20T13:05:00+00:00",
        origem: "Aplicação",
        codigo: "c".repeat(64),
        versao: null,
      },
      {
        tipo: "documento",
        acao: null,
        titulo: "Áudio do depoimento, Acusado 1",
        autor: "Bruno Membro",
        data: "2026-11-20T13:10:00+00:00",
        origem: "Upload",
        codigo: CODIGO,
        versao: 2,
      },
    ],
    gavetas: [
      { rotulo: "Termo de declaração, Acusado 1", origem: "Upload", obrigatoria: true, situacao: "Aguardando" },
      { rotulo: "Ata de deliberação", origem: "ClickSign", obrigatoria: true, situacao: "Assinado" },
    ],
    conferencia: { intacta: true, linhas_adulteradas: [], texto: "A cadeia da trilha confere." },
    pode_baixar_dossie: true,
    ...trocas,
  };
}

describe("Trilha do caso", () => {
  it("mostra o documento com autor, data, origem, versão e código de integridade", () => {
    render(<TrilhaDoCaso casoId="caso-1" protocolo="CC-AB12-CD34" trilha={trilha()} />);

    const linha = within(screen.getByRole("list", { name: "Linha do tempo" }));
    expect(linha.getByText("Áudio do depoimento, Acusado 1, versão 2")).toBeTruthy();
    expect(linha.getByText("Bruno Membro, 20/11/2026, 10:10, Upload")).toBeTruthy();
    expect(linha.getByText(`Código de integridade: ${CODIGO}`)).toBeTruthy();
    expect(linha.getByText("Ana Coordenadora, 20/11/2026, 10:00, Aplicação")).toBeTruthy();
  });

  it("guarda as leituras atrás de um botão", () => {
    render(<TrilhaDoCaso casoId="caso-1" protocolo="CC-AB12-CD34" trilha={trilha()} />);

    expect(screen.queryByText("abriu o caso")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "MOSTRAR AS LEITURAS (1)" }));
    expect(screen.getByText("abriu o caso")).toBeTruthy();
  });

  it("mostra cada gaveta do rito com a situação", () => {
    render(<TrilhaDoCaso casoId="caso-1" protocolo="CC-AB12-CD34" trilha={trilha()} />);

    const gavetas = screen.getByRole("list", { name: "Gavetas do rito" });
    expect(gavetas.textContent).toContain("Termo de declaração, Acusado 1: aguardando");
    expect(gavetas.textContent).toContain("Ata de deliberação: assinado");
  });

  it("avisa quando a cadeia da trilha não confere", () => {
    const conferencia = { intacta: false, linhas_adulteradas: [7], texto: "A cadeia da trilha não confere na linha 7." };
    render(<TrilhaDoCaso casoId="caso-1" protocolo="CC-AB12-CD34" trilha={trilha({ conferencia })} />);

    expect(screen.getByRole("alert").textContent).toBe("A cadeia da trilha não confere na linha 7.");
  });

  it("BAIXAR DOSSIÊ chama a rota do pacote do caso", async () => {
    render(<TrilhaDoCaso casoId="caso-1" protocolo="CC-AB12-CD34" trilha={trilha()} />);

    fireEvent.click(screen.getByRole("button", { name: "BAIXAR DOSSIÊ" }));

    await waitFor(() => expect(chamadas).toEqual(["/api/comite-de-conduta/casos/caso-1/dossie"]));
  });

  it("quem não pode baixar não vê o botão", () => {
    render(<TrilhaDoCaso casoId="caso-1" protocolo="CC-AB12-CD34" trilha={trilha({ pode_baixar_dossie: false })} />);

    expect(screen.queryByRole("button", { name: "BAIXAR DOSSIÊ" })).toBeNull();
  });
});
