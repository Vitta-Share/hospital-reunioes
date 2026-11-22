/**
 * A página de Tecnologia do manual (issue #1727, ADR 0094, decisões 4 e 5).
 *
 * Lê o Markdown de verdade, em `public/manual/tecnologia/pagina.md`, e prova o
 * que a issue promete dele: só quem acessa Tecnologia vê a página, cada tarefa
 * tem passos numerados e print, e o fluxograma desenha o caminho de um pedido,
 * da conversa com o Assistente até Entregue.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MarkdownDoManual } from "@/components/manual/MarkdownDoManual";
import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { lerFluxograma, type Fluxo, type Passo } from "@/components/manual/fluxograma/fluxo";
import { carregarPaginasDoManual } from "./carregar";
import { fluxogramasCitados, imagensCitadas, paginasVisiveis } from "./paginas";

const PAGINAS = carregarPaginasDoManual();
const TECNOLOGIA = PAGINAS.find((p) => p.modulo === "tecnologia");
const TAREFAS = [
  "Pedir um bug ou uma melhoria ao Assistente",
  "Acompanhar o pedido no Quadro",
  "Ver o que espera sua resposta",
  "Responder uma pergunta da Vitta",
  "Pedir explicação ao assistente (Me explique)",
  "Mandar o que você escreveu aos desenvolvedores",
  "Filtrar por Projeto",
  "Ver as Entregas",
];

function pessoa(campos: Partial<CurrentParticipante>): CurrentParticipante {
  return {
    id: "p1",
    nome_completo: "Fulana de Tal",
    email: "fulana@hsm",
    access_profile: "regular",
    perfil_pop: null,
    perfil_ouvidoria: null,
    perfil_contas_medicas: null,
    ...campos,
  };
}

/** As seções `## ` do corpo, com o título e o texto de cada uma. */
function secoes(corpo: string): { titulo: string; texto: string }[] {
  return corpo
    .split(/^## /m)
    .slice(1)
    .map((bloco) => {
      const [titulo, ...resto] = bloco.split("\n");
      return { titulo: titulo.trim(), texto: resto.join("\n") };
    });
}

function secao(titulo: string) {
  const achada = secoes(TECNOLOGIA!.corpo).find((s) => s.titulo === titulo);
  expect(achada, `a página não tem a tarefa "${titulo}"`).toBeDefined();
  return achada!;
}

/** Os passos que se alcançam saindo de um, pelas ligações, sem passar pelos de `evitar`. */
function alcancaveis(fluxo: Fluxo, de: string, evitar: Set<string> = new Set()): Set<string> {
  const vistos = new Set([de]);
  const fila = [de];
  while (fila.length) {
    const atual = fila.shift()!;
    for (const l of fluxo.ligacoes) {
      if (l.de === atual && !vistos.has(l.para) && !evitar.has(l.para)) {
        vistos.add(l.para);
        fila.push(l.para);
      }
    }
  }
  return vistos;
}

function passoPorRotulo(fluxo: Fluxo, rotulo: RegExp): Passo {
  const passo = fluxo.passos.find((p) => rotulo.test(p.rotulo));
  if (!passo) throw new Error(`O fluxograma não tem um passo ${rotulo}.`);
  return passo;
}

describe("a página de Tecnologia do manual", () => {
  it("existe e aparece para o Super admin, que tem Tecnologia no menu", () => {
    expect(TECNOLOGIA?.pasta).toBe("tecnologia");
    const superAdmin = pessoa({ access_profile: "super_admin" });
    expect(paginasVisiveis(PAGINAS, superAdmin).map((p) => p.modulo)).toContain("tecnologia");
  });

  it.each([
    ["o Facilitador, que entra no Admin só pelo Dados do Atendimento", pessoa({ access_profile: "regular" })],
    ["a Secretária", pessoa({ access_profile: "secretaria" })],
  ])("não aparece para %s", (_quem, participante) => {
    expect(paginasVisiveis(PAGINAS, participante).map((p) => p.modulo)).not.toContain("tecnologia");
  });

  it.each(TAREFAS)("a tarefa %s tem passos numerados e pelo menos um print", (tarefa) => {
    const { texto } = secao(tarefa);
    const passos = texto.match(/^\d+\. /gm) ?? [];
    expect(passos.slice(0, 2)).toEqual(["1. ", "2. "]);
    expect(imagensCitadas(texto).length).toBeGreaterThan(0);
  });

  it.each(TAREFAS)("a tarefa %s sai na tela como uma lista só, numerada em sequência", (tarefa) => {
    const { texto } = secao(tarefa);
    const numeros = (texto.match(/^\d+(?=\. )/gm) ?? []).map(Number);
    expect(numeros).toEqual(numeros.map((_, i) => i + 1));
    // O `ol` do manual não repassa o `start`: um print fora do item fecha a
    // lista e a próxima recomeça em 1 na tela. Uma lista só, com todos os passos.
    const html = renderToStaticMarkup(MarkdownDoManual({ pasta: "tecnologia", children: texto }));
    expect(html.match(/<ol[ >]/g) ?? []).toHaveLength(1);
    expect(html.match(/<li[ >]/g) ?? []).toHaveLength(numeros.length);
  });
});

/** Os passos numerados de uma tarefa, cada um com o texto que vem até o próximo número. */
function passosDa(tarefa: string): string[] {
  return secao(tarefa)
    .texto.split(/^(?=\d+\. )/m)
    .filter((bloco) => /^\d+\. /.test(bloco));
}

describe("a pergunta da Vitta na tarefa de responder a ela (issues #1807 e #1968, ADR 0096)", () => {
  const TAREFA = "Responder uma pergunta da Vitta";

  it("um passo diz que a pergunta chega na Conversa da Demanda, com aviso no sino e por e-mail", () => {
    const chegada = passosDa(TAREFA).find((p) => /pergunta/i.test(p) && /decisão sua/.test(p));
    expect(chegada, "nenhum passo diz onde chega a pergunta da Vitta").toBeDefined();
    expect(chegada).toMatch(/Conversa da Demanda/);
    // O aviso vem pelos dois canais; o "link do e-mail" do mesmo passo não conta como aviso.
    expect(chegada).toMatch(/aviso no sino e por e-mail/);
  });

  it("um passo depois diz para responder ali mesmo, pelo Conversar", () => {
    const passos = passosDa(TAREFA);
    const i = passos.findIndex((p) => /pergunta/i.test(p) && /decisão sua/.test(p));
    expect(i, "nenhum passo diz onde chega a pergunta da Vitta").toBeGreaterThanOrEqual(0);
    const resposta = passos.slice(i + 1).find((p) => /\*\*Conversar\*\*/.test(p)) ?? "";
    expect(resposta).toMatch(/responda ali mesmo/);
  });

  it("não traz travessão nem meia-risca, nem o nome de quem manda a pergunta", () => {
    expect(TECNOLOGIA!.corpo).not.toMatch(/[–—]/);
    expect(TECNOLOGIA!.corpo).not.toMatch(/\bPedro\b/);
  });
});

describe("o aviso Pede sua resposta e o pedido de projeto novo (issue #1968, PRD #1964)", () => {
  const TAREFA = "Responder uma pergunta da Vitta";

  function passoDoAviso(): string {
    const passo = passosDa(TAREFA).find((p) => /\*\*Pede sua resposta\*\*/.test(p));
    expect(passo, "nenhum passo mostra o aviso Pede sua resposta").toBeDefined();
    return passo!;
  }

  it("um passo mostra o aviso Pede sua resposta no sino, com o assunto, e só para quem responde", () => {
    const passo = passoDoAviso();
    expect(passo).toMatch(/sino/);
    expect(passo).toMatch(/assunto/);
    expect(passo).toMatch(/mesmo num pedido que você não abriu/);
    expect(imagensCitadas(passo)).toContain("aviso-pede-resposta.png");
  });

  it("um passo diz o assunto do e-mail, com quem pergunta e sobre o quê", () => {
    const passo = passosDa(TAREFA).find((p) => /e-mail/.test(p) && /pede sua resposta: /.test(p));
    expect(passo, "nenhum passo diz o assunto do e-mail").toBeDefined();
  });

  it("responder no cartão da lista vem primeiro, e a Conversa da Demanda depois, com o print do cartão (issues #2123 e #2145)", () => {
    const passos = passosDa(TAREFA).filter((p) => /responda ali mesmo/.test(p));
    expect(passos.length, "faltam os passos de responder na lista e na Conversa").toBeGreaterThanOrEqual(2);
    const [naLista, naConversa] = passos;
    expect(naLista).toMatch(/no cartão da lista/);
    expect(naLista).toMatch(/sem abrir o pedido/);
    expect(naConversa).toMatch(/Conversa da Demanda/);
    expect(imagensCitadas(naConversa)).toContain("cartao-da-pergunta.png");
  });

  it("a tarefa Acompanhar o pedido no Quadro manda para a tarefa nova, sem repetir os passos", () => {
    const passos = passosDa("Acompanhar o pedido no Quadro");
    expect(passos.some((p) => /\*\*Responder uma pergunta da Vitta\*\*/.test(p))).toBe(true);
    expect(passos.some((p) => /responda ali mesmo/.test(p))).toBe(false);
  });

  it("explica o pedido de projeto novo: Vitta, nome do projeto, Abrir o plano, filtro Projeto, com print", () => {
    const { texto } = secao(TAREFA);
    const trecho = texto.split(/\n\s*\n/).filter((p) => /projeto novo|ainda não aparecia/.test(p) || /projeto-novo\.png/.test(p)).join("\n");
    expect(trecho, "a tarefa não explica o pedido de projeto novo").toMatch(/ainda não aparecia no aplicativo/);
    expect(trecho).toMatch(/\*\*Vitta\*\*/);
    expect(trecho).toMatch(/nome do projeto/);
    expect(trecho).toMatch(/\*\*Abrir o plano\*\*/);
    expect(trecho).toMatch(/\*\*Projeto\*\*/);
    expect(imagensCitadas(trecho)).toContain("projeto-novo.png");
  });

  it("o filtro Projeto lista os projetos novos da Vitta que já têm pedido na aba, sem prender a pergunta a quem lê", () => {
    // O Super admin vê todo pedido de Origem Vitta e /projetos lista todo projeto novo com pedido,
    // não só os que têm pergunta para quem lê (revisão do PR #1977).
    const { texto } = secao("Filtrar por Projeto");
    const abertura = texto.split(/\n\s*\n/).find((p) => /projetos novos da Vitta/.test(p));
    expect(abertura, "a tarefa não diz que a aba junta os projetos novos da Vitta").toBeDefined();
    expect(abertura).toMatch(/projetos novos da Vitta que já têm pedido na aba/);
    expect(abertura).not.toMatch(/pergunta para você/);
  });
});

describe("a lista Esperando sua resposta, o cartão e o Me explique (issue #2123, PRD #2112, ADR 0109)", () => {
  const LISTA = "Ver o que espera sua resposta";
  const RESPONDER = "Responder uma pergunta da Vitta";
  const ME_EXPLIQUE = "Pedir explicação ao assistente (Me explique)";

  it("a lista Esperando sua resposta fica no alto da aba, com as suas perguntas primeiro e o cartão em destaque pelo aviso", () => {
    const passos = passosDa(LISTA);
    const daLista = passos.find((p) => /\*\*Esperando sua resposta\*\*/.test(p));
    expect(daLista, "nenhum passo mostra a lista Esperando sua resposta").toBeDefined();
    expect(daLista).toMatch(/no alto da aba/);
    expect(imagensCitadas(daLista!)).toContain("esperando-sua-resposta.png");
    expect(passos.some((p) => /as suas vêm primeiro/.test(p))).toBe(true);
    expect(passos.some((p) => /aviso do sino ou no link do e-mail/.test(p) && /em destaque/.test(p))).toBe(true);
  });

  it("o cartão diz por que precisa de você, o que está parado, o que anda depois e o que o hospital ganha", () => {
    const { texto } = secao(LISTA);
    for (const linha of [
      "Por que precisa de você",
      "O que está parado",
      "O que anda quando você responder",
      "O que o hospital ganha",
    ]) {
      expect(texto).toContain(`**${linha}**`);
    }
  });

  it("responder no cartão: a opção, com a Recomendada em destaque, ou o campo livre e o Responder", () => {
    const passos = passosDa(RESPONDER);
    const i = passos.findIndex((p) => /responda ali mesmo/.test(p));
    expect(i, "nenhum passo manda responder no cartão").toBeGreaterThanOrEqual(0);
    const noCartao = passos.slice(i).find((p) => /\*\*Recomendada\*\*/.test(p));
    expect(noCartao, "nenhum passo mostra as opções com a Recomendada").toBeDefined();
    expect(noCartao).toMatch(/clique na opção/);
    expect(noCartao).toMatch(/\*\*Responder\*\*/);
  });

  it("a resposta deixa a pergunta Respondida, sai da lista na hora, e só destrava com o ok da Vitta", () => {
    const passo = passosDa(RESPONDER).find((p) => /\*\*Respondida\*\*/.test(p));
    expect(passo, "nenhum passo diz o que acontece depois de responder").toBeDefined();
    // Desde a issue #2145 a lista tira a Pergunta respondida na hora, sem reler a aba.
    expect(passo).toMatch(/sai da lista \*\*Esperando sua resposta\*\* na hora/);
    const daLista = secao(LISTA).texto.split(/\n\s*\n/).find((p) => /sai da lista/.test(p));
    expect(daLista, "a tarefa da lista não diz quando a pergunta respondida sai").toBeDefined();
    expect(daLista).toMatch(/responda ali mesmo, no cartão da lista/);
    expect(daLista).toMatch(/\*\*Me explique\*\*/);
    expect(daLista).toMatch(/sai da lista na hora/);
    const tudo = secao(LISTA).texto + secao(RESPONDER).texto;
    expect(tudo).not.toMatch(/na próxima vez que a aba abre/);
    expect(tudo).not.toMatch(/serve para ler\. Para responder, abra o pedido/);
    expect(tudo).not.toMatch(/continua na lista como \*\*Aberta\*\*/);
    const { texto } = secao(RESPONDER);
    expect(texto).toMatch(/\*\*Resolvida\*\*/);
    expect(texto).toMatch(/\*\*O que foi decidido\*\*/);
    expect(texto).toMatch(/\*\*Cancelada\*\*/);
    expect(texto).toMatch(/depois de 3 dias/);
  });

  it("o Me explique é uma conversa só sua, o rascunho vai para o campo pelo Usar este rascunho, e quem envia é o Responder", () => {
    const passos = passosDa(ME_EXPLIQUE);
    const abrir = passos.findIndex((p) => /clique em \*\*Me explique\*\*/.test(p));
    const rascunho = passos.findIndex((p) => /\*\*Usar este rascunho\*\*/.test(p));
    const responder = passos.findIndex((p, i) => i > rascunho && /\*\*Responder\*\*/.test(p));
    expect([abrir, rascunho, responder].every((i) => i >= 0), `faltam passos: ${abrir}, ${rascunho}, ${responder}`).toBe(true);
    expect(abrir).toBeLessThan(rascunho);
    expect(imagensCitadas(passos.slice(abrir, rascunho + 1).join("\n"))).toContain("me-explique.png");
    expect(secao(ME_EXPLIQUE).texto).toMatch(/só sua/);
    expect(secao(ME_EXPLIQUE).texto).toMatch(/nada do Me explique vai para a Conversa da Demanda/);
  });

  it("a Pergunta da Vitta nunca se chama Pendência, que é a Ação da Ata (ADR 0109, decisão 2)", () => {
    expect(TECNOLOGIA!.corpo).not.toMatch(/pend[êe]ncia/i);
  });
});

describe("as partes do pedido na tarefa de abrir o card (issue #1903, ADR 0100)", () => {
  const TAREFA = "Acompanhar o pedido no Quadro";

  function passoDasPartes(): string {
    const passo = passosDa(TAREFA).find((p) => /\*\*Partes\*\*/.test(p));
    expect(passo, "nenhum passo explica a seção Partes do card").toBeDefined();
    return passo!;
  }

  it("um passo numerado explica as partes agrupadas por Onda, o número de cada uma e o Espera a", () => {
    const passo = passoDasPartes();
    expect(passo).toMatch(/\bOnda 1\b/);
    expect(passo).toMatch(/Onda/);
    expect(passo).toMatch(/número/);
    expect(passo).toMatch(/#\d+/);
    expect(passo).toMatch(/\*\*Espera a #\d+\*\*/);
    expect(passo).toMatch(/\*\*Espera a #\d+, de outro pedido\*\*/);
  });

  it("o passo das partes traz o print delas", () => {
    expect(imagensCitadas(passoDasPartes())).toContain("partes-por-onda.png");
  });
});

describe("o atalho Ver o plano na tarefa de acompanhar o pedido (issue #2015, PRD #2007)", () => {
  const TAREFA = "Acompanhar o pedido no Quadro";

  function passoDoPlano(): string {
    const passo = passosDa(TAREFA).find((p) => /\*\*Ver o plano\*\*/.test(p));
    expect(passo, "nenhum passo mostra o botão Ver o plano do card").toBeDefined();
    return passo!;
  }

  it("um passo numerado mostra o botão Ver o plano, que abre a página do plano em outra aba, com o check de validado", () => {
    const passo = passoDoPlano();
    expect(passo).toMatch(/página do plano/);
    expect(passo).toMatch(/outra aba/);
    expect(passo).toMatch(/check/);
    expect(passo).toMatch(/já validou/);
  });

  it("o mesmo passo cita o cartão Plano do card aberto e manda validar pelo link do e-mail", () => {
    const passo = passoDoPlano();
    expect(passo).toMatch(/\*\*Plano\*\*/);
    expect(passo).toMatch(/validar, continue usando o link do e-mail/);
  });

  it("o passo do Ver o plano traz o print dele", () => {
    expect(imagensCitadas(passoDoPlano())).toContain("ver-o-plano.png");
  });
});

describe("a tarefa de mandar o que você escreveu aos desenvolvedores (issue #2015, ADR 0108)", () => {
  const TAREFA = "Mandar o que você escreveu aos desenvolvedores";

  /** O índice do primeiro passo que casa com o padrão, ou -1. */
  function indice(padrao: RegExp): number {
    return passosDa(TAREFA).findIndex((p) => padrao.test(p));
  }

  it("os passos vão na ordem: escrever na Conversa, Enviar para os desenvolvedores, Entendi assim, Enviar ou Corrigir, a linha Enviado", () => {
    const ordem = [
      indice(/Escreva/),
      indice(/clique em \*\*Enviar para os desenvolvedores\*\*/),
      indice(/\*\*Entendi assim:\*\*/),
      indice(/clique em \*\*Enviar\*\*[\s\S]*\*\*Corrigir\*\*/),
      indice(/\*\*Enviado aos desenvolvedores\*\*/),
    ];
    expect(ordem.every((i) => i >= 0), `faltam passos: ${ordem.join(", ")}`).toBe(true);
    expect(ordem).toEqual([...ordem].sort((a, b) => a - b));
    expect(new Set(ordem).size).toBe(ordem.length);
  });

  it("o passo da escrita fica na Conversa da Demanda, com quantas mensagens quiser", () => {
    const passos = passosDa(TAREFA);
    expect(passos.some((p) => /\*\*Conversar\*\*/.test(p))).toBe(true);
    expect(passos[indice(/Escreva/)]).toMatch(/quantas mensagens quiser/);
  });

  it("o botão fica desligado sem mensagem nova desde o último envio", () => {
    expect(passosDa(TAREFA)[indice(/clique em \*\*Enviar para os desenvolvedores\*\*/)]).toMatch(
      /desligado enquanto não há mensagem sua nova desde o último envio/,
    );
  });

  it("o Corrigir leva à caixa: manda a mensagem pelo botão ao lado dela antes de Enviar para os desenvolvedores de novo", () => {
    const passo = passosDa(TAREFA)[indice(/\*\*Corrigir\*\*/)];
    const corrigir = passo.slice(passo.indexOf("**Corrigir**"));
    const mandar = corrigir.search(/clique no botão de enviar, ao lado da caixa/);
    const deNovo = corrigir.search(/de novo em Enviar para os desenvolvedores/);
    expect(mandar).toBeGreaterThan(0);
    expect(deNovo).toBeGreaterThan(mandar);
    expect(corrigir).toMatch(/resumo seguinte já leva em conta o que você escreveu/);
    // A caixa nunca sai da tela: o Corrigir só fecha o Entendi assim e põe o cursor nela.
    expect(corrigir).not.toMatch(/caixa[^.]*volta/);
  });

  it("a linha Enviado traz a data, a hora e os tópicos, e o que vem depois entra no próximo envio", () => {
    const passo = passosDa(TAREFA)[indice(/\*\*Enviado aos desenvolvedores\*\*/)];
    expect(passo).toMatch(/data, a hora e os tópicos/);
    expect(passo).toMatch(/entra no próximo envio/);
  });

  it("diz que quem cuida do pedido lê a conversa, e que do aplicativo sai só o resumo aprovado (ADR 0083, decisão 8; ADR 0108, decisão 5)", () => {
    const { texto } = secao(TAREFA);
    expect(texto).toMatch(/Quem cuida do pedido lê a conversa no aplicativo/);
    expect(texto).toMatch(/Do aplicativo sai só o resumo que você aprovou/);
    // Só o GitHub recebe apenas o resumo: os desenvolvedores leem a conversa no app.
    expect(texto).not.toMatch(/desenvolvedores recebem só/i);
  });

  it("o Entendi assim e a linha Enviado têm print, cada um no seu passo", () => {
    expect(imagensCitadas(passosDa(TAREFA)[indice(/\*\*Entendi assim:\*\*/)])).toContain("entendi-assim.png");
    expect(imagensCitadas(passosDa(TAREFA)[indice(/\*\*Enviado aos desenvolvedores\*\*/)])).toContain(
      "enviado-aos-desenvolvedores.png",
    );
  });

  it("a falha diz o motivo e o Tente de novo, sem perder o que você escreveu", () => {
    expect(secao(TAREFA).texto).toMatch(/\*\*Tente de novo\*\*, sem perder nada do que você escreveu/);
  });
});

describe("o fluxograma do caminho de um pedido", () => {
  function fluxo(): Fluxo {
    const blocos = fluxogramasCitados(TECNOLOGIA!.corpo);
    expect(blocos).toHaveLength(1);
    const leitura = lerFluxograma(blocos[0]);
    if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
    return leitura.fluxo;
  }

  it("lê sem erro de bloco e começa num só lugar, a conversa com o Assistente", () => {
    const inicios = fluxo().passos.filter((p) => p.forma === "inicio");
    expect(inicios).toHaveLength(1);
    expect(inicios[0].rotulo).toMatch(/Assistente/);
  });

  it("termina em Entregue, que se alcança a partir da conversa", () => {
    const f = fluxo();
    const entregue = passoPorRotulo(f, /^Entregue$/);
    expect(entregue.forma).toBe("fim");
    const inicio = f.passos.find((p) => p.forma === "inicio")!;
    expect(alcancaveis(f, inicio.id).has(entregue.id)).toBe(true);
  });

  it("nada chega a Entregue sem o clique em Criar o card", () => {
    const f = fluxo();
    const inicio = f.passos.find((p) => p.forma === "inicio")!;
    const criar = passoPorRotulo(f, /^Criar o card$/);
    const entregue = passoPorRotulo(f, /^Entregue$/);
    expect(alcancaveis(f, inicio.id, new Set([criar.id])).has(entregue.id)).toBe(false);
  });

  it("o bug e a melhoria são os dois lados da primeira decisão, e os dois chegam ao Criar o card", () => {
    const f = fluxo();
    const decisao = passoPorRotulo(f, /[Bb]ug ou melhoria/);
    expect(decisao.forma).toBe("decisao");
    const criar = passoPorRotulo(f, /^Criar o card$/);
    const saidas = f.ligacoes.filter((l) => l.de === decisao.id);
    expect(saidas.map((l) => l.rotulo).sort()).toEqual(["bug", "melhoria"]);
    for (const saida of saidas) {
      expect(alcancaveis(f, saida.para).has(criar.id), `o lado ${saida.rotulo} não chega ao Criar o card`).toBe(true);
    }
  });

  it("depois do card, o pedido passa pelas Etapas Em análise, Planejada e Em desenvolvimento, nessa ordem", () => {
    const f = fluxo();
    const criar = passoPorRotulo(f, /^Criar o card$/);
    const etapas = [/^Em análise$/, /^Planejada$/, /^Em desenvolvimento$/, /^Entregue$/].map((r) => passoPorRotulo(f, r));
    expect(alcancaveis(f, criar.id).has(etapas[0].id)).toBe(true);
    for (let i = 0; i < etapas.length - 1; i++) {
      expect(alcancaveis(f, etapas[i].id).has(etapas[i + 1].id), `${etapas[i].rotulo} não leva a ${etapas[i + 1].rotulo}`).toBe(true);
      expect(alcancaveis(f, etapas[i + 1].id).has(etapas[i].id), `${etapas[i + 1].rotulo} volta para ${etapas[i].rotulo}`).toBe(false);
    }
  });

  it("o passo do Envio aos desenvolvedores só se alcança depois do Criar o card (issue #2015)", () => {
    const f = fluxo();
    const inicio = f.passos.find((p) => p.forma === "inicio")!;
    const criar = passoPorRotulo(f, /^Criar o card$/);
    const envio = passoPorRotulo(f, /^Enviar para os desenvolvedores$/);
    expect(alcancaveis(f, criar.id).has(envio.id)).toBe(true);
    expect(alcancaveis(f, inicio.id, new Set([criar.id])).has(envio.id)).toBe(false);
  });

  it("o Entendi assim decide entre Enviar, que chega ao Enviado, e Corrigir, que volta ao botão (issue #2015)", () => {
    const f = fluxo();
    const envio = passoPorRotulo(f, /^Enviar para os desenvolvedores$/);
    const entendi = passoPorRotulo(f, /Entendi assim/);
    const enviado = passoPorRotulo(f, /^Enviado aos desenvolvedores$/);
    expect(entendi.forma).toBe("decisao");
    expect(f.ligacoes.some((l) => l.de === envio.id && l.para === entendi.id)).toBe(true);
    const saidas = f.ligacoes.filter((l) => l.de === entendi.id);
    expect(saidas.map((l) => l.rotulo).sort()).toEqual(["Corrigir", "Enviar"]);
    const enviar = saidas.find((l) => l.rotulo === "Enviar")!;
    const corrigir = saidas.find((l) => l.rotulo === "Corrigir")!;
    expect(alcancaveis(f, enviar.para).has(enviado.id)).toBe(true);
    expect(alcancaveis(f, corrigir.para, new Set([enviado.id])).has(envio.id)).toBe(true);
    expect(enviado.detalhe).toMatch(/só o resumo que você aprovou/);
  });

  it("a pergunta da Vitta entra pela lista Esperando sua resposta, e o trabalho só anda depois da resposta e do ok da Vitta (issue #2123)", () => {
    const f = fluxo();
    const inicio = f.passos.find((p) => p.forma === "inicio")!;
    const lista = passoPorRotulo(f, /^Esperando sua resposta$/);
    const responder = passoPorRotulo(f, /^Responder no cartão$/);
    const resolvida = passoPorRotulo(f, /^Resolvida$/);
    const desenvolvimento = passoPorRotulo(f, /^Em desenvolvimento$/);
    expect(alcancaveis(f, inicio.id).has(lista.id)).toBe(true);
    // A lista é a entrada: nenhum caminho chega ao cartão sem passar por ela.
    expect(alcancaveis(f, inicio.id, new Set([lista.id])).has(responder.id)).toBe(false);
    expect(alcancaveis(f, lista.id).has(responder.id)).toBe(true);
    expect(alcancaveis(f, responder.id, new Set([resolvida.id])).has(desenvolvimento.id)).toBe(false);
    expect(alcancaveis(f, resolvida.id).has(desenvolvimento.id)).toBe(true);
    expect(responder.detalhe).toMatch(/Me explique/);
  });
});
