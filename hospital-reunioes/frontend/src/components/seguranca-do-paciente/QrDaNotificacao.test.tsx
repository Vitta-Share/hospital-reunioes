/**
 * @vitest-environment jsdom
 */

/**
 * O QR e o endereço da notificação na Configuração (issue #2046).
 *
 * O servidor diz o endereço (no domínio do app) e devolve a imagem do QR; a
 * tela mostra os dois, deixa baixar a imagem e copiar o endereço. A leitura do
 * QR em si é conferida no backend (`test_seguranca_do_paciente_fundacao.py`).
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { QrDaNotificacao } from "./QrDaNotificacao";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const ENDERECO = "https://app.hsm.test/notificar";
const IMAGEM = new Blob(["png"], { type: "image/png" });

let escrito: string | null;
let qrResponde: boolean;
let chamadas: { url: string; auth: string | undefined }[];

beforeEach(() => {
  escrito = null;
  qrResponde = true;
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, opcoes?: RequestInit) => {
      chamadas.push({ url, auth: (opcoes?.headers as Record<string, string> | undefined)?.Authorization });
      if (url === "/api/nsp/configuracao") {
        return { ok: true, status: 200, json: async () => ({ colegiado: null, endereco_da_notificacao: ENDERECO }) };
      }
      if (url === "/api/nsp/configuracao/qr-da-notificacao.png") {
        if (!qrResponde) return { ok: false, status: 401, json: async () => ({}) };
        return { ok: true, status: 200, blob: async () => IMAGEM };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    })
  );
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: {
      writeText: vi.fn(async (texto: string) => {
        escrito = texto;
      }),
    },
  });
  URL.createObjectURL = vi.fn(() => "blob:qr-da-notificacao");
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("a seção QR e endereço da notificação", () => {
  it("abre com o título e a linha de orientação", async () => {
    render(<QrDaNotificacao />);

    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("QR e endereço da notificação");
    expect(
      screen.getByText(
        "Imprima o QR no cartaz ou use como papel de parede. Com o endereço, a TI cria o ícone nos computadores."
      ).tagName
    ).toBe("P");
  });

  it("mostra o QR pedido ao servidor com o token, e o botão baixa a imagem", async () => {
    render(<QrDaNotificacao />);

    const qr = await screen.findByRole("img", { name: "QR da notificação de incidente" });
    expect(qr.getAttribute("src")).toBe("blob:qr-da-notificacao");
    expect(chamadas).toContainEqual({
      url: "/api/nsp/configuracao/qr-da-notificacao.png",
      auth: "Bearer token-de-teste",
    });
    const baixar = screen.getByRole("link", { name: "Baixar o QR" });
    expect(baixar.getAttribute("href")).toBe("blob:qr-da-notificacao");
    expect(baixar.getAttribute("download")).toBe("qr-notificacao-nsp.png");
  });

  it("mostra o endereço completo e o botão Copiar põe esse endereço na área de transferência", async () => {
    render(<QrDaNotificacao />);

    expect(await screen.findByText(ENDERECO)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Copiar" }));

    await waitFor(() => expect(escrito).toBe(ENDERECO));
    expect(await screen.findByRole("button", { name: "Copiado" })).toBeTruthy();
  });

  it("avisa quando o QR não carrega, sem o botão Baixar o QR", async () => {
    qrResponde = false;
    render(<QrDaNotificacao />);

    expect(await screen.findByText("Não foi possível carregar o QR. Recarregue a página.")).toBeTruthy();
    expect(screen.queryByRole("img", { name: "QR da notificação de incidente" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Baixar o QR" })).toBeNull();
  });
});
