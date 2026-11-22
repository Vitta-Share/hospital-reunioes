/**
 * @vitest-environment jsdom
 */

/**
 * O afastamento cautelar na tela do caso e os pedidos da Rota Especial para a
 * coordenação (issue #1836). Quem decide o que vale é o servidor; aqui se
 * trava o que a tela mostra e o que ela pede a ele.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Afastamento, PedidoDeAfastamento } from "@/lib/conduta/afastamento";

import { AfastamentoCautelar, PedidosDeAfastamento } from "./AfastamentoCautelar";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const AVISO = "O afastamento cautelar é remunerado e não é punição.";
const CITADO = { id: "cit-1", nome: "Carlos Pereira", ligado: false };

const DECIDIDO: Afastamento = {
  id: "af-1",
  rota: "comum",
  quem: "Carlos Pereira",
  motivo: "Ameaça às testemunhas.",
  registrado_em: "2026-11-20T13:00:00+00:00",
  resultado: "afastar",
  entregas: { dp: "2026-11-20", juridico: null },
  parecer: null,
  pode_registrar_entrega: true,
  pode_anexar_parecer: true,
};

function resposta(corpo: unknown, ok = true) {
  return { ok, status: ok ? 200 : 403, json: async () => corpo } as Response;
}

describe("Na tela do caso", () => {
  it("o coordenador registra o afastamento de um Citado com o motivo", async () => {
    const chamada = vi.fn(async () => resposta({ caso: {} }));
    vi.stubGlobal("fetch", chamada);
    const aoMudar = vi.fn();
    render(
      <AfastamentoCautelar casoId="caso-1" rota="comum" citados={[CITADO]} afastamentos={[]} podeRegistrar aoMudar={aoMudar} />,
    );

    expect(screen.getByText(AVISO)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Quem afastar"), { target: { value: "cit-1" } });
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: "Ameaça às testemunhas." } });
    fireEvent.click(screen.getByRole("button", { name: "REGISTRAR AFASTAMENTO" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    const [url, opcoes] = chamada.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/comite-de-conduta/casos/caso-1/afastamentos");
    expect(JSON.parse(String(opcoes.body))).toEqual({ citado_id: "cit-1", motivo: "Ameaça às testemunhas." });
  });

  it("na Rota Especial o grupo pede à coordenação", () => {
    render(
      <AfastamentoCautelar casoId="caso-1" rota="especial" citados={[CITADO]} afastamentos={[]} podeRegistrar aoMudar={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: "PEDIR AFASTAMENTO À COORDENAÇÃO" })).toBeTruthy();
  });

  it("mostra a entrega registrada e registra a que falta", async () => {
    const chamada = vi.fn(async () => resposta({ ok: true }));
    vi.stubGlobal("fetch", chamada);
    render(
      <AfastamentoCautelar casoId="caso-1" rota="comum" citados={[CITADO]} afastamentos={[DECIDIDO]} podeRegistrar={false} aoMudar={vi.fn()} />,
    );
    const cartao = screen.getByRole("listitem", { name: "Afastamento de Carlos Pereira" });

    expect(within(cartao).getByText("Entregue ao DP em 20/11/2026.")).toBeTruthy();
    expect(within(cartao).getByText("Decisão do coordenador: afastar.")).toBeTruthy();
    fireEvent.change(within(cartao).getByLabelText("Data da entrega ao Jurídico"), { target: { value: "2026-11-20" } });
    fireEvent.click(within(cartao).getByRole("button", { name: "REGISTRAR ENTREGA AO JURÍDICO" }));

    await waitFor(() => expect(chamada).toHaveBeenCalled());
    const [url, opcoes] = chamada.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/comite-de-conduta/casos/caso-1/afastamentos/af-1/entrega");
    expect(JSON.parse(String(opcoes.body))).toEqual({ destino: "juridico", entregue_em: "2026-11-20" });
  });

  it("na Rota Especial o parecer pede o resultado antes de anexar", () => {
    const pedido = { ...DECIDIDO, rota: "especial" as const, resultado: null, entregas: { dp: null, juridico: null } };
    render(
      <AfastamentoCautelar casoId="caso-1" rota="especial" citados={[]} afastamentos={[pedido]} podeRegistrar={false} aoMudar={vi.fn()} />,
    );
    const anexar = screen.getByRole("button", { name: "ANEXAR PARECER DO JURÍDICO" }) as HTMLButtonElement;
    fireEvent.change(screen.getByLabelText("Parecer do Jurídico (PDF)"), {
      target: { files: [new File(["%PDF"], "parecer.pdf", { type: "application/pdf" })] },
    });

    expect(anexar.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Não afastar"));
    expect(anexar.disabled).toBe(false);
    expect(screen.getByText("Aguardando o parecer do Jurídico, que define o afastamento.")).toBeTruthy();
  });

  it("mostra a ciência do grupo no parecer anexado", () => {
    const definido: Afastamento = {
      ...DECIDIDO,
      rota: "especial",
      resultado: "nao_afastar",
      parecer: { anexado_em: "2026-11-21T13:00:00+00:00", ciencia_de: ["Ana Souza", "Bruno Dias"] },
      pode_anexar_parecer: false,
    };
    render(
      <AfastamentoCautelar casoId="caso-1" rota="especial" citados={[]} afastamentos={[definido]} podeRegistrar={false} aoMudar={vi.fn()} />,
    );

    expect(screen.getByText("O parecer do Jurídico definiu: não afastar.")).toBeTruthy();
    expect(screen.getByText("Com ciência de: Ana Souza, Bruno Dias.")).toBeTruthy();
  });

  it("sem afastamento e sem poder registrar, não mostra nada", () => {
    render(
      <AfastamentoCautelar casoId="caso-1" rota="comum" citados={[CITADO]} afastamentos={[]} podeRegistrar={false} aoMudar={vi.fn()} />,
    );

    expect(screen.queryByRole("region", { name: "Afastamento cautelar" })).toBeNull();
  });
});

describe("Pedidos da Rota Especial para a coordenação", () => {
  it("lista o pedido sem dado do caso e abre só o pedido", async () => {
    const pedido: PedidoDeAfastamento = {
      id: "af-2",
      rota: "especial",
      registrado_em: "2026-11-20T13:00:00+00:00",
      resultado: null,
      entregas: { dp: null, juridico: null },
      parecer: null,
      pode_registrar_entrega: true,
      pode_anexar_parecer: true,
      pedido: { quem: "Carlos Pereira", motivo: "Ameaça.", texto: "Pedido de afastamento cautelar\nQuem afastar: Carlos Pereira" },
      aviso: AVISO,
    };
    const chamada = vi.fn(async (url: string) =>
      url.endsWith("/afastamentos/pedidos")
        ? resposta({ pedidos: [{ id: "af-2", caso_id: "caso-9", registrado_em: pedido.registrado_em, resultado: null, parecer_anexado: false }] })
        : resposta(pedido),
    );
    vi.stubGlobal("fetch", chamada);
    render(<PedidosDeAfastamento />);

    fireEvent.click(await screen.findByRole("button", { name: "ABRIR PEDIDO" }));

    expect(await screen.findByLabelText("Pedido de afastamento")).toBeTruthy();
    expect(chamada).toHaveBeenLastCalledWith("/api/comite-de-conduta/casos/caso-9/afastamentos/af-2", expect.anything());
  });

  it("quem não é da coordenação não vê a seção", async () => {
    const chamada = vi.fn(async () => resposta({ detail: "Sem acesso" }, false));
    vi.stubGlobal("fetch", chamada);
    render(<PedidosDeAfastamento />);

    await waitFor(() => expect(chamada).toHaveBeenCalled());
    expect(screen.queryByRole("region", { name: "Pedidos de afastamento da Rota Especial" })).toBeNull();
  });
});
