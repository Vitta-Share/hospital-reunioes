"use client";

/**
 * O botão Encaminhar da tela de triagem (issue #1995, ADR 0095 decisão 11).
 *
 * Um ou mais destinos e o motivo em uma frase; o protocolo não muda. Marcando
 * o Núcleo, o caso continua na triagem. Fora de escopo vai sozinho e leva a
 * orientação que quem notificou vê no acompanhamento. Ao Canal de Conduta nada
 * é enviado: a tela mostra a orientação que o servidor devolve, sem link.
 */
import { useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";
import { DESTINOS_DO_ENCAMINHAMENTO } from "@/lib/seguranca-do-paciente/triagem";
import { ESTADOS } from "./NotificacoesDoNucleo";

const CAMPO =
  "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30";
const FORA_DE_ESCOPO = "fora_de_escopo";
const ESTADOS_DA_FILA = ["recebida", "em_triagem"];

interface Resultado {
  estado: string;
  orientacao_do_canal_de_conduta?: string;
}

export function EncaminharDoCaso({ id, aoEncaminhar }: { id: string; aoEncaminhar: (estado: string) => void }) {
  const [destinos, setDestinos] = useState<string[]>([]);
  const [motivo, setMotivo] = useState("");
  const [orientacao, setOrientacao] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);

  const foraDeEscopo = destinos.includes(FORA_DE_ESCOPO);
  const liberado =
    destinos.length > 0 && motivo.trim() !== "" && (!foraDeEscopo || orientacao.trim() !== "") && !enviando;

  function alternar(destino: string) {
    if (destino === FORA_DE_ESCOPO) {
      setDestinos(foraDeEscopo ? [] : [FORA_DE_ESCOPO]);
      return;
    }
    setDestinos((atual) => (atual.includes(destino) ? atual.filter((d) => d !== destino) : [...atual, destino]));
  }

  async function registrar() {
    setEnviando(true);
    setErro(null);
    try {
      const ordenados = DESTINOS_DO_ENCAMINHAMENTO.map((d) => d.valor).filter((d) => destinos.includes(d));
      const corpo = await chamarNsp<Resultado>(`/api/nsp/triagem/${encodeURIComponent(id)}/encaminhamento`, {
        method: "POST",
        body: { destinos: ordenados, motivo: motivo.trim(), orientacao: foraDeEscopo ? orientacao.trim() : null },
      });
      setResultado(corpo);
      aoEncaminhar(corpo.estado);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  if (resultado) {
    const naFila = ESTADOS_DA_FILA.includes(resultado.estado);
    return (
      <div role="status" className="space-y-2">
        <p className="flex gap-2 items-start text-sm font-semibold text-slate-900">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-600" aria-hidden />
          {naFila
            ? "Encaminhamento registrado. O caso continua na triagem do Núcleo."
            : `Encaminhamento registrado. O caso está em ${ESTADOS[resultado.estado] ?? resultado.estado}.`}
        </p>
        {resultado.orientacao_do_canal_de_conduta && (
          <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {resultado.orientacao_do_canal_de_conduta}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <fieldset className="space-y-1">
        <legend className="text-xs text-slate-500">Destinos</legend>
        {DESTINOS_DO_ENCAMINHAMENTO.map(({ valor, rotulo, explicacao }) => (
          <label key={valor} className="flex min-h-[44px] items-start gap-2 text-sm text-slate-800">
            <input
              type="checkbox"
              aria-label={rotulo}
              checked={destinos.includes(valor)}
              disabled={foraDeEscopo && valor !== FORA_DE_ESCOPO}
              onChange={() => alternar(valor)}
              className="mt-0.5 h-4 w-4 accent-primary"
            />
            <span>
              <span className="font-semibold">{rotulo}</span>
              <span className="block text-xs text-slate-500">{explicacao}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <div className="space-y-1">
        <label htmlFor="motivo-do-encaminhamento" className="text-xs text-slate-500">
          Motivo, em uma frase
        </label>
        <input
          id="motivo-do-encaminhamento"
          type="text"
          maxLength={300}
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          className={CAMPO}
        />
      </div>
      {foraDeEscopo && (
        <div className="space-y-1">
          <label htmlFor="orientacao-ao-notificante" className="text-xs text-slate-500">
            Orientação para quem notificou
          </label>
          <input
            id="orientacao-ao-notificante"
            type="text"
            maxLength={300}
            value={orientacao}
            onChange={(e) => setOrientacao(e.target.value)}
            className={CAMPO}
          />
          <p className="text-xs text-slate-500">Quem notificou vê esta frase na página de acompanhamento.</p>
        </div>
      )}
      {erro && (
        <p role="alert" className="text-sm text-red-700">
          {erro}
        </p>
      )}
      <button
        type="button"
        onClick={registrar}
        disabled={!liberado}
        className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-50"
      >
        {enviando && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
        Registrar o encaminhamento
      </button>
    </div>
  );
}
