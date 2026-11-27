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

/** Os textos das Configurações que a tela do relato lê: os avisos do passo 1
 * e os contatos que o aviso da revisão mostra (issue #1848). */
export const TEXTOS_DA_TELA = [...AVISOS_DO_PASSO_1, "contato_dp", "orientacao_nsp"] as const;
export type TextoDaTela = (typeof TEXTOS_DA_TELA)[number];

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
export async function lerAvisos(): Promise<Partial<Record<TextoDaTela, TextoVigente>>> {
  try {
    const resposta = await chamar("/textos");
    if (!resposta.ok) return {};
    const { textos } = (await resposta.json()) as { textos: Record<string, TextoVigente | null> };
    const avisos: Partial<Record<TextoDaTela, TextoVigente>> = {};
    for (const chave of TEXTOS_DA_TELA) {
      const vigente = textos?.[chave];
      if (vigente) avisos[chave] = { texto: vigente.texto, versao: vigente.versao };
    }
    return avisos;
  } catch {
    return {};
  }
}

/** Para onde o aviso da revisão (P5) manda a pessoa, quando o assunto parece
 * de fora do canal (issue #1848, seção 4.1 da especificação). */
export type DestinoDoAviso = "DP" | "OUVIDORIA" | "NSP" | "GESTAO";

/** Os textos do aviso são fixos, por destino: o agente não escreve nada para
 * a página pública. */
export const TEXTOS_DO_AVISO: Record<DestinoDoAviso, string> = {
  DP: "Pelo que você escreveu, este assunto é do Departamento Pessoal. O Canal de Conduta não resolve esse tipo de questão.",
  OUVIDORIA:
    "Pelo que você escreveu, este assunto é da Ouvidoria. O Canal de Conduta não trata de atendimento a pacientes.",
  NSP: "Pelo que você escreveu, este é um assunto de segurança do paciente.",
  GESTAO: "Pelo que você escreveu, este assunto é tratado com a sua liderança ou com o DP.",
};

/** A leitura do agente ao abrir a revisão: o destino do aviso, ou nada. Com
 * falha, teto ou agente fora do ar, nada, e o envio segue normal. */
export async function lerAvisoDaRevisao(relato: string): Promise<DestinoDoAviso | null> {
  try {
    const resposta = await chamar("/relatos/aviso", { relato });
    if (!resposta.ok) return null;
    const { aviso } = (await resposta.json()) as { aviso?: unknown };
    return typeof aviso === "string" && aviso in TEXTOS_DO_AVISO ? (aviso as DestinoDoAviso) : null;
  } catch {
    return null;
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

// ── Os anexos do passo 4 (issue #1844) ─────────────────────────────────────

export const AVISO_DOS_ANEXOS = "Os dados de origem do arquivo são apagados automaticamente.";
export const MAXIMO_DE_ANEXOS = 10;
export const RECUSA_DO_FORMATO =
  "Este arquivo não pode ser anexado. O canal aceita foto (JPG, PNG ou WEBP), PDF e áudio (MP3, M4A, OGG ou WAV).";

const MB = 1024 * 1024;
type TipoDeAnexo = "imagem" | "pdf" | "audio";
const TIPOS_POR_EXTENSAO: Record<string, TipoDeAnexo> = {
  jpg: "imagem",
  jpeg: "imagem",
  png: "imagem",
  webp: "imagem",
  pdf: "pdf",
  mp3: "audio",
  m4a: "audio",
  ogg: "audio",
  oga: "audio",
  opus: "audio",
  wav: "audio",
};
const LIMITES: Record<TipoDeAnexo, { bytes: number; recusa: string }> = {
  imagem: { bytes: 20 * MB, recusa: "A imagem passa de 20 MB." },
  pdf: { bytes: 20 * MB, recusa: "O PDF passa de 20 MB." },
  audio: { bytes: 50 * MB, recusa: "O áudio passa de 50 MB." },
};

/** O que o seletor de arquivo do celular mostra. O servidor confere de novo, pelo conteúdo. */
export const ACEITOS = Object.keys(TIPOS_POR_EXTENSAO)
  .map((extensao) => `.${extensao}`)
  .join(",");

/** O motivo de recusa do arquivo, ou nulo se ele pode ir. */
export function conferirAnexo(arquivo: File): string | null {
  const extensao = /\.([^.]+)$/.exec(arquivo.name)?.[1]?.toLowerCase() ?? "";
  const tipo = TIPOS_POR_EXTENSAO[extensao];
  if (!tipo) return RECUSA_DO_FORMATO;
  if (arquivo.size > LIMITES[tipo].bytes) return LIMITES[tipo].recusa;
  return null;
}

/** Um anexo do relato já registrado, com o protocolo e o código que a tela
 * ainda tem na memória. O nome do arquivo não sai do aparelho. Devolve nulo
 * quando o anexo foi guardado, ou o motivo da recusa. O complemento do
 * acompanhamento usa a mesma rota, com origem "complemento" (issue #2187). */
export async function enviarAnexo(
  protocolo: Pick<Protocolo, "protocolo" | "codigo">,
  arquivo: File,
  origem: "relato" | "complemento" = "relato"
): Promise<string | null> {
  const formulario = new FormData();
  formulario.append("protocolo", protocolo.protocolo);
  formulario.append("codigo", protocolo.codigo);
  formulario.append("origem", origem);
  formulario.append("arquivo", arquivo, "anexo");
  let resposta: Response;
  try {
    resposta = await fetch("/api/conduta/relatos/anexos", {
      method: "POST",
      body: formulario,
      credentials: "omit",
      cache: "no-store",
      referrerPolicy: "no-referrer",
    });
  } catch {
    return "Sem conexão. O anexo não foi enviado.";
  }
  if (resposta.ok) return null;
  if (resposta.status === 429) return "Muitos envios deste aparelho em pouco tempo. O anexo não foi enviado.";
  const corpo = (await resposta.json().catch(() => null)) as { detail?: unknown } | null;
  return typeof corpo?.detail === "string" ? corpo.detail : "Não deu para guardar o anexo agora.";
}

/** "2026-11-27" vira "27/11/2026", sem passar por fuso. */
export function dataLegivel(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}
