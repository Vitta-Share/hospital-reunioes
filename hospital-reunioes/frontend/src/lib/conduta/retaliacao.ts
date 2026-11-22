/**
 * A verificação de retaliação do caso concluído (issue #1839; especificação,
 * 6.11): os tipos que a API devolve na tela do caso. O servidor decide o que
 * vale e quem pode.
 */

export type Marco = 30 | 90 | 180;

export interface MarcoDaVerificacao {
  marco: Marco;
  /** O dia da verificação, "2026-12-20". */
  data: string;
  situacao: "aguardando" | "pendente" | "verificada";
  houve: boolean | null;
  observacao: string | null;
  verificada_por: string | null;
  verificada_em: string | null;
  caso_novo: { id: string; protocolo: string } | null;
  pode_abrir_caso_novo: boolean;
}

export interface VerificacaoDeRetaliacao {
  marcos: MarcoDaVerificacao[];
  /** A verificação que a coordenação registra agora: a mais antiga que chegou. */
  marco_pendente: Marco | null;
  pode_registrar: boolean;
}
