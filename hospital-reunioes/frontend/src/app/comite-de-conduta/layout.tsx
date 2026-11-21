import { AppShell } from "@/components/layout/AppShell";
import { requireComiteDeCondutaAccess } from "@/lib/conduta/guard";

/**
 * Layout da área /comite-de-conduta (issue #1824, ADR 0097): AppShell e o
 * portão do módulo no servidor, antes de a página existir. Quem o portão
 * recusa volta ao início.
 */
export default async function ComiteDeCondutaLayout({ children }: { children: React.ReactNode }) {
  const { user } = await requireComiteDeCondutaAccess();

  const nome = (user.user_metadata?.nome as string) || user.email?.split("@")[0] || "Usuário";

  return (
    <AppShell userName={nome} userEmail={user.email}>
      {children}
    </AppShell>
  );
}
