"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";

import { useCurrentParticipante } from "@/hooks/useCurrentParticipante";
import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";

interface Item {
  rotulo: string;
  link: string;
  urgente: boolean;
}

interface Grupo {
  chave: string;
  titulo: string;
  link: string;
  total: number | null;
  itens: Item[];
  ilegivel: boolean;
}

/**
 * A faixa "o que exige ação hoje" no início do módulo (issue #2000): casos A e
 * B abertos, triagens pendentes por idade, prazos legais a vencer e Termos
 * pendentes, cada grupo com a contagem e o link para a tela onde se resolve.
 * O prazo que vence em menos de 24 horas vem em destaque. Só quem abre os
 * casos a vê; o servidor recusa os outros, e a tela nem pergunta.
 */
export function AcaoDeHoje() {
  const { participante } = useCurrentParticipante();
  const abreOsCasos = participante?.recursos_nsp?.includes("casos") ?? false;
  const [grupos, setGrupos] = useState<Grupo[]>([]);

  useEffect(() => {
    if (!abreOsCasos) return;
    let vivo = true;
    chamarNsp<{ grupos?: Grupo[] }>("/api/nsp/acao-de-hoje")
      .then((corpo) => vivo && setGrupos(corpo.grupos ?? []))
      .catch(() => vivo && setGrupos([]));
    return () => {
      vivo = false;
    };
  }, [abreOsCasos]);

  if (!abreOsCasos || grupos.length === 0) return null;

  return (
    <section aria-label="O que exige ação hoje" className="mb-6">
      <h2 className="text-base font-semibold text-slate-900 mb-3">O que exige ação hoje</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {grupos.map((grupo) => (
          <div
            key={grupo.chave}
            role="group"
            aria-label={grupo.titulo}
            className="bg-white rounded-2xl border border-border shadow-premium px-4 py-3 min-w-0"
          >
            <Link
              href={grupo.link}
              className="flex items-baseline justify-between gap-3 text-sm font-semibold text-slate-900 hover:underline"
            >
              <span className="min-w-0">{grupo.titulo}</span>
              <span className="text-lg font-bold text-[#282760]">{grupo.ilegivel ? "?" : (grupo.total ?? 0)}</span>
            </Link>
            {grupo.ilegivel ? (
              <p className="mt-1.5 text-sm text-slate-600">Não deu para ler agora. Recarregue a página.</p>
            ) : grupo.itens.length === 0 ? (
              <p className="mt-1.5 text-sm text-slate-500">Nada pendente.</p>
            ) : (
              <ul className="mt-2 space-y-1.5">
                {grupo.itens.map((item) => (
                  <li key={`${item.link}-${item.rotulo}`}>
                    <Link
                      href={item.link}
                      className={
                        item.urgente
                          ? "flex gap-1.5 items-start text-sm font-semibold text-rose-800 underline underline-offset-2 hover:text-rose-900"
                          : "text-sm text-slate-700 underline underline-offset-2 hover:text-slate-900"
                      }
                    >
                      {item.urgente && <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-label="Urgente" />}
                      <span className="min-w-0">{item.rotulo}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
