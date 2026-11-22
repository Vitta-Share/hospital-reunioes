/**
 * @vitest-environment jsdom
 */

/**
 * A Implantação no card (issue #2209, PRD #2205, ADR 0111, decisão 5).
 *
 * O Documento do card ganha a seção Implantação, logo depois de O que muda,
 * com cada Pedido de implantação, quem recebeu e a situação. O card do Quadro
 * mostra o selo "Implantação X de Y" enquanto falta algum Pedido, e o esconde
 * com todos concluídos. Demanda sem Pedido de implantação não muda. A Etapa
 * é a do GitHub: a Demanda Em produção com implantação aberta fica na coluna
 * Entregue, com o selo.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DocumentoDoCard, TITULO_DOCUMENTO, TITULO_IMPLANTACAO, TITULO_O_QUE_MUDA, TITULO_PARTES } from "./DocumentoDoCard";
import { QuadroDaTecnologia } from "./QuadroDaTecnologia";
import type { Demanda, ImplantacaoDaDemanda } from "./demandas";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const TESTE = "testar o anonimato do Canal de Conduta";
const ABERTURA = "abrir o Canal de Conduta para todos";
const TREINAMENTO = "treinar a recepção no Canal de Conduta";

const UM_DE_TRES: ImplantacaoDaDemanda = {
  feitos: 1,
  total: 3,
  pedidos: [
    { titulo: TESTE, destinatario: "Diretora Clínica", situacao: "feito", espera: null },
    { titulo: ABERTURA, destinatario: "Diretor Geral", situacao: "esperando", espera: "Espera o teste do Canal" },
    { titulo: TREINAMENTO, destinatario: "Pedro Rezende", situacao: "aberto", espera: null },
  ],
};

const TODOS_FEITOS: ImplantacaoDaDemanda = {
  feitos: 2,
  total: 2,
  pedidos: [
    { titulo: TESTE, destinatario: "Diretora Clínica", situacao: "feito", espera: null },
    { titulo: ABERTURA, destinatario: "Diretor Geral", situacao: "feito", espera: null },
  ],
};

function demanda(extra: Partial<Demanda> = {}): Demanda {
  return {
    id: "d-1",
    numero: 42,
    titulo: "O Canal de Conduta",
    criado_em: new Date().toISOString(),
    etapa: "em_producao",
    versao: "v0.390.0",
    em_producao_em: new Date().toISOString(),
    partes_entregues: 2,
    partes_total: 2,
    o_que_muda: "**O que muda:** o hospital ganha o Canal de Conduta.\n\n- Relato sem se identificar.",
    partes: [{ o_que_muda: "O relato anônimo.", situacao: "entregue", fechada_em: "2026-11-20T14:00:00Z" }],
    ...extra,
  };
}

function documento(): HTMLElement {
  return screen.getByRole("region", { name: TITULO_DOCUMENTO });
}

function quadro(demandas: Demanda[]) {
  return render(<QuadroDaTecnologia demandas={demandas} comNaoSeraFeita={false} onAbrir={vi.fn()} />);
}

function cardDoQuadro(): HTMLElement {
  return screen.getByRole("button", { name: "Demanda 42: O Canal de Conduta" });
}

describe("A seção Implantação do Documento do card", () => {
  it("mostra cada Pedido de implantação, o Destinatário e a situação, logo depois de O que muda", () => {
    render(<DocumentoDoCard demanda={demanda({ implantacao: UM_DE_TRES })} />);

    const secao = within(documento()).getByRole("region", { name: TITULO_IMPLANTACAO });
    expect(within(secao).getByText("1 de 3 feitos")).toBeTruthy();
    const itens = within(secao).getAllByRole("listitem");
    expect(itens.map((item) => within(item).getByText(/Canal de Conduta/).textContent)).toEqual([
      TESTE,
      ABERTURA,
      TREINAMENTO,
    ]);
    expect(within(itens[0]).getByText("Com Diretora Clínica")).toBeTruthy();
    expect(within(itens[0]).getByText("Feito")).toBeTruthy();
    expect(within(itens[1]).getByText("Com Diretor Geral")).toBeTruthy();
    expect(within(itens[1]).getByText("Esperando")).toBeTruthy();
    expect(within(itens[1]).getByText("Espera o teste do Canal")).toBeTruthy();
    expect(within(itens[2]).getByText("Com Pedro Rezende")).toBeTruthy();
    expect(within(itens[2]).getByText("Aberto")).toBeTruthy();

    const oQueMuda = within(documento()).getByRole("heading", { name: TITULO_O_QUE_MUDA });
    const partes = within(documento()).getByRole("heading", { name: TITULO_PARTES });
    expect(oQueMuda.compareDocumentPosition(secao) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(secao.compareDocumentPosition(partes) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("a Demanda sem Pedido de implantação não ganha a seção", () => {
    render(<DocumentoDoCard demanda={demanda({ implantacao: null })} />);

    expect(within(documento()).getByRole("heading", { name: TITULO_O_QUE_MUDA })).toBeTruthy();
    expect(within(documento()).queryByRole("region", { name: TITULO_IMPLANTACAO })).toBeNull();
    expect(within(documento()).queryByText(/Implantação/)).toBeNull();
  });
});

describe("O selo Implantação no Quadro", () => {
  it("aparece com Pedido de implantação aberto", () => {
    quadro([demanda({ implantacao: UM_DE_TRES })]);

    expect(within(cardDoQuadro()).getByText("Implantação 1 de 3")).toBeTruthy();
  });

  it("some com todos os Pedidos de implantação concluídos", () => {
    quadro([demanda({ implantacao: TODOS_FEITOS })]);

    expect(within(cardDoQuadro()).getByText("v0.390.0")).toBeTruthy();
    expect(within(cardDoQuadro()).queryByText(/Implantação/)).toBeNull();
  });

  it("a Demanda sem Pedido de implantação não ganha selo", () => {
    quadro([demanda({ implantacao: null })]);

    expect(within(cardDoQuadro()).getByText("v0.390.0")).toBeTruthy();
    expect(within(cardDoQuadro()).queryByText(/Implantação/)).toBeNull();
  });

  it("a Demanda Em produção com implantação aberta fica em Entregue, com a versão e o selo", () => {
    quadro([demanda({ implantacao: UM_DE_TRES })]);

    const entregue = screen.getByRole("region", { name: "Entregue" });
    const card = within(entregue).getByRole("button", { name: "Demanda 42: O Canal de Conduta" });
    expect(within(card).getByText("v0.390.0")).toBeTruthy();
    expect(within(card).getByText("Implantação 1 de 3")).toBeTruthy();
  });
});
