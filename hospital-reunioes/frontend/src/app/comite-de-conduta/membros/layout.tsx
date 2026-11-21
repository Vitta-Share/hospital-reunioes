import { ApresentacaoDoComite } from "@/components/conduta/ApresentacaoDoComite";
import { AppShell } from "@/components/layout/AppShell";
import { requireMembrosDoComiteAccess } from "@/lib/conduta/guard";
import { precisaDaApresentacao } from "@/lib/conduta/guia";

/**
 * Layout da tela Membros do Comitê de Conduta (issue #1822): AppShell e o
 * gate no servidor, antes de a página existir. Quem a rota recusa (o super
 * admin sem o perfil de cadastro inclusive) volta ao início.
 */
export default async function MembrosDoComiteLayout({ children }: { children: React.ReactNode }) {
  const { user } = await requireMembrosDoComiteAccess();

  const nome = (user.user_metadata?.nome as string) || user.email?.split("@")[0] || "Usuário";

  return (
    <AppShell userName={nome} userEmail={user.email}>
      {children}
      {precisaDaApresentacao(user) && <ApresentacaoDoComite pessoa={user.id} />}
    </AppShell>
  );
}
