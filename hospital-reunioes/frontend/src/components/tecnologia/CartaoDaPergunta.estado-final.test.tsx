/**
 * @vitest-environment jsdom
 */

/**
 * O estado final da Pergunta da Vitta no cartão (issue #2121, PRD #2112, ADR
 * 0109, decisão 6).
 *
 * Depois que a Vitta lê a resposta e dá o ok, a Pergunta resolvida mostra o
 * que foi decidido e o que destravou. A que deixou de ser necessária mostra o
 * motivo. Nas duas, o cartão não responde mais.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CartaoDaPergunta, type PerguntaDaVitta } from "./CartaoDaPergunta";

afterEach(() => {
  cleanup();
});

const PERGUNTA: PerguntaDaVitta = {
  id: "p-1",
  projeto: "Aplicativo do Hospital",
  assunto: "quem assina a Ata pela diretoria",
  texto: "Quem assina a Ata em nome da diretoria quando a senhora não está?",
  por_que_precisa: "Só a diretoria decide quem assina a ata em nome do hospital.",
  o_que_esta_parado: "A tela de assinatura da Ata espera essa regra para sair.",
  o_que_anda_depois: "A Vitta termina a tela e ela entra na próxima subida.",
  ganho: "A ata sai assinada no mesmo dia da reunião.",
  opcoes: [
    { letra: "A", texto: "O diretor geral" },
    { letra: "B", texto: "Quem presidiu a reunião" },
  ],
  recomendada: "B",
  porque: "Quem presidiu esteve na reunião e conhece o que foi decidido.",
  estado: "aberta",
  criado_em: "2026-11-18T10:00:00Z",
  destinatario: "Diretora Clínica",
  resposta: null,
  pode_responder: true,
};

const DECIDIDO = "Quem presidiu a reunião assina a Ata pela diretoria.";
const DESTRAVOU = "A tela de assinatura da Ata volta a andar e entra na próxima subida.";
const MOTIVO = "A diretoria decidiu na reunião de quinta, não precisa mais perguntar.";

describe("o cartão da Pergunta resolvida", () => {
  it("mostra o estado Resolvida com o que foi decidido e o que destravou, e não responde", () => {
    render(
      <CartaoDaPergunta
        token="t"
        pergunta={{
          ...PERGUNTA,
          estado: "resolvida",
          pode_responder: true,
          resolucao: { decidido: DECIDIDO, destravou: DESTRAVOU, resolvida_em: "2026-11-22T10:00:00Z" },
        }}
      />,
    );

    const cartao = screen.getByRole("article", { name: "Pergunta da Vitta" });
    expect(within(cartao).getByText("Resolvida")).toBeTruthy();
    const final = within(cartao).getByRole("group", { name: "Resolvida" });
    expect(within(final).getByText("O que foi decidido")).toBeTruthy();
    expect(within(final).getByText(DECIDIDO)).toBeTruthy();
    expect(within(final).getByText("O que destravou")).toBeTruthy();
    expect(within(final).getByText(DESTRAVOU)).toBeTruthy();
    expect(within(cartao).queryByRole("textbox", { name: "Sua resposta" })).toBeNull();
  });
});

describe("o cartão da Pergunta cancelada", () => {
  it("mostra o estado Cancelada com o motivo, e não responde", () => {
    render(
      <CartaoDaPergunta
        token="t"
        pergunta={{
          ...PERGUNTA,
          estado: "cancelada",
          pode_responder: true,
          cancelamento: { motivo: MOTIVO, cancelada_em: "2026-11-22T10:00:00Z" },
        }}
      />,
    );

    const cartao = screen.getByRole("article", { name: "Pergunta da Vitta" });
    const final = within(cartao).getByRole("group", { name: "Cancelada" });
    expect(within(final).getByText("Motivo")).toBeTruthy();
    expect(within(final).getByText(MOTIVO)).toBeTruthy();
    expect(within(cartao).queryByRole("textbox", { name: "Sua resposta" })).toBeNull();
    expect(within(cartao).queryByText(/Esperando há/)).toBeNull();
  });
});

describe("o cartão que ainda espera", () => {
  it("não mostra estado final", () => {
    render(<CartaoDaPergunta pergunta={PERGUNTA} />);

    expect(screen.queryByRole("group", { name: "Resolvida" })).toBeNull();
    expect(screen.queryByRole("group", { name: "Cancelada" })).toBeNull();
  });
});
