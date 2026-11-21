/**
 * A busca da tela de contas (issue #1956, ADR 0105, decisão 4): a rota, o
 * que ela devolve e o trecho que a tela marca no número ou no nome de cada
 * resultado. Quem procura é o servidor, em todas as etapas.
 */
import type { ItemDaFila } from "./envio";
import type { Etapa } from "./textos";

export const ROTA_BUSCA = "/api/contas-medicas/busca";
/** A busca começa no segundo caractere. */
export const MINIMO_DA_BUSCA = 2;
/** Quanto a tela espera depois da última tecla para buscar. */
export const ESPERA_DA_BUSCA_MS = 300;
/** O máximo de contas que a rota devolve. */
export const TETO_DA_BUSCA = 50;

export function rotaDaBusca(texto: string): string {
  return `${ROTA_BUSCA}?q=${encodeURIComponent(texto)}`;
}

/** A conta achada: a etapa em que está e se a pessoa pode abrir o Guia dela. */
export interface ItemDaBusca extends ItemDaFila {
  etapa_da_esteira: Etapa;
  pode_abrir: boolean;
}

export interface RespostaDaBusca {
  contas: ItemDaBusca[];
  /** Há mais que o teto: a tela pede para refinar. */
  mais: boolean;
}

/** Cada caractere sem acento e em minúscula, com o lugar dele no texto original. */
function semAcento(texto: string): { letras: string; origem: number[] } {
  let letras = "";
  const origem: number[] = [];
  Array.from(texto).forEach((caractere, i) => {
    const limpo = caractere.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
    for (const letra of limpo) {
      letras += letra;
      origem.push(i);
    }
  });
  return { letras, origem };
}

/**
 * O texto partido em antes, trecho achado e depois, sem diferenciar
 * maiúscula nem acento, como a rota procura. Sem o trecho, nulo.
 */
export function trechoAchado(texto: string, termo: string): [string, string, string] | null {
  const alvo = semAcento(termo.trim()).letras;
  if (!alvo) return null;
  const { letras, origem } = semAcento(texto);
  const inicio = letras.indexOf(alvo);
  if (inicio < 0) return null;
  const caracteres = Array.from(texto);
  const de = origem[inicio];
  const ate = origem[inicio + alvo.length - 1] + 1;
  return [caracteres.slice(0, de).join(""), caracteres.slice(de, ate).join(""), caracteres.slice(ate).join("")];
}

/** Os textos da busca, para o teste e o manual lerem a mesma frase. */
export const NOME_DA_BUSCA = "Buscar conta";
export const DICA_DA_BUSCA = "Número do atendimento ou nome do paciente";
export const DIGITE_MAIS = "Digite pelo menos 2 caracteres para buscar.";
export const SEM_RESULTADO = "Nenhuma conta com esse número ou nome. A busca olhou todas as etapas.";
export const REFINE_A_BUSCA = `Aparecem só as ${TETO_DA_BUSCA} primeiras. Digite mais do número ou do nome para refinar.`;
export const ERRO_DA_BUSCA = "Não consegui buscar. Tente de novo.";
