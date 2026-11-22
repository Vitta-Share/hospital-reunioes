/**
 * @vitest-environment jsdom
 */

/**
 * As Capacitações do Núcleo (issue #1778, PRD #1764).
 *
 * A tela não decide nada: quem edita é o servidor que diz (`pode_editar`), quem
 * confirma a presença também (a rota só aceita a própria pessoa), e a cobertura
 * dos temas vem pronta. O que se trava aqui é o que a pessoa vê e o que cada
 * botão manda para a API.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CapacitacoesDoNucleo, type RespostaDasCapacitacoes } from "./CapacitacoesDoNucleo";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

function resposta(campos: Partial<RespostaDasCapacitacoes> = {}): RespostaDasCapacitacoes {
  return {
    eu: "p2",
    hoje: "2026-11-16",
    pode_editar: false,
    temas: [
      { id: "t-maos", nome: "Higiene das mãos", ativo: true },
      { id: "t-id", nome: "Identificação do paciente", ativo: true },
      { id: "t-velho", nome: "Tema antigo", ativo: false },
    ],
    capacitacoes: [
      {
        id: "cap-1",
        titulo: "Higiene das mãos na prática",
        data: "2026-10-20",
        carga_horaria: 1.5,
        instrutor: "Instrutor de Teste",
        instrutor_formacao: "Enfermeira de Teste",
        publico: "membros",
        tema_ids: ["t-maos"],
        participantes: [
          { participante_id: "p2", nome: "Pessoa de Teste Dois", presenca_confirmada_em: null },
          {
            participante_id: "p3",
            nome: "Pessoa de Teste Três",
            presenca_confirmada_em: "2026-10-20T18:30:00+00:00",
          },
        ],
      },
      {
        id: "cap-2",
        titulo: "Cirurgia segura",
        data: "2026-09-10",
        carga_horaria: 2,
        instrutor: "Outra Instrutora",
        // Capacitação de antes da migration 228: sem a formação (issue #1927).
        instrutor_formacao: null,
        publico: "profissionais",
        tema_ids: [],
        participantes: [{ participante_id: "p3", nome: "Pessoa de Teste Três", presenca_confirmada_em: null }],
      },
    ],
    cobertura: [
      { participante_id: "p1", nome: "Pessoa de Teste Um", papel: "presidencia", temas_cobertos: [] },
      { participante_id: "p3", nome: "Pessoa de Teste Três", papel: "membro", temas_cobertos: ["t-maos"] },
    ],
    ...campos,
  };
}

let chamadas: { url: string; metodo: string; corpo: unknown }[] = [];
let lista: RespostaDasCapacitacoes;

beforeEach(() => {
  chamadas = [];
  lista = resposta();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const metodo = init?.method ?? "GET";
      chamadas.push({ url, metodo, corpo: init?.body ? JSON.parse(String(init.body)) : undefined });
      let corpo: unknown = { id: "x" };
      if (metodo === "GET" && url === "/api/nsp/capacitacoes") corpo = lista;
      if (metodo === "GET" && url === "/api/nsp/membros/pessoas")
        corpo = {
          pessoas: [
            { id: "p2", nome: "Pessoa de Teste Dois" },
            { id: "p4", nome: "Pessoa de Teste Quatro" },
          ],
        };
      return new Response(JSON.stringify(corpo), { status: 200, headers: { "Content-Type": "application/json" } });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function cartao(titulo: string): Promise<HTMLElement> {
  return (await screen.findByRole("heading", { name: titulo })).closest("li") as HTMLElement;
}

describe("o que a pessoa vê", () => {
  it("cada capacitação com data, carga horária, instrutor, público, temas e presença", async () => {
    render(<CapacitacoesDoNucleo />);

    const primeira = within(await cartao("Higiene das mãos na prática"));
    expect(primeira.getByText("20/10/2026")).toBeTruthy();
    expect(primeira.getByText("1,5 h")).toBeTruthy();
    expect(primeira.getByText("Instrutor de Teste")).toBeTruthy();
    expect(primeira.getByText("Membros do Núcleo")).toBeTruthy();
    expect(primeira.getByText("Higiene das mãos")).toBeTruthy();
    const tres = primeira.getByText("Pessoa de Teste Três").closest("li") as HTMLElement;
    expect(within(tres).getByText("Confirmou em 20/10/2026, 15:30")).toBeTruthy();
    const dois = primeira.getByText("Pessoa de Teste Dois").closest("li") as HTMLElement;
    expect(within(dois).getByText("Não confirmou")).toBeTruthy();

    const segunda = within(await cartao("Cirurgia segura"));
    expect(segunda.getByText("Profissionais")).toBeTruthy();
    expect(segunda.getByText("2 h")).toBeTruthy();
  });

  it("a formação aparece junto do nome do instrutor, e a capacitação antiga diz que não foi informada", async () => {
    render(<CapacitacoesDoNucleo />);

    const primeira = await cartao("Higiene das mãos na prática");
    const instrutor = within(primeira).getByText("Instrutor de Teste").closest("dd") as HTMLElement;
    expect(within(instrutor).getByText("Enfermeira de Teste")).toBeTruthy();

    const segunda = await cartao("Cirurgia segura");
    const antiga = within(segunda).getByText("Outra Instrutora").closest("dd") as HTMLElement;
    expect(within(antiga).getByText("Formação não informada")).toBeTruthy();
  });

  it("a cobertura mostra, por membro, quantos temas mínimos já foram cobertos e quais", async () => {
    render(<CapacitacoesDoNucleo />);

    const tabela = await screen.findByRole("table", { name: "Temas mínimos por membro" });
    const tres = within(tabela).getByText("Pessoa de Teste Três").closest("tr") as HTMLElement;
    expect(within(tres).getByText("1 de 2")).toBeTruthy();
    expect(within(tres).getByText("Higiene das mãos")).toBeTruthy();
    const um = within(tabela).getByText("Pessoa de Teste Um").closest("tr") as HTMLElement;
    expect(within(um).getByText("0 de 2")).toBeTruthy();
  });

  it("com a lista de temas vazia, a cobertura diz que a lista ainda não foi preenchida", async () => {
    lista = resposta({ temas: [] });
    render(<CapacitacoesDoNucleo />);

    expect(await screen.findByText("A lista de temas mínimos ainda está vazia.")).toBeTruthy();
    expect(screen.queryByRole("table", { name: "Temas mínimos por membro" })).toBeNull();
  });
});

describe("a presença", () => {
  it("quem está na lista e não confirmou confirma com um toque", async () => {
    render(<CapacitacoesDoNucleo />);

    const primeira = within(await cartao("Higiene das mãos na prática"));
    fireEvent.click(primeira.getByRole("button", { name: "Confirmar minha presença" }));

    await waitFor(() =>
      expect(chamadas).toContainEqual({
        url: "/api/nsp/capacitacoes/cap-1/presenca",
        metodo: "POST",
        corpo: undefined,
      })
    );
  });

  it("o botão não aparece na capacitação em que a pessoa não está", async () => {
    render(<CapacitacoesDoNucleo />);

    const segunda = within(await cartao("Cirurgia segura"));
    expect(segunda.queryByRole("button", { name: "Confirmar minha presença" })).toBeNull();
  });

  it("na capacitação que ainda não aconteceu, o botão não aparece", async () => {
    lista = resposta({ hoje: "2026-10-19" });
    render(<CapacitacoesDoNucleo />);

    const primeira = within(await cartao("Higiene das mãos na prática"));
    expect(primeira.queryByRole("button", { name: "Confirmar minha presença" })).toBeNull();
  });

  it("no dia da capacitação, o botão aparece", async () => {
    lista = resposta({ hoje: "2026-10-20" });
    render(<CapacitacoesDoNucleo />);

    const primeira = within(await cartao("Higiene das mãos na prática"));
    expect(primeira.getByRole("button", { name: "Confirmar minha presença" })).toBeTruthy();
  });

  it("depois de confirmar, o botão some", async () => {
    lista = resposta({ eu: "p3" });
    render(<CapacitacoesDoNucleo />);

    const primeira = within(await cartao("Higiene das mãos na prática"));
    expect(primeira.queryByRole("button", { name: "Confirmar minha presença" })).toBeNull();
  });
});

describe("a Presidência", () => {
  it("o membro não vê o cadastro nem a edição dos temas", async () => {
    render(<CapacitacoesDoNucleo />);

    await cartao("Cirurgia segura");
    expect(screen.queryByRole("button", { name: "Registrar capacitação" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Incluir tema" })).toBeNull();
  });

  it("registra a capacitação com todos os campos e os participantes", async () => {
    lista = resposta({ pode_editar: true });
    render(<CapacitacoesDoNucleo />);

    fireEvent.click(await screen.findByRole("button", { name: "Registrar capacitação" }));
    const form = within(screen.getByRole("form", { name: "Nova capacitação" }));
    fireEvent.change(form.getByLabelText("Título"), { target: { value: "Prevenção de quedas" } });
    fireEvent.change(form.getByLabelText("Data"), { target: { value: "2026-11-05" } });
    fireEvent.change(form.getByLabelText("Carga horária (horas)"), { target: { value: "1.5" } });
    fireEvent.change(form.getByLabelText("Instrutor"), { target: { value: "Instrutor de Teste" } });
    fireEvent.change(form.getByLabelText("Formação do instrutor"), { target: { value: " Enfermeira de Teste " } });
    fireEvent.change(form.getByLabelText("Público"), { target: { value: "profissionais" } });
    fireEvent.click(form.getByRole("checkbox", { name: "Identificação do paciente" }));
    fireEvent.click(await form.findByRole("checkbox", { name: "Pessoa de Teste Quatro" }));
    fireEvent.click(form.getByRole("button", { name: "Salvar" }));

    await waitFor(() =>
      expect(chamadas).toContainEqual({
        url: "/api/nsp/capacitacoes",
        metodo: "POST",
        corpo: {
          titulo: "Prevenção de quedas",
          data: "2026-11-05",
          carga_horaria: 1.5,
          instrutor: "Instrutor de Teste",
          instrutor_formacao: "Enfermeira de Teste",
          publico: "profissionais",
          tema_ids: ["t-id"],
          participantes: ["p4"],
        },
      })
    );
  });

  it("a formação do instrutor é obrigatória na capacitação nova", async () => {
    lista = resposta({ pode_editar: true });
    render(<CapacitacoesDoNucleo />);

    fireEvent.click(await screen.findByRole("button", { name: "Registrar capacitação" }));
    const form = within(screen.getByRole("form", { name: "Nova capacitação" }));
    expect((form.getByLabelText("Formação do instrutor") as HTMLInputElement).required).toBe(true);
  });

  it("a formação só com espaços volta da API recusada, e a tela mostra a mensagem dela (#1931)", async () => {
    lista = resposta({ pode_editar: true });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const metodo = init?.method ?? "GET";
        if (metodo === "POST")
          return new Response(JSON.stringify({ detail: "Diga a formação de quem deu a capacitação." }), {
            status: 422,
            headers: { "Content-Type": "application/json" },
          });
        const corpo = url === "/api/nsp/capacitacoes" ? lista : { pessoas: [{ id: "p4", nome: "Pessoa de Teste Quatro" }] };
        return new Response(JSON.stringify(corpo), { status: 200, headers: { "Content-Type": "application/json" } });
      })
    );
    render(<CapacitacoesDoNucleo />);

    fireEvent.click(await screen.findByRole("button", { name: "Registrar capacitação" }));
    const form = within(screen.getByRole("form", { name: "Nova capacitação" }));
    fireEvent.change(form.getByLabelText("Título"), { target: { value: "Prevenção de quedas" } });
    fireEvent.change(form.getByLabelText("Data"), { target: { value: "2026-11-05" } });
    fireEvent.change(form.getByLabelText("Carga horária (horas)"), { target: { value: "1.5" } });
    fireEvent.change(form.getByLabelText("Instrutor"), { target: { value: "Instrutor de Teste" } });
    fireEvent.change(form.getByLabelText("Formação do instrutor"), { target: { value: "   " } });
    fireEvent.click(await form.findByRole("checkbox", { name: "Pessoa de Teste Quatro" }));
    fireEvent.submit(screen.getByRole("form", { name: "Nova capacitação" }));

    expect((await screen.findByRole("alert")).textContent).toBe("Diga a formação de quem deu a capacitação.");
  });

  it("o tema desativado não aparece para escolher no cadastro", async () => {
    lista = resposta({ pode_editar: true });
    render(<CapacitacoesDoNucleo />);

    fireEvent.click(await screen.findByRole("button", { name: "Registrar capacitação" }));
    const form = within(screen.getByRole("form", { name: "Nova capacitação" }));
    expect(form.queryByRole("checkbox", { name: "Tema antigo" })).toBeNull();
  });

  it("inclui, renomeia e desativa um tema mínimo", async () => {
    lista = resposta({ pode_editar: true });
    render(<CapacitacoesDoNucleo />);

    fireEvent.click(await screen.findByRole("button", { name: "Incluir tema" }));
    fireEvent.change(screen.getByLabelText("Nome do tema"), { target: { value: "Prevenção de quedas" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar tema" }));
    await waitFor(() =>
      expect(chamadas).toContainEqual({
        url: "/api/nsp/capacitacoes/temas",
        metodo: "POST",
        corpo: { nome: "Prevenção de quedas" },
      })
    );

    const temas = within(screen.getByRole("list", { name: "Temas mínimos" }));
    const maos = temas.getByText("Higiene das mãos").closest("li") as HTMLElement;
    fireEvent.click(within(maos).getByRole("button", { name: "Renomear" }));
    fireEvent.change(within(maos).getByLabelText("Nome do tema"), { target: { value: "Higiene de mãos" } });
    fireEvent.click(within(maos).getByRole("button", { name: "Salvar tema" }));
    await waitFor(() =>
      expect(chamadas).toContainEqual({
        url: "/api/nsp/capacitacoes/temas/t-maos",
        metodo: "PATCH",
        corpo: { nome: "Higiene de mãos" },
      })
    );

    const id = temas.getByText("Identificação do paciente").closest("li") as HTMLElement;
    fireEvent.click(within(id).getByRole("button", { name: "Desativar" }));
    await waitFor(() =>
      expect(chamadas).toContainEqual({
        url: "/api/nsp/capacitacoes/temas/t-id",
        metodo: "PATCH",
        corpo: { ativo: false },
      })
    );
  });
});
