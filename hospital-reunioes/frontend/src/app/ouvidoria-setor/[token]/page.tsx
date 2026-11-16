"use client";

/**
 * Portal do setor por link tokenizado (issue #326, ADR 0034 decisão 4).
 *
 * O titular chega pelo link do email de acionamento, sem senha: o token opaco
 * de uso único é a credencial, no padrão do Aceite interno. A tela é a mesma
 * que o botão RESPONDER abre dentro do app (issue #1886, ADR 0099): ela mora
 * em `TelaDoResponsavel`, e esta página só diz qual é a porta.
 */

import { useParams } from "next/navigation";
import { TelaDoResponsavel } from "@/components/ouvidoria/TelaDoResponsavel";

export default function PortalDoSetorPage() {
  const params = useParams();
  const token = params.token as string;
  return <TelaDoResponsavel endereco={`/api/ouvidoria-setor/${encodeURIComponent(token)}`} />;
}
