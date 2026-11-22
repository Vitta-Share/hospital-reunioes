"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";

import { chamarComite, type CasoAberto, type ContagemDaRotaEspecial } from "@/lib/conduta/comite";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";

/** "2026-11-21T13:00:00+00:00" vira "21/11/2026 às 10:00", no fuso do hospital. */
function dataEHora(iso: string): string {
  const momento = new Date(iso);
  const fuso = { timeZone: "America/Sao_Paulo" } as const;
  const dia = new Intl.DateTimeFormat("pt-BR", { ...fuso, dateStyle: "short" }).format(momento);
  const hora = new Intl.DateTimeFormat("pt-BR", { ...fuso, timeStyle: "short" }).format(momento);
  return `${dia} às ${hora}`;
}

/** "2026-11-20" vira "20/11/2026", sem passar por fuso. */
function dataDoDia(dia: string): string {
  const [ano, mes, d] = dia.slice(0, 10).split("-");
  return `${d}/${mes}/${ano}`;
}

function hojeEmSaoPaulo(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
}

interface Props {
  caso: Pick<CasoAberto, "aviso_de_rota_especial" | "pode_desviar" | "rota_especial">;
  ocupado: boolean;
  /** Manda a ação ao servidor; devolve se deu certo. */
  enviar: (caminho: string, body?: unknown) => Promise<boolean>;
}

/**
 * A Rota Especial na tela do caso (issue #1829; especificação, seção 10). Na
 * fila comum, o aviso do "Não sei" ou do agente, com o desvio. No caso da
 * Rota Especial, o registro selado, o prazo vencido sem parecer e a entrega
 * do parecer, que o grupo registra.
 */
export function RotaEspecial({ caso, ocupado, enviar }: Props) {
  const [destinatario, setDestinatario] = useState("");
  const [entregueEm, setEntregueEm] = useState("");
  const especial = caso.rota_especial ?? null;

  if (caso.aviso_de_rota_especial) {
    return (
      <section aria-label="Aviso de Rota Especial" className="rounded-2xl border-2 border-amber-400 bg-amber-50 px-4 py-4 space-y-3">
        <p className="flex gap-2 items-start text-sm font-semibold text-amber-900">
          <AlertTriangle className="w-5 h-5 shrink-0" aria-hidden />
          <span>{caso.aviso_de_rota_especial}</span>
        </p>
        <p className="text-sm text-amber-900">
          Confirmado o desvio, o caso sai da fila comum e só o Grupo Especial, sem nenhum diretor, passa a ver.
        </p>
        {caso.pode_desviar && (
          <button type="button" className={BOTAO} disabled={ocupado} onClick={() => void enviar("desvio-especial")}>
            CONFIRMAR DESVIO PARA A ROTA ESPECIAL
          </button>
        )}
      </section>
    );
  }
  if (!especial) return null;

  return (
    <section aria-label="Rota Especial" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 className="text-base font-semibold text-slate-900">Rota Especial</h2>
      {especial.nao_respondido_no_prazo && (
        <p role="status" className="text-sm font-semibold text-red-700">
          Caso não respondido no prazo
        </p>
      )}
      {especial.selo && (
        <div className="space-y-1">
          <p className="text-sm text-slate-800">{`Relato selado em ${dataEHora(especial.selo.selado_em)}`}</p>
          <p className="text-xs text-slate-500 break-all">{`Código de integridade: ${especial.selo.codigo}`}</p>
          {!especial.selo.confere && (
            <p role="alert" className="text-sm font-semibold text-red-700">
              O relato não confere com o código do selo.
            </p>
          )}
        </div>
      )}
      {especial.entrega ? (
        <p className="text-sm text-slate-800">
          {`Parecer entregue a ${especial.entrega.destinatario} em ${dataDoDia(especial.entrega.entregue_em)}.`}
        </p>
      ) : especial.pode_registrar_entrega ? (
        <form
          aria-label="Registrar a entrega do parecer"
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            void enviar("entrega-do-parecer", { destinatario: destinatario.trim(), entregue_em: entregueEm });
          }}
        >
          <p className="text-sm text-slate-700">
            O parecer é entregue fora do aplicativo, à autoridade não envolvida que o grupo escolheu. Registre aqui a
            quem e quando.
          </p>
          <label className="text-sm font-semibold text-slate-700 space-y-1 block">
            <span>Entregue a</span>
            <input
              className={CAMPO}
              value={destinatario}
              maxLength={300}
              onChange={(e) => setDestinatario(e.target.value)}
            />
          </label>
          <label className="text-sm font-semibold text-slate-700 space-y-1 block">
            <span>Data da entrega</span>
            <input
              type="date"
              className={CAMPO}
              value={entregueEm}
              max={hojeEmSaoPaulo()}
              onChange={(e) => setEntregueEm(e.target.value)}
            />
          </label>
          <button type="submit" className={BOTAO} disabled={!destinatario.trim() || !entregueEm || ocupado}>
            REGISTRAR ENTREGA DO PARECER
          </button>
        </form>
      ) : null}
    </section>
  );
}

/**
 * O que se vê da Rota Especial de fora do grupo: só a contagem de casos
 * recebidos, concluídos e em aberto (issue #1829).
 */
export function ContagemDaRotaEspecialNaLista() {
  const [contagem, setContagem] = useState<ContagemDaRotaEspecial | null>(null);

  useEffect(() => {
    let vivo = true;
    chamarComite<ContagemDaRotaEspecial>("/rota-especial/contagem")
      .then((corpo) => vivo && setContagem(corpo))
      .catch(() => vivo && setContagem(null));
    return () => {
      vivo = false;
    };
  }, []);

  if (contagem === null || contagem.recebidos === 0) return null;
  return (
    <p aria-label="Rota Especial" className="text-sm text-slate-600">
      {`Rota Especial: ${contagem.recebidos} recebidos, ${contagem.concluidos} concluídos, ${contagem.em_aberto} em aberto.`}
    </p>
  );
}
