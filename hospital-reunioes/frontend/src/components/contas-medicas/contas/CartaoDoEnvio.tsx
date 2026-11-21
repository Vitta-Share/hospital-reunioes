"use client";

/**
 * O cartão do envio, na etapa Envios (issues #1336, #1337, #1338, #1339,
 * #1401, #1416 a #1419), saído da página na divisão em peças da issue #1951.
 * As regras e a aparência seguem as de antes; o topo do cartão mostra o
 * número do atendimento e o rótulo do paciente, sem a palavra "Atendimento".
 */

import { useEffect, useRef, useState } from "react";
import { Upload } from "lucide-react";

import {
  type BarraDosEnvios,
  type ItemDaFila,
  detalheDaConta,
  rotuloDaSituacao,
  textoParaATI,
  textosDaBarra,
} from "@/lib/contas-medicas/envio";

import { NumeroEPaciente, periodoDaConta } from "./ListaDeContas";
import { COR_DO_TOM, tomDaSituacao } from "./situacao";

/** A borda do cartão do envio pela situação, nas cores dos cartões da Ouvidoria. */
const BORDA_DA_SITUACAO: Record<string, string> = {
  ERRO: "border-l-red-500",
  AGUARDANDO_ARQUIVO: "border-l-amber-500",
  NA_FILA: "border-l-slate-300",
  PROCESSANDO: "border-l-emerald-500",
};

/** O quadrado de cada estado: o que falta, o que chegou e o arquivo em que a análise parou (issue #1337). */
const COR_DO_QUADRADO = {
  falta: { caixa: "border-dashed border-slate-300 bg-white", rotulo: "text-slate-500", texto: "text-slate-600" },
  chegou: { caixa: "border-emerald-200 bg-emerald-50", rotulo: "text-emerald-800", texto: "text-emerald-900" },
  erro: { caixa: "border-red-300 bg-red-50", rotulo: "text-red-800", texto: "text-red-900" },
};

function Quadrado({
  nome,
  falta,
  comErro = false,
  rotuloDoBotao,
  onEnviar,
  children,
}: {
  nome: "Conta" | "Prontuário";
  falta: boolean;
  comErro?: boolean;
  rotuloDoBotao: string;
  onEnviar: () => void;
  children: React.ReactNode;
}) {
  const estado = falta ? "falta" : comErro ? "erro" : "chegou";
  const cor = COR_DO_QUADRADO[estado];
  return (
    <section
      aria-label={nome}
      data-estado={estado}
      className={`min-w-0 rounded-xl border px-3 py-2.5 ${cor.caixa}`}
    >
      <p className={`text-xs font-semibold uppercase tracking-wide ${cor.rotulo}`}>
        {nome}
      </p>
      {falta ? (
        <>
          <p className="mt-0.5 text-sm text-slate-600">Falta enviar</p>
          <button
            type="button"
            onClick={onEnviar}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white"
          >
            <Upload className="h-3.5 w-3.5" aria-hidden="true" />
            {rotuloDoBotao}
          </button>
        </>
      ) : (
        <div className={`mt-0.5 text-sm break-words ${cor.texto}`}>{children}</div>
      )}
    </section>
  );
}

/**
 * A frase da cópia que não aconteceu. O `writeText` falha igual quando a API
 * não existe e quando o navegador nega: a frase diz o desfecho e a saída, que
 * é a caixa logo abaixo (o mesmo cuidado do "Copiar para IA" da Tecnologia).
 */
const NAO_COPIOU =
  "O navegador não liberou a cópia automática. O texto está na caixa abaixo, já selecionado: copie com Ctrl+C (ou Cmd+C).";

/**
 * O Erro do cartão do envio (issue #1337): a frase, o Código do erro, "Ver
 * detalhes" com o detalhe técnico e "Copiar para a TI", que leva o que a TI
 * precisa para achar o erro sem ver a tela. Quando o servidor diz que a ação é
 * Analisar de novo (o erro não foi no PDF e ele ainda está guardado), o botão
 * põe a conta de volta na fila sem anexar nada (issue #1339). Na conta parada
 * por folha escaneada ilegível, "Analisar assim mesmo" fica ao lado de "Enviar
 * de novo" quando o servidor deixa (issue #1401).
 */
function ErroDoEnvio({
  conta,
  onEnviar,
  onAnalisarDeNovo,
  onAnalisarAssimMesmo,
  onDescartar,
}: {
  conta: ItemDaFila;
  onEnviar: () => void;
  onAnalisarDeNovo: () => Promise<string | null>;
  onAnalisarAssimMesmo: () => Promise<string | null>;
  onDescartar?: () => void;
}) {
  const [aberto, setAberto] = useState(false);
  const [analisando, setAnalisando] = useState(false);
  const [recusa, setRecusa] = useState<string | null>(null);
  const [copiou, setCopiou] = useState(false);
  const [paraPegarAMao, setParaPegarAMao] = useState<string | null>(null);
  const caixa = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (paraPegarAMao) caixa.current?.select();
  }, [paraPegarAMao]);

  async function copiar() {
    const texto = textoParaATI(conta);
    setCopiou(false);
    setParaPegarAMao(null);
    try {
      await navigator.clipboard.writeText(texto);
      setCopiou(true);
    } catch (e) {
      console.error("[contas-medicas] o navegador não copiou", e);
      setParaPegarAMao(texto);
    }
  }

  async function analisar(pedir: () => Promise<string | null>) {
    setAnalisando(true);
    setRecusa(null);
    const frase = await pedir();
    setAnalisando(false);
    setRecusa(frase);
  }

  const idDoDetalhe = `detalhe-do-erro-${conta.id}`;
  return (
    <div className="space-y-2">
      {conta.erro_motivo && <p className="min-w-0 break-words text-sm text-red-700">{conta.erro_motivo}</p>}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {conta.erro_codigo && (
          <span className="text-xs text-slate-500">
            Código <span className="font-mono font-semibold text-slate-800">{conta.erro_codigo}</span>
          </span>
        )}
        <button
          type="button"
          aria-expanded={aberto}
          aria-controls={idDoDetalhe}
          onClick={() => setAberto((valor) => !valor)}
          className="text-sm font-medium text-primary hover:underline"
        >
          Ver detalhes
        </button>
        <button type="button" onClick={copiar} className="text-sm font-medium text-primary hover:underline">
          Copiar para a TI
        </button>
        {conta.erro_acao === "analisar_de_novo" ? (
          <button
            type="button"
            onClick={() => analisar(onAnalisarDeNovo)}
            disabled={analisando}
            className="text-sm font-medium text-primary hover:underline disabled:opacity-50"
          >
            Analisar de novo
          </button>
        ) : (
          <button type="button" onClick={onEnviar} className="text-sm font-medium text-primary hover:underline">
            Enviar de novo
          </button>
        )}
        {conta.pode_analisar_assim_mesmo && (
          <button
            type="button"
            onClick={() => analisar(onAnalisarAssimMesmo)}
            disabled={analisando}
            className="text-sm font-medium text-primary hover:underline disabled:opacity-50"
          >
            Analisar assim mesmo
          </button>
        )}
        {onDescartar && (
          <button type="button" onClick={onDescartar} className="text-sm font-medium text-red-700 hover:underline">
            Descartar
          </button>
        )}
      </div>
      {recusa && (
        <p role="alert" className="text-sm text-red-700">
          {recusa}
        </p>
      )}
      {aberto && (
        <p id={idDoDetalhe} className="break-all rounded-lg bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700">
          {conta.erro_detalhe ?? "Sem detalhe técnico gravado."}
        </p>
      )}
      {copiou && (
        <p role="status" className="text-xs text-emerald-700">
          Copiado. Cole na conversa com a TI.
        </p>
      )}
      {paraPegarAMao && (
        <>
          <p role="status" className="text-xs text-amber-800">
            {NAO_COPIOU}
          </p>
          <textarea
            ref={caixa}
            readOnly
            value={paraPegarAMao}
            rows={5}
            aria-label="Texto para a TI"
            className="w-full rounded-lg border border-border bg-white px-3 py-2 font-mono text-xs text-slate-800"
          />
        </>
      )}
    </div>
  );
}

/** A pílula âmbar da conta que passou de 2 vezes a Previsão (issue #1417). */
const COR_DA_DEMORA = "bg-amber-100 text-amber-900";

/** A cor da pílula: a da situação, ou âmbar na conta demorando mais que o normal. */
function corDaPilula(conta: ItemDaFila): string {
  if (conta.demorando) return COR_DA_DEMORA;
  return COR_DO_TOM[tomDaSituacao(conta.situacao)];
}

/**
 * A barra fina no topo da aba Envios (issue #1417): quantas contas estão sendo
 * lidas e quantas esperam, os tempos médios da semana e a hora em que a fila
 * deve esvaziar.
 */
export function BarraDeTempos({ barra }: { barra: BarraDosEnvios }) {
  return (
    <div role="status" aria-label="Tempos da fila" className="border-b border-border px-1 py-2">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
        {textosDaBarra(barra).map((texto) => (
          <li key={texto}>{texto}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * A conta da aba de envios, com o quadrado de cada arquivo (issue #1336). O
 * clique no cartão abre o painel lateral do Processamento (issue #1418); o
 * clique nos botões e links de dentro faz só o que eles fazem.
 */
export function CartaoDoEnvio({
  conta,
  onAbrir,
  onEnviar,
  onAnalisarDeNovo,
  onAnalisarAssimMesmo,
  onDescartar,
}: {
  conta: ItemDaFila;
  onAbrir: () => void;
  onEnviar: () => void;
  onAnalisarDeNovo: () => Promise<string | null>;
  onAnalisarAssimMesmo: () => Promise<string | null>;
  onDescartar: () => void;
}) {
  // O valor da conta fica fora do cartão (issue #1419): a Fila nunca anda por valor.
  const detalhe = detalheDaConta({ ...conta, valor_apontado: null });
  const periodo = periodoDaConta(conta);
  const paginas = conta.prontuario_paginas;
  const ocr = conta.prontuario_paginas_ocr;
  const dias = conta.dias_internacao;
  const erro = conta.situacao === "ERRO";
  return (
    <li>
      <article
        onClick={(e) => {
          if (!(e.target as HTMLElement).closest("button, a, textarea")) onAbrir();
        }}
        className={`cursor-pointer rounded-xl border border-border border-l-4 bg-white p-4 space-y-3 hover:shadow-premium ${
          BORDA_DA_SITUACAO[conta.situacao] ?? "border-l-slate-300"
        }`}
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <button
            type="button"
            onClick={onAbrir}
            aria-haspopup="dialog"
            className="min-w-0 flex-1 text-left normal-case hover:underline"
          >
            <NumeroEPaciente conta={conta} />
          </button>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${corDaPilula(conta)}`}>
            {rotuloDaSituacao(conta)}
          </span>
          {conta.com && <span className="text-xs text-slate-500">com {conta.com}</span>}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Quadrado
            nome="Conta"
            falta={conta.falta === "conta"}
            comErro={erro && conta.erro_arquivo === "conta"}
            rotuloDoBotao="Enviar a conta"
            onEnviar={onEnviar}
          >
            <p>{conta.numero_conta ? `Conta ${conta.numero_conta}` : "Chegou"}</p>
            {periodo && <p className="text-xs">{periodo}</p>}
            {(conta.operadora || dias != null) && (
              <p className="text-xs">
                {[conta.operadora, dias != null ? `${dias} ${dias === 1 ? "dia" : "dias"} de internação` : null]
                  .filter(Boolean)
                  .join(", ")}
              </p>
            )}
          </Quadrado>
          <Quadrado
            nome="Prontuário"
            falta={conta.falta === "prontuario"}
            comErro={erro && conta.erro_arquivo === "prontuario"}
            rotuloDoBotao="Enviar o prontuário"
            onEnviar={onEnviar}
          >
            <p>{paginas != null ? `${paginas} ${paginas === 1 ? "página" : "páginas"}` : "Chegou"}</p>
            {ocr != null && (
              <p className="text-xs">{ocr === 0
                  ? "nenhuma escaneada"
                  : ocr === 1
                    ? "1 escaneada, lida por OCR"
                    : `${ocr} escaneadas, lidas por OCR`}</p>
            )}
          </Quadrado>
        </div>
        {erro ? (
          <ErroDoEnvio
            conta={conta}
            onEnviar={onEnviar}
            onAnalisarDeNovo={onAnalisarDeNovo}
            onAnalisarAssimMesmo={onAnalisarAssimMesmo}
            onDescartar={conta.pode_descartar ? onDescartar : undefined}
          />
        ) : (
          (detalhe || conta.pode_descartar) && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              {detalhe && <span className="min-w-0 break-words text-xs text-slate-600">{detalhe}</span>}
              {conta.pode_descartar && (
                <button type="button" onClick={onDescartar} className="text-sm font-medium text-red-700 hover:underline">
                  Descartar
                </button>
              )}
            </div>
          )
        )}
      </article>
    </li>
  );
}
