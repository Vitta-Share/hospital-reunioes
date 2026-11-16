/**
 * Perfil de acesso é determinado por `access_profile` (enum único).
 * Fallback (fase 1 da migração 035): se access_profile não estiver presente,
 * usa is_super_admin pra compatibilidade.
 */

import type {
  AccessProfile,
  PapelOuvidoria,
  PerfilContasMedicas,
  PerfilOuvidoria,
  PerfilPop,
} from "@/types";

export interface AuthUser {
  id?: string;
  email?: string;
  role?: string | null;
  is_super_admin?: boolean;
  access_profile?: AccessProfile | null;
  perfil_pop?: PerfilPop | null;
  perfil_ouvidoria?: PerfilOuvidoria | null;
  perfil_contas_medicas?: PerfilContasMedicas | null;
  recursos_nsp?: string[];
  papel_ouvidoria?: PapelOuvidoria | null;
}

export function isSuperAdmin(user: AuthUser | null | undefined): boolean {
  if (!user) return false;
  if (user.access_profile) return user.access_profile === "super_admin";
  return user.is_super_admin === true;
}

export function isSecretaria(user: AuthUser | null | undefined): boolean {
  return user?.access_profile === "secretaria";
}

export function isRegular(user: AuthUser | null | undefined): boolean {
  if (!user) return false;
  if (user.access_profile) return user.access_profile === "regular";
  return user.is_super_admin !== true;
}

/**
 * Contexto POPs (ADR 0007): perfil_pop é o eixo de permissão próprio,
 * ortogonal ao access_profile das Reuniões.
 */
export function temPerfilPop(user: AuthUser | null | undefined): boolean {
  return Boolean(user?.perfil_pop);
}

export function isSuperadminPops(user: AuthUser | null | undefined): boolean {
  return user?.perfil_pop === "superadmin";
}

/**
 * Contexto Ouvidoria (ADR 0034): `perfil_ouvidoria` é o terceiro eixo de
 * permissão, ortogonal ao das Reuniões e ao dos POPs. Ter o campo preenchido
 * (`ouvidor` ou `diretoria_executiva`) é ser da Ouvidoria; nulo é estar fora
 * dela, mesmo sendo super admin de Reuniões.
 */
export function temPerfilOuvidoria(user: AuthUser | null | undefined): boolean {
  return Boolean(user?.perfil_ouvidoria);
}

/**
 * O papel na Ouvidoria (ADR 0099). Quem decide é o servidor, em
 * `papel_ouvidoria`; sem ele (o cadastro de responsáveis não pôde ser lido),
 * vale o que dá para saber aqui: o Perfil da Ouvidoria e o índice geral da
 * Secretária e do Super admin. O responsável do setor só vem do servidor.
 */
export function papelNaOuvidoria(user: AuthUser | null | undefined): PapelOuvidoria {
  if (!user) return "nenhum";
  if (user.papel_ouvidoria) return user.papel_ouvidoria;
  if (temPerfilOuvidoria(user)) return "perfil_ouvidoria";
  if (isSecretaria(user) || isSuperAdmin(user)) return "indice_geral";
  return "nenhum";
}

/** Quem vê a Ouvidoria no menu e entra na rota (ADR 0099, decisão 3). */
export function temPapelNaOuvidoria(user: AuthUser | null | undefined): boolean {
  return papelNaOuvidoria(user) !== "nenhum";
}

/**
 * Contexto Contas médicas (ADR 0070, decisão 10): `perfil_contas_medicas` é o
 * quarto eixo. Ter um perfil nele, ou ser super admin do app (que passa em
 * todos os módulos, como no backend), é entrar no módulo. Decide o menu; quem
 * barra de verdade é o gate da rota no servidor.
 */
export function temAcessoContasMedicas(user: AuthUser | null | undefined): boolean {
  return isSuperAdmin(user) || Boolean(user?.perfil_contas_medicas);
}

/**
 * Segurança do Paciente (ADR 0095, decisão 4): quem entra no módulo é o
 * servidor que diz, em `recursos_nsp` (Participação vigente no Núcleo, Acesso
 * pleno ou Diretoria). Ao contrário de Contas médicas, o super admin não
 * entra só por ser super admin. Decide o menu; quem barra é a rota.
 */
export function temAcessoSegurancaDoPaciente(user: AuthUser | null | undefined): boolean {
  return Boolean(user?.recursos_nsp?.includes("ver_modulo"));
}

/**
 * True se a pessoa tem papel no contexto Reuniões. access_profile NULL
 * explícito = sem papel (ex.: Coordenador de POPs); campo ausente mantém o
 * comportamento legado (com acesso).
 */
export function temAcessoReunioes(user: AuthUser | null | undefined): boolean {
  if (!user) return false;
  if ("access_profile" in user) return user.access_profile != null;
  return true;
}

/**
 * @deprecated Use isSuperAdmin(user). O modelo agora usa access_profile.
 */
export function isSuperUser(_role: string): boolean {
  if (typeof console !== "undefined" && console.warn) {
    console.warn(
      "[auth] isSuperUser(role) está deprecado. Use isSuperAdmin(user) lendo user.access_profile."
    );
  }
  return false;
}
