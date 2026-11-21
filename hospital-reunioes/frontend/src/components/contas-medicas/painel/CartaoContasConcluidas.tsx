import { DICA_DO_NUMERO, type Painel } from "@/lib/contas-medicas/painel";

import { NumeroDaFaixa } from "./FaixaDosNumeros";
import { Apoio, Numero } from "./Moldura";

/** Quantas contas foram concluídas na semana. */
export function CartaoContasConcluidas({ contas }: { contas: NonNullable<Painel["contas_concluidas"]> }) {
  return (
    <NumeroDaFaixa titulo="Contas concluídas" dica={DICA_DO_NUMERO.contas_concluidas}>
      <Numero>{contas.total}</Numero>
      <Apoio>{contas.total === 1 ? "conta na semana" : "contas na semana"}</Apoio>
    </NumeroDaFaixa>
  );
}
