"use client";

/**
 * A Tela do responsável aberta pelo app (issue #1886, ADR 0099, decisão 4).
 *
 * O botão RESPONDER da fila abre aqui. É a mesma tela do link do email, com o
 * login no lugar do token: a rota é pelo id da manifestação, e cada pedido leva
 * a sessão de quem está logado. Quem recusa o caso de outro setor é o servidor,
 * com 403. Deslogado não chega aqui: o layout da Ouvidoria manda para o login
 * com este endereço de volta.
 */

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { TelaDoResponsavel } from "@/components/ouvidoria/TelaDoResponsavel";

export default function ResponderPeloAppPage() {
  const params = useParams();
  const id = params.id as string;

  // Estável entre renders: a tela recarrega o caso quando a porta muda.
  const pedir = useCallback(async (url: string, init?: RequestInit) => {
    const {
      data: { session },
    } = await createClient().auth.getSession();
    const headers = new Headers(init?.headers);
    if (session?.access_token) headers.set("Authorization", `Bearer ${session.access_token}`);
    return fetch(url, { ...init, headers });
  }, []);

  return <TelaDoResponsavel endereco={`/api/ouvidoria/responder/${encodeURIComponent(id)}`} pedir={pedir} peloApp />;
}
