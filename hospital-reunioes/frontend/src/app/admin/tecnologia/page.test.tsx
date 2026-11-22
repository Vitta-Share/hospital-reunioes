/**
 * @vitest-environment jsdom
 */

/**
 * A página da aba Tecnologia lê o `?pergunta=<id>` do endereço (issue #2118):
 * é o link do sino e do e-mail da Pergunta da Vitta, e abre a aba com o cartão
 * dela em foco.
 */

import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";

import TecnologiaPage from "./page";

let endereco = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => endereco,
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ token: "token-de-teste", userId: "auth-1", userEmail: "p1@hsm", loading: false }),
}));

const PERGUNTA = {
  demanda_id: "d-9",
  demanda: "A Ata assinada no app",
  projeto: "Aplicativo do Hospital",
  assunto: "quem assina a Ata",
  texto: "Quem assina a Ata em nome da diretoria?",
  por_que_precisa: "Só a diretoria decide.",
  o_que_esta_parado: "A tela de assinatura.",
  o_que_anda_depois: "A tela sai.",
  ganho: "A ata sai no mesmo dia.",
  estado: "aberta",
  criado_em: "2026-11-18T10:00:00Z",
  minha: true,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("A página da aba Tecnologia", () => {
  it("o ?pergunta= do link do sino e do e-mail abre a aba com o cartão dessa Pergunta em foco", async () => {
    endereco = new URLSearchParams("pergunta=p-2");
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const corpo = url.endsWith("/eu")
          ? { desenvolvedor: false }
          : url.endsWith("/perguntas/esperando")
            ? [
                { ...PERGUNTA, id: "p-1" },
                { ...PERGUNTA, id: "p-2", demanda_id: "d-2", demanda: "A agenda do diretor" },
              ]
            : [];
        return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
      }),
    );

    render(
      <ToastProvider>
        <TecnologiaPage />
      </ToastProvider>,
    );

    const lista = await screen.findByRole("region", { name: "Esperando você" });
    const [primeiro, segundo] = within(lista).getAllByRole("listitem");
    await waitFor(() => expect(document.activeElement).toBe(segundo));
    expect(segundo.getAttribute("aria-current")).toBe("true");
    expect(primeiro.getAttribute("aria-current")).toBeNull();
  });
});
