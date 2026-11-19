/**
 * O roteiro dos prints da página do Início e o seed dele (issue #1947, ADR
 * 0094, decisão 5).
 *
 * O roteiro (`scripts/manual/inicio/roteiro.sh`) semeia o banco local,
 * fotografa a tela pelo playwright-cli e só deixa o PNG chegar à página depois
 * que a guarda confere que o texto fotografado não tem nome nem título de fora
 * do seed. Rodar o roteiro de verdade pede o app no ar, o que o CI não tem;
 * aqui se prova o contrato dele: refaz todas as imagens que a página cita,
 * recusa o que não é o app local, o seed fica na faixa de id do Início e só
 * tem gente de exemplo, e a guarda acha o nome de fora mesmo em caixa alta.
 */

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { carregarPaginasDoManual } from "./carregar";
import { imagensCitadas } from "./paginas";

const PASTA = join(process.cwd(), "scripts", "manual", "inicio");
const ROTEIRO = join(PASTA, "roteiro.sh");
const PRINTS = join(PASTA, "prints.js");
const SEED_CRU = readFileSync(join(PASTA, "seed.json"), "utf8");
const SEED = JSON.parse(SEED_CRU);

/** Os PNGs que o roteiro grava: o arquivo de cada `foto(...)` do prints.js. */
function imagensDoRoteiro(texto: string): string[] {
  return Array.from(texto.matchAll(/^\s*await foto\(\s*"([^"/]+\.png)"/gm), (m) => m[1]);
}

/** Todo id de pessoa (P seguido de dígitos) que o seed escreve. */
function idsDePessoa(cru: string): string[] {
  return Array.from(cru.matchAll(/"(P\d+)"/g), (m) => m[1]);
}

/** A guarda do roteiro, a de verdade, do `semear.py`. */
function nomesDeForaNoTexto(texto: string, nomesDeFora: string[]): string[] {
  const rodada = spawnSync(
    "python3",
    [
      "-I",
      "-c",
      "import json, sys; sys.path.insert(0, sys.argv[1]); from semear import nomes_de_fora_no_texto; " +
        "print(json.dumps(nomes_de_fora_no_texto(sys.argv[2], json.loads(sys.argv[3]))))",
      PASTA,
      texto,
      JSON.stringify(nomesDeFora),
    ],
    { encoding: "utf8" }
  );
  if (rodada.status !== 0) throw new Error(rodada.stderr);
  return JSON.parse(rodada.stdout);
}

describe("o roteiro dos prints da página do Início", () => {
  it("refaz todas as imagens que a página cita, e só elas", () => {
    const pagina = carregarPaginasDoManual().find((p) => p.modulo === "inicio")!;
    const citadas = imagensCitadas(pagina.corpo);
    const doRoteiro = imagensDoRoteiro(readFileSync(PRINTS, "utf8"));

    expect(citadas.length).toBeGreaterThan(0);
    expect([...doRoteiro].sort()).toEqual([...citadas].sort());
  });

  it("recusa rodar contra um endereço que não é o app local", () => {
    const rodada = spawnSync("bash", [ROTEIRO], {
      env: { ...process.env, BASE: "https://app.hospitalsaomatheus.cloud", PATH: "/usr/bin:/bin" },
      encoding: "utf8",
    });

    expect(rodada.status).toBe(1);
    expect(rodada.stderr).toContain("não é o app local");
    expect(rodada.stdout).not.toContain("prontos");
  });
});

describe("o seed da página do Início", () => {
  it("toda pessoa do seed fica na faixa P19470 a P19479, longe das pessoas dos outros roteiros", () => {
    const ids = idsDePessoa(SEED_CRU);
    expect(ids.length).toBeGreaterThan(1);
    expect(ids.filter((id) => !/^P1947\d$/.test(id))).toEqual([]);
  });

  it("todo e-mail do seed é de exemplo", () => {
    const emails = SEED_CRU.match(/[\w.+-]+@[\w.-]+/g) ?? [];
    expect(emails.length).toBeGreaterThan(0);
    expect(emails.filter((email) => !email.endsWith("@exemplo.local"))).toEqual([]);
  });

  it("a Facilitadora conduz a Reunião de onde vêm as Pendências de quem responde a ela", () => {
    const outras = SEED.pessoas.map((p: { id: string }) => p.id);
    const deOutros = SEED.pendencias.filter((p: { responsavel: string }) => outras.includes(p.responsavel));
    expect(SEED.reunioes.passada.facilitador).toBe(SEED.facilitadora.id);
    expect(deOutros.some((p: { prazo: number }) => p.prazo < 0)).toBe(true);
  });
});

describe("a guarda do dado real nos prints", () => {
  it("acha o nome de fora do seed mesmo quando a tela o mostra em caixa alta", () => {
    const tela = "QUEM RESPONDE A VOCÊ · JOSÉ MARTINS · 2 VENCIDOS";
    expect(nomesDeForaNoTexto(tela, ["José Martins", "Yara Quintela"])).toEqual(["José Martins"]);
  });

  it("nome de uma palavra só fica de fora da conta, porque casaria com qualquer texto", () => {
    expect(nomesDeForaNoTexto("Abrir a Pendência", ["Pendência"])).toEqual([]);
  });
});

describe("os detectores do roteiro e do seed", () => {
  it("cada foto do prints.js conta como imagem do roteiro, e o comentário não", () => {
    const texto = '  await foto("inicio.png");\n  // await foto("velho.png")\n  await foto("quem-responde.png", bloco);';
    expect(imagensDoRoteiro(texto)).toEqual(["inicio.png", "quem-responde.png"]);
  });

  it("um id de pessoa fora da faixa é achado", () => {
    expect(idsDePessoa('{"id": "P1300", "responsavel": "P19471"}')).toEqual(["P1300", "P19471"]);
  });
});
