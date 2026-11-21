/**
 * @vitest-environment jsdom
 */

/**
 * O Guia da faturista na Mesa de trabalho (issue #1952, PRD #1933; antes #1121).
 *
 * A tela não decide nada: quem marca, recusa e conclui é o servidor. O que se
 * trava aqui é o que a faturista vê (o cabeçalho, a faixa dos números, a lista
 * por dia e setor, o Item da vez, o rodapé) e o que cada clique dispara (a URL
 * e o corpo).
 *
 * Todo teste de ausência tem irmão de presença no mesmo estado: afirmar que a
 * linha Validar não tem botão é vazio se nenhuma linha tivesse.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LegendasProvider } from "@/components/ui/Legenda";
import { ToastProvider } from "@/components/ui/Toast";
import { caixaDoDado } from "@/lib/testes/caixaDoDado";
import type { Guia, LinhaGuia } from "@/lib/contas-medicas/guia";

import GuiaPage from "./page";

const CONTA = "11111111-1111-1111-1111-111111111111";
const PROXIMA = "22222222-2222-2222-2222-222222222222";

const navegacao = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useParams: () => ({ contaId: "11111111-1111-1111-1111-111111111111" }),
  useRouter: () => ({ push: navegacao.push }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

function linha(campos: Partial<LinhaGuia>): LinhaGuia {
  return {
    id: "l-luva",
    acao: "INCLUIR",
    data: "2026-10-03",
    data_fim: "2026-10-05",
    setor: "CTI",
    codigo: "70012345",
    descricao: "Luva de procedimento",
    quantidade_lancada: 0,
    quantidade_devida: 180,
    preco_lancado: null,
    preco_tabela: 0.38,
    valor_diferenca: 68.4,
    regra_codigo: "ASSIM-INS-03",
    motivo: "3 diárias de CTI pagas",
    evidencia_pagina: 2,
    evidencia_trecho: "Luva de procedimento 60 por dia",
    nivel_evidencia: "REGISTRADO",
    confianca: "ALTA",
    estado: "ABERTA",
    motivo_nao_procede: null,
    texto_nao_procede: null,
    nao_conferido: false,
    ...campos,
  };
}

function guia(campos: Partial<Guia> = {}): Guia {
  return {
    cabecalho: {
      numero_atendimento: "31245",
      paciente_rotulo: "Maria S.",
      numero_conta: "48811",
      operadora: "ASSIM",
      coluna_preco: "CARIOCA",
      periodo_inicio: "2026-10-03",
      periodo_fim: "2026-10-07",
      situacao: "EM_CORRECAO",
      parecer_parcial: false,
      faltantes: [],
    },
    numeros: {
      nota_entrada: 74,
      valor_a_ajustar: 584.6,
      itens_a_ajustar: 9,
      valor_em_validacao: 1212,
      itens_feitos: 0,
      itens_total: 3,
      itens_sem_marcacao: 3,
    },
    grupos: [
      {
        data: "2026-10-03",
        setor: "CTI",
        linhas: [
          linha({}),
          linha({
            id: "l-lavagem",
            acao: "AJUSTAR_QUANTIDADE",
            data_fim: null,
            codigo: "80055501",
            descricao: "Lavagem de sonda",
            quantidade_lancada: 12,
            quantidade_devida: 9,
            valor_diferenca: -4.17,
            nao_conferido: true,
            confianca: "BAIXA",
          }),
        ],
      },
      {
        data: "2026-10-04",
        setor: "ENFERMARIA",
        linhas: [
          linha({
            id: "l-fita",
            data: "2026-10-04",
            data_fim: null,
            setor: "ENFERMARIA",
            codigo: "80077702",
            descricao: "Fita de glicemia",
            quantidade_devida: 4,
            valor_diferenca: 36,
          }),
          linha({
            id: "l-unidade",
            acao: "VALIDAR",
            data: "2026-10-04",
            data_fim: null,
            setor: "ENFERMARIA",
            codigo: "90011122",
            descricao: "Dieta enteral",
            valor_diferenca: 1212,
            motivo: "A unidade do preço ainda está pendente",
            estado: "EM_VALIDACAO",
          }),
        ],
      },
    ],
    ...campos,
  };
}

let chamadas: { url: string; metodo: string; corpo: unknown }[] = [];
let respostaDoGuia: Guia;
let respostaDaConclusao: Record<string, unknown>;

beforeEach(() => {
  chamadas = [];
  respostaDoGuia = guia();
  respostaDaConclusao = { situacao: "CONCLUIDA_COM_PENDENCIA", pendencias: 3, proxima_conta_id: PROXIMA };
  navegacao.push.mockReset();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const metodo = init?.method ?? "GET";
      const corpoEnviado =
        init?.body instanceof FormData ? init.body : init?.body ? JSON.parse(String(init.body)) : undefined;
      chamadas.push({ url, metodo, corpo: corpoEnviado });
      const corpo = url.endsWith("/concluir")
        ? respostaDaConclusao
        : url.endsWith("/reenvio")
          ? { nota_saida: 86, corrigidas: 2, ainda_na_conta: 1, linhas: {} }
        : metodo === "GET"
          ? respostaDoGuia
          : { ok: true };
      return new Response(JSON.stringify(corpo), { status: 200 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function abrir(legendasLigadas = true) {
  render(
    <LegendasProvider chave="teste-legendas" ligadasIniciais={legendasLigadas}>
      <ToastProvider>
        <GuiaPage />
      </ToastProvider>
    </LegendasProvider>,
  );
  await screen.findByRole("heading", { level: 1, name: "31245 Maria S." });
}

/** A frase da dica do elemento, aberta pelo teclado. */
function dicaDe(elemento: HTMLElement): string {
  fireEvent.focus(elemento);
  const texto = screen.getByRole("tooltip").textContent ?? "";
  fireEvent.blur(elemento);
  return texto;
}

function aLista() {
  return screen.getByRole("region", { name: "Itens da conta" });
}

function oItem() {
  return screen.getByRole("region", { name: "Item da vez" });
}

/** A Linha na lista, pelo nome do item. */
function naLista(nome: string) {
  return within(aLista()).getByRole("button", { name: new RegExp(nome) });
}

describe("o cabeçalho da conta", () => {
  it("mostra o atendimento grande e o rótulo, sem a palavra Atendimento, com operadora, coluna, período e situação", async () => {
    await abrir();

    const titulo = screen.getByRole("heading", { level: 1 });
    expect(titulo.textContent).not.toContain("Atendimento");
    expect(within(titulo).getByText("31245").className).toContain("text-3xl");
    expect(caixaDoDado(within(titulo).getByText("Maria S."))).toBe("normal-case");
    expect(screen.getByText("conta 48811 · ASSIM · coluna Carioca · parcial de 03/10 a 07/10")).toBeTruthy();
    expect(screen.getByText("Em correção")).toBeTruthy();
  });

  it("Devolver à fila e Reanalisar continuam, cada um com a dica", async () => {
    respostaDoGuia = guia({ pode_reanalisar: true });
    await abrir();

    expect(dicaDe(screen.getByRole("button", { name: "Devolver à fila" }))).toBe(
      "A conta volta para a Fila, livre, com as marcações que você já fez.",
    );
    expect(dicaDe(screen.getByRole("button", { name: "Reanalisar" }))).toBe(
      "A conta volta para a análise com a memória e as tabelas de agora. As linhas já marcadas ficam como estão.",
    );
  });

  it("a dica de Devolver à fila e de Reanalisar abre para a esquerda, sem passar da borda direita", async () => {
    // Os botões ficam colados na borda direita (`ml-auto`) e a raiz do Guia
    // corta o que passa dela (`overflow-x-clip`): a dica presa pela esquerda
    // do botão, com até 256 px, sairia cortada no fim de cada linha.
    respostaDoGuia = guia({ pode_reanalisar: true });
    await abrir();

    for (const nome of ["Devolver à fila", "Reanalisar"]) {
      const botao = screen.getByRole("button", { name: nome });
      fireEvent.focus(botao);
      const classes = screen.getByRole("tooltip").className.split(" ");
      expect(classes).toContain("right-0");
      expect(classes).not.toContain("left-0");
      fireEvent.blur(botao);
    }
  });

  it("pede o guia da conta da URL, com o token", async () => {
    await abrir();

    expect(chamadas[0]).toEqual({ url: `/api/contas-medicas/contas/${CONTA}/guia`, metodo: "GET", corpo: undefined });
  });
});

describe("os avisos acima da Mesa", () => {
  it("o parecer parcial e a resposta da Validação vêm antes da Mesa de trabalho", async () => {
    respostaDoGuia = guia({
      cabecalho: { ...guia().cabecalho, parecer_parcial: true, faltantes: ["Balanço hídrico"] },
      respostas: [
        { titulo: "Observações", regra_codigo: "ALFA-PRI-07", resposta: "Vem no pacote.", decidido_em: null },
      ],
    });
    await abrir();

    const mesa = screen.getByRole("region", { name: "Mesa de trabalho" });
    const parcial = screen.getByRole("note", { name: "Parecer parcial" });
    const resposta = screen.getByRole("note", { name: "Resposta da Validação" });
    expect(parcial.textContent).toContain("PARECER PARCIAL");
    expect(parcial.textContent).toContain("Balanço hídrico");
    expect(resposta.textContent).toContain("Vem no pacote.");
    for (const aviso of [parcial, resposta]) {
      expect(aviso.compareDocumentPosition(mesa) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });
});

describe("a faixa dos números", () => {
  it("Nota de entrada, R$ a ajustar e Itens feitos numa faixa só, com a barra de andamento", async () => {
    respostaDoGuia = guia({ numeros: { ...guia().numeros, itens_feitos: 1 } });
    await abrir();

    const faixa = screen.getByRole("region", { name: "Números do guia" });
    expect(within(faixa).getByText("74")).toBeTruthy();
    expect(within(faixa).getByText("R$ 584,60")).toBeTruthy();
    expect(within(faixa).getByText("em 9 itens, mais 1.212,00 em validação")).toBeTruthy();
    expect(within(faixa).getByText("1 de 3")).toBeTruthy();
    const barra = within(faixa).getByRole("progressbar", { name: "Andamento da conta" });
    expect([barra.getAttribute("aria-valuenow"), barra.getAttribute("aria-valuemax")]).toEqual(["1", "3"]);
  });

  it("cada número tem a dica", async () => {
    await abrir();
    const faixa = screen.getByRole("region", { name: "Números do guia" });

    expect(dicaDe(within(faixa).getByText("Nota de entrada"))).toBe(
      "De 0 a 100, quanto a conta estava certa antes da correção.",
    );
    expect(dicaDe(within(faixa).getByText("R$ a ajustar"))).toBe(
      "Quanto falta corrigir no MV. O que está em validação aparece à parte.",
    );
    expect(dicaDe(within(faixa).getByText("Itens feitos"))).toBe("Quantos itens você já marcou, de quantos a conta tem.");
  });

  it("com o reenvio, a nota de saída fica ao lado da de entrada, com a dica; sem ele, não aparece", async () => {
    respostaDoGuia = guia({
      cabecalho: { ...guia().cabecalho, situacao: "CONCLUIDA" },
      reenvio: { nota_saida: 86, reenviada_em: "2026-10-13T10:00:00+00:00", corrigidas: 1, ainda_na_conta: 1 },
    });
    await abrir();

    const faixa = screen.getByRole("region", { name: "Números do guia" });
    expect(within(faixa).getByText("86")).toBeTruthy();
    expect(dicaDe(within(faixa).getByText("Nota de saída"))).toBe(
      "A mesma nota, feita sobre a conta corrigida que você reenviou.",
    );
    cleanup();

    respostaDoGuia = guia({ cabecalho: { ...guia().cabecalho, situacao: "CONCLUIDA" } });
    await abrir();
    const semReenvio = screen.getByRole("region", { name: "Números do guia" });
    expect(within(semReenvio).getByText("Nota de entrada")).toBeTruthy();
    expect(within(semReenvio).queryByText("Nota de saída")).toBeNull();
  });
});

describe("a Mesa de trabalho", () => {
  it("duas colunas a partir de 1000 px, com a lista antes do Item da vez", async () => {
    await abrir();

    const mesa = screen.getByRole("region", { name: "Mesa de trabalho" });
    expect(mesa.className).toContain("min-[1000px]:grid-cols-");
    expect(mesa.className).toMatch(/(^| )grid-cols-1( |$)/);
    expect(aLista().compareDocumentPosition(oItem()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("a lista rola sozinha e a página não rola para os lados", async () => {
    await abrir();

    expect(aLista().className).toContain("overflow-y-auto");
    expect(screen.getByTestId("guia").className).toContain("overflow-x-clip");
  });
});

describe("a lista por dia e setor", () => {
  it("cada grupo tem o dia, o setor e a contagem", async () => {
    await abrir();

    const cti = within(aLista()).getByRole("region", { name: "03/10 · CTI" });
    expect(within(cti).getByRole("heading", { name: "03/10 · CTI" })).toBeTruthy();
    expect(within(cti).getByText("2 itens")).toBeTruthy();
  });

  it("cada Linha mostra o estado, o verbo, o nome e o valor", async () => {
    await abrir();

    const luva = naLista("Luva de procedimento");
    expect(within(luva).getByText("Aberta")).toBeTruthy();
    expect(within(luva).getByText("Incluir")).toBeTruthy();
    expect(within(luva).getByText("+R$ 68,40")).toBeTruthy();
    const lavagem = naLista("Lavagem de sonda");
    expect(within(lavagem).getByText("Ajustar quantidade")).toBeTruthy();
    expect(within(lavagem).getByText("-R$ 4,17")).toBeTruthy();
    expect(within(naLista("Dieta enteral")).getByText("Em validação")).toBeTruthy();
  });

  it("a Linha marcada fica apagada, com o estado; a aberta não", async () => {
    respostaDoGuia = guia();
    respostaDoGuia.grupos[0].linhas[0] = linha({ estado: "FEITO" });
    await abrir();

    const luva = naLista("Luva de procedimento");
    expect(within(luva).getByText("Feito")).toBeTruthy();
    expect(luva.className).toContain("opacity-60");
    expect(naLista("Lavagem de sonda").className).not.toContain("opacity-60");
  });
});

describe("o Item da vez", () => {
  it("mostra a posição, o dia e o setor, o verbo, o nome, a quantidade e quando, o valor e o motivo", async () => {
    await abrir();
    const item = oItem();

    expect(within(item).getByText("Item 1 de 4")).toBeTruthy();
    expect(within(item).getByText("03/10 · CTI")).toBeTruthy();
    expect(within(item).getByText("Incluir", { selector: "span" })).toBeTruthy();
    const nome = within(item).getByRole("heading", { name: "Luva de procedimento" });
    expect(caixaDoDado(within(nome).getByText("Luva de procedimento"))).toBe("normal-case");
    expect(within(item).getByText("Incluir 180, de 03/10 a 05/10")).toBeTruthy();
    expect(within(item).getByText("+R$ 68,40")).toBeTruthy();
    expect(within(item).getByText("3 diárias de CTI pagas")).toBeTruthy();
    expect(within(item).getByRole("button", { name: "Copiar código 70012345" })).toBeTruthy();
  });

  it("a Evidência aparece sem clicar, com a página, o trecho e o nível com a dica", async () => {
    await abrir();
    const item = oItem();

    expect(within(item).getByText("Prontuário, p. 2")).toBeTruthy();
    expect(within(item).getByText("Luva de procedimento 60 por dia")).toBeTruthy();
    expect(dicaDe(within(item).getByText("Registrado"))).toBe("O prontuário registra o uso.");
  });

  it("Não conferido e conferir evidência aparecem só onde cabem", async () => {
    await abrir();
    expect(within(oItem()).queryByText("Não conferido")).toBeNull();
    expect(within(oItem()).queryByText("conferir evidência")).toBeNull();

    fireEvent.click(naLista("Lavagem de sonda"));

    expect(within(oItem()).getByText("Não conferido")).toBeTruthy();
    expect(within(oItem()).getByText("conferir evidência")).toBeTruthy();
  });

  it("a linha se necessário sem registro tem a etiqueta âmbar e já abre o Não procede com o motivo", async () => {
    respostaDoGuia = guia();
    respostaDoGuia.grupos[0].linhas.unshift(
      linha({
        id: "l-dipirona",
        data_fim: null,
        codigo: "91000002",
        descricao: "DIPIRONA 1 G AMP",
        quantidade_devida: 1,
        valor_diferenca: 2,
        nivel_evidencia: "PRESCRITO_SN",
        motivo: "Confira a checagem em papel. Sem uso, marque NÃO PROCEDE.",
      }),
    );
    await abrir();

    const etiqueta = within(oItem()).getByText("SE NECESSÁRIO · SEM REGISTRO NO MV");
    expect(etiqueta.className).toContain("bg-[#FEF3C7]");
    fireEvent.click(within(oItem()).getByRole("button", { name: "Não procede" }));
    expect((within(oItem()).getByLabelText("Sem evidência no prontuário") as HTMLInputElement).checked).toBe(true);
    fireEvent.click(within(oItem()).getByRole("button", { name: "Confirmar Não procede" }));
    await waitFor(() => expect(chamadas[1]?.corpo).toEqual({ estado: "NAO_PROCEDE", motivo: "SEM_EVIDENCIA" }));

    fireEvent.click(naLista("Luva de procedimento"));
    expect(within(oItem()).queryByText("SE NECESSÁRIO · SEM REGISTRO NO MV")).toBeNull();
    fireEvent.click(within(oItem()).getByRole("button", { name: "Não procede" }));
    expect(within(oItem()).getAllByRole("radio").some((r) => (r as HTMLInputElement).checked)).toBe(false);
  });

  it("ao abrir, é a primeira Linha aberta; clicar numa Linha da lista a torna o Item da vez", async () => {
    respostaDoGuia = guia();
    respostaDoGuia.grupos[0].linhas[0] = linha({ estado: "FEITO" });
    await abrir();

    expect(within(oItem()).getByRole("heading", { name: "Lavagem de sonda" })).toBeTruthy();
    expect(within(oItem()).getByText("Item 2 de 4")).toBeTruthy();
    expect(naLista("Lavagem de sonda").getAttribute("aria-current")).toBe("true");

    fireEvent.click(naLista("Fita de glicemia"));

    expect(within(oItem()).getByRole("heading", { name: "Fita de glicemia" })).toBeTruthy();
    expect(within(oItem()).getByText("04/10 · ENFERMARIA")).toBeTruthy();
    expect(naLista("Lavagem de sonda").getAttribute("aria-current")).toBeNull();
  });
});

describe("os botões do Item da vez", () => {
  it("Feito manda a marcação, recarrega e passa para a próxima Linha aberta", async () => {
    await abrir();
    respostaDoGuia = guia();
    respostaDoGuia.grupos[0].linhas[0] = linha({ estado: "FEITO" });

    fireEvent.click(within(oItem()).getByRole("button", { name: "Feito" }));

    await waitFor(() => expect(within(oItem()).getByRole("heading", { name: "Lavagem de sonda" })).toBeTruthy());
    expect(chamadas[1]).toEqual({
      url: `/api/contas-medicas/contas/${CONTA}/guia/linhas/l-luva/marcacao`,
      metodo: "POST",
      corpo: { estado: "FEITO" },
    });
    expect(chamadas[2].metodo).toBe("GET");
  });

  it("a próxima aberta segue a ordem da lista, pula a Validar e volta ao começo", async () => {
    await abrir();
    fireEvent.click(naLista("Fita de glicemia"));
    respostaDoGuia = guia();
    respostaDoGuia.grupos[1].linhas[0] = linha({ id: "l-fita", estado: "BLOQUEADO", descricao: "Fita de glicemia" });

    fireEvent.click(within(oItem()).getByRole("button", { name: "Bloqueado" }));

    await waitFor(() => expect(chamadas[1]?.corpo).toEqual({ estado: "BLOQUEADO" }));
    await waitFor(() => expect(within(oItem()).getByRole("heading", { name: "Luva de procedimento" })).toBeTruthy());
  });

  it("sem nenhuma Linha aberta, a tela diz que todos os itens estão marcados", async () => {
    await abrir();
    respostaDoGuia = guia();
    respostaDoGuia.grupos[0].linhas[0] = linha({ estado: "FEITO" });
    respostaDoGuia.grupos[0].linhas[1] = linha({ id: "l-lavagem", descricao: "Lavagem de sonda", estado: "FEITO" });
    respostaDoGuia.grupos[1].linhas[0] = linha({ id: "l-fita", descricao: "Fita de glicemia", estado: "NAO_PROCEDE" });

    fireEvent.click(within(oItem()).getByRole("button", { name: "Feito" }));

    expect(await within(oItem()).findByText("Todos os itens estão marcados.")).toBeTruthy();
  });

  it("Feito, Não procede e Bloqueado têm cada um a Legenda, que some com as Legendas desligadas", async () => {
    const LEGENDAS = [
      "Você já corrigiu no MV. A tela passa para o próximo item.",
      "O item está errado. Diga o motivo, que vai para a gestão.",
      "O MV não deixou lançar, por falta de cadastro ou de preço.",
    ];
    await abrir();
    for (const legenda of LEGENDAS) expect(within(oItem()).getByText(legenda)).toBeTruthy();
    cleanup();

    await abrir(false);
    expect(within(oItem()).getByRole("button", { name: "Feito" })).toBeTruthy();
    for (const legenda of LEGENDAS) expect(within(oItem()).queryByText(legenda)).toBeNull();
  });

  it("Não procede abre os 4 motivos, com o Ditar; em outro, o texto é obrigatório", async () => {
    await abrir();
    const item = oItem();
    expect(within(item).queryByRole("button", { name: "Ditar: Motivo do Não procede" })).toBeNull();

    fireEvent.click(within(item).getByRole("button", { name: "Não procede" }));
    const motivos = within(item).getAllByRole("radio").map((radio) => radio.closest("label")?.textContent);
    expect(motivos).toEqual(["Já está na conta", "Sem evidência no prontuário", "A regra é outra", "Outro"]);
    const ditar = within(item).getByRole("button", { name: "Ditar: Motivo do Não procede" });
    expect(ditar.parentElement?.textContent).toContain("Não dite nome nem dado de paciente.");

    fireEvent.click(within(item).getByLabelText("Outro"));
    const confirmar = within(item).getByRole("button", { name: "Confirmar Não procede" }) as HTMLButtonElement;
    expect(confirmar.disabled).toBe(true);
    fireEvent.change(within(item).getByRole("textbox", { name: "Motivo do Não procede" }), {
      target: { value: "Já vem no kit" },
    });
    expect(confirmar.disabled).toBe(false);
    fireEvent.click(confirmar);

    await waitFor(() =>
      expect(chamadas[1]?.corpo).toEqual({ estado: "NAO_PROCEDE", motivo: "OUTRO", texto: "Já vem no kit" }),
    );
  });

  it("Não procede com motivo e sem texto passa direto", async () => {
    await abrir();

    fireEvent.click(within(oItem()).getByRole("button", { name: "Não procede" }));
    fireEvent.click(within(oItem()).getByLabelText("Já está na conta"));
    fireEvent.click(within(oItem()).getByRole("button", { name: "Confirmar Não procede" }));

    await waitFor(() => expect(chamadas[1]?.corpo).toEqual({ estado: "NAO_PROCEDE", motivo: "JA_ESTA_NA_CONTA" }));
  });

  it("a Linha marcada tem o Desfazer no Item da vez, que manda o DELETE e fica no mesmo item", async () => {
    respostaDoGuia = guia();
    respostaDoGuia.grupos[0].linhas[0] = linha({ estado: "FEITO" });
    await abrir();
    fireEvent.click(naLista("Luva de procedimento"));
    expect(within(oItem()).queryByRole("button", { name: "Feito" })).toBeNull();
    expect(within(oItem()).getByText("Feito", { selector: "span" })).toBeTruthy();
    respostaDoGuia = guia();

    fireEvent.click(within(oItem()).getByRole("button", { name: "Desfazer" }));

    await waitFor(() =>
      expect(chamadas[1]).toEqual({
        url: `/api/contas-medicas/contas/${CONTA}/guia/linhas/l-luva/marcacao`,
        metodo: "DELETE",
        corpo: undefined,
      }),
    );
    await waitFor(() => expect(within(oItem()).getByRole("button", { name: "Feito" })).toBeTruthy());
    expect(within(oItem()).getByRole("heading", { name: "Luva de procedimento" })).toBeTruthy();
  });

  it("na conta concluída, a Linha marcada não tem Desfazer e a aberta não tem os botões", async () => {
    respostaDoGuia = guia({ cabecalho: { ...guia().cabecalho, situacao: "CONCLUIDA" } });
    respostaDoGuia.grupos[0].linhas[0] = linha({ estado: "FEITO" });
    await abrir();

    fireEvent.click(naLista("Luva de procedimento"));
    expect(within(oItem()).getByText("Feito", { selector: "span" })).toBeTruthy();
    expect(within(oItem()).queryByRole("button", { name: "Desfazer" })).toBeNull();
    fireEvent.click(naLista("Lavagem de sonda"));
    expect(within(oItem()).getByRole("heading", { name: "Lavagem de sonda" })).toBeTruthy();
    expect(within(oItem()).queryByRole("button", { name: "Feito" })).toBeNull();
  });
});

describe("a Linha Validar", () => {
  it("não tem botão e mostra a frase e o valor em jogo", async () => {
    await abrir();
    expect(within(oItem()).getByRole("button", { name: "Feito" })).toBeTruthy();

    fireEvent.click(naLista("Dieta enteral"));

    const item = oItem();
    expect(within(item).getByRole("heading", { name: "Dieta enteral" })).toBeTruthy();
    for (const nome of ["Feito", "Não procede", "Bloqueado"]) {
      expect(within(item).queryByRole("button", { name: nome })).toBeNull();
    }
    expect(item.textContent).toContain("Nada a decidir aqui: o item já foi para a validação");
    expect(item.textContent).toContain("Em jogo: R$ 1.212,00");
  });
});

describe("o cabeçalho de cada dia da lista", () => {
  it("tem o Faltou isto e o Marcar o dia como feito, que manda o dia e o setor", async () => {
    await abrir();

    const dia = within(aLista()).getByRole("region", { name: "04/10 · ENFERMARIA" });
    expect(within(dia).getByRole("button", { name: "Faltou isto" })).toBeTruthy();
    fireEvent.click(within(dia).getByRole("button", { name: "Marcar o dia como feito" }));

    await waitFor(() =>
      expect(chamadas[1]).toEqual({
        url: `/api/contas-medicas/contas/${CONTA}/guia/dia/feito`,
        metodo: "POST",
        corpo: { data: "2026-10-04", setor: "ENFERMARIA" },
      }),
    );
  });

  it("o Marcar o dia só aparece no dia com Linha aberta e na conta não concluída", async () => {
    respostaDoGuia = guia();
    respostaDoGuia.grupos[1].linhas[0] = linha({ id: "l-fita", descricao: "Fita de glicemia", estado: "FEITO" });
    await abrir();

    const cti = within(aLista()).getByRole("region", { name: "03/10 · CTI" });
    const enfermaria = within(aLista()).getByRole("region", { name: "04/10 · ENFERMARIA" });
    expect(within(cti).getByRole("button", { name: "Marcar o dia como feito" })).toBeTruthy();
    expect(within(enfermaria).queryByRole("button", { name: "Marcar o dia como feito" })).toBeNull();
    cleanup();

    respostaDoGuia = guia({ cabecalho: { ...guia().cabecalho, situacao: "CONCLUIDA" } });
    await abrir();
    expect(screen.queryByRole("button", { name: "Marcar o dia como feito" })).toBeNull();
    expect(screen.getAllByRole("button", { name: "Faltou isto" })).toHaveLength(2);
  });

  it("o Faltou isto leva o dia para a conversa com o Auditor, que oferece todos os dias do período", async () => {
    await abrir();

    const dia = within(aLista()).getByRole("region", { name: "04/10 · ENFERMARIA" });
    fireEvent.click(within(dia).getByRole("button", { name: "Faltou isto" }));

    const conversa = screen.getByRole("region", { name: "Falar com o auditor" });
    await waitFor(() =>
      expect((within(conversa).getByLabelText("Dia") as HTMLSelectElement).value).toBe("2026-10-04"),
    );
    const dias = within(conversa)
      .getAllByRole("option")
      .map((opcao) => opcao.textContent);
    expect(dias).toEqual(["03/10", "04/10", "05/10", "06/10", "07/10"]);
  });
});

describe("o rodapé fixo", () => {
  it("mostra quantos itens faltam, a observação com o Ditar e o Concluir com a Legenda", async () => {
    await abrir();

    const rodape = screen.getByRole("contentinfo");
    expect(rodape.className).toContain("sticky");
    expect(within(rodape).getByText("Faltam 3 itens para marcar")).toBeTruthy();
    const ditar = within(rodape).getByRole("button", { name: "Ditar: Observação para a gestão de contas médicas" });
    expect(ditar.parentElement?.textContent).toContain("Não dite nome nem dado de paciente.");
    const concluir = within(rodape).getByRole("button", { name: "Concluir e abrir a próxima" }) as HTMLButtonElement;
    expect(concluir.disabled).toBe(false);
    expect(within(rodape).getByText(/Você pode concluir com pendência/)).toBeTruthy();
    cleanup();

    await abrir(false);
    expect(screen.getByRole("button", { name: "Concluir e abrir a próxima" })).toBeTruthy();
    expect(screen.queryByText(/Você pode concluir com pendência/)).toBeNull();
  });

  it("fica fixo na rolagem da página: entre ele e o main do AppShell, nenhuma caixa rola", async () => {
    // O `sticky` se prende à caixa de rolagem mais próxima. O `<main>` do
    // AppShell tem `overflow-auto` e cresce com o conteúdo (quem rola é a
    // página): sem a regra do `globals.css` que o desliga, o rodapé ficaria
    // parado no fim da conta, depois da conversa com o Auditor.
    const regrasDoMain = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8").match(
      /^main[^{]*\{[^}]*\}/gm,
    );
    const estilo = document.createElement("style");
    estilo.textContent = (regrasDoMain ?? []).join("\n");
    document.head.appendChild(estilo);
    try {
      render(
        <main className="flex-1 p-4 md:p-8 overflow-auto pb-[88px] md:pb-8">
          <LegendasProvider chave="teste-legendas" ligadasIniciais>
            <ToastProvider>
              <GuiaPage />
            </ToastProvider>
          </LegendasProvider>
        </main>,
      );
      await screen.findByRole("heading", { level: 1, name: "31245 Maria S." });

      const main = document.querySelector("main") as HTMLElement;
      expect(getComputedStyle(main).overflowY).toBe("visible");
      expect(getComputedStyle(main).overflowX).toBe("clip");

      const rodape = screen.getByRole("contentinfo");
      expect(rodape.className).toMatch(/(^| )sticky( |$)/);
      for (let caixa = rodape.parentElement; caixa && caixa !== main; caixa = caixa.parentElement) {
        expect(caixa.className).not.toMatch(/(^| )overflow(-[xy])?-(auto|scroll|hidden)( |$)/);
      }
    } finally {
      estilo.remove();
    }
  });

  it("com um item só, a frase vai no singular; sem nenhum, diz que não falta nada", async () => {
    respostaDoGuia = guia({ numeros: { ...guia().numeros, itens_sem_marcacao: 1 } });
    await abrir();
    expect(within(screen.getByRole("contentinfo")).getByText("Falta 1 item para marcar")).toBeTruthy();
    cleanup();

    respostaDoGuia = guia({ numeros: { ...guia().numeros, itens_sem_marcacao: 0 } });
    await abrir();
    expect(within(screen.getByRole("contentinfo")).getByText("Nenhum item sem marcação")).toBeTruthy();
  });
});

describe("concluir", () => {
  it("com item sem marcação pergunta antes; negar não conclui", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Concluir e abrir a próxima" }));

    expect(confirmar).toHaveBeenCalledWith("3 itens sem marcação. Concluir assim mesmo?");
    expect(chamadas.some((c) => c.url.endsWith("/concluir"))).toBe(false);
  });

  it("confirmando, conclui com a observação e abre a próxima", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await abrir();

    fireEvent.change(screen.getByLabelText("Observação para a gestão de contas médicas"), {
      target: { value: "Luva já vem no kit do CTI" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Concluir e abrir a próxima" }));

    await waitFor(() => expect(navegacao.push).toHaveBeenCalledWith(`/contas-medicas/guia/${PROXIMA}`));
    expect(chamadas[1]).toEqual({
      url: `/api/contas-medicas/contas/${CONTA}/guia/concluir`,
      metodo: "POST",
      corpo: { observacao: "Luva já vem no kit do CTI" },
    });
  });

  it("sem item sem marcação não pergunta, e sem próxima volta para a fila", async () => {
    const confirmar = vi.spyOn(window, "confirm");
    respostaDoGuia = guia({ numeros: { ...guia().numeros, itens_sem_marcacao: 0 } });
    respostaDaConclusao = { situacao: "CONCLUIDA", pendencias: 0, proxima_conta_id: null };
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Concluir e abrir a próxima" }));

    await waitFor(() => expect(navegacao.push).toHaveBeenCalledWith("/contas-medicas"));
    expect(confirmar).not.toHaveBeenCalled();
  });

  it("conta concluída mostra o aviso no rodapé, sem Concluir", async () => {
    respostaDoGuia = guia({ cabecalho: { ...guia().cabecalho, situacao: "CONCLUIDA" } });
    await abrir();

    expect(screen.getByText("Concluída")).toBeTruthy();
    const rodape = screen.getByRole("contentinfo");
    expect(within(rodape).getByText("Conta concluída. As marcações não mudam mais.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Concluir e abrir a próxima" })).toBeNull();
  });
});

describe("o código copia com um clique", () => {
  it("copia para a área de transferência e mostra o toast", async () => {
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    await abrir();

    fireEvent.click(within(oItem()).getByRole("button", { name: "Copiar código 70012345" }));

    expect(writeText).toHaveBeenCalledWith("70012345");
    expect(await screen.findByText("Código copiado")).toBeTruthy();
  });

  it("o código aparece como está gravado, mesmo sendo um botão (issue #1455)", async () => {
    await abrir();

    expect(caixaDoDado(within(oItem()).getByRole("button", { name: "Copiar código 70012345" }))).toBe("normal-case");
  });
});

describe("o botão Reanalisar (issue #1130)", () => {
  it("aparece quando o guia diz que pode e manda a conta para a análise de novo", async () => {
    respostaDoGuia = guia({ pode_reanalisar: true });
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Reanalisar" }));

    await waitFor(() => expect(navegacao.push).toHaveBeenCalledWith("/contas-medicas"));
    expect(chamadas[1]).toEqual({
      url: `/api/contas-medicas/contas/${CONTA}/reanalisar`,
      metodo: "POST",
      corpo: undefined,
    });
  });

  it("não aparece quando o guia diz que não pode", async () => {
    respostaDoGuia = guia({ pode_reanalisar: false });
    await abrir();

    expect(screen.getByRole("button", { name: "Concluir e abrir a próxima" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Reanalisar" })).toBeNull();
  });
});

describe("o botão Devolver à fila (issue #1309)", () => {
  const PERGUNTA = "Devolver esta conta à fila? As marcações ficam na conta para quem pegar depois.";

  it("pergunta antes; negar não devolve", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Devolver à fila" }));

    expect(confirmar).toHaveBeenCalledWith(PERGUNTA);
    expect(chamadas.some((c) => c.url.endsWith("/devolver"))).toBe(false);
    expect(navegacao.push).not.toHaveBeenCalled();
  });

  it("confirmando, devolve a conta e volta para a tela de contas", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Devolver à fila" }));

    await waitFor(() => expect(navegacao.push).toHaveBeenCalledWith("/contas-medicas"));
    expect(chamadas[1]).toEqual({
      url: `/api/contas-medicas/contas/${CONTA}/devolver`,
      metodo: "POST",
      corpo: undefined,
    });
    expect(await screen.findByText("A conta voltou para a Fila")).toBeTruthy();
  });

  it.each(["RETORNO", "CONCLUIDA"])("a conta em %s não tem o botão", async (situacao) => {
    respostaDoGuia = guia({ cabecalho: { ...guia().cabecalho, situacao } });
    await abrir();

    expect(screen.getByText(situacao === "RETORNO" ? "Retorno" : "Concluída")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Devolver à fila" })).toBeNull();
  });
});

describe("o reenvio da conta corrigida (issue #1136)", () => {
  function concluida(campos: Partial<Guia> = {}): Guia {
    return guia({ cabecalho: { ...guia().cabecalho, situacao: "CONCLUIDA" }, pode_reenviar: true, ...campos });
  }

  it("o botão fica no rodapé da conta concluída e manda só o PDF da conta", async () => {
    respostaDoGuia = concluida();
    await abrir();

    const rodape = screen.getByRole("contentinfo");
    expect(within(rodape).getByRole("button", { name: "Reenviar conta corrigida" })).toBeTruthy();
    const pdf = new File(["%PDF"], "conta-48811.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("PDF da conta corrigida"), { target: { files: [pdf] } });

    await waitFor(() => expect(chamadas.filter((c) => c.metodo === "GET")).toHaveLength(2));
    const reenvio = chamadas[1];
    expect([reenvio.url, reenvio.metodo]).toEqual([`/api/contas-medicas/contas/${CONTA}/reenvio`, "POST"]);
    const enviado = reenvio.corpo as FormData;
    expect([...enviado.keys()]).toEqual(["arquivo"]);
    expect((enviado.get("arquivo") as File).name).toBe("conta-48811.pdf");
    expect(await screen.findByText("2 corrigidas no MV, 1 ainda na conta, nota de saída 86")).toBeTruthy();
  });

  it("conta em aberto não tem o botão", async () => {
    respostaDoGuia = guia({ pode_reenviar: false });
    await abrir();

    expect(screen.getByRole("button", { name: "Concluir e abrir a próxima" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Reenviar conta corrigida" })).toBeNull();
  });

  it("a marca do reenvio aparece em cada Linha Feito da lista", async () => {
    respostaDoGuia = concluida({
      reenvio: { nota_saida: 86, reenviada_em: "2026-10-13T10:00:00+00:00", corrigidas: 1, ainda_na_conta: 1 },
      grupos: [
        {
          data: "2026-10-03",
          setor: "CTI",
          linhas: [
            linha({ estado: "FEITO", reenvio: "CORRIGIDA" }),
            linha({
              id: "l-senha",
              acao: "RETIRAR",
              descricao: "Senha de acesso",
              estado: "FEITO",
              reenvio: "AINDA_NA_CONTA",
            }),
            linha({ id: "l-gaze", descricao: "Gaze", estado: "NAO_PROCEDE", reenvio: null }),
          ],
        },
      ],
    });
    await abrir();

    expect(within(naLista("Luva de procedimento")).getByText("corrigida no MV")).toBeTruthy();
    expect(within(naLista("Senha de acesso")).getByText("ainda na conta")).toBeTruthy();
    expect(within(naLista("Gaze")).queryByText(/corrigida no MV|ainda na conta/)).toBeNull();
  });
});

describe("o Retorno da Validação (issue #1142)", () => {
  it("mostra só as Linhas devolvidas, a resposta ao time e a decidida com a etiqueta e os botões", async () => {
    respostaDoGuia = guia({
      cabecalho: { ...guia().cabecalho, situacao: "RETORNO" },
      respostas: [
        {
          titulo: "Observações sobre a regra ALFA-PRI-07",
          regra_codigo: "ALFA-PRI-07",
          resposta: "Confirmado com a ALFA: vem no pacote.",
          decidido_em: "2026-10-12T10:00:00+00:00",
        },
      ],
      grupos: [
        {
          data: "2026-10-03",
          setor: "CTI",
          linhas: [
            linha({ id: "l-descartada", acao: "VALIDAR", estado: "DECIDIDA", descricao: "Diária" }),
            linha({ id: "l-decidida", estado: "DECIDIDA", descricao: "Seringa pronta" }),
          ],
        },
      ],
    });
    await abrir();

    expect(screen.getByText("Retorno")).toBeTruthy();
    expect(within(aLista()).getAllByRole("button", { name: /Diária|Seringa pronta/ })).toHaveLength(2);
    expect(within(aLista()).queryByRole("button", { name: /Luva de procedimento/ })).toBeNull();
    expect(screen.getByRole("note", { name: "Resposta da Validação" }).textContent).toContain(
      "Confirmado com a ALFA: vem no pacote.",
    );
    const item = oItem();
    expect(within(item).getByRole("heading", { name: "Seringa pronta" })).toBeTruthy();
    expect(item.textContent).toContain("Decidida na validação");
    expect(within(item).getByRole("button", { name: "Feito" })).toBeTruthy();

    fireEvent.click(naLista("Diária"));
    expect(oItem().textContent).toContain("Decidida na validação, sem ação no MV");
    expect(oItem().textContent).not.toContain("Nada a decidir aqui");
  });
});

describe("a marca regra nova desde a análise (issue #1141)", () => {
  it("conta analisada antes da regra nova mostra a marca e o botão Reanalisar com a regra nova", async () => {
    respostaDoGuia = guia({ pode_reanalisar: true, regra_nova_desde_analise: true });
    await abrir();

    expect(screen.getByText("Regra nova desde a análise")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reanalisar com a regra nova" }));

    await waitFor(() => expect(navegacao.push).toHaveBeenCalledWith("/contas-medicas"));
    expect(chamadas[1].url).toBe(`/api/contas-medicas/contas/${CONTA}/reanalisar`);
  });

  it("conta analisada com a memória de agora fica sem a marca e com o botão Reanalisar", async () => {
    respostaDoGuia = guia({ pode_reanalisar: true, regra_nova_desde_analise: false });
    await abrir();

    expect(screen.getByRole("button", { name: "Reanalisar" })).toBeTruthy();
    expect(screen.queryByText("Regra nova desde a análise")).toBeNull();
    expect(screen.queryByRole("button", { name: "Reanalisar com a regra nova" })).toBeNull();
  });

  it("a faturista vê a marca mesmo sem o botão", async () => {
    respostaDoGuia = guia({ pode_reanalisar: false, regra_nova_desde_analise: true });
    await abrir();

    expect(screen.getByText("Regra nova desde a análise")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Reanalisar/ })).toBeNull();
  });
});

describe("a conta sem Linha", () => {
  it("diz que não há nada a corrigir", async () => {
    respostaDoGuia = guia({ grupos: [] });
    await abrir();

    expect(within(oItem()).getByText("Nada a corrigir nesta conta.")).toBeTruthy();
  });
});
