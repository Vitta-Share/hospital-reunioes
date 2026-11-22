"use client";

import { ConcordanciaDoAgente } from "@/components/seguranca-do-paciente/ConcordanciaDoAgente";
import { CortesDeFrequencia } from "@/components/seguranca-do-paciente/CortesDeFrequencia";
import { QrDaNotificacao } from "@/components/seguranca-do-paciente/QrDaNotificacao";
import { TabelaDePrazos } from "@/components/seguranca-do-paciente/TabelaDePrazos";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";
import { useCurrentParticipante } from "@/hooks/useCurrentParticipante";

/** Configuração do módulo (ADR 0095, decisão 4): o QR e o endereço da notificação (issue #2046), os cortes de frequência da matriz de prioridade (issue #1992), a tabela de prazos (issue #1993) e, para quem confirma a triagem, a concordância do agente (issue #2001). */
export default function ConfiguracaoPage() {
  const { participante } = useCurrentParticipante();
  const veConcordancia = participante?.recursos_nsp?.includes("triagem") ?? false;
  return (
    <TelaDoNucleo
      titulo="Configuração"
      orientacao="O que o módulo usa para funcionar no hospital."
      recurso="configuracao"
    >
      <div className="space-y-4">
        <QrDaNotificacao />
        <CortesDeFrequencia />
        <TabelaDePrazos />
        {veConcordancia && <ConcordanciaDoAgente />}
      </div>
    </TelaDoNucleo>
  );
}
