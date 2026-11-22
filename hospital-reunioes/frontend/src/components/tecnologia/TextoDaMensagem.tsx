"use client";

/**
 * O texto da mensagem da Conversa da Demanda (issue #2117, PRD #2112, ADR 0109,
 * decisão 9).
 *
 * A bolha deixa de ser texto puro: negrito, lista e link saem da marcação
 * simples que a pessoa escreve. HTML não entra: o `react-markdown` sem
 * `rehype-raw` mostra a tag digitada como texto, e o `urlTransform` padrão
 * tira o `javascript:` do link. Só as peças da lista abaixo são desenhadas; o
 * resto (título, itálico, código na linha, imagem) vira o texto de dentro, para a
 * conversa não ganhar letra que a casa não usa.
 *
 * A mensagem antiga foi escrita como texto puro: o `remark-breaks` guarda a
 * quebra simples de linha, como o `whitespace-pre-wrap` de antes. O bloco de
 * código (log colado, o que a ponte do terminal escreve) não passa pelo
 * `remark-breaks`: ele sai numa caixa com `whitespace-pre-wrap`, na mesma
 * letra do resto. A linha de traços (o título sublinhado e o separador) volta
 * a ser o texto que a pessoa digitou, senão o traço sumiria da tela.
 */

import ReactMarkdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";

const PECAS = ["p", "br", "strong", "ul", "ol", "li", "a", "pre", "code"];

type No = {
  type: string;
  position?: { start: { offset?: number }; end: { offset?: number } };
  children?: No[];
};

/** O título sublinhado e a linha de traços voltam a ser o texto digitado. */
function tracoComoTexto() {
  return (arvore: No, arquivo: { value: unknown }) => {
    const fonte = String(arquivo.value);
    const trocar = (no: No) => {
      no.children = no.children?.map((filho) => {
        const inicio = filho.position?.start.offset;
        const fim = filho.position?.end.offset;
        const digitado = inicio !== undefined && fim !== undefined ? fonte.slice(inicio, fim) : undefined;
        const sublinhado = filho.type === "heading" && digitado !== undefined && !digitado.startsWith("#");
        if (digitado !== undefined && (sublinhado || filho.type === "thematicBreak")) {
          return { type: "paragraph", children: [{ type: "text", value: digitado } as No] };
        }
        trocar(filho);
        return filho;
      });
    };
    trocar(arvore);
  };
}

const componentes: Components = {
  p: ({ children }) => <p className="normal-case mb-1 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  ul: ({ children }) => <ul className="normal-case list-disc pl-5 my-1 space-y-0.5">{children}</ul>,
  ol: ({ children, start }) => <ol start={start} className="normal-case list-decimal pl-5 my-1 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  pre: ({ children }) => <div className="normal-case whitespace-pre-wrap my-1">{children}</div>,
  code: ({ children }) => <>{children}</>,
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
        remarkPlugins={[tracoComoTexto, remarkBreaks]}
        components={componentes}
        allowedElements={PECAS}
        unwrapDisallowed
      >
        {texto}
      </ReactMarkdown>
    </div>
  );
}
