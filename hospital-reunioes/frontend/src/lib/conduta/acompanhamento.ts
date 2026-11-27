/**
 * A página de acompanhamento do Canal de Conduta (issue #1845; especificação,
 * P7): a situação do caso, as mensagens do Comitê e o complemento.
 *
 * Como o relato, toda chamada sai sem login (`credentials: "omit"`), sem
 * cache e sem nada no endereço: protocolo, código e texto viajam só no corpo.
 * Protocolo ou código errado recebem a mesma resposta do servidor, e a tela
 * também não diz qual dos dois errou.
 */

export type SituacaoDoRelato =
  | "Recebido"
  | "Em análise"
  | "Em apuração"
  | "Aguardando sua resposta"
  | "Concluído"
  | "Encaminhado";

export interface MensagemDoAcompanhamento {
  de: "comite" | "voce";
  tipo: "pergunta" | "complemento" | "resposta_final";
  texto: string;
  em: string;
}

export interface Acompanhamento {
  protocolo: string;
  situacao: SituacaoDoRelato;
  mensagens: MensagemDoAcompanhamento[];
}

export const LIMITE_DO_COMPLEMENTO = 5000;

export const NAO_ENCONTRADO =
  "Não encontramos um relato com esse protocolo e esse código. Confira os dois e tente de novo.";

export class FalhaDoAcompanhamento extends Error {}

function chamar(caminho: string, corpo: unknown): Promise<Response> {
  return fetch(`/api/conduta${caminho}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
    credentials: "omit",
    cache: "no-store",
    referrerPolicy: "no-referrer",
  });
}

async function responder(chamada: Promise<Response>, falha: string): Promise<Acompanhamento> {
  let resposta: Response;
  try {
    resposta = await chamada;
  } catch {
    throw new FalhaDoAcompanhamento("Sem conexão. Tente de novo.");
  }
  if (resposta.status === 404) throw new FalhaDoAcompanhamento(NAO_ENCONTRADO);
  if (resposta.status === 429) {
    throw new FalhaDoAcompanhamento("Muitas tentativas deste aparelho em pouco tempo. Espere alguns minutos e tente de novo.");
  }
  if (!resposta.ok) {
    const corpo = (await resposta.json().catch(() => null)) as { detail?: unknown } | null;
    throw new FalhaDoAcompanhamento(typeof corpo?.detail === "string" ? corpo.detail : falha);
  }
  return (await resposta.json()) as Acompanhamento;
}

export function acompanhar(protocolo: string, codigo: string): Promise<Acompanhamento> {
  return responder(
    chamar("/acompanhamento", { protocolo: protocolo.trim(), codigo: codigo.trim() }),
    "Não deu para abrir o acompanhamento agora. Tente de novo."
  );
}

export function enviarComplemento(protocolo: string, codigo: string, texto: string): Promise<Acompanhamento> {
  return responder(
    chamar("/acompanhamento/complemento", { protocolo: protocolo.trim(), codigo: codigo.trim(), texto: texto.trim() }),
    "Não deu para enviar o complemento agora. Tente de novo."
  );
}

/** "2026-11-20T15:04:00+00:00" vira "20/11/2026", no fuso de São Paulo. */
export function diaDaMensagem(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
}
