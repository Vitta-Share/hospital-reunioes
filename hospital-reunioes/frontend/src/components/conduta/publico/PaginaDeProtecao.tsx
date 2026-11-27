"use client";

/**
 * A página "Como este canal protege você" (issue #1846, especificação 4.3).
 *
 * Pública, sem login. Cada bloco é um texto das Configurações, na versão
 * vigente; o bloco do encarregado de dados só aparece com o contato salvo.
 * Embaixo, as versões arquivadas da página, uma por data.
 */

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import {
  FalhaDoCanal,
  ROTA_DA_PROTECAO,
  diaCurto,
  lerDoCanal,
  type PaginaDeProtecao as Pagina,
} from "@/lib/conduta/publico";

const ABERTURA = "protecao_abertura";

type Estado = { tipo: "carregando" } | { tipo: "fechado" } | { tipo: "falha"; mensagem: string } | { tipo: "pronto"; pagina: Pagina };

function Bloco({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <section className="bg-white rounded-2xl border border-border px-5 py-4 space-y-1.5">
      <h2 className="text-base font-semibold text-slate-900">{titulo}</h2>
      <p className="text-base text-slate-700 whitespace-pre-line">{texto}</p>
    </section>
  );
}

export function PaginaDeProtecao() {
  const [em, setEm] = useState<string | null>(null);
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });

  useEffect(() => {
    let vivo = true;
    const caminho = em ? `${ROTA_DA_PROTECAO}?em=${em}` : ROTA_DA_PROTECAO;
    lerDoCanal<Pagina>(caminho)
      .then((pagina) => {
        if (vivo) setEstado(pagina ? { tipo: "pronto", pagina } : { tipo: "fechado" });
      })
      .catch((erro: unknown) => {
        const mensagem = erro instanceof FalhaDoCanal ? erro.message : "Não foi possível abrir a página. Tente de novo.";
        if (vivo) setEstado({ tipo: "falha", mensagem });
      });
    return () => {
      vivo = false;
    };
  }, [em]);

  if (estado.tipo === "carregando") {
    return (
      <div className="flex justify-center py-10" role="status" aria-label="Carregando">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" aria-hidden="true" />
      </div>
    );
  }
  if (estado.tipo === "fechado") return <p className="text-center text-slate-600 py-10">Página não encontrada.</p>;
  if (estado.tipo === "falha") return <p className="text-center text-slate-600 py-10">{estado.mensagem}</p>;

  const { pagina } = estado;
  const abertura = pagina.blocos.find((b) => b.chave === ABERTURA);
  const blocos = pagina.blocos.filter((b) => b.chave !== ABERTURA);

  return (
    <article className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900 text-center">Como este canal protege você</h1>
      {pagina.em && (
        <p className="text-sm text-center text-slate-500">
          Versão arquivada de {diaCurto(pagina.em)}.{" "}
          <button type="button" className="underline font-semibold" onClick={() => setEm(null)}>
            Ver a versão de hoje
          </button>
        </p>
      )}
      {abertura && <p className="text-lg text-center text-slate-800 whitespace-pre-line">{abertura.texto}</p>}
      {blocos.map((b) => (
        <Bloco key={b.chave} titulo={b.titulo} texto={b.texto} />
      ))}
      {pagina.encarregado && <Bloco titulo="Encarregado de dados" texto={pagina.encarregado.texto} />}
      {pagina.versoes.length > 0 && (
        <section className="pt-2 space-y-2">
          <h2 className="text-sm font-semibold text-slate-600">Versões desta página</h2>
          <ul className="flex flex-wrap gap-2">
            {pagina.versoes.map((dia) => (
              <li key={dia}>
                <button
                  type="button"
                  aria-pressed={pagina.em === dia}
                  onClick={() => setEm(dia)}
                  className="min-h-[44px] rounded-xl border border-border bg-white px-3 text-sm text-slate-700"
                >
                  {diaCurto(dia)}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
