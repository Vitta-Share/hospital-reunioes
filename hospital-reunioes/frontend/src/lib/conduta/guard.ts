// Imports relativos, e não pelo alias `@/`: o vitest do projeto roda sem
// config, e é por eles que este gate consegue ter teste.
import { redirect } from "next/navigation";
import { createClient } from "../supabase/server";

async function perguntarAoPortao(...rotas: string[]) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) redirect("/login");

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  // Com mais de uma rota, basta uma abrir; elas são perguntadas na ordem.
  for (const rota of rotas) {
    const res = await fetch(`${apiBase}${rota}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (res.ok) return { user };
  }
  // Falha de leitura também fecha a porta: sem saber quem é, ninguém entra.
  redirect("/dashboard");
}

/**
 * Gate server-side da área /comite-de-conduta (issue #1824, ADR 0097).
 *
 * A pergunta vai ao portão do próprio módulo (`/api/comite-de-conduta/minha-vez`),
 * que sabe quem está designado. Quem ele recusa, o super admin inclusive,
 * volta ao início sem receber a página.
 */
export async function requireComiteDeCondutaAccess() {
  return perguntarAoPortao("/comite-de-conduta/minha-vez");
}

/**
 * Gate server-side da tela Membros do Comitê de Conduta (issue #1822).
 *
 * A pergunta vai à própria rota da tela, que sabe quem entra: quem está no
 * Comitê hoje e quem tem o perfil de cadastro de membros. O super admin sem um
 * dos dois é recusado lá e volta ao início sem receber a página.
 */
export async function requireMembrosDoComiteAccess() {
  return perguntarAoPortao("/comite-de-conduta/membros");
}

/**
 * Gate server-side da tela Configurações do Canal de Conduta (issue #1826).
 *
 * A pergunta vai à própria rota da tela, que só abre para a coordenação
 * vigente do Comitê. Quem ela recusa, o super admin inclusive, volta ao início
 * sem receber a página.
 */
export async function requireConfiguracoesDoCanalAccess() {
  return perguntarAoPortao("/comite-de-conduta/configuracoes");
}

/**
 * Gate server-side do Guia do rito (issue #1842). O guia não leva caso, e
 * abre para quem vê qualquer tela do Comitê: quem o portão dos casos deixa
 * entrar (o apurador designado inclusive) e quem entra na tela Membros, que é
 * onde o membro sem o Termo assinado chega.
 */
export async function requireGuiaDoRitoAccess() {
  return perguntarAoPortao("/comite-de-conduta/minha-vez", "/comite-de-conduta/membros");
}
