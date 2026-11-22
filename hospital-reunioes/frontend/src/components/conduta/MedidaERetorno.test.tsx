/**
 * @vitest-environment jsdom
 */

/**
 * O caminho do caso depois da votação na tela do caso (issue #1835): a
 * decisão da Direção, o retorno que só sai aprovado e a correção de processo
 * com responsável e prazo. O servidor decide o que vale; aqui se trava o que a
 * tela pede a ele.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MedidaERetorno as Dados } from "@/lib/conduta/retorno";

import { MedidaERetorno } from "./MedidaERetorno";

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

const BASE: Dados = {
  com_medida: true,
  pode_enviar_a_direcao: false,
  bloqueio_do_envio: null,
  enviado_a_direcao_em: "2026-11-16T12:00:00+00:00",
  decisao: {
    decisao: "Aplicada com ajuste",
    codigo: "aplicada_com_ajuste",
    justificativa: "A suspensão virou advertência pelo histórico.",
    decidida_em: "2026-11-18",
    registrada_em: "2026-11-18T15:00:00+00:00",
  },
  comunicacoes: [],
  retorno: {
    em_aberto: true,
    pode_redigir: true,
    pode_aprovar: false,
    bloqueio_da_aprovacao: "Escolha ao menos uma correção de processo, com responsável e prazo.",
    versoes: [
      {
        versao: 1,
        origem: "agente",
        autor: "Ana Coordenadora",
        criado_em: "2026-11-19T12:00:00+00:00",
        denunciante: "O Comitê concluiu a apuração do seu relato.",
        acusado: "O Comitê apurou os fatos e concluiu o caso.",
      },
    ],
    aprovado: null,
  },
  correcoes: { sugeridas: ["Revisar a escala do almoxarifado."], escolhidas: [], pode_escolher: true },
};

function montar(dados: Dados = BASE) {
  const aoMudar = vi.fn();
  render(<MedidaERetorno casoId="caso-1" dados={dados} aoMudar={aoMudar} />);
  return aoMudar;
}

describe("A decisão da Direção", () => {
  it("mostra a decisão registrada, com a data e a justificativa", () => {
    montar();

    const decisao = screen.getByRole("region", { name: "Decisão da Direção" });
    expect(within(decisao).getByText("Aplicada com ajuste")).toBeTruthy();
    expect(within(decisao).getByText(/18\/11\/2026/)).toBeTruthy();
    expect(within(decisao).getByText("A suspensão virou advertência pelo histórico.")).toBeTruthy();
  });

  it("enquanto a Direção não decide, diz que espera a decisão", () => {
    montar({ ...BASE, decisao: null });

    expect(screen.getByText("A Recomendação está com a Direção, à espera da decisão sobre a medida.")).toBeTruthy();
  });
});

describe("O retorno só sai aprovado", () => {
  it("mostra a versão em revisão e trava a aprovação com o motivo", () => {
    montar();

    const retorno = screen.getByRole("region", { name: "Retorno" });
    expect(within(retorno).getByText("O Comitê concluiu a apuração do seu relato.")).toBeTruthy();
    expect(within(retorno).getByText("Escolha ao menos uma correção de processo, com responsável e prazo.")).toBeTruthy();
    expect((within(retorno).getByRole("button", { name: "APROVAR RETORNO" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("aprova a última versão pelo servidor", async () => {
    const aoMudar = montar({ ...BASE, retorno: { ...BASE.retorno, pode_aprovar: true, bloqueio_da_aprovacao: null } });

    fireEvent.click(screen.getByRole("button", { name: "APROVAR RETORNO" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas).toEqual([
      { url: "/api/comite-de-conduta/casos/caso-1/retorno/aprovacao", method: "POST", body: {} },
    ]);
  });

  it("a revisão da coordenação vai como versão nova, com os dois textos", async () => {
    montar();

    fireEvent.click(screen.getByRole("button", { name: "REVISAR O RETORNO" }));
    fireEvent.change(screen.getByLabelText("Resposta a quem relatou"), {
      target: { value: "Seu relato foi apurado e o caso foi concluído." },
    });
    fireEvent.click(screen.getByRole("button", { name: "SALVAR VERSÃO" }));

    await waitFor(() => expect(chamadas).toHaveLength(1));
    expect(chamadas[0]).toEqual({
      url: "/api/comite-de-conduta/casos/caso-1/retorno/versoes",
      method: "POST",
      body: {
        denunciante: "Seu relato foi apurado e o caso foi concluído.",
        acusado: "O Comitê apurou os fatos e concluiu o caso.",
      },
    });
  });

  it("aprovado, abre a comunicação ao acusado para entregar", async () => {
    resposta = { texto: "O Comitê apurou os fatos sobre Rogério Valente." };
    montar({
      ...BASE,
      retorno: {
        ...BASE.retorno,
        em_aberto: false,
        pode_redigir: false,
        bloqueio_da_aprovacao: null,
        aprovado: { versao: 1, aprovado_em: "2026-11-20T12:00:00+00:00", aprovado_por: "Ana Coordenadora" },
      },
    });

    expect(screen.queryByRole("button", { name: "APROVAR RETORNO" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "ABRIR COMUNICAÇÃO AO ACUSADO" }));

    expect(await screen.findByText("O Comitê apurou os fatos sobre Rogério Valente.")).toBeTruthy();
    expect(chamadas[0].url).toBe("/api/comite-de-conduta/casos/caso-1/retorno/comunicacao-ao-acusado");
  });
});

describe("A correção de processo fica com responsável e prazo", () => {
  it("escolher uma sugestão pede responsável e prazo antes de gravar", async () => {
    montar();

    fireEvent.click(screen.getByRole("button", { name: "ESCOLHER: Revisar a escala do almoxarifado." }));
    const gravar = screen.getByRole("button", { name: "GRAVAR CORREÇÃO" }) as HTMLButtonElement;
    fireEvent.change(screen.getByLabelText("Prazo"), { target: { value: "2026-12-31" } });
    expect(gravar.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Responsável"), { target: { value: "Gerência de Logística" } });
    expect(gravar.disabled).toBe(false);
    fireEvent.click(gravar);

    await waitFor(() => expect(chamadas).toHaveLength(1));
    expect(chamadas[0]).toEqual({
      url: "/api/comite-de-conduta/casos/caso-1/correcoes",
      method: "POST",
      body: { texto: "Revisar a escala do almoxarifado.", responsavel: "Gerência de Logística", prazo_em: "2026-12-31" },
    });
  });

  it("mostra a correção escolhida com responsável e prazo", () => {
    montar({
      ...BASE,
      correcoes: {
        sugeridas: [],
        pode_escolher: false,
        escolhidas: [
          {
            texto: "Revisar a escala do almoxarifado.",
            responsavel: "Gerência de Logística",
            prazo_em: "2026-12-31",
            escolhida_por: "Bruno Membro",
            escolhida_em: "2026-11-19T12:00:00+00:00",
          },
        ],
      },
    });

    const correcoes = screen.getByRole("region", { name: "Correção de processo" });
    expect(within(correcoes).getByText("Revisar a escala do almoxarifado.")).toBeTruthy();
    expect(within(correcoes).getByText("Responsável: Gerência de Logística. Prazo: 31/12/2026.")).toBeTruthy();
  });

  it("o caso sem medida não mostra correção de processo nem decisão da Direção", () => {
    montar({ ...BASE, com_medida: false, enviado_a_direcao_em: null, decisao: null, correcoes: null });

    expect(screen.queryByRole("region", { name: "Correção de processo" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Decisão da Direção" })).toBeNull();
    expect(screen.getByText("Caso improcedente ou inconclusivo: não vai à Direção.")).toBeTruthy();
  });
});
