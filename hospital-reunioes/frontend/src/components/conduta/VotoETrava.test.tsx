/**
 * @vitest-environment jsdom
 */

/**
 * O voto e a trava de robustez do Canal de Conduta (issue #1833;
 * especificação, 6.6 e 6.7). O servidor decide o que vale; o que se trava
 * aqui é o que a tela pede a ele: o voto com resultado, medida e
 * justificativa, a trava preenchida num clique e confirmada item a item, e a
 * conclusão bloqueada com o motivo.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Trava, Votacao } from "@/lib/conduta/voto";

import { VotoETrava } from "./VotoETrava";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let chamadas: { url: string; method: string; body: unknown }[];

beforeEach(() => {
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body instanceof FormData ? "arquivo" : init?.body ? JSON.parse(String(init.body)) : null;
      chamadas.push({ url, method: init?.method ?? "GET", body });
      return { ok: true, status: 200, json: async () => ({ ok: true }) } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const VOTACAO: Votacao = {
  rodada: 1,
  votantes: 3,
  votaram: 1,
  meu_voto: null,
  pode_votar: true,
  bloqueio_do_voto: null,
  reuniao_curta_convocada: false,
  rodadas: [],
  resultado: null,
  concluida: null,
  pode_concluir: false,
  bloqueio_da_conclusao: "Só a coordenação conclui a votação.",
};

const ITEM = {
  confirmacoes: [] as string[],
  confirmacoes_precisas: 1,
  confirmado: false,
  pode_confirmar: true,
  bloqueio: null,
};

const TRAVA: Trava = {
  itens: [
    {
      ...ITEM,
      item: "fato",
      rotulo: "Fato descrito, com data e local",
      preenchimento: { atendido: true, texto: "O relato diz 3 de outubro, no almoxarifado." },
    },
    {
      ...ITEM,
      item: "ciencia",
      rotulo: "Ciência prévia do Código pelo acusado",
      preenchimento: null,
      pode_confirmar: false,
      bloqueio: "Anexe a ciência do Código registrada pelo DP antes de confirmar.",
    },
  ],
  preenchida_em: null,
  pode_preencher: true,
  ciencia: [],
};

function desenhar(votacao: Partial<Votacao> = {}, trava: Partial<Trava> = {}) {
  const aoMudar = vi.fn();
  render(<VotoETrava casoId="c1" votacao={{ ...VOTACAO, ...votacao }} trava={{ ...TRAVA, ...trava }} aoMudar={aoMudar} />);
  return aoMudar;
}

describe("VotoETrava", () => {
  it("o membro vota com resultado, medida da Matriz e a própria justificativa", async () => {
    const aoMudar = desenhar();

    const voto = screen.getByRole("form", { name: "Seu voto" });
    fireEvent.click(within(voto).getByLabelText("Procedente"));
    fireEvent.change(within(voto).getByLabelText("Medida da Matriz"), { target: { value: "suspensao" } });
    fireEvent.change(within(voto).getByLabelText("Dias de suspensão"), { target: { value: "5" } });
    fireEvent.change(within(voto).getByLabelText("Justificativa, em até três linhas"), {
      target: { value: "Os depoimentos confirmam." },
    });
    fireEvent.click(within(voto).getByRole("button", { name: "VOTAR" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas).toEqual([
      {
        url: "/api/comite-de-conduta/casos/c1/voto",
        method: "POST",
        body: { resultado: "procedente", medida: "suspensao", dias_de_suspensao: 5, justificativa: "Os depoimentos confirmam." },
      },
    ]);
  });

  it("improcedente não pede medida", async () => {
    desenhar();

    const voto = screen.getByRole("form", { name: "Seu voto" });
    fireEvent.click(within(voto).getByLabelText("Improcedente"));
    expect(within(voto).queryByLabelText("Medida da Matriz")).toBeNull();
    fireEvent.change(within(voto).getByLabelText("Justificativa, em até três linhas"), { target: { value: "Sem prova." } });
    fireEvent.click(within(voto).getByRole("button", { name: "VOTAR" }));

    await waitFor(() => expect(chamadas).toHaveLength(1));
    expect(chamadas[0].body).toEqual({ resultado: "improcedente", medida: null, dias_de_suspensao: null, justificativa: "Sem prova." });
  });

  it("antes de todos votarem mostra só o próprio voto e a contagem", () => {
    desenhar({
      votaram: 2,
      pode_votar: false,
      bloqueio_do_voto: "Você já votou nesta rodada.",
      meu_voto: { resultado: "improcedente", medida: null, dias_de_suspensao: null, justificativa: "Minha razão." },
    });

    expect(screen.getByText("2 de 3 já votaram. Os votos ficam ocultos até os três votarem.")).toBeTruthy();
    expect(screen.getByText("Minha razão.")).toBeTruthy();
    expect(screen.queryByRole("form", { name: "Seu voto" })).toBeNull();
  });

  it("com os três votos mostra cada voto e o resultado da maioria", () => {
    desenhar({
      votaram: 3,
      pode_votar: false,
      rodadas: [
        {
          rodada: 1,
          votos: [
            { membro: "Lia Leitora", resultado: "procedente", medida: "advertencia_escrita", dias_de_suspensao: null, justificativa: "Texto da Lia." },
          ],
          resultado: "procedente",
          medida: "Advertência escrita",
          reuniao_curta: false,
        },
      ],
      resultado: { resultado: "procedente", medida: "Advertência escrita" },
    });

    expect(screen.getByText("Texto da Lia.")).toBeTruthy();
    expect(screen.getByText("Resultado da maioria: Procedente, Advertência escrita")).toBeTruthy();
  });

  it("avisa quando a reunião curta foi convocada", () => {
    desenhar({ reuniao_curta_convocada: true, rodada: 2 });

    expect(screen.getByRole("status").textContent).toContain("reunião curta");
  });

  it("um clique em PREENCHER TRAVA pede o preenchimento ao agente", async () => {
    const aoMudar = desenhar();

    fireEvent.click(screen.getByRole("button", { name: "PREENCHER TRAVA" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas).toEqual([{ url: "/api/comite-de-conduta/casos/c1/trava/preenchimento", method: "POST", body: {} }]);
  });

  it("cada item mostra o preenchimento e é confirmado pelo membro", async () => {
    desenhar();

    const fato = screen.getByRole("listitem", { name: "Fato descrito, com data e local" });
    expect(within(fato).getByText("O relato diz 3 de outubro, no almoxarifado.")).toBeTruthy();
    fireEvent.click(within(fato).getByRole("button", { name: "CONFIRMAR" }));

    await waitFor(() => expect(chamadas).toHaveLength(1));
    expect(chamadas[0]).toEqual({ url: "/api/comite-de-conduta/casos/c1/trava/confirmacao", method: "POST", body: { item: "fato" } });
  });

  it("o item bloqueado diz o motivo e não confirma", () => {
    desenhar();

    const ciencia = screen.getByRole("listitem", { name: "Ciência prévia do Código pelo acusado" });
    expect(within(ciencia).getByText("Anexe a ciência do Código registrada pelo DP antes de confirmar.")).toBeTruthy();
    expect(within(ciencia).queryByRole("button", { name: "CONFIRMAR" })).toBeNull();
  });

  it("CONCLUIR VOTAÇÃO bloqueada mostra o motivo", () => {
    desenhar({ bloqueio_da_conclusao: "A trava de robustez tem item em aberto: Regra violada indicada (item do Código de Conduta)." });

    const botao = screen.getByRole("button", { name: "CONCLUIR VOTAÇÃO" }) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
    expect(screen.getByText("A trava de robustez tem item em aberto: Regra violada indicada (item do Código de Conduta).")).toBeTruthy();
  });

  it("a coordenação conclui a votação", async () => {
    desenhar({ pode_concluir: true, bloqueio_da_conclusao: null });

    fireEvent.click(screen.getByRole("button", { name: "CONCLUIR VOTAÇÃO" }));

    await waitFor(() => expect(chamadas).toHaveLength(1));
    expect(chamadas[0]).toEqual({ url: "/api/comite-de-conduta/casos/c1/conclusao-da-votacao", method: "POST", body: {} });
  });
});
