/**
 * A raiz do `/admin` (issue #1907, ADR 0101).
 *
 * Ela mandava quem não é super admin para Dados do Atendimento: era o caminho
 * do relato do diretor. O Admin agora é só do Super admin (o layout barra os
 * outros), e a raiz tem um destino só.
 */
import { expect, it, vi } from "vitest";

const redirect = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: (destino: string) => redirect(destino),
}));

import AdminRootPage from "./page";

it("a raiz do Admin leva a Usuários, e nunca a Dados do Atendimento", async () => {
  await AdminRootPage();

  expect(redirect.mock.calls).toEqual([["/admin/usuarios"]]);
});
