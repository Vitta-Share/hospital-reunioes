/**
 * @vitest-environment jsdom
 */

/**
 * A conversa da Conta com o Auditor, no Guia (issue #1489, PRD #1484, ADR 0081),
 * num painel lateral desde a issue #1957.
 *
 * A tela não decide nada: quem aponta, a origem e quem abre o pedido para a
 * Tecnologia vêm do servidor. O que se trava aqui é o que a pessoa vê (o nome
 * do agente, a resposta, o botão do pedido só para quem pode) e o que cada
 * clique dispara (a URL e o corpo).
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";
import type { FaltouIsto } from "@/lib/contas-medicas/faltouIsto";

import { ConversaDaConta } from "./ConversaDaConta";

const CONTA = "11111111-1111-1111-1111-111111111111";
const ROTA = `/api/contas-medicas/contas/${CONTA}/guia/faltou-isto`;
const DIAS = ["2026-10-03", "2026-10-04", "2026-10-05"];

function apontamento(campos: Partial<FaltouIsto> = {}): FaltouIsto {
  return {
    id: "f-1",
    data: "2026-10-03",
    item: "Equipo macrogotas",
    pagina: 2,
    texto: "Por que você não achou o equipo nesta página?",
    origem: "PESSOA",
    classificacao: "DEFEITO",
    explicacao: "O acesso está na página 2, mas o Guia não pediu o equipo.",
    pedido_aberto: false,
    pode_abrir_pedido: true,
    ...campos,
  };
}

let chamadas: { url: string; metodo: string; corpo: unknown }[] = [];
let lista: FaltouIsto[] = [];

beforeEach(() => {
  chamadas = [];
  lista = [apontamento()];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const metodo = init?.method ?? "GET";
      const corpo = init?.body ? JSON.parse(String(init.body)) : undefined;
      chamadas.push({ url, metodo, corpo });
      if (url.endsWith("/pedido")) {
        const aberto = { ...apontamento(), pedido_aberto: true, pode_abrir_pedido: false };
        return new Response(JSON.stringify({ apontamento: aberto }), { status: 200 });
      }
      const novo = apontamento({
        id: "f-2",
        data: corpo.data,
        item: corpo.item,
        pagina: corpo.pagina,
        texto: corpo.texto,
        classificacao: "REGRA",
        explicacao: "Nenhuma regra da memória cobra a fralda neste caso.",
        pode_abrir_pedido: false,
      });
      return new Response(JSON.stringify({ apontamento: novo }), { status: 200 });
    }),
  );
});

afterEach(() => {
  cleanup();
  fechar.mockReset();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const fechar = vi.fn();

function abrir(escolha: { dia: string; vez: number } | null = null, aberta = true) {
  return render(
    <ToastProvider>
      <ConversaDaConta
        contaId={CONTA}
        token="token-de-teste"
        dias={DIAS}
        iniciais={lista}
        escolha={escolha}
        aberta={aberta}
        onFechar={fechar}
      />
    </ToastProvider>,
  );
}

describe("a conversa com o Auditor", () => {
  it("chama o agente de Auditor e mostra a fala de quem apontou com a resposta e a origem", async () => {
    abrir();

    const conversa = screen.getByRole("dialog", { name: "Falar com o auditor" });
    expect(within(conversa).getByRole("heading", { name: "Falar com o auditor" })).toBeTruthy();
    expect(
      await within(conversa).findByText(
        "Faltou isto em 03/10, página 2: Equipo macrogotas. Por que você não achou o equipo nesta página?",
      ),
    ).toBeTruthy();
    const resposta = within(conversa).getByRole("article", { name: "Resposta do Auditor" });
    expect(within(resposta).getByText("Auditor")).toBeTruthy();
    expect(within(resposta).getByText("Defeito do sistema")).toBeTruthy();
    expect(within(resposta).getByText("O acesso está na página 2, mas o Guia não pediu o equipo.")).toBeTruthy();
    expect(chamadas).toEqual([]);
  });

  it("marca o Faltou isto que o segundo agente achou, e só ele", async () => {
    lista = [
      apontamento(),
      apontamento({ id: "f-2", origem: "AGENTE", texto: null, item: "Fralda geriátrica", pode_abrir_pedido: false }),
    ];
    abrir();

    const doAgente = (await screen.findByText(/Fralda geriátrica\./)).closest("div") as HTMLElement;
    expect(within(doAgente).getByText("Achado pelo agente")).toBeTruthy();
    expect(screen.getAllByText("Achado pelo agente")).toHaveLength(1);
  });

  it("aponta o Faltou isto do dia escolhido, com o item, a página e a pergunta", async () => {
    abrir();
    await screen.findByText(/Equipo macrogotas\./);

    fireEvent.change(screen.getByLabelText("Dia"), { target: { value: "2026-10-04" } });
    fireEvent.change(screen.getByLabelText("Item que faltou"), { target: { value: "Fralda geriátrica" } });
    fireEvent.change(screen.getByLabelText("Página do prontuário"), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText("Mensagem para o auditor"), { target: { value: "E a fralda?" } });
    fireEvent.click(screen.getByRole("button", { name: "Perguntar ao auditor" }));

    expect(await screen.findByText("Nenhuma regra da memória cobra a fralda neste caso.")).toBeTruthy();
    expect(chamadas.at(-1)).toEqual({
      url: ROTA,
      metodo: "POST",
      corpo: { data: "2026-10-04", item: "Fralda geriátrica", pagina: 12, texto: "E a fralda?" },
    });
    expect(screen.getByText("Falta regra")).toBeTruthy();
    expect((screen.getByLabelText("Item que faltou") as HTMLInputElement).value).toBe("");
  });

  it("sem o item, o botão de perguntar fica desligado", async () => {
    abrir();

    const perguntar = screen.getByRole("button", { name: "Perguntar ao auditor" }) as HTMLButtonElement;
    expect(perguntar.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Item que faltou"), { target: { value: "Equipo" } });
    expect(perguntar.disabled).toBe(false);
  });

  it("o dia escolhido no Guia chega ao formulário", async () => {
    abrir({ dia: "2026-10-05", vez: 1 });

    await waitFor(() => expect((screen.getByLabelText("Dia") as HTMLSelectElement).value).toBe("2026-10-05"));
    expect(screen.getAllByRole("option").map((opcao) => opcao.textContent)).toEqual(["03/10", "04/10", "05/10"]);
  });
});

describe("a Regra que nasceu do Faltou isto", () => {
  it("mostra onde está a proposta de Regra, como o servidor diz", async () => {
    const onde = "A Regra ALFA-INS-01 entrou na memória como pendente e foi para a Validação.";
    lista = [
      apontamento({ classificacao: "REGRA", pode_abrir_pedido: false, proposta_de_regra: onde }),
      apontamento({ id: "f-2", item: "Fralda geriátrica", texto: null, pode_abrir_pedido: false }),
    ];
    abrir();

    const respostas = await screen.findAllByRole("article", { name: "Resposta do Auditor" });
    expect(within(respostas[0]).getByText(onde)).toBeTruthy();
    expect(screen.getAllByText(onde)).toHaveLength(1);
  });
});

describe("o pedido para a Tecnologia", () => {
  it("quem apontou dá o ok e o pedido fica aberto, sem número na tela", async () => {
    abrir();

    fireEvent.click(await screen.findByRole("button", { name: "Abrir o pedido para a Tecnologia" }));

    expect(await screen.findByText("Pedido aberto para a Tecnologia.")).toBeTruthy();
    expect(chamadas.at(-1)).toEqual({ url: `${ROTA}/f-1/pedido`, metodo: "POST", corpo: undefined });
    expect(screen.queryByRole("button", { name: "Abrir o pedido para a Tecnologia" })).toBeNull();
  });

  it("quem não apontou não vê o botão do pedido", async () => {
    lista = [apontamento({ pode_abrir_pedido: false })];
    abrir();

    expect(await screen.findByText("O acesso está na página 2, mas o Guia não pediu o equipo.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Abrir o pedido para a Tecnologia" })).toBeNull();
  });
});

describe("o painel lateral da conversa (issue #1957)", () => {
  it("fechado, o painel não aparece; aberto, aparece com o título", async () => {
    abrir(null, false);
    expect(screen.queryByRole("dialog", { name: "Falar com o auditor" })).toBeNull();
    cleanup();

    abrir();
    expect(screen.getByRole("dialog", { name: "Falar com o auditor" })).toBeTruthy();
  });

  it("fecha pelo botão e pelo Esc; fechado, o Esc não chama nada", async () => {
    abrir();

    fireEvent.click(screen.getByRole("button", { name: "Fechar a conversa" }));
    expect(fechar).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(fechar).toHaveBeenCalledTimes(2);
    cleanup();

    abrir(null, false);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(fechar).toHaveBeenCalledTimes(2);
  });

  it("ocupa a tela inteira na largura estreita e fica numa coluna à direita a partir de 640 px, sem fundo escuro", async () => {
    const { container } = abrir();

    const painel = screen.getByRole("dialog", { name: "Falar com o auditor" });
    const classes = painel.className.split(" ");
    for (const classe of ["fixed", "inset-y-0", "right-0", "w-full", "sm:w-96", "overflow-y-auto"]) {
      expect(classes).toContain(classe);
    }
    expect(painel.getAttribute("aria-modal")).toBe("false");
    expect(container.querySelector(".bg-black\\/30")).toBeNull();
  });
});
