/**
 * @vitest-environment jsdom
 */

/**
 * Os anexos da notificação no navegador (issue #1988): a conferência antes do
 * envio e a redução da foto grande. A régua do servidor está em
 * `backend/tests/test_seguranca_do_paciente_anexos.py`.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { LIMITE_DA_SOMA, conferirArquivos, reduzirFoto } from "./anexos";

const MB = 1024 * 1024;

function arquivo(nome: string, tamanho: number, tipo: string): File {
  return new File([new Uint8Array(tamanho)], nome, { type: tipo });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("conferirArquivos", () => {
  it("aceita até três fotos ou PDFs somando menos de 9 MB", () => {
    expect(
      conferirArquivos([
        arquivo("a.jpg", 2 * MB, "image/jpeg"),
        arquivo("b.png", 2 * MB, "image/png"),
        arquivo("c.pdf", 2 * MB, "application/pdf"),
      ])
    ).toBeNull();
  });

  it("recusa o quarto arquivo", () => {
    const quatro = ["a", "b", "c", "d"].map((n) => arquivo(`${n}.jpg`, 1000, "image/jpeg"));
    expect(conferirArquivos(quatro)).toBe("Você pode anexar até 3 arquivos.");
  });

  it("recusa o tipo que não é foto nem PDF, pelo nome", () => {
    expect(conferirArquivos([arquivo("planilha.xlsx", 1000, "image/jpeg")])).toBe(
      "O arquivo planilha.xlsx não é aceito. Envie foto (JPG, PNG, WEBP ou HEIC) ou PDF."
    );
    expect(conferirArquivos([arquivo("audio.mp3", 1000, "audio/mpeg")])).toMatch(/não é aceito/);
  });

  it("recusa a soma de 9 MB ou mais e aceita logo abaixo", () => {
    expect(conferirArquivos([arquivo("a.jpg", 5 * MB, "image/jpeg"), arquivo("b.pdf", 4 * MB, "application/pdf")])).toBe(
      "Os arquivos somam 9,0 MB e precisam somar menos de 9 MB. Tire um arquivo ou envie um menor."
    );
    expect(LIMITE_DA_SOMA).toBe(9 * MB);
    expect(
      conferirArquivos([arquivo("a.jpg", 5 * MB, "image/jpeg"), arquivo("b.pdf", 4 * MB - 1, "application/pdf")])
    ).toBeNull();
  });

  it("recusa o arquivo vazio", () => {
    expect(conferirArquivos([arquivo("vazia.jpg", 0, "image/jpeg")])).toBe("O arquivo vazia.jpg está vazio.");
  });
});

describe("reduzirFoto", () => {
  function prepararCanvas(tamanhoDoResultado: number) {
    const desenhos: { largura: number; altura: number }[] = [];
    vi.stubGlobal(
      "createImageBitmap",
      vi.fn(async () => ({ width: 4000, height: 3000, close: () => {} }))
    );
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(function (this: HTMLCanvasElement) {
      const { width, height } = this;
      return {
        drawImage: () => desenhos.push({ largura: width, altura: height }),
      } as unknown as CanvasRenderingContext2D;
    } as unknown as HTMLCanvasElement["getContext"]);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(function (callback, tipo) {
      callback(new Blob([new Uint8Array(tamanhoDoResultado)], { type: tipo }));
    });
    return desenhos;
  }

  it("reduz a foto grande para JPEG de no máximo 1600 px no lado maior", async () => {
    const desenhos = prepararCanvas(600 * 1024);
    const grande = arquivo("IMG_0001.png", 12 * MB, "image/png");

    const reduzida = await reduzirFoto(grande);

    expect(desenhos).toEqual([{ largura: 1600, altura: 1200 }]);
    expect(reduzida.type).toBe("image/jpeg");
    expect(reduzida.name).toBe("IMG_0001.jpg");
    expect(reduzida.size).toBe(600 * 1024);
  });

  it("não mexe na foto pequena nem no PDF", async () => {
    const desenhos = prepararCanvas(100);
    const pequena = arquivo("p.jpg", 500 * 1024, "image/jpeg");
    const pdf = arquivo("escala.pdf", 5 * MB, "application/pdf");

    expect(await reduzirFoto(pequena)).toBe(pequena);
    expect(await reduzirFoto(pdf)).toBe(pdf);
    expect(desenhos).toEqual([]);
  });

  it("devolve a original quando o navegador não abre a foto", async () => {
    vi.stubGlobal(
      "createImageBitmap",
      vi.fn(async () => {
        throw new Error("formato não suportado");
      })
    );
    const heic = arquivo("IMG_0002.heic", 3 * MB, "image/heic");

    expect(await reduzirFoto(heic)).toBe(heic);
  });
});
