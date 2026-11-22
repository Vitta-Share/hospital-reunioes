/**
 * @vitest-environment jsdom
 */

/**
 * O termo de declaração no cartão do depoimento (issue #1831; especificação,
 * 7.1 e Anexos C e E.1).
 *
 * O servidor redige, numera as versões e monta o PDF. O que se trava aqui é o
 * que a tela pede e mostra: o clique que pede o termo com a identificação, as
 * notas marcadas como Sugestão, a correção que vai inteira ao servidor,
 * "IMPRIMIR TERMO" pelo backend e a certidão de recusa com o segundo membro.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Depoimento, ItemDaLista, TermoDeDeclaracao as Termo } from "@/lib/conduta/depoimentos";

import { TermoDeDeclaracao } from "./TermoDeDeclaracao";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let chamadas: { url: string; method: string; body: unknown }[];
const abertas: string[] = [];

beforeEach(() => {
  chamadas = [];
  abertas.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null });
      return {
        ok: true,
        status: 200,
        json: async () => ({ ok: true }),
        blob: async () => new Blob(["%PDF"], { type: "application/pdf" }),
      } as Response;
    })
  );
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:http://localhost/termo-1", revokeObjectURL: () => {} }));
  vi.stubGlobal("open", (endereco: string) => {
    abertas.push(endereco);
    return null;
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const LISTA: ItemDaLista[] = [];

const DEPOIMENTO: Depoimento = {
  id: "d1",
  nome: "Fulano de Tal",
  cargo: "Supervisor do almoxarifado",
  papel: "acusado",
  situacao: "Aguardando assinatura",
  arquivos: {
    transcricao: [{ versao: 1, enviado_em: "2026-11-20T17:00:00Z", enviado_por: "Bruno", paginas: [] }],
    audio: [],
    termo_assinado: [],
  },
  sem_gravacao: null,
  lista: LISTA,
  bloqueio_da_conclusao: null,
  concluido_em: null,
  concluido_por: null,
};

const TERMO: Termo = {
  versao: 1,
  origem: "agente",
  criado_em: "2026-11-20T18:00:00Z",
  criado_por: "Bruno Membro",
  identificacao: {
    nome: "Fulano de Tal",
    cargo: "Supervisor do almoxarifado",
    cpf: "",
    data: "2026-11-20",
    hora: "14:30",
    local: "Sala do Comitê",
    conduziram: ["Ana Coordenadora", "Bruno Membro"],
  },
  gravacao: "Esta conversa foi gravada com meu consentimento.",
  declaracoes: ["Fulano de Tal declarou que estava no almoxarifado."],
  documentos: [],
  lido_em_voz_alta: false,
  notas: { rotulo: "Sugestão", itens: ["Perguntar a Maria Souza o que ouviu."] },
};

function desenhar(depoimento: Partial<Depoimento> = {}) {
  const aoMudar = vi.fn();
  render(
    <TermoDeDeclaracao
      casoId="c1"
      depoimento={{ ...DEPOIMENTO, ...depoimento }}
      podeAgir
      membros={[{ id: "COORD", nome: "Ana Coordenadora", papel: "coordenacao" }]}
      aoMudar={aoMudar}
    />
  );
  return { aoMudar };
}

describe("o termo nasce de um clique", () => {
  it("REDIGIR TERMO pede o termo ao servidor com a identificação", async () => {
    const { aoMudar } = desenhar();
    expect(chamadas).toEqual([]);

    fireEvent.click(screen.getByRole("button", { name: "REDIGIR TERMO" }));
    fireEvent.change(screen.getByLabelText("Data da conversa"), { target: { value: "2026-11-20" } });
    fireEvent.change(screen.getByLabelText("Hora"), { target: { value: "14:30" } });
    fireEvent.change(screen.getByLabelText("Local"), { target: { value: "Sala do Comitê" } });
    fireEvent.change(screen.getByLabelText("Quem conduziu (1)"), { target: { value: "Ana Coordenadora" } });
    fireEvent.change(screen.getByLabelText("Quem conduziu (2)"), { target: { value: "Bruno Membro" } });
    fireEvent.click(within(screen.getByRole("form", { name: "Redigir termo" })).getByRole("button", { name: "REDIGIR TERMO" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas.at(-1)).toEqual({
      url: "/api/comite-de-conduta/casos/c1/depoimentos/d1/termo",
      method: "POST",
      body: {
        data: "2026-11-20",
        hora: "14:30",
        local: "Sala do Comitê",
        conduziram: ["Ana Coordenadora", "Bruno Membro"],
        cpf: "",
      },
    });
  });

  it("sem transcrição nem pontos, não há botão de redigir", () => {
    desenhar({ arquivos: { transcricao: [], audio: [], termo_assinado: [] } });

    expect(screen.queryByRole("button", { name: "REDIGIR TERMO" })).toBeNull();
  });

  it("SUGERIR ROTEIRO DE PERGUNTAS pede o roteiro, e o roteiro aparece como Sugestão", async () => {
    const { aoMudar } = desenhar({ roteiro: { rotulo: "Sugestão", perguntas: ["Onde o senhor estava?"] } });

    fireEvent.click(screen.getByRole("button", { name: "SUGERIR ROTEIRO DE PERGUNTAS" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas.at(-1)!.url).toBe("/api/comite-de-conduta/casos/c1/depoimentos/d1/roteiro");
    const roteiro = screen.getByRole("region", { name: "Roteiro de perguntas" });
    expect(within(roteiro).getByText("Sugestão")).toBeTruthy();
    expect(within(roteiro).getByText("Onde o senhor estava?")).toBeTruthy();
  });
});

describe("as notas para quem apura", () => {
  it("aparecem marcadas como Sugestão, separadas do termo", () => {
    desenhar({ termo: TERMO });

    const notas = screen.getByRole("region", { name: "Notas para quem apura" });
    expect(within(notas).getByText("Sugestão")).toBeTruthy();
    expect(within(notas).getByText("Perguntar a Maria Souza o que ouviu.")).toBeTruthy();
    expect(within(notas).getByText("Não fazem parte do termo e não são impressas.")).toBeTruthy();
  });
});

describe("a revisão e a impressão", () => {
  it("LANÇAR CORREÇÕES manda o termo inteiro, como ficou", async () => {
    const { aoMudar } = desenhar({ termo: TERMO });

    fireEvent.change(screen.getByLabelText(/Declarações/), {
      target: { value: "Fulano de Tal declarou que estava no almoxarifado.\n\nDisse que saiu às 15h." },
    });
    fireEvent.click(screen.getByLabelText("Termo lido em voz alta para o depoente"));
    fireEvent.click(screen.getByRole("button", { name: "LANÇAR CORREÇÕES" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas.at(-1)).toEqual({
      url: "/api/comite-de-conduta/casos/c1/depoimentos/d1/termo/correcoes",
      method: "POST",
      body: {
        identificacao: {
          cpf: "",
          data: "2026-11-20",
          hora: "14:30",
          local: "Sala do Comitê",
          conduziram: ["Ana Coordenadora", "Bruno Membro"],
        },
        gravacao: "Esta conversa foi gravada com meu consentimento.",
        declaracoes: ["Fulano de Tal declarou que estava no almoxarifado.", "Disse que saiu às 15h."],
        documentos: [],
        lido_em_voz_alta: true,
      },
    });
  });

  it("IMPRIMIR TERMO abre o PDF que o backend entregou", async () => {
    desenhar({ termo: TERMO });

    fireEvent.click(screen.getByRole("button", { name: "IMPRIMIR TERMO" }));

    await waitFor(() => expect(abertas).toEqual(["blob:http://localhost/termo-1"]));
    expect(chamadas.at(-1)!.url).toBe("/api/comite-de-conduta/casos/c1/depoimentos/d1/termo/pdf");
  });

  it("com correção sem lançar, não imprime a versão velha", () => {
    desenhar({ termo: TERMO });

    fireEvent.change(screen.getByLabelText(/Declarações/), { target: { value: "Outra coisa." } });

    expect((screen.getByRole("button", { name: "IMPRIMIR TERMO" }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("a certidão de recusa", () => {
  it("vai ao servidor com o segundo membro escolhido", async () => {
    const { aoMudar } = desenhar({ termo: TERMO });

    fireEvent.click(screen.getByRole("button", { name: "REGISTRAR RECUSA DE ASSINATURA" }));
    fireEvent.change(screen.getByLabelText("Quem assina com você"), { target: { value: "COORD" } });
    fireEvent.click(screen.getByRole("button", { name: "ENVIAR CERTIDÃO PARA ASSINATURA" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas.at(-1)).toEqual({
      url: "/api/comite-de-conduta/casos/c1/depoimentos/d1/recusa",
      method: "POST",
      body: { membro_id: "COORD" },
    });
  });

  it("assinada, a tela diz e não oferece de novo", () => {
    desenhar({ termo: TERMO, recusa: { situacao: "assinado", enviado_em: null, assinado_em: null, erro: null } });

    expect(screen.getByText("Certidão de recusa assinada pelos dois membros.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /RECUSA/ })).toBeNull();
  });
});
