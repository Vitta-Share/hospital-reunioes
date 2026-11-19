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
    const botao = within(vencida).getByRole("link", { name: /^Abrir a Pendência/ });
    expect(botao.getAttribute("href")).toBe("/pendencias/kanban?highlight=A001");
  });

  it("um dia de atraso fica no singular", async () => {
    await abrir();
    expect(within(linha("Agenda regulatória: relatório trimestral")).getByText("dia de atraso")).toBeTruthy();
  });

  it("a Pendência sem Reunião abre a Agenda regulatória do Núcleo", async () => {
    await abrir();

    const lembrete = linha("Agenda regulatória: relatório trimestral");
    const botao = within(lembrete).getByRole("link", { name: /^Abrir na agenda/ });
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
    expect(caixaDoDado(within(vencida).getByRole("link", { name: /^Abrir a Pendência/ }))).toBe("uppercase");
    expect(caixaDoDado(within(vencida).getByText("Treinar a equipe da noite"))).toBeNull();
  });
});

/** Quem pede menos movimento: o `matchMedia` que o jsdom não tem, dublado. */
function comMovimentoReduzido() {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((consulta: string) => ({
      matches: consulta === "(prefers-reduced-motion: reduce)",
      media: consulta,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
  );
}

/** As classes de um elemento, uma por item. */
function classes(el: Element): string[] {
  return (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
}

const EM_DIA: InicioDaPessoa = {
  ...COM_ATRASO,
  frase: { titulo: "Aurora, você está em dia.", apoio: "O próximo prazo é 20/11." },
  contadores: { passou_do_prazo: 0, ate_48_horas: 0, proximos_7_dias: 1 },
  itens: [
    item({ id: "A004", titulo: "Revisar o POP", prazo: "2026-11-20", grupo: "proximos_7_dias", dias_de_atraso: null }),
  ],
};

describe("o acabamento do protótipo (issue #1935)", () => {
  it("no hover e no foco a linha ganha fundo, o botão fica preenchido e o contexto aparece; na tela de toque o contexto fica sempre à vista", async () => {
    await abrir({
      ...COM_ATRASO,
      itens: COM_ATRASO.itens.map((i) => (i.id === "A003" ? { ...i, contexto: "Em andamento. Aberta em 01/11/2026." } : i)),
    });

    const deHoje = linha("Assinar a escala");
    expect(classes(deHoje)).toEqual(expect.arrayContaining(["group", "hover:bg-slate-50", "focus-within:bg-slate-50"]));
    const contexto = within(deHoje).getByText("Em andamento. Aberta em 01/11/2026.");
    expect(classes(contexto)).toEqual(
      expect.arrayContaining(["hidden", "group-hover:block", "group-focus-within:block", "[@media(hover:none)]:block"])
    );
    const botao = within(deHoje).getByRole("link", { name: /^Abrir a Pendência/ });
    expect(classes(botao)).toEqual(
      expect.arrayContaining(["bg-white", "group-hover:bg-primary", "group-hover:text-white", "group-focus-within:bg-primary"])
    );
  });

  it("sem contexto, a linha não ganha um parágrafo vazio", async () => {
    await abrir();
    const deHoje = linha("Assinar a escala");
    expect(Array.from(deHoje.querySelectorAll("p")).map((p) => p.textContent)).toEqual([
      "Assinar a escala",
      "Reunião de Atendimento, de 28/10/2026.",
    ]);
  });

  it("o grupo vencido entra uma vez, ao abrir, uma linha depois da outra; os outros grupos não se mexem", async () => {
    await abrir();

    const vencidas = [linha("Treinar a equipe da noite"), linha("Agenda regulatória: relatório trimestral")];
    expect(vencidas.map((li) => classes(li).includes("animate-fade-in-up"))).toEqual([true, true]);
    expect(vencidas.map((li) => li.style.animationDelay)).toEqual(["0ms", "70ms"]);
    expect(classes(linha("Assinar a escala"))).not.toContain("animate-fade-in-up");
    expect(classes(linha("Revisar o POP"))).not.toContain("animate-fade-in-up");
  });

  it("com movimento reduzido nada entra animado", async () => {
    comMovimentoReduzido();
    const { container } = await abrir();
    expect(container.querySelectorAll("[class*='animate-']")).toHaveLength(0);
  });

  it("nenhuma animação infinita, nem enquanto carrega", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    const { container } = render(<MinhaFila />);
    expect(await screen.findByText("Carregando o seu Início")).toBeTruthy();
    expect(
      container.querySelectorAll("[class*='animate-spin'], [class*='animate-ping'], [class*='animate-pulse']")
    ).toHaveLength(0);
  });

  it("o título da aba leva o número de prazos vencidos, e só Início quando não há", async () => {
    document.title = "Gestão HSM";
    const { unmount } = await abrir();
    expect(document.title).toBe("(2) Início");
    unmount();
    expect(document.title).toBe("Gestão HSM");

    await abrir(EM_DIA);
    expect(document.title).toBe("Início");
  });

  it("em dia: a frase diz que está em dia e o próximo prazo, sem faixa escura", async () => {
    await abrir(EM_DIA);

    expect(screen.getByText("Aurora, você está em dia.")).toBeTruthy();
    expect(screen.getByText("O próximo prazo é 20/11.")).toBeTruthy();
    expect(screen.getByTestId("abertura").className).not.toContain("bg-primary-dark");
  });

  it("cada contador leva ao grupo dele; o que está zerado não vira link", async () => {
    await abrir({ ...COM_ATRASO, contadores: { passou_do_prazo: 2, ate_48_horas: 1, proximos_7_dias: 0 } });

    const resumo = screen.getByRole("list", { name: "Resumo dos prazos" });
    const links = within(resumo).getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["#grupo-passou_do_prazo", "#grupo-ate_48_horas"]);
    const titulos = links.map((a) => {
      const alvo = document.getElementById(a.getAttribute("href")!.slice(1));
      return alvo?.tagName === "SECTION" ? within(alvo).getByRole("heading", { level: 2 }).textContent : null;
    });
    expect(titulos).toEqual(["Passou do prazo2", "Vence em até 48 horas1"]);
  });

  it("no celular, título e origem longos quebram a linha em vez de empurrar a tela para o lado", async () => {
    await abrir();
    const vencida = linha("Treinar a equipe da noite");
    expect(classes(within(vencida).getByText("Treinar a equipe da noite"))).toContain("break-words");
    expect(classes(within(vencida).getByText("Reunião de Atendimento, de 28/10/2026."))).toContain("break-words");
  });

  it("no celular, a etiqueta e o botão descem de linha e quebram o texto em vez de passar da borda do cartão", async () => {
    // O jsdom não mede: a medida no Chromium está no PR #2026. Aqui fica a
    // causa do corte, sem prefixo de tela (o que vale no celular): a linha
    // que não quebra e o texto que não quebra.
    await abrir();
    const botao = within(linha("Treinar a equipe da noite")).getByRole("link", {
      name: "Abrir a Pendência: Treinar a equipe da noite",
    });
    const etiqueta = within(linha("Treinar a equipe da noite")).getByText("Reuniões");
    expect(botao.parentElement).toBe(etiqueta.parentElement);
    expect(classes(botao.parentElement!)).toContain("flex-wrap");
    expect(classes(botao)).not.toContain("whitespace-nowrap");
    expect(classes(etiqueta)).not.toContain("whitespace-nowrap");
    expect(classes(botao)).toContain("max-w-full");
    expect(classes(etiqueta)).toContain("max-w-full");
  });

  it("leitor de tela: a frase fica numa região anunciada, que já existe enquanto carrega", async () => {
    let responder: (r: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((r) => (responder = r)))
    );
    render(<MinhaFila />);

    const carregando = await screen.findByText("Carregando o seu Início");
    const regiao = carregando.closest("[aria-live]") as HTMLElement;
    expect(regiao?.getAttribute("aria-live")).toBe("polite");
    responder({ ok: true, status: 200, json: async () => COM_ATRASO } as Response);

    await screen.findByText(COM_ATRASO.frase.titulo);
    expect(regiao.isConnected).toBe(true);
    expect(regiao.textContent).toBe("Aurora, dois prazos seus venceram.O mais antigo espera há 9 dias.");
  });

  it("leitor de tela: cada botão diz o que abre", async () => {
    await abrir();
    expect(
      within(linha("Treinar a equipe da noite")).getByRole("link", {
        name: "Abrir a Pendência: Treinar a equipe da noite",
      })
    ).toBeTruthy();
    expect(
      within(linha("Agenda regulatória: relatório trimestral")).getByRole("link", {
        name: "Abrir na agenda: Agenda regulatória: relatório trimestral",
      })
    ).toBeTruthy();
  });

  it("o contraste do texto da linha passa no nível AA, também com o fundo do hover", async () => {
    // As cores das classes usadas na linha: os tokens do globals.css e a
    // paleta do Tailwind 4 (oklch convertido para hex).
    const COR: Record<string, string> = {
      "text-text": "#1E293B",
      "text-text-secondary": "#64748B",
      "text-slate-600": "#45556C",
      "text-primary": "#2B2E7E",
      "text-red-700": "#C10007",
      "text-white": "#FFFFFF",
      "bg-white": "#FFFFFF",
      "bg-slate-100": "#F1F5F9",
      "bg-primary": "#2B2E7E",
      // O fundo da linha no hover e no foco: o pior caso, mais escuro que o branco.
      "hover:bg-slate-50": "#F8FAFC",
    };
    const luminancia = (hex: string) => {
      const [r, g, b] = [1, 3, 5].map((i) => {
        const c = parseInt(hex.slice(i, i + 2), 16) / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const contraste = (a: string, b: string) => {
      const [claro, escuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
      return (claro + 0.05) / (escuro + 0.05);
    };
    const subindo = (el: Element | null, prefixo: string): string => {
      for (let atual = el; atual; atual = atual.parentElement) {
        const achada = classes(atual).find((c) => c.startsWith(prefixo) && COR[c]);
        if (achada) return COR[achada];
      }
      throw new Error(`sem cor ${prefixo} para ${el?.textContent}`);
    };

    await abrir({
      ...COM_ATRASO,
      itens: COM_ATRASO.itens.map((i) => ({ ...i, contexto: "Em andamento. Aberta em 01/11/2026." })),
    });

    const textos = Array.from(document.querySelectorAll("section[id^='grupo-'] li :is(p, span, a)")).filter(
      (el) => el.children.length === 0 && el.textContent
    );
    expect(textos.length).toBeGreaterThan(20);
    const reprovados = textos
      .map((el) => {
        const fundo = classes(el).some((c) => c.startsWith("bg-")) ? subindo(el, "bg-") : subindo(el, "hover:bg-");
        return [el.textContent, Math.round(contraste(subindo(el, "text-"), fundo) * 100) / 100] as const;
      })
      .filter(([, razao]) => razao < 4.5);
    expect(reprovados).toEqual([]);
  });

  it("leitor de tela: cada grupo é uma seção nomeada com o título dela", async () => {
    await abrir();
    const secao = screen.getByRole("region", { name: "Passou do prazo" });
    expect(within(secao).getByRole("heading", { level: 2 }).textContent).toBe("Passou do prazo2");
  });
});
