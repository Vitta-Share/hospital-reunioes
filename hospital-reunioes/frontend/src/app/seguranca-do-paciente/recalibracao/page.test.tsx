/**
 * @vitest-environment jsdom
 */

/**
 * A recalibração do agente (issue #2001) abre para quem confirma a triagem,
 * com a linha de orientação no topo, e a concordância do agente aparece na
 * Configuração só para quem confirma a triagem: o super admin abre a
 * Configuração técnica e não vê os casos.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";

import RecalibracaoPage from "./page";
import ConfiguracaoPage from "../configuracao/page";

const sessao = vi.hoisted(() => ({ participante: null as CurrentParticipante | null }));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante: sessao.participante, loading: false, error: null }),
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { getSession: async () => ({ data: { session: null } }) } }),
}));
vi.mock("@/components/seguranca-do-paciente/RecalibracaoDoAgente", () => ({
  RecalibracaoDoAgente: () => <p>Os itens</p>,
}));
vi.mock("@/components/seguranca-do-paciente/ConcordanciaDoAgente", () => ({
  ConcordanciaDoAgente: () => <p>A concordância</p>,
}));
vi.mock("@/components/seguranca-do-paciente/CortesDeFrequencia", () => ({ CortesDeFrequencia: () => null }));
vi.mock("@/components/seguranca-do-paciente/QrDaNotificacao", () => ({ QrDaNotificacao: () => null }));

function entrar(recursos: string[]) {
  sessao.participante = { id: "p1", nome_completo: "Pessoa de Teste", email: "pessoa@hsm", recursos_nsp: recursos };
}

afterEach(() => {
  cleanup();
  sessao.participante = null;
});

describe("a recalibração do agente", () => {
  it("abre para quem confirma a triagem, com a orientação no topo", () => {
    entrar(["ver_modulo", "triagem"]);
    render(<RecalibracaoPage />);

    expect(
      screen.getByText(
        "Leia os itens da auditoria e registre a decisão sobre o agente: manter, ajustar ou ligar a aprovação em lote."
      )
    ).toBeTruthy();
    expect(screen.getByText("Os itens")).toBeTruthy();
  });

  it("fica fechada para quem não confirma a triagem", () => {
    entrar(["ver_modulo", "casos"]);
    render(<RecalibracaoPage />);

    expect(screen.queryByText("Os itens")).toBeNull();
  });
});

describe("a Configuração", () => {
  it("mostra a concordância do agente a quem confirma a triagem", () => {
    entrar(["ver_modulo", "configuracao", "triagem"]);
    render(<ConfiguracaoPage />);

    expect(screen.getByText("A concordância")).toBeTruthy();
  });

  it("não mostra a concordância ao super admin, que só abre a Configuração", () => {
    entrar(["configuracao"]);
    render(<ConfiguracaoPage />);

    expect(screen.queryByText("A concordância")).toBeNull();
  });
});
