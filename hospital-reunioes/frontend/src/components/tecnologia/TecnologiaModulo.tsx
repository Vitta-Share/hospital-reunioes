"use client";

/**
 * O módulo da aba Tecnologia (issue #636, PRD #634, ADR 0050).
 *
 * Desde a issue #2279 (ADR 0113, decisões 6 e 7) a aba só informa: duas abas,
 * o Quadro, com a Etapa de cada Demanda, e as Entregas, o retrato do que foi
 * entregue (issue #1556, ADR 0084, decisão 8). Saíram o chat do Assistente, o
 * "Novo pedido" e a lista Esperando você: o pedido nasce no GitHub. O gate de
 * verdade é o `require_super_admin` do backend; a sidebar apenas esconde o item.
 *
 * Na tela larga, a partir de 1280px, o Quadro mostra as Demandas em colunas
 * pela Etapa (issue #1642, ADR 0090, decisão 1); no celular, a lista. O "Ver
 * todos nas Entregas", no pé da coluna Entregue, troca para a aba Entregas
 * (issue #1644). `demandaInicial` é o `?demanda=` do endereço, que um aviso
 * antigo do sino ou do e-mail ainda traz: o Quadro abre com o pedido.
 */

import { useState } from "react";
import { Cpu } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";

import { ConversasDaTecnologia } from "./ConversasDaTecnologia";
import { EntregasDaTecnologia } from "./EntregasDaTecnologia";

type Aba = "quadro" | "entregas";

export const ABAS: { id: Aba; rotulo: string }[] = [
  { id: "quadro", rotulo: "Quadro" },
  { id: "entregas", rotulo: "Entregas" },
];

export function TecnologiaModulo({ demandaInicial = null }: { demandaInicial?: string | null }) {
  const { token } = useAuth();
  const [aba, setAba] = useState<Aba>("quadro");
  /** As Entregas só pedem ao servidor quando abertas pela primeira vez. */
  const [entregasAbertas, setEntregasAbertas] = useState(false);

  function escolher(id: Aba) {
    setAba(id);
    if (id === "entregas") setEntregasAbertas(true);
  }

  return (
    <div className="animate-fade-in-up space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-primary/10 text-primary">
          <Cpu className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-text">Tecnologia</h1>
          <p className="text-sm text-text-secondary">
            Acompanhe a fase de cada pedido e o que a Vitta já entregou.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-border" role="tablist" aria-label="Tecnologia">
        {ABAS.map((a) => (
          <button
            key={a.id}
            type="button"
            role="tab"
            aria-selected={aba === a.id}
            onClick={() => escolher(a.id)}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              aba === a.id ? "border-primary text-primary" : "border-transparent text-text-secondary hover:text-text"
            }`}
          >
            {a.rotulo}
          </button>
        ))}
      </div>

      {/* O Quadro fica montado atrás da aba: trocar de aba não perde os filtros. */}
      <div role="tabpanel" aria-label="Quadro" hidden={aba !== "quadro"}>
        <ConversasDaTecnologia
          token={token}
          demandaInicial={demandaInicial}
          onVerEntregas={() => escolher("entregas")}
        />
      </div>
      {entregasAbertas && (
        <div role="tabpanel" aria-label="Entregas" hidden={aba !== "entregas"}>
          <EntregasDaTecnologia token={token} />
        </div>
      )}
    </div>
  );
}
