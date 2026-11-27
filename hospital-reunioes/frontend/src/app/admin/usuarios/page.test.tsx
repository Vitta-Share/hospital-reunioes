/**
 * @vitest-environment jsdom
 */

/**
 * Excluir usuário na Administração (issue #2043).
 *
 * Quem tem histórico no app não pode sair da tabela, e o mesmo clique o
 * desliga. A tela diz qual dos dois aconteceu, fecha o quadro e tira a pessoa
 * da lista, que abre em "Apenas ativos".
 */

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AdminUsuario } from "@/components/admin/types";
import { ToastProvider } from "@/components/ui/Toast";

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ token: "token-de-teste", loading: false }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import AdminUsuariosPage from "./page";

const FELIPE: AdminUsuario = {
  id: "P040",
  nome_completo: "Felipe de Carvalho",
  email: "felipe@example.com",
  cargo: "Coordenador",
  setor: "Imagem",
  role: "coordenador",
  ativo: true,
  is_externo: false,
  is_super_admin: false,
  access_profile: "regular",
} as AdminUsuario;

function servidor(resultado: "excluido" | "desligado") {
  let excluido = false;
  const chamadas: string[] = [];
  const fetchFalso = vi.fn(async (url: string, init?: RequestInit) => {
    chamadas.push(`${init?.method ?? "GET"} ${url}`);
    if (init?.method === "DELETE") {
      excluido = true;
      return new Response(JSON.stringify({ success: true, id: FELIPE.id, resultado }), { status: 200 });
    }
    if (url.startsWith("/api/admin/usuarios?")) {
      const ativos = new URLSearchParams(url.split("?")[1]).get("ativo") === "true";
      // Desligado continua no banco; a lista em "Apenas ativos" não o traz.
      const sai = resultado === "excluido" || ativos;
      return new Response(JSON.stringify(excluido && sai ? [] : [FELIPE]), { status: 200 });
    }
    return new Response(JSON.stringify([]), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchFalso);
  return chamadas;
}

async function excluirFelipe(motivo: string) {
  await act(async () => {
    render(
      <ToastProvider>
        <AdminUsuariosPage />
      </ToastProvider>,
    );
  });
  const linha = (await screen.findByText("Felipe de Carvalho")).closest("tr") as HTMLElement;
  fireEvent.click(within(linha).getByTitle("Deletar"));
  const quadro = screen.getByRole("textbox", { name: /motivo/i }).closest("form") as HTMLElement;
  fireEvent.change(within(quadro).getByRole("textbox", { name: /motivo/i }), { target: { value: motivo } });
  await act(async () => {
    // O botão do quadro fica no rodapé, ligado ao formulário pelo atributo form.
    const confirmar = screen
      .getAllByRole("button", { name: "Deletar" })
      .find((b) => b.getAttribute("form") === quadro.id) as HTMLElement;
    fireEvent.click(confirmar);
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Excluir usuário", () => {
  it("a lista de Usuários abre em Apenas ativos", async () => {
    const chamadas = servidor("excluido");
    await act(async () => {
      render(
        <ToastProvider>
          <AdminUsuariosPage />
        </ToastProvider>,
      );
    });
    const lista = chamadas.find((c) => c.startsWith("GET /api/admin/usuarios?"));
    expect(lista).toContain("ativo=true");
  });

  it("quem tem histórico é desligado, com a confirmação, e sai da lista", async () => {
    servidor("desligado");
    await excluirFelipe("Usuário desligado");

    expect(await screen.findByText("Usuário desligado; o histórico dele foi mantido")).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: /motivo/i })).toBeNull();
    await waitFor(() => expect(screen.queryByText("Felipe de Carvalho")).toBeNull());
  });

  it("quem não tem histórico é excluído, com a confirmação, e sai da lista", async () => {
    servidor("excluido");
    await excluirFelipe("Cadastro duplicado");

    expect(await screen.findByText("Usuário excluído")).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: /motivo/i })).toBeNull();
    await waitFor(() => expect(screen.queryByText("Felipe de Carvalho")).toBeNull());
  });
});
