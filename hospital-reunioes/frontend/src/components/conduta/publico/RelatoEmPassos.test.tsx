/**
 * @vitest-environment jsdom
 */

/**
 * O relato do Canal de Conduta em passos (issue #1843): da entrada ao
 * protocolo, sem login e sem nada no endereço.
 *
 * jsdom não mede largura nem tempo de toque. O que segura o relato em menos
 * de cinco minutos num celular de entrada é o caminho mínimo curto (cinco
 * respostas obrigatórias, o resto opcional) e nenhuma largura fixa na tela;
 * os dois são travados aqui.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RelatoEmPassos } from "./RelatoEmPassos";

const PROTOCOLO = { protocolo: "CC-K7M4-Q2XT", codigo: "ABCD234567", voltar_a_partir_de: "2026-11-27" };
const TEXTOS = {
  textos: {
    aviso_p1_anonimato: { texto: "Aviso 1 da coordenação.", versao: 3, versao_id: "u1" },
    aviso_p1_protocolo: null,
    aviso_p1_boa_fe: { texto: "Aviso 3 revisado pelo jurídico.", versao: 2, versao_id: "u3" },
    contato_dp: null,
  },
};
const RELATO = "A supervisora gritou com a equipe na troca de turno.";

let chamadas: { url: string; init: RequestInit | undefined; corpo: Record<string, unknown> | null }[];
let respostaDoEnvio: () => Response;

function json(status: number, corpo: unknown): Response {
  return new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  chamadas = [];
  respostaDoEnvio = () => json(201, PROTOCOLO);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, init, corpo: init?.body ? JSON.parse(String(init.body)) : null });
      if (url.endsWith("/textos")) return json(200, TEXTOS);
      if (url.endsWith("/relatos")) return respostaDoEnvio();
      if (url.endsWith("/relatos/confianca")) return new Response(null, { status: 204 });
      return json(404, { detail: "Not Found" });
    })
  );
  Object.defineProperty(navigator, "clipboard", { value: { writeText: vi.fn(async () => {}) }, configurable: true });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
});

const clicar = (nome: string | RegExp) => fireEvent.click(screen.getByRole("button", { name: nome }));
const continuar = () => clicar("Continuar");
const passoAtual = () => Number(screen.getByRole("progressbar").getAttribute("aria-valuenow"));
const escolher = (grupo: string | RegExp, opcao: string | RegExp) =>
  fireEvent.click(within(screen.getByRole("group", { name: grupo })).getByRole("button", { name: opcao }));
const digitar = (rotulo: string | RegExp, valor: string) =>
  fireEvent.change(screen.getByLabelText(rotulo), { target: { value: valor } });

async function ateOPasso1() {
  render(<RelatoEmPassos />);
  clicar("Fazer relato");
  await screen.findByText("Aviso 1 da coordenação.");
}

/** O caminho mínimo: só o que é obrigatório. */
async function ateARevisaoPeloMinimo() {
  await ateOPasso1();
  fireEvent.click(screen.getByLabelText("Li as orientações. Relato o que acredito ser verdade."));
  continuar();
  escolher("Identificação", /Anônimo/);
  continuar();
  escolher("O relato envolve a Direção, a Presidência ou a família proprietária?", "Não");
  continuar();
  digitar("O que aconteceu?", RELATO);
  continuar();
}

const envios = () => chamadas.filter((c) => c.url.endsWith("/relatos"));

describe("a entrada (P0)", () => {
  it("cita o propósito AGIR CERTO, os três selos e as duas portas", () => {
    render(<RelatoEmPassos />);

    expect(screen.getByRole("heading", { name: "Canal de Conduta" })).toBeTruthy();
    expect(screen.getByText("AGIR CERTO é um dos nossos propósitos. Este canal existe para isso.")).toBeTruthy();
    const selos = within(screen.getByRole("list", { name: "O que o canal garante" })).getAllByRole("listitem");
    expect(selos.map((s) => s.textContent)).toEqual(["Sem login", "Sem registro de IP", "Só o Comitê lê"]);
    expect(screen.getByRole("button", { name: "Fazer relato" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Acompanhar relato" })).toBeTruthy();
  });
});

describe("o passo 1", () => {
  it("mostra os três avisos vigentes, com o padrão no que a coordenação não salvou", async () => {
    await ateOPasso1();

    const avisos = within(screen.getByRole("list", { name: "Avisos" })).getAllByRole("listitem");
    expect(avisos.map((a) => a.textContent)).toEqual([
      "Aviso 1 da coordenação.",
      "Guarde o protocolo e o código que vai receber. O hospital não consegue recuperá-los, e é só por esta página que o Comitê fala com você.",
      "Aviso 3 revisado pelo jurídico.",
    ]);
    expect(screen.getByText("Passo 1 de 6")).toBeTruthy();
  });

  it("traz a linha sobre a IA com a retenção de até 30 dias e sem treino", async () => {
    await ateOPasso1();

    expect(
      screen.getByText(
        "Usamos inteligência artificial para organizar o relato. Nenhuma decisão é tomada por IA. O serviço de IA guarda o texto por até 30 dias e não o usa para treinar a IA."
      )
    ).toBeTruthy();
  });

  it("sem a caixa de ciência marcada não continua, e diz por quê", async () => {
    await ateOPasso1();

    expect((screen.getByRole("button", { name: "Continuar" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Marque a caixa acima para continuar.")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("Li as orientações. Relato o que acredito ser verdade."));
    expect((screen.getByRole("button", { name: "Continuar" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("a versão de cada aviso lido vai no envio, sem identidade", async () => {
    await ateARevisaoPeloMinimo();
    clicar("Enviar");
    await screen.findByText("Relato registrado");

    const [{ corpo }] = envios();
    expect(corpo?.ciencia).toEqual({
      ciente: true,
      versoes: { aviso_p1_anonimato: 3, aviso_p1_protocolo: null, aviso_p1_boa_fe: 2 },
    });
    expect(corpo?.nome).toBeNull();
  });
});

describe("a barra de progresso e o Voltar", () => {
  it("andam juntos em todos os passos, e voltar não perde nada", async () => {
    await ateOPasso1();
    expect(passoAtual()).toBe(1);
    fireEvent.click(screen.getByLabelText("Li as orientações. Relato o que acredito ser verdade."));
    continuar();
    expect(passoAtual()).toBe(2);
    escolher("Identificação", /Com identificação/);
    digitar("Seu nome", "Joana Prudente");
    continuar();
    expect(passoAtual()).toBe(3);
    escolher("O relato envolve a Direção, a Presidência ou a família proprietária?", "Não sei");
    escolher(/^Assunto/, /Patrimônio/);
    escolher(/^Você/, "Presenciou");
    continuar();
    expect(passoAtual()).toBe(4);
    digitar("O que aconteceu?", RELATO);
    digitar(/Onde/, "Farmácia");
    escolher(/^Alguma liderança já sabe/, "Sim");
    digitar(/O que foi feito\?/, "Nada");
    continuar();
    expect(passoAtual()).toBe(5);

    // Do 5 de volta ao 1, um passo de cada vez.
    for (const esperado of [4, 3, 2, 1]) {
      clicar("Voltar");
      expect(passoAtual()).toBe(esperado);
    }
    expect((screen.getByLabelText("Li as orientações. Relato o que acredito ser verdade.") as HTMLInputElement).checked).toBe(
      true
    );
    continuar();
    expect((screen.getByLabelText("Seu nome") as HTMLInputElement).value).toBe("Joana Prudente");
    continuar();
    expect(
      within(screen.getByRole("group", { name: /Assunto/ }))
        .getByRole("button", { name: /Patrimônio/ })
        .getAttribute("aria-pressed")
    ).toBe("true");
    continuar();
    expect((screen.getByLabelText("O que aconteceu?") as HTMLTextAreaElement).value).toBe(RELATO);
    expect((screen.getByLabelText(/Onde/) as HTMLInputElement).value).toBe("Farmácia");
    continuar();

    const resumo = screen.getByLabelText("Resumo do relato");
    expect(within(resumo).getByText("Com identificação: Joana Prudente")).toBeTruthy();
    expect(within(resumo).getByText("Patrimônio")).toBeTruthy();
    expect(within(resumo).getByText(RELATO)).toBeTruthy();
    expect(within(resumo).getByText("Sim. Nada")).toBeTruthy();
  });

  it("o Voltar do passo 1 leva à entrada", async () => {
    await ateOPasso1();
    clicar("Voltar");

    expect(screen.getByRole("button", { name: "Fazer relato" })).toBeTruthy();
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
});

describe("o envio e o protocolo (P6)", () => {
  it("o caminho mínimo são cinco respostas e chega ao protocolo", async () => {
    await ateARevisaoPeloMinimo();
    expect(passoAtual()).toBe(5);
    clicar("Enviar");

    expect(await screen.findByText("Relato registrado")).toBeTruthy();
    expect(passoAtual()).toBe(6);
    expect(envios()[0].corpo).toMatchObject({ identificacao: "anonimo", direcao: "nao", relato: RELATO, assunto: null });
  });

  it("mostra protocolo e código com Copiar, o aviso de anotar e a data para voltar", async () => {
    await ateARevisaoPeloMinimo();
    clicar("Enviar");
    await screen.findByText("Relato registrado");

    expect(screen.getByText(PROTOCOLO.protocolo)).toBeTruthy();
    expect(screen.getByText(PROTOCOLO.codigo)).toBeTruthy();
    expect(screen.getByText("Anote agora. Não há como recuperar.")).toBeTruthy();
    expect(screen.getByText(/Volte a esta página a partir de 27\/11\/2026\. É por aqui que o Comitê fala com você\./)).toBeTruthy();

    clicar("Copiar protocolo");
    clicar("Copiar código");
    expect(vi.mocked(navigator.clipboard.writeText).mock.calls).toEqual([[PROTOCOLO.protocolo], [PROTOCOLO.codigo]]);
  });

  it("o protocolo aparece uma vez só: sem Voltar, sem endereço, sem nada guardado no aparelho", async () => {
    const endereco = window.location.href;
    await ateARevisaoPeloMinimo();
    clicar("Enviar");
    await screen.findByText("Relato registrado");

    expect(screen.queryByRole("button", { name: "Voltar" })).toBeNull();
    expect(window.location.href).toBe(endereco);
    const guardado = JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }) + document.cookie;
    expect(guardado).not.toContain(PROTOCOLO.protocolo);
    expect(guardado).not.toContain(PROTOCOLO.codigo);
    expect(guardado).not.toContain("supervisora");
    expect(document.cookie).toBe("");
  });

  it("a nota de confiança vai uma vez, com o protocolo e o código no corpo", async () => {
    await ateARevisaoPeloMinimo();
    clicar("Enviar");
    await screen.findByText("Relato registrado");

    escolher(/^De 1 a 5, quanto você confia neste canal/, "4");
    await screen.findByText("Obrigado pela resposta.");
    escolher(/^De 1 a 5, quanto você confia neste canal/, "2");

    const notas = chamadas.filter((c) => c.url.endsWith("/relatos/confianca"));
    expect(notas.map((c) => c.corpo)).toEqual([{ protocolo: PROTOCOLO.protocolo, codigo: PROTOCOLO.codigo, nota: 4 }]);
  });

  it("a recusa do servidor aparece e o relato continua na tela", async () => {
    respostaDoEnvio = () => json(429, { error: "limite" });
    await ateARevisaoPeloMinimo();
    clicar("Enviar");

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Muitos envios deste aparelho em pouco tempo. Espere alguns minutos e tente de novo."
    );
    expect(passoAtual()).toBe(5);
    expect(within(screen.getByLabelText("Resumo do relato")).getByText(RELATO)).toBeTruthy();
  });
});

describe("sem login, sem rastro e sem terceiros", () => {
  it("toda chamada sai sem token de login, sem cookie e sem dado no endereço", async () => {
    await ateARevisaoPeloMinimo();
    clicar("Enviar");
    await screen.findByText("Relato registrado");
    escolher(/^De 1 a 5, quanto você confia neste canal/, "5");
    await screen.findByText("Obrigado pela resposta.");

    expect(chamadas.map((c) => c.url)).toEqual([
      "/api/conduta/textos",
      "/api/conduta/relatos",
      "/api/conduta/relatos/confianca",
    ]);
    for (const { init } of chamadas) {
      expect(init?.credentials).toBe("omit");
      expect(init?.cache).toBe("no-store");
      expect(JSON.stringify(init?.headers ?? {})).not.toMatch(/authorization/i);
    }
  });

  it("nenhum passo carrega recurso de fora do app", async () => {
    const enderecos = new Set<string>();
    const colher = () =>
      document.querySelectorAll("[src], [href]").forEach((el) => {
        enderecos.add(el.getAttribute("src") ?? el.getAttribute("href") ?? "");
      });
    render(<RelatoEmPassos />);
    colher();
    cleanup();
    await ateOPasso1();
    for (const avancar of [
      () => fireEvent.click(screen.getByLabelText("Li as orientações. Relato o que acredito ser verdade.")),
      () => escolher("Identificação", /Anônimo/),
      () => escolher("O relato envolve a Direção, a Presidência ou a família proprietária?", "Não"),
      () => digitar("O que aconteceu?", RELATO),
    ]) {
      avancar();
      colher();
      continuar();
    }
    colher();
    clicar("Enviar");
    await screen.findByText("Relato registrado");
    colher();

    expect(enderecos.size).toBeGreaterThan(0);
    for (const endereco of enderecos) {
      expect(endereco, endereco).toMatch(/^\/(?!\/)/);
    }
  });
});

describe("a tela a 375 px", () => {
  const FONTE = readFileSync(resolve(__dirname, "RelatoEmPassos.tsx"), "utf8");

  it("nenhuma largura fixa, que quebraria a tela num celular de entrada", () => {
    expect(FONTE).not.toMatch(/\b(?:w|min-w)-\[\d+px\]/);
    // A largura da tela vem da moldura do layout (issue #1846), não do relato.
    const MOLDURA = readFileSync(resolve(__dirname, "MolduraDoCanal.tsx"), "utf8");
    expect(MOLDURA).toMatch(/max-w-lg mx-auto/);
  });

  it("sem travessão nem meia-risca", () => {
    expect(FONTE).not.toMatch(/[\u2013\u2014]/);
  });
});

describe("o envio que falha não some com o relato", () => {
  it("sem conexão, diz que nada foi enviado", async () => {
    respostaDoEnvio = () => {
      throw new TypeError("Failed to fetch");
    };
    await ateARevisaoPeloMinimo();
    clicar("Enviar");

    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("Sem conexão. Nada foi enviado. Tente de novo."));
  });
});
