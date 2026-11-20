"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AdminModal } from "@/components/admin/AdminModal";
import type { AtaDoDashboard } from "@/lib/reunioes/atasDoDashboard";

const STATUS_ATA_LABEL: Record<string, string> = {
  PROCESSANDO: "Processando IA",
  AGUARDANDO_VALIDACAO: "Aguard. Validação",
  AGUARDANDO_ASSINATURA: "Aguard. Assinatura",
};

const DIA = 24 * 60 * 60 * 1000;

function haQuanto(updatedAt?: string | null): string | null {
  if (!updatedAt) return null;
  const dias = Math.floor((Date.now() - new Date(updatedAt).getTime()) / DIA);
  if (dias <= 0) return "hoje";
  return dias === 1 ? "há 1 dia" : `há ${dias} dias`;
}

function formatarData(data: string): string {
  const [ano, mes, dia] = data.split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : data;
}

interface Signatario {
  nome: string;
  email: string;
  status: string;
}

/**
 * Quem falta assinar e o Cobrar (issue #1868, decisão 36 do diretor no PRD
 * #1757): o Cobrar manda de novo o pedido de assinatura da ClickSign só para
 * quem ainda não assinou.
 *
 * A consulta à ClickSign sai só quando a pessoa pede, uma ata por vez: o
 * Super admin pode cobrar todas as atas do hospital, e consultar cada linha
 * ao abrir a lista mandaria N pedidos de uma vez ao backend (revisão do PR
 * #2048).
 */
function CobrarAssinatura({ idReuniao, token }: { idReuniao: string; token: string }) {
  const [pedido, setPedido] = useState(false);
  const [faltam, setFaltam] = useState<string[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  useEffect(() => {
    if (!pedido) return;
    let vivo = true;
    fetch(`/api/reunioes/${idReuniao}/signatarios/status`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((corpo: { signatarios?: Signatario[] }) => {
        if (!vivo) return;
        const pendentes = (corpo.signatarios ?? [])
          .filter((s) => s.status !== "signed")
          .map((s) => s.nome || s.email);
        setFaltam(pendentes);
      })
      .catch(() => vivo && setErro("Não deu para ver quem falta assinar agora."));
    return () => {
      vivo = false;
    };
  }, [pedido, idReuniao, token]);

  async function cobrar() {
    setEnviando(true);
    setResultado(null);
    try {
      const res = await fetch(`/api/reunioes/${idReuniao}/signatarios/cobrar`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const corpo = await res.json().catch(() => ({}));
      if (!res.ok) {
        setResultado(corpo?.detail || "Não deu para cobrar agora. Tente de novo.");
        return;
      }
      const cobrados: string[] = corpo.cobrados ?? [];
      const falharam: string[] = corpo.falharam ?? [];
      const partes = [];
      if (cobrados.length > 0) partes.push(`Pedido reenviado para ${cobrados.join(", ")}.`);
      if (falharam.length > 0) partes.push(`Não foi para ${falharam.join(", ")}.`);
      setResultado(partes.join(" ") || "Todo mundo já assinou.");
    } finally {
      setEnviando(false);
    }
  }

  if (!pedido) {
    return (
      <button
        type="button"
        onClick={() => setPedido(true)}
        className="mt-1 text-xs font-semibold text-primary hover:underline"
      >
        Ver quem falta assinar
      </button>
    );
  }
  if (erro) return <p className="text-xs text-text-secondary mt-1">{erro}</p>;
  if (faltam === null) return <p className="text-xs text-text-secondary mt-1">Vendo quem falta assinar...</p>;
  if (faltam.length === 0) return <p className="text-xs text-text-secondary mt-1">Todo mundo já assinou.</p>;

  return (
    <div className="mt-1 flex flex-wrap items-center gap-2">
      <span className="text-xs text-text-secondary">Falta assinar: {faltam.join(", ")}</span>
      <button
        type="button"
        onClick={cobrar}
        disabled={enviando}
        className="text-xs font-semibold px-2 py-0.5 rounded-full border border-primary text-primary hover:bg-primary/5 disabled:opacity-50"
      >
        {enviando ? "Cobrando..." : "Cobrar"}
      </button>
      {resultado && (
        <span role="status" className="text-xs text-text-secondary">
          {resultado}
        </span>
      )}
    </div>
  );
}

export interface ListaAtasModalProps {
  titulo: string;
  atas: AtaDoDashboard[];
  /** Com o token, a ata que a pessoa pode cobrar mostra quem falta e o Cobrar. */
  token?: string | null;
  onClose: () => void;
}

export default function ListaAtasModal({ titulo, atas, token, onClose }: ListaAtasModalProps) {
  return (
    <AdminModal open onClose={onClose} title={titulo} size="lg" scrollable>
      {atas.length === 0 ? (
        <p className="text-sm text-text-secondary">Nenhuma ata nesta situação.</p>
      ) : (
        <ul className="divide-y divide-border">
          {atas.map((ata) => {
            const tempo = haQuanto(ata.updated_at);
            return (
              <li key={ata.id_reuniao} className="py-1">
                <Link
                  href={`/reunioes/${ata.id_reuniao}`}
                  className="flex items-start justify-between gap-4 py-2 px-2 -mx-2 rounded-lg hover:bg-slate-50 transition-colors"
                >
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-text truncate">
                      {ata.tipo || "Reunião"}
                    </div>
                    {ata.objetivo && (
                      <div className="text-xs text-text-secondary truncate">{ata.objetivo}</div>
                    )}
                    <div className="text-xs text-text-secondary/70 mt-0.5">
                      {formatarData(ata.data)}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                      {STATUS_ATA_LABEL[ata.status_ata] ?? ata.status_ata}
                    </span>
                    {tempo && <span className="text-xs text-text-secondary">{tempo}</span>}
                  </div>
                </Link>
                {token && ata.pode_cobrar && <CobrarAssinatura idReuniao={ata.id_reuniao} token={token} />}
              </li>
            );
          })}
        </ul>
      )}
    </AdminModal>
  );
}
