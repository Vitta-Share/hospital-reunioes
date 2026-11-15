import { AppShell } from "@/components/layout/AppShell";
import { requireSegurancaDoPacienteAccess } from "@/lib/seguranca-do-paciente/guard";

/**
 * Layout da área /seguranca-do-paciente (ADR 0095): AppShell e o gate do
 * módulo no servidor, antes de a página existir. Quem o módulo recusa (o
 * super admin sem Acesso pleno inclusive) volta ao início. Os títulos saem em
 * caixa alta pela regra base (ADR 0080).
 */
export default async function SegurancaDoPacienteLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user } = await requireSegurancaDoPacienteAccess();

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
