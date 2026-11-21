/**
 * @vitest-environment jsdom
 */

/**
 * A busca da tela de contas de Contas médicas (issue #1956, PRD #1933, ADR
 * 0105). Quem procura é o servidor; aqui se trava o que a tela faz com o
 * texto (quando busca, o que some e o que volta) e o que mostra de cada
 * resposta: a conta em destaque, a lista com o trecho marcado, nenhuma e a
 * conta que está com outra pessoa. Os nomes dos dados são inventados.
 */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DICA_DA_BUSCA, DIGITE_MAIS, type ItemDaBusca, REFINE_A_BUSCA, SEM_RESULTADO } from "@/lib/contas-medicas/busca";
import type { ItemDaFila } from "@/lib/contas-medicas/envio";

import ContasMedicasPage from "./page";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

function conta(campos: Partial<ItemDaBusca>): ItemDaBusca {
  return {
    id: "c-1",
    numero_atendimento: "27751",
    paciente_rotulo: null,
    numero_conta: "48001",
    situacao: "A_FAZER",
    falta: null,
    periodo_inicio: "2026-10-01",
    periodo_fim: "2026-10-05",
    operadora: "ASSIM",
    nota_entrada: null,
    valor_apontado: null,
    itens_feitos: 0,
    itens_total: 0,
    pendencias: 0,
    erro_motivo: null,
    etapa_da_esteira: "fila",
    pode_abrir: true,
    ...campos,
  };
}

const LIVRE = conta({ id: "livre", numero_atendimento: "27751", paciente_rotulo: "Fulana T." });
const DA_OUTRA = conta({
  id: "da-outra",
  numero_atendimento: "27752",
  paciente_rotulo: "Antônia Q.",
  situacao: "EM_CORRECAO",
  etapa_da_esteira: "em_analise",
  com: "Sicrana Z.",
  pode_abrir: false,
});
const MINHA = conta({
  id: "minha",
  numero_atendimento: "31999",
  paciente_rotulo: "Beltrana R.",
  situacao: "EM_CORRECAO",
  etapa_da_esteira: "em_analise",
  com: "Pessoa F1",
  minha: true,
});

const NA_FILA: ItemDaFila = { ...conta({ id: "na-fila-da-tela", numero_atendimento: "40100" }) };

let permissoes: string[];
let respostaDaBusca: (q: string) => { contas: ItemDaBusca[]; mais: boolean };
const buscas: string[] = [];

beforeEach(() => {
  permissoes = ["enviar_contas", "enviar_corrigir_contas"];
  respostaDaBusca = () => ({ contas: [LIVRE, DA_OUTRA], mais: false });
  buscas.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.startsWith("/api/contas-medicas/busca?")) {
        const q = new URL(url, "http://x").searchParams.get("q") ?? "";
        buscas.push(q);
        return new Response(JSON.stringify(respostaDaBusca(q)));
      }
      if (url === "/api/contas-medicas/fila")
        return new Response(
          JSON.stringify({
            todas: false,
            fila: [NA_FILA],
            minhas: [],
            concluidas: [],
            contagem: { fila: 1, em_analise: 0, concluidas: 0 },
          }),
        );
      if (url === "/api/contas-medicas/meus-envios")
        return new Response(JSON.stringify({ todas: false, meus_envios: [], barra: null, contagem: { envios: 0 } }));
      if (url === "/api/contas-medicas/me") return new Response(JSON.stringify({ perfil: "faturista", permissoes }));
      return new Response("{}", { status: 404 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function campo(): Promise<HTMLInputElement> {
  render(<ContasMedicasPage />);
  const entrada = (await screen.findByRole("searchbox", { name: "Buscar conta" })) as HTMLInputElement;
  await screen.findByRole("region", { name: "Esteira" });
  return entrada;
}

async function buscar(texto: string): Promise<HTMLElement> {
  fireEvent.change(await campo(), { target: { value: texto } });
  const resultados = screen.getByRole("region", { name: "Resultados da busca" });
  await waitFor(() => expect(buscas).toContain(texto));
  return resultados;
}

const esperar = (ms: number) => act(() => new Promise((fim) => setTimeout(fim, ms)));

describe("o campo de busca (issue #1956)", () => {
  it("fica na barra do topo, com a dica do que dá para digitar", async () => {
    const entrada = await campo();

    expect(entrada.placeholder).toBe(DICA_DA_BUSCA);
    expect(DICA_DA_BUSCA).toBe("Número do atendimento ou nome do paciente");
  });

  it("quem não analisa contas não vê o campo", async () => {
    permissoes = ["enviar_contas"];
    render(<ContasMedicasPage />);
    await screen.findByRole("region", { name: "Esteira" });

    expect(screen.queryByRole("searchbox", { name: "Buscar conta" })).toBeNull();
  });

  it("com um caractere não busca e pede mais um", async () => {
    fireEvent.change(await campo(), { target: { value: "2" } });
    await esperar(400);

    expect(buscas).toEqual([]);
    expect(within(screen.getByRole("region", { name: "Resultados da busca" })).getByText(DIGITE_MAIS)).toBeTruthy();
  });

  it("espera 300 ms depois da última tecla e busca só o texto final", async () => {
    const entrada = await campo();

    fireEvent.change(entrada, { target: { value: "27" } });
    await esperar(100);
    fireEvent.change(entrada, { target: { value: "277" } });
    await esperar(250);
    expect(buscas).toEqual([]);

    await waitFor(() => expect(buscas).toEqual(["277"]));
  });
});

describe("os resultados da busca (issue #1956)", () => {
  it("ocupam o lugar da Esteira e da lista; limpar o campo devolve a tela como estava", async () => {
    const entrada = await campo();
    fireEvent.click(within(screen.getByRole("region", { name: "Esteira" })).getByRole("tab", { name: /^Concluídas/ }));

    fireEvent.change(entrada, { target: { value: "2775" } });
    await waitFor(() => expect(buscas).toEqual(["2775"]));
    expect(screen.queryByRole("region", { name: "Esteira" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Lista de contas" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Limpar a busca" }));

    expect(entrada.value).toBe("");
    expect(screen.queryByRole("region", { name: "Resultados da busca" })).toBeNull();
    const marcada = within(screen.getByRole("region", { name: "Esteira" }))
      .getAllByRole("tab")
      .filter((aba) => aba.getAttribute("aria-selected") === "true");
    expect(marcada.map((aba) => aba.textContent)).toEqual(["Concluídas 0"]);
  });

  it("vários resultados: cada linha com o trecho marcado, com quem está, e sem botão na conta que a pessoa não abre", async () => {
    respostaDaBusca = () => ({ contas: [LIVRE, DA_OUTRA, MINHA], mais: false });
    const resultados = await buscar("27");
    const linhas = await within(resultados).findAllByRole("listitem");

    expect(linhas.map((l) => Array.from(l.querySelectorAll("mark")).map((m) => m.textContent))).toEqual([
      ["27"],
      ["27"],
      [],
    ]);
    expect(within(linhas[1]).getByText("com Sicrana Z.")).toBeTruthy();
    expect(within(linhas[0]).getByRole("link", { name: "Pegar" }).getAttribute("href")).toBe("/contas-medicas/guia/livre");
    expect(within(linhas[1]).queryByRole("link")).toBeNull();
    expect(within(linhas[2]).getByRole("link", { name: "Continuar" })).toBeTruthy();
    expect(within(resultados).queryByText(REFINE_A_BUSCA)).toBeNull();
  });

  it("marca o trecho do nome sem diferenciar maiúscula nem acento", async () => {
    respostaDaBusca = () => ({ contas: [DA_OUTRA, conta({ id: "x", paciente_rotulo: "Mariantonia S." })], mais: false });
    const resultados = await buscar("ANTO");
    const linhas = await within(resultados).findAllByRole("listitem");

    expect(linhas.map((l) => l.querySelector("mark")?.textContent)).toEqual(["Antô", "anto"]);
  });

  it("com mais de 50, avisa para refinar", async () => {
    respostaDaBusca = () => ({ contas: [LIVRE, DA_OUTRA], mais: true });
    const resultados = await buscar("27");

    expect(await within(resultados).findByText(REFINE_A_BUSCA)).toBeTruthy();
    expect(REFINE_A_BUSCA).toBe("Aparecem só as 50 primeiras. Digite mais do número ou do nome para refinar.");
  });

  it("um resultado só: a conta em destaque, com número grande, rótulo, onde está, com quem e o Pegar", async () => {
    respostaDaBusca = () => ({ contas: [LIVRE], mais: false });
    const resultados = await buscar("27751");
    const destaque = await within(resultados).findByRole("article", { name: "Conta encontrada" });

    const numero = destaque.querySelector("p.text-4xl");
    expect(numero?.textContent).toBe("27751");
    expect(numero?.querySelector("mark")?.textContent).toBe("27751");
    expect(within(destaque).getByText("Fulana T.")).toBeTruthy();
    expect(within(destaque).getByText("Fila, a fazer")).toBeTruthy();
    expect(within(destaque).getByText("Ninguém pegou ainda")).toBeTruthy();
    const pegar = within(destaque).getByRole("link", { name: "Pegar" });
    expect(pegar.getAttribute("href")).toBe("/contas-medicas/guia/livre");
    expect(within(resultados).queryByRole("listitem")).toBeNull();
  });

  it("um resultado só, a sua em análise: Continuar", async () => {
    respostaDaBusca = () => ({ contas: [MINHA], mais: false });
    const destaque = await within(await buscar("31999")).findByRole("article", { name: "Conta encontrada" });

    expect(within(destaque).getByText("Com você")).toBeTruthy();
    expect(within(destaque).getByText("Em análise, em correção")).toBeTruthy();
    expect(within(destaque).getByRole("link", { name: "Continuar" }).getAttribute("href")).toBe(
      "/contas-medicas/guia/minha",
    );
  });

  it("um resultado só, com outra pessoa: diz com quem está e não tem botão", async () => {
    respostaDaBusca = () => ({ contas: [DA_OUTRA], mais: false });
    const destaque = await within(await buscar("27752")).findByRole("article", { name: "Conta encontrada" });

    expect(within(destaque).getByText("Sicrana Z.")).toBeTruthy();
    expect(within(destaque).getByText("Em análise, em correção")).toBeTruthy();
    expect(within(destaque).queryByRole("link")).toBeNull();
  });

  it("sem resultado, diz que a busca olhou todas as etapas", async () => {
    respostaDaBusca = () => ({ contas: [], mais: false });
    const resultados = await buscar("99999");

    expect(await within(resultados).findByText(SEM_RESULTADO)).toBeTruthy();
    expect(SEM_RESULTADO).toBe("Nenhuma conta com esse número ou nome. A busca olhou todas as etapas.");
  });
});
