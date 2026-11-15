// Imports relativos, e não pelo alias `@/`: o vitest do projeto roda sem
// config, e é por eles que este gate consegue ter teste.
import { redirect } from "next/navigation";
import { createClient } from "../supabase/server";

/**
 * Gate server-side da área /seguranca-do-paciente (issue #1765, ADR 0095).
 *
 * Mesmo desenho do gate de Contas médicas: a pergunta vai à rota do próprio
 * módulo (`/api/nsp/inicio`), que sabe quem entra pela permissão efetiva
 * (Participação vigente, Acesso pleno, Diretoria). O super admin sem Acesso
 * pleno é recusado lá (decisão 4), e volta ao início sem receber a página.
 */
export async function requireSegurancaDoPacienteAccess() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) redirect("/login");

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  const res = await fetch(`${apiBase}/nsp/inicio`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  // Falha de leitura também fecha a porta: sem saber quem é, ninguém entra.
  if (!res.ok) redirect("/dashboard");

  return { user };
}
