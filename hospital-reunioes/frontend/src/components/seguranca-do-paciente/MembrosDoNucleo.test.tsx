/**
 * @vitest-environment jsdom
 */

/**
 * A tela Núcleo, Membros (issue #1766, PRD #1764).
 *
 * Uma linha por membro, com no máximo 7 campos (o resto numa seção recolhida),
 * o estado de cada um, o histórico dos encerrados recolhido e a composição em
 * qualquer data. O backend é um dublê que responde por rota; o que se confere é
 * o que a tela mostra do que veio e o que ela manda. Pessoas de teste, sem
 * nome nem registro real.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";

import { MembrosDoNucleo } from "./MembrosDoNucleo";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const sessao = vi.hoisted(() => ({ participante: null as CurrentParticipante | null }));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({ participante: sessao.participante, loading: false, error: null }),
}));

function entrar(recursos: string[]) {
  sessao.participante = { id: "P2", nome_completo: "Pessoa de Teste", email: "p@hsm", recursos_nsp: recursos };
}

function membro(campos: Record<string, unknown>) {
  return {
    id: "part-x",
    participante_id: "PX",
    nome: "Pessoa X",
    papel: "membro",
    area: "UTI adulto",
    conselho_profissional: "COREN",
    registro_profissional: "000001",
    registro_uf: "RJ",
    vigencia_inicio: "2026-07-01",
    vigencia_fim: "2027-06-30",
    encerrada_em: null,
    termo_assinado_em: null,
    estado: "cadastrado",
    ...campos,
  };
}

const LISTA = {
  data: null,
  membros: [
    membro({ id: "part-a", participante_id: "PA", nome: "Pessoa A", papel: "presidencia", estado: "ativo", termo_assinado_em: "2026-07-02T10:00:00+00:00" }),
    membro({ id: "part-b", participante_id: "PB", nome: "Pessoa B", papel: "suplente", estado: "a_vencer" }),
    membro({ id: "part-c", participante_id: "PC", nome: "Pessoa C", estado: "encerrado", encerrada_em: "2026-09-01" }),
  ],
};

const COMPOSICAO = { data: "2026-08-15", membros: [LISTA.membros[0], LISTA.membros[2]] };

const TERMO = {
  situacao: "enviado",
  erro: null,
  enviado_em: "2026-11-10T12:00:00+00:00",
  documento_url: "https://storage.test/nsp-documentos/termos/envio-b.pdf?token=t",
};

let chamadas: { url: string; init?: RequestInit }[] = [];

beforeEach(() => {
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, init });
      const corpo = (() => {
        if (url.startsWith("/api/nsp/membros?data=")) return COMPOSICAO;
        if (url === "/api/nsp/membros" && (!init?.method || init.method === "GET")) return LISTA;
        if (url === "/api/nsp/membros" && init?.method === "POST") return membro({ id: "part-novo" });
        if (url === "/api/nsp/membros/pessoas") return { pessoas: [{ id: "PN", nome: "Pessoa Nova" }] };
        if (url === "/api/participantes/setores") return ["Farmácia", "UTI adulto"];
        if (url.endsWith("/trilha")) return { trilha: [] };
        if (url.endsWith("/termo")) return TERMO;
        if (url.includes("/termo/")) return { ...membro({ id: "part-b" }), aviso_termo: null };
        return {};
      })();
      return new Response(JSON.stringify(corpo), { status: 200, headers: { "Content-Type": "application/json" } });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessao.participante = null;
});

async function abrir() {
  render(<MembrosDoNucleo />);
  await screen.findByText("Pessoa A");
}

describe("a lista", () => {
  it("mostra no máximo 7 campos por vez", async () => {
    entrar(["membros", "gerir_nucleo"]);
    await abrir();

    const cabecalho = within(screen.getByRole("table", { name: "Membros do Núcleo" })).getAllByRole("columnheader");
    expect(cabecalho.map((c) => c.textContent)).toEqual([
      "Membro",
      "Papel",
      "Área",
      "Registro",
      "Vigência",
      "Estado",
      "Termo",
    ]);
    expect(cabecalho.length).toBeLessThanOrEqual(7);
    for (const linha of within(screen.getByRole("table", { name: "Membros do Núcleo" })).getAllByRole("row").slice(1)) {
      expect(within(linha).queryAllByRole("cell").length).toBeLessThanOrEqual(7);
    }
  });

  it("mostra o papel, o estado e a situação do Termo de cada um", async () => {
    entrar(["membros"]);
    await abrir();

    const linhaA = screen.getByText("Pessoa A").closest("tr")!;
    expect(within(linhaA).getByText("Presidência")).toBeTruthy();
    expect(within(linhaA).getByText("Ativo")).toBeTruthy();
    expect(within(linhaA).getByText("Assinado em 02/07/2026")).toBeTruthy();
    expect(within(linhaA).getByText("COREN 000001/RJ")).toBeTruthy();

    const linhaB = screen.getByText("Pessoa B").closest("tr")!;
    expect(within(linhaB).getByText("Suplente da Presidência")).toBeTruthy();
    expect(within(linhaB).getByText("A vencer")).toBeTruthy();
    expect(within(linhaB).getByText("Sem Termo")).toBeTruthy();
  });

  it("os encerrados ficam no histórico, recolhido, e não na lista", async () => {
    entrar(["membros"]);
    await abrir();

    const tabela = screen.getByRole("table", { name: "Membros do Núcleo" });
    expect(within(tabela).queryByText("Pessoa C")).toBeNull();
    const historico = screen.getByText("Histórico de participações encerradas").closest("details")!;
    expect(historico.open).toBe(false);
    expect(within(historico).getByText("Pessoa C")).toBeTruthy();
  });

  it("o resto de cada membro fica numa seção recolhida", async () => {
    entrar(["membros"]);
    await abrir();

    expect(screen.queryByRole("region", { name: "Detalhes de Pessoa A" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Pessoa A" }));
    expect(await screen.findByRole("region", { name: "Detalhes de Pessoa A" })).toBeTruthy();
  });
});

describe("a composição em uma data", () => {
  it("pergunta ao servidor quem valia no dia escolhido e mostra só essas pessoas", async () => {
    entrar(["membros"]);
    await abrir();

    fireEvent.change(screen.getByLabelText("Composição do Núcleo em"), { target: { value: "2026-08-15" } });

    const resultado = await screen.findByRole("list", { name: "Composição em 15/08/2026" });
    expect(chamadas.some((c) => c.url === "/api/nsp/membros?data=2026-08-15")).toBe(true);
    expect(within(resultado).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      expect.stringContaining("Pessoa A"),
      expect.stringContaining("Pessoa C"),
    ]);
  });
});

describe("quem gere o Núcleo", () => {
  it("a Presidência cadastra um membro com papel, área, registro e vigência", async () => {
    entrar(["membros", "gerir_nucleo"]);
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Cadastrar membro" }));
    await screen.findByRole("option", { name: "Pessoa Nova" });
    fireEvent.change(screen.getByLabelText("Pessoa"), { target: { value: "PN" } });
    fireEvent.change(screen.getByLabelText("Papel"), { target: { value: "suplente" } });
    fireEvent.change(screen.getByLabelText("Área"), { target: { value: "Farmácia" } });
    fireEvent.change(screen.getByLabelText("Conselho"), { target: { value: "CRF" } });
    fireEvent.change(screen.getByLabelText("Número do registro"), { target: { value: "000009" } });
    fireEvent.change(screen.getByLabelText("UF do registro"), { target: { value: "RJ" } });
    fireEvent.change(screen.getByLabelText("Início da vigência"), { target: { value: "2026-11-15" } });
    fireEvent.change(screen.getByLabelText("Fim da vigência"), { target: { value: "2027-11-14" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar cadastro" }));

    await waitFor(() => expect(chamadas.some((c) => c.init?.method === "POST")).toBe(true));
    const post = chamadas.find((c) => c.init?.method === "POST")!;
    expect(post.url).toBe("/api/nsp/membros");
    expect(JSON.parse(String(post.init!.body))).toEqual({
      participante_id: "PN",
      papel: "suplente",
      area: "Farmácia",
      conselho_profissional: "CRF",
      registro_profissional: "000009",
      registro_uf: "RJ",
      vigencia_inicio: "2026-11-15",
      vigencia_fim: "2027-11-14",
    });
  });

  it("renova a vigência pela seção do membro", async () => {
    entrar(["membros", "gerir_nucleo"]);
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Pessoa B" }));
    const detalhes = await screen.findByRole("region", { name: "Detalhes de Pessoa B" });
    fireEvent.change(within(detalhes).getByLabelText("Novo fim da vigência"), { target: { value: "2028-06-30" } });
    fireEvent.click(within(detalhes).getByRole("button", { name: "Renovar" }));

    await waitFor(() => expect(chamadas.some((c) => c.url === "/api/nsp/membros/part-b/renovar")).toBe(true));
    const renovar = chamadas.find((c) => c.url === "/api/nsp/membros/part-b/renovar")!;
    expect(JSON.parse(String(renovar.init!.body))).toEqual({ vigencia_fim: "2028-06-30" });
  });

  it("quem só lê não vê cadastrar, renovar nem encerrar", async () => {
    entrar(["membros"]);
    await abrir();

    expect(screen.queryByRole("button", { name: "Cadastrar membro" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Pessoa B" }));
    const detalhes = await screen.findByRole("region", { name: "Detalhes de Pessoa B" });
    expect(within(detalhes).queryByRole("button", { name: "Renovar" })).toBeNull();
    expect(within(detalhes).queryByRole("button", { name: "Encerrar participação" })).toBeNull();
  });
});

describe("o Termo de Adesão na seção do membro", () => {
  async function abrirPessoaB() {
    entrar(["membros", "gerir_nucleo"]);
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Pessoa B" }));
    return screen.findByRole("region", { name: "Detalhes de Pessoa B" });
  }

  it("a Presidência reconsulta o status da assinatura", async () => {
    const detalhes = await abrirPessoaB();

    fireEvent.click(await within(detalhes).findByRole("button", { name: "Reconsultar status da assinatura" }));

    await waitFor(() =>
      expect(chamadas.some((c) => c.url === "/api/nsp/membros/part-b/termo/reconsultar" && c.init?.method === "POST")).toBe(
        true
      )
    );
  });

  it("a Presidência reenvia o Termo", async () => {
    const detalhes = await abrirPessoaB();

    fireEvent.click(await within(detalhes).findByRole("button", { name: "Reenviar o Termo" }));

    await waitFor(() =>
      expect(chamadas.some((c) => c.url === "/api/nsp/membros/part-b/termo/reenviar" && c.init?.method === "POST")).toBe(
        true
      )
    );
  });

  it("a liberação sem assinatura só sai com justificativa", async () => {
    const detalhes = await abrirPessoaB();

    fireEvent.click(await within(detalhes).findByRole("button", { name: "Liberar sem assinatura" }));
    const confirmar = within(detalhes).getByRole("button", { name: "Confirmar liberação" });
    expect((confirmar as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(detalhes).getByLabelText("Justificativa da liberação"), {
      target: { value: "Assinatura eletrônica fora do ar" },
    });
    fireEvent.click(confirmar);

    await waitFor(() => expect(chamadas.some((c) => c.url === "/api/nsp/membros/part-b/termo/liberar")).toBe(true));
    const liberar = chamadas.find((c) => c.url === "/api/nsp/membros/part-b/termo/liberar")!;
    expect(JSON.parse(String(liberar.init!.body))).toEqual({ justificativa: "Assinatura eletrônica fora do ar" });
  });

  it("a seção abre o documento enviado", async () => {
    const detalhes = await abrirPessoaB();

    const link = await within(detalhes).findByRole("link", { name: "Abrir o documento enviado" });
    expect(link.getAttribute("href")).toBe(TERMO.documento_url);
  });

  it("membro com Termo assinado não tem os botões do Termo", async () => {
    entrar(["membros", "gerir_nucleo"]);
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Pessoa A" }));
    const detalhes = await screen.findByRole("region", { name: "Detalhes de Pessoa A" });

    expect(within(detalhes).queryByRole("button", { name: "Reenviar o Termo" })).toBeNull();
    expect(within(detalhes).queryByRole("button", { name: "Liberar sem assinatura" })).toBeNull();
  });

  it("o Termo novo de quem já tinha assinado aparece com os botões (issue #1769)", async () => {
    const renovado = membro({
      id: "part-a",
      participante_id: "PA",
      nome: "Pessoa A",
      papel: "presidencia",
      estado: "ativo",
      termo_assinado_em: "2026-07-02T10:00:00+00:00",
      termo_gerado_em: "2026-11-10T12:00:00+00:00",
      termo_enviado_em: "2026-11-10T12:00:01+00:00",
    });
    entrar(["membros", "gerir_nucleo"]);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        chamadas.push({ url, init });
        const corpo = (() => {
          if (url === "/api/nsp/membros") return { data: null, membros: [renovado] };
          if (url === "/api/participantes/setores") return [];
          if (url.endsWith("/trilha")) return { trilha: [] };
          if (url.endsWith("/termo")) return TERMO;
          return {};
        })();
        return new Response(JSON.stringify(corpo), { status: 200 });
      })
    );
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Pessoa A" }));
    const detalhes = await screen.findByRole("region", { name: "Detalhes de Pessoa A" });

    expect(await within(detalhes).findByRole("button", { name: "Reenviar o Termo" })).toBeTruthy();
    expect(within(detalhes).getByText("Enviado para assinatura em 10/11/2026.")).toBeTruthy();
  });

  it("o Termo novo que nem chegou a ser gerado aparece com os botões, pela pendência do servidor", async () => {
    const semDocumento = membro({
      id: "part-a",
      participante_id: "PA",
      nome: "Pessoa A",
      papel: "membro",
      estado: "ativo",
      termo_assinado_em: "2026-07-02T10:00:00+00:00",
      termo_gerado_em: "2026-07-01T10:00:00+00:00",
      termo_pendente: true,
    });
    entrar(["membros", "gerir_nucleo"]);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        chamadas.push({ url, init });
        const corpo = (() => {
          if (url === "/api/nsp/membros") return { data: null, membros: [semDocumento] };
          if (url === "/api/participantes/setores") return [];
          if (url.endsWith("/trilha")) return { trilha: [] };
          if (url.endsWith("/termo")) return TERMO;
          return {};
        })();
        return new Response(JSON.stringify(corpo), { status: 200 });
      })
    );
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Pessoa A" }));
    const detalhes = await screen.findByRole("region", { name: "Detalhes de Pessoa A" });

    expect(await within(detalhes).findByRole("button", { name: "Reenviar o Termo" })).toBeTruthy();
  });

  it("quem só lê não vê os botões do Termo", async () => {
    entrar(["membros"]);
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Pessoa B" }));
    const detalhes = await screen.findByRole("region", { name: "Detalhes de Pessoa B" });

    expect(within(detalhes).queryByRole("button", { name: "Reconsultar status da assinatura" })).toBeNull();
    expect(within(detalhes).queryByRole("button", { name: "Liberar sem assinatura" })).toBeNull();
  });

  it("o aviso do cadastro sem Termo aparece na tela", async () => {
    entrar(["membros", "gerir_nucleo"]);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        chamadas.push({ url, init });
        const corpo = (() => {
          if (url === "/api/nsp/membros" && init?.method === "POST")
            return { ...membro({ id: "part-novo" }), aviso_termo: "Publique o Regimento em Documentos para gerar o Termo de Adesão." };
          if (url === "/api/nsp/membros") return LISTA;
          if (url === "/api/nsp/membros/pessoas") return { pessoas: [{ id: "PN", nome: "Pessoa Nova" }] };
          if (url === "/api/participantes/setores") return [];
          return {};
        })();
        return new Response(JSON.stringify(corpo), { status: 200 });
      })
    );
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Cadastrar membro" }));
    await screen.findByRole("option", { name: "Pessoa Nova" });
    fireEvent.change(screen.getByLabelText("Pessoa"), { target: { value: "PN" } });
    fireEvent.change(screen.getByLabelText("Fim da vigência"), { target: { value: "2027-11-14" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar cadastro" }));

    expect(await screen.findByText("Publique o Regimento em Documentos para gerar o Termo de Adesão.")).toBeTruthy();
  });
});
