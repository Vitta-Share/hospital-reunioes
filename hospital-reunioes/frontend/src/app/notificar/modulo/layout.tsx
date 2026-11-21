import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";

/**
 * O botão "Notificar incidente" do módulo Segurança do Paciente (issue #1987,
 * Ajuste do plano #2045). Todo usuário logado entra, mesmo sem outro acesso ao
 * Núcleo: por isso a página fica fora de `/seguranca-do-paciente`, cujo layout
 * barra quem não abre o módulo. Exige só a sessão.
 */
export default async function NotificarPeloModuloLayout({ children }: { children: React.ReactNode }) {
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
