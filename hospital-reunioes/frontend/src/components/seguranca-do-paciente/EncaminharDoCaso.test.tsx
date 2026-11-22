/**
 * @vitest-environment jsdom
 */

/**
 * O botão Encaminhar da tela de triagem (issue #1995).
 *
 * Um ou mais destinos e o motivo em uma frase. Fora de escopo vai sozinho e
 * pede a orientação para quem notificou. Ao Canal de Conduta nada é enviado:
 * a tela só mostra a orientação que o servidor devolve.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EncaminharDoCaso } from "./EncaminharDoCaso";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const ORIENTACAO_DO_CANAL = "Nada deste caso foi enviado ao Canal de Conduta.";
let resposta: Record<string, unknown>;
const enviados: { url: string; body: unknown }[] = [];

beforeEach(() => {
  enviados.length = 0;
  resposta = { estado: "encaminhada", encaminhamento: {} };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      enviados.push({ url, body: JSON.parse(String(init?.body)) });
      return { ok: true, status: 201, json: async () => resposta } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function marcar(nome: string) {
  fireEvent.click(screen.getByRole("checkbox", { name: nome }));
}

function registrar() {
  return screen.getByRole("button", { name: "Registrar o encaminhamento" });
}

describe("encaminhar da triagem", () => {
  it("só libera com ao menos um destino e o motivo", () => {
    render(<EncaminharDoCaso id="c1" aoEncaminhar={() => undefined} />);

    expect(registrar().hasAttribute("disabled")).toBe(true);
    marcar("Ouvidoria");
    expect(registrar().hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Motivo, em uma frase"), { target: { value: "   " } });
    expect(registrar().hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Motivo, em uma frase"), { target: { value: "Reclamação de atendimento." } });
    expect(registrar().hasAttribute("disabled")).toBe(false);
  });

  it("Núcleo e Ouvidoria juntos vão no mesmo envio, e a tela diz que o caso continua na triagem", async () => {
    resposta = { estado: "recebida", encaminhamento: {} };
    const aoEncaminhar = vi.fn();
    render(<EncaminharDoCaso id="c1" aoEncaminhar={aoEncaminhar} />);

    marcar("Núcleo");
    marcar("Ouvidoria");
    fireEvent.change(screen.getByLabelText("Motivo, em uma frase"), { target: { value: "Também é reclamação." } });
    fireEvent.click(registrar());

    expect(await screen.findByText(/O caso continua na triagem do Núcleo/)).toBeTruthy();
    expect(enviados).toEqual([
      {
        url: "/api/nsp/triagem/c1/encaminhamento",
        body: { destinos: ["nucleo", "ouvidoria"], motivo: "Também é reclamação.", orientacao: null },
      },
    ]);
    expect(aoEncaminhar).toHaveBeenCalledWith("recebida");
  });

  it("fora de escopo vai sozinho e pede a orientação para quem notificou", async () => {
    resposta = { estado: "fora_de_escopo", encaminhamento: {} };
    render(<EncaminharDoCaso id="c1" aoEncaminhar={() => undefined} />);

    marcar("Ouvidoria");
    marcar("Fora de escopo");
    expect((screen.getByRole("checkbox", { name: "Ouvidoria" }) as HTMLInputElement).checked).toBe(false);
    expect((screen.getByRole("checkbox", { name: "Ouvidoria" }) as HTMLInputElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Motivo, em uma frase"), { target: { value: "Assunto trabalhista." } });
    expect(registrar().hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Orientação para quem notificou"), {
      target: { value: "Procure o Departamento Pessoal." },
    });
    fireEvent.click(registrar());

    expect(await screen.findByText(/O caso está em Fora de escopo/)).toBeTruthy();
    expect(enviados[0].body).toEqual({
      destinos: ["fora_de_escopo"],
      motivo: "Assunto trabalhista.",
      orientacao: "Procure o Departamento Pessoal.",
    });
  });

  it("Canal de Conduta mostra a orientação do servidor, sem link", async () => {
    resposta = { estado: "encaminhada", encaminhamento: {}, orientacao_do_canal_de_conduta: ORIENTACAO_DO_CANAL };
    const { container } = render(<EncaminharDoCaso id="c1" aoEncaminhar={() => undefined} />);

    marcar("Canal de Conduta");
    fireEvent.change(screen.getByLabelText("Motivo, em uma frase"), { target: { value: "Conduta de colega." } });
    fireEvent.click(registrar());

    expect(await screen.findByText(ORIENTACAO_DO_CANAL)).toBeTruthy();
    expect(container.querySelector("a")).toBeNull();
  });

  it("Segurança do Trabalho pede o setor que recebe e o envia com o destino (issue #1996)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url === "/api/nsp/publico/setores") {
          return {
            ok: true,
            status: 200,
            json: async () => ({ setores: [{ id: "s-sst", nome: "Segurança do Trabalho" }, { id: "s-uti", nome: "UTI Adulto" }] }),
          } as Response;
        }
        enviados.push({ url, body: JSON.parse(String(init?.body)) });
        return { ok: true, status: 201, json: async () => resposta } as Response;
      })
    );
    render(<EncaminharDoCaso id="c1" aoEncaminhar={() => undefined} />);

    marcar("Segurança do Trabalho");
    fireEvent.change(screen.getByLabelText("Motivo, em uma frase"), { target: { value: "Acidente com agulha." } });
    expect(registrar().hasAttribute("disabled")).toBe(true);
    await screen.findByRole("option", { name: "Segurança do Trabalho" });
    fireEvent.change(screen.getByLabelText("Setor que recebe (Segurança do Trabalho)"), { target: { value: "s-sst" } });
    expect(registrar().hasAttribute("disabled")).toBe(false);
    fireEvent.click(registrar());

    expect(await screen.findByText(/Encaminhamento registrado/)).toBeTruthy();
    expect(enviados[0].body).toEqual({
      destinos: ["seguranca_do_trabalho"],
      motivo: "Acidente com agulha.",
      orientacao: null,
      setores: { seguranca_do_trabalho: "s-sst" },
    });
  });
});
