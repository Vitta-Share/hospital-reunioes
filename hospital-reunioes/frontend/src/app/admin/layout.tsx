import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";
import { RedirecionarParaLogin } from "@/components/auth/RedirecionarParaLogin";
import { isSuperAdmin, type AuthUser } from "@/lib/auth";

/**
 * Layout do painel /admin.
 *
 * Protecao:
 * - Sem user -> /login (com retorno so na aba Tecnologia, issue #1587).
 * - User que nao e super admin -> /dashboard.
 *
 * O Admin inteiro e so do Super admin (ADR 0101): Dados do Atendimento era o
 * unico modulo aberto a secretaria e ao facilitador, e fechou. O backend segue
 * sendo o gate dos dados (403); este impede a pagina.
 *
 * O participante e lido via backend (/api/participantes/me), que roda
 * com service_role e bypassa RLS. Consulta direta a tabela participantes via
 * anon client seria bloqueada pelo default-deny da migration 009.
 */
export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  // Sem sessão, o encaminhador vai no LUGAR dos filhos: ele lê o endereço no
  // navegador e deixa o link de um pedido da aba Tecnologia voltar a ele depois
  // do login (issue #1587); o resto do admin vai para o login limpo.
  if (!user) return <RedirecionarParaLogin />;

  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return <RedirecionarParaLogin />;

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  const res = await fetch(`${apiBase}/participantes/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) redirect("/dashboard");
  const me = (await res.json()) as AuthUser;
  if (!isSuperAdmin(me)) redirect("/dashboard");

  const nome =
    (user.user_metadata?.nome as string) ||
    user.email?.split("@")[0] ||
    "Usuário";

  return (
    <AppShell userName={nome} userEmail={user.email} variant="admin">
      {children}
    </AppShell>
  );
}
