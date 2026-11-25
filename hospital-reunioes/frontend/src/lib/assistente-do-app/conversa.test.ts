/**
 * O que a tela manda ao Assistente do app (issue #2267, ADR 0113, decisão 8).
 *
 * O `fetch` falso serve as páginas de verdade de `public/manual/` e guarda o
 * corpo do POST da conversa: é por ele que o teste lê quais páginas do Manual
 * entram no contexto. A escolha é a do Manual pelo menu, e a página de módulo
 * que a pessoa não acessa não sai.
 */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { ROTA_DA_CONVERSA, perguntarAoAssistente } from "./conversa";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "tok-2267" } } }) },
  }),
}));

const MANUAL = join(process.cwd(), "public", "manual");

/** Pessoa das Reuniões, sem Admin, POPs, Ouvidoria nem Contas médicas. */
const DAS_REUNIOES: CurrentParticipante = {
  id: "p2267",
  nome_completo: "Pessoa Ficticia",
  email: "p2267@exemplo.test",
  access_profile: "regular",
};

const SUPER_ADMIN: CurrentParticipante = {
  ...DAS_REUNIOES,
  access_profile: "super_admin",
  perfil_contas_medicas: "coordenadora",
};

function servidorFalso() {
  const enviados: { url: string; corpo: unknown; headers: Record<string, string> }[] = [];
  const buscar = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === ROTA_DA_CONVERSA) {
      enviados.push({
        url,
        corpo: JSON.parse(String(init?.body)),
        headers: init?.headers as Record<string, string>,
      });
      return new Response(JSON.stringify({ resposta: "Clique em Nova pendência." }), { status: 200 });
    }
    const arquivo = join(MANUAL, url.replace(/^\/manual\//, ""));
    return existsSync(arquivo)
      ? new Response(readFileSync(arquivo, "utf8"), { status: 200 })
      : new Response("", { status: 404 });
  });
  return { buscar: buscar as unknown as typeof fetch, enviados };
}

const PERGUNTA = [{ role: "user" as const, content: "Como abro uma pendência?" }];

function modulosEnviados(corpo: unknown): string[] {
  return (corpo as { paginas_do_manual: { modulo: string }[] }).paginas_do_manual.map((p) => p.modulo);
}

afterEach(() => vi.restoreAllMocks());

describe("as páginas do Manual que vão para o Assistente", () => {
  it("a página de um módulo que a pessoa não acessa não entra no contexto", async () => {
    const { buscar, enviados } = servidorFalso();

    const resposta = await perguntarAoAssistente(PERGUNTA, DAS_REUNIOES, buscar);

    expect(resposta).toBe("Clique em Nova pendência.");
    const modulos = modulosEnviados(enviados[0].corpo);
    expect(modulos).toContain("reunioes-e-pendencias");
    expect(modulos).not.toContain("tecnologia");
    expect(modulos).not.toContain("contas-medicas");
    const corpo = JSON.stringify(enviados[0].corpo);
    expect(corpo).not.toContain("# A aba Tecnologia");
  });

  it("quem acessa o módulo leva a página dele, com o corpo lido do Manual", async () => {
    const { buscar, enviados } = servidorFalso();

    await perguntarAoAssistente(PERGUNTA, SUPER_ADMIN, buscar);

    const paginas = (enviados[0].corpo as { paginas_do_manual: { modulo: string; corpo: string }[] })
      .paginas_do_manual;
    const tecnologia = paginas.find((p) => p.modulo === "tecnologia");
    expect(tecnologia?.corpo.length).toBeGreaterThan(100);
    expect(modulosEnviados(enviados[0].corpo)).toContain("contas-medicas");
    expect(enviados[0].headers.Authorization).toBe("Bearer tok-2267");
  });
});
