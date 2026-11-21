"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";

import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";

interface CasoGrave {
  protocolo: string;
  setor: string | null;
  criado_em: string;
}

function quando(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const fuso = { timeZone: "America/Sao_Paulo" } as const;
  const data = d.toLocaleDateString("pt-BR", fuso);
  const hora = d.toLocaleTimeString("pt-BR", { ...fuso, hour: "2-digit", minute: "2-digit" });
  return `${data} às ${hora}`;
}

/**
 * O destaque de caso grave no início do módulo (issue #1989): as
 * notificações marcadas "grave ou houve morte" que esperam a triagem. O
 * servidor só manda os casos a quem abre os casos; sem nenhum, nada aparece.
 */
export function CasosGraves() {
  const [casos, setCasos] = useState<CasoGrave[]>([]);

  useEffect(() => {
    let vivo = true;
    chamarNsp<{ casos_graves?: CasoGrave[] }>("/api/nsp/inicio")
      .then((corpo) => vivo && setCasos(corpo.casos_graves ?? []))
      .catch(() => vivo && setCasos([]));
    return () => {
      vivo = false;
    };
  }, []);

  if (casos.length === 0) return null;

  return (
    <div role="alert" className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4">
      <div className="flex gap-3 items-start">
        <AlertTriangle className="w-5 h-5 shrink-0 text-rose-700" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-rose-900">Caso grave ou com morte: abra antes de qualquer outro</p>
          <ul className="mt-2 space-y-1.5">
            {casos.map((caso) => (
              <li key={caso.protocolo}>
                <Link
                  href="/seguranca-do-paciente/notificacoes"
                  className="text-sm text-rose-800 underline underline-offset-2 hover:text-rose-900"
                >
                  {`${caso.protocolo}, ${caso.setor ?? "setor não informado"}, recebido em ${quando(caso.criado_em)}`}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
