/**
 * @vitest-environment jsdom
 */

/**
 * O link de voltar no alto das telas do Núcleo (issue #2249, PRD #2247).
 *
 * Toda tela do módulo leva de volta à Visão geral; o caso aberto de uma
 * notificação leva à lista de Notificações. A Visão geral não mostra o link, e
 * a triagem do caso fica com o "Voltar à fila de triagem" que já tem. O
 * conteúdo de cada tela é um dublê: aqui só importa a moldura.
 */
import { cleanup, render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";

import VisaoGeralPage from "./page";
import AgendaPage from "./agenda/page";
import CapacitacoesPage from "./capacitacoes/page";
import ConfiguracaoPage from "./configuracao/page";
import DocumentosPage from "./documentos/page";
import MembrosPage from "./membros/page";
import NotasDoComitePage from "./notas-do-comite/page";
import NotificacoesPage from "./notificacoes/page";
import CasoPage from "./notificacoes/[id]/page";
import TriagemDoCasoPage from "./notificacoes/[id]/triagem/page";
import RecalibracaoPage from "./recalibracao/page";
import ReunioesPage from "./reunioes/page";

const sessao = vi.hoisted(() => ({ participante: null as CurrentParticipante | null }));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante: sessao.participante, loading: false, error: null }),
}));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "caso-1" }) }));

vi.mock("@/components/seguranca-do-paciente/AcaoDeHoje", () => ({ AcaoDeHoje: () => null }));
vi.mock("@/components/seguranca-do-paciente/CasosGraves", () => ({ CasosGraves: () => null }));
vi.mock("@/components/seguranca-do-paciente/AgendaRegulatoria", () => ({ AgendaRegulatoria: () => null }));
vi.mock("@/components/seguranca-do-paciente/CapacitacoesDoNucleo", () => ({ CapacitacoesDoNucleo: () => null }));
vi.mock("@/components/seguranca-do-paciente/QrDaNotificacao", () => ({ QrDaNotificacao: () => null }));
vi.mock("@/components/seguranca-do-paciente/CortesDeFrequencia", () => ({ CortesDeFrequencia: () => null }));
vi.mock("@/components/seguranca-do-paciente/TabelaDePrazos", () => ({ TabelaDePrazos: () => null }));
vi.mock("@/components/seguranca-do-paciente/ConcordanciaDoAgente", () => ({ ConcordanciaDoAgente: () => null }));
vi.mock("@/components/seguranca-do-paciente/DocumentosDoNucleo", () => ({ DocumentosDoNucleo: () => null }));
vi.mock("@/components/seguranca-do-paciente/MembrosDoNucleo", () => ({ MembrosDoNucleo: () => null }));
vi.mock("@/components/seguranca-do-paciente/NotasDoComite", () => ({ NotasDoComite: () => null }));
vi.mock("@/components/seguranca-do-paciente/NotificacoesDoNucleo", () => ({ NotificacoesDoNucleo: () => null }));
vi.mock("@/components/seguranca-do-paciente/RegistroRapido", () => ({ RegistroRapido: () => null }));
vi.mock("@/components/seguranca-do-paciente/CasoDoNucleo", () => ({ CasoDoNucleo: () => null }));
vi.mock("@/components/seguranca-do-paciente/TriagemDoCaso", () => ({ TriagemDoCaso: () => null }));
vi.mock("@/components/seguranca-do-paciente/RecalibracaoDoAgente", () => ({ RecalibracaoDoAgente: () => null }));
vi.mock("@/components/seguranca-do-paciente/ReunioesDoNucleo", () => ({ ReunioesDoNucleo: () => null }));

afterEach(() => {
  cleanup();
  sessao.participante = null;
});

/** Quem abre todas as telas do módulo. */
function entrarComTudo() {
  sessao.participante = {
    id: "p1",
    nome_completo: "Pessoa de Teste",
    email: "pessoa@hsm",
    recursos_nsp: [
      "ver_modulo",
      "painel",
      "calendario",
      "agenda",
      "membros",
      "documentos",
      "capacitacoes",
      "reunioes",
      "casos",
      "triagem",
      "configuracao",
      "notas_do_comite",
      "gerir_nucleo",
    ],
  };
}

const VISAO_GERAL = "Núcleo de Segurança do Paciente";

const TELAS_QUE_VOLTAM_A_VISAO_GERAL: [string, ComponentType][] = [
  ["Documentos", DocumentosPage],
  ["Membros", MembrosPage],
  ["Capacitações", CapacitacoesPage],
  ["Agenda regulatória", AgendaPage],
  ["Reuniões", ReunioesPage],
  ["Notificações", NotificacoesPage],
  ["Configuração", ConfiguracaoPage],
  ["Recalibração", RecalibracaoPage],
  ["Notas do comitê", NotasDoComitePage],
];

describe("o link de voltar nas telas do Núcleo", () => {
  it.each(TELAS_QUE_VOLTAM_A_VISAO_GERAL)("%s mostra o link para a Visão geral", (_nome, Pagina) => {
    entrarComTudo();
    render(<Pagina />);

    expect(screen.getByRole("link", { name: VISAO_GERAL }).getAttribute("href")).toBe("/seguranca-do-paciente");
  });

  it("o caso aberto de uma notificação mostra o link para Notificações", () => {
    entrarComTudo();
    render(<CasoPage />);

    expect(screen.getByRole("link", { name: "Notificações" }).getAttribute("href")).toBe(
      "/seguranca-do-paciente/notificacoes"
    );
    expect(screen.queryByRole("link", { name: VISAO_GERAL })).toBeNull();
  });

  it("a Visão geral não mostra o link", () => {
    entrarComTudo();
    render(<VisaoGeralPage />);

    expect(screen.queryByRole("link", { name: VISAO_GERAL })).toBeNull();
  });

  it("a triagem do caso fica como está, sem o link do alto", () => {
    entrarComTudo();
    render(<TriagemDoCasoPage />);

    expect(screen.queryByRole("link", { name: VISAO_GERAL })).toBeNull();
  });
});
