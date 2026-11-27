/**
 * O roteiro dos prints da página do Canal de Conduta, o seed e a tabela de
 * respostas dele (issue #1851, ADR 0094, decisão 5).
 *
 * O roteiro (`scripts/manual/canal-de-conduta/roteiro.sh`) semeia a
 * coordenação de exemplo no banco local, responde no lugar do backend em toda
 * rota do Comitê e fotografa a tela pelo playwright-cli. Rodar o roteiro de
 * verdade pede o app no ar, o que o CI não tem; aqui se prova o contrato dele:
 * refaz todas as imagens que a página cita, recusa o que não é o app local, e
 * nada do que vai para o print é dado real: os relatos são os casos fictícios
 * do Anexo B, e as pessoas e os contatos são de exemplo.
 */

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { carregarPaginasDoManual } from "./carregar";
import { imagensCitadas } from "./paginas";

const PASTA = join(process.cwd(), "scripts", "manual", "canal-de-conduta");
const ROTEIRO = join(PASTA, "roteiro.sh");
const SEED_CRU = readFileSync(join(PASTA, "seed.json"), "utf8");
const SEED = JSON.parse(SEED_CRU);
const ANEXO_B: { id: number; relato: string }[] = JSON.parse(
  readFileSync(join(process.cwd(), "..", "backend", "tests", "fixtures", "conduta", "casos-anexo-b.json"), "utf8")
);

/** Os PNGs que o roteiro grava: o último argumento de cada `print` e `print_faixa`. */
function imagensDoRoteiro(texto: string): string[] {
  return Array.from(texto.matchAll(/^\s*print(?:_\w+)?\s.*"([^"/]+\.png)"\s*$/gm), (m) => m[1]);
}

/** A tabela que o roteiro serve no lugar do backend: a rota (depois de `/api/`) e o corpo. */
function tabela(): Record<string, unknown> {
  const rodada = spawnSync("python3", [join(PASTA, "respostas.py")], { encoding: "utf8" });
  if (rodada.status !== 0) throw new Error(rodada.stderr);
  return JSON.parse(rodada.stdout);
}

/** Os casos abertos da tabela, um por etapa. */
function casosDaTabela(): { protocolo: string; relato: string }[] {
  return Object.entries(tabela())
    .filter(([rota]) => /^comite-de-conduta\/casos\/[^/]+$/.test(rota))
    .map(([, corpo]) => corpo as { protocolo: string; relato: string });
}

/**
 * Os textos que o roteiro digita escritos direto no script, fora do seed: o
 * argumento de `.fill(` ou de `pw fill` que não começa por `$(seed `.
 */
function textosEscritosNoRoteiro(texto: string): string[] {
  const doSeed = String.raw`\$\(seed `;
  const padroes = [
    new RegExp(String.raw`\.fill\(\s*['"](?!${doSeed}).*`, "g"),
    new RegExp(String.raw`^\s*pw fill \S+ "(?!${doSeed}).*`, "gm"),
  ];
  return padroes.flatMap((p) => Array.from(texto.matchAll(p), (m) => m[0].trim()));
}

/** Todo texto de um valor JSON, folha por folha. */
function folhas(valor: unknown): string[] {
  if (typeof valor === "string") return [valor];
  if (valor && typeof valor === "object") return Object.values(valor).flatMap(folhas);
  return [];
}

const NUMERO_LONGO = /\d[\d .()-]{7,}\d/;
const EMAIL = /[\w.+-]+@[\w.-]+/g;
const ENDERECO = /https?:\/\/[^\s"']+/gi;
/** Gente de verdade do hospital: o nome não pode ir para um print do repositório público. */
const NOMES_REAIS = ["pedro rezende", "pedro rib", "lucas sampaio", "hospitalsaomatheus", "são matheus", "sao matheus"];

/** E-mails, telefones, endereços e nomes que não são de exemplo, num texto. Compara em casefold. */
function dadoReal(texto: string): string[] {
  const dobrado = texto.toLocaleLowerCase("pt-BR");
  const emails = (dobrado.match(EMAIL) ?? []).filter((e) => !e.endsWith("@exemplo.local"));
  const enderecos = dobrado.match(ENDERECO) ?? [];
  // Data, hora e id de exemplo (2026-11-12T10:00:00-03:00, 00000000-0000-4000-8000-000000018511)
  // são do calendário e do roteiro, não de gente.
  const semDatas = texto
    .replace(/\b\d{4}-\d{2}-\d{2}(?:T[\d:.]+(?:Z|[+-]\d{2}:\d{2})?)?\b/g, "")
    .replace(/\b\d{2}\/\d{2}\/\d{4}\b/g, "")
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/g, "");
  const numeros = NUMERO_LONGO.test(semDatas) ? [texto] : [];
  const nomes = NOMES_REAIS.filter((nome) => dobrado.includes(nome));
  return [...emails, ...enderecos, ...numeros, ...nomes];
}

describe("o roteiro dos prints da página do Canal de Conduta", () => {
  it("refaz todas as imagens que a página cita, e só elas", () => {
    const pagina = carregarPaginasDoManual().find((p) => p.modulo === "canal-de-conduta")!;
    const citadas = imagensCitadas(pagina.corpo);
    const doRoteiro = imagensDoRoteiro(readFileSync(ROTEIRO, "utf8"));

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
    expect(rodada.stdout).not.toContain("prints em");
  });

  it("serve a tabela no lugar do backend em toda rota do Comitê e recusa o que grava", () => {
    const roteiro = readFileSync(ROTEIRO, "utf8");
    expect(roteiro).toContain("startsWith('/api/comite-de-conduta/')");
    expect(roteiro).toMatch(/method\(\) !== 'GET'[\s\S]*?status: 403/);
  });
});

describe("a tabela de respostas do Comitê", () => {
  it("abre um caso para cada etapa que a página fotografa, e Minha vez aponta para casos da tabela", () => {
    const respostas = tabela();
    for (const chave of ["triagem", "apuracao", "voto", "ata", "direcao"]) {
      expect(respostas, chave).toHaveProperty([`comite-de-conduta/casos/${SEED.casos[chave].id}`]);
    }
    const minhaVez = respostas["comite-de-conduta/minha-vez"] as { itens: { id: string }[] };
    expect(minhaVez.itens.length).toBeGreaterThan(0);
    for (const item of minhaVez.itens) expect(respostas).toHaveProperty([`comite-de-conduta/casos/${item.id}`]);
  });

  it("o relato de cada caso é um dos casos fictícios do Anexo B, sem mudar uma palavra", () => {
    const doAnexo = ANEXO_B.map((c) => c.relato);
    const casos = casosDaTabela();
    expect(casos).toHaveLength(5);
    expect(casos.filter((c) => !doAnexo.includes(c.relato)).map((c) => c.protocolo)).toEqual([]);
  });
});

describe("o seed e as respostas da página do Canal de Conduta", () => {
  it("as pessoas de exemplo ficam na faixa P18510 a P18519, longe das pessoas dos outros roteiros", () => {
    for (const id of [SEED.coordenacao.id, SEED.membro.id, SEED.segundo_leitor.id]) expect(id).toMatch(/^P1851\d$/);
  });

  it("o seed só tem e-mail de exemplo, e nenhum telefone, endereço ou nome de gente de verdade", () => {
    expect((SEED_CRU.match(EMAIL) ?? []).length).toBeGreaterThan(0);
    expect(folhas(SEED).flatMap(dadoReal)).toEqual([]);
  });

  it("a tabela de respostas não traz e-mail, telefone, endereço nem nome de gente de verdade", () => {
    expect(folhas(tabela()).flatMap(dadoReal)).toEqual([]);
  });

  it("todo texto que o roteiro digita num print vem do seed, que a varredura acima lê", () => {
    expect(textosEscritosNoRoteiro(readFileSync(ROTEIRO, "utf8"))).toEqual([]);
  });
});

describe("os detectores do roteiro e do dado real", () => {
  it("o print de um pedaço e o de uma faixa contam como imagem do roteiro; o comentado não", () => {
    const texto = ['print "$(x)" "bloco.png"', 'print_faixa "$A" "$B" "faixa.png"', '# print "velho.png"'].join("\n");
    expect(imagensDoRoteiro(texto)).toEqual(["bloco.png", "faixa.png"]);
  });

  it("o texto digitado direto no roteiro é pego; o que vem do seed não é", () => {
    const escritos = ["  await nova.getByLabel('Nome').fill('João da Silva');", 'pw fill "#email" "fulano@gmail.com"'];
    const lidos = [
      `  await nova.getByLabel('Nome').fill('$(seed "['nova_pessoa']['nome']")');`,
      `pw fill "#email" "$(seed "['coordenacao']['email']")"`,
    ];
    expect(textosEscritosNoRoteiro([...escritos, ...lidos].join("\n"))).toHaveLength(escritos.length);
    expect(textosEscritosNoRoteiro(lidos.join("\n"))).toEqual([]);
  });

  it("e-mail de verdade, telefone, endereço e nome real são pegos, em maiúscula ou minúscula", () => {
    for (const real of [
      "comite@hospitalsaomatheus.com.br",
      "Fulano@Gmail.com",
      "(21) 99876-5432",
      "123.456.789-09",
      "HTTPS://assinatura.clicksign.com/ata",
      "Coordenação: PEDRO REZENDE",
      "Hospital São Matheus",
    ]) {
      expect(dadoReal(real), real).not.toEqual([]);
    }
    expect(dadoReal("HELENA.DUARTE.CONDUTA@EXEMPLO.LOCAL")).toEqual([]);
    expect(dadoReal("2026-11-12T10:00:00-03:00")).toEqual([]);
    expect(dadoReal("00000000-0000-4000-8000-000000018511")).toEqual([]);
    expect(dadoReal("Protocolo CC-7KQ2-M4XD")).toEqual([]);
    expect(dadoReal("CC-7KQ2-M4XD, ligue (21) 99876-5432")).not.toEqual([]);
  });
});
