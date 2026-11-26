/**
 * A página de Tecnologia do manual (issue #1727, ADR 0094, decisões 4 e 5).
 *
 * Lê o Markdown de verdade, em `public/manual/tecnologia/pagina.md`, e prova o
 * que a issue promete dele: só quem acessa Tecnologia vê a página, cada tarefa
 * tem passos numerados e print, e o fluxograma desenha o caminho de um pedido.
 *
 * Desde a issue #2282 (PRD #2262, ADR 0113) a página é a da aba de
 * acompanhamento: o Quadro, as Entregas e o que falta para começar a usar. O
 * pedido nasce no Claude do diretor ou no Assistente do app, e saíram as
 * tarefas das telas que a issue #2279 tirou da aba.
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
  "Acompanhar o pedido no Quadro",
  "Ver o que falta para começar a usar",
  "Filtrar por Projeto",
  "Ver as Entregas",
];
const FLUXOGRAMA = "O caminho de um pedido";
/** O nome, na tela, do que saiu da aba com a issue #2279 (ADR 0113, decisão 7). */
const TELAS_QUE_SAIRAM = [
  "Novo pedido",
  "Criar o card",
  "Não bateu",
  "Conversar",
  "Conversa da Demanda",
  "Esperando você",
  "Me explique",
  "Pede sua resposta",
  "Pede sua ação",
  "Passo a passo da Vitta",
  "Achei um problema",
  "Enviar para os desenvolvedores",
  "Entendi assim",
  "Concluir",
  "Reenviar",
];
/** Os prints das tarefas que saíram: nenhum volta à página. */
const PRINTS_QUE_SAIRAM = [
  "novo-pedido.png",
  "pergunta-da-melhoria.png",
  "resumo-do-bug.png",
  "esperando-sua-resposta.png",
  "aviso-pede-resposta.png",
  "cartao-da-pergunta.png",
  "projeto-novo.png",
  "concluir-passo-a-passo.png",
  "pedido-de-implantacao.png",
  "problema-no-assistente.png",
  "espera-a-demanda.png",
  "me-explique.png",
  "entendi-assim.png",
  "enviado-aos-desenvolvedores.png",
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


/** Os passos numerados de uma tarefa, cada um com o texto que vem até o próximo número. */
function passosDa(tarefa: string): string[] {
  return secao(tarefa)
    .texto.split(/^(?=\d+\. )/m)
    .filter((bloco) => /^\d+\. /.test(bloco));
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

  it("tem as tarefas da aba de acompanhamento, e só elas", () => {
    const titulos = secoes(TECNOLOGIA!.corpo).map((s) => s.titulo);
    expect(titulos.filter((t) => t !== FLUXOGRAMA)).toEqual(TAREFAS);
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

  it("não traz travessão nem meia-risca, nem o nome de gente da Vitta de verdade", () => {
    expect(TECNOLOGIA!.corpo).not.toMatch(/[–—]/);
    expect(TECNOLOGIA!.corpo).not.toMatch(/\bPedro\b/);
  });
});

describe("a aba mostrada como ela é, sem as telas que saíram (issue #2282, ADR 0113, decisões 6 e 7)", () => {
  it.each(TELAS_QUE_SAIRAM)("a página não ensina mais %s", (tela) => {
    expect(TECNOLOGIA!.corpo).not.toContain(tela);
  });

  it("a abertura diz que a aba só acompanha, e de onde nasce o pedido: o Claude do diretor ou o Assistente do app", () => {
    const abertura = TECNOLOGIA!.corpo.split(/^## /m)[0];
    expect(abertura).toMatch(/só acompanha/);
    expect(abertura).toMatch(/seu Claude/);
    expect(abertura).toMatch(/Assistente do app/);
    expect(abertura).toMatch(/GitHub/);
  });

  it("a Origem do pedido aparece ao abrir o pedido, porque o card do Quadro não a desenha", () => {
    const abertura = TECNOLOGIA!.corpo.split(/^## /m)[0];
    const frase = abertura.split(/(?<=\.)\s+/).find((f) => /\*\*Pedido do diretor\*\*/.test(f));
    expect(frase, "a abertura não diz de onde vem o pedido").toBeDefined();
    expect(frase).toMatch(/^Ao abrir o pedido, o painel mostra de onde ele veio/);
    expect(frase).toMatch(/\*\*Relato no app\*\*/);
  });

  it("o bug do Assistente aparece no Quadro, em Registrada, assim que você responde às perguntas", () => {
    const abertura = TECNOLOGIA!.corpo.split(/^## /m)[0];
    expect(abertura).toMatch(/aparece no Quadro, em Registrada, assim que você responde às perguntas/);
  });

  it("só o aviso sobre um pedido abre o painel; o aviso antigo que pedia resposta ou ação abre só a aba", () => {
    const { texto } = secao("Acompanhar o pedido no Quadro");
    expect(texto).toMatch(/aviso do sino ou do e-mail sobre um pedido abre o pedido no painel/);
    expect(texto).toMatch(/aviso antigo que pedia a sua resposta ou a sua ação, e o lembrete dele, abrem só a aba, no Quadro, sem pedido aberto/);
  });

  it("nenhum print da página é de uma tela que saiu", () => {
    const citadas = imagensCitadas(TECNOLOGIA!.corpo);
    for (const velho of PRINTS_QUE_SAIRAM) expect(citadas).not.toContain(velho);
  });
});

describe("ver o que falta para começar a usar (issue #2282, ADR 0113, decisão 9)", () => {
  const TAREFA = "Ver o que falta para começar a usar";

  it("um passo mostra o selo Implantação 1 de 3 do card no Quadro, com print", () => {
    const passo = passosDa(TAREFA).find((p) => /selo \*\*Implantação 1 de 3\*\*/.test(p));
    expect(passo, "nenhum passo mostra o selo Implantação do card").toBeDefined();
    expect(imagensCitadas(passo!)).toContain("selo-da-implantacao.png");
  });

  it("um passo explica a seção Implantação do card aberto: quantos feitos, Feito ou Aberto, e com quem, com print", () => {
    const passo = passosDa(TAREFA).find((p) => /seção \*\*Implantação\*\*/.test(p));
    expect(passo, "nenhum passo explica a seção Implantação do card").toBeDefined();
    expect(passo).toMatch(/\*\*1 de 3 feitos\*\*/);
    expect(passo).toMatch(/\*\*Feito\*\*/);
    expect(passo).toMatch(/\*\*Aberto\*\*/);
    expect(passo).toMatch(/com quem/);
    expect(imagensCitadas(passo!)).toContain("implantacao-no-card.png");
  });

  it("cada linha é um card de implantação no GitHub, que se fecha lá, e a conta anda sozinha", () => {
    const { texto } = secao(TAREFA);
    expect(texto).toMatch(/card de implantação/);
    expect(texto).toMatch(/no GitHub/);
    expect(texto).toMatch(/fecha o card/);
    expect(texto).toMatch(/anda sozinha/);
  });

  it("diz que a entrega fica Em produção mesmo com a implantação por fazer, e que o selo some no fim", () => {
    const { texto } = secao(TAREFA);
    expect(texto).toMatch(/Em produção mesmo com a implantação por fazer/);
    expect(texto).toMatch(/o selo some/);
  });

  it("o Acompanhar o pedido no Quadro manda para a tarefa nova, sem repetir os passos", () => {
    const passos = passosDa("Acompanhar o pedido no Quadro");
    expect(passos.some((p) => new RegExp(`\\*\\*${TAREFA}\\*\\*`).test(p))).toBe(true);
    expect(passos.some((p) => /seção \*\*Implantação\*\*/.test(p))).toBe(false);
  });
});

describe("o filtro Projeto (issue #1715 e #1967)", () => {
  it("o filtro Projeto lista os projetos novos da Vitta que já têm pedido na aba", () => {
    const { texto } = secao("Filtrar por Projeto");
    const abertura = texto.split(/\n\s*\n/).find((p) => /projetos novos da Vitta/.test(p));
    expect(abertura, "a tarefa não diz que a aba junta os projetos novos da Vitta").toBeDefined();
    expect(abertura).toMatch(/projetos novos da Vitta que já têm pedido na aba/);
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

describe("o fluxograma do caminho de um pedido (issue #2282)", () => {
  function fluxo(): Fluxo {
    const blocos = fluxogramasCitados(TECNOLOGIA!.corpo);
    expect(blocos).toHaveLength(1);
    const leitura = lerFluxograma(blocos[0]);
    if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
    return leitura.fluxo;
  }

  const inicios = (f: Fluxo) => f.passos.filter((p) => p.forma === "inicio");

  it("fica na seção O caminho de um pedido", () => {
    expect(fluxogramasCitados(secao(FLUXOGRAMA).texto)).toHaveLength(1);
  });

  it("o pedido nasce em dois lugares: a melhoria no Claude do diretor e o bug no Assistente do app", () => {
    const [claude, assistente] = [/Claude/, /Assistente do app/].map((r) => {
      const achado = inicios(fluxo()).find((p) => r.test(p.rotulo));
      expect(achado, `nenhum início ${r}`).toBeDefined();
      return achado!;
    });
    expect(inicios(fluxo())).toHaveLength(2);
    expect(claude.detalhe).toMatch(/[Mm]elhoria/);
    expect(claude.detalhe).toMatch(/GitHub/);
    expect(assistente.detalhe).toMatch(/[Bb]ug/);
  });

  it("os dois inícios chegam ao Quadro sem o Enviar à Vitta: o bug aparece em Registrada antes do envio", () => {
    const f = fluxo();
    const quadro = passoPorRotulo(f, /Quadro/);
    const enviar = passoPorRotulo(f, /^Enviar à Vitta$/);
    for (const inicio of inicios(f)) {
      expect(alcancaveis(f, inicio.id, new Set([enviar.id])).has(quadro.id), inicio.rotulo).toBe(true);
    }
    expect(quadro.detalhe).toMatch(/bug aparece em Registrada/);
    expect(quadro.detalhe).not.toMatch(/selo/);
  });

  it("o bug só entra na fila da Vitta depois do Enviar à Vitta, que vem depois do Quadro", () => {
    const f = fluxo();
    const quadro = passoPorRotulo(f, /Quadro/);
    const enviar = passoPorRotulo(f, /^Enviar à Vitta$/);
    const planejada = passoPorRotulo(f, /^Planejada$/);
    const assistente = inicios(f).find((p) => /Assistente do app/.test(p.rotulo))!;
    expect(f.ligacoes.some((l) => l.de === assistente.id && l.para === enviar.id)).toBe(false);
    expect(alcancaveis(f, quadro.id).has(enviar.id)).toBe(true);
    expect(f.ligacoes.filter((l) => l.de === quadro.id && l.para === planejada.id)).toEqual([]);
    expect(alcancaveis(f, enviar.id).has(planejada.id)).toBe(true);
  });

  it("depois do Quadro, o pedido passa pelas Etapas Em análise, Planejada, Em desenvolvimento, Entregue e Em produção, nessa ordem", () => {
    const f = fluxo();
    const quadro = passoPorRotulo(f, /Quadro/);
    const etapas = [/^Em análise$/, /^Planejada$/, /^Em desenvolvimento$/, /^Entregue$/, /^Em produção$/].map((r) =>
      passoPorRotulo(f, r),
    );
    expect(alcancaveis(f, quadro.id).has(etapas[0].id)).toBe(true);
    for (let i = 0; i < etapas.length - 1; i++) {
      expect(alcancaveis(f, etapas[i].id).has(etapas[i + 1].id), `${etapas[i].rotulo} não leva a ${etapas[i + 1].rotulo}`).toBe(true);
      expect(alcancaveis(f, etapas[i + 1].id).has(etapas[i].id), `${etapas[i + 1].rotulo} volta para ${etapas[i].rotulo}`).toBe(false);
    }
  });

  it("a Implantação vem depois de Em produção, nos cards de implantação do GitHub, e termina num fim só", () => {
    const f = fluxo();
    const producao = passoPorRotulo(f, /^Em produção$/);
    const implantacao = passoPorRotulo(f, /^Implantação$/);
    const fins = f.passos.filter((p) => p.forma === "fim");
    expect(fins).toHaveLength(1);
    expect(alcancaveis(f, producao.id).has(implantacao.id)).toBe(true);
    for (const inicio of inicios(f)) {
      expect(alcancaveis(f, inicio.id, new Set([producao.id])).has(implantacao.id)).toBe(false);
      expect(alcancaveis(f, inicio.id).has(fins[0].id)).toBe(true);
    }
    expect(alcancaveis(f, implantacao.id).has(producao.id), "a Implantação volta para Em produção").toBe(false);
    expect(alcancaveis(f, implantacao.id).has(fins[0].id)).toBe(true);
    expect(implantacao.detalhe).toMatch(/Implantação 1 de 3/);
    expect(implantacao.detalhe).toMatch(/card de implantação/);
    expect(implantacao.detalhe).toMatch(/GitHub/);
  });

  it("a entrega sem nada a fazer pelo hospital vai direto ao fim, sem passar pela Implantação", () => {
    const f = fluxo();
    const producao = passoPorRotulo(f, /^Em produção$/);
    const implantacao = passoPorRotulo(f, /^Implantação$/);
    const fim = f.passos.find((p) => p.forma === "fim")!;
    expect(alcancaveis(f, producao.id, new Set([implantacao.id])).has(fim.id)).toBe(true);
  });

  it("nenhum passo é de uma tela que saiu", () => {
    const texto = fluxo()
      .passos.map((p) => `${p.rotulo} ${p.detalhe}`)
      .join("\n");
    for (const tela of TELAS_QUE_SAIRAM) expect(texto).not.toContain(tela);
  });
});
