/**
 * @vitest-environment jsdom
 */

/**
 * A faixa do Termo de Adesão nas telas bloqueadas (issue #1768, PRD #1764).
 *
 * Quem está no Núcleo e ainda não assinou o Termo vê, na tela que não abre, a
 * faixa "Assine o Termo de Adesão para liberar este acesso" com o botão que
 * abre o documento pendente. O servidor é um dublê da rota `/api/nsp/meu-termo`.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";

import { TelaDoNucleo } from "./TelaDoNucleo";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const sessao = vi.hoisted(() => ({ participante: null as CurrentParticipante | null }));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante: sessao.participante, loading: false, error: null }),
}));

const FAIXA = "Assine o Termo de Adesão para liberar este acesso";
const DOCUMENTO = "https://storage.test/nsp-documentos/termos/envio-1.pdf?token=t";

let meuTermo: { pendente: boolean; documento_url: string | null };
let urls: string[] = [];

beforeEach(() => {
  urls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      urls.push(url);
      return new Response(JSON.stringify(meuTermo));
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessao.participante = null;
});

function entrar(recursos: string[]) {
  sessao.participante = { id: "P4", nome_completo: "Pessoa de Teste", email: "p@hsm", recursos_nsp: recursos };
}

function tela() {
  return render(
    <TelaDoNucleo titulo="Documentos" orientacao="Os documentos." recurso="documentos">
      <p>Conteúdo liberado</p>
    </TelaDoNucleo>
  );
}

describe("a faixa do Termo de Adesão", () => {
  it("o membro sem Termo vê a faixa com o botão que abre o documento pendente", async () => {
    entrar(["ver_modulo", "painel", "calendario", "agenda"]);
    meuTermo = { pendente: true, documento_url: DOCUMENTO };

    tela();

    expect(await screen.findByText(FAIXA)).toBeTruthy();
    const botao = screen.getByRole("link", { name: "Abrir o Termo de Adesão" });
    expect(botao.getAttribute("href")).toBe(DOCUMENTO);
    expect(botao.getAttribute("target")).toBe("_blank");
    expect(screen.queryByText("Conteúdo liberado")).toBeNull();
  });

  it("sem o documento gerado ainda, a faixa diz para falar com a Presidência", async () => {
    entrar(["ver_modulo", "painel"]);
    meuTermo = { pendente: true, documento_url: null };

    tela();

    expect(await screen.findByText(FAIXA)).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Abrir o Termo de Adesão" })).toBeNull();
    expect(screen.getByText(/Fale com a Presidência do Núcleo/)).toBeTruthy();
  });

  it("quem não tem Termo pendente vê a recusa de sempre, sem a faixa", async () => {
    entrar(["ver_modulo", "painel", "membros"]);
    meuTermo = { pendente: false, documento_url: null };

    tela();

    await waitFor(() => expect(urls).toContain("/api/nsp/meu-termo"));
    expect(screen.getByText("Esta tela ainda não está liberada para você.")).toBeTruthy();
    expect(screen.queryByText(FAIXA)).toBeNull();
  });

  it("a tela liberada não pergunta pelo Termo", () => {
    entrar(["ver_modulo", "documentos"]);
    meuTermo = { pendente: true, documento_url: DOCUMENTO };

    tela();

    expect(screen.getByText("Conteúdo liberado")).toBeTruthy();
    expect(urls).toEqual([]);
  });
});
