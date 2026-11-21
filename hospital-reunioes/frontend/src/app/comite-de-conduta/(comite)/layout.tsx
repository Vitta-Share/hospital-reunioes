import { ApresentacaoDoComite } from "@/components/conduta/ApresentacaoDoComite";
import { RedirecionarParaLogin } from "@/components/auth/RedirecionarParaLogin";
import { AppShell } from "@/components/layout/AppShell";
import { requireComiteDeCondutaAccess } from "@/lib/conduta/guard";
import { precisaDaApresentacao } from "@/lib/conduta/guia";
import { createClient } from "@/lib/supabase/server";

/**
 * Layout da área /comite-de-conduta (issue #1824, ADR 0097): AppShell e o
 * portão do módulo no servidor, antes de a página existir. Quem o portão
 * recusa volta ao início.
 *
 * Fica no grupo `(comite)` para não envolver a tela Membros (issue #1822), que
 * tem o gate e o AppShell dela: quem só tem o perfil de cadastro entra lá sem
 * passar pelo portão dos casos.
 */
export default async function ComiteDeCondutaLayout({ children }: { children: React.ReactNode }) {
  // Sem sessão, o encaminhador vai no LUGAR dos filhos e leva o endereço pedido
  // ao login: o convidado chega pelo link do e-mail e não tem o item no menu,
  // então voltar ao Início o deixaria sem caminho até o caso (issue #1825).
  const supabase = await createClient();
  const {
    data: { user: logado },
  } = await supabase.auth.getUser();
  if (!logado) return <RedirecionarParaLogin />;
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) return <RedirecionarParaLogin />;

  const { user } = await requireComiteDeCondutaAccess();

  const nome = (user.user_metadata?.nome as string) || user.email?.split("@")[0] || "Usuário";

  return (
    <AppShell userName={nome} userEmail={user.email}>
      {children}
      {precisaDaApresentacao(user) && <ApresentacaoDoComite pessoa={user.id} />}
    </AppShell>
  );
}
