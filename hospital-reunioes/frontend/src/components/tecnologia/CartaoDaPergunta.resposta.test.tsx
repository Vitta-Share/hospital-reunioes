/**
 * @vitest-environment jsdom
 */

/**
 * Responder a Pergunta da Vitta no cartão (issue #2119, PRD #2112, ADR 0109,
 * decisões 4 e 5).
 *
 * As opções prontas, na mesma peça do Planejamento da Demanda (a recomendada
 * em destaque, o porquê embaixo), e o campo livre. Quem não pode responder vê
 * o cartão sem o campo. A Pergunta respondida mostra a resposta, com os dois
 * nomes quando um Desenvolvedor registrou no lugar do Destinatário.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CartaoDaPergunta, type PerguntaDaVitta } from "./CartaoDaPergunta";
import { ConversaDaDemanda } from "./ConversaDaDemanda";

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

const URL = "/api/admin/tecnologia/perguntas/p-1/resposta";

const RESPONDIDA = {
  pergunta: {
    ...PERGUNTA,
    estado: "respondida",
    pode_responder: false,
    resposta: {
      opcao: "B",
      opcao_texto: "Quem presidiu a reunião",
      texto: null,
      respondida_em: "2026-11-21T09:00:00Z",
      respondida_por: "Diretora Clínica",
      em_nome_de: null,
    },
  },
  mensagem: {
    id: "m-9",
    autor: "Diretora Clínica",
    texto: "Resposta: B) Quem presidiu a reunião",
    criado_em: "2026-11-21T09:00:00Z",
    minha: true,
  },
};

function servidor(status = 200, corpo: unknown = RESPONDIDA) {
  const chamadas: { url: string; metodo: string; corpo: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, metodo: init?.method ?? "GET", corpo: init?.body ? JSON.parse(String(init.body)) : null });
      return { ok: status < 400, status, json: async () => corpo } as unknown as Response;
    }),
  );
  return chamadas;
}

function cartao() {
  return screen.getByRole("article", { name: "Pergunta da Vitta" });
}

describe("Responder a Pergunta da Vitta no cartão", () => {
  it("mostra as opções com a recomendada em destaque e o porquê embaixo", () => {
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" />);

    const opcoes = within(within(cartao()).getByRole("group", { name: "Opções" })).getAllByRole("button");
    expect(opcoes.map((b) => b.textContent)).toEqual(["AO diretor geral", "BQuem presidiu a reuniãoRecomendada"]);
    expect(
      within(cartao()).getByText("Por que recomendo a B: Quem presidiu esteve na reunião e conhece o que foi decidido."),
    ).toBeTruthy();
  });

  it("o clique numa opção responde com a letra e avisa quem desenha a Conversa", async () => {
    const chamadas = servidor();
    const aoResponder = vi.fn();
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" onRespondida={aoResponder} />);

    fireEvent.click(within(cartao()).getByRole("button", { name: /Quem presidiu a reunião/ }));

    await waitFor(() => expect(aoResponder).toHaveBeenCalledWith(RESPONDIDA));
    expect(chamadas).toEqual([{ url: URL, metodo: "POST", corpo: { opcao: "B" } }]);
  });

  it("o campo livre responde com o texto escrito", async () => {
    const chamadas = servidor();
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" onRespondida={vi.fn()} />);

    const campo = within(cartao()).getByRole("textbox", { name: "Sua resposta" });
    const botao = within(cartao()).getByRole("button", { name: "Responder" });
    expect((botao as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(campo, { target: { value: "Quem estiver de plantão." } });
    fireEvent.click(botao);

    await waitFor(() => expect(chamadas).toHaveLength(1));
    expect(chamadas[0]).toEqual({ url: URL, metodo: "POST", corpo: { texto: "Quem estiver de plantão." } });
  });

  it("a recusa do servidor aparece no cartão com o motivo", async () => {
    servidor(409, { detail: "Esta Pergunta já não espera resposta." });
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" onRespondida={vi.fn()} />);

    fireEvent.click(within(cartao()).getByRole("button", { name: /O diretor geral/ }));

    expect(await within(cartao()).findByRole("alert")).toHaveProperty(
      "textContent",
      "Esta Pergunta já não espera resposta.",
    );
  });

  it("quem não pode responder vê o cartão com as opções, sem botão nem campo de resposta", () => {
    render(<CartaoDaPergunta pergunta={{ ...PERGUNTA, pode_responder: false }} token="t" />);

    expect(within(cartao()).getByText("Quem presidiu a reunião")).toBeTruthy();
    expect(within(cartao()).queryByRole("button")).toBeNull();
    expect(within(cartao()).queryByRole("textbox")).toBeNull();
  });

  it("a pergunta respondida mostra a resposta e quem respondeu, sem campo", () => {
    render(<CartaoDaPergunta pergunta={RESPONDIDA.pergunta as PerguntaDaVitta} token="t" />);

    const resposta = within(cartao()).getByRole("group", { name: "Resposta" });
    expect(resposta.textContent).toContain("B) Quem presidiu a reunião");
    expect(resposta.textContent).toContain("Respondida por Diretora Clínica");
    expect(within(cartao()).queryByRole("textbox")).toBeNull();
    expect(within(cartao()).queryByRole("button")).toBeNull();
  });

  it("a resposta registrada pelo Desenvolvedor mostra os dois nomes", () => {
    const registrada = {
      ...RESPONDIDA.pergunta,
      resposta: {
        ...RESPONDIDA.pergunta.resposta,
        opcao: null,
        opcao_texto: null,
        texto: "Ela disse que é o diretor geral.",
        respondida_por: "Pedro Rezende",
        em_nome_de: "Diretora Clínica",
      },
    } as PerguntaDaVitta;
    render(<CartaoDaPergunta pergunta={registrada} token="t" />);

    const resposta = within(cartao()).getByRole("group", { name: "Resposta" });
    expect(resposta.textContent).toContain("Ela disse que é o diretor geral.");
    expect(resposta.textContent).toContain("Registrada por Pedro Rezende em nome de Diretora Clínica");
  });

  it("na Conversa da Demanda, a resposta troca o cartão e entra como mensagem de quem respondeu", async () => {
    const conversa = {
      mensagens: [
        {
          id: "m-1",
          autor: "Pedro Rezende",
          texto: PERGUNTA.texto,
          criado_em: "2026-11-18T10:00:00Z",
          minha: false,
          pergunta: PERGUNTA,
        },
      ],
      mencionaveis: [],
      envio: null,
    };
    const chamadas: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        chamadas.push(`${init?.method ?? "GET"} ${url}`);
        const corpo = init?.method === "POST" ? RESPONDIDA : conversa;
        return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
      }),
    );
    render(<ConversaDaDemanda demandaId="d-1" token="t" />);

    await screen.findByRole("article", { name: "Pergunta da Vitta" });
    fireEvent.click(within(cartao()).getByRole("button", { name: /Quem presidiu a reunião/ }));

    const area = screen.getByRole("region", { name: "Conversa da Demanda" });
    expect(await within(area).findByText("Resposta: B) Quem presidiu a reunião")).toBeTruthy();
    expect(within(cartao()).getByText("Respondida")).toBeTruthy();
    expect(within(cartao()).getByRole("group", { name: "Resposta" })).toBeTruthy();
    expect(within(cartao()).queryByRole("textbox")).toBeNull();
    expect(chamadas).toEqual(["GET /api/admin/tecnologia/chat/d-1/conversa", `POST ${URL}`]);
  });

  it("não chama a Pergunta de Pendência nem usa itálico, com a resposta aberta", () => {
    render(<CartaoDaPergunta pergunta={PERGUNTA} token="t" />);

    expect(cartao().textContent).not.toMatch(/Pend[êe]ncia/i);
    expect(cartao().querySelector("em, i, .italic, [class*='font-serif']")).toBeNull();
  });
});
