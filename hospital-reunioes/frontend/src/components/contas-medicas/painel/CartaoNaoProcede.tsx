import { DICA_DO_NUMERO, textoDaTaxa, type Painel } from "@/lib/contas-medicas/painel";

import { NumeroDaFaixa } from "./FaixaDosNumeros";
import { Apoio, Numero } from "./Moldura";

/** A taxa de Não procede: linhas Não procede sobre as apontadas, sem Validar. */
export function CartaoNaoProcede({ naoProcede }: { naoProcede: NonNullable<Painel["nao_procede"]> }) {
  return (
    <NumeroDaFaixa titulo="Não procede" dica={DICA_DO_NUMERO.nao_procede}>
      <Numero>{textoDaTaxa(naoProcede.taxa)}</Numero>
      <Apoio>
        {naoProcede.linhas} de {naoProcede.de} {naoProcede.de === 1 ? "linha" : "linhas"}
      </Apoio>
    </NumeroDaFaixa>
  );
}
