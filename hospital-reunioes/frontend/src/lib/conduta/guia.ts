/**
 * Os textos do Guia do rito e da apresentação do primeiro acesso do Comitê de
 * Conduta (issue #1842, seções 5.4, 6 e 10 da especificação do PRD #1786).
 */

export type RitoDoGuia = {
  nome: string;
  quando: string;
  prazo: string;
  quemFaz: string[];
};

/** O que vale em todo rito, antes de ele começar. */
export const ANTES_DO_RITO =
  "Todo caso começa pela triagem: a coordenação confirma se o relato é do canal e qual o rito, e o segundo leitor confere ou contesta. O prazo conta do dia em que o relato foi enviado.";

export const RITOS_DO_GUIA: RitoDoGuia[] = [
  {
    nome: "Encaminhamento",
    quando: "O assunto não é do canal, como salário, escala ou atendimento a paciente.",
    prazo: "5 dias úteis.",
    quemFaz: [
      "A coordenação envia ao relator a orientação padrão, com o lugar certo para o assunto.",
      "O segundo leitor confere a triagem antes do envio.",
      "Não há apuração nem voto. O caso encerra como Encaminhado.",
    ],
  },
  {
    nome: "Rito rápido",
    quando: "A regra geral: tudo o que não pode levar a demissão.",
    prazo: "20 dias corridos.",
    quemFaz: [
      "A coordenação e um membro apuram juntos: ouvem o acusado, sempre, e até duas pessoas.",
      "Os dois revisam o relatório de uma página antes do voto.",
      "Os três membros votam no aplicativo. O voto fica oculto até todos votarem, e todos assinam a ata.",
      "A Direção recebe o dossiê e a ata e registra a decisão sobre a medida.",
      "A coordenação aprova a resposta ao relator e a comunicação ao acusado.",
    ],
  },
  {
    nome: "Rito completo",
    quando:
      "Assédio sexual, violência, fraude, desvio, ou qualquer caso com risco de demissão por justa causa ou de rescisão de contrato.",
    prazo: "30 dias corridos, que se prorrogam uma vez por mais 30, com justificativa escrita.",
    quemFaz: [
      "Dois apuradores de fora da área afetada conduzem a apuração, sem limite de depoimentos, e assinam o relatório.",
      "A coordenação organiza a apuração, mas não conduz.",
      "Os três membros se reúnem presencialmente, em reunião gravada, e depois votam e assinam a ata.",
      "A Direção registra a decisão sobre a medida, e a coordenação aprova o retorno.",
    ],
  },
  {
    nome: "Rota Especial",
    quando: "O relato envolve a Direção, a Presidência ou a família proprietária.",
    prazo: "60 dias corridos, com avisos aos 15, 30 e 60 dias.",
    quemFaz: [
      "O caso nunca entra na fila comum, e nenhum diretor participa.",
      "Um grupo de três apura: o membro do Comitê que não é diretor, um suplente que não é diretor e um membro eleito da CIPA.",
      "O grupo escolhe a autoridade não envolvida que recebe o parecer.",
    ],
  },
];

export type CartaoDoPrimeiroAcesso = { titulo: string; texto: string };

/** Os cinco cartões do primeiro acesso (regra T9). */
export const CARTOES_DO_PRIMEIRO_ACESSO: CartaoDoPrimeiroAcesso[] = [
  {
    titulo: "O Canal de Conduta",
    texto:
      "Aqui chegam os relatos de assédio, fraude, desvio e outras condutas graves, feitos por quem trabalha no hospital, muitas vezes sem se identificar.",
  },
  {
    titulo: "Minha vez",
    texto:
      "A tela inicial mostra só o que depende de você, do prazo mais curto ao mais longo. Cada tela diz o que fazer agora, com um botão principal.",
  },
  {
    titulo: "Os quatro ritos",
    texto:
      "Cada caso segue um rito: Encaminhamento, Rápido, Completo ou Especial. O Guia do rito explica cada um e abre de qualquer tela do Comitê.",
  },
  {
    titulo: "Ninguém apura sozinho",
    texto:
      "Quem apura vai sempre em dupla. O prazo do caso aparece em todas as telas, e prazo vencido fica registrado para sempre.",
  },
  {
    titulo: "Sigilo e registro",
    texto:
      "Você só abre os casos em que está designado, depois de assinar o Termo de Confidencialidade e Posse. Tudo o que se faz no caso fica registrado e não se apaga.",
  },
];

/**
 * Onde fica guardado que a pessoa já viu a apresentação: no cadastro de login
 * dela, e não no navegador, para valer em qualquer aparelho.
 */
export const CHAVE_DA_APRESENTACAO = "conduta_apresentacao_vista_em";

export const ENDERECO_DO_GUIA = "/comite-de-conduta/guia";

/** A pessoa ainda não viu os cinco cartões do primeiro acesso. */
export function precisaDaApresentacao(user: { user_metadata?: Record<string, unknown> | null }): boolean {
  return !user.user_metadata?.[CHAVE_DA_APRESENTACAO];
}
