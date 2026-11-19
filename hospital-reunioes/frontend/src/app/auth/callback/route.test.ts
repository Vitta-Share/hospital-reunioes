/**
 * Para onde o callback do Supabase manda quem acabou de trocar o code por
 * sessão (issue #1942, revisão do PR #2033).
 *
 * O `next` chega pela query string, então quem monta o link escolhe o valor.
 * A régua é a mesma do login (`lib/login/destino.ts`): só caminho do próprio
 * site é destino; o resto cai no Início.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const exchangeCodeForSession = vi.fn();

vi.mock("@supabase/ssr", () => ({
  createServerClient: () => ({ auth: { exchangeCodeForSession } }),
}));

import { GET } from "./route";

const SITE = "https://app.hospital.test";

async function destinoDoCallback(query: string): Promise<string | null> {
  const resposta = await GET(new NextRequest(`${SITE}/auth/callback?${query}`));
  return resposta.headers.get("location");
}

describe("o destino do callback do login", () => {
  beforeEach(() => {
    exchangeCodeForSession.mockReset();
    exchangeCodeForSession.mockResolvedValue({ error: null });
  });

  it("sem destino, a pessoa cai no Início", async () => {
    expect(await destinoDoCallback("code=abc")).toBe(`${SITE}/inicio`);
  });

  it("com destino interno, a pessoa volta para ele", async () => {
    expect(await destinoDoCallback(`code=abc&next=${encodeURIComponent("/ouvidoria/casos/7")}`)).toBe(
      `${SITE}/ouvidoria/casos/7`
    );
  });

  it.each(["//evil.com", "https://evil.com/x", "/\\evil.com", "javascript:alert(1)"])(
    "destino para fora (%s) cai no Início, sem sair do site",
    async (externo) => {
      expect(await destinoDoCallback(`code=abc&next=${encodeURIComponent(externo)}`)).toBe(
        `${SITE}/inicio`
      );
    }
  );

  it("code que não vira sessão volta para o login com erro", async () => {
    exchangeCodeForSession.mockResolvedValue({ error: new Error("code inválido") });
    expect(await destinoDoCallback("code=abc&next=/ouvidoria")).toBe(
      `${SITE}/login?error=auth_callback_failed`
    );
  });
});
