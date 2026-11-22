/**
 * @vitest-environment jsdom
 */

/**
 * A ata de deliberação e a reunião do Comitê (issue #1834; especificação, 7.3
 * e 8). O servidor decide o que vale; aqui se trava o que a tela pede a ele:
 * o botão próprio da transcrição da reunião, sem seletor de tipo e sem áudio,
 * a ata com os votos registrados e os Pontos a confirmar como Sugestão, e o
 * "CONCLUIR REUNIÃO" que só libera com os quatro itens.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AtaDoCaso, ReuniaoDoComite } from "@/lib/conduta/ata";

import { AtaEReuniao } from "./AtaEReuniao";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }) },
  }),
}));

let chamadas: { url: string; method: string; body: unknown }[];

beforeEach(() => {
  chamadas = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body instanceof FormData ? [...init.body.keys()] : init?.body ? JSON.parse(String(init.body)) : null;
      chamadas.push({ url, method: init?.method ?? "GET", body });
      return { ok: true, status: 200, json: async () => ({ ok: true }) } as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ATA: AtaDoCaso = {
  documento: {
    versao: 1,
    identificacao: { rito: "Completo", data: "20/11/2026", presentes: ["Ana", "Bruno", "Lia"], impedimentos: [], suplentes: [] },
    resumo: "O supervisor ameaçou cortar as horas da equipe.",
    provas: ["Depoimento de duas testemunhas."],
    defesa: "O acusado negou a ameaça.",
    deliberacao: "Procedente, por maioria",
    fundamentos: "Item 3.2 do Código de Conduta.",
    medida: "Advertência escrita",
    votos: [
      { membro: "Ana", resultado: "Procedente", medida: "Advertência escrita", justificativa: "A prova confirma." },
      { membro: "Bruno", resultado: "Improcedente", medida: null, justificativa: "Faltou prova." },
    ],
    correcao: [],
    encaminhamentos: ["Envio à Direção."],
    pontos: { rotulo: "Sugestão", itens: ["Na transcrição Bruno diz procedente; o voto registrado é improcedente."] },
    assinatura: null,
  },
  pode_gerar: true,
  bloqueio_da_geracao: null,
  pode_enviar: true,
};

const LISTA: ReuniaoDoComite["lista"] = [
  { item: "transcricao", rotulo: "Transcrição anexada", automatico: true, estado: "feito" },
  { item: "ata_assinada", rotulo: "Ata assinada pelos três", automatico: true, estado: "pendente" },
  { item: "gravacao_apagada", rotulo: "Apaguei a gravação de áudio da plataforma de gravação", automatico: false, estado: "pendente" },
  { item: "arquivos_apagados", rotulo: "Apaguei os arquivos do computador e do celular", automatico: false, estado: "pendente" },
];

const REUNIAO: ReuniaoDoComite = {
  transcricoes: [{ versao: 1, enviado_em: "2026-11-20T12:00:00Z", enviado_por: "Ana" }],
  lista: LISTA,
  pode_anexar: true,
  pode_marcar: true,
  pode_concluir: false,
  bloqueio_da_conclusao: "Falta marcar: Ata assinada pelos três.",
  concluida_em: null,
  concluida_por: null,
  transcricao_eliminada_em: null,
};

function montar(ata: AtaDoCaso | null = ATA, reuniao: ReuniaoDoComite | null = REUNIAO) {
  const aoMudar = vi.fn();
  render(<AtaEReuniao casoId="caso-1" ata={ata} reuniao={reuniao} aoMudar={aoMudar} />);
  return aoMudar;
}

describe("A transcrição da reunião do Comitê", () => {
  it("tem botão próprio, sem seletor de tipo, e vai só o arquivo", async () => {
    montar();
    const reuniao = screen.getByRole("region", { name: "Reunião do Comitê" });

    expect(within(reuniao).getByText("ANEXAR TRANSCRIÇÃO DA REUNIÃO DO COMITÊ")).toBeTruthy();
    expect(within(reuniao).queryByRole("combobox")).toBeNull();
    expect(within(reuniao).queryByRole("radio")).toBeNull();

    const arquivo = new File(["transcrição"], "reuniao.txt", { type: "text/plain" });
    fireEvent.change(within(reuniao).getByLabelText("Anexar transcrição da reunião do Comitê"), { target: { files: [arquivo] } });

    await waitFor(() => expect(chamadas).toHaveLength(1));
    expect(chamadas[0].url).toBe("/api/comite-de-conduta/casos/caso-1/reuniao/transcricao");
    expect(chamadas[0].body).toEqual(["arquivo"]);
  });

  it("não aceita áudio e não tem lugar para o áudio da reunião", () => {
    montar();
    const reuniao = screen.getByRole("region", { name: "Reunião do Comitê" });
    const entrada = within(reuniao).getByLabelText("Anexar transcrição da reunião do Comitê") as HTMLInputElement;

    expect(entrada.accept).toBe(".txt,.vtt,.pdf,.docx");
    expect(entrada.accept).not.toMatch(/mp3|m4a|ogg|wav|audio/);
    expect(reuniao.querySelectorAll("input[type=file]")).toHaveLength(1);
    expect(within(reuniao).queryByText(/ANEXAR ÁUDIO/)).toBeNull();
  });

  it("no rito rápido não aparece", () => {
    montar(ATA, null);
    expect(screen.queryByRole("region", { name: "Reunião do Comitê" })).toBeNull();
  });
});

describe("A ata", () => {
  it("mostra os votos registrados e os Pontos a confirmar como Sugestão, fora da ata", () => {
    montar();
    const ata = screen.getByRole("region", { name: "Ata de deliberação" });

    expect(within(ata).getByText("Procedente, por maioria")).toBeTruthy();
    expect(within(ata).getByText("Bruno: Improcedente")).toBeTruthy();
    const pontos = within(ata).getByRole("complementary", { name: "Pontos a confirmar" });
    expect(within(pontos).getByText("Sugestão")).toBeTruthy();
    expect(within(pontos).getByText(/o voto registrado é improcedente/)).toBeTruthy();
  });

  it("gera e envia a ata para a assinatura dos três", async () => {
    const aoMudar = montar(ATA, null);

    fireEvent.click(screen.getByRole("button", { name: "ENVIAR PARA ASSINATURA" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas[0]).toMatchObject({ url: "/api/comite-de-conduta/casos/caso-1/ata/assinatura", method: "POST" });
  });

  it("antes dos votos o botão GERAR ATA fica bloqueado com o motivo", () => {
    montar({ documento: null, pode_gerar: false, bloqueio_da_geracao: "A ata sai dos votos registrados: faltam votos.", pode_enviar: false }, null);

    expect((screen.getByRole("button", { name: "GERAR ATA" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("A ata sai dos votos registrados: faltam votos.")).toBeTruthy();
  });
});

describe("CONCLUIR REUNIÃO", () => {
  it("fica bloqueado com o que falta e a declaração é marcada pela coordenação", async () => {
    montar();
    const reuniao = screen.getByRole("region", { name: "Reunião do Comitê" });

    expect((within(reuniao).getByRole("button", { name: "CONCLUIR REUNIÃO" }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(reuniao).getByText("Falta marcar: Ata assinada pelos três.")).toBeTruthy();

    fireEvent.click(within(reuniao).getByLabelText("Apaguei a gravação de áudio da plataforma de gravação"));
    await waitFor(() => expect(chamadas).toHaveLength(1));
    expect(chamadas[0]).toMatchObject({
      url: "/api/comite-de-conduta/casos/caso-1/reuniao/conferencia",
      body: { item: "gravacao_apagada" },
    });
  });

  it("com os quatro itens, conclui", async () => {
    const aoMudar = montar(ATA, { ...REUNIAO, lista: LISTA.map((i) => ({ ...i, estado: "feito" })), pode_concluir: true, bloqueio_da_conclusao: null });

    fireEvent.click(screen.getByRole("button", { name: "CONCLUIR REUNIÃO" }));

    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
    expect(chamadas[0].url).toBe("/api/comite-de-conduta/casos/caso-1/reuniao/conclusao");
  });
});
