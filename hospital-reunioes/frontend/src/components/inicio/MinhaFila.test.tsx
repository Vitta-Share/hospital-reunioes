/**
 * @vitest-environment jsdom
 */

/**
 * O Início com a Minha Fila (issue #1934, PRD #1932, ADR 0104).
 *
 * A tela não decide grupo, atraso nem frase: tudo vem do servidor, que tem os
 * testes da regra em `backend/tests/test_inicio.py`. O que se trava aqui é o
 * que a pessoa vê em cada linha (os dias de atraso ou a data, a origem e o
 * botão que abre a tela dona), o aviso de uma fonte que falhou, a faixa
 * escura enquanto há prazo vencido e as regras de texto da casa: vermelho só
 * em texto, sem seta nem chevron, sem travessão e caixa alta (ADR 0080).
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { caixaDoDado } from "@/lib/testes/caixaDoDado";
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
    prazo: "2026-11-09",
    chegou_em: "2026-10-28",
    area: "Reuniões",
    acao: "Abrir a Pendência",
    destino: "/pendencias/kanban?highlight=A001",
    acao_de_um_clique: null,
    grupo: "passou_do_prazo",
    dias_de_atraso: 9,
    ...campos,
  };
}

const COM_ATRASO: InicioDaPessoa = {
  hoje: "2026-11-18",
  frase: { titulo: "Aurora, dois prazos seus venceram.", apoio: "O mais antigo espera há 9 dias." },
  contadores: { passou_do_prazo: 2, ate_48_horas: 1, proximos_7_dias: 1 },
  itens: [
    item({}),
    item({
      tipo: "lembrete_da_agenda",
      id: "A020",
      titulo: "Agenda regulatória: relatório trimestral",
      origem: "Lembrete da Agenda regulatória do Núcleo.",
      prazo: "2026-11-17",
      area: "Segurança do Paciente",
      acao: "Abrir na agenda",
      destino: "/seguranca-do-paciente/agenda",
      dias_de_atraso: 1,
    }),
    item({ id: "A003", titulo: "Assinar a escala", prazo: "2026-11-18", grupo: "ate_48_horas", dias_de_atraso: null }),
    item({ id: "A004", titulo: "Revisar o POP", prazo: "2026-11-20", grupo: "proximos_7_dias", dias_de_atraso: null }),
    item({ id: "A005", titulo: "Planejar 2027", prazo: "2027-01-10", grupo: null, dias_de_atraso: null }),
  ],
  avisos: [],
  trilho: [],
  filas_do_papel: [],
};

function servidor(corpo: InicioDaPessoa, status = 200) {
  const chamadas: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      chamadas.push(url);
      return { ok: status < 300, status, json: async () => corpo } as Response;
    })
  );
  return chamadas;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(corpo: InicioDaPessoa = COM_ATRASO) {
  const chamadas = servidor(corpo);
  const tela = render(<MinhaFila />);
  await screen.findByText(corpo.frase.titulo);
  return { ...tela, chamadas };
}

function linha(titulo: string): HTMLElement {
  return screen.getByText(titulo).closest("li") as HTMLElement;
}

describe("a abertura", () => {
  it("lê o Início da pessoa e mostra a frase, o apoio e os três contadores", async () => {
    const { chamadas } = await abrir();

    expect(chamadas).toEqual(["/api/inicio"]);
    expect(screen.getByText("O mais antigo espera há 9 dias.")).toBeTruthy();
    const resumo = screen.getByRole("list", { name: "Resumo dos prazos" });
    expect(within(resumo).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "2prazos vencidos",
      "1vence em até 48 horas",
      "1nos próximos 7 dias",
    ]);
  });

  it("fica na faixa azul-marinho escura enquanto há prazo vencido", async () => {
    await abrir();
    expect(screen.getByTestId("abertura").className).toContain("bg-primary-dark");
  });

  it("sem prazo vencido, a abertura fica clara", async () => {
    await abrir({
      ...COM_ATRASO,
      frase: { titulo: "Aurora, nada atrasado.", apoio: "Um prazo vence em até 48 horas." },
      contadores: { passou_do_prazo: 0, ate_48_horas: 1, proximos_7_dias: 0 },
      itens: [item({ grupo: "ate_48_horas", prazo: "2026-11-19", dias_de_atraso: null })],
    });
    expect(screen.getByTestId("abertura").className).not.toContain("bg-primary-dark");
  });
});

describe("os grupos e as linhas", () => {
  it("mostra os três grupos em ordem, com a contagem, e deixa de fora o que não tem grupo", async () => {
    await abrir();

    const titulos = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(titulos).toEqual(["Passou do prazo2", "Vence em até 48 horas1", "Próximos 7 dias1"]);
    expect(screen.queryByText("Planejar 2027")).toBeNull();
  });

  it("a linha vencida diz os dias de atraso, a origem, a área e o botão que abre o quadro já destacado", async () => {
    await abrir();

    const vencida = linha("Treinar a equipe da noite");
    expect(within(vencida).getByText("9")).toBeTruthy();
    expect(within(vencida).getByText("dias de atraso")).toBeTruthy();
    expect(within(vencida).getByText("Reunião de Atendimento, de 28/10/2026.")).toBeTruthy();
    expect(within(vencida).getByText("Reuniões")).toBeTruthy();
    const botao = within(vencida).getByRole("link", { name: "Abrir a Pendência" });
    expect(botao.getAttribute("href")).toBe("/pendencias/kanban?highlight=A001");
  });

  it("um dia de atraso fica no singular", async () => {
    await abrir();
    expect(within(linha("Agenda regulatória: relatório trimestral")).getByText("dia de atraso")).toBeTruthy();
  });

  it("a Pendência sem Reunião abre a Agenda regulatória do Núcleo", async () => {
    await abrir();

    const lembrete = linha("Agenda regulatória: relatório trimestral");
    const botao = within(lembrete).getByRole("link", { name: "Abrir na agenda" });
    expect(botao.getAttribute("href")).toBe("/seguranca-do-paciente/agenda");
    expect(within(lembrete).getByText("Lembrete da Agenda regulatória do Núcleo.")).toBeTruthy();
  });

  it("a linha que não venceu mostra a data: hoje, ou o dia da semana e a data", async () => {
    await abrir();

    const deHoje = linha("Assinar a escala");
    expect(within(deHoje).getByText("Hoje")).toBeTruthy();
    expect(within(deHoje).getByText("18/11")).toBeTruthy();
    const daSemana = linha("Revisar o POP");
    expect(within(daSemana).getByText("sex")).toBeTruthy();
    expect(within(daSemana).getByText("20/11")).toBeTruthy();
  });

  it("sem nada nos três grupos, diz que não há prazo por perto", async () => {
    await abrir({
      ...COM_ATRASO,
      frase: { titulo: "Aurora, você está em dia.", apoio: "O próximo prazo é 10/01." },
      contadores: { passou_do_prazo: 0, ate_48_horas: 0, proximos_7_dias: 0 },
      itens: [item({ grupo: null, prazo: "2027-01-10", dias_de_atraso: null })],
    });

    expect(screen.getByText("Nada vencido e nada para os próximos 7 dias.")).toBeTruthy();
    expect(screen.queryAllByRole("heading", { level: 2 })).toHaveLength(0);
  });
});

describe("a fonte que falhou", () => {
  it("mostra o aviso daquela fonte e segue com o resto", async () => {
    await abrir({
      ...COM_ATRASO,
      avisos: [
        {
          fonte: "pendencias",
          mensagem: "Não foi possível carregar as Pendências agora. Tente de novo em instantes.",
        },
      ],
    });

    const aviso = screen.getByRole("status");
    expect(aviso.textContent).toContain("Não foi possível carregar as Pendências agora.");
    expect(screen.getByText("Treinar a equipe da noite")).toBeTruthy();
  });

  it("quando a rota inteira falha, diz que não abriu", async () => {
    servidor(COM_ATRASO, 500);
    render(<MinhaFila />);
    expect(await screen.findByText("Não foi possível abrir o seu Início agora. Tente de novo em instantes.")).toBeTruthy();
  });
});

describe("as regras de texto da casa", () => {
  it("vermelho só em texto: nenhum fundo nem borda vermelha", async () => {
    const { container } = await abrir();

    const classes = Array.from(container.querySelectorAll("[class]")).map((el) => el.getAttribute("class") ?? "");
    expect(classes.filter((c) => /\b(bg|border|ring)-red-/.test(c))).toEqual([]);
    expect(classes.some((c) => /\btext-red-/.test(c))).toBe(true);
  });

  it("sem seta nem chevron inline", async () => {
    const { container } = await abrir();

    expect(container.querySelector("[class*='lucide-arrow'], [class*='lucide-chevron']")).toBeNull();
    expect(container.textContent).not.toMatch(/[→›»]/);
  });

  it("sem travessão nem meia-risca", async () => {
    const { container } = await abrir();

    expect(container.textContent).not.toContain(String.fromCharCode(0x2014));
    expect(container.textContent).not.toContain(String.fromCharCode(0x2013));
  });

  it("caixa alta no título, nos grupos, na etiqueta da área e no botão; o título do item como foi escrito", async () => {
    await abrir();

    // h1 e h2 são caixa alta pela regra base do globals.css.
    expect(screen.getByRole("heading", { level: 1, name: "Início" })).toBeTruthy();
    const vencida = linha("Treinar a equipe da noite");
    expect(within(vencida).getByText("Reuniões").classList.contains("etiqueta")).toBe(true);
    expect(caixaDoDado(within(vencida).getByRole("link", { name: "Abrir a Pendência" }))).toBe("uppercase");
    expect(caixaDoDado(within(vencida).getByText("Treinar a equipe da noite"))).toBeNull();
  });
});
