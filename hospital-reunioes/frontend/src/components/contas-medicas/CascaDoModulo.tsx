"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Dica } from "@/components/ui/Dica";
import { InterruptorDeLegendas, LegendasProvider } from "@/components/ui/Legenda";

interface Aba {
  rotulo: string;
  href: string;
  /** Qualquer uma destas libera a aba; vazia, a aba é de todos do módulo. */
  permissoes: string[];
  dica: string;
}

/**
 * As abas do módulo, na ordem da tela. Cada uma aparece pela mesma permissão
 * que liberava o botão dela ao lado do título da tela de contas.
 */
const ABAS: Aba[] = [
  {
    rotulo: "Contas",
    href: "/contas-medicas",
    permissoes: [],
    dica: "Onde se envia a conta e o prontuário do MV e se pega a próxima conta da fila.",
  },
  {
    rotulo: "Painel",
    href: "/contas-medicas/painel",
    permissoes: ["painel_completo", "enviar_corrigir_contas"],
    dica: "A nota da semana e onde a perda da conta nasce.",
  },
  {
    rotulo: "Validação",
    href: "/contas-medicas/validacao",
    permissoes: ["decidir_validacao"],
    dica: "As regras e os códigos que esperam a decisão da gestão.",
  },
  {
    rotulo: "Coordenação",
    href: "/contas-medicas/coordenacao",
    permissoes: ["conferencia_coordenacao"],
    dica: "A segunda checagem da conta, com os insumos que o prontuário mostra e a conta não cobra.",
  },
  {
    rotulo: "Contratos",
    href: "/contas-medicas/contratos",
    permissoes: ["contratos_avisos"],
    dica: "O contrato de cada operadora e a data do aviso de reajuste.",
  },
  {
    rotulo: "Operadoras",
    href: "/contas-medicas/operadoras",
    permissoes: ["regra_contratual_tabelas"],
    dica: "A memória de cada convênio, as tabelas de preço e os planos e setores do MV.",
  },
  {
    rotulo: "Habilitação",
    href: "/contas-medicas/habilitacao",
    permissoes: ["habilitar_pessoas"],
    dica: "Quem tem cada perfil no módulo e o que cada perfil pode fazer.",
  },
];

/** A aba da tela aberta: a de endereço mais longo que casa; o Guia cai em Contas. */
function abaAtual(caminho: string): string {
  const casam = ABAS.filter((aba) => caminho === aba.href || caminho.startsWith(`${aba.href}/`));
  casam.sort((a, b) => b.href.length - a.href.length);
  return casam[0]?.href ?? "/contas-medicas";
}

/**
 * A casca de Contas médicas (issue #1950): as abas fixas no topo, lidas uma
 * vez das permissões que o gate do layout já trouxe, e o interruptor
 * "Legendas", que vale para todas as telas do módulo. O layout lê no servidor
 * o cookie da escolha e passa o nome e o valor dele.
 */
export function CascaDoModulo({
  permissoes,
  chaveDasLegendas,
  legendasLigadas,
  children,
}: {
  permissoes: string[];
  chaveDasLegendas: string;
  legendasLigadas: boolean;
  children: ReactNode;
}) {
  const caminho = usePathname() ?? "/contas-medicas";
  const atual = abaAtual(caminho);
  const visiveis = ABAS.filter(
    (aba) => aba.permissoes.length === 0 || aba.permissoes.some((p) => permissoes.includes(p)),
  );

  return (
    <LegendasProvider chave={chaveDasLegendas} ligadasIniciais={legendasLigadas}>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-border">
        <nav aria-label="Telas de Contas médicas">
          <ul className="-mb-px flex flex-wrap gap-x-1">
            {visiveis.map((aba) => {
              const marcada = aba.href === atual;
              return (
                <li key={aba.href}>
                  <Dica texto={aba.dica}>
                    <Link
                      href={aba.href}
                      aria-current={marcada ? "page" : undefined}
                      className={`inline-block border-b-2 px-3 py-2 text-sm ${
                        marcada
                          ? "border-primary font-semibold text-primary"
                          : "border-transparent text-slate-500 hover:text-slate-700"
                      }`}
                    >
                      {aba.rotulo}
                    </Link>
                  </Dica>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="pb-2">
          <InterruptorDeLegendas />
        </div>
      </div>
      {children}
    </LegendasProvider>
  );
}
