import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";

/**
 * Layout do Início (ADR 0104): exige sessão e devolve a Secretária à tela
 * dela, que não tem Início (decisão 1). Os títulos saem em caixa alta pela
 * regra base (ADR 0080).
 */
export default async function InicioLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // Apura o perfil dentro do try para não capturar o NEXT_REDIRECT que o
  // redirect() lança.
  let ehSecretaria = false;
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const token = session?.access_token;
    if (token) {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
      const res = await fetch(`${apiBase}/participantes/me`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (res.ok) {
        const me = (await res.json()) as { access_profile?: string | null };
        ehSecretaria = me.access_profile === "secretaria";
      }
    }
  } catch {
    // Backend fora do ar: a tela abre e o servidor recusa o que não é dela.
  }
  if (ehSecretaria) redirect("/secretaria");

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
