import { redirect } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { createClient } from "@/lib/supabase/server";

/**
 * Layout da área logada do Comitê de Conduta (PRD #1786, ADR 0097). Sem
 * sessão, vai ao login. Quem abre cada tela é a API, pelo portão do módulo:
 * aqui não se decide acesso a nada.
 */
export default async function ComiteDeCondutaLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const nome = (user.user_metadata?.nome as string) || user.email?.split("@")[0] || "Usuário";

  return (
    <AppShell userName={nome} userEmail={user.email}>
      {children}
    </AppShell>
  );
}
