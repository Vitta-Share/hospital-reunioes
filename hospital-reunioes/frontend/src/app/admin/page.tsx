import { redirect } from "next/navigation";

/**
 * Raiz do painel admin: leva a Usuários. O Admin é só do Super admin (ADR
 * 0101) e o gate de acesso é feito pelo layout; aqui só se escolhe o destino.
 */
export default async function AdminRootPage() {
  redirect("/admin/usuarios");
}
