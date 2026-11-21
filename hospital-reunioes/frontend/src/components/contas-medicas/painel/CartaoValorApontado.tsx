import { DICA_DO_NUMERO, textoEmReais, type Painel } from "@/lib/contas-medicas/painel";

import { NumeroDaFaixa } from "./FaixaDosNumeros";
import { Apoio, Numero } from "./Moldura";

/** O R$ apontado nas contas da semana, com quanto disso já entrou no MV (as linhas Feito). */
export function CartaoValorApontado({ valor }: { valor: NonNullable<Painel["valor_apontado"]> }) {
  return (
    <NumeroDaFaixa titulo="R$ apontado" dica={DICA_DO_NUMERO.valor_apontado}>
      <Numero>{textoEmReais(valor.total)}</Numero>
      <Apoio>Já incluídos: {textoEmReais(valor.ja_incluido)}</Apoio>
    </NumeroDaFaixa>
  );
}
