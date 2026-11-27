/**
 * @vitest-environment jsdom
 */

/**
 * O Atualizar que fecha a Ata (issue #2085).
 *
 * Com todos assinados na ClickSign e o webhook de fechamento perdido, o
 * backend fecha a Ata na própria leitura do status e devolve `finalizada`.
 * A tela precisa recarregar a Reunião nessa hora: sem isso, o card seguiria
 * dizendo "Aguardando assinatura" com a Ata já ASSINADA no banco.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";

import { SignatariosCard } from "./SignatariosCard";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "tok" } } }),
    },
  }),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function statusCom(finalizada: boolean) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        total: 2,
        assinaram: 2,
        envelope_id: "env-1",
        signatarios: [],
        pendencias_criadas: 10,
        total_acoes: 10,
        finalizada,
      }),
    })),
  );
}

function renderCard(onDesfecho: () => void) {
  render(
    <ToastProvider>
      <SignatariosCard idReuniao="R1" envelopeKey="doc-1" enabled={false} onDesfecho={onDesfecho} />
    </ToastProvider>,
  );
}

describe("SignatariosCard, o Atualizar que fecha a Ata", () => {
  it("recarrega a Reunião quando a leitura do status finalizou a Ata", async () => {
    statusCom(true);
    const onDesfecho = vi.fn();
    renderCard(onDesfecho);

    await waitFor(() => {
      expect(onDesfecho).toHaveBeenCalledTimes(1);
    });
  });

  it("não recarrega quando a Ata segue aguardando", async () => {
    statusCom(false);
    const onDesfecho = vi.fn();
    renderCard(onDesfecho);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled();
    });
    expect(onDesfecho).not.toHaveBeenCalled();
  });
});

// Issue #1904: a Ata assinada por todos que o diretor sincronizou e seguiu em
// "Aguardando assinatura digital". O Sincronizar que finaliza recarrega a
// Reunião, e a página troca o card pelo banner de Ata Assinada.
describe("SignatariosCard, o Sincronizar que fecha a Ata", () => {
  function servirSincronizar(desfecho: string) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const corpo = url.endsWith("/signatarios/sincronizar")
          ? { desfecho }
          : {
              total: 2,
              assinaram: 2,
              envelope_id: "env-1",
              signatarios: [],
              pendencias_criadas: 0,
              total_acoes: 20,
              finalizada: false,
            };
        return { ok: true, status: 200, json: async () => corpo };
      }),
    );
  }

  it("recarrega a Reunião quando o Sincronizar finalizou a Ata", async () => {
    servirSincronizar("finalizada");
    const onDesfecho = vi.fn();
    renderCard(onDesfecho);

    fireEvent.click(await screen.findByRole("button", { name: "Sincronizar com a ClickSign" }));

    await waitFor(() => {
      expect(onDesfecho).toHaveBeenCalledTimes(1);
    });
  });

  it("não recarrega quando o Sincronizar não mudou nada", async () => {
    servirSincronizar("sem_mudanca");
    const onDesfecho = vi.fn();
    renderCard(onDesfecho);

    fireEvent.click(await screen.findByRole("button", { name: "Sincronizar com a ClickSign" }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/reunioes/R1/signatarios/sincronizar",
        expect.objectContaining({ method: "POST" }),
      );
    });
    expect(onDesfecho).not.toHaveBeenCalled();
  });
});
