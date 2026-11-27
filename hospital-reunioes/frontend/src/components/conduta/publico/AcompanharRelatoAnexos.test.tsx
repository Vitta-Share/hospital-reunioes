/**
 * @vitest-environment jsdom
 */

/**
 * O anexo no complemento do acompanhamento (issue #2187): imagem, PDF e áudio,
 * com o mesmo aviso do passo "O que aconteceu". O anexo sobe pela mesma rota
 * do relato, com origem "complemento", depois do complemento enviado. Formato
 * fora da lista é recusado na hora e o complemento segue sem ele.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AcompanharRelato } from "./AcompanharRelato";

const PROTOCOLO = "CC-K7M4-Q2XT";
const CODIGO = "ABCDE-23456";
const COMPLEMENTO = "Mando a foto da porta do almoxarifado.";
const AVISO = "Os dados de origem do arquivo são apagados automaticamente.";
const RECUSA =
  "Este arquivo não pode ser anexado. O canal aceita foto (JPG, PNG ou WEBP), PDF e áudio (MP3, M4A, OGG ou WAV).";

const AGUARDANDO = {
  protocolo: PROTOCOLO,
  situacao: "Aguardando sua resposta",
  mensagens: [{ de: "comite", tipo: "pergunta", texto: "Tem foto?", em: "2026-11-20T15:00:00+00:00" }],
};
const RESPONDIDO = {
  protocolo: PROTOCOLO,
  situacao: "Em análise",
  mensagens: [
    ...AGUARDANDO.mensagens,
    { de: "voce", tipo: "complemento", texto: COMPLEMENTO, em: "2026-11-21T15:00:00+00:00" },
  ],
};

let chamadas: { url: string; body: BodyInit | null | undefined }[];
let respostaDoAnexo: () => Response | Promise<Response>;

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
      if (url.endsWith("/acompanhamento")) return json(200, AGUARDANDO);
      if (url.endsWith("/acompanhamento/complemento")) return json(200, RESPONDIDO);
      if (url.endsWith("/relatos/anexos")) return respostaDoAnexo();
      return json(404, { detail: "Not Found" });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function arquivo(nome: string, tamanho = 1024): File {
  const conteudo = new File([new Uint8Array(8)], nome);
  Object.defineProperty(conteudo, "size", { value: tamanho });
  return conteudo;
}

const digitar = (rotulo: string | RegExp, valor: string) =>
  fireEvent.change(screen.getByLabelText(rotulo), { target: { value: valor } });
const anexar = (...arquivos: File[]) =>
  fireEvent.change(screen.getByLabelText(/Anexos/), { target: { files: arquivos } });
const anexosEnviados = () => chamadas.filter((c) => c.url.endsWith("/relatos/anexos"));
const complementosEnviados = () => chamadas.filter((c) => c.url.endsWith("/acompanhamento/complemento"));

async function entrar() {
  render(<AcompanharRelato />);
  digitar("Protocolo", PROTOCOLO);
  digitar("Código", CODIGO);
  fireEvent.click(screen.getByRole("button", { name: "Acompanhar" }));
  await screen.findByText("Tem foto?");
}

function enviarComplemento() {
  digitar("Complemento", COMPLEMENTO);
  fireEvent.click(screen.getByRole("button", { name: "Enviar complemento" }));
}

describe("o anexo no complemento do acompanhamento", () => {
  it("aceita imagem, PDF e áudio e avisa que os dados de origem são apagados", async () => {
    await entrar();

    const formulario = screen.getByRole("form", { name: "Enviar complemento" });
    expect(within(formulario).getByText(AVISO)).toBeTruthy();
    const seletor = within(formulario).getByLabelText(/Anexos/) as HTMLInputElement;
    expect(seletor.type).toBe("file");
    for (const extensao of [".jpg", ".png", ".webp", ".pdf", ".mp3", ".m4a", ".ogg", ".wav"]) {
      expect(seletor.accept.split(",")).toContain(extensao);
    }

    anexar(arquivo("foto.JPG"), arquivo("documento.pdf"), arquivo("audio.m4a"));

    const lista = within(screen.getByRole("list", { name: "Arquivos anexados" })).getAllByRole("listitem");
    expect(lista).toHaveLength(3);
  });

  it("sobe cada anexo depois do complemento, pela rota do relato, com origem complemento e sem o nome", async () => {
    await entrar();
    anexar(arquivo("Foto da Joana.jpg"), arquivo("audio.ogg"));

    enviarComplemento();

    expect(await screen.findByText("Em análise")).toBeTruthy();
    await waitFor(() => expect(anexosEnviados()).toHaveLength(2));
    expect(chamadas.findIndex((c) => c.url.endsWith("/relatos/anexos"))).toBeGreaterThan(
      chamadas.findIndex((c) => c.url.endsWith("/acompanhamento/complemento"))
    );
    const corpo = anexosEnviados()[0].body as FormData;
    expect(corpo.get("protocolo")).toBe(PROTOCOLO);
    expect(corpo.get("codigo")).toBe(CODIGO);
    expect(corpo.get("origem")).toBe("complemento");
    expect((corpo.get("arquivo") as File).name).toBe("anexo");
    expect(await screen.findByText("2 anexos guardados.")).toBeTruthy();
    expect(screen.queryByRole("list", { name: "Arquivos anexados" })).toBeNull();
  });

  it("recusa na hora o formato fora da lista e o complemento segue sem ele", async () => {
    await entrar();

    anexar(arquivo("IMG_0042.HEIC"));

    expect(screen.getByRole("alert").textContent).toContain(RECUSA);
    expect(screen.queryByRole("list", { name: "Arquivos anexados" })).toBeNull();

    enviarComplemento();

    expect(await screen.findByText("Em análise")).toBeTruthy();
    expect(complementosEnviados()).toHaveLength(1);
    expect(anexosEnviados()).toHaveLength(0);
  });

  it("o anexo que o servidor recusa aparece com o motivo, e o complemento fica enviado", async () => {
    respostaDoAnexo = () => json(415, { detail: RECUSA });
    await entrar();
    anexar(arquivo("foto.jpg"));

    enviarComplemento();

    expect(await screen.findByText("Em análise")).toBeTruthy();
    expect(await screen.findByText(`foto.jpg: ${RECUSA}`)).toBeTruthy();
    expect(screen.getByText(COMPLEMENTO)).toBeTruthy();
  });

  it("segura a tela ocupada, com o botão bloqueado, até o último anexo subir", async () => {
    let liberar: () => void = () => {};
    respostaDoAnexo = () =>
      new Promise<Response>((resolver) => {
        liberar = () => resolver(json(201, { id: "a1", tipo: "audio" }));
      });
    await entrar();
    anexar(arquivo("audio.m4a"));

    enviarComplemento();

    const botao = (await screen.findByRole("button", { name: /Enviando anexos/ })) as HTMLButtonElement;
    await waitFor(() => expect(anexosEnviados()).toHaveLength(1));
    expect(botao.disabled).toBe(true);
    expect(screen.getByText(/Não feche esta página/)).toBeTruthy();
    expect(screen.queryByText("1 anexo guardado.")).toBeNull();

    digitar("Complemento", "Outro complemento.");
    fireEvent.click(botao);
    expect(complementosEnviados()).toHaveLength(1);

    liberar();

    expect(await screen.findByText("1 anexo guardado.")).toBeTruthy();
    expect(screen.queryByText(/Enviando anexos/)).toBeNull();
    expect(screen.queryByText(/Não feche esta página/)).toBeNull();
    expect(screen.getByText("Em análise")).toBeTruthy();
  });
});
