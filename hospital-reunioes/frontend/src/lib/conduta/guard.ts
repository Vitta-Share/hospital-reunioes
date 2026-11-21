// Imports relativos, e não pelo alias `@/`: mesmo motivo do gate de
// Segurança do Paciente (o vitest do projeto roda sem config).
import { redirect } from "next/navigation";
import { createClient } from "../supabase/server";

/**
 * Gate server-side da tela Membros do Comitê de Conduta (issue #1822).
 *
 * A pergunta vai à própria rota da tela, que sabe quem entra: quem está no
 * Comitê hoje e quem tem o perfil de cadastro de membros. O super admin sem um
 * dos dois é recusado lá e volta ao início sem receber a página.
 */
export async function requireMembrosDoComiteAccess() {
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
  const res = await fetch(`${apiBase}/comite-de-conduta/membros`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  // Falha de leitura também fecha a porta.
  if (!res.ok) redirect("/dashboard");

  return { user };
}
