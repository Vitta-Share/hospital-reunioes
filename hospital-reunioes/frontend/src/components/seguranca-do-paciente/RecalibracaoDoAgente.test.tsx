/**
 * @vitest-environment jsdom
 */

/**
 * A recalibração do agente do Núcleo (issue #2001). A tela mostra os itens
 * das seções 4 e 5 do Anexo F, com "Sem dados nesta fase" no que ainda não
 * tem dado, e quem tem Acesso pleno registra uma das três decisões; sem
 * escolha, o botão não grava. A concordância por eixo aparece na Configuração.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConcordanciaDoAgente } from "./ConcordanciaDoAgente";
import { RecalibracaoDoAgente } from "./RecalibracaoDoAgente";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const DECISOES = [
  { valor: "manter", rotulo: "Manter o agente como está" },
  { valor: "ajustar", rotulo: "Ajustar o prompt e a base" },
  { valor: "ligar_lote", rotulo: "Ligar a aprovação em lote" },
];

function tela(podeDecidir: boolean) {
  return {
    pode_decidir: podeDecidir,
    decisoes: DECISOES,
    recalibracoes: [{ marco: 30, devida_em: "2026-10-31", decisao: null, decidido_por: null, decidido_em: null }],
    itens: [
      {
        numero: 1,
        secao: 4,
        titulo: "Volume de notificações",
        sinal: "Setor assistencial com zero notificação",
        com_dados: true,
        linhas: ["4 notificações nos últimos 30 dias."],
        alerta: false,
      },
      {
        numero: 5,
        secao: 4,
        titulo: "Prazos legais",
        sinal: "Qualquer atraso",
        com_dados: false,
        linhas: [],
        alerta: false,
      },
      {
        numero: 13,
        secao: 5,
        titulo: "Aprovação em lote",
        sinal: "Abaixo de 90%: manter o lote desligado",
        com_dados: true,
        linhas: ["Casos leves confirmados nas últimas 4 semanas: 1 de 2 sem ajuste (50%)."],
        alerta: true,
      },
    ],
  };
}

const enviados: unknown[] = [];
let corpoDaTela = tela(true);

beforeEach(() => {
  enviados.length = 0;
  corpoDaTela = tela(true);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        enviados.push({ url, corpo: JSON.parse(String(init.body)) });
        return {
          ok: true,
          status: 200,
          json: async () => ({
            recalibracoes: [
              {
                marco: 30,
                devida_em: "2026-10-31",
                decisao: "ajustar",
                decidido_por: "Pessoa de Teste",
                decidido_em: "2026-11-02T13:00:00+00:00",
              },
            ],
          }),
        } as Response;
      }
      if (url.endsWith("/concordancia")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            versoes: { prompt: "1.0.1", base: "1.1" },
            casos: 4,
            eixos: [
              { eixo: "natureza", rotulo: "Natureza", acatadas: 4, total: 4, percentual: 100 },
              { eixo: "grau_de_dano", rotulo: "Grau de dano", acatadas: 3, total: 4, percentual: 75 },
            ],
            erros_para_baixo: [
              { notificacao_id: "n2", protocolo: "NSP-2026-0002", sugerido: "moderado", decidido: "grave", grave_ou_obito: true },
            ],
          }),
        } as Response;
      }
      return { ok: true, status: 200, json: async () => corpoDaTela } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("a tela da recalibração", () => {
  it("mostra os itens do Anexo F e marca os que não têm dados nesta fase", async () => {
    render(<RecalibracaoDoAgente />);

    expect(await screen.findByText("1. Volume de notificações")).toBeTruthy();
    expect(screen.getByText("4 notificações nos últimos 30 dias.")).toBeTruthy();
    const prazos = screen.getByText("5. Prazos legais").closest("li") as HTMLElement;
    expect(prazos.textContent).toContain("Sem dados nesta fase");
    const lote = screen.getByText("13. Aprovação em lote").closest("li") as HTMLElement;
    expect(lote.textContent).toContain("Sinal de alerta aceso");
    expect(screen.getByText("Auditoria de 60 dias")).toBeTruthy();
  });

  it("só grava com uma das três decisões escolhida e mostra quem decidiu", async () => {
    render(<RecalibracaoDoAgente />);

    const botao = (await screen.findByRole("button", { name: "Registrar a decisão" })) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
    fireEvent.click(botao);
    expect(enviados).toEqual([]);

    fireEvent.click(screen.getByLabelText("Ajustar o prompt e a base"));
    fireEvent.click(botao);

    expect(await screen.findByText(/Decisão: Ajustar o prompt e a base\. Registrada por Pessoa de Teste em 02\/11\/2026/)).toBeTruthy();
    expect(enviados).toEqual([{ url: "/api/nsp/recalibracao/30", corpo: { decisao: "ajustar" } }]);
  });

  it("quem não tem Acesso pleno lê a tela sem os botões da decisão", async () => {
    corpoDaTela = tela(false);
    render(<RecalibracaoDoAgente />);

    expect(await screen.findByText("Aguardando a decisão de quem tem Acesso pleno.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Registrar a decisão" })).toBeNull();
  });
});

describe("a concordância na Configuração", () => {
  it("mostra cada eixo, as versões e os casos com o grau subido à parte", async () => {
    render(<ConcordanciaDoAgente />);

    expect(await screen.findByText("75% (3 de 4)")).toBeTruthy();
    expect(screen.getByText("Grau de dano")).toBeTruthy();
    expect(screen.getByText(/Prompt na versão 1\.0\.1 e base de conhecimento na versão 1\.1/)).toBeTruthy();
    expect(screen.getByText("NSP-2026-0002: sugerido moderado, decidido grave")).toBeTruthy();
  });
});
