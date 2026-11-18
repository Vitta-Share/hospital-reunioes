/**
 * O Documento do card (issue #1552, PRD #1548, ADR 0084, decisão 7), que
 * substituiu a seção "O que muda" de texto corrido (issue #676).
 *
 * Seções fixas: Em uma frase, O que muda (até cinco tópicos, o resto atrás do
 * "Ver tudo"), Partes (com a Etapa e a data de fechamento) e Datas (criado,
 * entregue, em produção). A Demonstração, num cartão próprio, só quando a
 * issue traz o link do vídeo (issue #1559). O texto vem do bloco "Para o diretor" da issue e do
 * de cada parte, lido do GitHub e guardado no cache da Demanda. Ninguém o
 * digita no app, e o app só o separa em seções, sem reescrever.
 *
 * Nada aqui é técnico para o diretor: título de fatia, link e nome de label
 * não aparecem (ADR 0054, decisão 9). O número da raiz e o de cada parte são
 * de todos, sem link, e as partes vêm agrupadas por Onda, com o "Espera a #N"
 * de cada bloqueadora aberta (issue #1902, ADR 0100). O link da issue aparece
 * só para o Desenvolvedor, porque só para ele o servidor o manda. O Número da
 * Demanda ("Demanda 42", issue #1585) é de todos e abre o topo.
 *
 * O texto é desenhado como TEXTO, com um Markdown simples de negrito e lista.
 * Nada vira HTML nem link: ele vem de fora do app, e um `dangerouslySetInnerHTML`
 * aqui transformaria o corpo de uma issue em elemento da nossa tela.
 *
 * Sem Vínculo não há documento: é o mesmo `temSelo` do card que decide, e não
 * uma segunda condição escrita aqui, que divergiria dele na primeira mudança.
 * A exceção é o pedido de um projeto novo da Vitta (issue #1967), que não sai
 * de Registrada e abre o documento com o nome do projeto e o link do plano.
 */

import { useEffect, useRef, useState } from "react";

import {
  BlocoDoTextoSimples,
  blocosDoTextoSimples,
  BloqueadoraDaParte,
  Demanda,
  diaDoHospital,
  diaEHoraDoHospital,
  documentoDoBloco,
  ETAPA_CLASSE,
  ETAPA_ROTULO,
  EtapaDemanda,
  linkDaDemonstracao,
  nomeDoNumero,
  ParteDaEntrega,
  PedacoForte,
  rotuloDoProjeto,
  temSelo,
} from "./demandas";

export const TITULO_DOCUMENTO = "Documento do card";
export const TITULO_EM_UMA_FRASE = "Em uma frase";
export const TITULO_O_QUE_MUDA = "O que muda";
export const TITULO_PARTES = "Partes";
export const TITULO_DATAS = "Datas";
export const TITULO_DEMONSTRACAO = "Demonstração";
export const ASSISTIR_A_DEMONSTRACAO = "Assistir à demonstração";
export const TITULO_PLANO_DO_PROJETO = "Plano do projeto";
export const ABRIR_O_PLANO = "Abrir o plano";
export const VER_TUDO = "Ver tudo";
export const COPIAR_LINK = "Copiar link";
export const LINK_COPIADO = "Link copiado";
export const NAO_COPIOU_O_LINK =
  "O navegador não liberou a cópia automática. O texto está na caixa abaixo, já selecionado: copie com Ctrl+C (ou Cmd+C).";

/** Quantos tópicos de O que muda aparecem antes do "Ver tudo" (ADR 0084). */
export const TOPICOS_VISIVEIS = 5;

/**
 * O que a tela diz no lugar do texto que ainda não existe.
 *
 * A mesma frase para a raiz e para a parte: as duas ausências significam a
 * mesma coisa para quem lê, e mostrar o corpo técnico da issue no lugar dela é
 * exatamente o que a decisão 7 proíbe.
 */
export const SEM_O_QUE_MUDA = "Descrição em preparação";

function Pedacos({ linha }: { linha: PedacoForte[] }) {
  return (
    <>
      {linha.map((pedaco, i) =>
        pedaco.forte ? (
          <strong key={i} className="font-semibold text-text">
            {pedaco.texto}
          </strong>
        ) : (
          <span key={i}>{pedaco.texto}</span>
        ),
      )}
    </>
  );
}

function Bloco({ bloco }: { bloco: BlocoDoTextoSimples }) {
  if (bloco.lista) {
    return (
      <ul className="list-disc pl-5 space-y-0.5">
        {bloco.linhas.map((linha, i) => (
          <li key={i}>
            <Pedacos linha={linha} />
          </li>
        ))}
      </ul>
    );
  }
  return (
    <>
      {bloco.linhas.map((linha, i) => (
        <p key={i}>
          <Pedacos linha={linha} />
        </p>
      ))}
    </>
  );
}

function TextoSimples({ texto }: { texto: string | null }) {
  const blocos = blocosDoTextoSimples(texto);
  if (blocos.length === 0) {
    return <p className="text-text-secondary italic">{SEM_O_QUE_MUDA}</p>;
  }
  return (
    <div className="space-y-2">
      {blocos.map((bloco, i) => (
        <Bloco key={i} bloco={bloco} />
      ))}
    </div>
  );
}

function SeloDaSituacao({ situacao }: { situacao: EtapaDemanda | null }) {
  const rotulo = situacao ? ETAPA_ROTULO[situacao as EtapaDemanda] : undefined;
  if (!rotulo) return null;

  return (
    <span
      className={`shrink-0 px-2 py-0.5 rounded text-xs font-medium ${ETAPA_CLASSE[situacao as EtapaDemanda]}`}
    >
      {rotulo}
    </span>
  );
}

/** O nome da Onda como a tela o escreve (issue #1902, ADR 0100, decisão 3). */
export function nomeDaOnda(onda: number): string {
  return `Onda ${onda}`;
}

/** A linha de uma bloqueadora aberta (ADR 0100, decisão 2). */
export function esperaA(bloqueadora: BloqueadoraDaParte): string {
  return bloqueadora.de_outro_pedido
    ? `Espera a #${bloqueadora.numero}, de outro pedido`
    : `Espera a #${bloqueadora.numero}`;
}

/**
 * As partes em grupos por Onda, da 1 em diante, cada grupo na ordem em que as
 * partes vieram. A linha de antes da issue #1902 não tem Onda e fica na 1.
 */
function partesPorOnda(partes: ParteDaEntrega[]): [number, ParteDaEntrega[]][] {
  const grupos = new Map<number, ParteDaEntrega[]>();
  for (const parte of partes) {
    const onda = parte.onda ?? 1;
    grupos.set(onda, [...(grupos.get(onda) ?? []), parte]);
  }
  return [...grupos.entries()].sort(([a], [b]) => a - b);
}

function Parte({ parte }: { parte: ParteDaEntrega }) {
  const fechou = diaDoHospital(parte.fechada_em);
  const bloqueadoras = parte.bloqueadoras ?? [];
  return (
    <li className="flex items-start gap-2">
      <SeloDaSituacao situacao={parte.situacao} />
      {/* O número sem link (ADR 0100, decisão 1): o diretor cita a parte, mas não entra no GitHub. */}
      {parte.numero ? (
        <span className="shrink-0 text-xs font-semibold text-text pt-0.5">#{parte.numero}</span>
      ) : null}
      {fechou && <span className="shrink-0 text-xs text-text-secondary pt-0.5">em {fechou}</span>}
      <div className="min-w-0 flex-1 space-y-1">
        <TextoSimples texto={parte.o_que_muda} />
        {bloqueadoras.map((b) => (
          <p key={b.numero} className="text-xs text-amber-800">
            {esperaA(b)}
          </p>
        ))}
      </div>
    </li>
  );
}

function Titulo({ children }: { children: string }) {
  return <h3 className="text-xs font-medium text-text-secondary uppercase">{children}</h3>;
}

/** O link da issue, só para o Desenvolvedor e só se apontar para o GitHub. */
function LinkDaIssue({ demanda }: { demanda: Demanda }) {
  const url = demanda.issue_url;
  if (!demanda.issue_numero || !url || !url.startsWith("https://github.com/")) return null;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold text-primary underline">
      #{demanda.issue_numero}
    </a>
  );
}

/**
 * O número da raiz ao lado do Número da Demanda: o link para o Desenvolvedor
 * e, para quem não tem o link, só o número (issue #1902, ADR 0100, decisão 1).
 */
function NumeroDaRaiz({ demanda }: { demanda: Demanda }) {
  const link = <LinkDaIssue demanda={demanda} />;
  if (demanda.issue_numero && demanda.issue_url?.startsWith("https://github.com/")) return link;
  if (!demanda.raiz_numero) return null;
  return <span className="text-xs font-semibold text-text">#{demanda.raiz_numero}</span>;
}

/**
 * O topo do Documento (issue #1585): o Número da Demanda para todos e, ao
 * lado, o `#<issue>`: link para o Desenvolvedor, número para os demais.
 */
function Topo({ demanda }: { demanda: Demanda }) {
  const nome = nomeDoNumero(demanda);
  const issue = <NumeroDaRaiz demanda={demanda} />;
  if (!nome) return issue;
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-semibold text-text">{nome}</span>
      {issue}
    </div>
  );
}

/**
 * O texto que o Copiar link põe na área de transferência (issue #1588): o
 * Número e o título numa linha, o endereço que abre a Demanda na outra. É o
 * mesmo `?demanda=<id>` do sino, que a página já sabe abrir.
 */
function textoDoLink(demanda: Demanda): string {
  const nome = nomeDoNumero(demanda);
  const titulo = nome ? `${nome}: ${demanda.titulo}` : demanda.titulo;
  return `${titulo}\n${window.location.origin}/admin/tecnologia?demanda=${encodeURIComponent(demanda.id)}`;
}

/**
 * O Copiar link (issue #1588), no padrão de copiar de Contas médicas: o aviso
 * quando copia e, se o navegador recusa, o texto numa caixa já selecionada.
 * A linha aberta das Entregas usa o mesmo (issue #1703).
 */
export function CopiarLink({ demanda }: { demanda: Demanda }) {
  const [copiou, setCopiou] = useState(false);
  const [paraPegarAMao, setParaPegarAMao] = useState<string | null>(null);
  const caixa = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (paraPegarAMao) caixa.current?.select();
  }, [paraPegarAMao]);

  async function copiar() {
    const texto = textoDoLink(demanda);
    setCopiou(false);
    setParaPegarAMao(null);
    try {
      await navigator.clipboard.writeText(texto);
      setCopiou(true);
    } catch (e) {
      console.error("[tecnologia] o navegador não copiou o link", e);
      setParaPegarAMao(texto);
    }
  }

  return (
    <div className="space-y-1">
      <button type="button" onClick={copiar} className="text-xs font-semibold text-primary underline">
        {COPIAR_LINK}
      </button>
      {copiou && (
        <p role="status" className="text-xs text-emerald-700">
          {LINK_COPIADO}
        </p>
      )}
      {paraPegarAMao && (
        <>
          <p role="status" className="text-xs text-amber-800">
            {NAO_COPIOU_O_LINK}
          </p>
          <textarea
            ref={caixa}
            readOnly
            value={paraPegarAMao}
            rows={2}
            aria-label="Link da Demanda"
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-xs text-slate-800"
          />
        </>
      )}
    </div>
  );
}

/**
 * O topo e o Copiar link juntos, o cabeçalho de toda Demanda aberta: o do
 * Documento do card e o do chat, quando a Demanda abre nele (a conversa
 * Registrada do autor e o card em revisão, issue #1669).
 */
export function CabecalhoDaDemanda({ demanda }: { demanda: Demanda }) {
  return (
    <>
      <Topo demanda={demanda} />
      <CopiarLink demanda={demanda} />
    </>
  );
}

function Topicos({ topicos }: { topicos: PedacoForte[][] }) {
  const [tudo, setTudo] = useState(false);
  const visiveis = tudo ? topicos : topicos.slice(0, TOPICOS_VISIVEIS);
  return (
    <>
      <Titulo>{TITULO_O_QUE_MUDA}</Titulo>
      <ul className="list-disc pl-5 space-y-0.5 text-sm text-text">
        {visiveis.map((linha, i) => (
          <li key={i}>
            <Pedacos linha={linha} />
          </li>
        ))}
      </ul>
      {!tudo && topicos.length > TOPICOS_VISIVEIS && (
        <button type="button" onClick={() => setTudo(true)} className="text-xs font-semibold text-primary underline">
          {VER_TUDO}
        </button>
      )}
    </>
  );
}

/**
 * O vídeo de demonstração da entrega, num cartão próprio (issue #1559). Só com
 * link `https`: o link vem do corpo da issue, de fora do app.
 */
function Demonstracao({ demanda }: { demanda: Demanda }) {
  const url = linkDaDemonstracao(demanda);
  if (!url) return null;
  const dia = diaDoHospital(demanda.demonstracao_em);
  return (
    <section
      aria-label={TITULO_DEMONSTRACAO}
      className="px-3 py-2 rounded-lg bg-white border border-violet-200 space-y-1"
    >
      <Titulo>{TITULO_DEMONSTRACAO}</Titulo>
      <a href={url} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-primary underline">
        {ASSISTIR_A_DEMONSTRACAO}
      </a>
      {dia && <p className="text-xs text-text-secondary">Adicionada em {dia}</p>}
    </section>
  );
}

/**
 * O pedido de um projeto novo da Vitta (issue #1967): o nome do projeto e o
 * link do plano, para todos que veem a Demanda. O app não lê o repositório
 * desse projeto, e o link é o que a ponte gravou. Só com link `https`.
 */
function PlanoDoProjeto({ demanda }: { demanda: Demanda }) {
  const url = demanda.raiz_url;
  if (!url || !demanda.projeto) return null;
  return (
    <section
      aria-label={TITULO_PLANO_DO_PROJETO}
      className="px-3 py-2 rounded-lg bg-white border border-slate-200 space-y-1"
    >
      <Titulo>{TITULO_PLANO_DO_PROJETO}</Titulo>
      <p className="text-sm text-text">{rotuloDoProjeto(demanda.projeto, demanda.projeto_nome)}</p>
      {url.startsWith("https://") && (
        <a href={url} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-primary underline">
          {ABRIR_O_PLANO}
        </a>
      )}
    </section>
  );
}

/**
 * Em uma frase e O que muda, lidos do bloco "Para o diretor". É a parte do
 * documento que o planejamento monta ao vivo ao lado do chat (issue #1553):
 * o mesmo componente nos dois lugares, para o rascunho e o card não divergirem.
 * `chave` recolhe o "Ver tudo" ao trocar de card.
 */
export function FraseEOQueMuda({ texto, chave }: { texto: string | null | undefined; chave: string }) {
  const bloco = documentoDoBloco(texto);
  return (
    <>
      {/* Sem bloco, a frase de preparação no lugar da frase; o bloco só de
          tópicos não tem frase a mostrar, e a seção some. */}
      {(!bloco || bloco.frase.length > 0) && (
        <>
          <Titulo>{TITULO_EM_UMA_FRASE}</Titulo>
          <div className="text-sm text-text">
            {bloco ? (
              bloco.frase.map((linha, i) => (
                <p key={i}>
                  <Pedacos linha={linha} />
                </p>
              ))
            ) : (
              <p className="text-text-secondary italic">{SEM_O_QUE_MUDA}</p>
            )}
          </div>
        </>
      )}

      {bloco && bloco.topicos.length > 0 && <Topicos key={chave} topicos={bloco.topicos} />}
    </>
  );
}

export function DocumentoDoCard({ demanda }: { demanda: Demanda }) {
  // O pedido de um projeto novo (issue #1967) fica Registrado para sempre: o
  // app não lê o repositório dele. O documento abre só com o plano.
  const soOPlano = !temSelo(demanda);
  if (soOPlano && !demanda.raiz_url) return null;

  const partes = demanda.partes ?? [];
  const datas = [
    ["Criado em", diaEHoraDoHospital(demanda.criado_em)],
    ["Entregue em", diaEHoraDoHospital(demanda.fechada_em)],
    ["Em produção em", diaEHoraDoHospital(demanda.em_producao_em)],
  ].filter((par): par is [string, string] => par[1] !== null);

  return (
    <section
      aria-label={TITULO_DOCUMENTO}
      className="md:col-span-2 px-4 py-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2"
    >
      <CabecalhoDaDemanda demanda={demanda} />

      <PlanoDoProjeto demanda={demanda} />

      {!soOPlano && <FraseEOQueMuda texto={demanda.o_que_muda} chave={demanda.id} />}

      <Demonstracao demanda={demanda} />

      {partes.length > 0 && (
        <>
          <Titulo>{TITULO_PARTES}</Titulo>
          <div className="space-y-3">
            {partesPorOnda(partes).map(([onda, daOnda]) => (
              <div key={onda} className="space-y-1">
                <h4 className="text-xs font-semibold text-text">{nomeDaOnda(onda)}</h4>
                <ul className="space-y-2 text-sm text-text">
                  {daOnda.map((parte, i) => (
                    // Pela posição: as Entregas mandam a parte sem número, e a
                    // lista é redesenhada inteira a cada sincronização.
                    <Parte key={i} parte={parte} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </>
      )}

      {datas.length > 0 && (
        <>
          <Titulo>{TITULO_DATAS}</Titulo>
          <ul className="space-y-0.5 text-sm text-text">
            {datas.map(([rotulo, dia]) => (
              <li key={rotulo}>
                {rotulo} {dia}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
