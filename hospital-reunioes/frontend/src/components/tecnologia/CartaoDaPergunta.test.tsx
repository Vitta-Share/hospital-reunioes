/**
 * @vitest-environment jsdom
 */

/**
 * O cartão da Pergunta da Vitta (issue #2116, PRD #2112, ADR 0109, decisão 3).
 *
 * Uma peça só, que a Conversa da Demanda e as próximas partes reaproveitam:
 * de qual Projeto é, a pergunta, as quatro linhas em palavras simples, o
 * estado e há quantos dias espera.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CartaoDaPergunta, type PerguntaDaVitta } from "./CartaoDaPergunta";

afterEach(cleanup);

const PERGUNTA: PerguntaDaVitta = {
  id: "p-1",
  projeto: "Aplicativo do Hospital",
  assunto: "quem assina a Ata pela diretoria",
  texto: "Quem assina a Ata em nome da diretoria quando a senhora não está?",
  por_que_precisa: "Só a diretoria decide quem assina a ata em nome do hospital.",
  o_que_esta_parado: "A tela de assinatura da Ata espera essa regra para sair.",
  o_que_anda_depois: "A Vitta termina a tela e ela entra na próxima subida.",
  ganho: "A ata sai assinada no mesmo dia da reunião.",
  estado: "aberta",
  criado_em: "2026-11-18T10:00:00Z",
  destinatario: "Diretora Clínica",
};

const AGORA = new Date("2026-11-21T09:00:00Z");

function cartao() {
  return screen.getByRole("article", { name: "Pergunta da Vitta" });
}

describe("O cartão da Pergunta da Vitta", () => {
  it("mostra o projeto, a pergunta e as quatro linhas em palavras simples", () => {
    render(<CartaoDaPergunta pergunta={PERGUNTA} agora={AGORA} />);

    const peca = within(cartao());
    expect(peca.getByText("Aplicativo do Hospital")).toBeTruthy();
    expect(peca.getByText("Quem assina a Ata em nome da diretoria quando a senhora não está?")).toBeTruthy();
    const linhas: [string, string][] = [
      ["Por que precisa de você", PERGUNTA.por_que_precisa],
      ["O que está parado", PERGUNTA.o_que_esta_parado],
      ["O que anda quando você responder", PERGUNTA.o_que_anda_depois],
      ["O que o hospital ganha", PERGUNTA.ganho],
    ];
    for (const [rotulo, valor] of linhas) {
      const termo = peca.getByText(rotulo);
      expect(termo.tagName).toBe("DT");
      expect(termo.nextElementSibling?.textContent).toBe(valor);
    }
  });

  it("mostra o estado e há quantos dias a pergunta aberta espera", () => {
    render(<CartaoDaPergunta pergunta={PERGUNTA} agora={AGORA} />);

    expect(within(cartao()).getByText("Aberta")).toBeTruthy();
    expect(within(cartao()).getByText("Esperando há 2 dias")).toBeTruthy();
  });

  it("conta os dias inteiros de espera, com um dia no singular", () => {
    const { rerender } = render(
      <CartaoDaPergunta pergunta={{ ...PERGUNTA, criado_em: "2026-11-20T08:00:00Z" }} agora={AGORA} />,
    );
    expect(within(cartao()).getByText("Esperando há 1 dia")).toBeTruthy();

    rerender(<CartaoDaPergunta pergunta={{ ...PERGUNTA, criado_em: "2026-11-20T21:30:00Z" }} agora={AGORA} />);
    expect(within(cartao()).getByText("Esperando há menos de 1 dia")).toBeTruthy();
  });

  it("a pergunta que não está mais aberta mostra o estado e não conta a espera", () => {
    render(<CartaoDaPergunta pergunta={{ ...PERGUNTA, estado: "respondida" }} agora={AGORA} />);

    expect(within(cartao()).getByText("Respondida")).toBeTruthy();
    expect(within(cartao()).queryByText(/Esperando/)).toBeNull();
  });

  it("não chama a Pergunta de Pendência nem usa itálico", () => {
    render(<CartaoDaPergunta pergunta={PERGUNTA} agora={AGORA} />);

    expect(cartao().textContent).not.toMatch(/Pend[êe]ncia/i);
    expect(cartao().querySelector("em, i, .italic, [class*='font-serif']")).toBeNull();
  });
});
