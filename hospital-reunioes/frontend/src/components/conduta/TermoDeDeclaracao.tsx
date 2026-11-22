"use client";

import { useState } from "react";

import { chamarComite, type MembroDoCaso } from "@/lib/conduta/comite";
import { abrirTermoImpresso, dataEHora, type Depoimento, type TermoDeDeclaracao as Termo } from "@/lib/conduta/depoimentos";

const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 disabled:text-slate-600 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";
const SELO = "inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800";

function Aviso({ texto }: { texto: string | null }) {
  if (!texto) return null;
  return (
    <p role="alert" className="text-sm text-red-700">
      {texto}
    </p>
  );
}

/** Um pedido ao servidor com o "ocupado" e o aviso de erro da tela. */
function usePedido(aoMudar: () => void) {
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const pedir = async (caminho: string, body: unknown = {}) => {
    setOcupado(true);
    setAviso(null);
    try {
      await chamarComite(caminho, { method: "POST", body });
      aoMudar();
      return true;
    } catch (e) {
      setAviso((e as Error).message);
      return false;
    } finally {
      setOcupado(false);
    }
  };
  return { ocupado, aviso, setAviso, pedir };
}

/** O roteiro de perguntas que o agente sugere, por clique. */
function Roteiro({ base, depoimento, podeAgir, aoMudar }: { base: string; depoimento: Depoimento; podeAgir: boolean; aoMudar: () => void }) {
  const { ocupado, aviso, pedir } = usePedido(aoMudar);
  const roteiro = depoimento.roteiro;
  return (
    <section aria-label="Roteiro de perguntas" className="space-y-2 border-t border-border pt-3">
      <h4 className="text-sm font-semibold text-slate-900">
        Roteiro de perguntas {roteiro && <span className={SELO}>{roteiro.rotulo}</span>}
      </h4>
      {roteiro && (
        <ol className="list-decimal pl-5 space-y-1 text-sm text-slate-800">
          {roteiro.perguntas.map((p, i) => (
            <li key={i} className="break-words">
              {p}
            </li>
          ))}
        </ol>
      )}
      {podeAgir && (
        <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void pedir(`${base}/roteiro`)}>
          SUGERIR ROTEIRO DE PERGUNTAS
        </button>
      )}
      {ocupado && <p className="text-sm text-slate-600">O agente está preparando o roteiro.</p>}
      <Aviso texto={aviso} />
    </section>
  );
}

/** O formulário de "REDIGIR TERMO": o que o sistema põe na identificação. */
function Redigir({ base, aoMudar }: { base: string; aoMudar: () => void }) {
  const [aberto, setAberto] = useState(false);
  const [data, setData] = useState("");
  const [hora, setHora] = useState("");
  const [local, setLocal] = useState("");
  const [primeiro, setPrimeiro] = useState("");
  const [segundo, setSegundo] = useState("");
  const [cpf, setCpf] = useState("");
  const { ocupado, aviso, pedir } = usePedido(aoMudar);

  if (!aberto) {
    return (
      <button type="button" className={BOTAO} onClick={() => setAberto(true)}>
        REDIGIR TERMO
      </button>
    );
  }
  const pronto = data && hora && local.trim() && primeiro.trim() && segundo.trim();
  return (
    <form
      aria-label="Redigir termo"
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        void pedir(`${base}/termo`, { data, hora, local, conduziram: [primeiro, segundo], cpf });
      }}
    >
      <p className="text-sm text-slate-700">
        O agente redige o termo a partir da transcrição ou dos pontos da conversa. Nenhum nome sai do aplicativo.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="text-sm font-semibold text-slate-700 space-y-1 block">
          <span>Data da conversa</span>
          <input type="date" className={CAMPO} value={data} onChange={(e) => setData(e.target.value)} />
        </label>
        <label className="text-sm font-semibold text-slate-700 space-y-1 block">
          <span>Hora</span>
          <input type="time" className={CAMPO} value={hora} onChange={(e) => setHora(e.target.value)} />
        </label>
      </div>
      <label className="text-sm font-semibold text-slate-700 space-y-1 block">
        <span>Local</span>
        <input className={CAMPO} value={local} maxLength={200} onChange={(e) => setLocal(e.target.value)} />
      </label>
      <label className="text-sm font-semibold text-slate-700 space-y-1 block">
        <span>Quem conduziu (1)</span>
        <input className={CAMPO} value={primeiro} maxLength={200} onChange={(e) => setPrimeiro(e.target.value)} />
      </label>
      <label className="text-sm font-semibold text-slate-700 space-y-1 block">
        <span>Quem conduziu (2)</span>
        <input className={CAMPO} value={segundo} maxLength={200} onChange={(e) => setSegundo(e.target.value)} />
      </label>
      <label className="text-sm font-semibold text-slate-700 space-y-1 block">
        <span>CPF do declarante (opcional, pode ser preenchido à caneta)</span>
        <input className={CAMPO} value={cpf} maxLength={14} inputMode="numeric" onChange={(e) => setCpf(e.target.value)} />
      </label>
      <Aviso texto={aviso} />
      <button type="submit" className={BOTAO} disabled={!pronto || ocupado}>
        {ocupado ? "O AGENTE ESTÁ REDIGINDO" : "REDIGIR TERMO"}
      </button>
    </form>
  );
}

const paragrafos = (texto: string) =>
  texto
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
const linhas = (texto: string) =>
  texto
    .split("\n")
    .map((p) => p.trim())
    .filter(Boolean);

/** A revisão do termo: cada correção lançada vira uma versão nova. */
function Revisao({
  casoId,
  depoimentoId,
  termo,
  podeAgir,
  aoMudar,
}: {
  casoId: string;
  depoimentoId: string;
  termo: Termo;
  podeAgir: boolean;
  aoMudar: () => void;
}) {
  const base = `/casos/${casoId}/depoimentos/${depoimentoId}`;
  const [gravacao, setGravacao] = useState(termo.gravacao);
  const [declaracoes, setDeclaracoes] = useState(termo.declaracoes.join("\n\n"));
  const [documentos, setDocumentos] = useState(termo.documentos.join("\n"));
  const [lido, setLido] = useState(termo.lido_em_voz_alta);
  const { ocupado, aviso, setAviso, pedir } = usePedido(aoMudar);
  const [imprimindo, setImprimindo] = useState(false);

  const mudou =
    gravacao.trim() !== termo.gravacao ||
    JSON.stringify(paragrafos(declaracoes)) !== JSON.stringify(termo.declaracoes) ||
    JSON.stringify(linhas(documentos)) !== JSON.stringify(termo.documentos) ||
    lido !== termo.lido_em_voz_alta;

  const lancar = () => {
    const { cpf, data, hora, local, conduziram } = termo.identificacao;
    void pedir(`${base}/termo/correcoes`, {
      identificacao: { cpf, data, hora, local, conduziram },
      gravacao,
      declaracoes: paragrafos(declaracoes),
      documentos: linhas(documentos),
      lido_em_voz_alta: lido,
    });
  };

  const imprimir = async () => {
    setImprimindo(true);
    setAviso(null);
    try {
      window.open(await abrirTermoImpresso(casoId, depoimentoId), "_blank", "noopener");
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setImprimindo(false);
    }
  };

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-600">{`Versão ${termo.versao}, ${termo.origem === "agente" ? "redigida pelo agente" : "com correções"}, por ${termo.criado_por} em ${dataEHora(termo.criado_em)}`}</p>
      <label className="text-sm font-semibold text-slate-700 space-y-1 block">
        <span>Gravação</span>
        <textarea className={CAMPO} rows={2} value={gravacao} disabled={!podeAgir} onChange={(e) => setGravacao(e.target.value)} />
      </label>
      <label className="text-sm font-semibold text-slate-700 space-y-1 block">
        <span>Declarações (um parágrafo por bloco, separados por uma linha em branco)</span>
        <textarea className={CAMPO} rows={10} value={declaracoes} disabled={!podeAgir} onChange={(e) => setDeclaracoes(e.target.value)} />
      </label>
      <label className="text-sm font-semibold text-slate-700 space-y-1 block">
        <span>Documentos ou evidências (um por linha)</span>
        <textarea className={CAMPO} rows={3} value={documentos} disabled={!podeAgir} onChange={(e) => setDocumentos(e.target.value)} />
      </label>
      <label className="flex gap-2 items-start text-sm text-slate-800">
        <input type="checkbox" className="mt-0.5" checked={lido} disabled={!podeAgir} onChange={(e) => setLido(e.target.checked)} />
        Termo lido em voz alta para o depoente
      </label>
      <Aviso texto={aviso} />
      <div className="flex flex-col sm:flex-row gap-2">
        {podeAgir && (
          <button type="button" className={BOTAO_CLARO} disabled={!mudou || ocupado} onClick={lancar}>
            LANÇAR CORREÇÕES
          </button>
        )}
        <button type="button" className={BOTAO} disabled={imprimindo || mudou} onClick={() => void imprimir()}>
          IMPRIMIR TERMO
        </button>
      </div>
      {mudou && <p className="text-xs text-slate-600">Lance as correções antes de imprimir.</p>}
    </div>
  );
}

/** As notas do agente para quem apura: Sugestão, nunca impressas. */
function Notas({ termo }: { termo: Termo }) {
  if (termo.notas.itens.length === 0) return null;
  return (
    <section aria-label="Notas para quem apura" className="space-y-1 rounded-xl bg-amber-50 px-3 py-2">
      <h5 className="text-sm font-semibold text-slate-900">
        Notas para quem apura <span className={SELO}>{termo.notas.rotulo}</span>
      </h5>
      <p className="text-xs text-slate-600">Não fazem parte do termo e não são impressas.</p>
      <ul className="list-disc pl-5 space-y-1 text-sm text-slate-800">
        {termo.notas.itens.map((n, i) => (
          <li key={i} className="break-words">
            {n}
          </li>
        ))}
      </ul>
    </section>
  );
}

const SITUACAO_DA_RECUSA: Record<string, string> = {
  gerado: "A certidão de recusa foi gerada e não saiu para assinatura.",
  enviado: "Certidão de recusa enviada para assinatura dos dois membros.",
  assinado: "Certidão de recusa assinada pelos dois membros.",
};

/** A pessoa se recusou a assinar: a certidão vai à ClickSign para quem
 * registra e mais um membro do caso. */
function Recusa({ base, depoimento, membros, podeAgir, aoMudar }: { base: string; depoimento: Depoimento; membros: MembroDoCaso[]; podeAgir: boolean; aoMudar: () => void }) {
  const [aberto, setAberto] = useState(false);
  const [membro, setMembro] = useState("");
  const { ocupado, aviso, pedir } = usePedido(aoMudar);
  const recusa = depoimento.recusa;
  const assinada = recusa?.situacao === "assinado";
  const temTermoAssinado = depoimento.arquivos.termo_assinado.length > 0;
  if (temTermoAssinado && !recusa) return null;
  return (
    <section aria-label="Recusa de assinatura" className="space-y-2">
      {recusa && (
        <p className="text-sm text-slate-700">
          {SITUACAO_DA_RECUSA[recusa.situacao]}
          {recusa.erro ? ` ${recusa.erro}` : ""}
        </p>
      )}
      {podeAgir && !assinada && !temTermoAssinado && !aberto && (
        <button type="button" className={BOTAO_CLARO} onClick={() => setAberto(true)}>
          {recusa ? "REENVIAR CERTIDÃO DE RECUSA" : "REGISTRAR RECUSA DE ASSINATURA"}
        </button>
      )}
      {aberto && (
        <form
          aria-label="Certidão de recusa"
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            void pedir(`${base}/recusa`, { membro_id: membro }).then((ok) => ok && setAberto(false));
          }}
        >
          <p className="text-sm text-slate-700">Você e mais um membro do Comitê assinam a certidão na assinatura eletrônica.</p>
          <label className="text-sm font-semibold text-slate-700 space-y-1 block">
            <span>Quem assina com você</span>
            <select className={CAMPO} value={membro} onChange={(e) => setMembro(e.target.value)}>
              <option value="">Escolha</option>
              {membros.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nome ?? m.id}
                </option>
              ))}
            </select>
          </label>
          <Aviso texto={aviso} />
          <button type="submit" className={BOTAO} disabled={!membro || ocupado}>
            ENVIAR CERTIDÃO PARA ASSINATURA
          </button>
        </form>
      )}
    </section>
  );
}

/**
 * O termo de declaração do depoimento (issue #1831; especificação, 7.1 e
 * Anexos C e E.1): o roteiro sugerido, o termo redigido pelo agente depois do
 * clique, a revisão com as correções em versão nova, as Notas para quem apura
 * (Sugestão, nunca impressas), "IMPRIMIR TERMO" e a certidão de recusa.
 */
export function TermoDeDeclaracao({
  casoId,
  depoimento,
  podeAgir,
  membros,
  aoMudar,
}: {
  casoId: string;
  depoimento: Depoimento;
  podeAgir: boolean;
  membros: MembroDoCaso[];
  aoMudar: () => void;
}) {
  const base = `/casos/${casoId}/depoimentos/${depoimento.id}`;
  const termo = depoimento.termo ?? null;
  const temConversa =
    depoimento.arquivos.transcricao.length > 0 || Boolean(depoimento.sem_gravacao);
  return (
    <>
      <Roteiro base={base} depoimento={depoimento} podeAgir={podeAgir} aoMudar={aoMudar} />
      <section aria-label="Termo de declaração" className="space-y-2 border-t border-border pt-3">
        <h4 className="text-sm font-semibold text-slate-900">Termo de declaração</h4>
        {termo ? (
          <>
            <Revisao key={termo.versao} casoId={casoId} depoimentoId={depoimento.id} termo={termo} podeAgir={podeAgir} aoMudar={aoMudar} />
            <Notas termo={termo} />
            <Recusa base={base} depoimento={depoimento} membros={membros} podeAgir={podeAgir} aoMudar={aoMudar} />
          </>
        ) : podeAgir && temConversa ? (
          <Redigir base={base} aoMudar={aoMudar} />
        ) : (
          <p className="text-sm text-slate-600">O termo é redigido depois que a transcrição ou os pontos da conversa chegam.</p>
        )}
      </section>
    </>
  );
}
