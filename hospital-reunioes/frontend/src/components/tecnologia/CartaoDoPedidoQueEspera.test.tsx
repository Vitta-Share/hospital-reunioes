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

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PerguntaDaVitta } from "./CartaoDaPergunta";
import { CartaoDoPedido } from "./CartaoDoPedido";
import { EsperandoVoce } from "./EsperandoVoce";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

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

/** O esperado, aberto e com os checks marcados, na mesma lista que o espera. */
const TESTE: PerguntaDaVitta = {
  ...ABERTURA,
  id: "pi-1",
  assunto: "testar o anonimato do Canal de Conduta",
  texto: "Teste o anonimato do Canal de Conduta.",
};

function naLista(pedido: PerguntaDaVitta) {
  return { ...pedido, demanda_id: "d-1", demanda: "O Canal de Conduta", minha: true };
}

/** A lista com o teste e a abertura; o Concluir do teste devolve o cartão concluído. */
function montarALista(esperado: PerguntaDaVitta = TESTE) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const corpo =
        init?.method === "POST"
          ? { pergunta: { ...esperado, estado: "concluida", pode_responder: false }, mensagem: null }
          : [naLista(esperado), naLista({ ...ABERTURA, espera: ESPERA })];
      return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
    }),
  );
  render(<EsperandoVoce token="token-de-teste" />);
}

async function cartaoDe(texto: string) {
  const regiao = await screen.findByRole("region", { name: "Esperando você" });
  return within(regiao)
    .getAllByRole("article", { name: "Pedido de implantação" })
    .find((cartao) => cartao.textContent?.includes(texto)) as HTMLElement;
}

describe("Concluído o esperado na mesma tela", () => {
  it("o Pedido que espera libera o Concluir sem recarregar", async () => {
    montarALista();
    const abertura = await cartaoDe("Divulgue o Canal de Conduta");
    expect((within(abertura).getByRole("button", { name: "Concluir" }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(within(await cartaoDe("Teste o anonimato")).getByRole("button", { name: "Concluir" }));

    await waitFor(() =>
      expect((within(abertura).getByRole("button", { name: "Concluir" }) as HTMLButtonElement).disabled).toBe(false),
    );
    expect(within(abertura).queryByText(/^Espera:/)).toBeNull();
    expect(within(abertura).queryByText(/ser concluído\.$/)).toBeNull();
  });

  it("concluir outro Pedido não solta a espera", async () => {
    montarALista({ ...TESTE, id: "pi-9" });
    const abertura = await cartaoDe("Divulgue o Canal de Conduta");

    fireEvent.click(within(await cartaoDe("Teste o anonimato")).getByRole("button", { name: "Concluir" }));

    await waitFor(() => expect(screen.queryByText("Teste o anonimato do Canal de Conduta.")).toBeNull());
    expect(within(abertura).getByText("Espera: testar o anonimato do Canal de Conduta")).toBeTruthy();
    expect((within(abertura).getByRole("button", { name: "Concluir" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
