/**
 * @vitest-environment jsdom
 */

/**
 * O separador por dia da Conversa da Demanda (issue #2117, PRD #2112): um
 * traço com a data marca a troca de dia. O dia é o do hospital, no fuso de
 * São Paulo, e não o do computador de quem lê.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SeparadorDeDia, diaDaMensagem } from "./SeparadorDeDia";

afterEach(cleanup);

describe("O separador por dia", () => {
  it("mostra a data por extenso num separador", () => {
    render(<SeparadorDeDia dia="2026-11-19" />);

    const separador = screen.getByRole("separator", { name: "19 de novembro de 2026" });
    expect(separador.textContent).toBe("19 de novembro de 2026");
  });

  it("o dia da mensagem é o do hospital, no fuso de São Paulo", () => {
    // 01:30 em Greenwich ainda é a noite do dia 19 em São Paulo.
    expect(diaDaMensagem("2026-11-20T01:30:00Z")).toBe("2026-11-19");
    expect(diaDaMensagem("2026-11-20T03:30:00Z")).toBe("2026-11-20");
  });

  it("a mensagem sem data não tem dia", () => {
    expect(diaDaMensagem(null)).toBeNull();
    expect(diaDaMensagem("não é data")).toBeNull();
  });
});
