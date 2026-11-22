"use client";

/**
 * O texto da mensagem da Conversa da Demanda (issue #2117, PRD #2112, ADR 0109,
 * decisão 9).
 *
 * A bolha deixa de ser texto puro: negrito, lista e link saem da marcação
 * simples que a pessoa escreve. HTML não entra: o `react-markdown` sem
 * `rehype-raw` mostra a tag digitada como texto, e o `urlTransform` padrão
 * tira o `javascript:` do link. Só as peças da lista abaixo são desenhadas; o
 * resto (título, itálico, código, imagem) vira o texto de dentro, para a
 * conversa não ganhar letra que a casa não usa.
 *
 * A mensagem antiga foi escrita como texto puro: o `remark-breaks` guarda a
 * quebra simples de linha, como o `whitespace-pre-wrap` de antes.
 */

import ReactMarkdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";

const PECAS = ["p", "br", "strong", "ul", "ol", "li", "a"];

const componentes: Components = {
  p: ({ children }) => <p className="normal-case mb-1 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  ul: ({ children }) => <ul className="normal-case list-disc pl-5 my-1 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="normal-case list-decimal pl-5 my-1 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  a: ({ children, href }) => (
    <a href={href} className="text-primary underline break-all" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

export function TextoDaMensagem({ texto }: { texto: string }) {
  return (
    <div className="break-words">
      <ReactMarkdown
        remarkPlugins={[remarkBreaks]}
        components={componentes}
        allowedElements={PECAS}
        unwrapDisallowed
      >
        {texto}
      </ReactMarkdown>
    </div>
  );
}
