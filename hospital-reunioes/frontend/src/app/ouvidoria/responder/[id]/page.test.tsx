/**
 * @vitest-environment jsdom
 */

/**
 * A Tela do responsável aberta pelo app (issue #1886, ADR 0099, decisão 4).
 *
 * É a MESMA tela do link do email, aberta pelo botão RESPONDER com o login no
 * lugar do token. O teste de ordem é o mesmo da página do link: a porta muda,
 * a hierarquia da RN-59 não.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ResponderPeloAppPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "uuid-7" }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "sessao-do-carlos" } } }) },
  }),
}));

const NOTA = "Confirmar a escala da recepção no turno da manhã e responder o que foi corrigido.";

function caso(overrides: Record<string, unknown> = {}) {
  return {
    protocolo: "2026-0007",
    setor: "Recepção",
    categoria: "Tempo de espera",
    gravidade: "alto",
    extrato: NOTA,
    blocos: [
      { chave: "resumo", rotulo: "RESUMO", texto: "Espera acima de duas horas." },
      { chave: "relato_integral", rotulo: "RELATO INTEGRAL", texto: "Cheguei às 8h." },
      { chave: "nota_da_ouvidoria", rotulo: "NOTA DA OUVIDORIA", texto: NOTA },
    ],
    aviso: null,
    identificacao: "Joana da Silva",
    paciente: { nome: "Maria Aparecida Souza", referencia: "leito 12" },
    sigiloso: false,
    destinatario_nome: "Carlos Titular",
    aceita_resposta: true,
    rotulo_prazo: "vence em 4 dias úteis",
    vencimento_formatado: "31/08/2026 às 17h00",
    prazo_estourado: false,
    minutos_uteis_restantes: 1080,
    degradado: [],
    prorrogacao: {
      regras: ["Uma vez por manifestação."],
      max_dias_uteis: 30,
      permitida: true,
      motivo: null,
      pedido: null,
    },
    ...overrides,
  };
}

let chamadas: { url: string; init?: RequestInit }[] = [];

function servidor(corpoDaAbertura: unknown, status = 200) {
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, init });
      if (init?.method === "POST") {
        return { ok: true, status: 200, json: async () => ({ anexos_gravados: 0 }) } as unknown as Response;
      }
      return { ok: status < 400, status, json: async () => corpoDaAbertura } as unknown as Response;
    })
  );
}

function vemAntes(a: Element, b: Element): boolean {
  return Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
}

async function abrirTela() {
  render(<ResponderPeloAppPage />);
  await screen.findByText(NOTA);
}

beforeEach(() => {
  servidor(caso());
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("a porta do login", () => {
  it("abre o caso pelo id, com a sessão de quem está logado", async () => {
    await abrirTela();

    expect(chamadas[0].url).toBe("/api/ouvidoria/responder/uuid-7");
    expect(new Headers(chamadas[0].init?.headers).get("Authorization")).toBe("Bearer sessao-do-carlos");
  });

  it("responde pela rota do login, sem token na URL", async () => {
    await abrirTela();

    fireEvent.change(screen.getByLabelText(/o que foi feito/i), {
      target: { value: "Conversamos com a equipe da recepção e abrimos o segundo guichê às 7h." },
    });
    fireEvent.click(screen.getByRole("button", { name: /^responder/i }));

    await waitFor(() => expect(chamadas.some((c) => c.init?.method === "POST")).toBe(true));
    const envio = chamadas.find((c) => c.init?.method === "POST")!;
    expect(envio.url).toBe("/api/ouvidoria/responder/uuid-7/responder");
    expect(new Headers(envio.init?.headers).get("Authorization")).toBe("Bearer sessao-do-carlos");
    expect(await screen.findByText(/resposta registrada/i)).toBeTruthy();
  });

  it("o caso fora do setor de quem está logado diz isso, e não fala em link", async () => {
    servidor({ detail: "Este caso não está com um setor pelo qual você responde" }, 403);
    render(<ResponderPeloAppPage />);

    expect(await screen.findByText("Este caso não está com um setor pelo qual você responde")).toBeTruthy();
    expect(screen.queryByText(/link/i)).toBeNull();
  });
});

describe("a ordem da RN-59, igual à da página do link", () => {
  it("apresenta os elementos de cima para baixo, na ordem que faz responder rápido", async () => {
    await abrirTela();

    const sequencia = [
      screen.getByTestId("faixa-de-gravidade"),
      screen.getByTestId("prazo-regressivo"),
      screen.getByTestId("linha-secundaria"),
      screen.getByTestId("quem-manifestou"),
      screen.getByTestId("paciente-do-caso"),
      screen.getByTestId("bloco-resumo"),
      screen.getByTestId("bloco-relato_integral"),
      screen.getByTestId("bloco-nota_da_ouvidoria"),
      screen.getByLabelText(/o que foi feito/i),
      screen.getByRole("button", { name: /anexar/i }),
      screen.getByRole("button", { name: /^responder/i }),
      screen.getByRole("button", { name: /solicitar prorrogação/i }),
      screen.getByTestId("abrir-devolucao"),
    ];

    for (let i = 0; i < sequencia.length - 1; i++) {
      expect(vemAntes(sequencia[i], sequencia[i + 1])).toBe(true);
    }
  });
});
