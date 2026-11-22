/**
 * @vitest-environment jsdom
 */

/**
 * O Painel de Contas médicas (issue #1137, PRD #1128).
 *
 * A tela não soma nada: o servidor manda cada cartão e cada bloco pronto, e a
 * faturista recebe só a própria linha de produção. O que se trava aqui é o
 * que aparece (os 4 cartões e os 7 blocos, com os números do payload), o que
 * some para a faturista e o que cada filtro pede ao servidor.
 */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { cloneElement, type ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { comLegendas } from "@/lib/testes/legendas";

import { type Painel, PERGUNTA_A_CADA_MS, type PedidoAoSegundoAgente } from "@/lib/contas-medicas/painel";

import PainelPage from "./page";

// O jsdom não mede layout nem tem `ResizeObserver`: o `ResponsiveContainer`
// vira um de tamanho fixo e o resto do `recharts` roda de verdade (molde do
// teste do gráfico de Visitantes da Central de Comando).
vi.mock("recharts", async (importOriginal) => {
  const real = await importOriginal<typeof import("recharts")>();
  return {
    ...real,
    ResponsiveContainer: ({ children }: { children: ReactElement<{ width?: number; height?: number }> }) =>
      cloneElement(children, { width: 600, height: 240 }),
  };
});

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const ASSIM = "aaaaaaaa-0000-0000-0000-000000000001";

function semana(inicio: string, campos: Partial<Record<string, number>> = {}) {
  return { semana: inicio, REGISTRADO: 0, PRESCRITO: 0, PRESCRITO_SN: 0, POR_REGRA: 0, ...campos };
}

const PRODUCAO_DA_ANA = {
  faturista_id: "F1",
  nome: "Ana Faturista",
  contas: 2,
  com_pendencia: 1,
  valor_incluido: 200,
  valor_retirado: 30,
  taxa_nao_procede: 0.1429,
};

const PAINEL: Painel = {
  semana: { inicio: "2026-10-05", fim: "2026-10-11" },
  filtros: {
    operadoras: [
      { id: ASSIM, sigla: "ASSIM", nome: "ASSIM Saúde" },
      { id: "unimed", sigla: "UNIMED", nome: "Unimed" },
    ],
  },
  nota_media: { semana: 70, anterior: 72 },
  contas_concluidas: { total: 3 },
  valor_apontado: { total: 315, ja_incluido: 250 },
  nao_procede: { linhas: 2, de: 10, taxa: 0.2 },
  nota_por_semana: [
    { semana: "2026-09-28", nota_media: 72, contas: 2 },
    { semana: "2026-10-05", nota_media: 70, contas: 3 },
  ],
  causa_raiz: [
    { causa: "DISPENSACAO", valor: 200, percentual: 63.5 },
    { causa: "REGRA_AUTOMATICA", valor: 50, percentual: 15.9 },
    { causa: "CADASTRO_PRECO", valor: 15, percentual: 4.8 },
    { causa: "REGISTRO_ASSISTENCIAL", valor: 0, percentual: 0 },
    { causa: "LANCAMENTO_MANUAL", valor: 50, percentual: 15.9 },
  ],
  itens_que_faltam: [
    { codigo: "M100", descricao: "Luva", contas: 3, valor: 210 },
    { codigo: "M200", descricao: "Lanceta", contas: 1, valor: 40 },
  ],
  producao: [
    PRODUCAO_DA_ANA,
    {
      faturista_id: "F2",
      nome: "Bia Faturista",
      contas: 1,
      com_pendencia: 0,
      valor_incluido: 50,
      valor_retirado: 20,
      taxa_nao_procede: 0.3333,
    },
  ],
  nivel_evidencia: [
    semana("2026-09-28", { REGISTRADO: 70, PRESCRITO: 30 }),
    semana("2026-10-05", { REGISTRADO: 100, PRESCRITO: 40, PRESCRITO_SN: 60, POR_REGRA: 50 }),
  ],
  custo_ia: {
    total_usd: 1.7,
    analise_usd: 1.05,
    conversa_usd: 0.25,
    provas_usd: 0.3,
    revisor_usd: 0.1,
    medio_por_conta_usd: 0.35,
    contas: 3,
  },
  faltou_isto: [
    {
      semana: "2026-09-28",
      total: 1,
      classificacao: { REGRA: 0, LEITURA: 1, DEFEITO: 0, SEM_CLASSIFICACAO: 0 },
      origem: { PESSOA: 1, AGENTE: 0 },
    },
    {
      semana: "2026-10-05",
      total: 5,
      classificacao: { REGRA: 2, LEITURA: 1, DEFEITO: 1, SEM_CLASSIFICACAO: 1 },
      origem: { PESSOA: 3, AGENTE: 2 },
    },
  ],
};

const DA_FATURISTA: Painel = {
  semana: PAINEL.semana,
  filtros: PAINEL.filtros,
  producao: [PRODUCAO_DA_ANA],
};

const SEGUNDO_AGENTE = "/api/contas-medicas/painel/segundo-agente";

/** `segundoAgente` nulo é quem não tem o painel completo: a rota dele dá 403. */
function servidorResponde(painel: Painel, segundoAgente: PedidoAoSegundoAgente | null = null) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === SEGUNDO_AGENTE) {
      if (!segundoAgente) return { ok: false, status: 403, json: async () => ({ detail: "Sem permissão" }) };
      if (init?.method === "POST") segundoAgente.em_andamento = true;
      return { ok: true, status: init?.method === "POST" ? 202 : 200, json: async () => ({ ...segundoAgente }) };
    }
    return { ok: true, status: 200, json: async () => painel };
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

/** Os pedidos do Painel, sem os do botão do segundo agente. */
function pedidos(fetch: ReturnType<typeof vi.fn>): string[] {
  return fetch.mock.calls.map(([url]) => String(url)).filter((url) => url !== SEGUNDO_AGENTE);
}

beforeEach(() => {
  // O jsdom não implementa `scrollIntoView`, que o `Select` da casa chama ao
  // abrir a lista de opções.
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CARTOES = ["Nota média de entrada", "Contas concluídas", "R$ apontado", "Não procede"];
const BLOCOS = [
  "Nota média por semana",
  "R$ apontado por causa-raiz",
  "Os dez itens que mais faltam",
  "Produção por faturista",
  "R$ incluído por nível de evidência",
  "Custo de IA",
  "Faltou isto por semana",
];

describe("o Painel", () => {
  it("mostra os 4 cartões e os 7 blocos com os números do servidor", async () => {
    servidorResponde(PAINEL);

    render(<PainelPage />);

    await screen.findByRole("group", { name: "Nota média de entrada" });
    // Os números ficam na faixa do topo; os blocos, cada um na sua moldura.
    for (const nome of CARTOES) expect(screen.getByRole("group", { name: nome }), nome).toBeTruthy();
    for (const nome of BLOCOS) expect(screen.getByRole("region", { name: nome }), nome).toBeTruthy();
    const nota = screen.getByRole("group", { name: "Nota média de entrada" });
    expect(nota.textContent).toContain("70");
    expect(nota.textContent).toContain("Semana anterior: 72");
    expect(screen.getByRole("group", { name: "Contas concluídas" }).textContent).toContain("3");
    const apontado = screen.getByRole("group", { name: "R$ apontado" });
    expect(apontado.textContent).toContain("R$ 315,00");
    expect(apontado.textContent).toContain("Já incluídos: R$ 250,00");
    const naoProcede = screen.getByRole("group", { name: "Não procede" });
    expect(naoProcede.textContent).toContain("20%");
    expect(naoProcede.textContent).toContain("2 de 10 linhas");

    const causa = screen.getByRole("region", { name: "R$ apontado por causa-raiz" });
    expect(within(causa).getByText("Dispensação").closest("li")?.textContent).toContain("63,5%");
    expect(within(causa).getByText("Dispensação").closest("li")?.textContent).toContain("R$ 200,00");

    const itens = within(screen.getByRole("region", { name: "Os dez itens que mais faltam" })).getAllByRole("row");
    expect(itens[1].textContent).toContain("M100");
    expect(itens[1].textContent).toContain("Luva");
    expect(itens[1].textContent).toContain("3");
    expect(itens[1].textContent).toContain("R$ 210,00");

    const producao = within(screen.getByRole("region", { name: "Produção por faturista" })).getAllByRole("row");
    expect(producao[1].textContent).toContain("Ana Faturista");
    expect(producao[1].textContent).toContain("R$ 200,00");
    expect(producao[1].textContent).toContain("14,3%");
    expect(producao[1].textContent).toContain("R$ 30,00");

    const custo = screen.getByRole("region", { name: "Custo de IA" });
    expect(custo.textContent).toContain("US$ 1,70");
    expect(custo.textContent).toContain("US$ 0,35 por conta");
    const parte = (nome: string) => within(custo).getByText(nome).closest("li")?.textContent;
    expect(parte("Análise das contas")).toContain("US$ 1,05");
    expect(parte("Conversas com o Auditor")).toContain("US$ 0,25");
    expect(parte("Provas de regra")).toContain("US$ 0,30");
    expect(parte("Revisor")).toContain("US$ 0,10");

    const faltou = within(screen.getByRole("region", { name: "Faltou isto por semana" })).getAllByRole("row");
    const cabecalho = Array.from(faltou[0].querySelectorAll("th")).map((th) => th.textContent);
    expect(cabecalho).toEqual(["Semana", "Total", "Regra", "Leitura", "Defeito", "Sem classificação", "Pessoa", "Agente"]);
    // A semana escolhida no alto, a anterior embaixo.
    const celulas = (linha: HTMLElement) => Array.from(linha.querySelectorAll("td")).map((td) => td.textContent);
    expect(celulas(faltou[1])).toEqual(["05/10", "5", "2", "1", "1", "1", "3", "2"]);
    expect(celulas(faltou[2])).toEqual(["28/09", "1", "0", "1", "0", "0", "1", "0"]);

    expect(screen.getByText(/05\/10 a 11\/10\/2026/)).toBeTruthy();
  });

  it("a faturista vê só a própria linha de produção", async () => {
    servidorResponde(DA_FATURISTA);

    render(<PainelPage />);

    const producao = await screen.findByRole("region", { name: "Produção por faturista" });
    expect(within(producao).getAllByRole("row")).toHaveLength(2);
    expect(screen.queryByRole("region", { name: "Números da semana" })).toBeNull();
    for (const nome of CARTOES) expect(screen.queryByRole("group", { name: nome }), nome).toBeNull();
    for (const nome of BLOCOS.filter((b) => b !== "Produção por faturista")) {
      expect(screen.queryByRole("region", { name: nome }), nome).toBeNull();
    }
  });

  it("sem o custo de IA no payload (quem não é Super admin), o bloco some e os outros ficam", async () => {
    const semCusto: Painel = { ...PAINEL };
    delete semCusto.custo_ia;
    servidorResponde(semCusto);

    render(<PainelPage />);

    await screen.findByRole("group", { name: "Nota média de entrada" });
    expect(screen.queryByRole("region", { name: "Custo de IA" })).toBeNull();
    for (const nome of BLOCOS.filter((b) => b !== "Custo de IA")) {
      expect(screen.getByRole("region", { name: nome }), nome).toBeTruthy();
    }
  });

  it("cada filtro pede o Painel de novo ao servidor", async () => {
    const fetch = servidorResponde(PAINEL);

    render(<PainelPage />);
    await screen.findByRole("group", { name: "Nota média de entrada" });
    expect(pedidos(fetch)[0]).toMatch(/^\/api\/contas-medicas\/painel\?semana=\d{4}-\d{2}-\d{2}$/);

    fireEvent.change(screen.getByLabelText("Semana"), { target: { value: "2026-09-28" } });
    await waitFor(() => expect(pedidos(fetch).at(-1)).toBe("/api/contas-medicas/painel?semana=2026-09-28"));

    fireEvent.click(screen.getByRole("combobox", { name: "Operadora" }));
    fireEvent.click(screen.getByRole("option", { name: "ASSIM" }));
    await waitFor(() =>
      expect(pedidos(fetch).at(-1)).toBe(`/api/contas-medicas/painel?semana=2026-09-28&operadora_id=${ASSIM}`),
    );

    fireEvent.click(screen.getByRole("combobox", { name: "Tipo de conta" }));
    fireEvent.click(screen.getByRole("option", { name: "Parcial" }));
    await waitFor(() =>
      expect(pedidos(fetch).at(-1)).toBe(
        `/api/contas-medicas/painel?semana=2026-09-28&operadora_id=${ASSIM}&tipo=parcial`,
      ),
    );
  });
});

describe("o botão do segundo agente (ADR 0082, issue #1523)", () => {
  const DEZ = (): PedidoAoSegundoAgente => ({ contas: 10, custo_estimado_usd: 6, em_andamento: false });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("mostra quantas contas e o custo antes do clique, sem chamar o agente", async () => {
    const fetch = servidorResponde(PAINEL, DEZ());

    render(<PainelPage />);

    const agente = await screen.findByRole("region", { name: "Segundo agente" });
    expect(agente.textContent).toContain("relê 10 contas concluídas que ele ainda não revisou");
    expect(agente.textContent).toContain("cerca de US$ 6,00");
    expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  });

  it("o clique pergunta com o custo, chama o agente e mostra que ele está relendo", async () => {
    const fetch = servidorResponde(PAINEL, DEZ());
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<PainelPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Reler contas concluídas" }));

    expect(confirmar).toHaveBeenCalledWith(
      "Pedir ao segundo agente a releitura de 10 contas? Custo estimado: cerca de US$ 6,00.",
    );
    await screen.findByText("O segundo agente está relendo as contas.", { exact: false });
    expect(fetch.mock.calls.filter(([url, init]) => url === SEGUNDO_AGENTE && init?.method === "POST")).toHaveLength(1);
  });

  it("sem confirmar, não chama o agente", async () => {
    const fetch = servidorResponde(PAINEL, DEZ());
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<PainelPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Reler contas concluídas" }));

    expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  });

  it("sem o painel completo, o botão não aparece", async () => {
    servidorResponde(DA_FATURISTA, null);

    render(<PainelPage />);

    await screen.findByRole("region", { name: "Produção por faturista" });
    expect(screen.queryByRole("region", { name: "Segundo agente" })).toBeNull();
  });

  it("quando o agente termina, o Painel é pedido de novo e o aviso some", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const agente = { ...DEZ(), em_andamento: true };
    const fetch = servidorResponde(PAINEL, agente);
    render(<PainelPage />);
    await screen.findByText("O segundo agente está relendo as contas.", { exact: false });
    await screen.findByRole("group", { name: "Nota média de entrada" });
    const antes = pedidos(fetch).length;

    Object.assign(agente, { contas: 0, em_andamento: false });
    await vi.advanceTimersByTimeAsync(PERGUNTA_A_CADA_MS);

    await waitFor(() => expect(pedidos(fetch).length).toBe(antes + 1));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Segundo agente" })).toBeNull());
  });
});

describe("a faixa dos números (issue #1953)", () => {
  const COORDENACAO = { valor_incluido: 1250.5, lembretes_incluidos: 4 };

  it("junta os números numa faixa só, e cada um diz o que mede ao passar o mouse", async () => {
    servidorResponde({ ...PAINEL, coordenacao: COORDENACAO });
    render(<PainelPage />);

    const faixa = await screen.findByRole("region", { name: "Números da semana" });
    const dicas: [string, string][] = [
      [
        "Nota média de entrada",
        "De 0 a 100, quanto as contas concluídas na semana estavam certas antes da correção. Sobe quando a ponta registra e dispensa melhor.",
      ],
      ["Contas concluídas", "Quantas contas as faturistas concluíram na semana, de segunda a domingo."],
      [
        "R$ apontado",
        "O valor dos itens que o módulo apontou nas contas da semana. Já incluídos é o que já entrou no MV, as linhas Feito.",
      ],
      [
        "Não procede",
        "Quantas linhas apontadas a faturista marcou como Não procede, sem as de validação. Mede o acerto da IA e da memória.",
      ],
      [
        "R$ incluído pela coordenação",
        "O R$ que a coordenação incluiu na semana pelos lembretes da Conferência. Não entra na nota de entrada nem na produção.",
      ],
    ];
    expect(within(faixa).getAllByRole("group")).toHaveLength(5);
    for (const [nome, dica] of dicas) {
      const numero = within(faixa).getByRole("group", { name: nome });
      const rotulo = within(numero).getByText(nome);
      expect(screen.queryByRole("tooltip"), nome).toBeNull();

      fireEvent.mouseEnter(rotulo);
      expect(screen.getByRole("tooltip").textContent, nome).toBe(dica);
      fireEvent.mouseLeave(rotulo);
    }
  });

  it("a dica do número da borda direita abre para dentro da faixa", async () => {
    // O jsdom não mede layout. A dica tem 256 px e abre presa ao nome do
    // número; na coluna da direita (duas colunas, celular) e no último número
    // (uma linha só, computador) ela passaria da borda e a página rolaria de
    // lado. Aqui se trava a regra: a dica se prende ao título inteiro da
    // célula, e nessas células abre a partir da borda direita.
    servidorResponde({ ...PAINEL, coordenacao: COORDENACAO });
    render(<PainelPage />);

    const faixa = await screen.findByRole("region", { name: "Números da semana" });
    const numero = within(faixa).getByRole("group", { name: "Não procede" });
    fireEvent.mouseEnter(within(numero).getByText("Não procede"));
    const dica = screen.getByRole("tooltip");

    const titulo = numero.querySelector("h3")!;
    expect(titulo.classList.contains("relative")).toBe(true);
    expect(dica.parentElement?.parentElement).toBe(titulo);
    expect(titulo.className).toContain("[&>span]:static");
    expect(numero.className).toContain("max-lg:even:[&_[role=tooltip]]:right-0");
    expect(numero.className).toContain("max-lg:even:[&_[role=tooltip]]:left-auto");
    expect(numero.className).toContain("lg:last:[&_[role=tooltip]]:right-0");
    expect(numero.className).toContain("lg:last:[&_[role=tooltip]]:left-auto");
  });

  it("a dica do número também abre pelo teclado", async () => {
    servidorResponde(PAINEL);
    render(<PainelPage />);

    const faixa = await screen.findByRole("region", { name: "Números da semana" });
    const rotulo = within(within(faixa).getByRole("group", { name: "Contas concluídas" })).getByText(
      "Contas concluídas",
    );
    act(() => rotulo.focus());

    expect(document.activeElement).toBe(rotulo);
    expect(screen.getByRole("tooltip").textContent).toBe(
      "Quantas contas as faturistas concluíram na semana, de segunda a domingo.",
    );
  });
});

describe("o hover nos blocos (issue #1953)", () => {
  it("o ponto do gráfico da nota mostra a semana e a nota", async () => {
    servidorResponde(PAINEL);
    render(<PainelPage />);

    const bloco = await screen.findByRole("region", { name: "Nota média por semana" });
    // 600 px de largura (o `ResponsiveContainer` do mock): o eixo da nota ocupa
    // os primeiros 36 e a margem os últimos 12, então a semana de 05/10 fica em 588.
    fireEvent.mouseMove(bloco.querySelector(".recharts-wrapper")!, { clientX: 580, clientY: 100 });

    const dica = bloco.querySelector(".recharts-tooltip-wrapper")!;
    expect(dica.textContent).toContain("Semana de 05/10");
    expect(dica.textContent).toContain("Nota média : 70");
  });

  it("a barra do nível de evidência mostra o R$ de cada nível da semana", async () => {
    servidorResponde(PAINEL);
    render(<PainelPage />);

    const bloco = await screen.findByRole("region", { name: "R$ incluído por nível de evidência" });
    fireEvent.mouseMove(bloco.querySelector(".recharts-wrapper")!, { clientX: 500, clientY: 100 });

    const dica = bloco.querySelector(".recharts-tooltip-wrapper")!;
    expect(dica.textContent).toContain("Semana de 05/10");
    expect(dica.textContent).toContain("Prescrito SN : R$ 60,00");
  });

  it("a barra da causa-raiz mostra o R$ e o percentual dela", async () => {
    servidorResponde(PAINEL);
    render(<PainelPage />);

    const bloco = await screen.findByRole("region", { name: "R$ apontado por causa-raiz" });
    expect(screen.queryByRole("tooltip")).toBeNull();

    fireEvent.mouseEnter(within(bloco).getByRole("img", { name: "Regra automática" }));

    expect(screen.getByRole("tooltip").textContent).toBe("Regra automática: R$ 50,00, 15,9% do R$ apontado");
  });
});

describe("as tabelas e a largura estreita (issue #1953)", () => {
  // O jsdom não mede layout: o que se trava aqui são as classes que seguram a
  // largura. Bloco sem `min-w-0` cresce até a largura da tabela e a página
  // inteira rola de lado; tabela fora de um `overflow-x-auto` faz o mesmo.
  it("cada tabela rola dentro do próprio bloco, e nenhum bloco empurra a página", async () => {
    servidorResponde(PAINEL);
    render(<PainelPage />);
    await screen.findByRole("region", { name: "Os dez itens que mais faltam" });

    const tabelas = screen.getAllByRole("table");
    expect(tabelas).toHaveLength(3);
    for (const tabela of tabelas) {
      const bloco = tabela.closest("section")!.getAttribute("aria-labelledby");
      expect(tabela.parentElement?.classList.contains("overflow-x-auto"), bloco ?? "").toBe(true);
    }
    for (const nome of BLOCOS) {
      expect(screen.getByRole("region", { name: nome }).classList.contains("min-w-0"), nome).toBe(true);
    }
  });

  it("a linha da tabela se destaca ao passar o mouse", async () => {
    servidorResponde(PAINEL);
    render(<PainelPage />);
    await screen.findByRole("region", { name: "Os dez itens que mais faltam" });

    for (const tabela of screen.getAllByRole("table")) {
      for (const linha of Array.from(tabela.querySelectorAll("tbody tr"))) {
        expect(linha.classList.contains("hover:bg-slate-50"), linha.textContent ?? "").toBe(true);
      }
    }
  });
});

describe("a Legenda dos filtros (issue #1953)", () => {
  const LEGENDA = "Os números são das contas concluídas na semana escolhida, de segunda a domingo.";

  it("diz que os números são das contas concluídas na semana, e some com as Legendas desligadas", async () => {
    servidorResponde(PAINEL);
    render(comLegendas(false, <PainelPage />));

    await screen.findByRole("group", { name: "Nota média de entrada" });
    expect(screen.queryByText(LEGENDA)).toBeNull();
    cleanup();

    render(comLegendas(true, <PainelPage />));

    expect(await screen.findByText(LEGENDA)).toBeTruthy();
  });
});

describe("o subtítulo da tela (issue #1950)", () => {
  it("é uma Legenda: some com as Legendas desligadas e volta com elas ligadas", async () => {
    servidorResponde(PAINEL);
    render(comLegendas(false, <PainelPage />));

    await screen.findByRole("heading", { level: 1, name: "Painel" });
    expect(screen.queryByText(/^A nota da semana e onde a perda da conta nasce/)).toBeNull();
    cleanup();

    render(comLegendas(true, <PainelPage />));

    expect(await screen.findByText(/^A nota da semana e onde a perda da conta nasce/)).toBeTruthy();
  });
});
