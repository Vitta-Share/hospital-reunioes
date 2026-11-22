/**
 * @vitest-environment jsdom
 */

/**
 * Um Pedido de implantação espera outro (issue #2208, ADR 0111, decisão 8).
 *
 * Enquanto o esperado está aberto, o servidor manda a `espera` no cartão: ele
 * mostra "Espera" com o assunto do outro, e o Concluir fica bloqueado com o
 * motivo numa linha, mesmo com todos os checks marcados. Concluído o esperado,
 * o cartão chega sem `espera` e o Concluir libera.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { PerguntaDaVitta } from "./CartaoDaPergunta";
import { CartaoDoPedido } from "./CartaoDoPedido";

afterEach(cleanup);

const ABERTURA: PerguntaDaVitta = {
  id: "pi-2",
  tipo: "implantacao",
  projeto: "Aplicativo do Hospital",
  assunto: "abrir o Canal de Conduta para todos",
  texto: "Divulgue o Canal de Conduta depois do teste.",
  por_que_precisa: "Só o hospital divulga o Canal.",
  o_que_esta_parado: "O Canal espera a divulgação.",
  o_que_anda_depois: "Todos podem relatar.",
  ganho: "Quem relata confia no Canal.",
  estado: "aberta",
  criado_em: "2026-11-20T10:00:00Z",
  destinatario: "Diretora Clínica",
  passos: [
    { texto: "Mande o link do Canal para todos.", marcado: true },
    { texto: "Como saber que acabou: o primeiro relato chega.", marcado: true },
  ],
  fechamento: { estado: "fechado", motivo: null },
  pode_responder: true,
};

const ESPERA = { pedido_id: "pi-1", assunto: "testar o anonimato do Canal de Conduta" };

const concluir = () => screen.getByRole("button", { name: "Concluir" }) as HTMLButtonElement;

describe("O Pedido de implantação que espera outro", () => {
  it('com o esperado aberto, o cartão mostra "Espera" e o Concluir fica bloqueado com o motivo', () => {
    render(<CartaoDoPedido pedido={{ ...ABERTURA, espera: ESPERA }} token="token-de-teste" />);

    const cartao = screen.getByRole("article", { name: "Pedido de implantação" });
    expect(within(cartao).getByText("Espera: testar o anonimato do Canal de Conduta")).toBeTruthy();
    expect(concluir().disabled).toBe(true);
    expect(
      within(cartao).getByText('Este Pedido espera "testar o anonimato do Canal de Conduta" ser concluído.'),
    ).toBeTruthy();
    expect(screen.queryByText("Marque todos os passos para concluir.")).toBeNull();
  });

  it("concluído o esperado, o cartão chega sem a espera e o Concluir libera", () => {
    render(<CartaoDoPedido pedido={{ ...ABERTURA, espera: null }} token="token-de-teste" />);

    expect(screen.queryByText(/^Espera:/)).toBeNull();
    expect(concluir().disabled).toBe(false);
  });
});
