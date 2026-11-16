/**
 * @vitest-environment jsdom
 */

/**
 * As telas da primeira fase de Segurança do Paciente (issue #1765, PRD #1764).
 *
 * Cada tela abre com uma linha dizendo o que fazer ali (seção 17 da
 * especificação), título em h1 (a regra base da Caixa alta põe em maiúsculas,
 * ADR 0080) e, enquanto a fatia dela não chega, o estado vazio. Quem não tem o
 * recurso da tela vê a recusa, e não a tela.
 *
 * jsdom não mede largura. O que segura a tela a 375 px aqui é não ter largura
 * fixa nenhuma e o texto curto: a orientação numa frase só, os passos do
 * "Como funciona" com uma frase cada.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";

import InicioPage from "./page";
import AgendaPage from "./agenda/page";
import CapacitacoesPage from "./capacitacoes/page";
import DocumentosPage from "./documentos/page";
import MembrosPage from "./membros/page";
import ReunioesPage from "./reunioes/page";

const sessao = vi.hoisted(() => ({
  participante: null as CurrentParticipante | null,
}));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({
    participante: sessao.participante,
    loading: false,
    error: null,
  }),
}));

// A agenda tem conteúdo e teste próprios (`AgendaRegulatoria.test.tsx`).
vi.mock("@/components/seguranca-do-paciente/AgendaRegulatoria", () => ({
  AgendaRegulatoria: () => <p>Conteúdo da agenda</p>,
}));

// As capacitações chamam a API (issue #1778) e têm teste próprio, ao lado do
// componente. Aqui só importa que a tela Capacitações as mostra.
vi.mock("@/components/seguranca-do-paciente/CapacitacoesDoNucleo", () => ({
  CapacitacoesDoNucleo: () => <p>Conteúdo das capacitações</p>,
}));

// A lista dos membros chama a API (issue #1766) e tem teste próprio, ao lado
// do componente. Aqui só importa que a tela Membros a mostra.
vi.mock("@/components/seguranca-do-paciente/MembrosDoNucleo", () => ({
  MembrosDoNucleo: () => <p>Lista dos membros</p>,
}));

// As telas Documentos (issue #1767) e Reuniões (issue #1772) já têm conteúdo e
// pedem a lista ao servidor; aqui só importa a moldura, e as listas voltam vazias.
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            documentos: [],
            reunioes: [],
            tipos: [],
            pode_abrir: false,
            pode_criar: false,
          })
        )
    )
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessao.participante = null;
});

const TODOS = [
  "ver_modulo",
  "painel",
  "calendario",
  "agenda",
  "membros",
  "documentos",
  "capacitacoes",
  "reunioes",
  "casos",
];
const SEM_TERMO = ["ver_modulo", "painel", "calendario", "agenda"];

function entrar(recursos: string[]) {
  sessao.participante = {
    id: "p1",
    nome_completo: "Pessoa de Teste",
    email: "pessoa@hsm",
    recursos_nsp: recursos,
  };
}

const TELAS = [
  {
    nome: "Início",
    Pagina: InicioPage,
    titulo: "Segurança do Paciente",
    orientacao: "O que precisa de você hoje vem primeiro. O resto é acompanhamento.",
  },
  {
    nome: "Reuniões",
    Pagina: ReunioesPage,
    titulo: "Reuniões do Núcleo",
    orientacao: "A pauta é montada pelo sistema. Depois da reunião, importe a transcrição e revise a ata.",
  },
  {
    nome: "Membros",
    Pagina: MembrosPage,
    titulo: "Membros",
    orientacao: "Quem compõe o Núcleo, até quando, e quem ainda precisa assinar.",
  },
  {
    nome: "Documentos",
    Pagina: DocumentosPage,
    titulo: "Documentos",
    orientacao: "A versão vigente de cada documento e as anteriores.",
  },
  {
    nome: "Capacitações",
    Pagina: CapacitacoesPage,
    titulo: "Capacitações",
    orientacao: "As capacitações do Núcleo e quem confirmou presença.",
  },
  {
    nome: "Agenda regulatória",
    Pagina: AgendaPage,
    titulo: "Agenda regulatória",
    orientacao: "O que a vigilância sanitária cobra do hospital, e até quando.",
  },
] as const;

describe("as telas do módulo", () => {
  it.each(TELAS)("$nome abre com o título e a linha de orientação", ({ Pagina, titulo, orientacao }) => {
    entrar(TODOS);
    render(<Pagina />);

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(titulo);
    expect(screen.getByText(orientacao).tagName).toBe("P");
  });

  // Toda tela do grupo Núcleo já tem conteúdo (issues #1766, #1767, #1772,
  // #1778 e #1779): o estado vazio não aparece em nenhuma.
  it.each(TELAS)("$nome não mostra o estado vazio", ({ Pagina }) => {
    entrar(TODOS);
    render(<Pagina />);

    expect(screen.queryByText("Nada por aqui ainda.")).toBeNull();
  });

  it("Capacitações mostra as capacitações, e não o estado vazio (issue #1778)", () => {
    entrar(TODOS);
    render(<CapacitacoesPage />);

    expect(screen.getByText("Conteúdo das capacitações")).toBeTruthy();
  });

  it("Documentos mostra os documentos do Núcleo, e não o estado vazio (issue #1767)", async () => {
    entrar(TODOS);
    render(<DocumentosPage />);

    expect(await screen.findByText("Nenhum documento publicado ainda.")).toBeTruthy();
    expect(screen.queryByText("Nada por aqui ainda.")).toBeNull();
  });

  it.each([
    ["a Presidência", [...TODOS, "gerir_nucleo"], true],
    ["o membro", TODOS, false],
  ] as const)("em Documentos, %s vê o botão de publicar: %s", async (_quem, recursos, ve) => {
    entrar([...recursos]);
    render(<DocumentosPage />);

    await screen.findByText("Nenhum documento publicado ainda.");
    expect(screen.queryByRole("button", { name: "Publicar versão nova" }) !== null).toBe(ve);
  });

  it("Membros mostra a lista dos membros, e não o estado vazio", () => {
    entrar(TODOS);
    render(<MembrosPage />);

    expect(screen.getByText("Lista dos membros")).toBeTruthy();
    expect(screen.queryByText("Nada por aqui ainda.")).toBeNull();
  });

  it("a Agenda regulatória mostra a agenda, e não o estado vazio", () => {
    entrar(TODOS);
    render(<AgendaPage />);

    expect(screen.getByText("Conteúdo da agenda")).toBeTruthy();
    expect(screen.queryByText("Nada por aqui ainda.")).toBeNull();
  });

  it("o Início explica como funciona o Núcleo em seis passos curtos", () => {
    entrar(TODOS);
    render(<InicioPage />);

    const passos = within(screen.getByRole("list", { name: "Como funciona o Núcleo" })).getAllByRole("listitem");
    expect(passos).toHaveLength(6);
    for (const passo of passos) {
      expect(passo.textContent!.length).toBeLessThanOrEqual(90);
    }
  });
});

describe("quem não tem o recurso da tela", () => {
  it.each([
    ["Membros", MembrosPage],
    ["Documentos", DocumentosPage],
    ["Capacitações", CapacitacoesPage],
  ] as const)("o membro sem Termo vê a recusa em %s, e não a tela", (_nome, Pagina) => {
    entrar(SEM_TERMO);
    render(<Pagina />);

    expect(screen.getByText("Esta tela ainda não está liberada para você.")).toBeTruthy();
    expect(screen.queryByText("Nada por aqui ainda.")).toBeNull();
    expect(screen.queryByText("Lista dos membros")).toBeNull();
    expect(screen.queryByText("Conteúdo das capacitações")).toBeNull();
  });

  it.each([
    ["Início", InicioPage],
    ["Agenda regulatória", AgendaPage],
    ["Reuniões", ReunioesPage],
  ] as const)("o membro sem Termo abre %s (painel, calendário e agenda)", (_nome, Pagina) => {
    entrar(SEM_TERMO);
    render(<Pagina />);

    expect(screen.queryByText("Esta tela ainda não está liberada para você.")).toBeNull();
  });
});

describe("o texto das telas", () => {
  const PASTAS = [resolve(process.cwd(), "src/app/seguranca-do-paciente"), resolve(process.cwd(), "src/components/seguranca-do-paciente")];

  function arquivos(pasta: string): string[] {
    return readdirSync(pasta).flatMap((nome) => {
      const caminho = join(pasta, nome);
      if (statSync(caminho).isDirectory()) return arquivos(caminho);
      return /\.tsx?$/.test(nome) && !nome.endsWith(".test.tsx") ? [caminho] : [];
    });
  }

  it("o detector acha os arquivos das telas (piso)", () => {
    expect(PASTAS.flatMap(arquivos).length).toBeGreaterThanOrEqual(7);
  });

  it("nenhuma largura fixa, que quebraria a tela a 375 px", () => {
    for (const caminho of PASTAS.flatMap(arquivos)) {
      expect(readFileSync(caminho, "utf8")).not.toMatch(/\b(?:min-)?w-\[\d+px\]/);
    }
  });

  it("sem travessão nem meia-risca", () => {
    for (const caminho of PASTAS.flatMap(arquivos)) {
      const texto = readFileSync(caminho, "utf8");
      expect(texto.includes(String.fromCharCode(0x2014)), caminho).toBe(false);
      expect(texto.includes(String.fromCharCode(0x2013)), caminho).toBe(false);
    }
  });
});
