/**
 * @vitest-environment jsdom
 */

/**
 * O robô do Assistente do app na casca das áreas logadas (issue #2267, ADR
 * 0113, decisão 8).
 *
 * Monta o `AppShell` de verdade, nas variantes do app e do Admin, porque a
 * promessa é o robô em toda área logada e não só o componente: apagar o robô
 * da casca tem que deixar este arquivo vermelho. `Header`, `Footer` e a gaveta
 * entram dublados, como no `AppShell.test.tsx`, por serem vizinhos de layout.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { AppShell } from "@/components/layout/AppShell";

const sessao = vi.hoisted(() => ({
  participante: {
    id: "p2267",
    nome_completo: "Pessoa Ficticia",
    email: "p2267@exemplo.test",
    access_profile: "regular",
  } as CurrentParticipante,
}));

vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard" }));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante: sessao.participante, loading: false, error: null }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "tok-2267" } } }) },
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

let buscar: ReturnType<typeof vi.fn>;

beforeEach(() => {
  buscar = vi.fn(async (url: string) => {
    if (url === "/api/assistente-do-app/conversa") {
      return new Response(JSON.stringify({ resposta: "Clique em Nova pendência. Fonte: Reuniões e Pendências." }));
    }
    if (url.startsWith("/manual/")) {
      return new Response("---\nmodulo: reunioes-e-pendencias\ntitulo: Reuniões e Pendências\n---\nTexto.");
    }
    return new Response(JSON.stringify({ total: 0, degradado: [] }));
  });
  vi.stubGlobal("fetch", buscar);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe.each([
  ["app", "default"],
  ["Admin", "admin"],
] as const)("o robô na área %s", (_area, variante) => {
  it("fica no canto inferior direito e abre com a sugestão Tirar uma dúvida", () => {
    render(
      <AppShell userName="Pessoa" variant={variante}>
        <p>conteúdo</p>
      </AppShell>
    );

    const robo = screen.getByRole("button", { name: "Assistente do app" });
    const canto = robo.closest("[data-assistente-do-app]") as HTMLElement;
    expect(canto.className).toMatch(/\bfixed\b/);
    expect(canto.className).toMatch(/\bright-\d/);
    expect(canto.className).toMatch(/\bbottom-/);
    expect(screen.queryByRole("button", { name: "Tirar uma dúvida" })).toBeNull();

    fireEvent.click(robo);

    const painel = screen.getByRole("dialog", { name: "Assistente do app" });
    expect(within(painel).getByRole("button", { name: "Tirar uma dúvida" })).toBeTruthy();
    expect(within(painel).getByRole("textbox", { name: "Sua pergunta" })).toBeTruthy();
  });
});

describe("a conversa no painel", () => {
  it("manda a pergunta e mostra a resposta do assistente", async () => {
    render(
      <AppShell userName="Pessoa">
        <p>conteúdo</p>
      </AppShell>
    );
    fireEvent.click(screen.getByRole("button", { name: "Assistente do app" }));
    fireEvent.click(screen.getByRole("button", { name: "Tirar uma dúvida" }));
    const campo = screen.getByRole("textbox", { name: "Sua pergunta" });
    expect(document.activeElement).toBe(campo);

    fireEvent.change(campo, { target: { value: "Como abro uma pendência?" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Clique em Nova pendência. Fonte: Reuniões e Pendências.")).toBeTruthy();
    expect(screen.getByText("Como abro uma pendência?")).toBeTruthy();
    await waitFor(() => expect((campo as HTMLTextAreaElement).value).toBe(""));
  });
});
