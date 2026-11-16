import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";
import { RedirecionarParaLogin } from "@/components/auth/RedirecionarParaLogin";

async function papelNaOuvidoria(
  supabase: Awaited<ReturnType<typeof createClient>>
): Promise<string | null> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return null;
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  try {
    const res = await fetch(`${apiBase}/participantes/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const me = (await res.json()) as { papel_ouvidoria?: string | null };
    return me.papel_ouvidoria ?? null;
  } catch {
    return null;
  }
}

export default async function OuvidoriaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Sem sessão, a área não monta: o que volta é o encaminhamento para o login,
  // no LUGAR dos filhos (issue #477, RN-54). Ele leva o endereço pedido junto,
  // para a pessoa cair no caso que tentou abrir em vez de na tela inicial.
  if (!user) return <RedirecionarParaLogin />;

  // Quem não tem papel na Ouvidoria não entra na área (issue #1884, ADR 0099,
  // decisão 3): o item some do menu e a rota manda para o Dashboard. Só o
  // "nenhum" dito pelo servidor barra; falha de leitura deixa a área montar, e
  // o servidor da fila recusa com 403 de qualquer jeito.
  if ((await papelNaOuvidoria(supabase)) === "nenhum") return redirect("/dashboard");

  const nome =
    (user.user_metadata?.nome as string) ||
    user.email?.split("@")[0] ||
    "Usuário";

  return (
    <AppShell userName={nome} userEmail={user.email}>
      {children}
    </AppShell>
  );
}
