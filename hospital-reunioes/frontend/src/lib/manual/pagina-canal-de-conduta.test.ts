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
import { carregarPaginasDoManual } from "./carregar";
import { paginasVisiveis } from "./paginas";

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

describe("a página do Canal de Conduta no manual", () => {
  it("existe e aparece para quem está no Comitê de Conduta", () => {
    expect(CONDUTA?.pasta).toBe("canal-de-conduta");
    expect(modulos(pessoa({ ve_membros_do_comite: true }))).toContain("canal-de-conduta");
  });

  it("não aparece para quem não é do Comitê, nem para o super admin sem lugar nele", () => {
    expect(modulos(pessoa({ ve_membros_do_comite: false }))).not.toContain("canal-de-conduta");
    expect(modulos(pessoa({ access_profile: "super_admin" }))).not.toContain("canal-de-conduta");
  });
});
