/**
 * O texto que o Canal de Conduta passa à Ouvidoria (issue #1847, seção 4.1 da
 * especificação do PRD #1786): quem escreveu no Canal um assunto que é da
 * Ouvidoria vai ao formulário dela com o texto já escrito.
 *
 * O texto viaja pela memória da aba (sessionStorage), nunca pelo endereço da
 * página: query, hash e caminho ficam no histórico do navegador, no log do
 * servidor e no cabeçalho Referer. O Canal guarda com `guardarTextoParaAOuvidoria`
 * e leva a pessoa a `/manifestacao`; o formulário toma o texto uma vez só, e
 * ele some da memória ao ser lido.
 */

const CHAVE = "ouvidoria:texto-vindo-do-canal";

function memoriaDaAba(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    // Navegador que bloqueia o armazenamento: o formulário abre vazio.
    return null;
  }
}

export function guardarTextoParaAOuvidoria(texto: string): void {
  try {
    memoriaDaAba()?.setItem(CHAVE, texto);
  } catch {
    // Memória cheia ou bloqueada: a pessoa chega ao formulário vazio.
  }
}

/** O texto guardado pelo Canal, que deixa a memória ao ser lido; sem nada, `null`. */
export function tomarTextoVindoDoCanal(): string | null {
  const memoria = memoriaDaAba();
  if (!memoria) return null;
  try {
    const texto = memoria.getItem(CHAVE);
    memoria.removeItem(CHAVE);
    return texto && texto.trim() ? texto : null;
  } catch {
    return null;
  }
}
