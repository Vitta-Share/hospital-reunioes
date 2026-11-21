import { DICA_DO_NUMERO, textoEmReais, type Painel } from "@/lib/contas-medicas/painel";

import { NumeroDaFaixa } from "./FaixaDosNumeros";
import { Apoio, Numero } from "./Moldura";

/**
 * O R$ que a coordenadora incluiu na semana pelos lembretes da Conferência da
 * coordenação (issue #1143). Vem numa chave própria, só para quem tem a
 * permissão, e não entra na nota de entrada nem na produção das faturistas.
 */
export function CartaoCoordenacao({ coordenacao }: { coordenacao: NonNullable<Painel["coordenacao"]> }) {
  const lembretes = coordenacao.lembretes_incluidos;
  return (
    <NumeroDaFaixa titulo="R$ incluído pela coordenação" dica={DICA_DO_NUMERO.coordenacao}>
      <Numero>{textoEmReais(coordenacao.valor_incluido)}</Numero>
      <Apoio>{lembretes === 1 ? "1 lembrete incluído" : `${lembretes} lembretes incluídos`}</Apoio>
    </NumeroDaFaixa>
  );
}
