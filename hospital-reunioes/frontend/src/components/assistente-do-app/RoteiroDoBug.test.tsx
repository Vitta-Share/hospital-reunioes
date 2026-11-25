/**
 * @vitest-environment jsdom
 */

/**
 * O Roteiro do bug no robô do Assistente do app (issue #2275, ADR 0113,
 * decisão 8): a sugestão "Relatar um bug", as quatro perguntas e o print, o
 * resumo antes de enviar e a falha do envio com "Tentar de novo".
 *
 * Monta o `AppShell` de verdade, como o `AssistenteDoApp.test.tsx`: a
 * promessa é a sugestão no robô de toda área logada.
 */

import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { AppShell } from "@/components/layout/AppShell";

const sessao = vi.hoisted(() => ({
  participante: {
    id: "p2275",
    nome_completo: "Pessoa Ficticia",
    email: "p2275@exemplo.test",
    access_profile: "regular",
  } as CurrentParticipante,
}));

vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard" }));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante: sessao.participante, loading: false, error: null }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "tok-2275" } } }) },
  }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/layout/Header", () => ({ Header: () => <header /> }));
vi.mock("@/components/layout/Footer", () => ({ Footer: () => <footer /> }));
vi.mock("@/components/layout/MobileDrawer", () => ({
  MobileDrawer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const BUG = "/api/assistente-do-app/bug";
const MOTIVO = "O GitHub não respondeu agora, e o bug não chegou à Vitta. O relato ficou guardado: clique em Tentar de novo.";

let buscar: ReturnType<typeof vi.fn>;
let respostasDoEnvio: Response[];

function chamadasPara(url: string) {
  return buscar.mock.calls.filter(([chamada]) => chamada === url);
}

beforeEach(() => {
  respostasDoEnvio = [];
  buscar = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === BUG) {
      const corpo = JSON.parse(String(init?.body));
      return new Response(
        JSON.stringify({
          demanda_id: "d-1",
          resumo: {
            titulo: corpo.o_que_aconteceu,
            onde: corpo.onde || "não informado",
            o_que_aconteceu: corpo.o_que_aconteceu || "não informado",
            o_que_esperava: corpo.o_que_esperava || "não informado",
            como_repetir: corpo.como_repetir || "não informado",
            criterios: ["Que a Pendência fosse salva"],
          },
        })
      );
    }
    if (url === "/api/assistente-do-app/conversa") {
      return new Response(JSON.stringify({ resposta: "Fica no menu Pendências." }));
    }
    if (url === `${BUG}/d-1/print`) return new Response(JSON.stringify({ prints: 1 }));
    if (url === `${BUG}/d-1/enviar`) {
      return respostasDoEnvio.shift() ?? new Response(JSON.stringify({ demanda_id: "d-1" }));
    }
    return new Response(JSON.stringify({ total: 0, degradado: [] }));
  });
  vi.stubGlobal("fetch", buscar);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function abrirORoteiro() {
  render(
    <AppShell userName="Pessoa">
      <p>conteúdo</p>
    </AppShell>
  );
  fireEvent.click(screen.getByRole("button", { name: "Assistente do app" }));
  const painel = screen.getByRole("dialog", { name: "Assistente do app" });
  fireEvent.click(within(painel).getByRole("button", { name: "Relatar um bug" }));
  return painel;
}

function responder(texto: string) {
  fireEvent.change(screen.getByRole("textbox", { name: "Sua resposta" }), { target: { value: texto } });
  fireEvent.click(screen.getByRole("button", { name: "Responder" }));
}

async function ateOResumo() {
  abrirORoteiro();
  responder("Na tela de Pendências");
  responder("O botão Salvar não faz nada");
  responder("Que a Pendência fosse salva");
  fireEvent.click(screen.getByRole("button", { name: "Pular" }));
  const arquivo = new File(["png"], "tela.png", { type: "image/png" });
  const escolher = await screen.findByLabelText("Escolher o print");
  await act(async () => {
    fireEvent.change(escolher, { target: { files: [arquivo] } });
  });
  await screen.findByText("Confira o resumo antes de enviar.");
}

describe("a sugestão no robô", () => {
  it("o painel abre com a sugestão Relatar um bug", () => {
    render(
      <AppShell userName="Pessoa">
        <p>conteúdo</p>
      </AppShell>
    );
    fireEvent.click(screen.getByRole("button", { name: "Assistente do app" }));

    const painel = screen.getByRole("dialog", { name: "Assistente do app" });
    expect(within(painel).getByRole("button", { name: "Relatar um bug" })).toBeTruthy();
  });
});

describe("o Roteiro do bug", () => {
  it("faz as perguntas, guarda o print e mostra o resumo antes de enviar", async () => {
    await ateOResumo();

    const [, registro] = chamadasPara(BUG)[0];
    expect(JSON.parse(String(registro?.body))).toEqual({
      onde: "Na tela de Pendências",
      o_que_aconteceu: "O botão Salvar não faz nada",
      o_que_esperava: "Que a Pendência fosse salva",
      como_repetir: "",
    });
    expect(chamadasPara(`${BUG}/d-1/print`)).toHaveLength(1);
    expect(screen.getByText("não informado")).toBeTruthy();
    expect(screen.getByText("1 print guardado no aplicativo")).toBeTruthy();
    expect(chamadasPara(`${BUG}/d-1/enviar`)).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Enviar à Vitta" }));

    expect(await screen.findByText(/O bug foi enviado à Vitta/)).toBeTruthy();
    expect(chamadasPara(`${BUG}/d-1/enviar`)).toHaveLength(1);
  });

  it("a falha do envio mostra o motivo e Tentar de novo, e nada reenvia sozinho", async () => {
    respostasDoEnvio = [new Response(JSON.stringify({ detail: MOTIVO }), { status: 502 })];
    await ateOResumo();

    fireEvent.click(screen.getByRole("button", { name: "Enviar à Vitta" }));

    expect(await screen.findByText(MOTIVO)).toBeTruthy();
    const deNovo = screen.getByRole("button", { name: "Tentar de novo" });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(chamadasPara(`${BUG}/d-1/enviar`)).toHaveLength(1);

    fireEvent.click(deNovo);

    expect(await screen.findByText(/O bug foi enviado à Vitta/)).toBeTruthy();
    expect(chamadasPara(`${BUG}/d-1/enviar`)).toHaveLength(2);
  });
});

describe("sair do Roteiro do bug", () => {
  function voltouAoInicio() {
    const painel = screen.getByRole("dialog", { name: "Assistente do app" });
    expect(within(painel).getByRole("button", { name: "Tirar uma dúvida" })).toBeTruthy();
    expect(within(painel).getByRole("textbox", { name: "Sua pergunta" })).toBeTruthy();
    expect(within(painel).queryByRole("textbox", { name: "Sua resposta" })).toBeNull();
  }

  it("fechar e reabrir o painel no meio do relato volta a Tirar uma dúvida", () => {
    abrirORoteiro();
    responder("Na tela de Pendências");

    fireEvent.click(screen.getByRole("button", { name: "Fechar" }));
    fireEvent.click(screen.getByRole("button", { name: "Assistente do app" }));

    voltouAoInicio();
  });

  it("cancelar o relato volta a Tirar uma dúvida", () => {
    abrirORoteiro();
    responder("Na tela de Pendências");

    fireEvent.click(screen.getByRole("button", { name: "Cancelar o relato" }));

    voltouAoInicio();
  });

  it("depois do envio, Voltar sai do relato", async () => {
    await ateOResumo();
    fireEvent.click(screen.getByRole("button", { name: "Enviar à Vitta" }));
    await screen.findByText(/O bug foi enviado à Vitta/);

    fireEvent.click(screen.getByRole("button", { name: "Voltar" }));

    voltouAoInicio();
  });

  it("depois de uma dúvida, ainda dá para relatar um bug", async () => {
    render(
      <AppShell userName="Pessoa">
        <p>conteúdo</p>
      </AppShell>
    );
    fireEvent.click(screen.getByRole("button", { name: "Assistente do app" }));
    const painel = screen.getByRole("dialog", { name: "Assistente do app" });
    fireEvent.change(within(painel).getByRole("textbox", { name: "Sua pergunta" }), {
      target: { value: "Onde vejo as Pendências?" },
    });
    await act(async () => {
      fireEvent.click(within(painel).getByRole("button", { name: "Enviar" }));
    });
    await within(painel).findByText("Fica no menu Pendências.");

    fireEvent.click(within(painel).getByRole("button", { name: "Relatar um bug" }));

    expect(within(painel).getByRole("textbox", { name: "Sua resposta" })).toBeTruthy();
  });
});
