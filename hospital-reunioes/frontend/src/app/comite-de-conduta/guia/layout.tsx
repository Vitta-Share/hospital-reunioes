import { ApresentacaoDoComite } from "@/components/conduta/ApresentacaoDoComite";
import { AppShell } from "@/components/layout/AppShell";
import { requireGuiaDoRitoAccess } from "@/lib/conduta/guard";
import { precisaDaApresentacao } from "@/lib/conduta/guia";

/**
 * Layout do Guia do rito do Comitê de Conduta (issue #1842): AppShell e o
 * gate no servidor. Fica fora do grupo `(comite)`, como Membros e
 * Configurações, porque o portão dos casos recusa o membro sem o Termo
 * assinado, e ele também lê o guia.
 */
export default async function GuiaDoRitoLayout({ children }: { children: React.ReactNode }) {
  const { user } = await requireGuiaDoRitoAccess();

  const nome = (user.user_metadata?.nome as string) || user.email?.split("@")[0] || "Usuário";

  return (
    <AppShell userName={nome} userEmail={user.email}>
      {children}
      {precisaDaApresentacao(user) && <ApresentacaoDoComite pessoa={user.id} />}
    </AppShell>
  );
}
