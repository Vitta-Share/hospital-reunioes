"use client";

// PROTÓTIPO, descartável. Barra flutuante que troca a versão da tela pelo
// parâmetro `?variant=` da URL. Nunca aparece no build de produção.

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";

export type Versao = { chave: string; nome: string };

export function useVersao(versoes: Versao[]): string {
  const params = useSearchParams();
  const atual = params.get("variant") ?? versoes[0].chave;
  return versoes.some((v) => v.chave === atual) ? atual : versoes[0].chave;
}

export function PrototypeSwitcher({ versoes, rotulo }: { versoes: Versao[]; rotulo: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const atual = useVersao(versoes);
  const i = versoes.findIndex((v) => v.chave === atual);
  // A página anima com transform, que prende o `fixed` dentro dela: a barra vai
  // para o body por portal.
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);

  function ir(passo: number) {
    const proxima = versoes[(i + passo + versoes.length) % versoes.length];
    const novos = new URLSearchParams(params.toString());
    novos.set("variant", proxima.chave);
    router.replace(`${pathname}?${novos.toString()}`, { scroll: false });
  }

  useEffect(() => {
    function tecla(e: KeyboardEvent) {
      const alvo = e.target as HTMLElement | null;
      if (alvo && (alvo.closest("input, textarea, [contenteditable='true']") || alvo.isContentEditable)) return;
      if (e.key === "ArrowLeft") ir(-1);
      if (e.key === "ArrowRight") ir(1);
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  });

  // O build local também roda com NODE_ENV=production (Dockerfile), então quem
  // separa é o ambiente: em produção a barra some.
  if (process.env.NEXT_PUBLIC_ENVIRONMENT === "production" || !montado) return null;

  return createPortal(
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[300] flex items-center gap-2 rounded-full bg-slate-900 text-white shadow-2xl px-2 py-1.5 text-sm">
      <button onClick={() => ir(-1)} className="p-1.5 rounded-full hover:bg-white/10" aria-label="Versão anterior">
        <ChevronLeft className="w-4 h-4" />
      </button>
      <span className="px-2 whitespace-nowrap">
        <span className="text-white/50">Protótipo, {rotulo}:</span> {atual}. {versoes[i].nome}
      </span>
      <button onClick={() => ir(1)} className="p-1.5 rounded-full hover:bg-white/10" aria-label="Próxima versão">
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>,
    document.body,
  );
}
