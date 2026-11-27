/**
 * @vitest-environment jsdom
 */

/**
 * A área Mensagens da tela do caso (issue #1845): a coordenação pergunta a
 * quem relatou (com as perguntas que o agente sugeriu), vê o complemento,
 * arquiva o pedido sem resposta em 15 dias e reabre o arquivado. O servidor
 * decide o que vale; aqui se trava o que a tela pede a ele.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MensagensDoCaso as Dados } from "@/lib/conduta/mensagens";

import { MensagensDoCaso } from "./MensagensDoCaso";

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
      return { ok: true, status: 200, json: async () => ({}) } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const VAZIO: Dados = {
  itens: [],
  aguardando_resposta: false,
  pode_perguntar: true,
  perguntas_sugeridas: ["Quando foi?", "Alguém mais viu?"],
  arquivar_a_partir_de: null,
  pode_arquivar: false,
  arquivado: false,
  pode_reabrir: false,
};

const CONVERSA: Dados = {
  ...VAZIO,
  itens: [
    { id: "m1", tipo: "pergunta", de: "comite", texto: "Quando foi?", enviada_em: "2026-11-01T12:00:00+00:00" },
    { id: "m2", tipo: "complemento", de: "relator", texto: "Numa terça.", enviada_em: "2026-11-03T12:00:00+00:00" },
  ],
};

describe("Mensagens do caso", () => {
  it("a coordenação envia a pergunta, partindo da sugestão do agente", async () => {
    const aoMudar = vi.fn();
    render(<MensagensDoCaso casoId="c1" dados={VAZIO} aoMudar={aoMudar} />);

    fireEvent.click(screen.getByRole("button", { name: "Alguém mais viu?" }));
    expect((screen.getByLabelText("Pergunta a quem relatou") as HTMLTextAreaElement).value).toBe("Alguém mais viu?");
    fireEvent.click(screen.getByRole("button", { name: "ENVIAR PERGUNTA" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas).toEqual([
      { url: "/api/comite-de-conduta/casos/c1/mensagens", method: "POST", body: { texto: "Alguém mais viu?" } },
    ]);
  });

  it("mostra a pergunta do Comitê e o complemento de quem relatou", () => {
    render(<MensagensDoCaso casoId="c1" dados={CONVERSA} aoMudar={() => {}} />);

    expect(screen.getByText("Pergunta do Comitê")).toBeTruthy();
    expect(screen.getByText("Complemento de quem relatou")).toBeTruthy();
    expect(screen.getByText("Numa terça.")).toBeTruthy();
  });

  it("quem não é da coordenação lê a conversa, sem o campo de pergunta", () => {
    render(<MensagensDoCaso casoId="c1" dados={{ ...CONVERSA, pode_perguntar: false }} aoMudar={() => {}} />);

    expect(screen.queryByLabelText("Pergunta a quem relatou")).toBeNull();
  });

  it("o pedido sem resposta diz quando o arquivamento fica disponível", () => {
    const dados = { ...CONVERSA, aguardando_resposta: true, arquivar_a_partir_de: "2026-12-07" };
    render(<MensagensDoCaso casoId="c1" dados={dados} aoMudar={() => {}} />);

    expect(screen.getByText(/Arquivar por falta de elementos fica disponível em 07\/12\/2026/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "ARQUIVAR POR FALTA DE ELEMENTOS" })).toBeNull();
  });

  it("depois de 15 dias, a coordenação arquiva", async () => {
    const aoMudar = vi.fn();
    const dados = { ...CONVERSA, aguardando_resposta: true, arquivar_a_partir_de: "2026-11-16", pode_arquivar: true };
    render(<MensagensDoCaso casoId="c1" dados={dados} aoMudar={aoMudar} />);

    fireEvent.click(screen.getByRole("button", { name: "ARQUIVAR POR FALTA DE ELEMENTOS" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas[0]).toEqual({ url: "/api/comite-de-conduta/casos/c1/arquivamento", method: "POST", body: null });
  });

  it("o caso arquivado com complemento novo reabre", async () => {
    const aoMudar = vi.fn();
    const dados = { ...CONVERSA, pode_perguntar: false, arquivado: true, pode_reabrir: true };
    render(<MensagensDoCaso casoId="c1" dados={dados} aoMudar={aoMudar} />);

    fireEvent.click(screen.getByRole("button", { name: "REABRIR CASO" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas[0]).toEqual({ url: "/api/comite-de-conduta/casos/c1/reabertura", method: "POST", body: null });
  });
});
