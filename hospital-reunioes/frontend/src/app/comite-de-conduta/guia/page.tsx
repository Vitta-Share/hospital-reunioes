import { ANTES_DO_RITO, RITOS_DO_GUIA } from "@/lib/conduta/guia";

/**
 * O Guia do rito do Comitê de Conduta (issue #1842, seção 5.4): os quatro
 * ritos e o que cada pessoa faz em cada um. Abre de qualquer tela do Comitê,
 * e o membro sem o Termo assinado também entra (o portão fica no layout).
 */
export default function GuiaDoRitoPage() {
  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto w-full min-w-0">
      <h1 className="text-2xl font-bold text-slate-900">Guia do rito</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-5">{ANTES_DO_RITO}</p>

      <div className="space-y-3">
        {RITOS_DO_GUIA.map((rito) => (
          <article key={rito.nome} className="bg-white rounded-2xl border border-border shadow-premium px-4 py-3 min-w-0">
            <h2 className="text-base font-semibold text-slate-900 normal-case tracking-normal">{rito.nome}</h2>
            <p className="text-sm text-slate-600 mt-1">
              <span className="font-semibold text-slate-700">Quando: </span>
              {rito.quando}
            </p>
            <p className="text-sm text-slate-600 mt-0.5">
              <span className="font-semibold text-slate-700">Prazo: </span>
              {rito.prazo}
            </p>
            <ul className="list-disc pl-5 mt-2 space-y-1 text-sm text-slate-700">
              {rito.quemFaz.map((linha) => (
                <li key={linha}>{linha}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}
