"use client";

import { useEffect, useState } from "react";

import { ROTA_DA_ABERTURA } from "@/lib/conduta/publico";

/**
 * Se o Canal de Conduta está aberto, visto do navegador (issue #1847, ADR 0097
 * decisão 11). A rota pública responde 200 aberto e 404 fechado. Até a
 * resposta chegar, ou se ela falhar, o canal conta como fechado: a saída para
 * ele nunca aparece por engano. A pergunta sai sem cookie nem sessão.
 */
export function useCanalDeCondutaAberto(): boolean {
  const [aberto, setAberto] = useState(false);

  useEffect(() => {
    let vivo = true;
    fetch(ROTA_DA_ABERTURA, { credentials: "omit", cache: "no-store" })
      .then((res) => {
        if (vivo) setAberto(res.ok);
      })
      .catch(() => {
        if (vivo) setAberto(false);
      });
    return () => {
      vivo = false;
    };
  }, []);

  return aberto;
}
