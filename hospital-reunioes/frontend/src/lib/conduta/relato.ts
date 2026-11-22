/**
 * O relato em passos da página pública do Canal de Conduta (issue #1843,
 * especificação seção 4, regras C1, C2 e C6).
 *
 * Toda chamada daqui sai sem login: sem o cabeçalho de sessão do app e com
 * `credentials: "omit"`, para nem o cookie de quem esqueceu o app aberto no
 * mesmo navegador ir junto. Nada vai no endereço: protocolo, código e texto
 * viajam só no corpo, e a resposta não fica em cache.
 */

export const LIMITE_DO_RELATO = 10_000;

export type Identificacao = "anonimo" | "identificado";
export type SimNaoNaoSei = "sim" | "nao" | "nao_sei";
export type Posicao = "sofreu" | "presenciou" | "ficou_sabendo";
export type Assunto = "A" | "B" | "C" | "D" | "E" | "F";

export const AVISOS_DO_PASSO_1 = ["aviso_p1_anonimato", "aviso_p1_protocolo", "aviso_p1_boa_fe"] as const;
export type AvisoDoPasso1 = (typeof AVISOS_DO_PASSO_1)[number];

/** O texto da especificação, mostrado enquanto a coordenação não salva o dela
 * nas Configurações. A versão gravada, nesse caso, é nula. */
export const AVISOS_PADRAO: Record<AvisoDoPasso1, string> = {
  aviso_p1_anonimato: "Você pode relatar sem se identificar.",
  aviso_p1_protocolo:
    "Guarde o protocolo e o código que vai receber. O hospital não consegue recuperá-los, e é só por esta página que o Comitê fala com você.",
  aviso_p1_boa_fe:
    "Relato equivocado, feito de boa-fé, não gera nenhuma consequência. Acusação que a pessoa sabe ser falsa, feita para prejudicar alguém, é falta grave e pode ser crime contra a honra.",
};

/** A linha sobre a IA do passo 1, com o que o diretor decidiu: até 30 dias, sem treino. */
export const LINHA_DA_IA =
  "Usamos inteligência artificial para organizar o relato. Nenhuma decisão é tomada por IA. O serviço de IA guarda o texto por até 30 dias e não o usa para treinar a IA.";

export const ASSUNTOS: { codigo: Assunto; nome: string; exemplos: string }[] = [
  { codigo: "A", nome: "Conduta e relações", exemplos: "Assédio moral, assédio sexual, discriminação, violência, retaliação" },
  { codigo: "B", nome: "Patrimônio", exemplos: "Furto, desvio de material, desvio de medicamento controlado" },
  {
    codigo: "C",
    nome: "Integridade nos negócios",
    exemplos: "Propina, comissão de fornecedor, conflito de interesse, irregularidade em compra, fraude de faturamento",
  },
  {
    codigo: "D",
    nome: "Registros e informação",
    exemplos: "Falsificação de ponto, escala ou prontuário, acesso indevido a dados, vazamento",
  },
  {
    codigo: "E",
    nome: "Segurança e conformidade",
    exemplos: "Descumprimento de norma de segurança, exercício profissional irregular, risco assistencial ocultado",
  },
  { codigo: "F", nome: "Não sei classificar", exemplos: "" },
];

export interface TextoVigente {
  texto: string;
  versao: number;
}

export interface Rascunho {
  ciente: boolean;
  versoes: Record<AvisoDoPasso1, number | null>;
  identificacao: Identificacao | null;
  nome: string;
  assunto: Assunto | null;
  direcao: SimNaoNaoSei | null;
  posicao: Posicao | null;
  relato: string;
  quando: string;
  ainda_acontece: boolean;
  onde: string;
  quem: string;
  testemunhas: string;
  lideranca_sabe: SimNaoNaoSei | null;
  o_que_foi_feito: string;
  evidencias: string;
}

export const RASCUNHO_VAZIO: Rascunho = {
  ciente: false,
  versoes: { aviso_p1_anonimato: null, aviso_p1_protocolo: null, aviso_p1_boa_fe: null },
  identificacao: null,
  nome: "",
  assunto: null,
  direcao: null,
  posicao: null,
  relato: "",
  quando: "",
  ainda_acontece: false,
  onde: "",
  quem: "",
  testemunhas: "",
  lideranca_sabe: null,
  o_que_foi_feito: "",
  evidencias: "",
};

export interface Protocolo {
  protocolo: string;
  codigo: string;
  voltar_a_partir_de: string;
}

/** A chamada sem login. Nenhum dado no endereço; tudo no corpo. */
function chamar(caminho: string, corpo?: unknown): Promise<Response> {
  return fetch(`/api/conduta${caminho}`, {
    method: corpo === undefined ? "GET" : "POST",
    headers: corpo === undefined ? undefined : { "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
    credentials: "omit",
    cache: "no-store",
    referrerPolicy: "no-referrer",
  });
}

/** Os avisos vigentes do passo 1. Sem resposta, vale o texto padrão. */
export async function lerAvisos(): Promise<Partial<Record<AvisoDoPasso1, TextoVigente>>> {
  try {
    const resposta = await chamar("/textos");
    if (!resposta.ok) return {};
    const { textos } = (await resposta.json()) as { textos: Record<string, TextoVigente | null> };
    const avisos: Partial<Record<AvisoDoPasso1, TextoVigente>> = {};
    for (const chave of AVISOS_DO_PASSO_1) {
      const vigente = textos?.[chave];
      if (vigente) avisos[chave] = { texto: vigente.texto, versao: vigente.versao };
    }
    return avisos;
  } catch {
    return {};
  }
}

/** O corpo do envio: só o que a pessoa preencheu, sem o nome no anônimo. */
export function corpoDoEnvio(r: Rascunho) {
  const opcional = (texto: string) => (texto.trim() ? texto.trim() : null);
  return {
    ciencia: { ciente: r.ciente, versoes: r.versoes },
    identificacao: r.identificacao,
    nome: r.identificacao === "identificado" ? opcional(r.nome) : null,
    assunto: r.assunto,
    direcao: r.direcao,
    posicao: r.posicao,
    relato: r.relato.trim(),
    quando: opcional(r.quando),
    ainda_acontece: r.ainda_acontece,
    onde: opcional(r.onde),
    quem: opcional(r.quem),
    testemunhas: opcional(r.testemunhas),
    lideranca_sabe: r.lideranca_sabe,
    o_que_foi_feito: r.lideranca_sabe === "sim" ? opcional(r.o_que_foi_feito) : null,
    evidencias: opcional(r.evidencias),
  };
}

export class FalhaDoEnvio extends Error {}

export async function enviarRelato(r: Rascunho): Promise<Protocolo> {
  let resposta: Response;
  try {
    resposta = await chamar("/relatos", corpoDoEnvio(r));
  } catch {
    throw new FalhaDoEnvio("Sem conexão. Nada foi enviado. Tente de novo.");
  }
  if (resposta.status === 429) {
    throw new FalhaDoEnvio("Muitos envios deste aparelho em pouco tempo. Espere alguns minutos e tente de novo.");
  }
  if (!resposta.ok) {
    const corpo = (await resposta.json().catch(() => null)) as { detail?: unknown } | null;
    const motivo = typeof corpo?.detail === "string" ? corpo.detail : null;
    throw new FalhaDoEnvio(motivo ?? "Não deu para registrar o relato agora. Nada foi gravado. Tente de novo.");
  }
  return (await resposta.json()) as Protocolo;
}

/** A pergunta opcional do P6. Falhar aqui não atrapalha nada. */
export async function enviarConfianca(protocolo: Protocolo, nota: number): Promise<boolean> {
  try {
    const resposta = await chamar("/relatos/confianca", { protocolo: protocolo.protocolo, codigo: protocolo.codigo, nota });
    return resposta.ok;
  } catch {
    return false;
  }
}

/** "2026-11-27" vira "27/11/2026", sem passar por fuso. */
export function dataLegivel(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}
