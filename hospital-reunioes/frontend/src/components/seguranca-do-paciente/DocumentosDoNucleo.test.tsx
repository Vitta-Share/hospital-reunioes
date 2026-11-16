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

import type { AssinaturaDoDocumento, DocumentoDoNucleo } from "@/lib/seguranca-do-paciente/documentos";

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

/*
 * A assinatura eletrônica (issue #1771): o ato de designação, o Regimento e o
 * Plano vão para assinatura; a versão enviada espera, com quem já assinou e
 * quem falta, e a anterior continua vigente. O arquivo assinado se baixa.
 */
describe("a assinatura", () => {
  const REGIMENTO_V3 = documento({ id: "reg-3", versao: 3, vigente: false, natureza_revisao: "material" });
  const ESPERANDO: AssinaturaDoDocumento = {
    documento_id: "reg-3",
    situacao: "enviado",
    erro: null,
    enviado_em: "2026-11-10T12:00:00+00:00",
    assinado_em: null,
    pode_reenviar: true,
    signatarios: [
      { nome: "Pessoa de Teste P1", qualidade: "diretoria_executiva", assinado_em: null },
      { nome: "Pessoa de Teste P2", qualidade: "presidencia", assinado_em: "2026-11-11T12:00:00+00:00" },
    ],
  };

  function servidorComAssinaturas(documentos: DocumentoDoNucleo[], assinaturas: AssinaturaDoDocumento[]) {
    const fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return { ok: true, status: 201, json: async () => ({ aviso: null, situacao: "enviado", signatarios: [] }) };
      }
      if (url === "/api/nsp/documentos") return { ok: true, status: 200, json: async () => ({ documentos }) };
      if (url === "/api/nsp/assinaturas-dos-documentos") {
        return { ok: true, status: 200, json: async () => ({ assinaturas }) };
      }
      if (url.endsWith("/arquivo-assinado")) {
        return { ok: true, status: 200, json: async () => ({ url: "https://storage.test/assinado.pdf" }) };
      }
      return { ok: true, status: 200, json: async () => ({ texto: "Texto de teste." }) };
    });
    vi.stubGlobal("fetch", fetch);
    return fetch;
  }

  it("a versão enviada espera com quem assinou e quem falta, e a anterior continua vigente", async () => {
    servidorComAssinaturas([REGIMENTO_V3, REGIMENTO_V2, REGIMENTO_V1], [ESPERANDO]);

    render(<DocumentosDoNucleo podePublicar={false} />);

    const regimento = await screen.findByRole("region", { name: "Regimento" });
    const esperando = await within(regimento).findByRole("article", { name: "Versão 3, aguardando assinatura" });
    expect(within(esperando).getByText(/Diretoria Executiva: Pessoa de Teste P1, falta assinar/)).toBeTruthy();
    expect(within(esperando).getByText(/Presidência do Núcleo: Pessoa de Teste P2, assinou em 11\/11\/2026/)).toBeTruthy();
    expect(within(regimento).getByRole("article", { name: "Versão 2, vigente" })).toBeTruthy();
    const anteriores = within(regimento).getByRole("list", { name: "Versões anteriores" });
    expect(within(anteriores).queryByText("Versão 3")).toBeNull();
    expect(within(esperando).queryByRole("button", { name: "Reconsultar status da assinatura" })).toBeNull();
    expect(within(esperando).queryByRole("button", { name: "Reenviar para assinatura" })).toBeNull();
  });

  it("a Presidência reconsulta e reenvia a versão que espera", async () => {
    const fetch = servidorComAssinaturas([REGIMENTO_V3, REGIMENTO_V2], [ESPERANDO]);
    render(<DocumentosDoNucleo podePublicar />);
    const esperando = await screen.findByRole("article", { name: "Versão 3, aguardando assinatura" });

    fireEvent.click(within(esperando).getByRole("button", { name: "Reconsultar status da assinatura" }));
    await waitFor(() =>
      expect(posts(fetch).map(([url]) => url)).toContain("/api/nsp/documentos/reg-3/assinatura/reconsultar")
    );

    fireEvent.click(within(esperando).getByRole("button", { name: "Reenviar para assinatura" }));
    await waitFor(() =>
      expect(posts(fetch).map(([url]) => url)).toContain("/api/nsp/documentos/reg-3/assinatura/reenviar")
    );
  });

  it("envia o Regimento para assinatura pelo formulário", async () => {
    const fetch = servidorComAssinaturas([], []);
    render(<DocumentosDoNucleo podePublicar />);
    fireEvent.click(await screen.findByRole("button", { name: "Publicar versão nova" }));
    fireEvent.change(screen.getByLabelText("Tipo"), { target: { value: "regimento" } });
    fireEvent.change(screen.getByLabelText("Título"), { target: { value: "Regimento Interno do Núcleo" } });
    fireEvent.change(screen.getByLabelText("Texto"), { target: { value: "Art. 1º Texto de teste." } });
    fireEvent.click(screen.getByLabelText("Material (pede nova assinatura do Termo)"));

    fireEvent.click(screen.getByRole("button", { name: "Enviar para assinatura" }));

    await waitFor(() => expect(posts(fetch)).toHaveLength(1));
    const [url, init] = posts(fetch)[0];
    expect(url).toBe("/api/nsp/documentos/assinatura");
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      tipo: "regimento",
      titulo: "Regimento Interno do Núcleo",
      texto: "Art. 1º Texto de teste.",
      natureza_revisao: "material",
    });
  });

  it("ata e outros documentos não vão para assinatura pelo formulário", async () => {
    servidorComAssinaturas([], []);
    render(<DocumentosDoNucleo podePublicar />);
    fireEvent.click(await screen.findByRole("button", { name: "Publicar versão nova" }));

    fireEvent.change(screen.getByLabelText("Tipo"), { target: { value: "ata" } });

    expect(screen.queryByRole("button", { name: "Enviar para assinatura" })).toBeNull();
    expect(screen.getByRole("button", { name: "Publicar" })).toBeTruthy();
  });

  it("quem lê Documentos baixa o arquivo assinado", async () => {
    const fetch = servidorComAssinaturas([documento({ id: "reg-4", versao: 4, tem_arquivo_assinado: true })], []);
    const aba = { opener: {}, location: { href: "" }, close: vi.fn() };
    vi.stubGlobal("open", vi.fn(() => aba));
    render(<DocumentosDoNucleo podePublicar={false} />);

    fireEvent.click(await screen.findByRole("button", { name: "Baixar o arquivo assinado" }));

    await waitFor(() => expect(aba.location.href).toBe("https://storage.test/assinado.pdf"));
    expect(fetch).toHaveBeenCalledWith("/api/nsp/documentos/reg-4/arquivo-assinado", expect.anything());
  });
});
