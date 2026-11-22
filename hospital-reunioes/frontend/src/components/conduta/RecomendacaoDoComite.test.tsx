/**
 * @vitest-environment jsdom
 */

/**
 * A Recomendação do Comitê na tela da Direção (issue #1835; especificação,
 * 6.8). O Presidente só lê; a diretoria executiva registra a decisão, e "com
 * ajuste" e "não aplicada" pedem justificativa. O servidor decide o que vale;
 * aqui se trava o que a tela pede a ele.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Recomendacao } from "@/lib/conduta/direcao";

import { ListaDeRecomendacoes, RecomendacaoDoComite } from "./RecomendacaoDoComite";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

const PAGINA: Recomendacao = {
  id: "caso-1",
  protocolo: "CC-AB12-CD34",
  rito: "Rápido",
  categoria: "Conduta e relações",
  resultado: "Procedente",
  medida_recomendada: "Advertência escrita",
  relatorio: "O supervisor ameaçou cortar as horas da equipe.",
  votacao_concluida_em: "2026-11-15T12:00:00+00:00",
  enviado_a_direcao_em: "2026-11-16T12:00:00+00:00",
  tem_ata_assinada: true,
  decisao: null,
  comunicacoes: [],
  pode_registrar: false,
  pode_anexar_comunicacao: false,
};

let chamadas: { url: string; method: string; body: unknown }[];
let pagina: Recomendacao;

beforeEach(() => {
  chamadas = [];
  pagina = PAGINA;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null });
      const corpo = url.endsWith("/recomendacoes")
        ? { recomendacoes: [{ id: "caso-1", protocolo: "CC-AB12-CD34", enviado_a_direcao_em: "2026-11-16T12:00:00+00:00", decisao: null }], registra_decisao: false }
        : url.endsWith("/decisao")
          ? { decisao: "aplicada" }
          : pagina;
      return { ok: true, status: 200, json: async () => corpo } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("A lista das Recomendações", () => {
  it("mostra os casos enviados, com o link para a Recomendação", async () => {
    render(<ListaDeRecomendacoes />);

    const link = await screen.findByRole("link", { name: /CC-AB12-CD34/ });
    expect(link.getAttribute("href")).toBe("/comite-de-conduta/recomendacoes/caso-1");
    expect(screen.getByText("Aguardando a decisão")).toBeTruthy();
  });
});

describe("O Presidente só lê", () => {
  it("lê a página de conclusão sem formulário de decisão", async () => {
    render(<RecomendacaoDoComite casoId="caso-1" />);

    expect(await screen.findByText("O supervisor ameaçou cortar as horas da equipe.")).toBeTruthy();
    expect(screen.getByText("Procedente")).toBeTruthy();
    expect(screen.getByText("Advertência escrita")).toBeTruthy();
    expect(screen.getByRole("button", { name: "ABRIR A ATA ASSINADA" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "REGISTRAR DECISÃO" })).toBeNull();
    expect(chamadas[0].url).toBe("/api/comite-de-conduta/direcao/recomendacoes/caso-1");
  });
});

describe("A diretoria executiva registra a decisão", () => {
  it("com ajuste pede justificativa antes de registrar", async () => {
    pagina = { ...PAGINA, pode_registrar: true };
    render(<RecomendacaoDoComite casoId="caso-1" />);

    fireEvent.click(await screen.findByLabelText("Aplicada com ajuste"));
    fireEvent.change(screen.getByLabelText("Data da decisão do Presidente"), { target: { value: "2026-11-18" } });
    const registrar = screen.getByRole("button", { name: "REGISTRAR DECISÃO" }) as HTMLButtonElement;
    expect(registrar.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Justificativa"), { target: { value: "Ajustada pelo histórico." } });
    fireEvent.click(registrar);

    await waitFor(() => expect(chamadas.some((c) => c.url.endsWith("/decisao"))).toBe(true));
    expect(chamadas.find((c) => c.url.endsWith("/decisao"))).toEqual({
      url: "/api/comite-de-conduta/direcao/recomendacoes/caso-1/decisao",
      method: "POST",
      body: { decisao: "aplicada_com_ajuste", justificativa: "Ajustada pelo histórico.", decidida_em: "2026-11-18" },
    });
  });

  it("aplicada registra sem justificativa", async () => {
    pagina = { ...PAGINA, pode_registrar: true };
    render(<RecomendacaoDoComite casoId="caso-1" />);

    fireEvent.click(await screen.findByLabelText("Aplicada"));
    fireEvent.change(screen.getByLabelText("Data da decisão do Presidente"), { target: { value: "2026-11-18" } });

    expect((screen.getByRole("button", { name: "REGISTRAR DECISÃO" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("a decisão registrada aparece com a data e a justificativa", async () => {
    pagina = {
      ...PAGINA,
      decisao: {
        decisao: "Não aplicada",
        codigo: "nao_aplicada",
        justificativa: "Sem histórico anterior.",
        decidida_em: "2026-11-18",
        registrada_em: "2026-11-18T15:00:00+00:00",
      },
    };
    render(<RecomendacaoDoComite casoId="caso-1" />);

    expect(await screen.findByText("Não aplicada")).toBeTruthy();
    expect(screen.getByText("Sem histórico anterior.")).toBeTruthy();
    expect(screen.getByText(/18\/11\/2026/)).toBeTruthy();
  });
});
