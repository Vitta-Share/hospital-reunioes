/**
 * @vitest-environment jsdom
 */

/**
 * O cartão do Pedido de implantação (issue #2207, ADR 0111).
 *
 * O terceiro tipo do Pedido da Vitta usa o cartão do Passo a passo: os
 * passos, um check por passo, e o Concluir só libera com todos marcados. O
 * nome no cartão é Pedido de implantação. O card fecha quando o Pedido nasce:
 * se o GitHub recusou, o cartão aberto mostra "Não chegou ao GitHub" com o
 * motivo e o Reenviar.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PerguntaDaVitta } from "./CartaoDaPergunta";
import { CartaoDoPedido } from "./CartaoDoPedido";
import { EsperandoVoce } from "./EsperandoVoce";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const TEXTOS = [
  "Escolha quem do hospital vai testar o Canal de Conduta e mande o link para essa pessoa.",
  "Peça que ela faça um relato de teste sem se identificar.",
  "Como saber que acabou: o relato de teste aparece na lista do Canal sem o nome de quem relatou.",
];

const IMPLANTACAO: PerguntaDaVitta = {
  id: "pi-1",
  tipo: "implantacao",
  projeto: "Aplicativo do Hospital",
  assunto: "testar o anonimato do Canal de Conduta",
  texto: "Teste o Canal de Conduta com alguém do hospital antes de divulgar.",
  por_que_precisa: "Só o hospital sabe quem pode testar sem ser identificado.",
  o_que_esta_parado: "A divulgação do Canal espera o teste.",
  o_que_anda_depois: "O Canal é divulgado para todos.",
  ganho: "Quem relata confia que não vai ser identificado.",
  estado: "aberta",
  criado_em: "2026-11-20T10:00:00Z",
  destinatario: "Diretora Clínica",
  passos: TEXTOS.map((texto) => ({ texto, marcado: false })),
  fechamento: { estado: "fechado", motivo: null },
  pode_responder: true,
};

/** O servidor de mentira: guarda os checks e devolve o cartão como o backend. */
function servidor() {
  const marcados = TEXTOS.map(() => false);
  const chamadas: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push(url);
      const corpo = init?.body ? JSON.parse(String(init.body)) : null;
      let resposta: unknown;
      if (url.endsWith("/checks")) {
        marcados[corpo.passo] = corpo.marcado;
        resposta = { ...IMPLANTACAO, passos: TEXTOS.map((texto, i) => ({ texto, marcado: marcados[i] })) };
      } else {
        resposta = { ...IMPLANTACAO, fechamento: { estado: "fechado", motivo: null }, pode_reenviar: false };
      }
      return { ok: true, status: 200, json: async () => resposta } as unknown as Response;
    }),
  );
  return chamadas;
}

const concluir = () => screen.getByRole("button", { name: "Concluir" }) as HTMLButtonElement;

describe("O cartão do Pedido de implantação", () => {
  it("o cartão do Pedido desenha o Pedido de implantação pelo tipo, com os passos", () => {
    render(<CartaoDoPedido pedido={IMPLANTACAO} />);

    const cartao = screen.getByRole("article", { name: "Pedido de implantação" });
    expect(within(cartao).getByRole("img", { name: "Pedido de implantação" })).toBeTruthy();
    expect(within(cartao).getByText("Pedido de implantação")).toBeTruthy();
    expect(within(cartao).getAllByRole("checkbox")).toHaveLength(3);
    expect(screen.queryByRole("article", { name: "Passo a passo da Vitta" })).toBeNull();
    expect(screen.queryByRole("img", { name: "Pergunta" })).toBeNull();
  });

  it("o Concluir só libera com todos os checks marcados", async () => {
    servidor();
    render(<CartaoDoPedido pedido={IMPLANTACAO} token="token-de-teste" />);
    expect(concluir().disabled).toBe(true);

    for (const texto of TEXTOS.slice(0, 2)) {
      fireEvent.click(screen.getByRole("checkbox", { name: texto }));
      await waitFor(() => expect((screen.getByRole("checkbox", { name: texto }) as HTMLInputElement).checked).toBe(true));
    }
    expect(concluir().disabled).toBe(true);

    fireEvent.click(screen.getByRole("checkbox", { name: TEXTOS[2] }));
    await waitFor(() => expect(concluir().disabled).toBe(false));
  });

  it("o cartão aberto com o fechamento que falhou mostra o motivo e o Reenviar", async () => {
    const chamadas = servidor();
    render(
      <CartaoDoPedido
        pedido={{
          ...IMPLANTACAO,
          fechamento: { estado: "falhou", motivo: "O GitHub não aceitou (GitHub respondeu 403)." },
          pode_reenviar: true,
        }}
        token="token-de-teste"
      />,
    );

    const aviso = screen.getByRole("alert");
    expect(within(aviso).getByText("Não chegou ao GitHub")).toBeTruthy();
    expect(within(aviso).getByText("O GitHub não aceitou (GitHub respondeu 403).")).toBeTruthy();
    fireEvent.click(within(aviso).getByRole("button", { name: "Reenviar" }));

    await waitFor(() => expect(screen.queryByText("Não chegou ao GitHub")).toBeNull());
    expect(chamadas.at(-1)).toBe("/api/admin/tecnologia/perguntas/pi-1/reenviar");
  });

  it("a Esperando você mostra o Pedido de implantação com os checks", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => [{ ...IMPLANTACAO, demanda_id: "d-1", demanda: "O Canal de Conduta", minha: true }],
      })) as unknown as typeof fetch,
    );
    render(<EsperandoVoce token="token-de-teste" agora={new Date("2026-11-22T10:00:00Z")} />);

    const regiao = await screen.findByRole("region", { name: "Esperando você" });
    const cartao = within(regiao).getByRole("article", { name: "Pedido de implantação" });
    expect(within(cartao).getAllByRole("checkbox")).toHaveLength(3);
    expect(within(cartao).getByRole("button", { name: "Concluir" })).toBeTruthy();
  });
});
