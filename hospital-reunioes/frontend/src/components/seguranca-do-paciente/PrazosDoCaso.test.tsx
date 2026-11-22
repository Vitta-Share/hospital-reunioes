/**
 * @vitest-environment jsdom
 */

/**
 * Os prazos do caso (issue #1993): cada prazo com data e hora absolutas no
 * relógio do hospital, o legal separado do interno, e a linha de notificação
 * externa com o sistema de destino.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PrazosDoCaso } from "./PrazosDoCaso";

afterEach(() => cleanup());

const PRAZOS = [
  {
    marco: "triagem",
    rotulo: "Triagem e classificação",
    tipo: "interno",
    valor: 4,
    unidade: "horas_uteis",
    vence_em: "2026-11-10T17:00:00+00:00",
  },
  {
    marco: "notificacao_externa",
    rotulo: "Notificação externa à vigilância sanitária",
    tipo: "legal",
    valor: 72,
    unidade: "horas_corridas",
    vence_em: "2026-11-13T01:00:00+00:00",
  },
];

describe("os prazos do caso", () => {
  it("mostram cada prazo com data e hora de São Paulo, e dizem qual é legal", () => {
    render(
      <PrazosDoCaso
        prazos={PRAZOS}
        notificacaoExterna={{
          sistema: "vigimed",
          rotulo: "VigiMed",
          prazo_legal: "2026-11-13T01:00:00+00:00",
          estado: "pendente",
        }}
      />
    );

    const triagem = screen.getByText("Triagem e classificação").closest("li") as HTMLElement;
    expect(within(triagem).getByText("10/11/2026, 14:00")).toBeTruthy();
    expect(within(triagem).getByText("Interno")).toBeTruthy();

    const externa = screen.getByText("Notificação externa à vigilância sanitária").closest("li") as HTMLElement;
    expect(within(externa).getByText("12/11/2026, 22:00")).toBeTruthy();
    expect(within(externa).getByText("Legal")).toBeTruthy();

    expect(screen.getByText("Notificar no VigiMed até 12/11/2026, 22:00.")).toBeTruthy();
    expect(screen.queryByText(/em \d+ dias?/)).toBeNull();
  });

  it("não aparece antes da confirmação da triagem", () => {
    const { container } = render(<PrazosDoCaso prazos={[]} notificacaoExterna={null} />);

    expect(container.textContent).toBe("");
  });
});
