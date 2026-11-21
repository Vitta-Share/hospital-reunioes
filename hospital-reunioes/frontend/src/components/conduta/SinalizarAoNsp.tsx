"use client";

import { useState } from "react";

import type { NotaAoNucleo } from "@/lib/conduta/comite";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] w-full sm:w-auto";

const SO_A_COORDENACAO = "Só a coordenação envia a nota ao Núcleo.";

/** "2026-11-21T13:00:00+00:00" vira "21/11/2026", no fuso do hospital. */
function dataBr(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo" }).format(new Date(iso));
}

interface Props {
  notas: NotaAoNucleo[];
  papel: string | null;
  ocupado: boolean;
  /** Manda a ação ao servidor; devolve se deu certo. */
  enviar: (caminho: string, body?: unknown) => Promise<boolean>;
}

/**
 * A ação lateral "Sinalizar ao NSP" da tela do caso (issue #1850; especificação,
 * seção 5.3). Um membro do Comitê escreve a nota e só a coordenação a envia.
 * O Núcleo recebe só a nota, e a tela diz isso antes de a pessoa escrever.
 */
export function SinalizarAoNsp({ notas, papel, ocupado, enviar }: Props) {
  const [escrevendo, setEscrevendo] = useState(false);
  const [texto, setTexto] = useState("");
  const pendente = notas.find((nota) => !nota.enviada_em) ?? null;
  const doComite = papel !== null;
  const coordenacao = papel === "coordenacao";

  const abrir = () => {
    setTexto(pendente?.texto ?? "");
    setEscrevendo(true);
  };

  const salvar = async () => {
    if (await enviar("nota-ao-nsp", { texto })) setEscrevendo(false);
  };

  return (
    <section aria-label="Sinalizar ao NSP" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 className="text-base font-semibold text-slate-900">Sinalizar ao NSP</h2>
      <p className="text-sm text-slate-700">
        Quando o caso descreve um risco ao paciente, o Comitê manda uma nota ao Núcleo de Segurança do Paciente. O
        Núcleo recebe só a nota: sem o protocolo, sem o relato e sem quem relatou.
      </p>

      {notas.length > 0 && (
        <ul aria-label="Notas ao Núcleo" className="space-y-2">
          {notas.map((nota, i) => (
            <li key={`${nota.escrita_em ?? ""}-${i}`} className="rounded-xl bg-slate-50 px-3 py-2 space-y-1">
              <p className="text-sm text-slate-800 whitespace-pre-line break-words">{nota.texto}</p>
              <p className="text-xs text-slate-500">
                {nota.enviada_em ? `Enviada ao Núcleo em ${dataBr(nota.enviada_em)}` : "Esperando a coordenação enviar"}
              </p>
            </li>
          ))}
        </ul>
      )}

      {escrevendo ? (
        <form
          aria-label="Escrever a nota ao Núcleo"
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            void salvar();
          }}
        >
          <label className="text-sm font-semibold text-slate-700 space-y-1 block">
            <span>Nota ao Núcleo</span>
            <textarea
              className={CAMPO}
              rows={4}
              maxLength={2000}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
            />
          </label>
          <p className="text-xs text-slate-500">Não escreva o protocolo, nomes nem trechos do relato.</p>
          <button type="submit" className={BOTAO} disabled={!texto.trim() || ocupado}>
            SALVAR A NOTA
          </button>
        </form>
      ) : (
        doComite && (
          <button type="button" className={BOTAO_CLARO} onClick={abrir}>
            {pendente ? "EDITAR A NOTA" : "SINALIZAR AO NSP"}
          </button>
        )
      )}

      {pendente && !escrevendo && (
        <div className="space-y-1">
          <button
            type="button"
            className={BOTAO}
            disabled={!coordenacao || ocupado}
            onClick={() => void enviar("nota-ao-nsp/envio")}
          >
            ENVIAR AO NSP
          </button>
          {!coordenacao && <p className="text-sm text-slate-600">{SO_A_COORDENACAO}</p>}
        </div>
      )}
    </section>
  );
}
