/**
 * @vitest-environment jsdom
 */

/**
 * Os anexos do relato do Canal de Conduta (issue #1844): imagem, PDF e áudio
 * no passo 4, com o aviso de que os dados de origem do arquivo são apagados.
 * Formato fora da lista é recusado na hora e o relato segue sem ele. Os
 * anexos sobem depois do relato, com o protocolo e o código, e o nome do
 * arquivo não sai do aparelho.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RelatoEmPassos } from "./RelatoEmPassos";

const PROTOCOLO = { protocolo: "CC-K7M4-Q2XT", codigo: "ABCD234567", voltar_a_partir_de: "2026-11-27" };
const AVISO = "Os dados de origem do arquivo são apagados automaticamente.";
const RECUSA =
  "Este arquivo não pode ser anexado. O canal aceita foto (JPG, PNG ou WEBP), PDF e áudio (MP3, M4A, OGG ou WAV).";

let chamadas: { url: string; body: BodyInit | null | undefined }[];
let respostaDoAnexo: () => Response;

function json(status: number, corpo: unknown): Response {
  return new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  chamadas = [];
  respostaDoAnexo = () => json(201, { id: "a1", tipo: "imagem" });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, body: init?.body });
      if (url.endsWith("/textos")) return json(200, { textos: {} });
      if (url.endsWith("/relatos")) return json(201, PROTOCOLO);
      if (url.endsWith("/relatos/anexos")) return respostaDoAnexo();
      return json(404, { detail: "Not Found" });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const clicar = (nome: string | RegExp) => fireEvent.click(screen.getByRole("button", { name: nome }));
const continuar = () => clicar("Continuar");
const escolher = (grupo: string | RegExp, opcao: string | RegExp) =>
  fireEvent.click(within(screen.getByRole("group", { name: grupo })).getByRole("button", { name: opcao }));

function arquivo(nome: string, tamanho = 1024): File {
  const conteudo = new File([new Uint8Array(8)], nome);
  Object.defineProperty(conteudo, "size", { value: tamanho });
  return conteudo;
}

async function ateOPasso4() {
  render(<RelatoEmPassos />);
  clicar("Fazer relato");
  await screen.findByText("Você pode relatar sem se identificar.");
  fireEvent.click(screen.getByLabelText("Li as orientações. Relato o que acredito ser verdade."));
  continuar();
  escolher("Identificação", /Anônimo/);
  continuar();
  escolher("O relato envolve a Direção, a Presidência ou a família proprietária?", "Não");
  continuar();
  fireEvent.change(screen.getByLabelText("O que aconteceu?"), { target: { value: "Sumiram caixas da farmácia." } });
}

const anexar = (...arquivos: File[]) =>
  fireEvent.change(screen.getByLabelText(/Anexos/), { target: { files: arquivos } });
const anexosEnviados = () => chamadas.filter((c) => c.url.endsWith("/relatos/anexos"));

describe("os anexos no passo 4", () => {
  it("aceita imagem, PDF e áudio e avisa que os dados de origem são apagados", async () => {
    await ateOPasso4();

    expect(screen.getByText(AVISO)).toBeTruthy();
    const seletor = screen.getByLabelText(/Anexos/) as HTMLInputElement;
    expect(seletor.type).toBe("file");
    for (const extensao of [".jpg", ".png", ".webp", ".pdf", ".mp3", ".m4a", ".ogg", ".wav"]) {
      expect(seletor.accept.split(",")).toContain(extensao);
    }

    anexar(arquivo("foto.JPG"), arquivo("documento.pdf"), arquivo("audio.m4a"));

    const lista = within(screen.getByRole("list", { name: "Arquivos anexados" })).getAllByRole("listitem");
    expect(lista).toHaveLength(3);
  });

  it("recusa na hora o formato fora da lista, com a mensagem, e o relato segue sem ele", async () => {
    await ateOPasso4();

    anexar(arquivo("IMG_0042.HEIC"), arquivo("foto.png"));

    expect(screen.getByRole("alert").textContent).toContain(RECUSA);
    const lista = within(screen.getByRole("list", { name: "Arquivos anexados" })).getAllByRole("listitem");
    expect(lista.map((item) => item.textContent)).toEqual([expect.stringContaining("foto.png")]);

    continuar();
    clicar("Enviar");
    await screen.findByText("Relato registrado");
    expect(anexosEnviados()).toHaveLength(1);
  });

  it("recusa o arquivo acima do tamanho", async () => {
    await ateOPasso4();

    anexar(arquivo("gravacao.mp3", 51 * 1024 * 1024));

    expect(screen.getByRole("alert").textContent).toContain("O áudio passa de 50 MB.");
    expect(screen.queryByRole("list", { name: "Arquivos anexados" })).toBeNull();
  });

  it("deixa remover um anexo antes de enviar", async () => {
    await ateOPasso4();
    anexar(arquivo("foto.jpg"));

    clicar("Remover foto.jpg");

    expect(screen.queryByRole("list", { name: "Arquivos anexados" })).toBeNull();
  });
});

describe("o envio dos anexos", () => {
  it("sobe cada anexo depois do relato, com o protocolo e o código, sem o nome do arquivo", async () => {
    await ateOPasso4();
    anexar(arquivo("Foto da Joana.jpg"), arquivo("audio.ogg"));
    continuar();

    expect(screen.getByText("Anexos")).toBeTruthy();
    expect(screen.getByText("2 arquivos")).toBeTruthy();
    clicar("Enviar");
    await screen.findByText("Relato registrado");

    await waitFor(() => expect(anexosEnviados()).toHaveLength(2));
    const corpo = anexosEnviados()[0].body as FormData;
    expect(corpo.get("protocolo")).toBe(PROTOCOLO.protocolo);
    expect(corpo.get("codigo")).toBe(PROTOCOLO.codigo);
    expect((corpo.get("arquivo") as File).name).toBe("anexo");
    expect(screen.getByText("2 anexos guardados.")).toBeTruthy();
  });

  it("o anexo que o servidor recusa aparece no protocolo, e o relato fica registrado", async () => {
    respostaDoAnexo = () => json(415, { detail: RECUSA });
    await ateOPasso4();
    anexar(arquivo("foto.jpg"));
    continuar();

    clicar("Enviar");

    await screen.findByText("Relato registrado");
    expect(screen.getByText(PROTOCOLO.protocolo)).toBeTruthy();
    expect(await screen.findByText(`foto.jpg: ${RECUSA}`)).toBeTruthy();
  });
});
