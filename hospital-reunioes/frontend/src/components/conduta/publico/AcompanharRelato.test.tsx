/**
 * @vitest-environment jsdom
 */

/**
 * A página de acompanhamento do Canal de Conduta (issue #1845): protocolo e
 * código abrem a situação e as mensagens do Comitê, e o complemento sai pela
 * mesma página. Sem login e sem nada no endereço. O backend é um dublê.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AcompanharRelato } from "./AcompanharRelato";

const PROTOCOLO = "CC-K7M4-Q2XT";
const CODIGO = "ABCDE-23456";
const PERGUNTA = "Em que dia e em que setor isso aconteceu?";
const COMPLEMENTO = "Foi na oficina, numa terça de manhã.";

const AGUARDANDO = {
  protocolo: PROTOCOLO,
  situacao: "Aguardando sua resposta",
  mensagens: [{ de: "comite", tipo: "pergunta", texto: PERGUNTA, em: "2026-11-20T15:00:00+00:00" }],
};
const RESPONDIDO = {
  protocolo: PROTOCOLO,
  situacao: "Em análise",
  mensagens: [
    ...AGUARDANDO.mensagens,
    { de: "voce", tipo: "complemento", texto: COMPLEMENTO, em: "2026-11-21T15:00:00+00:00" },
  ],
};

let chamadas: { url: string; init: RequestInit | undefined; corpo: Record<string, unknown> }[];
let respostaDaConsulta: () => Response;

function json(status: number, corpo: unknown): Response {
  return new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  chamadas = [];
  respostaDaConsulta = () => json(200, AGUARDANDO);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, init, corpo: JSON.parse(String(init?.body ?? "{}")) });
      if (url.endsWith("/acompanhamento")) return respostaDaConsulta();
      if (url.endsWith("/acompanhamento/complemento")) return json(200, RESPONDIDO);
      return json(404, { detail: "Not Found" });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const digitar = (rotulo: string | RegExp, valor: string) =>
  fireEvent.change(screen.getByLabelText(rotulo), { target: { value: valor } });

async function entrar() {
  render(<AcompanharRelato />);
  digitar("Protocolo", PROTOCOLO);
  digitar("Código", CODIGO);
  fireEvent.click(screen.getByRole("button", { name: "Acompanhar" }));
}

describe("Acompanhar o relato", () => {
  it("protocolo e código abrem a situação e a pergunta do Comitê", async () => {
    await entrar();

    expect(await screen.findByText("Aguardando sua resposta")).toBeTruthy();
    expect(screen.getByText(PERGUNTA)).toBeTruthy();
    expect(screen.getByText("Pergunta do Comitê")).toBeTruthy();
  });

  it("protocolo e código vão só no corpo, sem login e sem cache", async () => {
    await entrar();
    await screen.findByText(PERGUNTA);

    const { url, init, corpo } = chamadas[0];
    expect(url).toBe("/api/conduta/acompanhamento");
    expect(url).not.toContain(PROTOCOLO);
    expect(corpo).toEqual({ protocolo: PROTOCOLO, codigo: CODIGO });
    expect(init?.credentials).toBe("omit");
    expect(init?.cache).toBe("no-store");
    expect(new Headers(init?.headers).has("Authorization")).toBe(false);
  });

  it("qualquer erro diz o mesmo, sem apontar qual dos dois errou", async () => {
    respostaDaConsulta = () =>
      json(404, { detail: "Não encontramos um relato com esse protocolo e esse código. Confira os dois e tente de novo." });

    await entrar();

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toBe(
      "Não encontramos um relato com esse protocolo e esse código. Confira os dois e tente de novo."
    );
  });

  it("muitas tentativas pedem para esperar", async () => {
    respostaDaConsulta = () => json(429, { error: "Rate limit exceeded" });

    await entrar();

    expect((await screen.findByRole("alert")).textContent).toMatch(/Espere alguns minutos/);
  });

  it("o complemento sai pela mesma página e a situação muda", async () => {
    await entrar();
    await screen.findByText(PERGUNTA);

    digitar("Complemento", COMPLEMENTO);
    fireEvent.click(screen.getByRole("button", { name: "Enviar complemento" }));

    expect(await screen.findByText("Em análise")).toBeTruthy();
    expect(screen.getByText(COMPLEMENTO)).toBeTruthy();
    expect(chamadas[1].url).toBe("/api/conduta/acompanhamento/complemento");
    expect(chamadas[1].corpo).toEqual({ protocolo: PROTOCOLO, codigo: CODIGO, texto: COMPLEMENTO });
    expect(chamadas[1].init?.credentials).toBe("omit");
  });

  it("a resposta final do Comitê aparece com o título dela", async () => {
    respostaDaConsulta = () =>
      json(200, {
        protocolo: PROTOCOLO,
        situacao: "Concluído",
        mensagens: [{ de: "comite", tipo: "resposta_final", texto: "O Comitê concluiu o caso.", em: "2026-11-22T12:00:00+00:00" }],
      });

    await entrar();

    expect(await screen.findByText("Concluído")).toBeTruthy();
    expect(screen.getByText("Resposta do Comitê")).toBeTruthy();
    expect(screen.getByText("O Comitê concluiu o caso.")).toBeTruthy();
  });
});
