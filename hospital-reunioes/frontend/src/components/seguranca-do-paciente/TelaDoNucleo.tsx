"use client";

import type { ReactNode } from "react";
import { Inbox, Lock } from "lucide-react";

import { useCurrentParticipante } from "@/hooks/useCurrentParticipante";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";

interface Props {
  titulo: string;
  /** A linha no topo dizendo o que fazer ali (seção 17 da especificação). */
  orientacao: string;
  /** O recurso da permissão efetiva que abre a tela (ADR 0095). */
  recurso: string;
  /** O conteúdo da tela. Sem ele, o estado vazio. */
  children?: ReactNode;
}

/**
 * A moldura de toda tela de Segurança do Paciente (issue #1765): título,
 * linha de orientação e o conteúdo, ou o estado vazio enquanto a fatia da tela
 * não chega.
 *
 * Quem decide o acesso é o servidor: o layout já barrou quem não entra no
 * módulo, e cada rota da API barra o recurso dela. Aqui a tela só deixa de se
 * mostrar a quem não tem o recurso (o membro sem Termo, por exemplo, não abre
 * Membros), em vez de mostrar uma tela que a API vai recusar.
 */
export function TelaDoNucleo({ titulo, orientacao, recurso, children }: Props) {
  const { participante } = useCurrentParticipante();
  const liberada = participante?.recursos_nsp?.includes(recurso) ?? false;

  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto w-full">
      <h1 className="text-2xl font-bold text-slate-900">{titulo}</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-5">{orientacao}</p>

      {participante && !liberada ? (
        <div className={`${CARTAO} flex gap-3 items-start px-4 py-4`}>
          <Lock className="w-5 h-5 shrink-0 text-slate-400" aria-hidden />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900">Esta tela ainda não está liberada para você.</p>
            <p className="text-sm text-slate-600 mt-0.5">
              Quem está no Núcleo libera as telas ao assinar o Termo de Adesão.
            </p>
          </div>
        </div>
      ) : (
        (children ?? (
          <div className={`${CARTAO} flex flex-col items-center text-center gap-2 px-4 py-10`}>
            <Inbox className="w-8 h-8 text-slate-300" aria-hidden />
            <p className="text-sm font-semibold text-slate-900">Nada por aqui ainda.</p>
            <p className="text-sm text-slate-600">Esta tela chega nas próximas entregas do módulo.</p>
          </div>
        ))
      )}
    </div>
  );
}
