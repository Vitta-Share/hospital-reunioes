/**
 * @vitest-environment jsdom
 */

/**
 * A tela Documentos do Núcleo (issue #1767): a vigente de cada tipo marcada e
 * as anteriores embaixo, a leitura do texto na tela, e a publicação de uma
 * versão nova, que no Regimento exige dizer se a revisão é material ou de
 * redação. Nenhum botão de apagar.
 *
 * O texto do Regimento daqui é de teste; o de verdade entra pela tela.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DocumentoDoNucleo } from "@/lib/seguranca-do-paciente/documentos";

import { DocumentosDoNucleo } from "./DocumentosDoNucleo";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function documento(campos: Partial<DocumentoDoNucleo>): DocumentoDoNucleo {
  return {
    id: "doc",
    tipo: "regimento",
    versao: 1,
    titulo: "Regimento Interno do Núcleo",
    natureza_revisao: "material",
    vigente: true,
    tem_texto: true,
    tem_arquivo_assinado: false,
    publicado_em: "2026-11-01T12:00:00+00:00",
    publicado_por: "Pessoa de Teste",
    ...campos,
  };
}

const REGIMENTO_V2 = documento({ id: "reg-2", versao: 2, natureza_revisao: "redacao" });
const REGIMENTO_V1 = documento({ id: "reg-1", versao: 1, vigente: false });
const PLANO_V1 = documento({
  id: "plano-1",
  tipo: "plano_seguranca_paciente",
  titulo: "Plano de Segurança do Paciente",
  natureza_revisao: null,
});

function servidor(documentos: DocumentoDoNucleo[]) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") return { ok: true, status: 201, json: async () => ({}) };
    if (url === "/api/nsp/documentos") return { ok: true, status: 200, json: async () => ({ documentos }) };
    return { ok: true, status: 200, json: async () => ({ texto: `Texto de teste de ${url.split("/").pop()}.` }) };
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function posts(fetch: ReturnType<typeof servidor>) {
  return fetch.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST");
}

describe("a lista", () => {
  it("marca a vigente de cada tipo e guarda as anteriores embaixo", async () => {
    servidor([REGIMENTO_V2, REGIMENTO_V1, PLANO_V1]);

    render(<DocumentosDoNucleo podePublicar={false} />);

    const regimento = await screen.findByRole("region", { name: "Regimento" });
    const vigente = within(regimento).getByRole("article", { name: "Versão 2, vigente" });
    expect(within(vigente).getByText("Vigente")).toBeTruthy();
    expect(within(vigente).getByText("Revisão de redação")).toBeTruthy();
    const anteriores = within(regimento).getByRole("list", { name: "Versões anteriores" });
    expect(within(anteriores).getByText(/Versão 1/)).toBeTruthy();
    expect(within(anteriores).queryByText("Vigente")).toBeNull();
    expect(screen.getByRole("region", { name: "Plano de Segurança do Paciente" })).toBeTruthy();
  });

  it("não tem botão de apagar nem de editar", async () => {
    servidor([REGIMENTO_V2, REGIMENTO_V1]);

    render(<DocumentosDoNucleo podePublicar />);

    await screen.findByRole("region", { name: "Regimento" });
    expect(screen.queryByRole("button", { name: /apagar|excluir|remover|editar/i })).toBeNull();
  });

  it("sem documento publicado, diz que não há nenhum ainda", async () => {
    servidor([]);

    render(<DocumentosDoNucleo podePublicar={false} />);

    expect(await screen.findByText("Nenhum documento publicado ainda.")).toBeTruthy();
  });
});

describe("a leitura", () => {
  it("o membro lê o texto do Regimento vigente na tela", async () => {
    const fetch = servidor([REGIMENTO_V2, PLANO_V1]);

    render(<DocumentosDoNucleo podePublicar={false} />);

    const regimento = await screen.findByRole("region", { name: "Regimento" });
    fireEvent.click(within(regimento).getByRole("button", { name: "Ler o texto" }));

    expect(await within(regimento).findByText("Texto de teste de reg-2.")).toBeTruthy();
    expect(fetch).toHaveBeenCalledWith("/api/nsp/documentos/reg-2", expect.anything());
  });
});

describe("a publicação", () => {
  async function abrirFormulario(tipo: string) {
    fireEvent.click(await screen.findByRole("button", { name: "Publicar versão nova" }));
    fireEvent.change(screen.getByLabelText("Tipo"), { target: { value: tipo } });
    fireEvent.change(screen.getByLabelText("Título"), { target: { value: "Regimento Interno do Núcleo" } });
    fireEvent.change(screen.getByLabelText("Texto"), { target: { value: "Art. 1º Texto de teste." } });
  }

  it("quem não gere o Núcleo não vê o botão de publicar", async () => {
    servidor([REGIMENTO_V2]);

    render(<DocumentosDoNucleo podePublicar={false} />);

    await screen.findByRole("region", { name: "Regimento" });
    expect(screen.queryByRole("button", { name: "Publicar versão nova" })).toBeNull();
  });

  it("o Regimento sem a natureza da revisão não é enviado", async () => {
    const fetch = servidor([]);
    render(<DocumentosDoNucleo podePublicar />);
    await abrirFormulario("regimento");

    fireEvent.click(screen.getByRole("button", { name: "Publicar" }));

    expect(await screen.findByText("Diga se a revisão do Regimento é material ou só de redação.")).toBeTruthy();
    expect(posts(fetch)).toHaveLength(0);
  });

  it("o Regimento sai com a natureza escolhida", async () => {
    const fetch = servidor([]);
    render(<DocumentosDoNucleo podePublicar />);
    await abrirFormulario("regimento");

    fireEvent.click(screen.getByLabelText("De redação (não pede nova assinatura)"));
    fireEvent.click(screen.getByRole("button", { name: "Publicar" }));

    await waitFor(() => expect(posts(fetch)).toHaveLength(1));
    const corpo = JSON.parse(String((posts(fetch)[0][1] as RequestInit).body));
    expect(corpo).toEqual({
      tipo: "regimento",
      titulo: "Regimento Interno do Núcleo",
      texto: "Art. 1º Texto de teste.",
      natureza_revisao: "redacao",
    });
  });

  it("depois de publicar, a lista é lida de novo", async () => {
    const fetch = servidor([]);
    render(<DocumentosDoNucleo podePublicar />);
    await abrirFormulario("plano_seguranca_paciente");

    fireEvent.click(screen.getByRole("button", { name: "Publicar" }));

    await waitFor(() =>
      expect(fetch.mock.calls.filter(([url, init]) => url === "/api/nsp/documentos" && !init?.method)).toHaveLength(2)
    );
  });
});
