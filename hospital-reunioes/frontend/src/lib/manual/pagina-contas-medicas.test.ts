/**
 * A página de Contas médicas do manual (issue #1724, ADR 0094, decisões 4 e 5).
 *
 * Lê o Markdown de verdade, em `public/manual/contas-medicas/pagina.md`, e
 * prova o que a issue promete dele: quem vê a página, o passo a passo de cada
 * tarefa com o print, e o fluxograma do caminho de uma conta, do envio à
 * análise concluída.
 *
 * Desde a issue #1959 (PRD #1933) a página ensina a tela nova: a Esteira com
 * as cinco etapas, a busca, o arquivar por Competência e as Legendas.
 */

import { describe, expect, it } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { lerFluxograma, ordemDoFluxo, type Fluxo } from "@/components/manual/fluxograma/fluxo";
import { O_QUE_E_ARQUIVAR } from "@/lib/contas-medicas/arquivo";
import { NOME_DA_ETAPA } from "@/lib/contas-medicas/textos";
import { carregarPaginasDoManual } from "./carregar";
import { imagensCitadas, paginasVisiveis } from "./paginas";

const PAGINAS = carregarPaginasDoManual();
const CONTAS = PAGINAS.find((p) => p.modulo === "contas-medicas");

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

/** O texto do bloco ```fluxograma da página. */
function blocoDoFluxograma(corpo: string): string {
  const achado = /```fluxograma\n([\s\S]*?)```/.exec(corpo);
  if (!achado) throw new Error("A página não tem o bloco fluxograma.");
  return achado[1];
}

/** Os passos que se alcançam a partir de um, seguindo as ligações. */
function alcancaveis(fluxo: Fluxo, de: string): Set<string> {
  const vistos = new Set([de]);
  const fila = [de];
  while (fila.length) {
    const atual = fila.shift()!;
    for (const l of fluxo.ligacoes) {
      if (l.de === atual && !vistos.has(l.para)) {
        vistos.add(l.para);
        fila.push(l.para);
      }
    }
  }
  return vistos;
}

describe("a página de Contas médicas do manual", () => {
  it("aparece para a faturista, que tem Contas médicas no menu", () => {
    expect(CONTAS?.pasta).toBe("contas-medicas");
    const faturista = pessoa({ access_profile: null, perfil_contas_medicas: "faturista" });
    expect(paginasVisiveis(PAGINAS, faturista).map((p) => p.modulo)).toContain("contas-medicas");
  });

  it("não aparece para quem não acessa Contas médicas", () => {
    const semOModulo = pessoa({ access_profile: "regular", perfil_contas_medicas: null });
    expect(paginasVisiveis(PAGINAS, semOModulo).map((p) => p.modulo)).not.toContain("contas-medicas");
  });

  it.each([
    ["Enviar uma conta"],
    ["Pegar uma conta da Fila"],
    ["Analisar a conta no Guia"],
    ["Pedir o que faltou"],
    ["Achar uma conta"],
    ["Arquivar as contas do mês"],
    ["Ligar e desligar as legendas"],
  ])("a tarefa %s tem passos numerados e pelo menos um print", (tarefa) => {
    const secao = secoes(CONTAS!.corpo).find((s) => s.titulo === tarefa);
    expect(secao, `a página não tem a tarefa "${tarefa}"`).toBeDefined();
    const passos = secao!.texto.match(/^\d+\. /gm) ?? [];
    expect(passos.slice(0, 2)).toEqual(["1. ", "2. "]);
    expect(imagensCitadas(secao!.texto).length).toBeGreaterThan(0);
  });

  it("Arquivar as contas do mês ensina uma a uma, o mês inteiro, o que arquivar quer dizer e como desarquivar", () => {
    const arquivar = secoes(CONTAS!.corpo).find((s) => s.titulo === "Arquivar as contas do mês");
    expect(arquivar, "a página não tem a tarefa de arquivar").toBeDefined();
    const texto = arquivar!.texto;
    const inicioUmaAUma = texto.indexOf("Para arquivar uma a uma");
    const inicioMesInteiro = texto.indexOf("Para arquivar o mês inteiro");
    expect(inicioUmaAUma, "falta o trecho Para arquivar uma a uma").toBeGreaterThanOrEqual(0);
    expect(inicioMesInteiro, "falta o trecho Para arquivar o mês inteiro").toBeGreaterThan(inicioUmaAUma);
    const umaAUma = texto.slice(inicioUmaAUma, inicioMesInteiro);
    expect(umaAUma, "falta arquivar uma a uma").toContain("**Arquivar**");
    expect(texto, "falta arquivar o mês inteiro").toContain("**Arquivar o mês**");
    expect(texto, "falta dizer o que arquivar quer dizer").toContain(O_QUE_E_ARQUIVAR);
    expect(texto, "falta ensinar a desarquivar").toContain("**Desarquivar**");
  });

  it("as tarefas antigas falam da tela nova: Pegar na Fila, a etapa Envios e a Mesa de trabalho", () => {
    const tarefa = (titulo: string) => secoes(CONTAS!.corpo).find((s) => s.titulo === titulo)!.texto;
    expect(tarefa("Pegar uma conta da Fila")).toContain("**Pegar**");
    expect(tarefa("Enviar uma conta")).toContain("**Enviar contas**");
    expect(tarefa("Enviar uma conta")).toContain("**Envios**");
    expect(tarefa("Analisar a conta no Guia")).toContain("**Mesa de trabalho**");
    expect(CONTAS!.corpo, "a aba Meus envios não existe mais").not.toMatch(/Meus envios/i);
  });

  it("não traz travessão nem meia-risca", () => {
    expect(CONTAS!.corpo).not.toMatch(/[\u2013\u2014]/);
  });

  it("O caminho de uma conta descreve a Esteira com as cinco etapas da tela", () => {
    const caminho = secoes(CONTAS!.corpo).find((s) => s.titulo === "O caminho de uma conta");
    expect(caminho, "a página não tem O caminho de uma conta").toBeDefined();
    expect(caminho!.texto).toMatch(/\bEsteira\b/);
    const semOFluxograma = caminho!.texto.replace(/```fluxograma[\s\S]*?```/, "");
    for (const etapa of ["Envios", "Fila", "Em análise", "Concluídas", "Arquivadas"]) {
      expect(Object.values(NOME_DA_ETAPA)).toContain(etapa);
      expect(semOFluxograma, `o texto não fala da etapa ${etapa}`).toContain(`**${etapa}**`);
    }
  });

  it("o fluxograma lê sem erro e vai do envio à análise concluída e à conta arquivada", () => {
    const leitura = lerFluxograma(blocoDoFluxograma(CONTAS!.corpo));
    if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
    const { fluxo } = leitura;

    const [primeiro] = ordemDoFluxo(fluxo);
    expect(primeiro.forma).toBe("inicio");
    expect(primeiro.rotulo).toMatch(/envi/i);

    const alcancados = alcancaveis(fluxo, primeiro.id);
    const concluida = fluxo.passos.find((p) => /conclu/i.test(p.rotulo));
    expect(concluida, "falta o passo da análise concluída").toBeDefined();
    expect(alcancados.has(concluida!.id)).toBe(true);

    const arquivada = fluxo.passos.find((p) => p.forma === "fim" && /Arquivadas/.test(p.rotulo));
    expect(arquivada, "falta o fim na etapa Arquivadas").toBeDefined();
    expect(alcancados.has(arquivada!.id)).toBe(true);
    expect(alcancaveis(fluxo, concluida!.id).has(arquivada!.id)).toBe(true);
  });

  it("o fluxograma mostra a volta por Retorno: da conta arquivada de novo para o Guia", () => {
    const leitura = lerFluxograma(blocoDoFluxograma(CONTAS!.corpo));
    if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
    const { fluxo } = leitura;

    const arquivar = fluxo.passos.find((p) => p.forma !== "fim" && /Arquiv/.test(p.rotulo));
    expect(arquivar, "falta o passo de arquivar a conta").toBeDefined();
    const guia = fluxo.passos.find((p) => /Guia/.test(p.rotulo));
    const retorno = fluxo.ligacoes.find((l) => /Retorno/.test(l.rotulo));
    expect(retorno, "nenhuma ligação diz Retorno").toBeDefined();
    expect(retorno!.para).toBe(guia!.id);
    expect(alcancaveis(fluxo, arquivar!.id).has(retorno!.de)).toBe(true);
  });

  it("o fluxograma passa pela Fila e pelo Guia da faturista", () => {
    const leitura = lerFluxograma(blocoDoFluxograma(CONTAS!.corpo));
    if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
    const rotulos = leitura.fluxo.passos.map((p) => p.rotulo).join("\n");
    expect(rotulos).toMatch(/Fila/);
    expect(rotulos).toMatch(/Guia/);
  });
});
