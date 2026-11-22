import { AppShell } from "@/components/layout/AppShell";
import { requireRecomendacoesDoComiteAccess } from "@/lib/conduta/guard";

/**
 * Layout das Recomendações do Comitê (issue #1835): AppShell e o gate no
 * servidor, antes de a página existir. Fica fora do grupo `(comite)`: o
 * Presidente e a diretoria executiva não passam pelo portão dos casos.
 */
export default async function RecomendacoesDoComiteLayout({ children }: { children: React.ReactNode }) {
  const { user } = await requireRecomendacoesDoComiteAccess();

  const nome = (user.user_metadata?.nome as string) || user.email?.split("@")[0] || "Usuário";

  return (
    <AppShell userName={nome} userEmail={user.email}>
      {children}
    </AppShell>
  );
}
