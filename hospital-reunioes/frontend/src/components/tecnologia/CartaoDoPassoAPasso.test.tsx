/**
 * @vitest-environment jsdom
 */

/**
 * O cartão do Passo a passo da Vitta (issue #2176, ADR 0110, decisões 4 a 8).
 *
 * Cada passo tem um check, e o Concluir só libera com todos marcados. A
 * anotação é opcional. Concluído, o cartão mostra quem concluiu; se o GitHub
 * recusou o fechamento, "Não chegou ao GitHub" com o motivo e o Reenviar.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PerguntaDaVitta } from "./CartaoDaPergunta";
import { CartaoDoPassoAPasso } from "./CartaoDoPassoAPasso";
import { CartaoDoPedido } from "./CartaoDoPedido";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const TEXTOS = [
  "Abra a aba Segurança do Paciente e clique em Documentos.",
  "Clique em Publicar no Regimento do NSP.",
  "Como saber que acabou: o Regimento aparece como Publicado na lista.",
];

const PEDIDO: PerguntaDaVitta = {
  id: "pp-1",
  tipo: "passo_a_passo",
  projeto: "Aplicativo do Hospital",
  assunto: "publicar o Regimento do NSP",
  texto: "Publique o Regimento do NSP no app.",
  por_que_precisa: "Só a diretoria publica o Regimento.",
  o_que_esta_parado: "A fatia da suplente espera o Regimento publicado.",
  o_que_anda_depois: "A Vitta cadastra a suplente.",
  ganho: "O NSP fica regular na vistoria.",
  estado: "aberta",
  criado_em: "2026-11-20T10:00:00Z",
  destinatario: "Diretora Clínica",
  passos: TEXTOS.map((texto) => ({ texto, marcado: false })),
  pode_responder: true,
};

/** O servidor de mentira: guarda os checks e devolve o cartão como o backend. */
function servidor({ falhaNoGithub = false } = {}) {
  const marcados = TEXTOS.map(() => false);
  const chamadas: { url: string; corpo: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const corpo = init?.body ? JSON.parse(String(init.body)) : null;
      chamadas.push({ url, corpo });
      const passos = TEXTOS.map((texto, i) => ({ texto, marcado: marcados[i], por: marcados[i] ? "Diretora Clínica" : null }));
      let resposta: unknown;
      if (url.endsWith("/checks")) {
        marcados[corpo.passo] = corpo.marcado;
        resposta = { ...PEDIDO, passos: TEXTOS.map((texto, i) => ({ texto, marcado: marcados[i] })) };
      } else if (url.endsWith("/concluir")) {
        resposta = {
          pergunta: {
            ...PEDIDO,
            passos,
            estado: "concluida",
            pode_responder: false,
            pode_reenviar: falhaNoGithub,
            conclusao: { concluida_em: "2026-11-22T17:30:00Z", como: "app", por: "Diretora Clínica", em_nome_de: null, anotacao: corpo.anotacao },
            fechamento: falhaNoGithub
              ? { estado: "falhou", motivo: "O GitHub não aceitou (GitHub respondeu 403)." }
              : { estado: "fechado", motivo: null },
          },
          mensagem: null,
        };
      } else {
        resposta = { ...PEDIDO, passos, estado: "concluida", fechamento: { estado: "fechado", motivo: null } };
      }
      return { ok: true, status: 200, json: async () => resposta } as unknown as Response;
    }),
  );
  return chamadas;
}

const concluir = () => screen.getByRole("button", { name: "Concluir" }) as HTMLButtonElement;

describe("O cartão do Passo a passo", () => {
  it("o Concluir fica desabilitado até o último check", async () => {
    servidor();
    render(<CartaoDoPassoAPasso pedido={PEDIDO} token="token-de-teste" />);
    expect(concluir().disabled).toBe(true);

    fireEvent.click(screen.getByRole("checkbox", { name: TEXTOS[0] }));
    await waitFor(() => expect((screen.getByRole("checkbox", { name: TEXTOS[0] }) as HTMLInputElement).checked).toBe(true));
    fireEvent.click(screen.getByRole("checkbox", { name: TEXTOS[1] }));
    await waitFor(() => expect((screen.getByRole("checkbox", { name: TEXTOS[1] }) as HTMLInputElement).checked).toBe(true));
    expect(concluir().disabled).toBe(true);

    fireEvent.click(screen.getByRole("checkbox", { name: TEXTOS[2] }));
    await waitFor(() => expect(concluir().disabled).toBe(false));
  });

  it("o Concluir manda a anotação e avisa quem desenha o cartão", async () => {
    const chamadas = servidor();
    const onConcluido = vi.fn();
    render(
      <CartaoDoPassoAPasso
        pedido={{ ...PEDIDO, passos: TEXTOS.map((texto) => ({ texto, marcado: true })) }}
        token="token-de-teste"
        onConcluido={onConcluido}
      />,
    );

    fireEvent.change(screen.getByRole("textbox", { name: "Sua anotação (opcional)" }), {
      target: { value: "Publicado com o anexo." },
    });
    fireEvent.click(concluir());

    await waitFor(() => expect(onConcluido).toHaveBeenCalledTimes(1));
    expect(chamadas.at(-1)).toEqual({
      url: "/api/admin/tecnologia/perguntas/pp-1/concluir",
      corpo: { anotacao: "Publicado com o anexo." },
    });
    expect(screen.getByRole("group", { name: "Concluído" }).textContent).toContain("Concluído por Diretora Clínica");
  });

  it("quem não faz o Passo a passo vê os passos sem poder marcar nem concluir", () => {
    render(<CartaoDoPassoAPasso pedido={{ ...PEDIDO, pode_responder: false }} token="token-de-teste" />);

    expect((screen.getByRole("checkbox", { name: TEXTOS[0] }) as HTMLInputElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Concluir" })).toBeNull();
  });

  it("Não chegou ao GitHub mostra o motivo e o Reenviar, que fecha de novo", async () => {
    const chamadas = servidor({ falhaNoGithub: true });
    render(
      <CartaoDoPassoAPasso
        pedido={{ ...PEDIDO, passos: TEXTOS.map((texto) => ({ texto, marcado: true })) }}
        token="token-de-teste"
      />,
    );
    fireEvent.click(concluir());

    const aviso = await screen.findByRole("alert");
    expect(within(aviso).getByText("Não chegou ao GitHub")).toBeTruthy();
    expect(within(aviso).getByText("O GitHub não aceitou (GitHub respondeu 403).")).toBeTruthy();

    fireEvent.click(within(aviso).getByRole("button", { name: "Reenviar" }));

    await waitFor(() => expect(screen.queryByText("Não chegou ao GitHub")).toBeNull());
    expect(chamadas.at(-1)?.url).toBe("/api/admin/tecnologia/perguntas/pp-1/reenviar");
    expect(screen.getByText("O card foi fechado no GitHub.")).toBeTruthy();
  });

  it("o cartão do Pedido desenha o Passo a passo pelo tipo, e a Pergunta sem tipo", () => {
    const { rerender } = render(<CartaoDoPedido pedido={PEDIDO} />);
    expect(screen.getByRole("img", { name: "Passo a passo" })).toBeTruthy();

    rerender(<CartaoDoPedido pedido={{ ...PEDIDO, tipo: undefined, passos: [] }} />);
    expect(screen.getByRole("img", { name: "Pergunta" })).toBeTruthy();
    expect(screen.queryByRole("img", { name: "Passo a passo" })).toBeNull();
  });
});
