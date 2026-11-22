/**
 * @vitest-environment jsdom
 */

/**
 * Gestão de POPs (issue #2044).
 *
 * 1. A janela "Criar novo POP" abria muito abaixo da tela: o modal usava
 *    `position: fixed` dentro do miolo da página, que anima com `transform`
 *    (`animate-fade-in-up`). Com transform num ancestral, o fixed se ancora
 *    nele e não na tela. O modal agora sai por portal no `document.body`,
 *    como os outros modais do app (AdminModal, ModalPortal). O jsdom não mede
 *    layout: o que dá para provar é que o modal não fica dentro do ancestral.
 * 2. O Elaborador designado, sem papel de admin, vê o POP atribuído a ele na
 *    lista e o link Elaborar leva à tela de elaboração do POP.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";
import type { Pop } from "@/types";

import { PopsManager } from "./PopsManager";

let participante: { id: string; nome_completo: string; email: string; perfil_pop: string } = {
  id: "P_SUPER",
  nome_completo: "Superadmin",
  email: "super@hsm.com",
  perfil_pop: "superadmin",
};

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ token: "tok", userId: "U_1", userEmail: null, loading: false }),
}));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante, loading: false }),
}));

const POP_DO_LUCAS: Pop = {
  id: "pop-ti-1",
  codigo: "HSM_TI-001",
  nome: "Gestão de acesso e assinatura eletrônica MV",
  setor_id: "s-ti",
  setor_nome: "Tecnologia da Informação",
  setor_sigla: "TI",
  criticidade: "MEDIA",
  base_normativa: null,
  periodicidade_revisao: "1_ano",
  prazo_elaboracao_dias: 15,
  prazo_revisao_dias: 30,
  elaborador_id: "P_LUCAS",
  revisor_id: "P_REV",
  validador_id: "P_VAL",
  criado_por: "P_SUPER",
  created_at: null,
  versao: { id: "v-1", numero_versao: "1.0", estado: "A_ELABORAR" },
} as Pop;

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const body = url === "/api/pops" ? [POP_DO_LUCAS] : [];
      return { ok: true, status: 200, json: async () => body } as unknown as Response;
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function montar() {
  // O miolo da página /pops anima com transform: é o ancestral que prendia o modal.
  return render(
    <ToastProvider>
      <div data-testid="miolo" className="animate-fade-in-up">
        <PopsManager />
      </div>
    </ToastProvider>,
  );
}

describe("Criar novo POP (issue #2044)", () => {
  it("abre a janela fora do miolo animado, presa à tela e não à página", async () => {
    montar();
    fireEvent.click(await screen.findByRole("button", { name: /Criar novo POP/i }));

    const titulo = await screen.findByRole("heading", { name: "Criar novo POP" });
    expect(screen.getByTestId("miolo").contains(titulo)).toBe(false);
    expect(document.body.contains(titulo)).toBe(true);
  });

  it("a janela de Papéis também abre fora do miolo animado", async () => {
    montar();
    fireEvent.click(await screen.findByRole("button", { name: /Papéis/i }));

    const titulo = await screen.findByRole("heading", { name: "Editar papéis do POP" });
    expect(screen.getByTestId("miolo").contains(titulo)).toBe(false);
    expect(document.body.contains(titulo)).toBe(true);
  });
});

describe("Elaborador designado (issue #2044)", () => {
  it("vê o POP atribuído e o link Elaborar abre a tela de elaboração", async () => {
    participante = {
      id: "P_LUCAS",
      nome_completo: "Lucas",
      email: "lucas@hsm.com",
      perfil_pop: "coordenador",
    };
    montar();

    expect(await screen.findByText("Gestão de acesso e assinatura eletrônica MV")).toBeTruthy();
    const elaborar = screen.getByRole("link", { name: /Elaborar/i });
    expect(elaborar.getAttribute("href")).toBe("/pops/pop-ti-1/elaboracao");
  });
});
