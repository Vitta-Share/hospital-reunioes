/**
 * @vitest-environment jsdom
 */

/**
 * Os anexos do caso na lista do Núcleo (issue #1988).
 *
 * O arquivo só sai pelo backend, com a sessão de quem abre: a tela pede a
 * rota do anexo com o token e abre o que voltou. Quem pode abrir é o servidor
 * que decide (`backend/tests/test_seguranca_do_paciente_anexos.py`).
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NotificacoesDoNucleo } from "./NotificacoesDoNucleo";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const CASO = {
  id: "n1",
  protocolo: "NSP-2026-0001",
  estado: "recebida",
  origem: "qr",
  relato: "O soro acabou e ninguém viu.",
  leito_ou_atendimento: null,
  setor_id: "setor-uti",
  setor: "UTI Adulto",
  data_ocorrencia: "2026-11-19",
  turno: "noite",
  hora_aproximada: null,
  chegou_ao_paciente: "nao",
  grave_ou_morte: null,
  percebido_ou_reclamacao: null,
  criado_em: "2026-11-20T10:00:00+00:00",
  anexos: [
    { id: "a1", content_type: "image/jpeg", tamanho_bytes: 700 * 1024 },
    { id: "a2", content_type: "application/pdf", tamanho_bytes: 300 * 1024 },
  ],
};

interface Chamada {
  url: string;
  autorizacao: string | null;
}

let chamadas: Chamada[] = [];
let respostaDoArquivo: { ok: boolean; status: number };
const abertos: string[] = [];

beforeEach(() => {
  chamadas = [];
  abertos.length = 0;
  respostaDoArquivo = { ok: true, status: 200 };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, autorizacao: new Headers(init?.headers).get("Authorization") });
      if (url === "/api/nsp/notificacoes") {
        return { ok: true, status: 200, json: async () => ({ notificacoes: [CASO] }) } as Response;
      }
      return {
        ...respostaDoArquivo,
        blob: async () => new Blob(["conteudo"], { type: "image/jpeg" }),
        json: async () => ({ detail: "Conteúdo restrito ao Núcleo de Segurança do Paciente" }),
      } as unknown as Response;
    })
  );
  URL.createObjectURL = vi.fn(() => "blob:anexo-de-teste");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    abertos.push(`${this.href} ${this.target}`);
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("os anexos do caso", () => {
  it("cada caso diz os seus anexos, foto e PDF", async () => {
    render(<NotificacoesDoNucleo />);

    const caso = await screen.findByRole("article", { name: "NSP-2026-0001" });
    const lista = within(caso).getByRole("list", { name: "Anexos" });
    expect(within(lista).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Foto 1 (700 KB)",
      "PDF 2 (300 KB)",
    ]);
  });

  it("abrir pede o arquivo ao backend com a sessão e abre o que voltou", async () => {
    render(<NotificacoesDoNucleo />);
    const caso = await screen.findByRole("article", { name: "NSP-2026-0001" });

    fireEvent.click(within(caso).getByRole("button", { name: "Foto 1 (700 KB)" }));

    await waitFor(() => expect(abertos).toEqual(["blob:anexo-de-teste _blank"]));
    expect(chamadas.at(-1)).toEqual({ url: "/api/nsp/notificacoes/n1/anexos/a1", autorizacao: "Bearer token-de-teste" });
  });

  it("a recusa do servidor aparece no caso e nada abre", async () => {
    respostaDoArquivo = { ok: false, status: 403 };
    render(<NotificacoesDoNucleo />);
    const caso = await screen.findByRole("article", { name: "NSP-2026-0001" });

    fireEvent.click(within(caso).getByRole("button", { name: "PDF 2 (300 KB)" }));

    await waitFor(() =>
      expect(within(caso).getByRole("alert").textContent).toBe("Conteúdo restrito ao Núcleo de Segurança do Paciente")
    );
    expect(abertos).toEqual([]);
  });

  it("caso sem anexo não mostra a lista", async () => {
    CASO.anexos = [];
    render(<NotificacoesDoNucleo />);
    const caso = await screen.findByRole("article", { name: "NSP-2026-0001" });

    expect(within(caso).queryByRole("list", { name: "Anexos" })).toBeNull();
  });
});
