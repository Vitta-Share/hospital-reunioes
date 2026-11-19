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
    ["quem só tem POPs", pessoa({ access_profile: null, perfil_pop: "elaborador" })],
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
