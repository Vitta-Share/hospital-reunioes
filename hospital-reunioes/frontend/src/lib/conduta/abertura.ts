/**
 * A chave de abertura do Canal de Conduta vista pela página pública (issue
 * #1843, ADR 0097, decisão 11).
 *
 * O servidor do Next pergunta ao backend antes de entregar qualquer tela de
 * `/conduta`. Fechado, ou sem resposta, a página responde 404, como se não
 * existisse: na dúvida, o canal fica fechado. A pergunta sai do servidor do
 * Next, sem cookie nem sessão de ninguém.
 */
export async function canalAberto(): Promise<boolean> {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  try {
    const resposta = await fetch(`${apiBase}/conduta/abertura`, { cache: "no-store" });
    return resposta.ok;
  } catch {
    return false;
  }
}
