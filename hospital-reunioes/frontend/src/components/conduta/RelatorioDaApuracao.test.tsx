/**
 * @vitest-environment jsdom
 */

/**
 * O relatório de apuração do Canal de Conduta (issue #1832; especificação,
 * 6.3 e 6.4). O servidor decide o que vale; o que se trava aqui é o que a
 * tela pede a ele: um clique gera, a edição sobe como versão nova, e no rito
 * Completo o relatório vai à assinatura dos apuradores.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TextoDaApuracao } from "@/lib/conduta/relatorio";

import { RelatorioDaApuracao } from "./RelatorioDaApuracao";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let chamadas: { url: string; method: string; body: unknown }[];

beforeEach(() => {
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null });
      return { ok: true, status: 200, json: async () => ({ versao: 1 }) } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const RELATORIO: TextoDaApuracao = {
  texto: "Fatos: Rogério Valente teria ameaçado cortar as horas.",
  versao: 2,
  limite: 3000,
  versoes: [
    { versao: 2, origem: "edicao", autor: "Ana Coordenadora", criado_em: null, texto: "Fatos: Rogério Valente teria ameaçado cortar as horas." },
    { versao: 1, origem: "agente", autor: "Bruno Membro", criado_em: null, texto: "Fatos: rascunho do agente." },
  ],
};

function desenhar(extra: Partial<Parameters<typeof RelatorioDaApuracao>[0]> = {}) {
  const aoMudar = vi.fn();
  render(<RelatorioDaApuracao casoId="c1" relatorio={null} cronologia={null} podeRedigir aoMudar={aoMudar} {...extra} />);
  return aoMudar;
}

describe("RelatorioDaApuracao", () => {
  it("um clique em GERAR RELATÓRIO pede o relatório ao servidor", async () => {
    const aoMudar = desenhar();

    fireEvent.click(screen.getByRole("button", { name: "GERAR RELATÓRIO" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas).toEqual([{ url: "/api/comite-de-conduta/casos/c1/relatorio", method: "POST", body: {} }]);
  });

  it("MONTAR CRONOLOGIA pede a cronologia dos fatos", async () => {
    desenhar();

    fireEvent.click(screen.getByRole("button", { name: "MONTAR CRONOLOGIA" }));

    await waitFor(() => expect(chamadas.map((c) => c.url)).toEqual(["/api/comite-de-conduta/casos/c1/cronologia"]));
  });

  it("a edição sobe como versão nova, e as versões anteriores aparecem", async () => {
    desenhar({ relatorio: RELATORIO });
    const secao = screen.getByRole("region", { name: "Relatório de apuração" });
    expect(within(secao).getByText("Fatos: rascunho do agente.")).toBeTruthy();

    fireEvent.click(within(secao).getByRole("button", { name: "EDITAR" }));
    fireEvent.change(within(secao).getByLabelText("Texto"), { target: { value: "Fatos revistos." } });
    fireEvent.click(within(secao).getByRole("button", { name: "SALVAR NOVA VERSÃO" }));

    await waitFor(() =>
      expect(chamadas).toEqual([
        { url: "/api/comite-de-conduta/casos/c1/relatorio/versoes", method: "POST", body: { texto: "Fatos revistos." } },
      ])
    );
  });

  it("no rito Completo, a última versão vai à assinatura dos apuradores", async () => {
    desenhar({ relatorio: { ...RELATORIO, assinatura: null } });

    fireEvent.click(screen.getByRole("button", { name: "ENVIAR PARA ASSINATURA" }));

    await waitFor(() => expect(chamadas.map((c) => c.url)).toEqual(["/api/comite-de-conduta/casos/c1/relatorio/assinatura"]));
  });

  it("o relatório assinado mostra a situação e o botão de abrir a cópia", () => {
    desenhar({
      relatorio: { ...RELATORIO, assinatura: { situacao: "assinado", erro: null, assinado_em: null, tem_copia: true } },
    });

    expect(screen.getByText("Assinado pelos apuradores")).toBeTruthy();
    expect(screen.getByRole("button", { name: "ABRIR RELATÓRIO ASSINADO" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "ENVIAR PARA ASSINATURA" })).toBeNull();
  });

  it("quem não apura vê o relatório, mas não gera nem edita", () => {
    desenhar({ relatorio: RELATORIO, podeRedigir: false });

    expect(screen.getAllByText("Fatos: Rogério Valente teria ameaçado cortar as horas.").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /GERAR RELATÓRIO/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "EDITAR" })).toBeNull();
  });
});
