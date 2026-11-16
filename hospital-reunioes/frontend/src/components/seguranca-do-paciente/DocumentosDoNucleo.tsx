"use client";

import { useCallback, useEffect, useState } from "react";
import { FileCheck2 } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import {
  ROTULO_DA_NATUREZA,
  TIPOS,
  lerTexto,
  listarDocumentos,
  publicarVersao,
  type DocumentoDoNucleo,
  type NaturezaDaRevisao,
  type TipoDeDocumento,
} from "@/lib/seguranca-do-paciente/documentos";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO =
  "w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30";
const BOTAO_PRIMARIO =
  "inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-60";
const BOTAO_SECUNDARIO =
  "inline-flex items-center justify-center rounded-lg border border-border bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50";

const FALTA_A_NATUREZA = "Diga se a revisão do Regimento é material ou só de redação.";

async function token(): Promise<string | null> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return session?.access_token ?? null;
}

function dataCurta(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
}

function Versao({ documento }: { documento: DocumentoDoNucleo }) {
  const [texto, setTexto] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function ler() {
    const t = await token();
    if (!t) return;
    const lido = await lerTexto(t, documento.id);
    if (lido.erro) setErro(lido.erro);
    else setTexto(lido.texto ?? "");
  }

  const publicado = [
    documento.publicado_em ? `Publicada em ${dataCurta(documento.publicado_em)}` : null,
    documento.publicado_por ? `por ${documento.publicado_por}` : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-slate-900">Versão {documento.versao}</span>
        {documento.vigente && (
          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">Vigente</span>
        )}
        {documento.natureza_revisao && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
            {ROTULO_DA_NATUREZA[documento.natureza_revisao]}
          </span>
        )}
        {documento.tem_arquivo_assinado && (
          <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">
            <FileCheck2 className="h-3 w-3" aria-hidden />
            Assinado
          </span>
        )}
      </div>
      <p className="mt-0.5 text-sm text-slate-700 break-words">{documento.titulo}</p>
      {publicado && <p className="text-xs text-slate-500">{publicado}</p>}
      {documento.tem_texto && texto === null && (
        <button type="button" className={`${BOTAO_SECUNDARIO} mt-2`} onClick={ler}>
          Ler o texto
        </button>
      )}
      {erro && <p className="mt-2 text-sm text-red-600">{erro}</p>}
      {texto !== null && (
        <div className="mt-2 max-h-[60vh] overflow-y-auto rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-800 whitespace-pre-wrap break-words">
          {texto}
        </div>
      )}
    </div>
  );
}

function DoTipo({ rotulo, versoes }: { rotulo: string; versoes: DocumentoDoNucleo[] }) {
  const vigente = versoes.find((v) => v.vigente);
  const anteriores = versoes.filter((v) => v !== vigente);
  const idTitulo = `documentos-${versoes[0].tipo}`;

  return (
    <section aria-labelledby={idTitulo} className={`${CARTAO} px-4 py-4`}>
      <h2 id={idTitulo} className="text-base font-semibold text-slate-900">
        {rotulo}
      </h2>
      {vigente && (
        <article aria-label={`Versão ${vigente.versao}, vigente`} className="mt-3">
          <Versao documento={vigente} />
        </article>
      )}
      {anteriores.length > 0 && (
        <>
          <p className="mt-4 text-xs font-semibold text-slate-500">Versões anteriores</p>
          <ul aria-label="Versões anteriores" className="mt-2 space-y-3 border-t border-border pt-3">
            {anteriores.map((versao) => (
              <li key={versao.id}>
                <Versao documento={versao} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function FormularioDePublicacao({ aoPublicar }: { aoPublicar: () => void }) {
  const [tipo, setTipo] = useState<TipoDeDocumento>("regimento");
  const [titulo, setTitulo] = useState("");
  const [texto, setTexto] = useState("");
  const [natureza, setNatureza] = useState<NaturezaDaRevisao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    if (!titulo.trim()) {
      setErro("Dê um título ao documento.");
      return;
    }
    if (tipo === "regimento" && natureza === null) {
      setErro(FALTA_A_NATUREZA);
      return;
    }
    if (tipo === "regimento" && !texto.trim()) {
      setErro("O texto do Regimento é obrigatório.");
      return;
    }
    const t = await token();
    if (!t) return;
    setEnviando(true);
    const falha = await publicarVersao(t, { tipo, titulo: titulo.trim(), texto, natureza_revisao: natureza });
    setEnviando(false);
    if (falha) {
      setErro(falha);
      return;
    }
    setTitulo("");
    setTexto("");
    setNatureza(null);
    aoPublicar();
  }

  return (
    <form onSubmit={enviar} className={`${CARTAO} space-y-3 px-4 py-4`} noValidate>
      <p className="text-sm text-slate-600">
        A versão publicada passa a ser a vigente do tipo. A anterior continua na lista.
      </p>
      <div>
        <label htmlFor="documento-tipo" className="text-sm font-medium text-slate-700">
          Tipo
        </label>
        <select
          id="documento-tipo"
          className={`${CAMPO} mt-1`}
          value={tipo}
          onChange={(e) => setTipo(e.target.value as TipoDeDocumento)}
        >
          {TIPOS.map(({ tipo: valor, rotulo }) => (
            <option key={valor} value={valor}>
              {rotulo}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="documento-titulo" className="text-sm font-medium text-slate-700">
          Título
        </label>
        <input
          id="documento-titulo"
          className={`${CAMPO} mt-1`}
          maxLength={200}
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor="documento-texto" className="text-sm font-medium text-slate-700">
          Texto
        </label>
        <textarea
          id="documento-texto"
          className={`${CAMPO} mt-1 min-h-40`}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
      </div>
      <fieldset>
        <legend className="text-sm font-medium text-slate-700">
          Natureza da revisão{tipo === "regimento" ? "" : " (opcional)"}
        </legend>
        <div className="mt-1 space-y-1">
          {(
            [
              ["material", "Material (pede nova assinatura do Termo)"],
              ["redacao", "De redação (não pede nova assinatura)"],
            ] as const
          ).map(([valor, rotulo]) => (
            <label key={valor} className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="radio"
                name="natureza-revisao"
                value={valor}
                checked={natureza === valor}
                onChange={() => setNatureza(valor)}
              />
              {rotulo}
            </label>
          ))}
        </div>
      </fieldset>
      {erro && <p className="text-sm text-red-600">{erro}</p>}
      <button type="submit" className={BOTAO_PRIMARIO} disabled={enviando}>
        Publicar
      </button>
    </form>
  );
}

/**
 * A tela Documentos do Núcleo (issue #1767): a vigente de cada tipo e as
 * anteriores, o texto lido na tela, e a publicação de versão nova para quem
 * gere o Núcleo. Não há apagar nem editar: a correção é uma versão nova.
 */
export function DocumentosDoNucleo({ podePublicar }: { podePublicar: boolean }) {
  const [documentos, setDocumentos] = useState<DocumentoDoNucleo[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [publicando, setPublicando] = useState(false);

  const carregar = useCallback(async () => {
    const t = await token();
    if (!t) return;
    const lido = await listarDocumentos(t);
    if (lido.erro) setErro(lido.erro);
    else {
      setErro(null);
      setDocumentos(lido.documentos ?? []);
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const grupos = TIPOS.map(({ tipo, rotulo }) => ({
    rotulo,
    versoes: (documentos ?? []).filter((d) => d.tipo === tipo).sort((a, b) => b.versao - a.versao),
  })).filter((g) => g.versoes.length > 0);

  return (
    <div className="space-y-4">
      {podePublicar &&
        (publicando ? (
          <FormularioDePublicacao
            aoPublicar={() => {
              setPublicando(false);
              void carregar();
            }}
          />
        ) : (
          <button type="button" className={BOTAO_PRIMARIO} onClick={() => setPublicando(true)}>
            Publicar versão nova
          </button>
        ))}
      {erro && <p className="text-sm text-red-600">{erro}</p>}
      {documentos !== null && grupos.length === 0 && (
        <div className={`${CARTAO} px-4 py-6 text-center text-sm text-slate-600`}>Nenhum documento publicado ainda.</div>
      )}
      {grupos.map((grupo) => (
        <DoTipo key={grupo.rotulo} rotulo={grupo.rotulo} versoes={grupo.versoes} />
      ))}
    </div>
  );
}
