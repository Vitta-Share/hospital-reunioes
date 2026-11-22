/**
 * @vitest-environment jsdom
 */

/**
 * O Me explique no cartão da Pergunta da Vitta (issue #2122, PRD #2112, ADR
 * 0109, decisão 8).
 *
 * O botão abre a conversa particular com o Assistente, já com a explicação.
 * A pessoa pergunta por texto. O rascunho só vai para o campo de resposta do
 * cartão com o clique em "Usar este rascunho", e ela ainda edita antes de
 * enviar: nada é respondido sem o clique em Responder.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CartaoDaPergunta, type PerguntaDaVitta } from "./CartaoDaPergunta";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
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
  opcoes: [],
  recomendada: null,
  porque: null,
  estado: "aberta",
  criado_em: "2026-11-18T10:00:00Z",
  destinatario: "Diretora Clínica",
  resposta: null,
  pode_responder: true,
};

const URL = "/api/admin/tecnologia/perguntas/p-1/me-explique";
const URL_DA_RESPOSTA = "/api/admin/tecnologia/perguntas/p-1/resposta";

const EXPLICACAO = {
  papel: "assistente",
  texto: "A Vitta quer saber quem assina a ata quando a diretora clínica não está.",
  rascunho: "Quem presidiu a reunião assina.",
};

type Chamada = { url: string; metodo: string; corpo: unknown };

/** O servidor de mentira: cada rota devolve o corpo dado, por método e endereço. */
function servidor(respostas: Record<string, unknown>) {
  const chamadas: Chamada[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const metodo = init?.method ?? "GET";
      chamadas.push({ url, metodo, corpo: init?.body ? JSON.parse(String(init.body)) : null });
      const corpo = respostas[`${metodo} ${url}`];
      return { ok: corpo !== undefined, status: corpo === undefined ? 500 : 200, json: async () => corpo } as Response;
    }),
  );
  return chamadas;
}

function cartao() {
  return screen.getByRole("article", { name: "Pergunta da Vitta" });
}

function painel() {
  return within(cartao()).getByRole("region", { name: "Me explique" });
}

describe("Me explique no cartão da Pergunta da Vitta", () => {
  it("o botão abre a conversa já com a explicação do Assistente", async () => {
    const chamadas = servidor({ [`GET ${URL}`]: { mensagens: [] }, [`POST ${URL}`]: { mensagens: [EXPLICACAO] } });
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" />);

    fireEvent.click(within(cartao()).getByRole("button", { name: "Me explique" }));

    expect(await within(painel()).findByText(EXPLICACAO.texto)).toBeTruthy();
    expect(chamadas.map((c) => `${c.metodo} ${c.url}`)).toEqual([`GET ${URL}`, `POST ${URL}`]);
    expect(chamadas[1].corpo).toEqual({});
  });

  it("reabrir mostra o que já foi dito, sem chamar o Assistente de novo", async () => {
    const pessoa = { papel: "pessoa", texto: "E se eu não souber?", rascunho: null };
    const chamadas = servidor({ [`GET ${URL}`]: { mensagens: [EXPLICACAO, pessoa] } });
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" />);

    fireEvent.click(within(cartao()).getByRole("button", { name: "Me explique" }));

    expect(await within(painel()).findByText("E se eu não souber?")).toBeTruthy();
    expect(within(painel()).getByText(EXPLICACAO.texto)).toBeTruthy();
    expect(chamadas.map((c) => c.metodo)).toEqual(["GET"]);
  });

  it("a pessoa pergunta por texto e recebe a resposta do Assistente", async () => {
    const resposta = { papel: "assistente", texto: "Não muda a ata de ontem.", rascunho: null };
    const pessoa = { papel: "pessoa", texto: "Isso muda a ata de ontem?", rascunho: null };
    const chamadas = servidor({
      [`GET ${URL}`]: { mensagens: [EXPLICACAO] },
      [`POST ${URL}`]: { mensagens: [EXPLICACAO, pessoa, resposta] },
    });
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" />);
    fireEvent.click(within(cartao()).getByRole("button", { name: "Me explique" }));
    await within(painel()).findByText(EXPLICACAO.texto);

    fireEvent.change(within(painel()).getByRole("textbox", { name: "Pergunte ao Assistente" }), {
      target: { value: "Isso muda a ata de ontem?" },
    });
    fireEvent.click(within(painel()).getByRole("button", { name: "Perguntar" }));

    expect(await within(painel()).findByText("Não muda a ata de ontem.")).toBeTruthy();
    expect(within(painel()).getByText("Isso muda a ata de ontem?")).toBeTruthy();
    expect(chamadas[1]).toEqual({ url: URL, metodo: "POST", corpo: { texto: "Isso muda a ata de ontem?" } });
  });

  it("o rascunho só vai para o campo de resposta com o clique, e a pessoa edita antes de enviar", async () => {
    const chamadas = servidor({
      [`GET ${URL}`]: { mensagens: [EXPLICACAO] },
      [`POST ${URL_DA_RESPOSTA}`]: undefined,
    });
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" onRespondida={vi.fn()} />);
    fireEvent.click(within(cartao()).getByRole("button", { name: "Me explique" }));
    await within(painel()).findByText(EXPLICACAO.texto);
    const campo = within(cartao()).getByRole("textbox", { name: "Sua resposta" }) as HTMLTextAreaElement;
    expect(campo.value).toBe("");

    fireEvent.click(within(painel()).getByRole("button", { name: "Usar este rascunho" }));

    expect(campo.value).toBe("Quem presidiu a reunião assina.");
    fireEvent.change(campo, { target: { value: "Quem presidiu a reunião assina, e eu confiro depois." } });
    expect(chamadas.some((c) => c.url === URL_DA_RESPOSTA)).toBe(false);

    fireEvent.click(within(cartao()).getByRole("button", { name: "Responder" }));

    await waitFor(() => expect(chamadas.some((c) => c.url === URL_DA_RESPOSTA)).toBe(true));
    expect(chamadas.find((c) => c.url === URL_DA_RESPOSTA)?.corpo).toEqual({
      texto: "Quem presidiu a reunião assina, e eu confiro depois.",
    });
  });

  it("a falha do Assistente aparece no painel com o motivo do servidor", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) =>
        init?.method === "POST"
          ? ({
              ok: false,
              status: 502,
              json: async () => ({ detail: "O assistente não conseguiu responder agora. Tente de novo." }),
            } as Response)
          : ({ ok: true, status: 200, json: async () => ({ mensagens: [] }) } as Response),
      ),
    );
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" />);

    fireEvent.click(within(cartao()).getByRole("button", { name: "Me explique" }));

    expect(await within(painel()).findByRole("alert")).toHaveProperty(
      "textContent",
      "O assistente não conseguiu responder agora. Tente de novo.",
    );
  });

  it("quem não pode responder não vê o Me explique", () => {
    render(<CartaoDaPergunta pergunta={{ ...PERGUNTA, pode_responder: false }} token="t" />);

    expect(within(cartao()).queryByRole("button", { name: "Me explique" })).toBeNull();
  });

  it("o painel não chama a Pergunta de Pendência nem usa itálico", async () => {
    servidor({ [`GET ${URL}`]: { mensagens: [EXPLICACAO] } });
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" />);

    fireEvent.click(within(cartao()).getByRole("button", { name: "Me explique" }));
    await within(painel()).findByText(EXPLICACAO.texto);

    expect(cartao().textContent).not.toMatch(/Pend[êe]ncia/i);
    expect(cartao().querySelector("em, i, .italic, [class*='font-serif']")).toBeNull();
  });
});
