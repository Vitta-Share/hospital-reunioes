"use client";

/**
 * A lista Esperando sua resposta (issue #2118, PRD #2112, ADR 0109, decisão 5).
 *
 * No topo da aba Tecnologia, as Perguntas da Vitta abertas de todos os
 * Projetos, cada uma no cartão da Pergunta, com o nome da Demanda. A ordem é a
 * do servidor: as do usuário logado primeiro e, em cada grupo, a mais antiga
 * primeiro. Sem Pergunta aberta, ou com a recusa de quem não é Super admin, a
 * lista não ocupa espaço. `perguntaEmFoco` é o `?pergunta=` do aviso (sino e
 * e-mail): o cartão dela vem em foco.
 *
 * O nome é Pergunta da Vitta, nunca Pendência (ADR 0109, decisão 2).
 */

import { useEffect, useRef, useState } from "react";

import { CartaoDaPergunta, perguntaValida, type PerguntaDaVitta } from "./CartaoDaPergunta";
import { BASE_TECNOLOGIA } from "./demandas";

export const URL_DA_LISTA_ESPERANDO = `${BASE_TECNOLOGIA}/perguntas/esperando`;

type PerguntaEsperando = PerguntaDaVitta & { demanda_id: string; demanda: string; minha: boolean };

function itemValido(item: unknown): item is PerguntaEsperando {
  return perguntaValida(item) && typeof (item as Record<string, unknown>).demanda === "string";
}

export function EsperandoSuaResposta({
  token,
  perguntaEmFoco = null,
  agora,
}: {
  token: string | null;
  perguntaEmFoco?: string | null;
  agora?: Date;
}) {
  const [itens, setItens] = useState<PerguntaEsperando[]>([]);
  const emFoco = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    if (!token) return;
    let vivo = true;
    (async () => {
      try {
        const resposta = await fetch(URL_DA_LISTA_ESPERANDO, { headers: { Authorization: `Bearer ${token}` } });
        if (!resposta.ok) return;
        const corpo: unknown = await resposta.json();
        if (vivo && Array.isArray(corpo)) setItens(corpo.filter(itemValido));
      } catch {
        // Sem conexão a lista só não aparece: o resto da aba segue.
      }
    })();
    return () => {
      vivo = false;
    };
  }, [token]);

  useEffect(() => {
    const alvo = emFoco.current;
    if (!alvo) return;
    alvo.scrollIntoView?.({ block: "center" });
    alvo.focus();
  }, [itens, perguntaEmFoco]);

  if (itens.length === 0) return null;

  return (
    <section aria-label="Esperando sua resposta" className="min-w-0 space-y-3">
      <h2 className="text-lg font-bold text-text">
        Esperando sua resposta <span className="text-sm font-medium text-text-secondary">({itens.length})</span>
      </h2>
      <ul className="min-w-0 space-y-3">
        {itens.map((item) => {
          const focado = item.id === perguntaEmFoco;
          return (
            <li
              key={item.id}
              ref={focado ? emFoco : undefined}
              tabIndex={focado ? -1 : undefined}
              aria-current={focado ? "true" : undefined}
              className={`min-w-0 break-words space-y-1 rounded-2xl outline-none ${
                focado ? "ring-2 ring-primary ring-offset-2" : ""
              }`}
            >
              <p className="normal-case text-xs text-text-secondary">
                Demanda: <span className="font-semibold text-text">{item.demanda}</span>
              </p>
              <CartaoDaPergunta pergunta={item} agora={agora} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}
