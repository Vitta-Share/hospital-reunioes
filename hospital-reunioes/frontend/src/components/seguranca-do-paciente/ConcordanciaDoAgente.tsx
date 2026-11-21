"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Loader2 } from "lucide-react";

import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";
import { ROTULO_DO_DANO, type Concordancia } from "@/lib/seguranca-do-paciente/recalibracao";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";

/**
 * A concordância entre a sugestão do agente e a decisão da Presidência, por
 * eixo, na Configuração (issue #2001), com as versões do prompt e da base em
 * uso. Os casos em que a Presidência subiu o grau de dano sugerido ficam à
 * parte: é o erro que mais importa.
 */
export function ConcordanciaDoAgente() {
  const [medida, setMedida] = useState<Concordancia | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    chamarNsp<Concordancia>("/api/nsp/configuracao/concordancia")
      .then((corpo) => vivo && setMedida(corpo))
      .catch((e: Error) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, []);

  if (medida === null) {
    return erro ? (
      <div role="alert" className={`${CARTAO} flex gap-2 items-start px-4 py-4`}>
        <AlertCircle className="w-5 h-5 shrink-0 text-red-500" aria-hidden />
        <p className="text-sm text-red-700">{erro}</p>
      </div>
    ) : (
      <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />
    );
  }

  return (
    <section aria-labelledby="concordancia-titulo" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 id="concordancia-titulo" className="text-base font-semibold text-slate-900">
        Concordância do agente
      </h2>
      <p className="text-sm text-slate-600">
        Prompt na versão {medida.versoes.prompt} e base de conhecimento na versão {medida.versoes.base}. A conta
        compara a sugestão do agente com a decisão da Presidência, em {medida.casos}{" "}
        {medida.casos === 1 ? "caso" : "casos"}, e deixa de fora o caso classificado sem sugestão.
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs font-semibold text-slate-600">
            <th className="py-1">Eixo</th>
            <th className="py-1">Sem ajuste</th>
          </tr>
        </thead>
        <tbody>
          {medida.eixos.map((e) => (
            <tr key={e.eixo} className="border-t border-border">
              <td className="py-1.5 text-slate-900">{e.rotulo}</td>
              <td className="py-1.5 tabular-nums text-slate-700">
                {e.percentual === null ? "Sem casos ainda" : `${e.percentual}% (${e.acatadas} de ${e.total})`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-slate-900">Grau de dano subido pela Presidência</h3>
        {medida.erros_para_baixo.length === 0 ? (
          <p className="text-sm text-slate-600">Nenhum caso até agora.</p>
        ) : (
          <ul className="space-y-1">
            {medida.erros_para_baixo.map((e) => (
              <li key={e.notificacao_id} className={`text-sm ${e.grave_ou_obito ? "text-red-700" : "text-slate-700"}`}>
                {e.protocolo}: sugerido {ROTULO_DO_DANO[e.sugerido] ?? e.sugerido}, decidido{" "}
                {ROTULO_DO_DANO[e.decidido] ?? e.decidido}
              </li>
            ))}
          </ul>
        )}
      </div>
      <Link
        href="/seguranca-do-paciente/recalibracao"
        className="inline-flex text-sm font-semibold text-primary hover:underline"
      >
        Abrir a recalibração do agente
      </Link>
    </section>
  );
}
