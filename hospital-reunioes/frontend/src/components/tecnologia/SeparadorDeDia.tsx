/**
 * O separador por dia da Conversa da Demanda (issue #2117, PRD #2112): um traço
 * com a data entra entre mensagens de dias diferentes. O dia é o do hospital,
 * no fuso de São Paulo, como a linha do Envio aos desenvolvedores.
 */

const FUSO_DO_HOSPITAL = "America/Sao_Paulo";

/** O dia (AAAA-MM-DD) da mensagem no fuso do hospital, ou nulo sem data legível. */
export function diaDaMensagem(criadoEm: string | null): string | null {
  if (!criadoEm) return null;
  const data = new Date(criadoEm);
  if (Number.isNaN(data.getTime())) return null;
  // O sueco escreve a data como AAAA-MM-DD.
  return data.toLocaleDateString("sv-SE", { timeZone: FUSO_DO_HOSPITAL });
}

function porExtenso(dia: string): string {
  // Meio-dia em Greenwich cai no mesmo dia em São Paulo.
  return new Date(`${dia}T12:00:00Z`).toLocaleDateString("pt-BR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: FUSO_DO_HOSPITAL,
  });
}

export function SeparadorDeDia({ dia }: { dia: string }) {
  const rotulo = porExtenso(dia);
  return (
    <div role="separator" aria-label={rotulo} className="flex items-center gap-3 text-xs text-text-secondary">
      <span aria-hidden="true" className="h-px flex-1 bg-slate-200" />
      <span className="normal-case font-semibold">{rotulo}</span>
      <span aria-hidden="true" className="h-px flex-1 bg-slate-200" />
    </div>
  );
}
