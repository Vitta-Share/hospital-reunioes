/**
 * @vitest-environment jsdom
 */

/**
 * O arquivar da tela de contas de Contas médicas (issue #1958, PRD #1933, ADR
 * 0105). Quem decide quem arquiva e o que entra no mês é o servidor; aqui se
 * trava o que a tela faz: Concluídas agrupada por Competência, "Arquivar" na
 * conta, "Arquivar o mês" com a confirmação na própria lista, a etapa
 * Arquivadas que só carrega quando abre, o "Desarquivar" e a busca. Os nomes
 * dos dados são inventados.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DICA_DO_ARQUIVAR,
  DICA_DO_DESARQUIVAR,
  agruparPorCompetencia,
  nomeDaCompetencia,
  resultadoDoMes,
} from "@/lib/contas-medicas/arquivo";
import type { ItemDaBusca } from "@/lib/contas-medicas/busca";
import type { ItemDaFila } from "@/lib/contas-medicas/envio";
import { LEGENDA_DA_ETAPA } from "@/lib/contas-medicas/textos";

import ContasMedicasPage from "./page";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

function conta(campos: Partial<ItemDaFila>): ItemDaFila {
  return {
    id: "c-1",
    numero_atendimento: "31200",
    numero_conta: "48001",
    situacao: "CONCLUIDA",
    falta: null,
    periodo_inicio: "2026-10-01",
    periodo_fim: "2026-10-20",
    nota_entrada: 80,
    valor_apontado: null,
    itens_feitos: 0,
    itens_total: 0,
    pendencias: 0,
    erro_motivo: null,
    ...campos,
  };
}

const NOV_MINHA = conta({ id: "nov-minha", numero_atendimento: "41001", competencia: "2026-11", minha: true });
const OUT_MINHA = conta({ id: "out-minha", numero_atendimento: "41002", competencia: "2026-10", minha: true });
const OUT_DA_COLEGA = conta({
  id: "out-colega",
  numero_atendimento: "41003",
  competencia: "2026-10",
  situacao: "CONCLUIDA_COM_PENDENCIA",
  pendencias: 1,
  com: "Faturista Inventada Dois",
});
const OUT_MINHA_PENDENCIA = conta({
  id: "out-minha-pendencia",
  numero_atendimento: "41004",
  competencia: "2026-10",
  situacao: "CONCLUIDA_COM_PENDENCIA",
  pendencias: 2,
  minha: true,
});
const ARQUIVADA_MINHA = conta({
  id: "arq-minha",
  numero_atendimento: "42001",
  competencia: "2026-09",
  arquivada_em: "2026-10-05T12:00:00+00:00",
  minha: true,
});
const ARQUIVADA_DA_COLEGA = conta({
  id: "arq-colega",
  numero_atendimento: "42002",
  competencia: "2026-09",
  arquivada_em: "2026-10-05T12:00:00+00:00",
  com: "Faturista Inventada Dois",
});

let todas: boolean;
let concluidas: ItemDaFila[];
let respostaDoMes: () => Response;
let respostaDoArquivar: () => Response;
let respostaDaBusca: { contas: ItemDaBusca[]; mais: boolean };
const chamadas: { url: string; metodo: string }[] = [];

beforeEach(() => {
  todas = false;
  concluidas = [NOV_MINHA, OUT_DA_COLEGA, OUT_MINHA, OUT_MINHA_PENDENCIA];
  respostaDoMes = () => new Response(JSON.stringify({ arquivadas: 2, com_pendencia: 1 }));
  respostaDoArquivar = () => new Response(JSON.stringify({ arquivada: "x" }));
  respostaDaBusca = { contas: [], mais: false };
  chamadas.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, metodo: init?.method ?? "GET" });
      if (url === "/api/contas-medicas/fila")
        return new Response(
          JSON.stringify({
            todas,
            fila: [],
            minhas: [],
            concluidas,
            contagem: { fila: 0, em_analise: 0, concluidas: concluidas.length, arquivadas: 2 },
            contagem_minhas: { em_analise: 0, concluidas: 3 },
          }),
        );
      if (url === "/api/contas-medicas/meus-envios")
        return new Response(JSON.stringify({ todas, meus_envios: [], barra: null, contagem: { envios: 0 } }));
      if (url === "/api/contas-medicas/me")
        return new Response(JSON.stringify({ perfil: "faturista", permissoes: ["enviar_corrigir_contas"] }));
      if (url === "/api/contas-medicas/arquivadas")
        return new Response(JSON.stringify({ todas, arquivadas: [ARQUIVADA_MINHA, ARQUIVADA_DA_COLEGA] }));
      if (url.startsWith("/api/contas-medicas/competencias/")) return respostaDoMes();
      if (url.endsWith("/arquivar") || url.endsWith("/desarquivar")) return respostaDoArquivar();
      if (url.startsWith("/api/contas-medicas/busca?")) return new Response(JSON.stringify(respostaDaBusca));
      return new Response("{}", { status: 404 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function etapa(nome: RegExp) {
  fireEvent.click(within(screen.getByRole("region", { name: "Esteira" })).getByRole("tab", { name: nome }));
}

async function abrirConcluidas(): Promise<HTMLElement> {
  render(<ContasMedicasPage />);
  await screen.findByRole("tab", { name: /^Concluídas/ });
  await waitFor(() => expect(chamadas.some((c) => c.url === "/api/contas-medicas/fila")).toBe(true));
  etapa(/^Concluídas/);
  const lista = screen.getByRole("region", { name: "Lista de contas" });
  await within(lista).findByRole("region", { name: "Outubro de 2026" });
  return lista;
}

function numeros(grupo: HTMLElement): string[] {
  return within(grupo)
    .getAllByRole("listitem")
    .map((li) => within(li).getByText(/^\d+$/).textContent ?? "");
}

function linhaDe(lista: HTMLElement, numero: string): HTMLElement {
  return within(lista).getByText(numero).closest("li") as HTMLElement;
}

const postados = () => chamadas.filter((c) => c.metodo === "POST").map((c) => c.url);

describe("a Competência na tela (issue #1958)", () => {
  it("o mês sai por extenso, e as contas se agrupam do mês mais recente ao mais antigo, sem mês no fim", () => {
    expect(nomeDaCompetencia("2026-10")).toBe("outubro de 2026");
    expect(nomeDaCompetencia(null)).toBe("sem mês");
    const grupos = agruparPorCompetencia([
      conta({ id: "a", competencia: "2026-09" }),
      conta({ id: "b", competencia: null }),
      conta({ id: "c", competencia: "2026-11" }),
      conta({ id: "d", competencia: "2026-09" }),
      conta({ id: "e", competencia: "2025-12" }),
    ]);
    expect(grupos.map((g) => [g.competencia, g.contas.map((c) => c.id)])).toEqual([
      ["2026-11", ["c"]],
      ["2026-09", ["a", "d"]],
      ["2025-12", ["e"]],
      [null, ["b"]],
    ]);
  });

  it("o aviso do lote diz quantas arquivou e quantas tinham pendência", () => {
    expect(resultadoDoMes({ arquivadas: 3, com_pendencia: 1 })).toBe("3 contas arquivadas, 1 com pendência.");
    expect(resultadoDoMes({ arquivadas: 1, com_pendencia: 0 })).toBe("1 conta arquivada.");
    expect(resultadoDoMes({ arquivadas: 0, com_pendencia: 0 })).toBe("Nenhuma conta arquivada.");
  });
});

describe("Concluídas por Competência (issue #1958)", () => {
  it("vem agrupada por mês, o mais recente primeiro, com o número de contas de cada mês", async () => {
    const lista = await abrirConcluidas();

    const grupos = within(lista).getAllByRole("region");
    expect(grupos.map((g) => within(g).getByRole("heading", { level: 3 }).textContent)).toEqual([
      "Novembro de 2026 1 conta",
      "Outubro de 2026 3 contas",
    ]);
    expect(numeros(grupos[1])).toEqual(["41003", "41002", "41004"]);
  });

  it("a etapa Concluídas tem Legenda", async () => {
    await abrirConcluidas();

    expect(within(screen.getByRole("region", { name: "Esteira" })).getByText(LEGENDA_DA_ETAPA.concluidas)).toBeTruthy();
  });

  it("a faturista vê Arquivar nas contas dela e não na da colega; o botão tem dica", async () => {
    const lista = await abrirConcluidas();

    expect(within(linhaDe(lista, "41002")).getByRole("button", { name: "Arquivar" })).toBeTruthy();
    expect(within(linhaDe(lista, "41003")).queryByRole("button", { name: "Arquivar" })).toBeNull();
    fireEvent.focus(within(linhaDe(lista, "41002")).getByRole("button", { name: "Arquivar" }));
    expect(screen.getByRole("tooltip").textContent).toBe(DICA_DO_ARQUIVAR);
    expect(DICA_DO_ARQUIVAR).toContain("já foi tratada no MV");
  });

  it("quem tem o painel completo vê Arquivar em qualquer conta", async () => {
    todas = true;
    const lista = await abrirConcluidas();

    expect(within(linhaDe(lista, "41003")).getByRole("button", { name: "Arquivar" })).toBeTruthy();
  });

  it("arquivar a conta manda ao servidor, mostra o aviso e relê a lista", async () => {
    const lista = await abrirConcluidas();
    const leiturasAntes = chamadas.filter((c) => c.url === "/api/contas-medicas/fila").length;

    fireEvent.click(within(linhaDe(lista, "41002")).getByRole("button", { name: "Arquivar" }));

    expect((await screen.findByRole("status")).textContent).toBe("41002 arquivada.");
    expect(postados()).toEqual(["/api/contas-medicas/contas/out-minha/arquivar"]);
    expect(chamadas.filter((c) => c.url === "/api/contas-medicas/fila").length).toBe(leiturasAntes + 1);
  });

  it("a recusa do servidor aparece com a frase dele", async () => {
    respostaDoArquivar = () =>
      new Response(JSON.stringify({ detail: "Esta conta já está arquivada." }), { status: 409 });
    const lista = await abrirConcluidas();

    fireEvent.click(within(linhaDe(lista, "41002")).getByRole("button", { name: "Arquivar" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Esta conta já está arquivada.");
  });
});

describe("Arquivar o mês (issue #1958)", () => {
  function cabecalho(lista: HTMLElement, mes: string): HTMLElement {
    return within(lista).getByRole("region", { name: mes });
  }

  it("fica no cabeçalho do grupo, com dica", async () => {
    const lista = await abrirConcluidas();
    const botao = within(cabecalho(lista, "Outubro de 2026")).getByRole("button", { name: "Arquivar o mês" });

    fireEvent.focus(botao);

    expect(screen.getByRole("tooltip").textContent).toContain("Arquiva as suas contas concluídas deste mês");
  });

  it("a confirmação aparece na própria lista, sem window.confirm, com quantas, quantas têm pendência e o MV", async () => {
    const confirmar = vi.spyOn(window, "confirm");
    const lista = await abrirConcluidas();
    const outubro = cabecalho(lista, "Outubro de 2026");

    fireEvent.click(within(outubro).getByRole("button", { name: "Arquivar o mês" }));

    const pergunta = within(outubro).getByRole("group", { name: "Confirmar o arquivar do mês" });
    // A faturista arquiva só as dela: duas de outubro, uma com pendência.
    expect(pergunta.textContent).toContain(
      "Arquivar 2 contas de outubro de 2026? 1 tem pendência. Arquivar quer dizer que a conta já foi tratada no MV.",
    );
    expect(confirmar).not.toHaveBeenCalled();
    expect(postados()).toEqual([]);
  });

  it("para quem tem o painel completo, a confirmação conta as contas de todas", async () => {
    todas = true;
    const lista = await abrirConcluidas();
    const outubro = cabecalho(lista, "Outubro de 2026");

    fireEvent.click(within(outubro).getByRole("button", { name: "Arquivar o mês" }));

    expect(within(outubro).getByRole("group").textContent).toContain("Arquivar 3 contas de outubro de 2026? 2 têm pendência.");
  });

  it("confirmado, manda o mês ao servidor e mostra o resultado num aviso", async () => {
    const lista = await abrirConcluidas();
    const outubro = cabecalho(lista, "Outubro de 2026");
    fireEvent.click(within(outubro).getByRole("button", { name: "Arquivar o mês" }));

    fireEvent.click(within(outubro).getByRole("button", { name: "Arquivar 2 contas" }));

    expect((await screen.findByRole("status")).textContent).toBe("2 contas arquivadas, 1 com pendência.");
    expect(postados()).toEqual(["/api/contas-medicas/competencias/2026-10/arquivar"]);
  });

  it("Cancelar fecha a confirmação sem arquivar nada", async () => {
    const lista = await abrirConcluidas();
    const outubro = cabecalho(lista, "Outubro de 2026");
    fireEvent.click(within(outubro).getByRole("button", { name: "Arquivar o mês" }));

    fireEvent.click(within(outubro).getByRole("button", { name: "Cancelar" }));

    expect(within(outubro).queryByRole("group")).toBeNull();
    expect(postados()).toEqual([]);
  });

  it("o mês sem conta da faturista não tem Arquivar o mês", async () => {
    concluidas = [NOV_MINHA, OUT_DA_COLEGA];
    const lista = await abrirConcluidas();

    expect(within(cabecalho(lista, "Outubro de 2026")).queryByRole("button", { name: "Arquivar o mês" })).toBeNull();
    expect(within(cabecalho(lista, "Novembro de 2026")).getByRole("button", { name: "Arquivar o mês" })).toBeTruthy();
  });
});

describe("a etapa Arquivadas (issue #1958)", () => {
  async function abrirArquivadas(): Promise<HTMLElement> {
    render(<ContasMedicasPage />);
    const aba = await screen.findByRole("tab", { name: /^Arquivadas/ });
    await waitFor(() => expect(aba.textContent).toBe("Arquivadas 2"));
    etapa(/^Arquivadas/);
    const lista = screen.getByRole("region", { name: "Lista de contas" });
    await within(lista).findByRole("region", { name: "Setembro de 2026" });
    return lista;
  }

  it("tem o número na Esteira e a lista só vem do servidor quando a etapa é aberta", async () => {
    render(<ContasMedicasPage />);
    const aba = await screen.findByRole("tab", { name: /^Arquivadas/ });
    await waitFor(() => expect(aba.textContent).toBe("Arquivadas 2"));

    expect(chamadas.some((c) => c.url === "/api/contas-medicas/arquivadas")).toBe(false);
    etapa(/^Arquivadas/);
    await waitFor(() => expect(chamadas.some((c) => c.url === "/api/contas-medicas/arquivadas")).toBe(true));
  });

  it("vem por Competência, com Legenda e com Desarquivar só nas que a pessoa pode, com dica", async () => {
    const lista = await abrirArquivadas();

    expect(numeros(within(lista).getByRole("region", { name: "Setembro de 2026" }))).toEqual(["42001", "42002"]);
    expect(within(screen.getByRole("region", { name: "Esteira" })).getByText(LEGENDA_DA_ETAPA.arquivadas)).toBeTruthy();
    const desarquivar = within(linhaDe(lista, "42001")).getByRole("button", { name: "Desarquivar" });
    expect(within(linhaDe(lista, "42002")).queryByRole("button", { name: "Desarquivar" })).toBeNull();
    expect(within(lista).queryByRole("button", { name: "Arquivar o mês" })).toBeNull();
    fireEvent.focus(desarquivar);
    expect(screen.getByRole("tooltip").textContent).toBe(DICA_DO_DESARQUIVAR);
  });

  it("quem tem o painel completo desarquiva qualquer uma", async () => {
    todas = true;
    const lista = await abrirArquivadas();

    expect(within(linhaDe(lista, "42002")).getByRole("button", { name: "Desarquivar" })).toBeTruthy();
  });

  it("desarquivar manda ao servidor, avisa e relê as arquivadas", async () => {
    const lista = await abrirArquivadas();
    const leiturasAntes = chamadas.filter((c) => c.url === "/api/contas-medicas/arquivadas").length;

    fireEvent.click(within(linhaDe(lista, "42001")).getByRole("button", { name: "Desarquivar" }));

    expect((await screen.findByRole("status")).textContent).toBe("42001 voltou para Concluídas.");
    expect(postados()).toEqual(["/api/contas-medicas/contas/arq-minha/desarquivar"]);
    await waitFor(() =>
      expect(chamadas.filter((c) => c.url === "/api/contas-medicas/arquivadas").length).toBe(leiturasAntes + 1),
    );
  });

  it("a conta arquivada continua com Abrir para quem já abria a concluída", async () => {
    const lista = await abrirArquivadas();

    expect(within(linhaDe(lista, "42001")).getByRole("link", { name: "Abrir" }).getAttribute("href")).toBe(
      "/contas-medicas/guia/arq-minha",
    );
  });
});

describe("a busca acha a arquivada (issue #1958)", () => {
  it("em destaque, diz que está em Arquivadas e a Competência dela", async () => {
    respostaDaBusca = {
      contas: [{ ...ARQUIVADA_MINHA, etapa_da_esteira: "arquivadas", pode_abrir: true }],
      mais: false,
    };
    render(<ContasMedicasPage />);
    const campo = await screen.findByRole("searchbox", { name: "Buscar conta" });

    fireEvent.change(campo, { target: { value: "42001" } });

    const destaque = await screen.findByRole("article", { name: "Conta encontrada" });
    expect(destaque.textContent).toContain("Onde estáArquivadas, concluída");
    expect(destaque.textContent).toContain("CompetênciaSetembro de 2026");
  });

  it("na lista de resultados, a linha diz Arquivada e o mês", async () => {
    respostaDaBusca = {
      contas: [
        { ...ARQUIVADA_MINHA, etapa_da_esteira: "arquivadas", pode_abrir: true },
        { ...NOV_MINHA, etapa_da_esteira: "concluidas", pode_abrir: true },
      ],
      mais: false,
    };
    render(<ContasMedicasPage />);
    fireEvent.change(await screen.findByRole("searchbox", { name: "Buscar conta" }), { target: { value: "4" } });
    fireEvent.change(screen.getByRole("searchbox", { name: "Buscar conta" }), { target: { value: "42" } });

    const resultados = await screen.findByRole("region", { name: "Resultados da busca" });
    await waitFor(() => expect(within(resultados).getAllByRole("listitem")).toHaveLength(2));
    expect(within(resultados).getAllByRole("listitem")[0].textContent).toContain("Arquivada, setembro de 2026");
    expect(within(resultados).getAllByRole("listitem")[1].textContent).not.toContain("Arquivada");
  });
});
