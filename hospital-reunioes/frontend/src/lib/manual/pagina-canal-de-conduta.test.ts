/**
 * A página do Canal de Conduta no manual (issue #1851, PRD #1786; ADR 0094,
 * decisões 4 a 6).
 *
 * Lê o Markdown de verdade, em `public/manual/canal-de-conduta/pagina.md`, e
 * prova o que a issue promete dele: a página é de quem trata os casos, cada
 * tarefa do Comitê tem passo a passo com print, e o fluxograma mostra os
 * quatro ritos.
 */

import { describe, expect, it } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { lerFluxograma, ordemDoFluxo, type Fluxo } from "@/components/manual/fluxograma/fluxo";
import { carregarPaginasDoManual } from "./carregar";
import { imagensCitadas, paginasVisiveis } from "./paginas";

const PAGINAS = carregarPaginasDoManual();
const CONDUTA = PAGINAS.find((p) => p.modulo === "canal-de-conduta");

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

const modulos = (p: CurrentParticipante) => paginasVisiveis(PAGINAS, p).map((pagina) => pagina.modulo);

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

const secao = (titulo: string) => secoes(CONDUTA?.corpo ?? "").find((s) => s.titulo === titulo);

/** O fluxograma da página, já lido. */
function fluxograma(): Fluxo {
  const achado = /```fluxograma\n([\s\S]*?)```/.exec(CONDUTA?.corpo ?? "");
  if (!achado) throw new Error("A página não tem o bloco fluxograma.");
  const leitura = lerFluxograma(achado[1]);
  if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
  return leitura.fluxo;
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

describe("a página do Canal de Conduta no manual", () => {
  it("existe e aparece para quem está no Comitê de Conduta", () => {
    expect(CONDUTA?.pasta).toBe("canal-de-conduta");
    expect(modulos(pessoa({ ve_membros_do_comite: true }))).toContain("canal-de-conduta");
  });

  it("não aparece para quem não é do Comitê, nem para o super admin sem lugar nele", () => {
    expect(modulos(pessoa({ ve_membros_do_comite: false }))).not.toContain("canal-de-conduta");
    expect(modulos(pessoa({ access_profile: "super_admin" }))).not.toContain("canal-de-conduta");
  });

  it.each([
    ["Confirmar a triagem"],
    ["Registrar um depoimento"],
    ["Votar"],
    ["Assinar a ata"],
    ["Enviar à Direção"],
    ["Arquivar o papel"],
  ])("a tarefa %s tem passos numerados e pelo menos um print", (tarefa) => {
    const achada = secao(tarefa);
    expect(achada, `a página não tem a tarefa "${tarefa}"`).toBeDefined();
    const passos = achada!.texto.match(/^\d+\. /gm) ?? [];
    expect(passos.slice(0, 2)).toEqual(["1. ", "2. "]);
    expect(imagensCitadas(achada!.texto).length).toBeGreaterThan(0);
  });

  it("o fluxograma lê sem erro, começa no relato e chega ao fim de cada um dos quatro ritos", () => {
    const fluxo = fluxograma();
    const [primeiro] = ordemDoFluxo(fluxo);
    expect(primeiro.forma).toBe("inicio");
    expect(primeiro.rotulo).toMatch(/relato/i);

    const alcance = alcancaveis(fluxo, primeiro.id);
    for (const rito of [/encaminhamento/i, /r[áa]pido/i, /completo/i, /rota especial/i]) {
      const passo = fluxo.passos.find((p) => rito.test(p.rotulo));
      expect(passo, `falta o rito ${rito}`).toBeDefined();
      expect(alcance.has(passo!.id), `o rito ${rito} não se alcança do relato`).toBe(true);
    }
    const fins = fluxo.passos.filter((p) => p.forma === "fim");
    expect(fins.length).toBeGreaterThanOrEqual(2);
    expect(fins.every((fim) => alcance.has(fim.id))).toBe(true);
  });

  it("o fluxograma diz o prazo de cada rito", () => {
    const textos = fluxograma()
      .passos.map((p) => `${p.rotulo} ${p.detalhe}`)
      .join("\n");
    expect(textos).toMatch(/5 dias úteis/);
    expect(textos).toMatch(/20 dias corridos/);
    expect(textos).toMatch(/30 dias corridos/);
    expect(textos).toMatch(/60 dias corridos/);
  });

  it("a página não tem travessão nem meia-risca", () => {
    expect(CONDUTA!.corpo).not.toMatch(/[\u2013\u2014]/);
  });
});
