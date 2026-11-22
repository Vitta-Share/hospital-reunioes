/**
 * O cartão do Pedido da Vitta (issue #2176, ADR 0110, decisão 1): a Pergunta
 * ou o Passo a passo, pelo tipo que o servidor manda. Sem tipo é Pergunta. A
 * Conversa da Demanda e a lista Esperando você desenham este, e não um dos
 * dois direto, para os dois tipos terem o mesmo lugar.
 */

import { CartaoDaPergunta, type PerguntaDaVitta, type PerguntaRespondida } from "./CartaoDaPergunta";
import { CartaoDoPassoAPasso, type PassoAPassoConcluido } from "./CartaoDoPassoAPasso";

export function CartaoDoPedido({
  pedido,
  agora,
  token = null,
  onRespondida,
  onConcluido,
}: {
  pedido: PerguntaDaVitta;
  agora?: Date;
  token?: string | null;
  onRespondida?: (respondida: PerguntaRespondida) => void;
  onConcluido?: (concluido: PassoAPassoConcluido) => void;
}) {
  if (pedido.tipo === "passo_a_passo") {
    return <CartaoDoPassoAPasso pedido={pedido} agora={agora} token={token} onConcluido={onConcluido} />;
  }
  return <CartaoDaPergunta pergunta={pedido} agora={agora} token={token} onRespondida={onRespondida} />;
}
