"use client";

import { useState } from "react";
import { Send } from "lucide-react";

import {
  PERGUNTAS_DO_BUG,
  PERGUNTA_DO_PRINT,
  anexarPrint,
  enviarBug,
  registrarBug,
  type RespostasDoBug,
  type ResumoDoBug,
} from "@/lib/assistente-do-app/bug";

/**
 * O Roteiro do bug dentro do painel do robô (issue #2275, ADR 0113, decisão
 * 8): uma pergunta por vez, no máximo cinco (Onde, O que aconteceu, O que
 * esperava, Como repetir e o print), o resumo e o clique de envio. Pergunta
 * pulada sai "não informado" no resumo. A falha do envio mostra o motivo e
 * "Tentar de novo"; nada é reenviado sem o clique.
 */

type Etapa = "perguntas" | "print" | "resumo" | "enviado";

const VAZIAS: RespostasDoBug = { onde: "", o_que_aconteceu: "", o_que_esperava: "", como_repetir: "" };

const BOLHA_DO_ROBO = "self-start bg-slate-100 text-slate-800";
const BOLHA_DA_PESSOA = "self-end bg-primary text-white";

function Bolha({ de, children }: { de: "robo" | "pessoa"; children: React.ReactNode }) {
  return (
    <p
      className={`text-sm whitespace-pre-wrap rounded-xl px-3 py-2 max-w-[85%] ${
        de === "robo" ? BOLHA_DO_ROBO : BOLHA_DA_PESSOA
      }`}
    >
      {children}
    </p>
  );
}

export function RoteiroDoBug() {
  const [etapa, setEtapa] = useState<Etapa>("perguntas");
  const [respostas, setRespostas] = useState<RespostasDoBug>(VAZIAS);
  const [indice, setIndice] = useState(0);
  const [texto, setTexto] = useState("");
  const [demandaId, setDemandaId] = useState<string | null>(null);
  const [resumo, setResumo] = useState<ResumoDoBug | null>(null);
  const [prints, setPrints] = useState(0);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [falhaDoEnvio, setFalhaDoEnvio] = useState<string | null>(null);

  async function responder(valor: string) {
    if (ocupado) return;
    const atual = PERGUNTAS_DO_BUG[indice];
    const novas = { ...respostas, [atual.campo]: valor.trim() };
    setRespostas(novas);
    setTexto("");
    if (indice < PERGUNTAS_DO_BUG.length - 1) {
      setIndice(indice + 1);
      return;
    }
    setOcupado(true);
    setErro(null);
    try {
      const registrado = await registrarBug(novas);
      setDemandaId(registrado.demanda_id);
      setResumo(registrado.resumo);
      setEtapa("print");
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }

  async function guardarOPrint(arquivo: File | undefined) {
    if (!arquivo || !demandaId || ocupado) return;
    setOcupado(true);
    setErro(null);
    try {
      setPrints(await anexarPrint(demandaId, arquivo));
      setEtapa("resumo");
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }

  async function enviar() {
    if (!demandaId || ocupado) return;
    setOcupado(true);
    setFalhaDoEnvio(null);
    try {
      await enviarBug(demandaId);
      setEtapa("enviado");
    } catch (e) {
      setFalhaDoEnvio(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }

  const feitas = etapa === "perguntas" ? PERGUNTAS_DO_BUG.slice(0, indice) : PERGUNTAS_DO_BUG;

  return (
    <div className="flex flex-col gap-2">
      <Bolha de="pessoa">Relatar um bug</Bolha>
      {feitas.map(({ campo, pergunta }) => (
        <div key={campo} className="flex flex-col gap-2">
          <Bolha de="robo">{pergunta}</Bolha>
          <Bolha de="pessoa">{respostas[campo] || "Pulei"}</Bolha>
        </div>
      ))}

      {etapa === "perguntas" && (
        <>
          <Bolha de="robo">{PERGUNTAS_DO_BUG[indice].pergunta}</Bolha>
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (texto.trim()) void responder(texto);
            }}
          >
            <textarea
              aria-label="Sua resposta"
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              rows={2}
              maxLength={2000}
              className="flex-1 resize-none text-sm rounded-lg border border-slate-200 px-3 py-2 focus:outline-none focus:border-primary"
            />
            <button
              type="submit"
              aria-label="Responder"
              disabled={ocupado || !texto.trim()}
              className="w-9 h-9 rounded-lg bg-primary text-white flex items-center justify-center disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
          <button
            type="button"
            onClick={() => void responder("")}
            disabled={ocupado}
            className="self-start text-xs text-slate-500 hover:text-slate-700 underline disabled:opacity-50"
          >
            Pular
          </button>
        </>
      )}

      {etapa === "print" && (
        <>
          <Bolha de="robo">{PERGUNTA_DO_PRINT}</Bolha>
          <div className="flex flex-wrap gap-2">
            <label className="px-3 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-primary text-sm font-medium hover:bg-primary/10 cursor-pointer">
              Escolher o print
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="sr-only"
                disabled={ocupado}
                onChange={(e) => void guardarOPrint(e.target.files?.[0])}
              />
            </label>
            <button
              type="button"
              onClick={() => setEtapa("resumo")}
              disabled={ocupado}
              className="px-3 py-1.5 rounded-full border border-slate-200 text-slate-600 text-sm hover:bg-slate-50 disabled:opacity-50"
            >
              Não tenho print
            </button>
          </div>
        </>
      )}

      {(etapa === "resumo" || etapa === "enviado") && resumo && (
        <div className="self-stretch rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 flex flex-col gap-1">
          <p className="font-semibold">Confira o resumo antes de enviar.</p>
          <dl className="flex flex-col gap-1">
            {PERGUNTAS_DO_BUG.map(({ campo, rotulo }) => (
              <div key={campo}>
                <dt className="text-xs font-semibold text-slate-500">{rotulo}</dt>
                <dd>{resumo[campo]}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-slate-500">
            {prints === 0 ? "Sem print" : `${prints} ${prints === 1 ? "print guardado" : "prints guardados"} no aplicativo`}
          </p>
          {etapa === "resumo" && !falhaDoEnvio && (
            <button
              type="button"
              onClick={() => void enviar()}
              disabled={ocupado}
              className="self-start mt-1 px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-medium disabled:opacity-50"
            >
              Enviar à Vitta
            </button>
          )}
          {etapa === "resumo" && falhaDoEnvio && (
            <>
              <p className="text-xs text-red-600">{falhaDoEnvio}</p>
              <button
                type="button"
                onClick={() => void enviar()}
                disabled={ocupado}
                className="self-start mt-1 px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-medium disabled:opacity-50"
              >
                Tentar de novo
              </button>
            </>
          )}
        </div>
      )}

      {etapa === "enviado" && (
        <Bolha de="robo">O bug foi enviado à Vitta. Obrigado por avisar.</Bolha>
      )}
      {ocupado && <p className="self-start text-xs text-slate-400">Guardando…</p>}
      {erro && <p className="text-xs text-red-600">{erro}</p>}
    </div>
  );
}
