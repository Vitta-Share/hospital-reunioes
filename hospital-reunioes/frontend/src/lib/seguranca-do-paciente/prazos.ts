/**
 * Os prazos do caso e a tabela de prazos do Núcleo (issue #1993, PRD #1979):
 * os tipos que a API devolve e o formato da data e hora. Quem calcula e quem
 * recusa é o servidor.
 */

export interface PrazoDoCaso {
  marco: string;
  rotulo: string;
  tipo: "legal" | "interno" | string;
  valor: number;
  unidade: string;
  vence_em: string;
}

export interface NotificacaoExterna {
  sistema: string;
  rotulo: string;
  prazo_legal: string;
  estado: string;
}

export interface CelulaInterna {
  faixa: string;
  marco: string;
  rotulo: string;
  valor: number | null;
  unidade: string | null;
  editavel: boolean;
}

export interface LinhaLegal {
  marco: string;
  rotulo: string;
  celulas: Record<string, string>;
  editavel: false;
}

export interface Valor {
  valor: number | null;
  unidade: string | null;
}

export interface RegistroDoHistorico {
  faixa: string;
  marco: string;
  rotulo: string;
  de: Valor;
  para: Valor;
  quem: string | null;
  quando: string;
}

export interface TabelaDePrazos {
  faixas: string[];
  unidades: { valor: string; rotulo: string }[];
  internos: CelulaInterna[];
  legais: LinhaLegal[];
  historico: RegistroDoHistorico[];
  pode_editar: boolean;
}

/** A data e a hora no relógio do hospital, sempre absolutas: "10/11/2026, 14:00". */
export function formatarDataHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const UNIDADES: Record<string, [string, string]> = {
  horas_corridas: ["hora corrida", "horas corridas"],
  horas_uteis: ["hora útil", "horas úteis"],
  dias_corridos: ["dia corrido", "dias corridos"],
  dias_uteis: ["dia útil", "dias úteis"],
};

/** "4 horas úteis", "1 dia útil", ou "Sem prazo próprio". */
export function descreverPrazo({ valor, unidade }: Valor): string {
  if (valor === null || unidade === null) return "Sem prazo próprio";
  const [um, varios] = UNIDADES[unidade] ?? [unidade, unidade];
  return `${valor} ${valor === 1 ? um : varios}`;
}
