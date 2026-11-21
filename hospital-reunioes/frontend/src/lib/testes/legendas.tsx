import type { ReactElement } from "react";

import { LegendasProvider } from "@/components/ui/Legenda";

const CHAVE_DE_TESTE = "teste:legendas";

/**
 * A tela dentro de um provedor de Legendas ligado ou desligado, como a casca
 * do módulo a entrega (issue #1950). Serve para provar que um texto da tela é
 * uma Legenda: some quando o interruptor desliga e volta quando liga.
 */
export function comLegendas(ligadas: boolean, tela: ReactElement): ReactElement {
  window.localStorage.setItem(CHAVE_DE_TESTE, ligadas ? "1" : "0");
  return <LegendasProvider chave={CHAVE_DE_TESTE}>{tela}</LegendasProvider>;
}
