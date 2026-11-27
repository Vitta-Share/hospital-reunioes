/**
 * @vitest-environment jsdom
 */

/**
 * O Quadro e a lista da aba Tecnologia, só para ler (issue #1384, PRD #1380;
 * issue #2279, ADR 0113, decisões 6 e 7).
 *
 * A tela inteira do Quadro, com o `fetch` dublado: a lista das Demandas, com
 * o título e a Etapa; o clique que abre o Documento do card; os filtros; o
 * endereço que acompanha o card aberto; e a lista como tela própria no
 * celular. O chat, a Conversa da Demanda e os botões que agiam saíram.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";
import { caixaDoDado } from "@/lib/testes/caixaDoDado";

import {
  ACOMPANHAMENTO,
  AMPLIAR,
  ConversasDaTecnologia,
  FECHAR_O_PAINEL,
  MOSTRAR_AS_QUE_NAO_SERAO_FEITAS,
  SEM_ACESSO,
  VOLTAR_AO_QUADRO,
  VOLTAR_PARA_A_LISTA,
} from "./ConversasDaTecnologia";
import { Demanda } from "./demandas";

beforeEach(() => {
  // O jsdom não implementa `scrollIntoView`, que o `Select` da casa chama ao
  // abrir a lista de opções dos filtros (issue #1578).
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const LISTA = "/api/admin/tecnologia/chat";

function demanda(id: string, titulo: string, extra: Partial<Demanda> = {}): Demanda {
  return {
    id,
    titulo,
    criado_em: "2026-11-01T10:00:00Z",
    etapa: "registrada",
    tem_vinculo: false,
    o_que_muda: null,
    partes: [],
    ...extra,
  };
}

type Chamada = { url: string; metodo: string; corpo: unknown };
type Resposta = { status: number; corpo: unknown };
type Servidor = (url: string, metodo: string, corpo: unknown) => Resposta;

/** Monta a aba com um servidor falso que responde pela URL e pelo método. */
function montar(servidor: Servidor, demandaInicial: string | null = null) {
  const chamadas: Chamada[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const metodo = init?.method ?? "GET";
      const corpo = init?.body ? JSON.parse(String(init.body)) : null;
      chamadas.push({ url, metodo, corpo });
      const resposta = servidor(url, metodo, corpo);
      return {
        ok: resposta.status < 400,
        status: resposta.status,
        json: async () => resposta.corpo,
      } as unknown as Response;
    }),
  );
  const arvore = (demanda: string | null) => (
    <ToastProvider>
      <ConversasDaTecnologia token="token-de-teste" demandaInicial={demanda} />
    </ToastProvider>
  );
  const { rerender } = render(arvore(demandaInicial));
  trocarDemandaInicial = (demanda) => rerender(arvore(demanda));
  return chamadas;
}

/** Remonta a aba montada com outra `demandaInicial`, como a página faz quando o endereço muda. */
let trocarDemandaInicial: (demanda: string | null) => void = () => {};

const demandaDaUrl = () => new URLSearchParams(window.location.search).get("demanda");

/** A página lê o `?demanda=` do endereço: depois de a tela escrever nele, a prop muda também. */
function aPaginaLeOEndereco() {
  trocarDemandaInicial(demandaDaUrl());
}

function lista() {
  return screen.getByRole("navigation", { name: "Pedidos" });
}

const SEM_CARD = demanda("d-1", "Botão de responder some na Ouvidoria");
const COM_VINCULO = demanda("d-2", "Aviso quando a ata sair", {
  etapa: "em_producao",
  versao: "v0.207.0",
  tem_vinculo: true,
  o_que_muda: "Agora o aviso da ata chega por e-mail.",
});

describe("A lista", () => {
  it("mostra o título e a Etapa de cada Demanda, na ordem que o servidor manda", async () => {
    montar((url) => (url === LISTA ? { status: 200, corpo: [COM_VINCULO, SEM_CARD] } : { status: 404, corpo: {} }));

    await within(lista()).findByText("Aviso quando a ata sair");
    const itens = within(lista()).getAllByRole("listitem");
    expect(itens).toHaveLength(2);
    expect(within(itens[0]).getByText("Aviso quando a ata sair")).toBeTruthy();
    expect(within(itens[0]).getByText("Em produção desde v0.207.0")).toBeTruthy();
    expect(within(itens[1]).getByText("Botão de responder some na Ouvidoria")).toBeTruthy();
    expect(within(itens[1]).getByText("Registrada")).toBeTruthy();
  });

  it("mostra o selo Bug ou Melhoria ao lado da Etapa (issue #1438)", async () => {
    const bug = demanda("d-3", "O relatório some", { classificacao: "bug" });
    const melhoria = demanda("d-4", "Aviso quando a ata sair", { classificacao: "melhoria" });
    const antiga = demanda("d-5", "Pedido de antes do chat", { classificacao: null });
    montar((url) => (url === LISTA ? { status: 200, corpo: [bug, melhoria, antiga] } : { status: 404, corpo: {} }));

    await within(lista()).findByText("O relatório some");
    const itens = within(lista()).getAllByRole("listitem");
    expect(within(itens[0]).getByText("Bug")).toBeTruthy();
    expect(within(itens[1]).getByText("Melhoria")).toBeTruthy();
    expect(within(itens[2]).queryByText(/^(Bug|Melhoria)$/)).toBeNull();
    expect(within(itens[2]).getByText("Registrada")).toBeTruthy();
  });

  it("mostra o selo Tem demonstração só no pedido com o link do vídeo (issue #1559)", async () => {
    const comVideo = demanda("d-6", "Selo na lista", { demonstracao_url: "https://youtu.be/demo" });
    const semVideo = demanda("d-7", "Sem vídeo", { demonstracao_url: null });
    montar((url) => (url === LISTA ? { status: 200, corpo: [comVideo, semVideo] } : { status: 404, corpo: {} }));

    await within(lista()).findByText("Selo na lista");
    const itens = within(lista()).getAllByRole("listitem");
    expect(within(itens[0]).getByText("Tem demonstração")).toBeTruthy();
    expect(within(itens[1]).queryByText("Tem demonstração")).toBeNull();
  });

  it("mostra o Número da Demanda em cada linha, até na conversa ainda sem card (issue #1585)", async () => {
    const semCard = demanda("d-8", "Conversa nova", { numero: 43 });
    const comCard = demanda("d-9", "Card antigo", { numero: 7, etapa: "em_desenvolvimento", tem_vinculo: true });
    montar((url) => (url === LISTA ? { status: 200, corpo: [semCard, comCard] } : { status: 404, corpo: {} }));

    await within(lista()).findByText("Conversa nova");
    const itens = within(lista()).getAllByRole("listitem");
    expect(within(itens[0]).getByText("Demanda 43")).toBeTruthy();
    expect(within(itens[1]).getByText("Demanda 7")).toBeTruthy();
  });

  it("sem pedido nenhum, diz que ainda não há", async () => {
    montar(() => ({ status: 200, corpo: [] }));

    expect(await within(lista()).findByText("Nenhum pedido ainda.")).toBeTruthy();
  });
});

describe("Acompanhar", () => {
  it("clicar num pedido com Vínculo mostra o Documento do card, sem conversa", async () => {
    montar((url) => {
      if (url === LISTA) return { status: 200, corpo: [COM_VINCULO] };
      return { status: 404, corpo: {} };
    });

    fireEvent.click(await within(lista()).findByRole("button", { name: /Aviso quando a ata sair/ }));

    const oQueMuda = await screen.findByRole("region", { name: ACOMPANHAMENTO });
    expect(within(oQueMuda).getByText("Agora o aviso da ata chega por e-mail.")).toBeTruthy();
    // Só para ler (issue #2279): nem a conversa com o agente, nem a Conversa da Demanda.
    expect(screen.queryByRole("region", { name: "Conversa da Demanda" })).toBeNull();
    expect(screen.queryByLabelText("Sua mensagem")).toBeNull();
  });

  it("o pedido validado mostra Plano validado em ao lado da Etapa (issue #1915)", async () => {
    montar((url) => {
      if (url === LISTA) return { status: 200, corpo: [{ ...COM_VINCULO, validado_em: "2026-11-16T13:05:00.000Z" }] };
      return { status: 404, corpo: {} };
    });

    fireEvent.click(await within(lista()).findByRole("button", { name: /Aviso quando a ata sair/ }));

    const selo = await screen.findByText("Plano validado em 16/11/2026");
    expect(selo.parentElement?.querySelector('[aria-label^="Etapa: "]')).toBeTruthy();
  });

  it("sem o texto da Vitta, diz Descrição em preparação", async () => {
    montar((url) => {
      if (url === LISTA) return { status: 200, corpo: [{ ...COM_VINCULO, o_que_muda: null }] };
      return { status: 404, corpo: { detail: "Esta conversa não foi encontrada." } };
    });

    fireEvent.click(await within(lista()).findByRole("button", { name: /Aviso quando a ata sair/ }));

    const oQueMuda = await screen.findByRole("region", { name: ACOMPANHAMENTO });
    expect(within(oQueMuda).getByText("Descrição em preparação")).toBeTruthy();
  });
});

describe("Caixa alta (ADR 0080, issue #1455)", () => {
  it("o título da Demanda aparece como foi escrito, na lista e no alto da conversa", async () => {
    montar((url) => {
      if (url === LISTA) return { status: 200, corpo: [COM_VINCULO] };
      return { status: 404, corpo: {} };
    });

    const naLista = await within(lista()).findByText("Aviso quando a ata sair");
    expect(caixaDoDado(naLista)).toBe("normal-case");

    fireEvent.click(within(lista()).getByRole("button", { name: /Aviso quando a ata sair/ }));
    const titulo = await screen.findByRole("heading", { level: 2, name: "Aviso quando a ata sair" });
    expect(caixaDoDado(titulo)).toBe("normal-case");
  });
});

describe("No celular", () => {
  it("a lista é a tela de entrada, e a conversa aberta tem o caminho de volta", async () => {
    montar((url) => {
      if (url === LISTA) return { status: 200, corpo: [SEM_CARD] };
      return { status: 404, corpo: {} };
    });
    const painelDaLista = () => lista().parentElement as HTMLElement;
    const painelDoChat = () => screen.getByRole("region", { name: "Pedido na tela" });

    // Na largura do celular só um dos dois aparece: `hidden` esconde, e o
    // `md:` devolve os dois lado a lado na tela larga.
    await within(lista()).findByText("Botão de responder some na Ouvidoria");
    expect(painelDaLista().className).not.toMatch(/(^|\s)hidden(\s|$)/);
    expect(painelDoChat().className).toMatch(/(^|\s)hidden(\s|$)/);

    fireEvent.click(within(lista()).getByRole("button", { name: /Botão de responder some/ }));
    await screen.findByRole("region", { name: ACOMPANHAMENTO });
    expect(painelDaLista().className).toMatch(/(^|\s)hidden(\s|$)/);
    expect(painelDoChat().className).not.toMatch(/(^|\s)hidden(\s|$)/);

    fireEvent.click(screen.getByRole("button", { name: VOLTAR_PARA_A_LISTA }));
    await waitFor(() => expect(painelDaLista().className).not.toMatch(/(^|\s)hidden(\s|$)/));
    expect(painelDoChat().className).toMatch(/(^|\s)hidden(\s|$)/);
  });
});

describe("O Desenvolvedor (issue #1531, ADR 0083)", () => {
  const EU = "/api/admin/tecnologia/eu";
  const TODAS = `${LISTA}?filtro=todas`;
  const PARA_MIM = `${LISTA}?filtro=para_mim`;
  const DO_DIRETOR = demanda("d-7", "O relatório some", { minha: false, autor: "Diretor do Hospital" });
  const COM_CARD_DE_OUTRO = demanda("d-8", "O botão sumiu", {
    minha: false,
    autor: "Outro Diretor",
    etapa: "em_desenvolvimento",
    tem_vinculo: true,
    issue_numero: 912,
    issue_url: "https://github.com/Vitta-Share/hospital-reunioes/issues/912",
  });

  it("vê o filtro Todas, que traz as Demandas de todos com o autor em cada linha", async () => {
    const chamadas = montar((url) => {
      if (url === EU) return { status: 200, corpo: { desenvolvedor: true } };
      if (url === PARA_MIM) return { status: 200, corpo: [SEM_CARD] };
      if (url === TODAS) return { status: 200, corpo: [DO_DIRETOR, { ...SEM_CARD, autor: "Pedro Vitta" }] };
      return { status: 404, corpo: {} };
    });

    fireEvent.click(await screen.findByRole("button", { name: "Todas" }));

    await within(lista()).findByText("O relatório some");
    const itens = within(lista()).getAllByRole("listitem");
    expect(within(itens[0]).getByText("O relatório some")).toBeTruthy();
    expect(within(itens[0]).getByText("Diretor do Hospital")).toBeTruthy();
    expect(within(itens[1]).getByText("Botão de responder some na Ouvidoria")).toBeTruthy();
    expect(within(itens[1]).getByText("Pedro Vitta")).toBeTruthy();
    expect(chamadas.some((c) => c.url === TODAS)).toBe(true);
  });

  it("quem não é Desenvolvedor não vê o filtro", async () => {
    montar((url) => {
      if (url === EU) return { status: 200, corpo: { desenvolvedor: false } };
      if (url === LISTA) return { status: 200, corpo: [SEM_CARD] };
      return { status: 404, corpo: {} };
    });

    await within(lista()).findByText("Botão de responder some na Ouvidoria");
    expect(screen.queryByRole("button", { name: "Todas" })).toBeNull();
  });

  it("vê o número e o link da issue na Demanda que já tem card", async () => {
    montar((url) => {
      if (url === EU) return { status: 200, corpo: { desenvolvedor: true } };
      if (url === PARA_MIM) return { status: 200, corpo: [COM_CARD_DE_OUTRO] };
      return { status: 404, corpo: {} };
    });

    fireEvent.click(await within(lista()).findByRole("button", { name: /O botão sumiu/ }));

    const link = await screen.findByRole("link", { name: "#912" });
    expect(link.getAttribute("href")).toBe("https://github.com/Vitta-Share/hospital-reunioes/issues/912");
  });

  // ─── O Responsável e o Para mim (issue #1533, ADR 0083, decisão 5) ────────

  it("a lista abre em Para mim e mostra só as Demandas de que ele é Responsável", async () => {
    const minha = demanda("d-9", "Agenda de retorno", {
      tem_vinculo: true,
      etapa: "em_analise",
      responsavel: "Pedro Vitta",
    });
    const chamadas = montar((url) => {
      if (url === EU) return { status: 200, corpo: { desenvolvedor: true } };
      if (url === PARA_MIM) return { status: 200, corpo: [minha] };
      if (url === LISTA) return { status: 200, corpo: [SEM_CARD] };
      return { status: 404, corpo: {} };
    });

    await within(lista()).findByText("Agenda de retorno");
    expect(screen.getByRole("button", { name: "Para mim" }).getAttribute("aria-pressed")).toBe("true");
    expect(within(lista()).getAllByRole("listitem")).toHaveLength(1);
    const listas = chamadas.filter((c) => c.url.startsWith(LISTA));
    expect(listas.map((c) => c.url)).toEqual([PARA_MIM]);
  });

  it("o recorte do Desenvolvedor é Para mim, Minhas e Todas", async () => {
    montar((url) => {
      if (url === EU) return { status: 200, corpo: { desenvolvedor: true } };
      return { status: 200, corpo: [] };
    });

    const filtros = await screen.findByRole("group", { name: "Recorte" });
    expect(within(filtros).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Para mim",
      "Minhas",
      "Todas",
    ]);
  });
});

describe("O Responsável na lista (issue #1533, ADR 0083)", () => {
  it("o diretor vê quem cuida de cada pedido que já virou card", async () => {
    const comResponsavel = demanda("d-10", "Agenda de retorno", {
      tem_vinculo: true,
      etapa: "em_analise",
      responsavel: "Lucas Sampaio",
    });
    montar((url) => (url === LISTA ? { status: 200, corpo: [comResponsavel, SEM_CARD] } : { status: 404, corpo: {} }));

    await within(lista()).findByText("Agenda de retorno");
    const itens = within(lista()).getAllByRole("listitem");
    expect(within(itens[0]).getByText("Responsável")).toBeTruthy();
    expect(within(itens[0]).getByText("Lucas Sampaio")).toBeTruthy();
    expect(within(itens[0]).getByText("Em análise")).toBeTruthy();
    expect(within(itens[1]).queryByText("Responsável")).toBeNull();
  });

  it("o Desenvolvedor vê o autor e o Responsável em cada linha", async () => {
    const deOutro = demanda("d-11", "O botão sumiu", {
      minha: false,
      autor: "Diretor do Hospital",
      tem_vinculo: true,
      etapa: "em_analise",
      responsavel: "Pedro Rib",
    });
    montar((url) => {
      if (url === "/api/admin/tecnologia/eu") return { status: 200, corpo: { desenvolvedor: true } };
      if (url === `${LISTA}?filtro=todas`) return { status: 200, corpo: [deOutro] };
      return { status: 200, corpo: [] };
    });

    fireEvent.click(await screen.findByRole("button", { name: "Todas" }));

    await within(lista()).findByText("O botão sumiu");
    const [item] = within(lista()).getAllByRole("listitem");
    expect(within(item).getByText("Pediu")).toBeTruthy();
    expect(within(item).getByText("Diretor do Hospital")).toBeTruthy();
    expect(within(item).getByText("Responsável")).toBeTruthy();
    expect(within(item).getByText("Pedro Rib")).toBeTruthy();
  });
});

describe("O selo Envio falhou (issue #1535, ADR 0083, decisão 7)", () => {
  const FALHOU = demanda("d-1", "Botão de responder some na Ouvidoria", {
    classificacao: "bug",
    envio_falhou: true,
    envio_motivo: null,
  });

  function linha(titulo: RegExp) {
    return within(lista()).getByRole("button", { name: titulo });
  }

  it("o diretor vê o selo Envio falhou na linha do pedido", async () => {
    montar((url) => (url === LISTA ? { status: 200, corpo: [FALHOU, COM_VINCULO] } : { status: 404, corpo: {} }));

    await within(lista()).findByText("Botão de responder some na Ouvidoria");
    expect(within(linha(/Botão de responder/)).getByText("Envio falhou")).toBeTruthy();
    expect(within(linha(/Aviso quando a ata/)).queryByText("Envio falhou")).toBeNull();
  });
});

/** Escolhe uma opção num campo de filtro: abre o campo pelo rótulo e clica na opção. */
function escolher(campo: string, opcao: string) {
  const filtros = screen.getByRole("region", { name: "Filtros da lista" });
  fireEvent.click(within(filtros).getByRole("combobox", { name: campo }));
  fireEvent.click(screen.getByRole("option", { name: opcao }));
}

describe("A barra de filtros por categoria (issue #1578, emenda da ADR 0084)", () => {
  const EU = "/api/admin/tecnologia/eu";
  const DESENVOLVEDORES = "/api/admin/tecnologia/desenvolvedores";
  const QUEM_CUIDA = [
    { id: "P1", nome: "Pedro Vitta", padrao: true },
    { id: "P4", nome: "Pedro Rib", padrao: false },
  ];

  function filtros() {
    return screen.getByRole("region", { name: "Filtros da lista" });
  }

  /** O rótulo visível de cada campo, na ordem da barra. */
  function campos() {
    return within(filtros())
      .getAllByRole("combobox")
      .map((c) => document.querySelector(`label[for="${c.id}"]`)?.textContent);
  }

  function comoDiretor() {
    return montar((url) => {
      if (url === EU) return { status: 200, corpo: { desenvolvedor: false } };
      if (url.startsWith(LISTA)) return { status: 200, corpo: [SEM_CARD] };
      return { status: 404, corpo: {} };
    });
  }

  it("a busca pelo título vai ao servidor", async () => {
    const chamadas = comoDiretor();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");

    fireEvent.change(screen.getByRole("searchbox", { name: "Buscar pelo título" }), {
      target: { value: "relatorio" },
    });

    await waitFor(() => expect(chamadas.map((c) => c.url)).toContain(`${LISTA}?busca=relatorio`));
  });

  it("o diretor combina Tipo e Etapa, e Todos desfaz o Tipo", async () => {
    const chamadas = comoDiretor();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");

    escolher("Tipo", "Bug");
    escolher("Etapa", "Em produção");
    await waitFor(() => expect(chamadas.map((c) => c.url)).toContain(`${LISTA}?tipo=bug&etapa=em_producao`));
    expect(within(filtros()).getByRole("combobox", { name: "Tipo" }).textContent).toBe("Bug");

    escolher("Tipo", "Todos");
    await waitFor(() => expect(chamadas.at(-1)?.url).toBe(`${LISTA}?etapa=em_producao`));
  });

  it("o diretor vê Tipo, Etapa, Origem e Projeto, sem o recorte, o Responsável e o Envio falhou", async () => {
    comoDiretor();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");

    expect(campos()).toEqual(["Tipo", "Etapa", "Origem", "Projeto"]);
    expect(within(filtros()).queryByRole("group", { name: "Recorte" })).toBeNull();
    expect(within(filtros()).queryByRole("switch")).toBeNull();
  });

  it("o Desenvolvedor combina Responsável e Envio falhou com o Para mim", async () => {
    // O que a rota de verdade responde a essa combinacao: a falha de outro autor,
    // porque Envio falhou nao e cortado por Responsavel (a Demanda sem card nao
    // tem um), como prova o teste de rota de mesmo nome no backend.
    const COMBINADA = `${LISTA}?filtro=para_mim&tipo=melhoria&responsavel=P4&envio_falhou=true`;
    const falhaDeOutro = demanda("d-9", "Relatorio de custo por setor", {
      classificacao: "melhoria",
      envio_falhou: true,
      minha: false,
      autor: "Diretor do Hospital",
    });
    const chamadas = montar((url) => {
      if (url === EU) return { status: 200, corpo: { desenvolvedor: true } };
      if (url === DESENVOLVEDORES) return { status: 200, corpo: QUEM_CUIDA };
      if (url === COMBINADA) return { status: 200, corpo: [falhaDeOutro] };
      if (url.startsWith(LISTA)) return { status: 200, corpo: [SEM_CARD] };
      return { status: 404, corpo: {} };
    });
    await within(lista()).findByText("Botão de responder some na Ouvidoria");
    await waitFor(() => expect(campos()).toEqual(["Tipo", "Etapa", "Origem", "Projeto", "Responsável"]));

    const recorte = within(filtros()).getByRole("group", { name: "Recorte" });
    expect(within(recorte).getAllByRole("button").map((b) => b.textContent)).toEqual(["Para mim", "Minhas", "Todas"]);
    expect(within(recorte).getByRole("button", { name: "Para mim" }).getAttribute("aria-pressed")).toBe("true");

    escolher("Responsável", "Pedro Rib");
    const soFalhas = within(filtros()).getByRole("switch", { name: "Só envio falhou" });
    expect(soFalhas.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(soFalhas);
    expect(soFalhas.getAttribute("aria-checked")).toBe("true");
    escolher("Tipo", "Melhoria");

    await waitFor(() => expect(chamadas.at(-1)?.url).toBe(COMBINADA));
    expect(await within(lista()).findByText("Relatorio de custo por setor")).toBeTruthy();
    expect(within(lista()).queryByText("Botão de responder some na Ouvidoria")).toBeNull();
  });

  it("Limpar filtros aparece só com filtro ativo e volta tudo ao padrão, menos o recorte", async () => {
    const chamadas = montar((url) => {
      if (url === EU) return { status: 200, corpo: { desenvolvedor: true } };
      if (url === DESENVOLVEDORES) return { status: 200, corpo: QUEM_CUIDA };
      if (url.startsWith(LISTA)) return { status: 200, corpo: [SEM_CARD] };
      return { status: 404, corpo: {} };
    });
    await within(lista()).findByText("Botão de responder some na Ouvidoria");
    await within(filtros()).findByRole("switch", { name: "Só envio falhou" });
    expect(within(filtros()).queryByRole("button", { name: "Limpar filtros" })).toBeNull();

    escolher("Etapa", "Planejada");
    fireEvent.click(within(filtros()).getByRole("switch", { name: "Só envio falhou" }));
    fireEvent.change(screen.getByRole("searchbox", { name: "Buscar pelo título" }), { target: { value: "ata" } });
    await waitFor(() =>
      expect(chamadas.at(-1)?.url).toBe(`${LISTA}?filtro=para_mim&busca=ata&etapa=planejada&envio_falhou=true`),
    );

    fireEvent.click(within(filtros()).getByRole("button", { name: "Limpar filtros" }));

    await waitFor(() => expect(chamadas.at(-1)?.url).toBe(`${LISTA}?filtro=para_mim`));
    expect((screen.getByRole("searchbox", { name: "Buscar pelo título" }) as HTMLInputElement).value).toBe("");
    expect(within(filtros()).getByRole("combobox", { name: "Etapa" }).textContent).toBe("Todas");
    expect(within(filtros()).getByRole("switch", { name: "Só envio falhou" }).getAttribute("aria-checked")).toBe(
      "false",
    );
    expect(within(filtros()).queryByRole("button", { name: "Limpar filtros" })).toBeNull();
  });

  it("a barra fica em cima, fora da coluna da lista", async () => {
    montar((url) => {
      if (url === LISTA) return { status: 200, corpo: [SEM_CARD] };
      return { status: 404, corpo: {} };
    });
    const painelDaLista = () => lista().parentElement as HTMLElement;

    await within(lista()).findByText("Botão de responder some na Ouvidoria");
    expect(painelDaLista().contains(filtros())).toBe(false);
    expect(filtros().compareDocumentPosition(lista()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe("O pedido ao lado da lista e o Ampliar (issue #1593)", () => {
  const OUTRO = demanda("d-3", "Relatório de leitos atrasa");
  const recolhida = /(^|\s)md:hidden(\s|$)/;

  function comDuas() {
    return montar((url) => {
      if (url === LISTA) return { status: 200, corpo: [SEM_CARD, OUTRO] };
      return { status: 404, corpo: {} };
    });
  }

  const painelDaLista = () => lista().parentElement as HTMLElement;
  const filtros = () => screen.getByRole("region", { name: "Filtros da lista" });
  const aberto = () => screen.getByRole("region", { name: "Pedido na tela" });
  const voltar = () => screen.getByRole("button", { name: VOLTAR_PARA_A_LISTA });
  const cardDe = (titulo: RegExp) =>
    within(lista())
      .getAllByRole("listitem")
      .find((item) => within(item).queryByRole("button", { name: titulo })) as HTMLElement;

  /** A lista e a barra à vista na tela larga, e o Voltar só no celular. */
  function listaAoLado() {
    expect(painelDaLista().className).not.toMatch(recolhida);
    expect(filtros().className).not.toMatch(recolhida);
    expect(voltar().className).toMatch(recolhida);
  }

  /** A lista e a barra recolhidas na tela larga, e o Voltar à vista. */
  function listaRecolhida() {
    expect(painelDaLista().className).toMatch(recolhida);
    expect(filtros().className).toMatch(recolhida);
    expect(voltar().className).not.toMatch(recolhida);
  }

  it("em tela larga, o clique no cartão abre o pedido com a lista visível", async () => {
    comDuas();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");

    fireEvent.click(within(lista()).getByRole("button", { name: /Botão de responder some/ }));
    await screen.findByRole("region", { name: ACOMPANHAMENTO });

    listaAoLado();
  });

  it("o Ampliar do cartão abre o pedido com a lista recolhida, e o Voltar devolve a lista", async () => {
    comDuas();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");

    fireEvent.click(within(cardDe(/Botão de responder some/)).getByRole("button", { name: AMPLIAR }));
    await screen.findByRole("region", { name: ACOMPANHAMENTO });
    listaRecolhida();

    fireEvent.click(voltar());
    await waitFor(() => expect(painelDaLista().className).not.toMatch(recolhida));
    expect(filtros().className).not.toMatch(recolhida);
  });

  it("o Ampliar também fica no topo do pedido aberto ao lado, e faz o mesmo", async () => {
    comDuas();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");

    fireEvent.click(within(lista()).getByRole("button", { name: /Botão de responder some/ }));
    await screen.findByRole("region", { name: ACOMPANHAMENTO });
    listaAoLado();

    fireEvent.click(within(aberto()).getByRole("button", { name: AMPLIAR }));
    listaRecolhida();
    // Ampliado, o pedido não oferece Ampliar de novo: o caminho é o Voltar.
    expect(within(aberto()).queryByRole("button", { name: AMPLIAR })).toBeNull();

    fireEvent.click(voltar());
    await waitFor(() => expect(painelDaLista().className).not.toMatch(recolhida));

    // De volta ao lado da lista, o Ampliar do topo amplia de novo.
    fireEvent.click(within(aberto()).getByRole("button", { name: AMPLIAR }));
    listaRecolhida();
  });

  it("depois de ampliar um pedido, o clique em outro cartão abre ao lado", async () => {
    comDuas();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");

    fireEvent.click(within(cardDe(/Botão de responder some/)).getByRole("button", { name: AMPLIAR }));
    await screen.findByRole("region", { name: ACOMPANHAMENTO });
    listaRecolhida();
    fireEvent.click(voltar());

    fireEvent.click(within(lista()).getByRole("button", { name: /Relatório de leitos atrasa/ }));
    await waitFor(() => expect(cardDe(/Relatório de leitos/).querySelector("[aria-current]")).toBeTruthy());
    listaAoLado();
  });

});

describe("O card da conversa (issue #1578)", () => {
  const COMPLETO = demanda("d-c", "Ata de reunião longa para com erro", {
    criado_em: "2026-11-01T13:00:00Z",
    etapa: "em_desenvolvimento",
    tem_vinculo: true,
    classificacao: "bug",
    origem: "diretor",
    autor: "Felipe Malafaia",
    responsavel: "Pedro Rezende",
    partes_entregues: 2,
    partes_total: 5,
  });

  function comCard() {
    return montar((url) => {
      if (url === LISTA) return { status: 200, corpo: [COMPLETO] };
      if (url === `${LISTA}/d-c/conversa`) return { status: 200, corpo: { mensagens: [], mencionaveis: [] } };
      return { status: 404, corpo: {} };
    });
  }

  async function card() {
    await within(lista()).findByText("Ata de reunião longa para com erro");
    return within(lista()).getAllByRole("listitem")[0];
  }

  it("mostra a data de abertura, quem pediu e quem cuida com as iniciais, e a Etapa", async () => {
    comCard();
    const item = await card();

    expect(within(item).getByText(/^Aberto em 01\/11/)).toBeTruthy();
    expect(within(item).getByText("Felipe Malafaia")).toBeTruthy();
    expect(within(item).getByText("FM")).toBeTruthy();
    expect(within(item).getByText("Pedro Rezende")).toBeTruthy();
    expect(within(item).getByText("PR")).toBeTruthy();
    expect(within(item).getByText("Em desenvolvimento")).toBeTruthy();
    expect(within(item).getByText("Bug")).toBeTruthy();
    expect(within(item).getByText("Pedido do diretor")).toBeTruthy();
  });

  it("o PRD com partes mostra X de Y partes e a barra de progresso", async () => {
    comCard();
    const item = await card();

    expect(within(item).getByText("2 de 5 partes")).toBeTruthy();
    const barra = within(item).getByRole("progressbar", { name: "Partes entregues" });
    expect(barra.getAttribute("aria-valuenow")).toBe("2");
    expect(barra.getAttribute("aria-valuemax")).toBe("5");
  });

  it("tem borda fora do hover, transição no hover e no foco, e não se move com motion-reduce", async () => {
    comCard();
    const item = await card();
    const contorno = item.firstElementChild as HTMLElement;

    expect(contorno.className).toMatch(/(^|\s)border(\s|$)/);
    expect(contorno.className).not.toMatch(/border-transparent/);
    expect(contorno.className).toMatch(/hover:shadow/);
    expect(contorno.className).toMatch(/focus-within:/);
    expect(contorno.className).toMatch(/(^|\s)transition/);
    // O translate do hover só existe sob motion-safe: com prefers-reduced-motion o card não pula.
    const classes = contorno.className.split(/\s+/);
    expect(classes).toContain("motion-safe:hover:-translate-y-0.5");
    const comTranslate = classes.filter((c) => /translate/.test(c));
    expect(comTranslate.length).toBeGreaterThan(0);
    for (const c of comTranslate) expect(c.startsWith("motion-safe:")).toBe(true);
  });

});

describe("Os cards que a Vitta abre pelo terminal (issue #1554, ADR 0084, decisão 4)", () => {
  const EU = "/api/admin/tecnologia/eu";
  const DO_TERMINAL = demanda("d-v", "Ouvidoria: prazo por setor", {
    etapa: "em_analise",
    tem_vinculo: true,
    minha: false,
    origem: "vitta",
    o_que_muda: "**O que muda:** o prazo aparece por setor.",
  });
  const DO_DIRETOR = demanda("d-d", "Botão de imprimir", {
    etapa: "em_analise",
    tem_vinculo: true,
    origem: "diretor",
  });

  function comoDiretor(extra: (url: string) => Resposta | null = () => null) {
    return montar((url) => {
      const especial = extra(url);
      if (especial) return especial;
      if (url === EU) return { status: 200, corpo: { desenvolvedor: false } };
      if (url.startsWith(LISTA + "?") || url === LISTA) return { status: 200, corpo: [DO_TERMINAL, DO_DIRETOR] };
      if (url === `${LISTA}/d-v/conversa`) return { status: 200, corpo: { mensagens: [], mencionaveis: [] } };
      return { status: 404, corpo: {} };
    });
  }

  it("cada linha leva o selo Vitta ou Pedido do diretor", async () => {
    comoDiretor();

    await within(lista()).findByText("Ouvidoria: prazo por setor");
    const itens = within(lista()).getAllByRole("listitem");
    expect(within(itens[0]).getByText("Ouvidoria: prazo por setor")).toBeTruthy();
    expect(within(itens[0]).getByText("Vitta")).toBeTruthy();
    expect(within(itens[1]).getByText("Botão de imprimir")).toBeTruthy();
    expect(within(itens[1]).getByText("Pedido do diretor")).toBeTruthy();
  });

  it("o filtro Origem pede ao servidor só os cards daquela origem", async () => {
    const chamadas = comoDiretor();
    await within(lista()).findByText("Ouvidoria: prazo por setor");

    escolher("Origem", "Vitta");
    await waitFor(() => expect(chamadas.at(-1)?.url).toBe(`${LISTA}?origem=vitta`));

    escolher("Origem", "Pedido do diretor");
    await waitFor(() => expect(chamadas.at(-1)?.url).toBe(`${LISTA}?origem=diretor`));
  });

});

describe("O endereço acompanha o card aberto (issue #1586)", () => {
  const OUTRO = demanda("d-3", "Relatório de leitos atrasa");

  function comDuas(demandaInicial: string | null = null) {
    return montar((url) => {
      if (url === LISTA) return { status: 200, corpo: [SEM_CARD, OUTRO] };
      return { status: 404, corpo: {} };
    }, demandaInicial);
  }

  it("abrir um card põe a Demanda no endereço sem nova entrada no histórico, e voltar no celular tira", async () => {
    window.history.replaceState(null, "", "/admin/tecnologia");
    const entradas = window.history.length;
    comDuas();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");

    fireEvent.click(within(lista()).getByRole("button", { name: /Botão de responder some/ }));
    await screen.findByRole("region", { name: ACOMPANHAMENTO });

    expect(window.location.pathname).toBe("/admin/tecnologia");
    expect(demandaDaUrl()).toBe("d-1");
    expect(window.history.length).toBe(entradas);

    fireEvent.click(screen.getByRole("button", { name: VOLTAR_PARA_A_LISTA }));

    await waitFor(() => expect(demandaDaUrl()).toBeNull());
    expect(window.location.pathname).toBe("/admin/tecnologia");
    expect(window.history.length).toBe(entradas);
  });

  it("abrir um card, clicar noutro e recarregar abre o segundo", async () => {
    comDuas();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");
    fireEvent.click(within(lista()).getByRole("button", { name: /Botão de responder some/ }));
    await screen.findByRole("region", { name: ACOMPANHAMENTO });
    aPaginaLeOEndereco();
    fireEvent.click(within(lista()).getByRole("button", { name: /Relatório de leitos atrasa/ }));
    aPaginaLeOEndereco();
    await waitFor(() => expect(screen.getAllByText("Relatório de leitos atrasa").length).toBeGreaterThan(1));

    // Recarregar: a tela nasce de novo, só com o que está no endereço.
    cleanup();
    comDuas(demandaDaUrl());

    await waitFor(() =>
      expect(
        within(lista()).getByRole("button", { name: /Relatório de leitos atrasa/ }).getAttribute("aria-current"),
      ).toBe("true"),
    );
    expect(within(lista()).getByRole("button", { name: /Botão de responder some/ }).getAttribute("aria-current")).not.toBe(
      "true",
    );
  });

  it("o endereço que a própria tela escreveu não reabre o card nem desfaz o Ampliar", async () => {
    comDuas();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");
    const card = within(lista())
      .getAllByRole("listitem")
      .find((item) => within(item).queryByRole("button", { name: /Botão de responder some/ })) as HTMLElement;

    fireEvent.click(within(card).getByRole("button", { name: AMPLIAR }));
    await screen.findByRole("region", { name: ACOMPANHAMENTO });
    aPaginaLeOEndereco();

    expect((lista().parentElement as HTMLElement).className).toMatch(/(^|\s)md:hidden(\s|$)/);
  });

  it("com uma Demanda fora da lista, avisa que não há acesso, sem título nem número, e volta à lista", async () => {
    const DE_OUTRO_DIRETOR = "Escala da enfermagem some";
    const chamadas = comDuas("d-99");
    await within(lista()).findByText("Botão de responder some na Ouvidoria");

    const aberto = screen.getByRole("region", { name: "Pedido na tela" });
    expect(await within(aberto).findByText(SEM_ACESSO)).toBeTruthy();
    expect(aberto.className).not.toMatch(/(^|\s)hidden(\s|$)/);
    expect(within(aberto).queryByText(DE_OUTRO_DIRETOR)).toBeNull();
    expect(within(aberto).queryByText(/#\d+/)).toBeNull();
    expect(chamadas.some((c) => c.url.startsWith(`${LISTA}/d-99`))).toBe(false);

    const voltar = screen.getByRole("button", { name: VOLTAR_PARA_A_LISTA });
    expect(voltar.className).not.toMatch(/(^|\s)md:hidden(\s|$)/);
    fireEvent.click(voltar);

    await waitFor(() => expect(screen.queryByText(SEM_ACESSO)).toBeNull());
    expect((lista().parentElement as HTMLElement).className).not.toMatch(/(^|\s)hidden(\s|$)/);
    expect(demandaDaUrl()).toBeNull();
  });

  it("o sino com a tela já aberta abre o card que ele aponta, e no celular mostra o card", async () => {
    comDuas();
    await within(lista()).findByText("Botão de responder some na Ouvidoria");
    fireEvent.click(within(lista()).getByRole("button", { name: /Botão de responder some/ }));
    await screen.findByRole("region", { name: ACOMPANHAMENTO });
    aPaginaLeOEndereco();
    fireEvent.click(screen.getByRole("button", { name: VOLTAR_PARA_A_LISTA }));
    aPaginaLeOEndereco();

    // O sino leva ao mesmo endereço com outra Demanda, e a página repassa.
    window.history.pushState(null, "", "/admin/tecnologia?demanda=d-3");
    aPaginaLeOEndereco();

    await waitFor(() =>
      expect(
        within(lista()).getByRole("button", { name: /Relatório de leitos atrasa/ }).getAttribute("aria-current"),
      ).toBe("true"),
    );
    expect(screen.getByRole("region", { name: "Pedido na tela" }).className).not.toMatch(/(^|\s)hidden(\s|$)/);
  });
});

describe("O Quadro na tela larga (issue #1642, ADR 0090)", () => {
  /** A tela a partir de 1280px: o `matchMedia` que o jsdom não tem, dublado. */
  function telaLarga(larga = true) {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((consulta: string) => ({
        matches: larga && consulta === "(min-width: 1280px)",
        media: consulta,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
  }

  const quadro = () => screen.getByRole("region", { name: "Quadro" });
  const colunaDe = (etapa: string) => within(quadro()).getByRole("region", { name: etapa });

  const NO_QUADRO = [
    demanda("q-1", "Conversa que ficou no meio", { numero: 41 }),
    demanda("q-2", "Escala some no domingo", { numero: 40 }),
    demanda("q-3", "Aviso da ata por e-mail", { etapa: "em_analise", tem_vinculo: true, numero: 39 }),
    demanda("q-4", "Relatório de leitos", { etapa: "em_desenvolvimento", tem_vinculo: true, numero: 38 }),
    demanda("q-5", "Ouvidoria no celular", { etapa: "em_producao", versao: "v0.207.0", tem_vinculo: true, numero: 37 }),
  ];

  it("mostra as cinco colunas com o nome da Etapa e a contagem, no lugar da lista", async () => {
    telaLarga();
    montar((url) => (url === LISTA ? { status: 200, corpo: NO_QUADRO } : { status: 404, corpo: {} }));

    await within(await screen.findByRole("region", { name: "Quadro" })).findByText("Conversa que ficou no meio");
    const titulos = within(quadro())
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(titulos).toEqual(["Registrada2", "Em análise1", "Planejada0", "Em desenvolvimento1", "Entregue1"]);
    expect(within(colunaDe("Registrada")).getByText("Escala some no domingo")).toBeTruthy();
    expect(within(colunaDe("Entregue")).getByText("Ouvidoria no celular")).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Pedidos" })).toBeNull();
  });

  it("as colunas não têm rolagem própria e o cabeçalho de cada uma fica fixo no topo", async () => {
    telaLarga();
    montar((url) => (url === LISTA ? { status: 200, corpo: NO_QUADRO } : { status: 404, corpo: {} }));
    const oQuadro = await screen.findByRole("region", { name: "Quadro" });
    const rolagemPropria = /(^|\s)(overflow-(y-)?(auto|scroll)|max-h-)/;

    // Do Quadro para cima até a aba, ninguém rola sozinho: quem rola é a página.
    for (let caixa: HTMLElement | null = oQuadro; caixa; caixa = caixa.parentElement) {
      expect(caixa.className).not.toMatch(rolagemPropria);
    }
    for (const etapa of ["Registrada", "Em análise", "Planejada", "Em desenvolvimento", "Entregue"]) {
      const coluna = colunaDe(etapa);
      expect(coluna.className).not.toMatch(rolagemPropria);
      const classes = within(coluna).getByRole("heading", { level: 3 }).className.split(/\s+/);
      expect(classes).toEqual(expect.arrayContaining(["sticky", "top-0"]));
    }
    // A marca que o `globals.css` procura para o `<main>` deixar o `sticky` valer.
    expect(oQuadro.hasAttribute("data-quadro")).toBe(true);
  });

  it("o card compacto mostra Número, título, Bug ou Melhoria, as iniciais de quem cuida, partes, versão e selos", async () => {
    telaLarga();
    const completo = demanda("q-9", "Ata de reunião longa para com erro", {
      numero: 42,
      etapa: "em_producao",
      versao: "v0.207.0",
      tem_vinculo: true,
      classificacao: "bug",
      responsavel: "Pedro Rezende",
      autor: "Felipe Malafaia",
      partes_entregues: 2,
      partes_total: 5,
      demonstracao_url: "https://youtu.be/demo",
      envio_falhou: true,
    });
    const simples = demanda("q-8", "Pedido sem nada", { etapa: "planejada", tem_vinculo: true });
    montar((url) => (url === LISTA ? { status: 200, corpo: [completo, simples] } : { status: 404, corpo: {} }));
    await screen.findByRole("region", { name: "Quadro" });

    const card = within(colunaDe("Entregue")).getByRole("button", { name: /Ata de reunião longa/ });
    expect(card.getAttribute("aria-label")).toBe("Demanda 42: Ata de reunião longa para com erro");
    expect(within(card).getByText("Demanda 42")).toBeTruthy();
    expect(within(card).getByText("Ata de reunião longa para com erro")).toBeTruthy();
    expect(within(card).getByText("Bug")).toBeTruthy();
    expect(within(card).getByText("PR")).toBeTruthy();
    expect(within(card).getByRole("progressbar", { name: "Partes entregues" }).getAttribute("aria-valuenow")).toBe("2");
    expect(within(card).getByText("2 de 5 partes")).toBeTruthy();
    expect(within(card).getByText("v0.207.0")).toBeTruthy();
    expect(within(card).getByText("Envio falhou")).toBeTruthy();
    // O vídeo abre direto do card, num link fora do botão que abre a Demanda.
    expect(within(card).queryByText("Tem demonstração")).toBeNull();
    const video = within(colunaDe("Entregue")).getByRole("link", { name: "Assistir à demonstração" });
    expect(video.getAttribute("href")).toBe("https://youtu.be/demo");
    expect(video.getAttribute("target")).toBe("_blank");
    expect(video.getAttribute("rel")).toBe("noopener noreferrer");
    expect(card.contains(video)).toBe(false);
    // Data, quem pediu e o Conversar ficam na Demanda aberta (ADR 0090, decisão 4).
    expect(within(card).queryByText(/Aberto/)).toBeNull();
    expect(within(card).queryByText("Felipe Malafaia")).toBeNull();
    expect(within(colunaDe("Entregue")).queryByRole("button", { name: "Conversar" })).toBeNull();

    const semNada = within(colunaDe("Planejada")).getByRole("button", { name: "Pedido sem nada" });
    expect(within(semNada).queryByRole("progressbar")).toBeNull();
    expect(within(semNada).queryByText(/^(Bug|Melhoria|Tem demonstração|Envio falhou)$/)).toBeNull();
    expect(within(semNada).queryByText(/^v\d/)).toBeNull();
    expect(within(colunaDe("Planejada")).queryByRole("link", { name: "Assistir à demonstração" })).toBeNull();
  });

  it("o card não abre link da Demonstração que não é https", async () => {
    telaLarga();
    const comScript = demanda("q-10", "Vídeo com script", {
      etapa: "em_producao",
      tem_vinculo: true,
      demonstracao_url: "javascript:alert(1)",
    });
    const semTls = demanda("q-11", "Vídeo sem https", {
      etapa: "em_producao",
      tem_vinculo: true,
      demonstracao_url: "http://youtu.be/demo",
    });
    montar((url) => (url === LISTA ? { status: 200, corpo: [comScript, semTls] } : { status: 404, corpo: {} }));
    await screen.findByRole("region", { name: "Quadro" });

    const entregue = colunaDe("Entregue");
    expect(within(entregue).getByRole("button", { name: /Vídeo com script/ })).toBeTruthy();
    expect(within(entregue).getByRole("button", { name: /Vídeo sem https/ })).toBeTruthy();
    expect(within(entregue).queryByRole("link", { name: "Assistir à demonstração" })).toBeNull();
  });

  it("o card com o plano publicado tem o botão Ver o plano, e o check só com o plano validado (issue #2010)", async () => {
    telaLarga();
    const aValidar = demanda("q-20", "Plano a validar", {
      etapa: "planejada",
      tem_vinculo: true,
      apresentacao_url: "https://planos-hsm.vercel.app/2007/",
      plano_validado: false,
    });
    const validado = demanda("q-21", "Plano validado", {
      etapa: "em_desenvolvimento",
      tem_vinculo: true,
      apresentacao_url: "https://planos-hsm.vercel.app/1979/",
      plano_validado: true,
    });
    const semPlano = demanda("q-22", "Pedido sem plano", { etapa: "em_analise", tem_vinculo: true });
    const foraDaPagina = demanda("q-23", "Plano fora da página", {
      etapa: "em_analise",
      tem_vinculo: true,
      apresentacao_url: "https://youtu.be/plano",
    });
    montar((url) =>
      url === LISTA ? { status: 200, corpo: [aValidar, validado, semPlano, foraDaPagina] } : { status: 404, corpo: {} },
    );
    await screen.findByRole("region", { name: "Quadro" });

    const plano = within(colunaDe("Planejada")).getByRole("link", { name: "Ver o plano" });
    expect(plano.getAttribute("href")).toBe("https://planos-hsm.vercel.app/2007/");
    expect(plano.getAttribute("title")).toBe("Ver o plano");
    expect(plano.getAttribute("target")).toBe("_blank");
    expect(plano.getAttribute("rel")).toBe("noopener noreferrer");
    expect(within(colunaDe("Planejada")).getByRole("button", { name: /Plano a validar/ }).contains(plano)).toBe(false);
    expect(plano.querySelector("[data-plano-validado]")).toBeNull();

    const comCheck = within(colunaDe("Em desenvolvimento")).getByRole("link", { name: "Ver o plano, já validado" });
    expect(comCheck.getAttribute("href")).toBe("https://planos-hsm.vercel.app/1979/");
    expect(comCheck.getAttribute("title")).toBe("Ver o plano");
    expect(comCheck.querySelector("[data-plano-validado]")).not.toBeNull();

    expect(within(colunaDe("Em análise")).queryByRole("link", { name: /Ver o plano/ })).toBeNull();
  });

  it("o card com vídeo e plano mostra os dois botões lado a lado, o vídeo no canto (issue #2010)", async () => {
    telaLarga();
    const comOsDois = demanda("q-24", "Vídeo e plano", {
      etapa: "em_producao",
      tem_vinculo: true,
      demonstracao_url: "https://youtu.be/demo",
      apresentacao_url: "https://planos-hsm.vercel.app/2007/",
      classificacao: "melhoria",
    });
    const soOPlano = demanda("q-25", "Só o plano", {
      etapa: "em_producao",
      tem_vinculo: true,
      apresentacao_url: "https://planos-hsm.vercel.app/1932/",
      classificacao: "bug",
    });
    montar((url) => (url === LISTA ? { status: 200, corpo: [comOsDois, soOPlano] } : { status: 404, corpo: {} }));
    await screen.findByRole("region", { name: "Quadro" });

    const entregue = colunaDe("Entregue");
    const card = within(entregue).getByRole("button", { name: /Vídeo e plano/ }).parentElement as HTMLElement;
    const classes = (el: HTMLElement) => el.className.split(/\s+/);
    const video = within(card).getByRole("link", { name: "Assistir à demonstração" });
    const plano = within(card).getByRole("link", { name: "Ver o plano" });
    // O vídeo no canto e o plano ao lado dele, na mesma linha de baixo.
    expect(classes(video)).toEqual(expect.arrayContaining(["bottom-2.5", "right-2.5"]));
    expect(classes(plano)).toEqual(expect.arrayContaining(["bottom-2.5", "right-12"]));
    // Os selos do card abrem espaço para os dois botões.
    expect(classes(within(card).getByText("Melhoria").parentElement as HTMLElement)).toContain("pr-20");

    // Sozinho, o plano fica no canto, no lugar do vídeo.
    const soPlano = within(entregue).getByRole("button", { name: /Só o plano/ }).parentElement as HTMLElement;
    expect(classes(within(soPlano).getByRole("link", { name: "Ver o plano" }))).toContain("right-2.5");
    expect(classes(within(soPlano).getByText("Bug").parentElement as HTMLElement)).toContain("pr-10");
  });

  it("o botão do vídeo tem o brilho, e com prefers-reduced-motion o brilho some", async () => {
    telaLarga();
    const comVideo = demanda("q-12", "Vídeo no card", {
      etapa: "em_producao",
      tem_vinculo: true,
      demonstracao_url: "https://youtu.be/demo",
    });
    montar((url) => (url === LISTA ? { status: 200, corpo: [comVideo] } : { status: 404, corpo: {} }));
    await screen.findByRole("region", { name: "Quadro" });

    const video = within(colunaDe("Entregue")).getByRole("link", { name: "Assistir à demonstração" });
    expect(video.className.split(/\s+/)).toContain("brilho-da-demonstracao");

    const css = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");
    // Fora do pedido de menos movimento, a faixa de luz anda.
    const brilho = css.match(/(?:^|\n)\.brilho-da-demonstracao::after\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(brilho).toMatch(/animation:\s*brilho-da-demonstracao\b/);
    // Com movimento reduzido, a faixa nem aparece.
    const reduzido = css.match(/@media \(prefers-reduced-motion: reduce\) \{([\s\S]*?)\n\}/)?.[1] ?? "";
    const regras = [...reduzido.matchAll(/([^{}]*)\{([^}]*)\}/g)];
    const desliga = regras.find((r) => r[1].split(",").map((s) => s.trim()).includes(".brilho-da-demonstracao::after"));
    expect(desliga?.[2]).toMatch(/display:\s*none/);
  });

  it("o Ampliar do painel leva a Demanda à largura toda, e Voltar ao quadro volta (issue #1643)", async () => {
    telaLarga();
    montar((url) => {
      if (url === LISTA) return { status: 200, corpo: NO_QUADRO };
      return { status: 404, corpo: {} };
    });
    await screen.findByRole("region", { name: "Quadro" });

    const card = within(colunaDe("Em análise")).getByRole("button", { name: /Aviso da ata por e-mail/ });
    // Botão de verdade: o navegador transforma o Enter (e o Espaço) em clique.
    expect(card.tagName).toBe("BUTTON");
    fireEvent.click(card);
    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });
    fireEvent.click(within(painel).getByRole("button", { name: AMPLIAR }));

    const aberto = await screen.findByRole("region", { name: "Pedido na tela" });
    expect(screen.queryByRole("complementary", { name: "Pedido aberto" })).toBeNull();
    expect(await within(aberto).findByRole("heading", { level: 2, name: "Aviso da ata por e-mail" })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Quadro" })).toBeNull();
    expect(screen.getByRole("region", { name: "Filtros da lista" }).className).toMatch(/(^|\s)hidden(\s|$)/);
    // Na largura toda, como o Ampliar: a Conversa da Demanda na coluna da direita, sem Ampliar de novo.
    expect(within(aberto).queryByRole("button", { name: AMPLIAR })).toBeNull();
    expect(demandaDaUrl()).toBe("q-3");

    const voltar = screen.getByRole("button", { name: VOLTAR_AO_QUADRO });
    expect(voltar.className).not.toMatch(/(^|\s)md:hidden(\s|$)/);
    fireEvent.click(voltar);

    expect(await screen.findByRole("region", { name: "Quadro" })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Pedido na tela" })).toBeNull();
    expect(screen.getByRole("region", { name: "Filtros da lista" }).className).not.toMatch(/(^|\s)hidden(\s|$)/);
    expect(demandaDaUrl()).toBeNull();
  });

  it("abaixo de 1280px a lista de antes aparece, com o filtro de Etapa", async () => {
    telaLarga(false);
    montar((url) => (url === LISTA ? { status: 200, corpo: NO_QUADRO } : { status: 404, corpo: {} }));

    expect(await within(lista()).findByText("Conversa que ficou no meio")).toBeTruthy();
    expect(within(lista()).getAllByRole("listitem")).toHaveLength(NO_QUADRO.length);
    expect(screen.queryByRole("region", { name: "Quadro" })).toBeNull();
    expect(screen.getByText("Etapa")).toBeTruthy();
    // Nenhum botão de pedido novo: o pedido nasce no GitHub (issue #2279).
    expect(screen.queryByRole("button", { name: /Nova conversa|Novo pedido/ })).toBeNull();
  });

  describe("a barra do Quadro (issue #1644, ADR 0090, decisões 2 e 8)", () => {
    const EU = "/api/admin/tecnologia/eu";
    const filtros = () => screen.getByRole("region", { name: "Filtros da lista" });
    const interruptor = () => within(filtros()).getByRole("switch", { name: MOSTRAR_AS_QUE_NAO_SERAO_FEITAS });
    const comNaoSeraFeita = [
      ...NO_QUADRO,
      demanda("q-6", "Relatório que ninguém usa", { etapa: "nao_sera_feita", tem_vinculo: true, numero: 36 }),
    ];

    it("na tela larga a barra não tem o campo de Etapa", async () => {
      telaLarga();
      montar((url) => (url === LISTA ? { status: 200, corpo: NO_QUADRO } : { status: 404, corpo: {} }));
      await screen.findByRole("region", { name: "Quadro" });

      expect(within(filtros()).getByRole("combobox", { name: "Tipo" })).toBeTruthy();
      expect(within(filtros()).queryByRole("combobox", { name: "Etapa" })).toBeNull();
    });

    it("o interruptor Mostrar as que não serão feitas põe a coluna Não será feita no fim, e a tira", async () => {
      telaLarga();
      montar((url) => (url === LISTA ? { status: 200, corpo: comNaoSeraFeita } : { status: 404, corpo: {} }));
      await screen.findByRole("region", { name: "Quadro" });
      const colunas = () =>
        within(quadro())
          .getAllByRole("heading", { level: 3 })
          .map((h) => h.firstChild?.textContent);

      expect(interruptor().getAttribute("aria-checked")).toBe("false");
      expect(colunas()).not.toContain("Não será feita");
      expect(within(quadro()).queryByText("Relatório que ninguém usa")).toBeNull();

      fireEvent.click(interruptor());

      expect(interruptor().getAttribute("aria-checked")).toBe("true");
      expect(colunas().at(-1)).toBe("Não será feita");
      expect(within(colunaDe("Não será feita")).getByText("Relatório que ninguém usa")).toBeTruthy();

      fireEvent.click(interruptor());

      expect(colunas()).not.toContain("Não será feita");
    });

    it("Limpar filtros aparece com o interruptor ligado e o desliga, sem mexer no recorte", async () => {
      telaLarga();
      montar((url) => {
        if (url === EU) return { status: 200, corpo: { desenvolvedor: true } };
        if (url.startsWith(LISTA)) return { status: 200, corpo: comNaoSeraFeita };
        return { status: 404, corpo: {} };
      });
      const recorte = await within(await screen.findByRole("region", { name: "Filtros da lista" })).findByRole(
        "group",
        { name: "Recorte" },
      );
      fireEvent.click(within(recorte).getByRole("button", { name: "Todas" }));
      await screen.findByRole("region", { name: "Quadro" });
      expect(within(filtros()).queryByRole("button", { name: "Limpar filtros" })).toBeNull();

      fireEvent.click(interruptor());
      expect(colunaDe("Não será feita")).toBeTruthy();

      fireEvent.click(within(filtros()).getByRole("button", { name: "Limpar filtros" }));

      expect(interruptor().getAttribute("aria-checked")).toBe("false");
      expect(within(quadro()).queryByRole("region", { name: "Não será feita" })).toBeNull();
      expect(within(recorte).getByRole("button", { name: "Todas" }).getAttribute("aria-pressed")).toBe("true");
      expect(within(filtros()).queryByRole("button", { name: "Limpar filtros" })).toBeNull();
    });
  });

  it("o link do sino abre o Quadro com o painel da Demanda certa (issue #1643)", async () => {
    telaLarga();
    montar(
      (url) => {
        if (url === LISTA) return { status: 200, corpo: [SEM_CARD, COM_VINCULO] };
        return { status: 404, corpo: {} };
      },
      "d-2",
    );

    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });
    expect(await within(painel).findByText("Agora o aviso da ata chega por e-mail.")).toBeTruthy();
    expect(within(painel).getByRole("heading", { level: 2, name: "Aviso quando a ata sair" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Quadro" })).toBeTruthy();
  });
});

describe("O card do Quadro abre num painel à direita (issue #1643, ADR 0090, decisão 5)", () => {
  /** A tela a partir de 1280px: o `matchMedia` que o jsdom não tem, dublado. */
  function telaLarga() {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((consulta: string) => ({
        matches: consulta === "(min-width: 1280px)",
        media: consulta,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
  }

  const ACOMPANHADA = demanda("p-1", "Aviso da ata por e-mail", {
    etapa: "em_analise",
    tem_vinculo: true,
    numero: 39,
    autor: "Felipe Malafaia",
    o_que_muda: "O aviso da ata chega por e-mail.",
  });
  const REGISTRADA = demanda("p-2", "Escala some no domingo", { numero: 40 });

  function comOQuadro(lidas: Demanda[] = [ACOMPANHADA, REGISTRADA], demandaInicial: string | null = null) {
    telaLarga();
    return montar((url) => {
      if (url === LISTA) return { status: 200, corpo: lidas };
      if (url.endsWith("/conversa")) return { status: 200, corpo: { mensagens: [], mencionaveis: [] } };
      return { status: 404, corpo: {} };
    }, demandaInicial);
  }

  const quadro = () => screen.getByRole("region", { name: "Quadro" });
  const cardDe = (titulo: RegExp) => within(quadro()).getByRole("button", { name: titulo });

  it("o clique num card abre o painel só com o Documento, sem Conversa, Revisar nem Apagar, com o Quadro à vista (issue #2279)", async () => {
    comOQuadro();
    await screen.findByRole("region", { name: "Quadro" });

    fireEvent.click(cardDe(/Aviso da ata por e-mail/));

    const aberto = await screen.findByRole("complementary", { name: "Pedido aberto" });
    expect(await within(aberto).findByRole("heading", { level: 2, name: "Aviso da ata por e-mail" })).toBeTruthy();
    expect(within(aberto).getByRole("region", { name: "Documento do card" })).toBeTruthy();
    expect(within(aberto).getByText("O aviso da ata chega por e-mail.")).toBeTruthy();
    // Só para ler (ADR 0113, decisão 7): nada que agia ficou no painel.
    expect(within(aberto).queryByRole("region", { name: "Conversa da Demanda" })).toBeNull();
    expect(within(aberto).queryByRole("textbox")).toBeNull();
    for (const nome of [/Conversar/, /Revisar/, /Apagar/, /Reenviar/, /Designar de novo/]) {
      expect(within(aberto).queryByRole("button", { name: nome })).toBeNull();
    }
    // O painel não é modal: o Quadro segue na página, atrás dele.
    expect(quadro()).toBeTruthy();
    expect(aberto.getAttribute("aria-modal")).toBeNull();
    expect(screen.getByRole("region", { name: "Filtros da lista" }).className).not.toMatch(/(^|\s)hidden(\s|$)/);
  });

  it("a URL muda ao abrir o painel, e abrir a aba com essa URL mostra o Quadro com o painel do card", async () => {
    comOQuadro();
    await screen.findByRole("region", { name: "Quadro" });
    expect(demandaDaUrl()).toBeNull();

    fireEvent.click(cardDe(/Aviso da ata por e-mail/));
    await screen.findByRole("complementary", { name: "Pedido aberto" });
    expect(demandaDaUrl()).toBe("p-1");

    // Outra aba com o mesmo endereço: a tela nasce só com o que está nele.
    cleanup();
    comOQuadro(undefined, demandaDaUrl());

    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });
    expect(await within(painel).findByRole("heading", { level: 2, name: "Aviso da ata por e-mail" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Quadro" })).toBeTruthy();
  });

  it("o painel nasce no body, fora do módulo, para se prender à janela mesmo sob o fade-in-up", async () => {
    comOQuadro();
    const quadroNaTela = await screen.findByRole("region", { name: "Quadro" });
    fireEvent.click(cardDe(/Aviso da ata por e-mail/));
    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });

    // O wrapper .animate-fade-in-up do módulo deixa um transform aplicado, e um ancestral
    // com transform vira o bloco de contenção do `fixed`; o jsdom não calcula layout,
    // então a prova é o painel ser filho direto do body.
    expect(painel.parentElement).toBe(document.body);
    expect(quadroNaTela.contains(painel)).toBe(false);
  });

  it("o painel começa logo abaixo da barra do topo e fica sob ela, para Ampliar e Fechar não sumirem atrás da barra (issue #1686)", async () => {
    // A altura e a camada da barra saem do próprio Header: se ela mudar, o teste cobra o painel.
    const header = readFileSync(resolve(process.cwd(), "src/components/layout/Header.tsx"), "utf8");
    const classesDaBarra = (header.match(/<header className="([^"]+)"/)?.[1] ?? "").split(/\s+/);
    const altura = classesDaBarra.find((c) => /^h-\d+$/.test(c))?.slice(2);
    const camadaDaBarra = Number(classesDaBarra.find((c) => /^z-\[\d+\]$/.test(c))?.slice(3, -1));
    expect(altura).toBeTruthy();
    expect(camadaDaBarra).toBeGreaterThan(0);

    comOQuadro();
    await screen.findByRole("region", { name: "Quadro" });
    fireEvent.click(cardDe(/Aviso da ata por e-mail/));
    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });
    const classes = painel.className.split(/\s+/);

    expect(classes).toContain("fixed");
    expect(classes).toContain(`top-${altura}`);
    expect(classes).toContain("bottom-0");
    expect(classes.filter((c) => /^(inset-0|inset-y-\S+|top-\S+)$/.test(c))).toEqual([`top-${altura}`]);
    // Abaixo da camada da barra: o sino e o menu do usuário abrem por cima do painel.
    const camadaDoPainel = Number(classes.find((c) => /^z-(\d+|\[\d+\])$/.test(c))?.replace(/^z-\[?|\]$/g, ""));
    expect(camadaDoPainel).toBeLessThan(camadaDaBarra);
    // Os dois botões da linha do topo seguem no painel e funcionam pelo clique.
    expect(within(painel).getByRole("button", { name: AMPLIAR })).toBeTruthy();
    fireEvent.click(within(painel).getByRole("button", { name: FECHAR_O_PAINEL }));
    expect(screen.queryByRole("complementary", { name: "Pedido aberto" })).toBeNull();
  });

  it("o botão de fechar fecha o painel e devolve o foco ao card", async () => {
    comOQuadro();
    await screen.findByRole("region", { name: "Quadro" });
    fireEvent.click(cardDe(/Aviso da ata por e-mail/));
    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });

    fireEvent.click(within(painel).getByRole("button", { name: FECHAR_O_PAINEL }));

    expect(screen.queryByRole("complementary", { name: "Pedido aberto" })).toBeNull();
    expect(document.activeElement).toBe(cardDe(/Aviso da ata por e-mail/));
    expect(demandaDaUrl()).toBeNull();
  });

  it("Esc fecha o painel e devolve o foco ao card", async () => {
    comOQuadro();
    await screen.findByRole("region", { name: "Quadro" });
    fireEvent.click(cardDe(/Aviso da ata por e-mail/));
    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });
    await within(painel).findByRole("region", { name: "Documento do card" });

    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });

    expect(screen.queryByRole("complementary", { name: "Pedido aberto" })).toBeNull();
    expect(document.activeElement).toBe(cardDe(/Aviso da ata por e-mail/));
  });

  it("o card da Ana, como a lista o serve, abre com o link no repositório da Ana (issue #1714)", async () => {
    const DA_ANA = demanda("a-12", "Ana: responder o preparo do exame", {
      etapa: "planejada",
      origem: "vitta",
      tem_vinculo: true,
      issue_numero: 12,
      issue_url: "https://github.com/Vitta-Share/programa-ana/issues/12",
    });
    telaLarga();
    montar((url) => {
      if (url === "/api/admin/tecnologia/eu") return { status: 200, corpo: { desenvolvedor: true } };
      if (url === `${LISTA}?filtro=para_mim`) return { status: 200, corpo: [DA_ANA] };
      if (url.endsWith("/conversa")) return { status: 200, corpo: { mensagens: [], mencionaveis: [] } };
      return { status: 404, corpo: {} };
    });
    await within(await screen.findByRole("region", { name: "Quadro" })).findByText("Ana: responder o preparo do exame");

    fireEvent.click(cardDe(/Ana: responder o preparo/));
    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });
    await within(painel).findByRole("heading", { level: 2, name: "Ana: responder o preparo do exame" });

    for (const nome of [/Apagar/, /Revisar/]) {
      expect(within(painel).queryByRole("button", { name: nome })).toBeNull();
    }
    const link = within(painel).getByRole("link", { name: "#12" });
    expect(link.getAttribute("href")).toBe("https://github.com/Vitta-Share/programa-ana/issues/12");
  });

  it("com prefers-reduced-motion, o painel abre sem animação", async () => {
    comOQuadro();
    await screen.findByRole("region", { name: "Quadro" });
    fireEvent.click(cardDe(/Aviso da ata por e-mail/));
    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });

    // O painel entra deslizando só pelas animações que o globals.css desliga com
    // o pedido de menos movimento.
    const animacoes = painel.className.split(/\s+/).filter((c) => /(^|:)animate-/.test(c));
    expect(animacoes).toEqual(["animate-fade-in-right"]);
    const css = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");
    const reduzido = css.match(/@media \(prefers-reduced-motion: reduce\) \{([\s\S]*?)\n\}/)?.[1] ?? "";
    const regra = reduzido.match(/([^{}]*)\{([^}]*)\}/)!;
    expect(regra[1].split(",").map((s) => s.trim())).toContain(".animate-fade-in-right");
    expect(regra[2]).toMatch(/animation:\s*none/);
  });
});

describe("O filtro Projeto e o selo (issue #1715, ADR 0093, decisão 8)", () => {
  /** A tela a partir de 1280px: o `matchMedia` que o jsdom não tem, dublado. */
  function telaLarga(larga = true) {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((consulta: string) => ({
        matches: larga && consulta === "(min-width: 1280px)",
        media: consulta,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
  }

  const quadro = () => screen.getByRole("region", { name: "Quadro" });
  const filtros = () => screen.getByRole("region", { name: "Filtros da lista" });

  const DO_APP = demanda("p-1", "Aviso quando a ata sair", {
    etapa: "em_analise",
    tem_vinculo: true,
    numero: 51,
    projeto: "hospital",
  });
  const DA_ANA = demanda("p-2", "Ana responde o horário da visita", {
    etapa: "em_analise",
    tem_vinculo: true,
    numero: 52,
    projeto: "ana",
  });

  /** O servidor que filtra pelo `projeto` como a rota de verdade (teste de rota no backend). */
  function servidor(url: string): Resposta {
    if (url === LISTA) return { status: 200, corpo: [DO_APP, DA_ANA] };
    if (url === `${LISTA}?projeto=ana`) return { status: 200, corpo: [DA_ANA] };
    if (url === `${LISTA}?projeto=hospital`) return { status: 200, corpo: [DO_APP] };
    return { status: 404, corpo: {} };
  }

  it("com Ana escolhido o Quadro mostra só as Demandas da Ana, e com Todos as duas", async () => {
    telaLarga();
    const chamadas = montar(servidor);
    await within(await screen.findByRole("region", { name: "Quadro" })).findByText("Aviso quando a ata sair");
    expect(within(filtros()).getByRole("combobox", { name: "Projeto" }).textContent).toBe("Todos");
    expect(within(quadro()).getByText("Ana responde o horário da visita")).toBeTruthy();

    escolher("Projeto", "Ana");

    await waitFor(() => expect(within(quadro()).queryByText("Aviso quando a ata sair")).toBeNull());
    expect(chamadas.at(-1)?.url).toBe(`${LISTA}?projeto=ana`);
    expect(within(quadro()).getByText("Ana responde o horário da visita")).toBeTruthy();

    escolher("Projeto", "Todos");

    expect(await within(quadro()).findByText("Aviso quando a ata sair")).toBeTruthy();
    expect(chamadas.at(-1)?.url).toBe(LISTA);
    expect(within(quadro()).getByText("Ana responde o horário da visita")).toBeTruthy();
  });

  it("Limpar filtros volta o Projeto para Todos", async () => {
    telaLarga();
    const chamadas = montar(servidor);
    await screen.findByRole("region", { name: "Quadro" });

    escolher("Projeto", "Aplicativo do Hospital");
    await waitFor(() => expect(chamadas.at(-1)?.url).toBe(`${LISTA}?projeto=hospital`));
    fireEvent.click(within(filtros()).getByRole("button", { name: "Limpar filtros" }));

    await waitFor(() => expect(chamadas.at(-1)?.url).toBe(LISTA));
    expect(within(filtros()).getByRole("combobox", { name: "Projeto" }).textContent).toBe("Todos");
  });

  it("o card do Quadro leva o selo do projeto", async () => {
    telaLarga();
    montar(servidor);
    await screen.findByRole("region", { name: "Quadro" });

    const doApp = await within(quadro()).findByRole("button", { name: /Aviso quando a ata sair/ });
    const daAna = within(quadro()).getByRole("button", { name: /Ana responde o horário da visita/ });
    expect(within(doApp).getByText("Aplicativo do Hospital")).toBeTruthy();
    expect(within(daAna).getByText("Ana")).toBeTruthy();
    expect(within(daAna).queryByText("Aplicativo do Hospital")).toBeNull();
  });

  it("a linha da lista do celular leva o selo do projeto, e o filtro vale para ela", async () => {
    telaLarga(false);
    const chamadas = montar(servidor);
    await within(lista()).findByText("Aviso quando a ata sair");

    const itens = within(lista()).getAllByRole("listitem");
    expect(within(itens[0]).getByText("Aplicativo do Hospital")).toBeTruthy();
    expect(within(itens[1]).getByText("Ana")).toBeTruthy();

    escolher("Projeto", "Ana");
    await waitFor(() => expect(chamadas.at(-1)?.url).toBe(`${LISTA}?projeto=ana`));
    await waitFor(() => expect(within(lista()).queryByText("Aviso quando a ata sair")).toBeNull());
  });

  describe("o projeto novo da Vitta (issue #1967)", () => {
    const PROJETOS = "/api/admin/tecnologia/projetos";
    const DO_PEDRO_OS = demanda("p-3", "Perguntas do PedroOS no app", {
      etapa: "registrada",
      tem_vinculo: true,
      origem: "vitta",
      projeto: "os",
      projeto_nome: "PedroOS",
      raiz_url: "https://github.com/Vitta-Share/os/issues/915",
    });

    /** O servidor com a lista de projetos que a rota `/projetos` devolve. */
    function comOPedroOS(url: string): Resposta {
      if (url === PROJETOS)
        return {
          status: 200,
          corpo: [
            { valor: "hospital", nome: "Aplicativo do Hospital" },
            { valor: "ana", nome: "Ana" },
            { valor: "os", nome: "PedroOS" },
          ],
        };
      if (url === LISTA) return { status: 200, corpo: [DO_APP, DA_ANA, DO_PEDRO_OS] };
      if (url === `${LISTA}?projeto=os`) return { status: 200, corpo: [DO_PEDRO_OS] };
      return servidor(url);
    }

    it("o filtro Projeto lista o projeto novo pelo nome e filtra por ele", async () => {
      telaLarga();
      const chamadas = montar(comOPedroOS);
      await within(await screen.findByRole("region", { name: "Quadro" })).findByText("Aviso quando a ata sair");

      await waitFor(() => expect(chamadas.map((c) => c.url)).toContain(PROJETOS));
      escolher("Projeto", "PedroOS");

      await waitFor(() => expect(chamadas.at(-1)?.url).toBe(`${LISTA}?projeto=os`));
      await waitFor(() => expect(within(quadro()).queryByText("Aviso quando a ata sair")).toBeNull());
      expect(within(quadro()).getByText("Perguntas do PedroOS no app")).toBeTruthy();
    });

    it("o card do projeto novo leva o selo com o nome dele", async () => {
      telaLarga();
      montar(comOPedroOS);
      await screen.findByRole("region", { name: "Quadro" });

      const doOS = await within(quadro()).findByRole("button", { name: /Perguntas do PedroOS no app/ });
      expect(within(doOS).getByText("PedroOS")).toBeTruthy();
    });

    it("sem a lista do servidor, o filtro fica com os dois projetos de sempre", async () => {
      telaLarga();
      montar(servidor);
      await screen.findByRole("region", { name: "Quadro" });

      fireEvent.click(within(filtros()).getByRole("combobox", { name: "Projeto" }));
      expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
        "Todos",
        "Aplicativo do Hospital",
        "Ana",
      ]);
    });
  });
});

