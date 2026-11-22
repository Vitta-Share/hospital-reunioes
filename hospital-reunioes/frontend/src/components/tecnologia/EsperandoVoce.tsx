"use client";

/**
 * A lista Esperando você (issue #2118, PRD #2112, ADR 0109, decisão 5; desde
 * a issue #2176, ADR 0110). Antes se chamava Esperando sua resposta.
 *
 * Junta os dois tipos de Pedido da Vitta, a Pergunta e o Passo a passo, cada
 * um com o seu ícone no cartão. O que está com a própria Vitta (o
 * Destinatário é Desenvolvedor) vem por último, no grupo "Com a Vitta", para
 * o diretor ver o que anda do lado de lá. O Passo a passo concluído sai da
 * lista na hora, como a Pergunta respondida.
 *
 * No topo da aba Tecnologia, as Perguntas da Vitta abertas de todos os
 * Projetos, cada uma no cartão da Pergunta, com o nome da Demanda. A ordem é a
 * do servidor: as do usuário logado primeiro e, em cada grupo, a mais antiga
 * primeiro. Sem Pergunta aberta, ou com a recusa de quem não é Super admin, a
 * lista não ocupa espaço. `perguntaEmFoco` é o `?pergunta=` do aviso (sino e
 * e-mail): o cartão dela vem em foco.
 *
 * Responder no cartão da lista (issue #2145): o cartão recebe o token, e quem o
 * servidor diz que responde (`pode_responder`, as regras da Conversa da
 * Demanda) vê as opções, o campo livre e o Me explique. A Pergunta respondida
 * sai da lista na hora, sem reler: a lista só traz as abertas.
 *
 * O nome é Pergunta da Vitta, nunca Pendência (ADR 0109, decisão 2).
 */

import { useEffect, useRef, useState } from "react";

import { perguntaValida, type PerguntaDaVitta, type PerguntaRespondida } from "./CartaoDaPergunta";
import { CartaoDoPedido } from "./CartaoDoPedido";
import type { PassoAPassoConcluido } from "./CartaoDoPassoAPasso";
import { BASE_TECNOLOGIA } from "./demandas";

export const URL_DA_LISTA_ESPERANDO = `${BASE_TECNOLOGIA}/perguntas/esperando`;

type PerguntaEsperando = PerguntaDaVitta & {
  demanda_id: string;
  demanda: string;
  minha: boolean;
  /** O Destinatário é Desenvolvedor: o Pedido está com a Vitta (ADR 0110, decisão 2). */
  com_a_vitta?: boolean;
};

function itemValido(item: unknown): item is PerguntaEsperando {
  return perguntaValida(item) && typeof (item as Record<string, unknown>).demanda === "string";
}

export function EsperandoVoce({
  token,
  perguntaEmFoco = null,
  agora,
}: {
  token: string | null;
  perguntaEmFoco?: string | null;
  agora?: Date;
}) {
  const [itens, setItens] = useState<PerguntaEsperando[] | null>(null);
  /** Muda para reler a lista. */
  const [leitura, setLeitura] = useState(0);
  /** A Pergunta do endereço que a última leitura já cobriu. */
  const coberta = useRef<string | null>(perguntaEmFoco);
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
  }, [token, leitura]);

  // Com a aba já aberta, o sino de uma Pergunta que nasceu depois da leitura só
  // troca o `?pergunta=` (o Next não remonta a página): fora da lista, relê uma vez.
  useEffect(() => {
    if (!perguntaEmFoco || perguntaEmFoco === coberta.current || itens === null) return;
    coberta.current = perguntaEmFoco;
    if (!itens.some((item) => item.id === perguntaEmFoco)) setLeitura((n) => n + 1);
  }, [perguntaEmFoco, itens]);

  useEffect(() => {
    const alvo = emFoco.current;
    if (!alvo) return;
    alvo.scrollIntoView?.({ block: "center" });
    alvo.focus();
  }, [itens, perguntaEmFoco]);

  function sair({ pergunta }: PerguntaRespondida | PassoAPassoConcluido) {
    setItens((atuais) => (atuais ?? []).filter((item) => item.id !== pergunta.id));
  }

  if (!itens || itens.length === 0) return null;

  const daqui = itens.filter((item) => !item.com_a_vitta);
  const comAVitta = itens.filter((item) => item.com_a_vitta);

  function lista(grupo: PerguntaEsperando[], rotulo: string) {
    return (
      <ul aria-label={rotulo} className="min-w-0 space-y-3">
        {grupo.map((item) => {
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
              <CartaoDoPedido pedido={item} agora={agora} token={token} onRespondida={sair} onConcluido={sair} />
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <section aria-label="Esperando você" className="min-w-0 space-y-3">
      <h2 className="text-lg font-bold text-text">
        Esperando você <span className="text-sm font-medium text-text-secondary">({itens.length})</span>
      </h2>
      {daqui.length > 0 && lista(daqui, "Pedidos da Vitta")}
      {comAVitta.length > 0 && (
        <div className="min-w-0 space-y-2">
          <h3 className="text-sm font-bold text-text">Com a Vitta</h3>
          <p className="normal-case text-xs text-text-secondary">O que a própria Vitta precisa fazer, para você acompanhar.</p>
          {lista(comAVitta, "Com a Vitta")}
        </div>
      )}
    </section>
  );
}
