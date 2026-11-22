/**
 * @vitest-environment jsdom
 */

/**
 * Gerar a ata de novo quando a reunião para no Erro (issue #1498).
 *
 * A rota `POST /api/reunioes/{id}/reprocessar` já relê a transcrição guardada
 * no Storage e roda o pipeline outra vez, mas nenhuma tela a chamava: a reunião
 * que caía em ERRO só saía dali criando outra reunião e colando a transcrição.
 * O que se prova aqui é a tela inteira, montada pela página de verdade: o botão
 * existe só no ERRO e fora da Secretária, o clique chama a rota uma vez, a tela
 * vai para o processamento, e a falha mostra a frase que o backend mandou.
 */

import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";

import ReuniaoDetailPage from "./page";

const perfil = vi.hoisted(() => ({
  participante: null as Record<string, unknown> | null,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "REU_TESTE" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante: perfil.participante, loading: false, error: null }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "tok" } } }) },
  }),
}));

// O card de signatários tem fetch e polling próprios, fora do que se prova aqui.
// O botão do dublê faz o que o card real faz quando o Sincronizar ou o
// Atualizar finalizam a Ata: chama o `onDesfecho` que a página passou.
vi.mock("@/components/reunioes/SignatariosCard", () => ({
  SignatariosCard: (props: { onDesfecho?: () => void }) => (
    <div data-testid="cartao-signatarios">
      <button type="button" onClick={() => props.onDesfecho?.()}>
        desfecho do cartão
      </button>
    </div>
  ),
}));
// A ata do Núcleo tem a própria tela, testada no componente dela.
vi.mock("@/components/seguranca-do-paciente/AtaDoNucleo", () => ({ AtaDoNucleo: () => null }));

const FACILITADOR = { id: "P_FACIL", nome_completo: "Facilitador", email: "f@hsm.com", access_profile: "regular" };
const SECRETARIA = { id: "P_SECRE", nome_completo: "Secretária", email: "s@hsm.com", access_profile: "secretaria" };

const BOTAO = "Gerar a ata de novo";

function reuniao(status_ata: string, json_ata: unknown) {
  return {
    id_reuniao: "REU_TESTE",
    data: "2026-11-04",
    tipo: "Diretoria",
    titulo: null,
    objetivo: null,
    status_ata,
    total_acoes: 0,
    acoes_concluidas: 0,
    hora_inicio: null,
    hora_fim: null,
    json_ata,
    url_pdf_preliminar: null,
    url_pdf_assinado: null,
    url_transcricao: null,
    envelope_key_clicksign: null,
    data_assinatura: null,
    fonte: "UPLOAD",
    metodo_geracao: "TRANSCRICAO",
    created_at: "2026-11-04T10:00:00Z",
    facilitador_id: "P_FACIL",
  };
}

type Resposta = { status: number; corpo: unknown };

/**
 * Responde o GET da reunião com o status pedido e o POST do reprocessar com a
 * resposta dada (ou com uma promessa que o teste resolve quando quiser).
 */
function servir(
  status_ata: string,
  reprocessar?: Resposta | Promise<Resposta>,
  json_ata: unknown = status_ata === "ERRO" ? { error: "Falha na IA" } : null,
) {
  const chamadas: Array<{ url: string; method: string }> = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    chamadas.push({ url, method });
    if (url === "/api/reunioes/REU_TESTE/reprocessar" && method === "POST") {
      const r = await reprocessar!;
      return { ok: r.status < 400, status: r.status, json: async () => r.corpo } as unknown as Response;
    }
    if (url === "/api/reunioes/REU_TESTE" && method === "GET") {
      return { ok: true, status: 200, json: async () => reuniao(status_ata, json_ata) } as unknown as Response;
    }
    return { ok: true, status: 200, json: async () => [] } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return chamadas;
}

function montar() {
  return render(
    <ToastProvider>
      <ReuniaoDetailPage />
    </ToastProvider>,
  );
}

async function esperarCarregar() {
  await screen.findByText("REU_TESTE");
}

beforeEach(() => {
  perfil.participante = FACILITADOR;
});

afterEach(() => {
  // O vitest deste projeto nao roda com `globals: true`, entao a limpeza
  // automatica do testing-library nao entra sozinha.
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Gerar a ata de novo", () => {
  it("a reunião em ERRO mostra o botão", async () => {
    servir("ERRO");
    montar();
    await esperarCarregar();
    expect(screen.getByRole("button", { name: BOTAO })).toBeTruthy();
  });

  // O orchestrator grava ERRO sem `json_ata.error` em vários caminhos (timeout,
  // falha do pipeline); é o caso comum em produção e também precisa do botão.
  it("a reunião em ERRO sem json_ata mostra o aviso e o botão", async () => {
    servir("ERRO", undefined, null);
    montar();
    await esperarCarregar();
    expect(screen.getByText("Erro no processamento.")).toBeTruthy();
    expect(screen.getByRole("button", { name: BOTAO })).toBeTruthy();
  });

  it.each(["PROCESSANDO", "AGUARDANDO_VALIDACAO", "AGUARDANDO_ASSINATURA", "ASSINADA", "APROVADA"])(
    "a reunião em %s não mostra o botão",
    async (status) => {
      servir(status);
      montar();
      await esperarCarregar();
      expect(screen.queryByRole("button", { name: BOTAO })).toBeNull();
    },
  );

  it("a Secretária não vê o botão na reunião em ERRO", async () => {
    perfil.participante = SECRETARIA;
    servir("ERRO");
    montar();
    await esperarCarregar();
    expect(screen.queryByRole("button", { name: BOTAO })).toBeNull();
  });

  it("o clique chama o reprocessar uma vez, com o botão desabilitado, e a tela passa a processar", async () => {
    let responder: (r: Resposta) => void = () => {};
    const pendente = new Promise<Resposta>((resolve) => { responder = resolve; });
    const chamadas = servir("ERRO", pendente);
    montar();
    await esperarCarregar();

    const botao = screen.getByRole("button", { name: BOTAO }) as HTMLButtonElement;
    fireEvent.click(botao);
    await waitFor(() => expect(botao.disabled).toBe(true));
    // Clique repetido durante a espera não dispara outra chamada.
    fireEvent.click(botao);

    await act(async () => {
      responder({
        status: 200,
        corpo: { id_reuniao: "REU_TESTE", status: "PROCESSANDO", message: "Reprocessamento iniciado" },
      });
    });

    await screen.findByText("A IA está processando a transcrição...");
    expect(screen.queryByRole("button", { name: BOTAO })).toBeNull();
    const posts = chamadas.filter((c) => c.method === "POST");
    expect(posts).toEqual([{ url: "/api/reunioes/REU_TESTE/reprocessar", method: "POST" }]);
  });

  // As frases são do backend: `detail` da rota em reunioes.py (404 e 400) e o
  // `error` que o slowapi devolve no 429 do limite de 3 por minuto.
  it.each([
    [404, { detail: "Arquivo de transcrição não encontrado no Storage" }, "Arquivo de transcrição não encontrado no Storage"],
    [400, { detail: "Reunião já assinada não pode ser reprocessada" }, "Reunião já assinada não pode ser reprocessada"],
    [429, { error: "Rate limit exceeded: 3 per 1 minute" }, "Rate limit exceeded: 3 per 1 minute"],
  ])("falha %i mostra a mensagem do backend e o botão volta a ficar clicável", async (status, corpo, frase) => {
    servir("ERRO", { status, corpo });
    montar();
    await esperarCarregar();

    const botao = screen.getByRole("button", { name: BOTAO }) as HTMLButtonElement;
    fireEvent.click(botao);

    await screen.findByText(frase);
    expect(screen.getByRole("button", { name: BOTAO })).toBe(botao);
    await waitFor(() => expect(botao.disabled).toBe(false));
  });
});

// Issue #1864 (ADR 0098, decisão 6): nada apaga Pendência. O Excluir do super
// admin, que apagava a reunião em qualquer status pelo force, sai do
// cabeçalho; o Desmarcar (a exclusão comum) continua, e a recusa por
// Pendência vem do backend.
describe("Excluir reunião no cabeçalho", () => {
  const SUPER_ADMIN = { id: "P_ADMIN", nome_completo: "Admin", email: "a@hsm.com", access_profile: "super_admin" };

  beforeEach(() => {
    perfil.participante = SUPER_ADMIN;
  });

  it.each(["PROGRAMADA", "AGUARDANDO_VALIDACAO"])(
    "na reunião %s o super admin não tem mais o Excluir em qualquer status",
    async (status) => {
      servir(status);
      montar();
      await esperarCarregar();

      expect(screen.queryByRole("button", { name: "Excluir" })).toBeNull();
      expect(screen.getByRole("button", { name: "Desmarcar" })).toBeTruthy();
    },
  );
});

// A Ata Guiada recusa a reunião do Núcleo (revisão do PR #1798, issue #1775):
// o cartão que a abre não aparece nela, só na reunião comum.
describe("Ata Guiada na reunião do Núcleo", () => {
  function servirProgramada(do_nucleo: boolean) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/reunioes/REU_TESTE") {
          const corpo = { ...reuniao("PROGRAMADA", null), do_nucleo };
          return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
        }
        return { ok: true, status: 200, json: async () => [] } as unknown as Response;
      }),
    );
  }

  it("a reunião comum mostra o cartão da Ata Guiada", async () => {
    servirProgramada(false);
    montar();
    expect(await screen.findByRole("button", { name: "Iniciar Ata Guiada" })).toBeTruthy();
  });

  it("a reunião do Núcleo não mostra o cartão da Ata Guiada", async () => {
    servirProgramada(true);
    montar();
    await screen.findByText("Anexar Transcrição e Processar com IA");
    expect(screen.queryByRole("button", { name: "Iniciar Ata Guiada" })).toBeNull();
  });
});

// A ata do Núcleo tem envelope próprio (issue #1776): o cartão de signatários
// e o banner de aprovada sem assinatura são da reunião comum.
describe("assinatura na reunião do Núcleo", () => {
  function servir(status_ata: string, do_nucleo: boolean) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/reunioes/REU_TESTE") {
          const corpo = {
            ...reuniao(status_ata, { modelo: do_nucleo ? "nsp_dez_blocos" : undefined }),
            envelope_key_clicksign: "doc-key",
            do_nucleo,
          };
          return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
        }
        return { ok: true, status: 200, json: async () => [] } as unknown as Response;
      }),
    );
  }

  it("a reunião comum aguardando assinatura mostra o cartão de signatários", async () => {
    servir("AGUARDANDO_ASSINATURA", false);
    montar();
    expect(await screen.findByTestId("cartao-signatarios")).toBeTruthy();
  });

  it("a reunião do Núcleo aguardando assinatura não mostra o cartão de signatários", async () => {
    servir("AGUARDANDO_ASSINATURA", true);
    montar();
    await esperarCarregar();
    expect(screen.queryByTestId("cartao-signatarios")).toBeNull();
  });

  // Issue #1904: depois que todos assinam, a tela sai de "Aguardando
  // assinatura digital" e mostra a Ata Assinada.
  it("a reunião comum assinada mostra o banner de assinada e não o cartão de signatários", async () => {
    servir("ASSINADA", false);
    montar();
    expect(await screen.findByText("Ata Assinada Digitalmente")).toBeTruthy();
    expect(screen.queryByTestId("cartao-signatarios")).toBeNull();
  });

  // Issue #1904, a troca na tela: o Sincronizar ou o Atualizar finalizam a Ata
  // no banco e o card avisa a página, que relê a Reunião e sai do aguardando
  // sem recarregar a página.
  it("o desfecho do cartão relê a Reunião e a tela passa de aguardando para assinada", async () => {
    const statusPorLeitura = ["AGUARDANDO_ASSINATURA", "ASSINADA"];
    let leituras = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url === "/api/reunioes/REU_TESTE" && (init?.method ?? "GET") === "GET") {
          const status_ata = statusPorLeitura[Math.min(leituras, statusPorLeitura.length - 1)];
          leituras += 1;
          const corpo = { ...reuniao(status_ata, null), envelope_key_clicksign: "doc-key", do_nucleo: false };
          return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
        }
        return { ok: true, status: 200, json: async () => [] } as unknown as Response;
      }),
    );
    montar();

    expect(await screen.findByTestId("cartao-signatarios")).toBeTruthy();
    expect(screen.queryByText("Ata Assinada Digitalmente")).toBeNull();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "desfecho do cartão" }));
    });

    expect(await screen.findByText("Ata Assinada Digitalmente")).toBeTruthy();
    expect(screen.queryByTestId("cartao-signatarios")).toBeNull();
    expect(leituras).toBe(2);
  });

  it("a reunião comum aprovada mostra o banner de aprovada sem assinatura", async () => {
    servir("APROVADA", false);
    montar();
    expect(await screen.findByText("Ata Aprovada")).toBeTruthy();
  });

  it("a ata do Núcleo validada não aparece como aprovada sem assinatura", async () => {
    servir("APROVADA", true);
    montar();
    await esperarCarregar();
    expect(screen.queryByText("Ata Aprovada")).toBeNull();
  });
});

// A Pendência nasce no envio (issue #1867): a Reunião já está aguardando
// assinatura quando a ClickSign falha, e o Reenviar fica nesse estado.
describe("falha da ClickSign depois do envio", () => {
  function servir(extra: Record<string, unknown>) {
    const chamadas: Array<{ url: string; method: string }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        chamadas.push({ url, method });
        if (url === "/api/reunioes/REU_TESTE" && method === "GET") {
          const corpo = { ...reuniao("AGUARDANDO_ASSINATURA", null), ...extra };
          return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
        }
        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      }),
    );
    return chamadas;
  }

  it("sem Envelope e com a falha registrada, mostra o Reenviar e não o cartão de signatários", async () => {
    const chamadas = servir({ falha_envio_assinatura: { passo: "criar_envelope", detalhe: "HTTP 500" } });
    montar();

    const botao = await screen.findByRole("button", { name: /Reenviar para assinatura/ });
    expect(screen.getByText(/As pendências já foram criadas/)).toBeTruthy();
    expect(screen.queryByTestId("cartao-signatarios")).toBeNull();

    await act(async () => {
      fireEvent.click(botao);
    });
    await waitFor(() =>
      expect(chamadas.filter((c) => c.url === "/api/reunioes/REU_TESTE/aprovar" && c.method === "POST")).toHaveLength(1),
    );
  });

  it("com o Envelope gravado, não mostra o Reenviar", async () => {
    servir({
      envelope_key_clicksign: "doc-key",
      falha_envio_assinatura: { passo: "notificar_signatarios", detalhe: "x" },
    });
    montar();

    expect(await screen.findByTestId("cartao-signatarios")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Reenviar para assinatura/ })).toBeNull();
  });
});
