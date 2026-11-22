/**
 * @vitest-environment jsdom
 */

/**
 * O texto da mensagem da Conversa da Demanda (issue #2117, PRD #2112, ADR 0109,
 * decisão 9): negrito, lista e link a partir de marcação simples, sem aceitar
 * HTML. A mensagem antiga, escrita como texto puro, continua legível.
 */

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TextoDaMensagem } from "./TextoDaMensagem";

afterEach(cleanup);

function desenhar(texto: string) {
  return render(<TextoDaMensagem texto={texto} />).container;
}

describe("O texto da mensagem", () => {
  it("desenha o negrito", () => {
    const caixa = desenhar("O relatório **sumiu** de novo.");

    expect(caixa.querySelector("strong")?.textContent).toBe("sumiu");
  });

  it("desenha a lista", () => {
    const caixa = desenhar("O que falta:\n- a escala\n- o plantão");

    expect([...caixa.querySelectorAll("ul > li")].map((li) => li.textContent)).toEqual(["a escala", "o plantão"]);
  });

  it("desenha o link, que abre em outra aba", () => {
    const caixa = desenhar("Veja [a tela](https://app.hsm.test/admin/tecnologia).");

    const link = caixa.querySelector("a");
    expect(link?.textContent).toBe("a tela");
    expect(link?.getAttribute("href")).toBe("https://app.hsm.test/admin/tecnologia");
    expect(link?.getAttribute("target")).toBe("_blank");
    expect(link?.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("mostra o HTML digitado como texto e não o executa", () => {
    const caixa = desenhar('Teste <img src="x" onerror="alert(1)"> e <b>forte</b>');

    expect(caixa.querySelector("img")).toBeNull();
    expect(caixa.querySelector("b")).toBeNull();
    expect(caixa.textContent).toContain('<img src="x" onerror="alert(1)">');
    expect(caixa.textContent).toContain("<b>forte</b>");
  });

  it("não deixa link de javascript virar link que roda", () => {
    const caixa = desenhar("[clique](javascript:alert(1))");

    expect(caixa.querySelector("a")?.getAttribute("href") ?? "").not.toContain("javascript");
  });

  it("a mensagem antiga, em texto puro, guarda as quebras de linha e a menção", () => {
    const caixa = desenhar("@Lucas Sampaio olha isso.\nAconteceu de novo agora.");

    expect(caixa.querySelector("br")).not.toBeNull();
    expect(caixa.textContent).toBe("@Lucas Sampaio olha isso.\nAconteceu de novo agora.");
  });

  it("não usa itálico", () => {
    const caixa = desenhar("Isso é *importante* e _urgente_.");

    expect(caixa.querySelector("em")).toBeNull();
    expect(caixa.textContent).toBe("Isso é importante e urgente.");
  });
});
