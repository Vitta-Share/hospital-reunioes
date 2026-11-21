/**
 * @vitest-environment jsdom
 */

/**
 * A dica compartilhada (issue #1950): aparece com o mouse e com o foco do
 * teclado, e some ao sair, ao perder o foco ou com Esc. Quem a lê no leitor
 * de tela chega pelo `aria-describedby` do elemento embrulhado.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Dica } from "./Dica";

afterEach(() => {
  cleanup();
});

const FRASE = "A nota da semana e onde a perda da conta nasce.";

function abrir() {
  render(
    <Dica texto={FRASE}>
      <a href="/contas-medicas/painel">Painel</a>
    </Dica>,
  );
  return screen.getByRole("link", { name: "Painel" });
}

describe("a dica", () => {
  it("não aparece antes de alguém chegar no elemento", () => {
    abrir();

    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("aparece no hover e some ao sair", () => {
    const link = abrir();

    fireEvent.mouseEnter(link);
    expect(screen.getByRole("tooltip").textContent).toBe(FRASE);

    fireEvent.mouseLeave(link);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("aparece no foco do teclado, descreve o elemento e some ao perder o foco", () => {
    const link = abrir();

    fireEvent.focus(link);
    const dica = screen.getByRole("tooltip");
    expect(dica.textContent).toBe(FRASE);
    expect(link.getAttribute("aria-describedby")).toBe(dica.id);

    fireEvent.blur(link);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("some com Esc, mesmo com o foco ainda no elemento", () => {
    const link = abrir();

    fireEvent.focus(link);
    fireEvent.keyDown(link, { key: "Escape" });

    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("aberta pelo mouse, some com Esc mesmo sem o foco no elemento", () => {
    const link = abrir();

    fireEvent.mouseEnter(link);
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("outra tecla no documento não fecha a dica aberta pelo mouse", () => {
    const link = abrir();

    fireEvent.mouseEnter(link);
    fireEvent.keyDown(document, { key: "Tab" });

    expect(screen.getByRole("tooltip").textContent).toBe(FRASE);
  });

  it("abre para a direita do elemento; com abrePara esquerda, fica presa na borda direita dele (issue #1952)", () => {
    fireEvent.focus(abrir());
    const padrao = screen.getByRole("tooltip").className.split(" ");
    expect(padrao).toContain("left-0");
    expect(padrao).not.toContain("right-0");
    cleanup();

    render(
      <Dica texto={FRASE} abrePara="esquerda">
        <button type="button">Reanalisar</button>
      </Dica>,
    );
    fireEvent.focus(screen.getByRole("button", { name: "Reanalisar" }));
    const aEsquerda = screen.getByRole("tooltip").className.split(" ");
    expect(aEsquerda).toContain("right-0");
    expect(aEsquerda).not.toContain("left-0");
  });
});
