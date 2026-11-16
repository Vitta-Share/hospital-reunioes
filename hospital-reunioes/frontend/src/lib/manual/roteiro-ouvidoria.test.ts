/**
 * O roteiro dos prints da página de Ouvidoria e o seed dele (issue #1723,
 * ADR 0094, decisão 5).
 *
 * O roteiro (`scripts/manual/ouvidoria/roteiro.sh`) semeia o banco local e
 * fotografa a tela pelo playwright-cli. Rodar o roteiro de verdade pede o app
 * no ar, o que o CI não tem; aqui se prova o contrato dele: refaz todas as
 * imagens que a página cita, recusa o que não é o app local, e o seed só tem
 * gente e contato de exemplo.
 */

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { carregarPaginasDoManual } from "./carregar";
import { imagensCitadas } from "./paginas";

const PASTA = join(process.cwd(), "scripts", "manual", "ouvidoria");
const ROTEIRO = join(PASTA, "roteiro.sh");
const SEED_CRU = readFileSync(join(PASTA, "seed.json"), "utf8");
const SEED = JSON.parse(SEED_CRU);

/** Os PNGs que o roteiro grava: o último argumento de cada `print`. */
function imagensDoRoteiro(texto: string): string[] {
  return Array.from(texto.matchAll(/^\s*print(?:_janela)?\s.*"([^"/]+\.png)"\s*$/gm), (m) => m[1]);
}

/** Para cada PNG do roteiro, a pessoa do seed com quem o roteiro entrou por
 * último antes de fotografá-lo (`entrar <pessoa>`). */
function quemFotografa(texto: string): Record<string, string> {
  const quem: Record<string, string> = {};
  let logada = "ninguém";
  for (const linha of texto.split("\n")) {
    const entrada = /^\s*entrar\s+(\w+)\s*$/.exec(linha);
    if (entrada) logada = entrada[1];
    const [png] = imagensDoRoteiro(linha);
    if (png) quem[png] = logada;
  }
  return quem;
}

/** Todo texto do seed, folha por folha. */
function folhas(valor: unknown): string[] {
  if (typeof valor === "string") return [valor];
  if (valor && typeof valor === "object") return Object.values(valor).flatMap(folhas);
  return [];
}

describe("o roteiro dos prints da página de Ouvidoria", () => {
  it("refaz todas as imagens que a página cita, e só elas", () => {
    const pagina = carregarPaginasDoManual().find((p) => p.modulo === "ouvidoria")!;
    const citadas = imagensCitadas(pagina.corpo);
    const doRoteiro = imagensDoRoteiro(readFileSync(ROTEIRO, "utf8"));

    expect(citadas.length).toBeGreaterThan(0);
    expect([...doRoteiro].sort()).toEqual([...citadas].sort());
  });

  it("fotografa a lista e a Tela do responsável entrando como o responsável do setor, e o resto como a ouvidora (issue #1888)", () => {
    const quem = quemFotografa(readFileSync(ROTEIRO, "utf8"));
    expect(quem["linha-responder.png"]).toBe("responsavel");
    expect(quem["tela-do-responsavel.png"]).toBe("responsavel");
    const daOuvidora = Object.entries(quem).filter(([png]) => !["linha-responder.png", "tela-do-responsavel.png"].includes(png));
    expect(daOuvidora.length).toBeGreaterThan(0);
    expect(daOuvidora.filter(([, pessoa]) => pessoa !== "ouvidora")).toEqual([]);
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

describe("o seed da página de Ouvidoria", () => {
  it("a ouvidora de exemplo fica na faixa P1300, longe das pessoas dos outros roteiros", () => {
    expect(SEED.ouvidora.id).toMatch(/^P13\d\d$/);
  });

  it("o responsável do setor de exemplo tem login, na mesma faixa e com outro id (issue #1888)", () => {
    expect(SEED.responsavel.id).toMatch(/^P13\d\d$/);
    expect(SEED.responsavel.id).not.toBe(SEED.ouvidora.id);
    expect(SEED.responsavel.senha).toBeTruthy();
  });

  it("todo e-mail do seed é de exemplo", () => {
    const emails = SEED_CRU.match(/[\w.+-]+@[\w.-]+/g) ?? [];
    expect(emails.length).toBeGreaterThan(0);
    expect(emails.filter((email) => !email.endsWith("@exemplo.local"))).toEqual([]);
  });

  it("nenhum telefone, CPF ou carteirinha no seed", () => {
    const comNumeroLongo = folhas(SEED).filter((texto) => /\d[\d .()-]{7,}\d/.test(texto));
    expect(comNumeroLongo).toEqual([]);
  });
});

describe("os detectores do roteiro e do seed", () => {
  it("o print de uma janela também conta como imagem do roteiro", () => {
    const texto = 'print "$(linha x)" "linha.png"\nprint_janela "Encerrar" "encerrar.png"\n# print "velho.png"';
    expect(imagensDoRoteiro(texto)).toEqual(["linha.png", "encerrar.png"]);
  });

  it("cada print fica com a última pessoa que entrou antes dele", () => {
    const texto = [
      "entrar ouvidora",
      'print "x" "a.png"',
      "entrar responsavel",
      'print "y" "b.png"',
      'print_janela "Z" "c.png"',
    ].join("\n");
    expect(quemFotografa(texto)).toEqual({ "a.png": "ouvidora", "b.png": "responsavel", "c.png": "responsavel" });
  });

  it("telefone escrito de qualquer jeito é pego", () => {
    for (const telefone of ["(21) 99876-5432", "21998765432", "+55 21 99887-7665", "123.456.789-09"]) {
      expect(folhas({ contato: telefone }).filter((t) => /\d[\d .()-]{7,}\d/.test(t))).toEqual([telefone]);
    }
  });
});
