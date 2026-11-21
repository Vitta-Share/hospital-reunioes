/**
 * @vitest-environment jsdom
 */

/**
 * A tela Membros do Comitê de Conduta (issue #1822, PRD #1786).
 *
 * A lista com cadeira, vigência e situação, a composição numa data passada, e
 * incluir e encerrar só para quem tem o perfil de cadastro (o servidor diz em
 * `pode_cadastrar`). O backend é um dublê que responde por rota; o que se
 * confere é o que a tela mostra e o que ela manda. Pessoas de teste.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MembrosDoComite } from "./MembrosDoComite";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

function membro(campos: Record<string, unknown>) {
  return {
    id: "part-x",
    participante_id: "PX",
    nome: "Pessoa X",
    papel: "membro",
    cadeira: "Membro",
    e_diretor: false,
    vigencia_inicio: "2026-07-01",
    vigencia_fim: "2028-06-30",
    encerrada_em: null,
    termo_assinado: false,
    situacao: "vigente",
    ...campos,
  };
}

const MEMBROS = [
  membro({ id: "part-a", nome: "Pessoa A", papel: "coordenacao", cadeira: "Coordenação", e_diretor: true }),
  membro({ id: "part-b", nome: "Pessoa B", papel: "segundo_leitor", cadeira: "Membro e segundo leitor" }),
  membro({ id: "part-c", nome: "Pessoa C", situacao: "encerrada", encerrada_em: "2026-09-01", vigencia_fim: "2026-09-01" }),
];

const REGISTRO = {
  registro: [
    {
      acao: "inclusao",
      pessoa: "Pessoa B",
      autor: "Pessoa do Cadastro",
      detalhe: "Membro e segundo leitor, de 01/07/2026 a 30/06/2028",
      registrado_em: "2026-07-01T13:00:00+00:00",
    },
  ],
};

let podeCadastrar = false;
let chamadas: { url: string; init?: RequestInit }[] = [];

beforeEach(() => {
  chamadas = [];
  podeCadastrar = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, init });
      const metodo = init?.method ?? "GET";
      const corpo = (() => {
        if (url.startsWith("/api/comite-de-conduta/membros?data="))
          return { data: "2026-08-15", pode_cadastrar: podeCadastrar, membros: [MEMBROS[2]] };
        if (url === "/api/comite-de-conduta/membros" && metodo === "GET")
          return { data: null, pode_cadastrar: podeCadastrar, membros: MEMBROS };
        if (url === "/api/comite-de-conduta/membros" && metodo === "POST") return membro({ id: "part-novo" });
        if (url === "/api/comite-de-conduta/membros/pessoas") return { pessoas: [{ id: "PN", nome: "Pessoa Nova" }] };
        if (url === "/api/comite-de-conduta/membros/registro") return REGISTRO;
        if (url.endsWith("/encerrar")) return membro({ id: "part-b", situacao: "encerrada" });
        return {};
      })();
      return new Response(JSON.stringify(corpo), { status: 200, headers: { "Content-Type": "application/json" } });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir() {
  render(<MembrosDoComite />);
  await screen.findByText("Pessoa A");
}

function tabela() {
  return screen.getByRole("table", { name: "Membros do Comitê de Conduta" });
}

describe("a lista", () => {
  it("mostra cadeira, diretor, vigência e situação de cada membro", async () => {
    await abrir();

    const linhaA = within(tabela()).getByText("Pessoa A").closest("tr")!;
    expect(within(linhaA).getByText("Coordenação")).toBeTruthy();
    expect(within(linhaA).getByText("Diretor")).toBeTruthy();
    expect(within(linhaA).getByText("01/07/2026 a 30/06/2028")).toBeTruthy();
    expect(within(linhaA).getByText("Vigente")).toBeTruthy();

    const linhaC = within(tabela()).getByText("Pessoa C").closest("tr")!;
    expect(within(linhaC).getByText("Encerrada")).toBeTruthy();
    expect(within(linhaC).getByText("Não")).toBeTruthy();
  });

  it("mostra a composição na data escolhida", async () => {
    await abrir();

    fireEvent.change(screen.getByLabelText("Composição em"), { target: { value: "2026-08-15" } });
    fireEvent.click(screen.getByRole("button", { name: "Ver a composição" }));

    await waitFor(() => expect(within(tabela()).queryByText("Pessoa A")).toBeNull());
    expect(chamadas.some((c) => c.url === "/api/comite-de-conduta/membros?data=2026-08-15")).toBe(true);
    expect(within(tabela()).getByText("Pessoa C")).toBeTruthy();
    expect(screen.getByText("Composição em 15/08/2026")).toBeTruthy();
  });

  it("mostra o registro com quem fez e quando", async () => {
    await abrir();
    const registro = await screen.findByRole("list", { name: "Registro do Comitê" });
    expect(within(registro).getByText(/Entrou no Comitê/)).toBeTruthy();
    expect(within(registro).getByText(/por Pessoa do Cadastro em 01\/07\/2026/)).toBeTruthy();
  });
});

describe("quem cadastra", () => {
  it("sem o perfil de cadastro, a tela não mostra incluir nem encerrar", async () => {
    await abrir();
    expect(screen.queryByRole("button", { name: "Incluir membro" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Encerrar/ })).toBeNull();
  });

  it("com o perfil, inclui com cadeira, diretor e início", async () => {
    podeCadastrar = true;
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Incluir membro" }));
    await screen.findByRole("option", { name: "Pessoa Nova" });
    fireEvent.change(screen.getByLabelText("Pessoa"), { target: { value: "PN" } });
    fireEvent.change(screen.getByLabelText("Cadeira"), { target: { value: "suplente" } });
    fireEvent.click(screen.getByLabelText("É diretor"));
    fireEvent.change(screen.getByLabelText("Início do mandato"), { target: { value: "2026-12-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(chamadas.some((c) => c.init?.method === "POST")).toBe(true));
    const envio = chamadas.find((c) => c.init?.method === "POST")!;
    expect(envio.url).toBe("/api/comite-de-conduta/membros");
    expect(JSON.parse(String(envio.init?.body))).toEqual({
      participante_id: "PN",
      papel: "suplente",
      e_diretor: true,
      vigencia_inicio: "2026-12-01",
    });
  });

  it("com o perfil, encerra depois de confirmar, e a linha encerrada não tem o botão", async () => {
    podeCadastrar = true;
    await abrir();

    const linhaC = within(tabela()).getByText("Pessoa C").closest("tr")!;
    expect(within(linhaC).queryByRole("button", { name: /Encerrar/ })).toBeNull();

    const linhaB = within(tabela()).getByText("Pessoa B").closest("tr")!;
    fireEvent.click(within(linhaB).getByRole("button", { name: "Encerrar" }));
    expect(chamadas.some((c) => c.url.endsWith("/encerrar"))).toBe(false);
    fireEvent.click(within(linhaB).getByRole("button", { name: "Confirmar o encerramento" }));

    await waitFor(() =>
      expect(chamadas.some((c) => c.url === "/api/comite-de-conduta/membros/part-b/encerrar")).toBe(true)
    );
  });
});
