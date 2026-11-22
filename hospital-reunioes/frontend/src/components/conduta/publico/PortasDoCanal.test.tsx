/**
 * @vitest-environment jsdom
 */

/**
 * As portas do lado público do Canal de Conduta (issue #1846, PRD #1786).
 *
 * O rodapé de toda tela pública leva à página de proteção, ao Código de
 * Conduta vigente e às portas "Não é aqui": o DP, que só mostra o contato, e
 * a Ouvidoria, para paciente e acompanhante. O backend é um dublê. Textos de
 * teste.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CondutaLayout from "@/app/conduta/layout";

import { PortaDoDp } from "./PortaDoDp";
import { RodapeDoCanal } from "./RodapeDoCanal";

let chamadas: { url: string; init?: RequestInit }[] = [];
let textos: Record<string, unknown> = {};
let statusDosTextos = 200;

beforeEach(() => {
  chamadas = [];
  statusDosTextos = 200;
  textos = { contato_dp: { texto: "Sala do DP, térreo\nRamal de teste 2040", versao: 3, versao_id: "dp-v3" } };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, init });
      if (url === "/api/conduta/textos") {
        return new Response(JSON.stringify(statusDosTextos === 200 ? { textos } : { detail: "Not Found" }), {
          status: statusDosTextos,
        });
      }
      return new Response("{}", { status: 404 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function link(nome: string | RegExp): HTMLAnchorElement {
  return screen.getByRole("link", { name: nome }) as HTMLAnchorElement;
}

describe("RodapeDoCanal", () => {
  it("leva à página de proteção", () => {
    render(<RodapeDoCanal />);

    expect(link("Como este canal protege você").getAttribute("href")).toBe("/conduta/protecao");
  });

  it("abre o Código de Conduta vigente, no endereço que não muda de uma versão para a outra", () => {
    render(<RodapeDoCanal />);

    expect(link("Código de Conduta").getAttribute("href")).toBe("/api/conduta/codigo-de-conduta");
  });

  it("a porta de paciente ou acompanhante leva ao formulário da Ouvidoria", () => {
    render(<RodapeDoCanal />);

    expect(link(/Sou paciente ou acompanhante/).getAttribute("href")).toBe("/manifestacao");
  });

  it("a porta de salário, contracheque e escala leva ao contato do DP", () => {
    render(<RodapeDoCanal />);

    expect(link(/Salário, contracheque, escala/).getAttribute("href")).toBe("/conduta/departamento-pessoal");
  });
});

describe("layout das telas públicas", () => {
  it("toda tela pública do canal tem o rodapé com a página de proteção", () => {
    render(
      <CondutaLayout>
        <p>Uma tela pública de teste</p>
      </CondutaLayout>,
    );

    expect(screen.getByText("Uma tela pública de teste")).toBeTruthy();
    const rodape = screen.getByRole("contentinfo");
    expect(within(rodape).getByRole("link", { name: "Como este canal protege você" })).toBeTruthy();
  });
});

describe("PortaDoDp", () => {
  it("mostra o contato do DP configurado", async () => {
    render(<PortaDoDp />);

    const contato = await screen.findByText(/Sala do DP, térreo/);
    expect(contato.textContent).toBe("Sala do DP, térreo\nRamal de teste 2040");
    expect(screen.getByText(/não abre protocolo/)).toBeTruthy();
  });

  it("não cria protocolo nem envia nada: só lê os textos", async () => {
    render(<PortaDoDp />);
    await screen.findByText(/Sala do DP, térreo/);

    expect(chamadas.map((c) => [c.url, c.init?.method ?? "GET"])).toEqual([["/api/conduta/textos", "GET"]]);
    expect(chamadas[0].init?.credentials).toBe("omit");
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /enviar|encaminhar/i })).toBeNull();
  });

  it("sem contato configurado, orienta a procurar o DP", async () => {
    textos = { contato_dp: null };

    render(<PortaDoDp />);

    expect(await screen.findByText("Procure o Departamento Pessoal do hospital.")).toBeTruthy();
  });

  it("com o canal fechado diz que a página não existe", async () => {
    statusDosTextos = 404;

    render(<PortaDoDp />);

    expect(await screen.findByText("Página não encontrada.")).toBeTruthy();
    expect(screen.queryByText(/não abre protocolo/)).toBeNull();
  });
});
