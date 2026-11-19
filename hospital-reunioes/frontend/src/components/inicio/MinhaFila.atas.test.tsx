/**
 * @vitest-environment jsdom
 */

/**
 * O Início com as Atas e as próximas Reuniões (issue #1936, PRD #1932).
 *
 * O grupo, os dias de espera e o recorte por papel vêm prontos do servidor
 * (`backend/tests/test_inicio_reunioes.py`). Aqui se trava o que a pessoa vê:
 * o grupo "Sem prazo" no fim, com há quantos dias o item espera e o botão que
 * leva à Ata, e o trilho com as próximas Reuniões, com dia, hora e link.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MinhaFila, type InicioDaPessoa, type ItemDoInicio } from "./MinhaFila";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

function item(campos: Partial<ItemDoInicio>): ItemDoInicio {
  return {
    tipo: "pendencia",
    id: "A001",
    titulo: "Treinar a equipe da noite",
    origem: "Reunião de Atendimento, de 28/10/2026.",
    prazo: "2026-11-17",
    chegou_em: "2026-10-28",
    area: "Reuniões",
    acao: "Abrir a Pendência",
    destino: "/pendencias/kanban?highlight=A001",
    acao_de_um_clique: null,
    grupo: "passou_do_prazo",
    dias_de_atraso: 1,
    dias_esperando: null,
    ...campos,
  };
}

const INICIO: InicioDaPessoa = {
  hoje: "2026-11-18",
  frase: { titulo: "Aurora, um prazo seu venceu.", apoio: "Ele espera há 1 dia." },
  contadores: { passou_do_prazo: 1, ate_48_horas: 0, proximos_7_dias: 0 },
  itens: [
    item({}),
    item({
      tipo: "ata_parada",
      id: "R10",
      titulo: "Ata em validação: Reunião de Farmácia",
      origem: "Reunião de Farmácia, de 05/11/2026.",
      prazo: "2026-11-18",
      chegou_em: "2026-11-15",
      acao: "Revisar a Ata",
      destino: "/reunioes/R10",
      grupo: "sem_prazo",
      dias_de_atraso: null,
      dias_esperando: 3,
    }),
    item({
      tipo: "ata_a_assinar",
      id: "R2",
      titulo: "Ata a assinar: Reunião de Enfermagem",
      origem: "Reunião de Enfermagem, de 09/11/2026.",
      prazo: null,
      chegou_em: "2026-11-17",
      acao: "Assinar a Ata",
      destino: "/reunioes/R2",
      grupo: "sem_prazo",
      dias_de_atraso: null,
      dias_esperando: 1,
    }),
  ],
  avisos: [],
  trilho: [
    {
      tipo: "reuniao",
      id: "R31",
      titulo: "Reunião de Diretoria",
      data: "2026-11-18",
      hora: "16:30",
      papel: "participante",
      destino: "/reunioes/R31",
    },
    {
      tipo: "reuniao",
      id: "R35",
      titulo: "Reunião de Qualidade",
      data: "2026-11-20",
      hora: null,
      papel: "facilitador",
      destino: "/reunioes/R35",
    },
  ],
  filas_do_papel: [],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(corpo: InicioDaPessoa = INICIO) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => corpo }) as Response)
  );
  const tela = render(<MinhaFila />);
  await screen.findByText(corpo.frase.titulo);
  return tela;
}

function linha(titulo: string): HTMLElement {
  return screen.getByText(titulo).closest("li") as HTMLElement;
}

describe("o grupo Sem prazo", () => {
  it("vem no fim, depois dos grupos com prazo, com a contagem", async () => {
    await abrir();

    const titulos = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(titulos.slice(0, 2)).toEqual(["Passou do prazo1", "Sem prazo2"]);
  });

  it("a Ata a assinar diz há quantos dias espera e o botão leva à Ata", async () => {
    await abrir();

    const ata = linha("Ata a assinar: Reunião de Enfermagem");
    expect(within(ata).getByText("1")).toBeTruthy();
    expect(within(ata).getByText("dia esperando")).toBeTruthy();
    expect(within(ata).getByText("Reunião de Enfermagem, de 09/11/2026.")).toBeTruthy();
    expect(within(ata).getByRole("link", { name: "Assinar a Ata" }).getAttribute("href")).toBe("/reunioes/R2");
  });

  it("a Ata parada até o terceiro dia mostra os dias de espera, sem atraso e sem vermelho", async () => {
    await abrir();

    const parada = linha("Ata em validação: Reunião de Farmácia");
    expect(within(parada).getByText("3")).toBeTruthy();
    expect(within(parada).getByText("dias esperando")).toBeTruthy();
    expect(within(parada).queryByText(/atraso/)).toBeNull();
    expect(parada.innerHTML).not.toMatch(/text-red-/);
    expect(within(parada).getByRole("link", { name: "Revisar a Ata" }).getAttribute("href")).toBe("/reunioes/R10");
  });
});

describe("o trilho", () => {
  it("mostra as próximas Reuniões com dia, hora e o link para cada uma", async () => {
    await abrir();

    const trilho = screen.getByRole("complementary", { name: "Próximas Reuniões" });
    const reunioes = within(trilho).getAllByRole("link");
    expect(reunioes.map((a) => a.getAttribute("href"))).toEqual(["/reunioes/R31", "/reunioes/R35"]);

    const hoje = reunioes[0];
    expect(within(hoje).getByText("Reunião de Diretoria")).toBeTruthy();
    expect(within(hoje).getByText("Hoje, 18/11, 16:30")).toBeTruthy();
    expect(within(hoje).getByText("Você participa")).toBeTruthy();

    const sexta = reunioes[1];
    expect(within(sexta).getByText("sex, 20/11")).toBeTruthy();
    expect(within(sexta).getByText("Você conduz")).toBeTruthy();
  });

  it("sem Reunião marcada, o trilho diz isso", async () => {
    await abrir({ ...INICIO, trilho: [] });

    const trilho = screen.getByRole("complementary", { name: "Próximas Reuniões" });
    expect(within(trilho).getByText("Nenhuma Reunião marcada.")).toBeTruthy();
  });

  it("sem travessão nem meia-risca", async () => {
    const { container } = await abrir();

    expect(container.textContent).not.toContain(String.fromCharCode(0x2014));
    expect(container.textContent).not.toContain(String.fromCharCode(0x2013));
  });
});
