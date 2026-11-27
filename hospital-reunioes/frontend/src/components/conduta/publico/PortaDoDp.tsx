"use client";

/**
 * A porta do DP do Canal de Conduta (issue #1846, decisão 4 do diretor).
 *
 * Só mostra o contato do DP salvo nas Configurações. Não abre protocolo, não
 * envia e-mail e não guarda nada: quem procura o DP fala com ele diretamente.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { ENDERECO_DO_CANAL, ROTA_DOS_TEXTOS, lerDoCanal, type TextoVigente } from "@/lib/conduta/publico";

type Estado = { tipo: "carregando" } | { tipo: "fechado" } | { tipo: "falha" } | { tipo: "pronto"; contato: string | null };

export function PortaDoDp() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });

  useEffect(() => {
    let vivo = true;
    lerDoCanal<{ textos: Record<string, TextoVigente | null> }>(ROTA_DOS_TEXTOS)
      .then((corpo) => {
        if (!vivo) return;
        setEstado(corpo ? { tipo: "pronto", contato: corpo.textos.contato_dp?.texto ?? null } : { tipo: "fechado" });
      })
      .catch(() => {
        if (vivo) setEstado({ tipo: "falha" });
      });
    return () => {
      vivo = false;
    };
  }, []);

  if (estado.tipo === "carregando") {
    return (
      <div className="flex justify-center py-10" role="status" aria-label="Carregando">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" aria-hidden="true" />
      </div>
    );
  }
  if (estado.tipo === "fechado") return <p className="text-center text-slate-600 py-10">Página não encontrada.</p>;
  if (estado.tipo === "falha") {
    return <p className="text-center text-slate-600 py-10">Não foi possível abrir a página. Tente de novo.</p>;
  }

  return (
    <article className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900 text-center">Departamento Pessoal</h1>
      <p className="text-base text-slate-700">
        Salário, contracheque, escala, férias, benefícios e banco de horas são tratados pelo Departamento Pessoal. Fale
        direto com o DP:
      </p>
      <div className="bg-white rounded-2xl border border-border px-5 py-4">
        <p className="text-base text-slate-800 whitespace-pre-line">
          {estado.contato ?? "Procure o Departamento Pessoal do hospital."}
        </p>
      </div>
      <p className="text-base text-slate-700">
        Este canal não envia nada ao DP e não abre protocolo. Quem procura o DP fala com ele diretamente.
      </p>
      <p className="text-sm text-slate-500">
        Se houver assédio, ameaça ou retaliação envolvidos,{" "}
        <Link href={ENDERECO_DO_CANAL} className="font-semibold text-primary underline">
          faça um relato
        </Link>{" "}
        contando essa parte.
      </p>
    </article>
  );
}
