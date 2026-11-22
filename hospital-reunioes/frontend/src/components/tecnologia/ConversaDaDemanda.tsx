"use client";

/**
 * A Conversa da Demanda (issue #1537, PRD #1529, ADR 0083, decisão 8).
 *
 * A troca de mensagens entre o diretor e os Desenvolvedores dentro de uma
 * Demanda, numa área própria, separada da conversa com a IA. A menção é por
 * nome, no formato dos comentários de Pendência: "@" abre a lista de quem vê
 * a Demanda, que o servidor manda, e o clique escreve "@Nome Completo ". Quem
 * é avisado no sino é o servidor que decide.
 *
 * O Envio aos desenvolvedores (issue #2011, ADR 0108, decisões 3 a 5): quem
 * não é Desenvolvedor vê o botão "Enviar para os desenvolvedores", desligado
 * sem mensagem nova dele desde o último envio. O clique mostra o "Entendi
 * assim:" que a IA leu das mensagens, com Enviar e Corrigir; o Enviar abre o
 * Ajuste do plano e a conversa ganha a linha do envio. Quem decide se o botão
 * aparece e quantas mensagens são novas é o servidor.
 */

import { Fragment, useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";

import { LIMITE_DA_MENSAGEM } from "./assistente";
import { CartaoDaPergunta, type PerguntaDaVitta, perguntaValida } from "./CartaoDaPergunta";
import { BASE_TECNOLOGIA, FALHA_DE_CONEXAO, motivoDaRecusa } from "./demandas";
import { SeparadorDeDia, diaDaMensagem } from "./SeparadorDeDia";
import { TextoDaMensagem } from "./TextoDaMensagem";

type Mensagem = {
  id: string;
  autor: string | null;
  texto: string;
  criado_em: string | null;
  minha: boolean;
  /** A linha do Envio aos desenvolvedores, que não é bolha de ninguém. */
  sistema?: boolean;
  /** A entrada que é Pergunta da Vitta (issue #2116): o cartão no lugar da bolha. */
  pergunta?: PerguntaDaVitta | null;
};
type Mencionavel = { id: string; nome: string };
/** O botão do envio: nulo quando ele não aparece (Desenvolvedor, ou pedido sem card). */
type Envio = { mensagens_novas: number };
type Entendi = {
  id: string;
  topicos: string[];
  cards: { numero: number; muda: string }[];
  /** Quantas mensagens novas a interpretação leu: o Enviar desconta só estas. */
  cobertas?: number;
};

const CONVERSA_FALHOU = "Não foi possível carregar a Conversa da Demanda. Tente recarregar a página.";

export function urlDaConversaDaDemanda(demandaId: string): string {
  return `${BASE_TECNOLOGIA}/chat/${encodeURIComponent(demandaId)}/conversa`;
}

function envioValido(item: unknown): item is Envio {
  return typeof item === "object" && item !== null && typeof (item as Envio).mensagens_novas === "number";
}

function entendiValido(item: unknown): item is Entendi {
  if (typeof item !== "object" || item === null) return false;
  const e = item as Record<string, unknown>;
  return typeof e.id === "string" && Array.isArray(e.topicos);
}

function mensagemValida(item: unknown): item is Mensagem {
  if (typeof item !== "object" || item === null) return false;
  const m = item as Record<string, unknown>;
  return typeof m.id === "string" && typeof m.texto === "string";
}

function quando(criadoEm: string | null): string {
  if (!criadoEm) return "";
  const data = new Date(criadoEm);
  if (Number.isNaN(data.getTime())) return "";
  return data.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/**
 * O dia da mensagem `i` quando ele é outro que o da mensagem anterior com data
 * (issue #2117): é ali que entra o separador. Nulo no mesmo dia ou sem data.
 */
function trocaDeDia(mensagens: Mensagem[], i: number): string | null {
  const dia = diaDaMensagem(mensagens[i].criado_em);
  if (!dia) return null;
  for (let j = i - 1; j >= 0; j--) {
    const anterior = diaDaMensagem(mensagens[j].criado_em);
    if (anterior) return anterior === dia ? null : dia;
  }
  return dia;
}

/** O trecho depois do último "@" antes do cursor, se ele ainda parece um nome. */
function buscaDaMencao(texto: string, cursor: number): string | null {
  const antes = texto.slice(0, cursor);
  const arroba = antes.lastIndexOf("@");
  if (arroba < 0) return null;
  const depois = antes.slice(arroba + 1);
  return depois.split(" ").length <= 3 ? depois.toLowerCase() : null;
}

export function ConversaDaDemanda({
  demandaId,
  token,
  focar = false,
}: {
  demandaId: string;
  token: string | null;
  /** O "Conversar" do card da lista (issue #1578): a caixa abre em foco, já à vista. */
  focar?: boolean;
}) {
  const [mensagens, setMensagens] = useState<Mensagem[] | null>(null);
  const [mencionaveis, setMencionaveis] = useState<Mencionavel[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [texto, setTexto] = useState("");
  const [busca, setBusca] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [envio, setEnvio] = useState<Envio | null>(null);
  const [entendi, setEntendi] = useState<Entendi | null>(null);
  const [ocupado, setOcupado] = useState(false);
  // A ação que falhou, para o "Tente de novo" repetir a mesma.
  const [falhou, setFalhou] = useState<{ motivo: string; repetir: () => void } | null>(null);
  const caixa = useRef<HTMLTextAreaElement>(null);
  // O "Tente de novo" do interpretar repete uma função antiga: o contador vem daqui.
  const envioAgora = useRef<Envio | null>(envio);
  envioAgora.current = envio;

  useEffect(() => {
    if (!token) return;
    let viva = true;
    (async () => {
      try {
        const resposta = await fetch(urlDaConversaDaDemanda(demandaId), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!viva) return;
        if (!resposta.ok) {
          setErro(CONVERSA_FALHOU);
          return;
        }
        const corpo = (await resposta.json()) as { mensagens?: unknown; mencionaveis?: unknown; envio?: unknown };
        if (!viva) return;
        setMensagens(Array.isArray(corpo.mensagens) ? corpo.mensagens.filter(mensagemValida) : []);
        setMencionaveis(Array.isArray(corpo.mencionaveis) ? (corpo.mencionaveis as Mencionavel[]) : []);
        setEnvio(envioValido(corpo.envio) ? corpo.envio : null);
      } catch (e) {
        console.error("[admin/tecnologia] falha ao abrir a Conversa da Demanda", e);
        if (viva) setErro(FALHA_DE_CONEXAO);
      }
    })();
    return () => {
      viva = false;
    };
  }, [demandaId, token]);

  const carregou = mensagens !== null;
  useEffect(() => {
    if (!focar || !carregou) return;
    caixa.current?.scrollIntoView?.({ block: "center" });
    caixa.current?.focus();
  }, [focar, carregou]);

  function aoDigitar(valor: string, cursor: number) {
    setTexto(valor);
    setBusca(buscaDaMencao(valor, cursor));
  }

  function mencionar(nome: string) {
    const cursor = caixa.current?.selectionStart ?? texto.length;
    const antes = texto.slice(0, cursor);
    const arroba = antes.lastIndexOf("@");
    setTexto(`${texto.slice(0, arroba)}@${nome} ${texto.slice(cursor)}`);
    setBusca(null);
    caixa.current?.focus();
  }

  async function enviar() {
    const limpo = texto.trim();
    if (!limpo || !token || enviando) return;
    setEnviando(true);
    setErro(null);
    try {
      const resposta = await fetch(urlDaConversaDaDemanda(demandaId), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ texto: limpo }),
      });
      if (!resposta.ok) {
        setErro(await motivoDaRecusa(resposta));
        return;
      }
      const nova: unknown = await resposta.json();
      if (mensagemValida(nova)) setMensagens((atuais) => [...(atuais ?? []), nova]);
      // A mensagem de quem vê o botão é do lado do hospital: entra no próximo envio.
      setEnvio((atual) => (atual ? { mensagens_novas: atual.mensagens_novas + 1 } : atual));
      setTexto("");
      setBusca(null);
    } catch (e) {
      console.error("[admin/tecnologia] falha ao enviar a mensagem", e);
      setErro(FALHA_DE_CONEXAO);
    } finally {
      setEnviando(false);
    }
  }

  async function interpretar() {
    if (!token || ocupado) return;
    setOcupado(true);
    setFalhou(null);
    // A mensagem escrita depois deste pedido fica fora da interpretação.
    const cobertas = envioAgora.current?.mensagens_novas ?? 0;
    try {
      const resposta = await fetch(`${urlDaConversaDaDemanda(demandaId)}/interpretar`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resposta.ok) {
        setFalhou({ motivo: await motivoDaRecusa(resposta), repetir: interpretar });
        return;
      }
      const corpo: unknown = await resposta.json();
      if (entendiValido(corpo)) setEntendi({ ...corpo, cobertas });
    } catch (e) {
      console.error("[admin/tecnologia] falha ao interpretar o envio", e);
      setFalhou({ motivo: FALHA_DE_CONEXAO, repetir: interpretar });
    } finally {
      setOcupado(false);
    }
  }

  async function enviarAosDesenvolvedores(aprovado: Entendi) {
    if (!token || ocupado) return;
    const repetir = () => enviarAosDesenvolvedores(aprovado);
    setOcupado(true);
    setFalhou(null);
    try {
      const resposta = await fetch(`${urlDaConversaDaDemanda(demandaId)}/enviar`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ envio_id: aprovado.id }),
      });
      if (!resposta.ok) {
        setFalhou({ motivo: await motivoDaRecusa(resposta), repetir });
        return;
      }
      const linha: unknown = await resposta.json();
      if (mensagemValida(linha)) setMensagens((atuais) => [...(atuais ?? []), linha]);
      setEntendi(null);
      // A mensagem escrita com o "Entendi assim:" aberto não foi neste Ajuste: espera o próximo.
      setEnvio((atual) => ({
        mensagens_novas: Math.max(0, (atual?.mensagens_novas ?? 0) - (aprovado.cobertas ?? 0)),
      }));
    } catch (e) {
      console.error("[admin/tecnologia] falha ao enviar aos desenvolvedores", e);
      setFalhou({ motivo: FALHA_DE_CONEXAO, repetir });
    } finally {
      setOcupado(false);
    }
  }

  function corrigir() {
    setEntendi(null);
    setFalhou(null);
    caixa.current?.focus();
  }

  const sugestoes = busca === null ? [] : mencionaveis.filter((p) => p.nome.toLowerCase().includes(busca));

  return (
    <section
      aria-label="Conversa da Demanda"
      className="w-full bg-white rounded-2xl border border-border shadow-premium p-5 space-y-4"
    >
      <div>
        <h2 className="text-sm font-bold text-slate-900">Conversa da Demanda</h2>
        <p className="normal-case text-xs text-text-secondary">
          Para falar com quem cuida deste pedido. A IA só lê esta conversa no Enviar para os desenvolvedores, e o que
          sai do aplicativo é só o resumo que você aprovar.
        </p>
      </div>

      {mensagens === null && !erro && (
        <p role="status" className="flex items-center gap-2 text-xs text-text-secondary">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Carregando a conversa...
        </p>
      )}
      {mensagens !== null && mensagens.length === 0 && (
        <p className="normal-case text-sm text-text-secondary">Nenhuma mensagem ainda.</p>
      )}
      {mensagens !== null && mensagens.length > 0 && (
        <ul className="space-y-3">
          {mensagens.map((mensagem, i) => {
            const dia = trocaDeDia(mensagens, i);
            return (
              <Fragment key={mensagem.id}>
                {dia && (
                  <li>
                    <SeparadorDeDia dia={dia} />
                  </li>
                )}
                {perguntaValida(mensagem.pergunta) ? (
                  <li key={mensagem.id}>
                    <CartaoDaPergunta pergunta={mensagem.pergunta} />
                  </li>
                ) : mensagem.sistema ? (
                  <li key={mensagem.id} className="flex justify-center">
                    <p className="normal-case max-w-[90%] whitespace-pre-wrap rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-800">
                      {mensagem.texto}
                    </p>
                  </li>
                ) : (
                  <li key={mensagem.id} className={`flex ${mensagem.minha ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                        mensagem.minha ? "bg-primary/5 border border-primary/20" : "bg-slate-50 border border-slate-200"
                      }`}
                    >
                      <p className="flex flex-wrap items-baseline gap-2 text-xs text-text-secondary">
                        <span className="normal-case font-semibold text-slate-800">{mensagem.autor}</span>
                        <span className="normal-case">{quando(mensagem.criado_em)}</span>
                      </p>
                      <div className="text-slate-800">
                        <TextoDaMensagem texto={mensagem.texto} />
                      </div>
                    </div>
                  </li>
                )}
              </Fragment>
            );
          })}
        </ul>
      )}

      {entendi && (
        <div
          role="group"
          aria-label="Entendi assim:"
          className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 space-y-2"
        >
          <p className="text-sm font-semibold text-slate-900">Entendi assim:</p>
          <ul className="list-disc pl-5 space-y-1">
            {entendi.topicos.map((topico) => (
              <li key={topico} className="normal-case text-sm text-slate-800">
                {topico}
              </li>
            ))}
          </ul>
          {entendi.cards.length > 0 && (
            <ul className="space-y-1">
              {entendi.cards.map((card) => (
                <li key={card.numero} className="normal-case text-xs text-text-secondary">
                  Parte {card.numero}: {card.muda}
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => enviarAosDesenvolvedores(entendi)}
              disabled={ocupado}
              className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-40"
            >
              Enviar
            </button>
            <button
              type="button"
              onClick={corrigir}
              disabled={ocupado}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-800 disabled:opacity-40"
            >
              Corrigir
            </button>
          </div>
        </div>
      )}

      {falhou && (
        <div
          role="alert"
          className="normal-case px-3 py-2 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm space-y-2"
        >
          <p>{falhou.motivo}</p>
          <button type="button" onClick={falhou.repetir} disabled={ocupado} className="font-semibold underline">
            Tente de novo
          </button>
        </div>
      )}

      {erro && (
        <p role="alert" className="normal-case px-3 py-2 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
          {erro}
        </p>
      )}

      <div className="relative">
        <textarea
          ref={caixa}
          aria-label="Mensagem para a Conversa"
          rows={2}
          maxLength={LIMITE_DA_MENSAGEM}
          placeholder="Escreva uma mensagem. Use @ para chamar alguém pelo nome."
          value={texto}
          onChange={(e) => aoDigitar(e.target.value, e.target.selectionStart ?? e.target.value.length)}
          onKeyDown={(e) => {
            // Com a lista de nomes aberta, o Esc só a fecha: o painel do Quadro não fecha junto.
            if (e.key === "Escape" && busca !== null) {
              e.preventDefault();
              setBusca(null);
            }
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              enviar();
            }
          }}
          className="w-full px-3 py-2 pr-12 text-sm border border-slate-200 rounded-xl outline-none focus:border-primary focus:ring-1 focus:ring-primary bg-white resize-y"
        />
        <button
          type="button"
          aria-label="Enviar na Conversa"
          onClick={enviar}
          disabled={!texto.trim() || enviando}
          className="absolute right-2 bottom-3 w-8 h-8 rounded-lg bg-primary text-white flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {enviando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
        </button>
        {sugestoes.length > 0 && (
          <ul
            role="listbox"
            aria-label="Quem vê este pedido"
            className="absolute bottom-full left-0 mb-2 w-full max-h-48 overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-premium z-10"
          >
            {sugestoes.map((pessoa) => (
              <li
                key={pessoa.id}
                role="option"
                aria-selected={false}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => mencionar(pessoa.nome)}
                className="normal-case px-4 py-2 text-sm text-slate-800 cursor-pointer hover:bg-slate-50"
              >
                {pessoa.nome}
              </li>
            ))}
          </ul>
        )}
      </div>

      {envio && (
        <button
          type="button"
          onClick={interpretar}
          disabled={envio.mensagens_novas === 0 || ocupado || entendi !== null}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl border border-primary text-primary text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {ocupado && !entendi && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          Enviar para os desenvolvedores
        </button>
      )}
    </section>
  );
}
