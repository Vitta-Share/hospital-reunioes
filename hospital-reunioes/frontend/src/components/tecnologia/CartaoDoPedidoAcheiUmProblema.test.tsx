/**
 * @vitest-environment jsdom
 */

/**
 * Achei um problema no Pedido de implantação (issue #2210, ADR 0111, decisão 9).
 *
 * O botão do cartão abre o Assistente em modo bug, com o texto inicial que o
 * servidor monta a partir do Pedido: o cartão pede o bug com o `pedido_id` e
 * avisa a tela para abrir a conversa que nasceu. Com o card do bug criado, o
 * servidor manda a `espera_demanda`, e o cartão mostra "Espera a Demanda N"
 * com o Concluir bloqueado e o motivo.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PerguntaDaVitta } from "./CartaoDaPergunta";
import { CartaoDoPedido } from "./CartaoDoPedido";
import { ABRIR_DEMANDA } from "./CartaoDoPassoAPasso";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const TESTE: PerguntaDaVitta = {
  id: "pi-1",
  tipo: "implantacao",
  projeto: "Aplicativo do Hospital",
  assunto: "testar o anonimato do Canal de Conduta",
  texto: "Teste o Canal de Conduta com alguém do hospital antes de divulgar.",
  por_que_precisa: "Só o hospital testa com gente de verdade.",
  o_que_esta_parado: "A divulgação espera o teste.",
  o_que_anda_depois: "O Canal abre para todos.",
  ganho: "Quem relata confia no anonimato.",
  estado: "aberta",
  criado_em: "2026-11-20T10:00:00Z",
  destinatario: "Diretora Clínica",
  passos: [
    { texto: "Faça um relato de teste sem se identificar.", marcado: true },
    { texto: "Como saber que acabou: o relato aparece sem o nome.", marcado: true },
  ],
  fechamento: { estado: "fechado", motivo: null },
  pode_responder: true,
};

const botao = () => screen.getByRole("button", { name: "Achei um problema" }) as HTMLButtonElement;
const concluir = () => screen.getByRole("button", { name: "Concluir" }) as HTMLButtonElement;

describe("O botão Achei um problema", () => {
  it("pede o bug com o Pedido e avisa a tela para abrir a conversa que nasceu", async () => {
    const pedidos: { url: string; corpo: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        pedidos.push({ url, corpo: JSON.parse(String(init?.body)) });
        return { ok: true, status: 201, json: async () => ({ demanda_id: "bug-1" }) } as unknown as Response;
      }),
    );
    const abertas: string[] = [];
    const ouvir = (evento: Event) => abertas.push((evento as CustomEvent<string>).detail);
    window.addEventListener(ABRIR_DEMANDA, ouvir);
    render(<CartaoDoPedido pedido={TESTE} token="token-de-teste" />);

    fireEvent.click(botao());

    await waitFor(() => expect(abertas).toEqual(["bug-1"]));
    window.removeEventListener(ABRIR_DEMANDA, ouvir);
    expect(pedidos).toEqual([{ url: "/api/admin/tecnologia/chat", corpo: { escolha: "bug", pedido_id: "pi-1" } }]);
  });

  it("o servidor recusando, o cartão mostra o motivo e não abre nada", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          ({
            ok: false,
            status: 422,
            json: async () => ({ detail: "Este Pedido de implantação já não está aberto." }),
          }) as unknown as Response,
      ),
    );
    render(<CartaoDoPedido pedido={TESTE} token="token-de-teste" />);

    fireEvent.click(botao());

    expect(await screen.findByText("Este Pedido de implantação já não está aberto.")).toBeTruthy();
  });

  it("só o Pedido de implantação aberto tem o botão", () => {
    render(<CartaoDoPedido pedido={{ ...TESTE, tipo: "passo_a_passo" }} token="token-de-teste" />);
    expect(screen.queryByRole("button", { name: "Achei um problema" })).toBeNull();
    cleanup();

    render(<CartaoDoPedido pedido={{ ...TESTE, estado: "concluida" }} token="token-de-teste" />);
    expect(screen.queryByRole("button", { name: "Achei um problema" })).toBeNull();
  });
});

describe("O Pedido que espera a Demanda de bug", () => {
  it('mostra "Espera a Demanda N" e bloqueia o Concluir com o motivo', () => {
    render(
      <CartaoDoPedido pedido={{ ...TESTE, espera_demanda: { demanda_id: "bug-1", numero: 57 } }} token="token-de-teste" />,
    );

    const cartao = screen.getByRole("article", { name: "Pedido de implantação" });
    expect(within(cartao).getByText("Espera a Demanda 57")).toBeTruthy();
    expect(concluir().disabled).toBe(true);
    expect(within(cartao).getByText("Este Pedido espera a Demanda 57 ser entregue.")).toBeTruthy();
  });

  it("com o bug entregue, o cartão chega sem a espera e o Concluir libera", () => {
    render(<CartaoDoPedido pedido={{ ...TESTE, espera_demanda: null }} token="token-de-teste" />);

    expect(screen.queryByText(/^Espera a Demanda/)).toBeNull();
    expect(concluir().disabled).toBe(false);
  });
});
