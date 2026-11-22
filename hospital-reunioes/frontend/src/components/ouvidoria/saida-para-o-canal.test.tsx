/**
 * @vitest-environment jsdom
 */

/**
 * A Ouvidoria e o Canal de Conduta, nos dois sentidos (issue #1847, PRD #1786,
 * ADR 0097 decisão 11).
 *
 * * A Manifestação guiada (`/manifestacao` e a que segue do cartaz) mostra a
 *   saída "Sou colaborador e quero relatar uma conduta" só com o canal aberto.
 *   Quem diz se ele está aberto é a rota pública `/api/conduta/abertura`: 200
 *   aberto, 404 fechado. Na dúvida (falha de rede), fechado.
 * * O registro manual do ouvidor mostra a orientação de indicar o Canal ao
 *   colaborador (decisão 2 do diretor), também só com o canal aberto: com ele
 *   fechado, a orientação mandaria a pessoa a uma página que não existe.
 * * Vindo do Canal, o formulário abre com o texto já escrito, lido da memória
 *   da aba (sessionStorage), nunca do endereço da página.
 *
 * O backend é um dublê por URL.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ManifestacaoPage from "@/app/manifestacao/page";
import { ManifestacaoPublica } from "./ManifestacaoPublica";
import { NovaManifestacaoModal } from "./NovaManifestacaoModal";
import { guardarTextoParaAOuvidoria } from "@/lib/ouvidoria/texto-do-canal";

const SAIDA = "Sou colaborador e quero relatar uma conduta";
const ORIENTACAO =
  "Colaborador que quer relatar uma conduta: indique o Canal de Conduta. Lá ele pode ficar anônimo e acompanhar o relato pelo código.";

let canalAberto = true;
let redeCaiu = false;
let perguntasDaAbertura = 0;

function json(body: unknown, status = 200) {
  return { ok: status < 300, status, json: async () => body } as Response;
}

beforeEach(() => {
  canalAberto = true;
  redeCaiu = false;
  perguntasDaAbertura = 0;
  window.sessionStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url === "/api/conduta/abertura") {
        perguntasDaAbertura += 1;
        if (redeCaiu) throw new TypeError("Failed to fetch");
        return canalAberto ? json({ aberto: true }) : json({ detail: "Not Found" }, 404);
      }
      if (url.includes("/publico/locais")) return json({ locais: [] });
      if (url.includes("/setores")) return json([]);
      return json({}, 404);
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("a saída para o Canal de Conduta na Manifestação guiada", () => {
  it("com o canal aberto, o formulário público mostra a saída e ela leva ao Canal", async () => {
    render(<ManifestacaoPage />);

    const saida = await screen.findByRole("link", { name: new RegExp(SAIDA) });
    expect(saida.getAttribute("href")).toBe("/conduta");
  });

  it("com o canal aberto, a Manifestação guiada que segue do cartaz também mostra a saída", async () => {
    render(<ManifestacaoPublica codigoDoCartaz="K7M2P" />);

    const saida = await screen.findByRole("link", { name: new RegExp(SAIDA) });
    expect(saida.getAttribute("href")).toBe("/conduta");
  });

  it("com o canal fechado, a saída não aparece", async () => {
    canalAberto = false;
    render(<ManifestacaoPage />);

    await waitFor(() => expect(perguntasDaAbertura).toBe(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByRole("link", { name: new RegExp(SAIDA) })).toBeNull();
    expect(screen.queryByText(new RegExp(SAIDA))).toBeNull();
  });

  it("sem resposta da abertura, a saída não aparece: na dúvida, o canal fica fechado", async () => {
    redeCaiu = true;
    render(<ManifestacaoPage />);

    await waitFor(() => expect(perguntasDaAbertura).toBe(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText(new RegExp(SAIDA))).toBeNull();
  });
});

const TEXTO_DO_CANAL = "Fiquei seis horas esperando na emergência com meu pai e ninguém explicou o motivo.";

function clicar(nome: string | RegExp) {
  fireEvent.click(screen.getByRole("button", { name: nome }));
}

/** Os passos 1 a 3 com o mínimo, parando no passo 4, o do relato. */
async function ateORelato() {
  clicar(/Com identificação/);
  clicar("Continuar");
  clicar("Sobre outra pessoa");
  clicar("Continuar");
  clicar("Tarde");
  fireEvent.change(await screen.findByLabelText("Onde foi?"), { target: { value: "Outro lugar do hospital" } });
  clicar("Continuar");
  return (await screen.findByLabelText("Seu relato")) as HTMLTextAreaElement;
}

describe("vindo do Canal, o formulário abre com o texto já escrito", () => {
  it("o relato chega preenchido com o texto guardado na memória da aba", async () => {
    guardarTextoParaAOuvidoria(TEXTO_DO_CANAL);
    render(<ManifestacaoPage />);

    const relato = await ateORelato();
    expect(relato.value).toBe(TEXTO_DO_CANAL);
    expect(screen.getByText(/O texto que você escreveu no Canal de Conduta já está no seu relato/)).toBeTruthy();
  });

  it("o texto não passa pelo endereço da página, nem ao guardar nem ao abrir o formulário", async () => {
    const antes = window.location.href;
    guardarTextoParaAOuvidoria(TEXTO_DO_CANAL);
    expect(window.location.href).toBe(antes);

    render(<ManifestacaoPage />);
    await ateORelato();

    expect(window.location.href).toBe(antes);
    expect(decodeURIComponent(window.location.href)).not.toContain("seis horas");
  });

  it("o texto vale uma vez: o formulário seguinte da mesma aba abre vazio", async () => {
    guardarTextoParaAOuvidoria(TEXTO_DO_CANAL);
    const { unmount } = render(<ManifestacaoPage />);
    await ateORelato();
    unmount();

    render(<ManifestacaoPage />);
    const relato = await ateORelato();
    expect(relato.value).toBe("");
  });

  it("sem nada guardado, o relato abre vazio, como sempre", async () => {
    render(<ManifestacaoPage />);

    const relato = await ateORelato();
    expect(relato.value).toBe("");
  });
});

function registroManual() {
  render(<NovaManifestacaoModal aberto token="token" onClose={() => {}} onRegistrada={() => {}} />);
}

describe("a orientação no registro manual do ouvidor", () => {
  it("com o canal aberto, o registro manual orienta a indicar o Canal ao colaborador", async () => {
    registroManual();

    expect(await screen.findByText(ORIENTACAO)).toBeTruthy();
  });

  it("com o canal fechado, a orientação não aparece", async () => {
    canalAberto = false;
    registroManual();

    await waitFor(() => expect(perguntasDaAbertura).toBe(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText(ORIENTACAO)).toBeNull();
  });

  it("o relato de conduta continua entre os tipos: os casos já abertos seguem tramitando na Ouvidoria", () => {
    registroManual();

    const tipo = screen.getByLabelText("Tipo da manifestação") as HTMLSelectElement;
    const opcoes = Array.from(tipo.options).map((o) => [o.value, o.textContent]);
    expect(opcoes).toContainEqual(["relato_de_conduta", "Relato de conduta"]);
  });
});
