/**
 * As opções de uma pergunta em cartão: a letra num círculo, o texto, o "Na
 * prática" quando houver e a recomendada em destaque. A mesma peça no
 * Planejamento da Demanda (issue #1592) e no cartão da Pergunta da Vitta
 * (issue #2119, ADR 0109, decisão 4).
 *
 * Sem `onEscolher`, as opções são só de leitura.
 */

export type OpcaoEmCartao = { letra: string; texto: string; naPratica?: string | null };

export function OpcoesEmCartao({
  opcoes,
  recomendada,
  desabilitado = false,
  onEscolher,
}: {
  opcoes: OpcaoEmCartao[];
  recomendada?: string | null;
  desabilitado?: boolean;
  onEscolher?: (letra: string) => void;
}) {
  return (
    <div role="group" aria-label="Opções" className="flex flex-col gap-2">
      {opcoes.map(({ letra, texto, naPratica }) => {
        const destaque = letra === recomendada;
        const conteudo = (
          <>
            <span
              className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold ${
                destaque ? "bg-primary text-white" : "bg-slate-100 text-slate-700"
              }`}
            >
              {letra}
            </span>
            <span className="flex-1 space-y-1">
              <span className="block normal-case text-[16px] font-semibold leading-snug text-slate-900">{texto}</span>
              {naPratica && (
                <span className="block normal-case text-sm leading-relaxed text-text-secondary">
                  {`Na prática: ${naPratica}`}
                </span>
              )}
            </span>
            {destaque && (
              <span className="flex-shrink-0 px-2 py-0.5 rounded-full bg-primary text-white text-xs font-semibold">
                Recomendada
              </span>
            )}
          </>
        );
        const classe = `flex items-start gap-3 w-full text-left px-4 py-3 rounded-xl border transition-colors ${
          destaque ? "border-primary bg-primary/5 ring-1 ring-primary" : "border-border"
        }`;
        if (!onEscolher) {
          return (
            <div key={letra} className={classe}>
              {conteudo}
            </div>
          );
        }
        return (
          <button
            key={letra}
            type="button"
            onClick={() => onEscolher(letra)}
            disabled={desabilitado}
            className={`${classe} disabled:opacity-60 ${destaque ? "" : "hover:border-primary"}`}
          >
            {conteudo}
          </button>
        );
      })}
    </div>
  );
}
