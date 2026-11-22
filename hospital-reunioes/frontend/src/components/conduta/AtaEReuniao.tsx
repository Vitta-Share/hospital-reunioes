"use client";

import { useState } from "react";

import { chamarComite } from "@/lib/conduta/comite";
import {
  FORMATOS_DA_TRANSCRICAO,
  abrirAtaAssinada,
  anexarTranscricaoDaReuniao,
  type AtaDoCaso,
  type DocumentoDaAta,
  type ReuniaoDoComite,
} from "@/lib/conduta/ata";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 disabled:text-slate-600 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

const SITUACAO_DA_ASSINATURA = {
  gerado: "Ainda não foi à ClickSign",
  enviado: "Aguardando a assinatura dos três",
  assinado: "Assinada pelos três",
};

function Lista({ titulo, itens }: { titulo: string; itens: string[] }) {
  if (itens.length === 0) return null;
  return (
    <div className="space-y-1">
      <h4 className="text-sm font-semibold text-slate-900">{titulo}</h4>
      <ul className="list-disc pl-5 space-y-1">
        {itens.map((item) => (
          <li key={item} className="text-sm text-slate-700 break-words">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Paragrafo({ titulo, texto }: { titulo: string; texto: string | null }) {
  if (!texto) return null;
  return (
    <div className="space-y-1">
      <h4 className="text-sm font-semibold text-slate-900">{titulo}</h4>
      <p className="text-sm text-slate-700 whitespace-pre-line break-words">{texto}</p>
    </div>
  );
}

/** A ata como ela vai para a assinatura, e os Pontos a confirmar à parte. */
function Documento({ ata }: { ata: DocumentoDaAta }) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">{`Versão ${ata.versao}, rito ${ata.identificacao.rito}, ${ata.identificacao.data}`}</p>
      <Paragrafo titulo="Resumo do caso" texto={ata.resumo} />
      <Lista titulo="Provas consideradas" itens={ata.provas} />
      <Paragrafo titulo="Defesa" texto={ata.defesa} />
      <Paragrafo titulo="Deliberação" texto={ata.deliberacao} />
      <Paragrafo titulo="Fundamentos" texto={ata.fundamentos} />
      <Paragrafo titulo="Medida recomendada à Direção" texto={ata.medida} />
      <div className="space-y-1">
        <h4 className="text-sm font-semibold text-slate-900">Votos registrados</h4>
        <ul className="space-y-2">
          {ata.votos.map((voto) => (
            <li key={voto.membro} className="text-sm text-slate-800">
              <p className="font-semibold">{`${voto.membro}: ${voto.resultado}${voto.medida ? `, ${voto.medida}` : ""}`}</p>
              <p className="text-slate-700 whitespace-pre-line break-words">{voto.justificativa}</p>
            </li>
          ))}
        </ul>
      </div>
      <Lista titulo="Correção de processo" itens={ata.correcao} />
      <Lista titulo="Encaminhamentos" itens={ata.encaminhamentos} />
      {ata.pontos.itens.length > 0 && (
        <aside aria-label="Pontos a confirmar" className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-3 space-y-1">
          <p className="text-xs font-semibold uppercase text-amber-800">{ata.pontos.rotulo}</p>
          <h4 className="text-sm font-semibold text-slate-900">Pontos a confirmar</h4>
          <p className="text-xs text-slate-600">Não fazem parte da ata. Em divergência, vale o voto registrado.</p>
          <ul className="list-disc pl-5 space-y-1">
            {ata.pontos.itens.map((ponto) => (
              <li key={ponto} className="text-sm text-slate-800 break-words">
                {ponto}
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}

/**
 * A ata de deliberação e, no rito Completo, a reunião do Comitê (issue #1834;
 * especificação, 7.3 e 8). A transcrição da reunião tem botão próprio, sem
 * seletor de tipo, e o áudio da reunião não entra. O servidor diz o que a
 * pessoa pode fazer.
 */
export function AtaEReuniao({
  casoId,
  ata,
  reuniao,
  aoMudar,
}: {
  casoId: string;
  ata: AtaDoCaso | null;
  reuniao: ReuniaoDoComite | null;
  aoMudar: () => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  if (!ata) return null;

  const fazer = async (acao: () => Promise<unknown>) => {
    setOcupado(true);
    setAviso(null);
    try {
      await acao();
      aoMudar();
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  const agir = (caminho: string, body?: unknown) =>
    fazer(() => chamarComite(`/casos/${casoId}/${caminho}`, { method: "POST", body: body ?? {} }));

  const verAssinada = async () => {
    try {
      window.open(await abrirAtaAssinada(casoId), "_blank", "noopener");
    } catch (e) {
      setAviso((e as Error).message);
    }
  };

  const documento = ata.documento;
  const assinatura = documento?.assinatura ?? null;

  return (
    <>
      {reuniao && (
        <section aria-label="Reunião do Comitê" className={`${CARTAO} px-4 py-4 space-y-3`}>
          <h2 className="text-base font-semibold text-slate-900">Reunião do Comitê</h2>
          <p className="text-sm text-slate-700">
            A reunião é gravada na plataforma de gravação do hospital. Anexe aqui só a transcrição: o áudio da reunião não é anexado.
          </p>
          {reuniao.transcricoes.length > 0 && (
            <p className="text-xs text-slate-500">
              {`Transcrição anexada: versão ${reuniao.transcricoes[0].versao}, por ${reuniao.transcricoes[0].enviado_por}`}
            </p>
          )}
          {reuniao.transcricao_eliminada_em && (
            <p className="text-xs text-slate-500">A transcrição foi eliminada ao concluir a reunião. Fica a ata assinada.</p>
          )}
          {reuniao.pode_anexar && (
            <label className="block text-sm font-semibold text-slate-700">
              <span>ANEXAR TRANSCRIÇÃO DA REUNIÃO DO COMITÊ</span>
              <input
                type="file"
                className="block text-sm"
                accept={FORMATOS_DA_TRANSCRICAO}
                disabled={ocupado}
                aria-label="Anexar transcrição da reunião do Comitê"
                onChange={(e) => {
                  const arquivo = e.target.files?.[0];
                  if (arquivo) void fazer(() => anexarTranscricaoDaReuniao(casoId, arquivo));
                }}
              />
            </label>
          )}
          <ul aria-label="Lista de conferência da reunião" className="space-y-2">
            {reuniao.lista.map((item) => (
              <li key={item.item} className="text-sm text-slate-800 space-y-1">
                {item.automatico ? (
                  <p>{`${item.estado === "feito" ? "Feito" : "Pendente"}: ${item.rotulo}`}</p>
                ) : (
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={item.estado === "feito"}
                      disabled={item.estado === "feito" || !reuniao.pode_marcar || ocupado}
                      onChange={() => void agir("reuniao/conferencia", { item: item.item })}
                    />
                    {item.rotulo}
                  </label>
                )}
                {item.marcado_por && <p className="text-xs text-slate-500">{`Marcado por ${item.marcado_por}`}</p>}
              </li>
            ))}
          </ul>
          {reuniao.concluida_em ? (
            <p className="text-sm font-semibold text-slate-900">{`Reunião concluída${reuniao.concluida_por ? ` por ${reuniao.concluida_por}` : ""}.`}</p>
          ) : (
            <div className="space-y-1">
              <button
                type="button"
                className={BOTAO}
                disabled={!reuniao.pode_concluir || ocupado}
                onClick={() => void agir("reuniao/conclusao")}
              >
                CONCLUIR REUNIÃO
              </button>
              {reuniao.bloqueio_da_conclusao && <p className="text-xs text-slate-600">{reuniao.bloqueio_da_conclusao}</p>}
            </div>
          )}
        </section>
      )}

      <section aria-label="Ata de deliberação" className={`${CARTAO} px-4 py-4 space-y-3`}>
        <h2 className="text-base font-semibold text-slate-900">Ata de deliberação</h2>
        <p className="text-sm text-slate-700">
          O agente redige a ata a partir dos votos registrados. A deliberação e os votos saem do aplicativo.
        </p>
        {documento ? <Documento ata={documento} /> : <p className="text-sm text-slate-600">A ata ainda não foi gerada.</p>}
        {assinatura && (
          <p className="text-sm font-semibold text-slate-900">
            {SITUACAO_DA_ASSINATURA[assinatura.situacao]}
            {assinatura.erro ? `. ${assinatura.erro}` : ""}
          </p>
        )}
        <div className="flex flex-col sm:flex-row gap-2">
          {(ata.pode_gerar || ata.bloqueio_da_geracao) && (
            <button type="button" className={BOTAO_CLARO} disabled={!ata.pode_gerar || ocupado} onClick={() => void agir("ata")}>
              {documento ? "GERAR ATA DE NOVO" : "GERAR ATA"}
            </button>
          )}
          {ata.pode_enviar && (
            <button type="button" className={BOTAO} disabled={ocupado} onClick={() => void agir("ata/assinatura")}>
              {assinatura ? "REENVIAR PARA ASSINATURA" : "ENVIAR PARA ASSINATURA"}
            </button>
          )}
          {assinatura?.situacao === "enviado" && (
            <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void agir("ata/reconsulta")}>
              Reconsultar status
            </button>
          )}
          {assinatura?.tem_copia && (
            <button type="button" className={BOTAO_CLARO} onClick={() => void verAssinada()}>
              Abrir a ata assinada
            </button>
          )}
        </div>
        {ata.bloqueio_da_geracao && <p className="text-xs text-slate-600">{ata.bloqueio_da_geracao}</p>}
      </section>

      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </>
  );
}
