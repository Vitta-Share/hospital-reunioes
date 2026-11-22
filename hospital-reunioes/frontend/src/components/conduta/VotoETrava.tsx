"use client";

import { useState } from "react";

import { chamarComite } from "@/lib/conduta/comite";
import {
  COM_MEDIDA,
  MEDIDAS,
  RESULTADOS,
  abrirCiencia,
  anexarCiencia,
  rotuloDaMedida,
  rotuloDoResultado,
  type ItemDaTrava,
  type Resultado,
  type Trava,
  type Votacao,
  type VotoRegistrado,
} from "@/lib/conduta/voto";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 disabled:text-slate-600 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

function textoDoVoto(voto: VotoRegistrado): string {
  const medida = rotuloDaMedida(voto);
  return medida ? `${rotuloDoResultado(voto.resultado)}, ${medida}` : rotuloDoResultado(voto.resultado);
}

/** O formulário do voto: resultado, medida da Matriz e a justificativa do próprio membro. */
function FormularioDoVoto({ ocupado, agir }: { ocupado: boolean; agir: (caminho: string, body?: unknown) => Promise<boolean> }) {
  const [resultado, setResultado] = useState<Resultado | "">("");
  const [medida, setMedida] = useState("");
  const [dias, setDias] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const comMedida = resultado !== "" && COM_MEDIDA.includes(resultado);
  const pronto =
    resultado !== "" && justificativa.trim() !== "" && (!comMedida || (medida !== "" && (medida !== "suspensao" || dias !== "")));

  return (
    <form
      aria-label="Seu voto"
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        void agir("voto", {
          resultado,
          medida: comMedida ? medida : null,
          dias_de_suspensao: comMedida && medida === "suspensao" ? Number(dias) : null,
          justificativa,
        });
      }}
    >
      <fieldset className="space-y-1">
        <legend className="text-sm font-semibold text-slate-700">Resultado</legend>
        <div className="flex flex-col gap-2">
          {RESULTADOS.map((r) => (
            <label key={r.valor} className="flex items-center gap-2 text-sm text-slate-800">
              <input type="radio" name="resultado" value={r.valor} checked={resultado === r.valor} onChange={() => setResultado(r.valor)} />
              {r.rotulo}
            </label>
          ))}
        </div>
      </fieldset>
      {comMedida && (
        <label className="text-sm font-semibold text-slate-700 space-y-1 block">
          <span>Medida da Matriz</span>
          <select className={CAMPO} value={medida} aria-label="Medida da Matriz" onChange={(e) => setMedida(e.target.value)}>
            <option value="">Escolha</option>
            {MEDIDAS.map((m) => (
              <option key={m.valor} value={m.valor}>
                {m.rotulo}
              </option>
            ))}
          </select>
        </label>
      )}
      {comMedida && medida === "suspensao" && (
        <label className="text-sm font-semibold text-slate-700 space-y-1 block">
          <span>Dias de suspensão</span>
          <input
            className={CAMPO}
            type="number"
            min={1}
            max={30}
            value={dias}
            aria-label="Dias de suspensão"
            onChange={(e) => setDias(e.target.value)}
          />
        </label>
      )}
      <label className="text-sm font-semibold text-slate-700 space-y-1 block">
        <span>Justificativa, em até três linhas</span>
        <textarea
          className={CAMPO}
          rows={3}
          maxLength={600}
          value={justificativa}
          aria-label="Justificativa, em até três linhas"
          onChange={(e) => setJustificativa(e.target.value)}
        />
      </label>
      <button type="submit" className={BOTAO} disabled={!pronto || ocupado}>
        VOTAR
      </button>
    </form>
  );
}

function ItemDaLista({ item, ocupado, agir }: { item: ItemDaTrava; ocupado: boolean; agir: (caminho: string, body?: unknown) => Promise<boolean> }) {
  return (
    <li aria-label={item.rotulo} className="space-y-1 border-t border-border pt-3 first:border-t-0 first:pt-0">
      <p className="text-sm font-semibold text-slate-900">
        {item.confirmado ? "Confirmado: " : "Em aberto: "}
        {item.rotulo}
      </p>
      {item.preenchimento && (
        <p className="text-sm text-slate-700 break-words">
          <span className="font-semibold">{item.preenchimento.atendido ? "O agente aponta: " : "O agente não achou: "}</span>
          {item.preenchimento.texto}
        </p>
      )}
      {item.confirmacoes.length > 0 && (
        <p className="text-xs text-slate-500">{`Confirmado por ${item.confirmacoes.join(" e ")}`}</p>
      )}
      {item.confirmacoes_precisas > 1 && !item.confirmado && (
        <p className="text-xs text-slate-500">{`Precisa de ${item.confirmacoes_precisas} membros.`}</p>
      )}
      {item.bloqueio && <p className="text-xs text-slate-600">{item.bloqueio}</p>}
      {item.pode_confirmar && (
        <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void agir("trava/confirmacao", { item: item.item })}>
          CONFIRMAR
        </button>
      )}
    </li>
  );
}

/**
 * A etapa Voto do caso (issue #1833; especificação, 6.6 e 6.7): o voto de
 * cada membro, oculto até os três votarem, o resultado da maioria, a trava de
 * robustez e a conclusão da votação. O servidor diz o que a pessoa pode fazer.
 */
export function VotoETrava({
  casoId,
  votacao,
  trava,
  aoMudar,
}: {
  casoId: string;
  votacao: Votacao | null;
  trava: Trava | null;
  aoMudar: () => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  if (!votacao || !trava) return null;

  const agir = async (caminho: string, body?: unknown): Promise<boolean> => {
    setOcupado(true);
    setAviso(null);
    try {
      await chamarComite(`/casos/${casoId}/${caminho}`, { method: "POST", body: body ?? {} });
      aoMudar();
      return true;
    } catch (e) {
      setAviso((e as Error).message);
      return false;
    } finally {
      setOcupado(false);
    }
  };

  const enviarCiencia = async (arquivo: File | undefined) => {
    if (!arquivo) return;
    setOcupado(true);
    setAviso(null);
    try {
      await anexarCiencia(casoId, arquivo);
      aoMudar();
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  const verCiencia = async () => {
    try {
      window.open(await abrirCiencia(casoId), "_blank", "noopener");
    } catch (e) {
      setAviso((e as Error).message);
    }
  };

  const concluida = votacao.concluida !== null;

  return (
    <>
      <section aria-label="Voto" className={`${CARTAO} px-4 py-4 space-y-3`}>
        <h2 className="text-base font-semibold text-slate-900">Voto</h2>
        {votacao.reuniao_curta_convocada && (
          <p role="status" className="text-sm text-amber-800">
            {`Não houve maioria. A reunião curta foi convocada: depois dela, os três votam de novo (rodada ${votacao.rodada}).`}
          </p>
        )}
        {concluida ? (
          <p className="text-sm font-semibold text-slate-900">{`Votação concluída: ${rotuloDoResultado(votacao.concluida)}`}</p>
        ) : (
          <p className="text-sm text-slate-700">
            {`${votacao.votaram} de ${votacao.votantes} já votaram. Os votos ficam ocultos até os três votarem.`}
          </p>
        )}
        {votacao.meu_voto && (
          <div className="space-y-1">
            <p className="text-sm text-slate-800">{`Seu voto: ${textoDoVoto(votacao.meu_voto)}`}</p>
            <p className="text-sm text-slate-700 whitespace-pre-line break-words">{votacao.meu_voto.justificativa}</p>
          </div>
        )}
        {votacao.pode_votar && <FormularioDoVoto ocupado={ocupado} agir={agir} />}
        {votacao.rodadas.map((rodada) => (
          <div key={rodada.rodada} className="space-y-2 border-t border-border pt-3">
            <h3 className="text-sm font-semibold text-slate-900">{`Rodada ${rodada.rodada}`}</h3>
            <ul className="space-y-2">
              {rodada.votos.map((voto) => (
                <li key={voto.membro} className="text-sm text-slate-800">
                  <p className="font-semibold">{`${voto.membro}: ${textoDoVoto(voto)}`}</p>
                  <p className="text-slate-700 whitespace-pre-line break-words">{voto.justificativa}</p>
                </li>
              ))}
            </ul>
            {rodada.reuniao_curta && <p className="text-xs text-slate-500">Sem maioria nesta rodada.</p>}
          </div>
        ))}
        {votacao.resultado && (
          <p className="text-sm font-semibold text-slate-900">
            {`Resultado da maioria: ${rotuloDoResultado(votacao.resultado.resultado)}${votacao.resultado.medida ? `, ${votacao.resultado.medida}` : ""}`}
          </p>
        )}
        {!concluida && (
          <div className="space-y-1">
            <button
              type="button"
              className={BOTAO}
              disabled={!votacao.pode_concluir || ocupado}
              onClick={() => void agir("conclusao-da-votacao")}
            >
              CONCLUIR VOTAÇÃO
            </button>
            {votacao.bloqueio_da_conclusao && <p className="text-xs text-slate-600">{votacao.bloqueio_da_conclusao}</p>}
          </div>
        )}
      </section>

      <section aria-label="Trava de robustez" className={`${CARTAO} px-4 py-4 space-y-3`}>
        <h2 className="text-base font-semibold text-slate-900">Trava de robustez</h2>
        <p className="text-sm text-slate-700">
          Procedente ou parcialmente procedente só concluem com os itens confirmados. O agente aponta; quem confirma é um membro.
        </p>
        {trava.pode_preencher && (
          <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void agir("trava/preenchimento")}>
            PREENCHER TRAVA
          </button>
        )}
        <ul className="space-y-3">
          {trava.itens.map((item) => (
            <ItemDaLista key={item.item} item={item} ocupado={ocupado} agir={agir} />
          ))}
        </ul>
        <div className="space-y-1 border-t border-border pt-3">
          <h3 className="text-sm font-semibold text-slate-900">Ciência do Código pelo acusado</h3>
          <p className="text-xs text-slate-500">O DP registra a ciência fora do aplicativo; um membro anexa o documento aqui.</p>
          {trava.ciencia.length > 0 && (
            <button type="button" className="text-sm font-semibold text-[#282760] underline" onClick={() => void verCiencia()}>
              {`Abrir a ciência anexada (versão ${trava.ciencia[0].versao}, por ${trava.ciencia[0].enviado_por})`}
            </button>
          )}
          {trava.pode_preencher && (
            <label className="block text-sm font-semibold text-slate-700">
              <span>ANEXAR CIÊNCIA DO CÓDIGO</span>
              <input
                type="file"
                className="block text-sm"
                accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif"
                disabled={ocupado}
                aria-label="Anexar ciência do Código"
                onChange={(e) => void enviarCiencia(e.target.files?.[0])}
              />
            </label>
          )}
        </div>
      </section>

      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </>
  );
}
