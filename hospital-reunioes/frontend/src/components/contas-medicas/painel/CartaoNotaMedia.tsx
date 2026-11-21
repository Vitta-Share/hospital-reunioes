import { DICA_DO_NUMERO, textoDaNota, type Painel } from "@/lib/contas-medicas/painel";

import { NumeroDaFaixa } from "./FaixaDosNumeros";
import { Apoio, Numero } from "./Moldura";

/** A nota média de entrada das contas concluídas na semana, com a da anterior ao lado. */
export function CartaoNotaMedia({ nota }: { nota: NonNullable<Painel["nota_media"]> }) {
  return (
    <NumeroDaFaixa titulo="Nota média de entrada" dica={DICA_DO_NUMERO.nota_media}>
      <Numero>{textoDaNota(nota.semana)}</Numero>
      <Apoio>Semana anterior: {textoDaNota(nota.anterior)}</Apoio>
    </NumeroDaFaixa>
  );
}
