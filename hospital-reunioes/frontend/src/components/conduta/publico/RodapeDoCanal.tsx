import Link from "next/link";

import {
  ENDERECO_DA_OUVIDORIA,
  ENDERECO_DA_PROTECAO,
  ENDERECO_DO_CODIGO,
  ENDERECO_DO_DP,
} from "@/lib/conduta/publico";

const PORTA =
  "flex flex-col gap-0.5 rounded-xl border border-border bg-white px-4 py-3 text-left min-h-[44px] hover:border-primary/40";

/**
 * O rodapé de toda tela pública do Canal de Conduta (issue #1846): as portas
 * "Não é aqui" e os links da página de proteção e do Código de Conduta.
 */
export function RodapeDoCanal() {
  return (
    <footer className="max-w-lg mx-auto px-4 pb-10 space-y-5">
      <section className="space-y-2" aria-labelledby="nao-e-aqui">
        <h2 id="nao-e-aqui" className="text-sm font-semibold text-slate-600">
          Não é aqui
        </h2>
        <Link href={ENDERECO_DO_DP} className={PORTA}>
          <span className="text-sm font-semibold text-slate-800">Salário, contracheque, escala, férias, benefícios</span>
          <span className="text-sm text-slate-500">Ver o contato do Departamento Pessoal</span>
        </Link>
        <a href={ENDERECO_DA_OUVIDORIA} className={PORTA}>
          <span className="text-sm font-semibold text-slate-800">Sou paciente ou acompanhante</span>
          <span className="text-sm text-slate-500">Ir para a Ouvidoria</span>
        </a>
      </section>
      <nav className="flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm" aria-label="Sobre o canal">
        <Link href={ENDERECO_DA_PROTECAO} className="font-semibold text-primary underline">
          Como este canal protege você
        </Link>
        <a href={ENDERECO_DO_CODIGO} className="font-semibold text-primary underline" target="_blank" rel="noopener">
          Código de Conduta
        </a>
      </nav>
    </footer>
  );
}
