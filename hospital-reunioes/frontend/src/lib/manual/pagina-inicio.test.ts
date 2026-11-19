/**
 * A página do Início no manual (issue #1947, PRD #1932, ADR 0094 e ADR 0104).
 *
 * Lê o Markdown de verdade, em `public/manual/inicio/pagina.md`, e prova o que
 * a issue promete dele: quem vê a página (quem tem o Início no menu, e a
 * Secretária não tem), o passo a passo de cada tarefa com o print, e o
 * fluxograma do processo do Início, de entrar no app a resolver o item na
 * tela do módulo.
 */

import { describe, expect, it } from "vitest";

import { itensDoMenu } from "@/components/layout/Sidebar";
import { lerFluxograma, ordemDoFluxo, type Fluxo } from "@/components/manual/fluxograma/fluxo";
import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { carregarPaginasDoManual } from "./carregar";
import { imagensCitadas, paginasVisiveis } from "./paginas";

const PAGINAS = carregarPaginasDoManual();
const INICIO = PAGINAS.find((p) => p.modulo === "inicio");

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

const temOInicioNoMenu = (p: CurrentParticipante) => itensDoMenu(p).some((item) => item.href === "/inicio");
const veAPagina = (p: CurrentParticipante) => paginasVisiveis(PAGINAS, p).some((pg) => pg.modulo === "inicio");

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

describe("quem vê a página do Início no manual", () => {
  it.each([
    ["o Facilitador", pessoa({ access_profile: "regular" })],
    ["quem só tem POPs", pessoa({ access_profile: null, perfil_pop: "coordenador" })],
    ["o Super admin", pessoa({ access_profile: "super_admin" })],
  ])("%s tem o Início no menu e vê a página", (_, quem) => {
    expect(temOInicioNoMenu(quem)).toBe(true);
    expect(INICIO?.pasta).toBe("inicio");
    expect(veAPagina(quem)).toBe(true);
  });

  it("a Secretária, que não tem o Início no menu, não vê a página", () => {
    const secretaria = pessoa({ access_profile: "secretaria" });
    expect(temOInicioNoMenu(secretaria)).toBe(false);
    expect(INICIO).toBeDefined();
    expect(veAPagina(secretaria)).toBe(false);
  });

  it("a página do Início é a primeira da lista, como o Início é o primeiro item do menu", () => {
    const lista = paginasVisiveis(PAGINAS, pessoa({ access_profile: "super_admin" }));
    expect(lista[0]?.modulo).toBe("inicio");
  });
});

/** O texto do bloco ```fluxograma da página. */
function blocoDoFluxograma(corpo: string): string {
  const achado = /```fluxograma\n([\s\S]*?)```/.exec(corpo);
  if (!achado) throw new Error("A página não tem o bloco fluxograma.");
  return achado[1];
}

/** O caminho mais curto de um passo a outro, seguindo as ligações, ou null. */
function caminho(fluxo: Fluxo, de: string, ate: string): string[] | null {
  const veioDe = new Map<string, string | null>([[de, null]]);
  const fila = [de];
  while (fila.length) {
    const atual = fila.shift()!;
    if (atual === ate) {
      const volta: string[] = [];
      for (let p: string | null = atual; p !== null; p = veioDe.get(p) ?? null) volta.unshift(p);
      return volta;
    }
    for (const l of fluxo.ligacoes) {
      if (l.de === atual && !veioDe.has(l.para)) {
        veioDe.set(l.para, atual);
        fila.push(l.para);
      }
    }
  }
  return null;
}

describe("o fluxograma do Início", () => {
  const leitura = lerFluxograma(blocoDoFluxograma(INICIO?.corpo ?? ""));
  const fluxo = () => {
    if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
    return leitura.fluxo;
  };
  const achar = (padrao: RegExp) => fluxo().passos.find((p) => padrao.test(p.rotulo));

  it("começa em entrar no app", () => {
    const [primeiro] = ordemDoFluxo(fluxo());
    expect(primeiro.forma).toBe("inicio");
    expect(primeiro.rotulo).toMatch(/^Entrar/);
  });

  it("vai de entrar a resolver na tela do módulo, passando por ler a frase e abrir o item, nesta ordem", () => {
    const [entrar] = ordemDoFluxo(fluxo());
    const frase = achar(/frase/i);
    const abrir = achar(/^Abrir o item/);
    const resolver = achar(/^Resolver na tela do módulo/);
    expect(frase && abrir && resolver, "falta ler a frase, abrir o item ou resolver na tela do módulo").toBeTruthy();

    const percurso = caminho(fluxo(), entrar.id, resolver!.id);
    expect(percurso, "resolver na tela do módulo não se alcança a partir de entrar").not.toBeNull();
    const posicao = (id: string) => percurso!.indexOf(id);
    expect(posicao(frase!.id)).toBeGreaterThan(0);
    expect(posicao(abrir!.id)).toBeGreaterThan(posicao(frase!.id));
    expect(posicao(resolver!.id)).toBeGreaterThan(posicao(abrir!.id));
  });
});

describe("as tarefas da página do Início", () => {
  it.each([["Ver o que tenho para entregar"], ["Abrir um item da Minha Fila"], ["Acompanhar quem responde a você"]])(
    "a tarefa %s tem passos numerados e pelo menos um print",
    (tarefa) => {
      const secao = secoes(INICIO!.corpo).find((s) => s.titulo === tarefa);
      expect(secao, `a página não tem a tarefa "${tarefa}"`).toBeDefined();
      const passos = secao!.texto.match(/^\d+\. /gm) ?? [];
      expect(passos.slice(0, 2)).toEqual(["1. ", "2. "]);
      expect(imagensCitadas(secao!.texto).length).toBeGreaterThan(0);
    }
  );
});
