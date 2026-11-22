"use client";

/**
 * Acompanhar o relato (issue #1845; especificação, P7): a pessoa entra com o
 * protocolo e o código, vê a situação do caso e as mensagens do Comitê, e
 * manda o complemento por aqui. É o único caminho entre o Comitê e quem
 * relatou.
 *
 * Sem login e sem nada no endereço: o protocolo e o código moram só no estado
 * desta tela. A página não mostra nada interno do caso; o servidor manda só a
 * situação e as mensagens.
 *
 * O complemento aceita anexo (issue #2187), com o mesmo seletor e o mesmo
 * aviso do passo "O que aconteceu". Os anexos sobem depois do complemento
 * enviado, pela rota do relato, com origem "complemento".
 */

import { useState } from "react";
import { Loader2 } from "lucide-react";

import {
  LIMITE_DO_COMPLEMENTO,
  acompanhar,
  diaDaMensagem,
  enviarComplemento,
  type Acompanhamento,
  type MensagemDoAcompanhamento,
} from "@/lib/conduta/acompanhamento";
import { enviarAnexo } from "@/lib/conduta/relato";

import { Anexos } from "./RelatoEmPassos";

const CAMPO =
  "w-full min-h-[44px] rounded-xl border border-border px-3 py-2.5 text-base text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary";
const ROTULO = "block text-sm font-semibold text-slate-700";
const BOTAO_PRINCIPAL =
  "flex w-full min-h-[44px] items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-base font-semibold text-white transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed";
const CARTAO = "bg-white rounded-2xl border border-border px-5 py-6 space-y-5";

const TITULO_DA_MENSAGEM: Record<MensagemDoAcompanhamento["tipo"], string> = {
  pergunta: "Pergunta do Comitê",
  resposta_final: "Resposta do Comitê",
  complemento: "Seu complemento",
};

function Mensagem({ mensagem }: { mensagem: MensagemDoAcompanhamento }) {
  const doComite = mensagem.de === "comite";
  return (
    <li className={`rounded-xl px-4 py-3 space-y-1 ${doComite ? "bg-primary/5" : "bg-slate-50"}`}>
      <p className="text-sm font-semibold text-slate-700">{TITULO_DA_MENSAGEM[mensagem.tipo]}</p>
      <p className="text-base text-slate-800 whitespace-pre-line break-words">{mensagem.texto}</p>
      <p className="text-xs text-slate-500">{diaDaMensagem(mensagem.em)}</p>
    </li>
  );
}

export function AcompanharRelato() {
  const [protocolo, setProtocolo] = useState("");
  const [codigo, setCodigo] = useState("");
  const [caso, setCaso] = useState<Acompanhamento | null>(null);
  const [complemento, setComplemento] = useState("");
  const [anexos, setAnexos] = useState<File[]>([]);
  const [anexosGuardados, setAnexosGuardados] = useState(0);
  const [anexosRecusados, setAnexosRecusados] = useState<string[]>([]);
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [enviandoAnexos, setEnviandoAnexos] = useState(false);

  const agir = async (chamada: () => Promise<Acompanhamento>) => {
    setOcupado(true);
    setAviso(null);
    try {
      setCaso(await chamada());
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  const entrar = (e: React.FormEvent) => {
    e.preventDefault();
    void agir(() => acompanhar(protocolo, codigo));
  };

  const complementar = async (e: React.FormEvent) => {
    e.preventDefault();
    setOcupado(true);
    setAviso(null);
    setAnexosGuardados(0);
    setAnexosRecusados([]);
    try {
      const atualizado = await enviarComplemento(protocolo, codigo, complemento);
      // Os anexos sobem um a um, depois do complemento enviado, com a tela
      // ocupada até o último: o que o servidor recusar aparece com o motivo,
      // e o complemento fica.
      const enviados = anexos;
      setEnviandoAnexos(enviados.length > 0);
      let guardados = 0;
      const recusados: string[] = [];
      for (const arquivo of enviados) {
        const motivo = await enviarAnexo({ protocolo, codigo }, arquivo, "complemento");
        if (motivo) recusados.push(`${arquivo.name}: ${motivo}`);
        else guardados += 1;
      }
      setCaso(atualizado);
      setComplemento("");
      setAnexos((atuais) => atuais.filter((arquivo) => !enviados.includes(arquivo)));
      setAnexosGuardados(guardados);
      setAnexosRecusados(recusados);
    } catch (falha) {
      setAviso((falha as Error).message);
    } finally {
      setEnviandoAnexos(false);
      setOcupado(false);
    }
  };

  if (!caso) {
    return (
      <form onSubmit={entrar} className={CARTAO} aria-label="Acompanhar relato">
        <div className="space-y-1">
          <h1 className="text-xl font-bold text-slate-900">Acompanhar relato</h1>
          <p className="text-base text-slate-700">Digite o protocolo e o código que você recebeu ao relatar.</p>
        </div>
        <label className="space-y-1.5 block">
          <span className={ROTULO}>Protocolo</span>
          <input
            className={CAMPO}
            value={protocolo}
            onChange={(e) => setProtocolo(e.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={20}
          />
        </label>
        <label className="space-y-1.5 block">
          <span className={ROTULO}>Código</span>
          <input
            className={CAMPO}
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={40}
          />
        </label>
        {aviso && (
          <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">
            {aviso}
          </p>
        )}
        <button type="submit" className={BOTAO_PRINCIPAL} disabled={ocupado || !protocolo.trim() || !codigo.trim()}>
          {ocupado && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
          Acompanhar
        </button>
        <p className="text-sm text-slate-500">Não guardamos IP, identificação do aparelho nem localização de quem acompanha.</p>
      </form>
    );
  }

  return (
    <div className={CARTAO}>
      <div className="space-y-1">
        <p className="text-sm text-slate-500">{`Relato ${caso.protocolo}`}</p>
        <h1 className="text-xl font-bold text-slate-900">Situação</h1>
        <p role="status" className="text-lg font-semibold text-primary">
          {caso.situacao}
        </p>
      </div>

      <section aria-labelledby="mensagens-do-comite" className="space-y-2">
        <h2 id="mensagens-do-comite" className="text-base font-semibold text-slate-900">
          Mensagens
        </h2>
        {caso.mensagens.length === 0 ? (
          <p className="text-sm text-slate-600">O Comitê ainda não enviou mensagem. Volte a esta página depois.</p>
        ) : (
          <ul className="space-y-2">
            {caso.mensagens.map((m, i) => (
              <Mensagem key={`${m.tipo}-${m.em}-${i}`} mensagem={m} />
            ))}
          </ul>
        )}
      </section>

      <form onSubmit={complementar} className="space-y-2" aria-label="Enviar complemento">
        <label className="space-y-1.5 block">
          <span className={ROTULO}>Complemento</span>
          <textarea
            aria-describedby="sobre-o-complemento"
            className={CAMPO}
            rows={5}
            maxLength={LIMITE_DO_COMPLEMENTO}
            value={complemento}
            onChange={(e) => setComplemento(e.target.value)}
          />
        </label>
        <p id="sobre-o-complemento" className="text-sm text-slate-500">
          Acrescente informação ao seu relato ou responda ao Comitê.
        </p>
        <Anexos arquivos={anexos} aoMudar={setAnexos} />
        {aviso && (
          <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">
            {aviso}
          </p>
        )}
        <button type="submit" className={BOTAO_PRINCIPAL} disabled={ocupado || !complemento.trim()}>
          {ocupado && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
          {enviandoAnexos ? "Enviando anexos" : "Enviar complemento"}
        </button>
        {enviandoAnexos && (
          <p className="text-sm text-slate-600">Não feche esta página até os anexos terminarem de subir.</p>
        )}
        {anexosGuardados > 0 && (
          <p className="text-sm text-slate-600">
            {anexosGuardados === 1 ? "1 anexo guardado." : `${anexosGuardados} anexos guardados.`}
          </p>
        )}
        {anexosRecusados.length > 0 && (
          <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800 space-y-1">
            <p className="font-semibold">O complemento foi enviado, mas estes anexos não foram guardados:</p>
            {anexosRecusados.map((recusa) => (
              <p key={recusa}>{recusa}</p>
            ))}
          </div>
        )}
      </form>
    </div>
  );
}
