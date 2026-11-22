/**
 * @vitest-environment jsdom
 */

/**
 * A lista Esperando sua resposta (issue #2118, PRD #2112, ADR 0109, decisão 5).
 *
 * No topo da aba Tecnologia, as Perguntas da Vitta abertas de todos os
 * Projetos, no cartão da Pergunta, com o nome da Demanda. A ordem vem do
 * servidor (as do logado primeiro, a mais antiga primeiro). Lista vazia não
 * ocupa espaço, e o link do aviso põe o cartão em foco.
 *
 * Responder no cartão da lista (issue #2145): quem o servidor diz que responde
 * vê as opções, o campo livre e o Me explique, como na Conversa da Demanda; a
 * Pergunta respondida sai da lista na hora, sem reler.
 */

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EsperandoSuaResposta, URL_DA_LISTA_ESPERANDO } from "./EsperandoSuaResposta";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const LINHAS = {
  por_que_precisa: "Só a diretoria decide quem assina a ata em nome do hospital.",
  o_que_esta_parado: "A tela de assinatura da Ata espera essa regra para sair.",
  o_que_anda_depois: "A Vitta termina a tela e ela entra na próxima subida.",
  ganho: "A ata sai assinada no mesmo dia da reunião.",
};

const MINHA = {
  id: "p-1",
  demanda_id: "d-1",
  demanda: "A Ata assinada no app",
  projeto: "Aplicativo do Hospital",
  assunto: "quem assina a Ata",
  texto: "Quem assina a Ata em nome da diretoria quando a senhora não está?",
  ...LINHAS,
  estado: "aberta",
  criado_em: "2026-11-18T10:00:00Z",
  destinatario: "Diretora Clínica",
  minha: true,
};

const DE_OUTRO = {
  ...MINHA,
  id: "p-2",
  demanda_id: "d-2",
  demanda: "A agenda do diretor no celular",
  projeto: "PedroOS",
  texto: "A agenda mostra a semana inteira ou só o dia?",
  criado_em: "2026-11-20T10:00:00Z",
  destinatario: "Diretor Geral",
  minha: false,
};

const AGORA = new Date("2026-11-21T12:00:00Z");

function montar(corpo: unknown, { status = 200, perguntaEmFoco = null }: { status?: number; perguntaEmFoco?: string | null } = {}) {
  const pedidos: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      pedidos.push({ url, init });
      return { ok: status < 400, status, json: async () => corpo } as unknown as Response;
    }),
  );
  const { container, rerender } = render(
    <EsperandoSuaResposta token="token-de-teste" perguntaEmFoco={perguntaEmFoco} agora={AGORA} />,
  );
  return { pedidos, container, rerender };
}

function lista() {
  return screen.findByRole("region", { name: "Esperando sua resposta" });
}

describe("A lista Esperando sua resposta", () => {
  it("pede as Perguntas abertas com o token e mostra cada uma no cartão, com a Demanda, o Projeto e os dias", async () => {
    const { pedidos } = montar([MINHA, DE_OUTRO]);

    const regiao = await lista();

    expect(pedidos[0].url).toBe(URL_DA_LISTA_ESPERANDO);
    expect(URL_DA_LISTA_ESPERANDO).toBe("/api/admin/tecnologia/perguntas/esperando");
    expect((pedidos[0].init?.headers as Record<string, string>).Authorization).toBe("Bearer token-de-teste");
    const itens = within(regiao).getAllByRole("listitem");
    expect(itens).toHaveLength(2);
    const [primeiro, segundo] = itens;
    expect(primeiro.textContent).toContain("A Ata assinada no app");
    expect(within(primeiro).getByRole("article", { name: "Pergunta da Vitta" }).textContent).toContain(
      "Aplicativo do Hospital",
    );
    expect(primeiro.textContent).toContain("Esperando há 3 dias");
    expect(segundo.textContent).toContain("A agenda do diretor no celular");
    expect(segundo.textContent).toContain("PedroOS");
    expect(segundo.textContent).toContain("Esperando há 1 dia");
  });

  it("mantém a ordem do servidor: as do usuário logado primeiro", async () => {
    montar([MINHA, DE_OUTRO]);

    const itens = within(await lista()).getAllByRole("listitem");

    expect(itens.map((i) => within(i).getByRole("article").textContent?.includes("Diretora Clínica"))).toEqual([
      true,
      false,
    ]);
  });

  it("sem Pergunta aberta, a lista não aparece", async () => {
    const { pedidos, container } = montar([]);

    await waitFor(() => expect(pedidos).toHaveLength(1));

    expect(screen.queryByRole("region", { name: "Esperando sua resposta" })).toBeNull();
    expect(container.innerHTML).toBe("");
  });

  it("quem não é Super admin recebe a recusa do servidor e não vê nada", async () => {
    const { pedidos, container } = montar({ detail: "Acesso restrito" }, { status: 403 });

    await waitFor(() => expect(pedidos).toHaveLength(1));

    expect(container.innerHTML).toBe("");
  });

  it("o link do aviso põe o cartão da Pergunta em foco", async () => {
    const rolar = vi.fn();
    Element.prototype.scrollIntoView = rolar;
    montar([MINHA, DE_OUTRO], { perguntaEmFoco: "p-2" });

    const [, segundo] = within(await lista()).getAllByRole("listitem");

    await waitFor(() => expect(document.activeElement).toBe(segundo));
    expect(rolar).toHaveBeenCalled();
    expect(segundo.getAttribute("aria-current")).toBe("true");
  });

  it("com a aba aberta, o sino de uma Pergunta que nasceu depois relê a lista e põe o cartão dela em foco", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    let respostas: unknown[] = [[]];
    const pedidos: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        pedidos.push(url);
        const corpo = respostas[Math.min(pedidos.length - 1, respostas.length - 1)];
        return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
      }),
    );
    const { rerender } = render(<EsperandoSuaResposta token="token-de-teste" agora={AGORA} />);
    await waitFor(() => expect(pedidos).toHaveLength(1));
    expect(screen.queryByRole("region", { name: "Esperando sua resposta" })).toBeNull();

    respostas = [[], [MINHA]];
    rerender(<EsperandoSuaResposta token="token-de-teste" perguntaEmFoco="p-1" agora={AGORA} />);

    const [item] = within(await lista()).getAllByRole("listitem");
    expect(pedidos).toHaveLength(2);
    await waitFor(() => expect(document.activeElement).toBe(item));
    expect(item.getAttribute("aria-current")).toBe("true");
  });

  it("o sino de uma Pergunta que já está na lista põe o cartão em foco sem reler", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    const { pedidos, rerender } = montar([MINHA, DE_OUTRO]);
    await lista();

    rerender(<EsperandoSuaResposta token="token-de-teste" perguntaEmFoco="p-2" agora={AGORA} />);

    const [, segundo] = within(await lista()).getAllByRole("listitem");
    await waitFor(() => expect(document.activeElement).toBe(segundo));
    await act(() => new Promise((pronto) => setTimeout(pronto, 50)));
    expect(pedidos).toHaveLength(1);
  });

  it("no celular a lista cabe na tela, sem largura fixa que force rolagem lateral", async () => {
    montar([MINHA]);

    const regiao = await lista();

    const [item] = within(regiao).getAllByRole("listitem");
    expect(item.className.split(" ")).toEqual(expect.arrayContaining(["min-w-0", "break-words"]));
    for (const elemento of [regiao, ...regiao.querySelectorAll("*")]) {
      const classes = (elemento.getAttribute("class") ?? "").split(" ");
      expect(classes.filter((c) => /^(w-\[|min-w-\[|grid-cols-[2-9]|whitespace-nowrap|overflow-x-scroll)/.test(c))).toEqual(
        [],
      );
    }
  });
});

describe("Responder no cartão da lista (issue #2145)", () => {
  const OPCOES = {
    opcoes: [
      { letra: "A", texto: "O diretor geral" },
      { letra: "B", texto: "Quem presidiu a reunião" },
    ],
    recomendada: "B",
    porque: "Quem presidiu esteve na reunião.",
  };
  const RESPONDE = { ...MINHA, ...OPCOES, pode_responder: true };
  const SO_LE = { ...DE_OUTRO, ...OPCOES, pode_responder: false };

  /** O servidor: a lista no GET e a Pergunta respondida no POST da resposta. */
  function servidor(itens: unknown[]) {
    const pedidos: { url: string; metodo: string; corpo: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const metodo = init?.method ?? "GET";
        pedidos.push({ url, metodo, corpo: init?.body ? JSON.parse(String(init.body)) : null });
        const corpo =
          metodo === "POST"
            ? {
                pergunta: { ...RESPONDE, estado: "respondida", pode_responder: false },
                mensagem: { id: "m-9", autor: "Diretora Clínica", texto: "Resposta: B) Quem presidiu a reunião", criado_em: null, minha: true },
              }
            : itens;
        return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
      }),
    );
    render(<EsperandoSuaResposta token="token-de-teste" agora={AGORA} />);
    return pedidos;
  }

  async function cartoes() {
    return within(await lista()).getAllByRole("article", { name: "Pergunta da Vitta" });
  }

  it("quem pode responder vê no cartão da lista as opções para clicar, o campo livre e o Me explique", async () => {
    servidor([RESPONDE]);

    const [cartao] = await cartoes();

    expect(within(cartao).getByRole("button", { name: /Quem presidiu a reunião/ })).toBeTruthy();
    expect(within(cartao).getByRole("textbox", { name: "Sua resposta" })).toBeTruthy();
    expect(within(cartao).getByRole("button", { name: "Responder" })).toBeTruthy();
    expect(within(cartao).getByRole("button", { name: "Me explique" })).toBeTruthy();
  });

  it("outro Super admin vê o cartão da lista sem o campo de resposta e sem o Me explique", async () => {
    servidor([SO_LE]);

    const [cartao] = await cartoes();

    expect(within(cartao).queryByRole("textbox", { name: "Sua resposta" })).toBeNull();
    expect(within(cartao).queryByRole("button", { name: "Responder" })).toBeNull();
    expect(within(cartao).queryByRole("button", { name: "Me explique" })).toBeNull();
    expect(within(cartao).queryByRole("button", { name: /Quem presidiu a reunião/ })).toBeNull();
  });

  it("o clique numa opção responde pela rota da resposta e a Pergunta sai da lista sem reler", async () => {
    const pedidos = servidor([RESPONDE, SO_LE]);
    const [cartao] = await cartoes();

    fireEvent.click(within(cartao).getByRole("button", { name: /Quem presidiu a reunião/ }));

    await waitFor(async () => expect(await cartoes()).toHaveLength(1));
    expect(pedidos.filter((p) => p.metodo === "POST")).toEqual([
      { url: "/api/admin/tecnologia/perguntas/p-1/resposta", metodo: "POST", corpo: { opcao: "B" } },
    ]);
    expect(pedidos.filter((p) => p.metodo === "GET")).toHaveLength(1);
    expect(within(await lista()).getByRole("heading").textContent).toContain("(1)");
    expect((await lista()).textContent).not.toContain(MINHA.texto);
  });

  it("o campo livre responde e, com a última Pergunta respondida, a lista some", async () => {
    const pedidos = servidor([RESPONDE]);
    const [cartao] = await cartoes();

    fireEvent.change(within(cartao).getByRole("textbox", { name: "Sua resposta" }), {
      target: { value: "Quem estiver de plantão." },
    });
    fireEvent.click(within(cartao).getByRole("button", { name: "Responder" }));

    await waitFor(() => expect(screen.queryByRole("region", { name: "Esperando sua resposta" })).toBeNull());
    expect(pedidos.find((p) => p.metodo === "POST")?.corpo).toEqual({ texto: "Quem estiver de plantão." });
  });
});
