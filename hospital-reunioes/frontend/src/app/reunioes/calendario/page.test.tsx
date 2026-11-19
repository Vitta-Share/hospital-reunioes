/**
 * @vitest-environment jsdom
 */

/**
 * O Calendário leva a Secretária para a tela Nova reunião (issue #761).
 *
 * O modal "Agendar Reunião" não pergunta quem facilita, e o backend fazia de
 * quem agenda o facilitador: a Secretária criava reunião que ela mesma não
 * conduz. Para ela, todo gesto de CRIAR (o botão, o clique no dia e o clique no
 * slot da semana) vai para `/secretaria/nova` com a data e a hora. Para os
 * outros perfis o modal continua, e ver os eventos não muda para ninguém.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";

import CalendarioPage from "./page";

const perfil = vi.hoisted(() => ({
  participante: null as Record<string, unknown> | null,
  loading: false,
  error: null as string | null,
}));
const navegacao = vi.hoisted(() => ({ empurrou: [] as string[] }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: (url: string) => navegacao.empurrou.push(url), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante: perfil.participante, loading: perfil.loading, error: perfil.error }),
}));

vi.mock("@/hooks/useFacilitadores", () => ({
  useFacilitadores: () => ({ facilitadores: [], loading: false }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "tok" } } }) },
  }),
}));

const SECRETARIA = { id: "P_SECRE", nome_completo: "Secretária", email: "s@hsm.com", access_profile: "secretaria" };
const FACILITADOR = { id: "P_FACIL", nome_completo: "Facilitador", email: "f@hsm.com", access_profile: "regular" };

// Terça, 10 de novembro de 2026: a semana vai de 8 a 14.
const HOJE = new Date(2026, 10, 10, 8, 0, 0);

function montar() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => [] }) as unknown as Response),
  );
  return render(
    <ToastProvider>
      <CalendarioPage />
    </ToastProvider>,
  );
}

function modalAberto() {
  return screen.queryByRole("heading", { name: "Agendar Reunião" }) !== null;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(HOJE);
  navegacao.empurrou = [];
  perfil.loading = false;
  perfil.error = null;
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("Secretária no Calendário", () => {
  beforeEach(() => {
    perfil.participante = SECRETARIA;
  });

  it("o botão Agendar Reunião leva para a Nova reunião com a data de hoje", async () => {
    montar();

    fireEvent.click(screen.getByRole("button", { name: /Agendar Reunião/ }));

    expect(navegacao.empurrou).toEqual(["/secretaria/nova?data=2026-11-10"]);
    expect(modalAberto()).toBe(false);
  });

  it("o clique no dia leva para a Nova reunião com aquela data", async () => {
    montar();

    fireEvent.click(screen.getByTestId("dia-2026-11-20"));

    expect(navegacao.empurrou).toEqual(["/secretaria/nova?data=2026-11-20"]);
    expect(modalAberto()).toBe(false);
  });

  it("o clique no slot da semana leva a data e a hora", async () => {
    montar();
    fireEvent.click(screen.getByRole("button", { name: /Semanal/ }));

    fireEvent.click(await screen.findByTestId("slot-2026-11-12-14:00"));

    expect(navegacao.empurrou).toEqual(["/secretaria/nova?data=2026-11-12&hora=14%3A00"]);
    expect(modalAberto()).toBe(false);
  });
});

describe("Outros perfis no Calendário", () => {
  beforeEach(() => {
    perfil.participante = FACILITADOR;
  });

  it("o botão abre o modal como sempre", async () => {
    montar();

    fireEvent.click(screen.getByRole("button", { name: /Agendar Reunião/ }));

    await waitFor(() => expect(modalAberto()).toBe(true));
    expect(navegacao.empurrou).toEqual([]);
  });

  it("o clique no dia abre o modal como sempre", async () => {
    montar();

    fireEvent.click(screen.getByTestId("dia-2026-11-20"));

    await waitFor(() => expect(modalAberto()).toBe(true));
    expect(navegacao.empurrou).toEqual([]);
  });

  it("o clique no slot abre o modal como sempre", async () => {
    montar();
    fireEvent.click(screen.getByRole("button", { name: /Semanal/ }));

    fireEvent.click(await screen.findByTestId("slot-2026-11-12-14:00"));

    await waitFor(() => expect(modalAberto()).toBe(true));
    expect(navegacao.empurrou).toEqual([]);
  });
});

// Issue #890: enquanto o perfil carrega (ou se a busca falha), a tela não sabe
// se quem clica é a Secretária. Antes ela abria o modal, e a Secretária levava
// 422 numa janela sem o campo Facilitador. Agora nenhum gesto de criar responde.
describe("Perfil ainda carregando", () => {
  beforeEach(() => {
    perfil.participante = null;
    perfil.loading = true;
  });

  it("o botão fica desabilitado e não abre nem navega", async () => {
    montar();
    const botao = screen.getByRole("button", { name: /Agendar Reunião/ });

    fireEvent.click(botao);

    expect(botao).toHaveProperty("disabled", true);
    expect(modalAberto()).toBe(false);
    expect(navegacao.empurrou).toEqual([]);
  });

  it("o clique no dia não abre nem navega", async () => {
    montar();

    fireEvent.click(screen.getByTestId("dia-2026-11-20"));

    expect(modalAberto()).toBe(false);
    expect(navegacao.empurrou).toEqual([]);
  });

  it("o clique no slot da semana não abre nem navega", async () => {
    montar();
    fireEvent.click(screen.getByRole("button", { name: /Semanal/ }));

    fireEvent.click(await screen.findByTestId("slot-2026-11-12-14:00"));

    expect(modalAberto()).toBe(false);
    expect(navegacao.empurrou).toEqual([]);
  });

  it("se a busca do perfil falha, continua sem abrir", async () => {
    perfil.loading = false;
    perfil.error = "falhou";
    montar();

    fireEvent.click(screen.getByTestId("dia-2026-11-20"));

    expect(modalAberto()).toBe(false);
    expect(navegacao.empurrou).toEqual([]);
  });
});

describe("Legenda de estados", () => {
  beforeEach(() => {
    perfil.participante = FACILITADOR;
  });

  it("mostra a situação Não instalada, da reunião do Núcleo sem quórum (issue #1774)", () => {
    montar();

    const legenda = screen.getByRole("list", { name: "Legenda de estados" });
    expect(within(legenda).getByText("Não instalada")).toBeTruthy();
  });
});

// Issue #1860: as Reuniões de um dia aparecem pela hora de início, em todas as
// visões, e o título longo que o bloco corta aparece inteiro no balão do hover.
describe("Reuniões do dia", () => {
  beforeEach(() => {
    perfil.participante = FACILITADOR;
  });

  function evento(id: string, hora_inicio: string, titulo: string) {
    return {
      id_reuniao: id,
      data: "2026-11-12",
      hora_inicio,
      tipo: "Diretoria",
      titulo,
      objetivo: null,
      status_ata: "PROGRAMADA",
      facilitador_id: "P_FACIL",
      participantes: [],
    };
  }

  function montarComEventos(eventos: unknown[]) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, status: 200, json: async () => eventos }) as unknown as Response),
    );
    return render(
      <ToastProvider>
        <CalendarioPage />
      </ToastProvider>,
    );
  }

  // A API devolve na ordem que quiser; aqui, 14h antes de 8h e 10h.
  const FORA_DE_ORDEM = [
    evento("R14", "14:00:00", "Reunião das catorze"),
    evento("R08", "08:00:00", "Reunião das oito"),
    evento("R10", "10:00:00", "Reunião das dez"),
  ];

  function titulosNaOrdem(container: HTMLElement) {
    return Array.from(container.querySelectorAll("a[href^='/reunioes/']")).map(
      (a) => a.querySelector("span")?.textContent,
    );
  }

  it("no mês, o dia mostra 8h, 10h e 14h, nessa ordem", async () => {
    montarComEventos(FORA_DE_ORDEM);
    const dia = screen.getByTestId("dia-2026-11-12");
    await within(dia).findByText("Reunião das oito");

    expect(titulosNaOrdem(dia)).toEqual(["Reunião das oito", "Reunião das dez", "Reunião das catorze"]);
  });

  it("no mês, o dia com mais de três reuniões mostra as três mais cedo", async () => {
    montarComEventos([...FORA_DE_ORDEM, evento("R09", "09:30:00", "Reunião das nove")]);
    const dia = screen.getByTestId("dia-2026-11-12");
    await within(dia).findByText("Reunião das oito");

    expect(titulosNaOrdem(dia)).toEqual(["Reunião das oito", "Reunião das nove", "Reunião das dez"]);
  });

  it("na semana, a mesma hora mostra a reunião mais cedo primeiro", async () => {
    montarComEventos([
      evento("R1045", "10:45:00", "Reunião das dez e quarenta"),
      evento("R1015", "10:15:00", "Reunião das dez e quinze"),
    ]);
    fireEvent.click(screen.getByRole("button", { name: /Semanal/ }));
    const slot = await screen.findByTestId("slot-2026-11-12-10:00");
    await within(slot).findByText("Reunião das dez e quinze");

    expect(titulosNaOrdem(slot)).toEqual(["Reunião das dez e quinze", "Reunião das dez e quarenta"]);
  });
});
