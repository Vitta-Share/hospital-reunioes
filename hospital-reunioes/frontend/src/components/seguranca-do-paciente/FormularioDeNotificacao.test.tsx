/**
 * @vitest-environment jsdom
 */

/**
 * O formulário de notificação de incidente (issue #1987, PRD #1979).
 *
 * Quatro telas e a confirmação, no máximo 7 campos visíveis por tela, o
 * rodapé "Notificar não gera punição" e a linha de orientação em todas. A
 * origem vem da porta (QR, endereço ou botão do módulo), nunca de escolha da
 * pessoa. A régua do que o servidor grava está em
 * `backend/tests/test_seguranca_do_paciente_notificacoes.py`.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FormularioDeNotificacao } from "./FormularioDeNotificacao";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

interface Chamada {
  url: string;
  metodo: string;
  corpo: Record<string, unknown> | null;
  autorizacao: string | null;
}

let chamadas: Chamada[] = [];
let respostaDoEnvio: { status: number; corpo: unknown } = {
  status: 201,
  corpo: { protocolo: "NSP-2026-0007", criado_em: "2026-11-20T10:00:00+00:00" },
};

beforeEach(() => {
  chamadas = [];
  respostaDoEnvio = { status: 201, corpo: { protocolo: "NSP-2026-0007", criado_em: "2026-11-20T10:00:00+00:00" } };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const cabecalhos = new Headers(init?.headers);
      chamadas.push({
        url,
        metodo: init?.method ?? "GET",
        corpo: init?.body ? JSON.parse(String(init.body)) : null,
        autorizacao: cabecalhos.get("Authorization"),
      });
      if (url === "/api/nsp/publico/setores") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ setores: [{ id: "setor-uti", nome: "UTI Adulto" }] }),
        } as Response;
      }
      const { status, corpo } = respostaDoEnvio;
      return { ok: status < 300, status, json: async () => corpo } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function botao(nome: string | RegExp) {
  return screen.getByRole("button", { name: nome }) as HTMLButtonElement;
}

function escrever(rotulo: string | RegExp, valor: string) {
  fireEvent.change(screen.getByLabelText(rotulo), { target: { value: valor } });
}

function escolher(grupo: string | RegExp, opcao: string) {
  fireEvent.click(within(screen.getByRole("group", { name: grupo })).getByRole("button", { name: opcao }));
}

/** O que a pessoa vê de campo na tela: cada caixa de texto, data, hora ou
 * lista, e cada grupo de escolhas de um toque. */
function camposVisiveis(): number {
  const formulario = screen.getByRole("form", { name: "Notificação de incidente" });
  return formulario.querySelectorAll("input:not([type=hidden]), textarea, select, [role=group]").length;
}

async function preencherAteAIdentificacao() {
  escrever("O que aconteceu", "A bomba de infusão alarmou e ninguém ouviu.");
  fireEvent.click(botao("Continuar"));
  await waitFor(() => expect(screen.getByRole("option", { name: "UTI Adulto" })).toBeTruthy());
  escrever("Setor", "setor-uti");
  escolher("Turno", "Noite");
  fireEvent.click(botao("Continuar"));
  escolher("O incidente chegou ao paciente?", "Chegou, com dano");
  escolher("Foi grave ou houve morte?", "Sim");
  fireEvent.click(botao("Continuar"));
}

describe("as quatro telas", () => {
  it("cada tela tem a orientação no topo, o rodapé e no máximo 7 campos", async () => {
    render(<FormularioDeNotificacao porta="endereco" />);

    const telas = [
      ["O que aconteceu", "Conte com as suas palavras. Você não precisa classificar nada."],
      ["Onde e quando", "Ajude o Núcleo a localizar o incidente."],
      ["O paciente foi atingido", "Diga até onde o incidente chegou."],
      ["Identificação", "Escolha se o Núcleo pode saber quem notificou."],
    ];
    for (const [indice, [titulo, orientacao]] of telas.entries()) {
      expect(screen.getByRole("heading", { name: titulo })).toBeTruthy();
      expect(screen.getByText(orientacao)).toBeTruthy();
      expect(screen.getByText("Notificar não gera punição.")).toBeTruthy();
      expect(screen.getByText(`Tela ${indice + 1} de 4`)).toBeTruthy();
      if (indice === 0) {
        expect(
          screen.getByText(
            "Não escreva o nome do paciente. Se precisar, informe o leito ou o número do atendimento."
          )
        ).toBeTruthy();
        escrever("O que aconteceu", "A bomba de infusão alarmou e ninguém ouviu.");
      }
      if (indice === 1) {
        await waitFor(() => expect(screen.getByRole("option", { name: "UTI Adulto" })).toBeTruthy());
        expect((screen.getByLabelText("Data") as HTMLInputElement).value).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        escrever("Setor", "setor-uti");
        escolher("Turno", "Noite");
      }
      if (indice === 2) {
        escolher("O incidente chegou ao paciente?", "Chegou, com dano");
        escolher("Foi grave ou houve morte?", "Sim");
      }
      expect(camposVisiveis()).toBeGreaterThan(0);
      expect(camposVisiveis()).toBeLessThanOrEqual(7);
      if (indice < 3) fireEvent.click(botao("Continuar"));
    }
  });

  it("não segue sem o relato", () => {
    render(<FormularioDeNotificacao porta="endereco" />);

    expect(botao("Continuar").disabled).toBe(true);
    escrever("O que aconteceu", "   ");
    expect(botao("Continuar").disabled).toBe(true);
  });

  it("a gravidade só é perguntada quando houve dano ou não sei", async () => {
    render(<FormularioDeNotificacao porta="endereco" />);
    escrever("O que aconteceu", "Queda no banheiro.");
    fireEvent.click(botao("Continuar"));
    await waitFor(() => expect(screen.getByRole("option", { name: "UTI Adulto" })).toBeTruthy());
    escrever("Setor", "setor-uti");
    escolher("Turno", "Tarde");
    fireEvent.click(botao("Continuar"));

    escolher("O incidente chegou ao paciente?", "Não chegou");
    expect(screen.queryByRole("group", { name: "Foi grave ou houve morte?" })).toBeNull();
    escolher("O incidente chegou ao paciente?", "Não sei");
    expect(screen.getByRole("group", { name: "Foi grave ou houve morte?" })).toBeTruthy();
    expect(botao("Continuar").disabled).toBe(true);
  });
});

describe("a origem vem da porta", () => {
  it("pelo endereço, identificado, manda a origem endereço sem login e mostra o protocolo", async () => {
    render(<FormularioDeNotificacao porta="endereco" />);
    await preencherAteAIdentificacao();

    expect((botao("Com o meu nome") as HTMLButtonElement).getAttribute("aria-pressed")).toBe("true");
    expect(
      screen.getByText("Seu nome aparece só para a Presidência do Núcleo e o Diretor Executivo.")
    ).toBeTruthy();
    escrever("Nome", "Profissional de Teste");
    escrever("E-mail ou telefone", "profissional@hsm.test");
    fireEvent.click(botao("Enviar notificação"));

    await waitFor(() => expect(screen.getByText("NSP-2026-0007")).toBeTruthy());
    const envio = chamadas.find((c) => c.metodo === "POST");
    expect(envio?.url).toBe("/api/nsp/publico/notificacoes");
    expect(envio?.autorizacao).toBeNull();
    expect(envio?.corpo).toMatchObject({
      origem: "endereco",
      anonimo: false,
      nome: "Profissional de Teste",
      contato: "profissional@hsm.test",
      setor_id: "setor-uti",
      turno: "noite",
      chegou_ao_paciente: "com_dano",
      grave_ou_morte: true,
    });
    expect(screen.getByText("Notificar não gera punição.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Acompanhar a notificação" }).getAttribute("href")).toBe(
      "/notificar/acompanhar"
    );
  });

  it("pelo QR, sem se identificar, manda a origem QR e mostra o código uma vez", async () => {
    respostaDoEnvio = {
      status: 201,
      corpo: { protocolo: "NSP-2026-0008", criado_em: "2026-11-20T10:00:00+00:00", codigo_acompanhamento: "ABCDE-FGHJK" },
    };
    render(<FormularioDeNotificacao porta="qr" />);
    await preencherAteAIdentificacao();

    fireEvent.click(botao("Sem me identificar"));
    expect(screen.queryByLabelText("Nome")).toBeNull();
    fireEvent.click(botao("Enviar notificação"));

    await waitFor(() => expect(screen.getByText("ABCDE-FGHJK")).toBeTruthy());
    const envio = chamadas.find((c) => c.metodo === "POST");
    expect(envio?.corpo).toMatchObject({ origem: "qr", anonimo: true });
    expect(envio?.corpo).not.toHaveProperty("nome");
    expect(screen.getByText(/o código aparece só agora/)).toBeTruthy();
  });

  it("pelo módulo, a identificação vem preenchida e o envio vai com a sessão", async () => {
    render(
      <FormularioDeNotificacao
        porta="modulo"
        identificacao={{ nome: "Pessoa de Teste", contato: "pessoa@hsm.test" }}
      />
    );
    await preencherAteAIdentificacao();

    expect(screen.getByText(/Pessoa de Teste/)).toBeTruthy();
    expect(screen.getByText(/pessoa@hsm\.test/)).toBeTruthy();
    expect(screen.queryByLabelText("Nome")).toBeNull();
    fireEvent.click(botao("Enviar notificação"));

    await waitFor(() => expect(screen.getByText("NSP-2026-0007")).toBeTruthy());
    const envio = chamadas.find((c) => c.metodo === "POST");
    expect(envio?.url).toBe("/api/nsp/notificacoes");
    expect(envio?.autorizacao).toBe("Bearer token-de-teste");
    expect(envio?.corpo).not.toHaveProperty("origem");
    expect(envio?.corpo).not.toHaveProperty("nome");
  });
});

describe("a recusa do servidor", () => {
  it("muitos envios do mesmo aparelho pedem para esperar", async () => {
    respostaDoEnvio = { status: 429, corpo: { error: "Rate limit exceeded" } };
    render(<FormularioDeNotificacao porta="endereco" />);
    await preencherAteAIdentificacao();
    fireEvent.click(botao("Sem me identificar"));
    fireEvent.click(botao("Enviar notificação"));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/muitos envios deste aparelho/));
  });
});
