/**
 * @vitest-environment jsdom
 */

/**
 * Os anexos no formulário de notificação (issue #1988, PRD #1979).
 *
 * Até 3 fotos ou PDFs, somando menos de 9 MB; a foto grande é reduzida antes
 * do envio. Com arquivo, o envio vai em multipart (o relato em `dados`, os
 * arquivos em `anexos`); sem arquivo, segue o JSON de sempre, conferido em
 * `FormularioDeNotificacao.test.tsx`. A régua do servidor está em
 * `backend/tests/test_seguranca_do_paciente_anexos.py`.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FormularioDeNotificacao } from "./FormularioDeNotificacao";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const MB = 1024 * 1024;

interface Envio {
  url: string;
  corpo: BodyInit | null | undefined;
  tipo: string | null;
}

let envios: Envio[] = [];
let respostaDoEnvio: { status: number; corpo: unknown };

beforeEach(() => {
  envios = [];
  respostaDoEnvio = { status: 201, corpo: { protocolo: "NSP-2026-0007", criado_em: null, anexos_guardados: true } };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/nsp/publico/setores") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ setores: [{ id: "setor-uti", nome: "UTI Adulto" }] }),
        } as Response;
      }
      envios.push({ url, corpo: init?.body, tipo: new Headers(init?.headers).get("Content-Type") });
      const { status, corpo } = respostaDoEnvio;
      return { ok: status < 300, status, json: async () => corpo } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function arquivo(nome: string, tamanho: number, tipo: string): File {
  return new File([new Uint8Array(tamanho)], nome, { type: tipo });
}

function escolherArquivos(...arquivos: File[]) {
  fireEvent.change(screen.getByLabelText(/Fotos ou PDF/), { target: { files: arquivos } });
}

function anexados(): string[] {
  const lista = screen.queryByRole("list", { name: "Arquivos anexados" });
  return lista ? within(lista).getAllByRole("listitem").map((item) => item.textContent ?? "") : [];
}

function botao(nome: string | RegExp) {
  return screen.getByRole("button", { name: nome }) as HTMLButtonElement;
}

function escolher(grupo: string, opcao: string) {
  fireEvent.click(within(screen.getByRole("group", { name: grupo })).getByRole("button", { name: opcao }));
}

async function irAteOEnvio() {
  fireEvent.change(screen.getByLabelText("O que aconteceu"), { target: { value: "O soro acabou e ninguém viu." } });
  fireEvent.click(botao("Continuar"));
  await waitFor(() => expect(screen.getByRole("option", { name: "UTI Adulto" })).toBeTruthy());
  fireEvent.change(screen.getByLabelText("Setor"), { target: { value: "setor-uti" } });
  escolher("Turno", "Noite");
  fireEvent.click(botao("Continuar"));
  escolher("O incidente chegou ao paciente?", "Não chegou");
  fireEvent.click(botao("Continuar"));
  escolher("Como você quer notificar?", "Sem me identificar");
  fireEvent.click(botao("Enviar notificação"));
}

/** O canvas do jsdom não desenha: a foto vira um JPEG do tamanho pedido. */
function prepararReducao(tamanhoDoResultado: number) {
  vi.stubGlobal(
    "createImageBitmap",
    vi.fn(async () => ({ width: 4032, height: 3024, close: () => {} }))
  );
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    drawImage: () => {},
  } as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(function (callback, tipo) {
    callback(new Blob([new Uint8Array(tamanhoDoResultado)], { type: tipo }));
  });
}

describe("anexar no celular", () => {
  it("a primeira tela aceita foto e PDF, até três, e diz o limite", async () => {
    render(<FormularioDeNotificacao porta="qr" />);

    const campo = screen.getByLabelText(/Fotos ou PDF/) as HTMLInputElement;
    expect(campo.type).toBe("file");
    expect(campo.multiple).toBe(true);
    expect(campo.accept).toBe("image/*,application/pdf");
    expect(screen.getByText(/Até 3 arquivos, somando menos de 9 MB/)).toBeTruthy();

    escolherArquivos(arquivo("corredor.jpg", 300 * 1024, "image/jpeg"), arquivo("escala.pdf", 200 * 1024, "application/pdf"));
    await waitFor(() => expect(anexados()).toHaveLength(2));
    escolherArquivos(arquivo("leito.png", 100 * 1024, "image/png"));
    await waitFor(() => expect(anexados()).toHaveLength(3));
    expect(anexados()[0]).toContain("corredor.jpg");
  });

  it("o quarto arquivo é recusado com a mensagem, e os três ficam", async () => {
    render(<FormularioDeNotificacao porta="qr" />);
    escolherArquivos(...["a", "b", "c"].map((n) => arquivo(`${n}.jpg`, 1000, "image/jpeg")));
    await waitFor(() => expect(anexados()).toHaveLength(3));

    escolherArquivos(arquivo("d.jpg", 1000, "image/jpeg"));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("Você pode anexar até 3 arquivos."));
    expect(anexados()).toHaveLength(3);
  });

  it("o tipo não aceito e a soma acima do limite são recusados com a mensagem", async () => {
    render(<FormularioDeNotificacao porta="qr" />);

    escolherArquivos(arquivo("planilha.xlsx", 1000, "application/vnd.ms-excel"));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/planilha\.xlsx não é aceito/));
    expect(anexados()).toEqual([]);

    escolherArquivos(arquivo("a.pdf", 5 * MB, "application/pdf"), arquivo("b.pdf", 4 * MB, "application/pdf"));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/precisam somar menos de 9 MB/));
    expect(anexados()).toEqual([]);
  });

  it("tirar um arquivo da lista abre espaço para outro", async () => {
    render(<FormularioDeNotificacao porta="qr" />);
    escolherArquivos(...["a", "b", "c"].map((n) => arquivo(`${n}.jpg`, 1000, "image/jpeg")));
    await waitFor(() => expect(anexados()).toHaveLength(3));

    fireEvent.click(botao("Tirar b.jpg"));

    expect(anexados().map((t) => t.split(" ")[0])).toEqual(["a.jpg", "c.jpg"]);
  });
});

describe("enviar com arquivo", () => {
  it("a foto grande é reduzida antes e vai em multipart com o relato, abaixo do corte do proxy", async () => {
    prepararReducao(700 * 1024);
    render(<FormularioDeNotificacao porta="qr" />);
    escolherArquivos(arquivo("IMG_0001.jpg", 12 * MB, "image/jpeg"), arquivo("escala.pdf", 300 * 1024, "application/pdf"));
    await waitFor(() => expect(anexados()).toHaveLength(2));
    expect(screen.queryByRole("alert")).toBeNull();

    await irAteOEnvio();

    await waitFor(() => expect(screen.getByText("Notificação registrada")).toBeTruthy());
    const [envio] = envios;
    expect(envio.url).toBe("/api/nsp/publico/notificacoes");
    // O navegador põe o boundary do multipart: o Content-Type não vai à mão.
    expect(envio.tipo).toBeNull();
    const corpo = envio.corpo as FormData;
    expect(corpo).toBeInstanceOf(FormData);
    expect(JSON.parse(String(corpo.get("dados")))).toMatchObject({ origem: "qr", anonimo: true, setor_id: "setor-uti" });
    const enviados = corpo.getAll("anexos") as File[];
    expect(enviados.map((f) => [f.name, f.type, f.size])).toEqual([
      ["IMG_0001.jpg", "image/jpeg", 700 * 1024],
      ["escala.pdf", "application/pdf", 300 * 1024],
    ]);
    expect(enviados.reduce((total, f) => total + f.size, 0)).toBeLessThan(9 * MB);
  });

  it("a recusa do servidor aparece na tela, com o relato e os arquivos ainda lá", async () => {
    respostaDoEnvio = { status: 415, corpo: { detail: "O arquivo x.gif não é aceito. Envie foto (JPG, PNG, WEBP ou HEIC) ou PDF." } };
    render(<FormularioDeNotificacao porta="qr" />);
    escolherArquivos(arquivo("a.jpg", 1000, "image/jpeg"));
    await waitFor(() => expect(anexados()).toHaveLength(1));

    await irAteOEnvio();

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/x\.gif não é aceito/));
  });

  it("se os arquivos não ficaram guardados, a confirmação avisa", async () => {
    respostaDoEnvio = { status: 201, corpo: { protocolo: "NSP-2026-0008", criado_em: null, anexos_guardados: false } };
    render(<FormularioDeNotificacao porta="qr" />);
    escolherArquivos(arquivo("a.jpg", 1000, "image/jpeg"));
    await waitFor(() => expect(anexados()).toHaveLength(1));

    await irAteOEnvio();

    await waitFor(() => expect(screen.getByText("Notificação registrada")).toBeTruthy());
    expect(screen.getByText(/não conseguimos guardar os arquivos/)).toBeTruthy();
  });
});
