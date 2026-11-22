/**
 * @vitest-environment jsdom
 */

/**
 * A Rota Especial na tela do caso e a contagem na lista (issue #1829). Quem
 * decide o que vale é o servidor; aqui se trava o que a tela mostra e o que
 * ela pede a ele.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CasoAberto, RotaEspecialDoCaso } from "@/lib/conduta/comite";

import { ContagemDaRotaEspecialNaLista, RotaEspecial } from "./RotaEspecial";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

type Parte = Pick<CasoAberto, "aviso_de_rota_especial" | "pode_desviar" | "rota_especial">;

const AVISO = "Este relato pode envolver a Direção, a Presidência ou a família proprietária.";
const ESPECIAL: RotaEspecialDoCaso = {
  selo: { selado_em: "2026-11-20T13:00:00+00:00", codigo: "ab".repeat(32), confere: true },
  nao_respondido_no_prazo: false,
  entrega: null,
  pode_registrar_entrega: true,
};

function desenhar(caso: Parte) {
  const enviar = vi.fn(async () => true);
  render(<RotaEspecial caso={caso} ocupado={false} enviar={enviar} />);
  return enviar;
}

describe("Aviso na fila comum", () => {
  it("mostra o aviso e o membro confirma o desvio", () => {
    const enviar = desenhar({ aviso_de_rota_especial: AVISO, pode_desviar: true, rota_especial: null });

    expect(screen.getByText(AVISO)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "CONFIRMAR DESVIO PARA A ROTA ESPECIAL" }));

    expect(enviar).toHaveBeenCalledWith("desvio-especial");
  });

  it("caso comum sem aviso não mostra nada da Rota Especial", () => {
    desenhar({ aviso_de_rota_especial: null, pode_desviar: false, rota_especial: null });

    expect(screen.queryByRole("region", { name: /Rota Especial/ })).toBeNull();
  });
});

describe("Caso da Rota Especial", () => {
  it("mostra o selo com data, hora e o código de integridade", () => {
    desenhar({ aviso_de_rota_especial: null, pode_desviar: false, rota_especial: ESPECIAL });

    expect(screen.getByText("Relato selado em 20/11/2026 às 10:00")).toBeTruthy();
    expect(screen.getByText(`Código de integridade: ${"ab".repeat(32)}`)).toBeTruthy();
  });

  it("mostra o registro permanente do prazo vencido sem parecer", () => {
    desenhar({
      aviso_de_rota_especial: null,
      pode_desviar: false,
      rota_especial: { ...ESPECIAL, nao_respondido_no_prazo: true },
    });

    expect(screen.getByRole("status").textContent).toBe("Caso não respondido no prazo");
  });

  it("o grupo registra a entrega do parecer com destinatário e data", () => {
    const enviar = desenhar({ aviso_de_rota_especial: null, pode_desviar: false, rota_especial: ESPECIAL });

    const form = screen.getByRole("form", { name: "Registrar a entrega do parecer" });
    const botao = within(form).getByRole("button", { name: "REGISTRAR ENTREGA DO PARECER" }) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
    fireEvent.change(within(form).getByLabelText("Entregue a"), { target: { value: " Presidente do Conselho " } });
    fireEvent.change(within(form).getByLabelText("Data da entrega"), { target: { value: "2026-11-20" } });
    fireEvent.click(botao);

    expect(enviar).toHaveBeenCalledWith("entrega-do-parecer", {
      destinatario: "Presidente do Conselho",
      entregue_em: "2026-11-20",
    });
  });

  it("depois da entrega mostra a quem e quando, sem o formulário", () => {
    desenhar({
      aviso_de_rota_especial: null,
      pode_desviar: false,
      rota_especial: {
        ...ESPECIAL,
        entrega: { destinatario: "Presidente do Conselho", entregue_em: "2026-11-20" },
        pode_registrar_entrega: false,
      },
    });

    expect(screen.getByText("Parecer entregue a Presidente do Conselho em 20/11/2026.")).toBeTruthy();
    expect(screen.queryByRole("form", { name: "Registrar a entrega do parecer" })).toBeNull();
  });
});

describe("Contagem na lista", () => {
  let chamadas: string[];

  beforeEach(() => {
    chamadas = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        chamadas.push(url);
        return { ok: true, status: 200, json: async () => ({ recebidos: 3, concluidos: 1, em_aberto: 2 }) } as Response;
      })
    );
  });

  it("de fora do grupo mostra só a contagem", async () => {
    render(<ContagemDaRotaEspecialNaLista />);

    await waitFor(() =>
      expect(screen.getByLabelText("Rota Especial").textContent).toBe(
        "Rota Especial: 3 recebidos, 1 concluídos, 2 em aberto."
      )
    );
    expect(chamadas).toEqual(["/api/comite-de-conduta/rota-especial/contagem"]);
  });
});
