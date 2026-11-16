/**
 * O roteiro dos prints da página de Segurança do Paciente e o seed dele
 * (issue #1780, PRD #1764).
 *
 * O roteiro (`scripts/manual/seguranca-do-paciente/roteiro.sh`) semeia a
 * Presidência de exemplo, responde no lugar do backend em toda rota do módulo
 * com a tabela do `respostas.py` e fotografa a tela pelo playwright-cli. Assim
 * nenhum e-mail sai, nenhum envelope vai para assinatura e nenhuma ata chega à
 * IA. Rodar o roteiro de verdade pede o app no ar, o que o CI não tem; aqui se
 * prova o contrato dele: refaz todas as imagens que a página cita, recusa o
 * que não é o app local, a tabela cobre o que cada print abre, e o seed e as
 * respostas só têm gente e endereço de exemplo.
 */

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { carregarPaginasDoManual } from "./carregar";
import { imagensCitadas } from "./paginas";

const PASTA = join(process.cwd(), "scripts", "manual", "seguranca-do-paciente");
const ROTEIRO = join(PASTA, "roteiro.sh");
const SEED_CRU = readFileSync(join(PASTA, "seed.json"), "utf8");
const SEED = JSON.parse(SEED_CRU);

/** Os PNGs que o roteiro grava: o último argumento de cada `print`, `print_tela`, `print_ficha` e afins. */
function imagensDoRoteiro(texto: string): string[] {
  return Array.from(texto.matchAll(/^\s*print(?:_\w+)?\s.*"([^"/]+\.png)"\s*$/gm), (m) => m[1]);
}

function rodar(...args: string[]): string {
  const rodada = spawnSync("python3", [join(PASTA, "respostas.py"), ...args], { encoding: "utf8" });
  if (rodada.status !== 0) throw new Error(rodada.stderr);
  return rodada.stdout;
}

/** A tabela que o roteiro serve no lugar do backend: a rota (depois de `/api/`) e o corpo. */
const tabela = (): Record<string, unknown> => JSON.parse(rodar());
/** O que o roteiro lê para clicar: o dia da composição e o título da reunião do dia. */
const doRoteiro = (): { composicao: string; reuniao_do_dia: string } => JSON.parse(rodar("--roteiro"));

/** Todo texto de um valor JSON, folha por folha. */
function folhas(valor: unknown): string[] {
  if (typeof valor === "string") return [valor];
  if (valor && typeof valor === "object") return Object.values(valor).flatMap(folhas);
  return [];
}

const NUMERO_LONGO = /\d[\d .()-]{7,}\d/;
const EMAIL = /[\w.+-]+@[\w.-]+/g;
const ENDERECO = /https?:\/\/[^\s"']+/gi;
/** Gente de verdade do hospital e do Núcleo: o nome não pode ir para um print do repositório público. */
const NOMES_REAIS = ["pedro rezende", "pedro rib", "lucas sampaio", "hospitalsaomatheus", "são matheus", "sao matheus"];

/** E-mails, telefones, endereços e nomes que não são de exemplo, num texto. Compara em casefold. */
function dadoReal(texto: string): string[] {
  const dobrado = texto.toLocaleLowerCase("pt-BR");
  const emails = (dobrado.match(EMAIL) ?? []).filter((e) => !e.endsWith("@exemplo.local"));
  const enderecos = (dobrado.match(ENDERECO) ?? []).filter((u) => !/^https:\/\/[\w.-]*exemplo\.local(\/|$)/.test(u));
  // Data e hora (2026-11-12, 2026-11-12T12:00:00-03:00) são do calendário, não de gente.
  const semDatas = texto.replace(/\b\d{4}-\d{2}-\d{2}(?:T[\d:.]+(?:Z|[+-]\d{2}:\d{2})?)?\b/g, "");
  const numeros = NUMERO_LONGO.test(semDatas) ? [texto] : [];
  const nomes = NOMES_REAIS.filter((nome) => dobrado.includes(nome));
  return [...emails, ...enderecos, ...numeros, ...nomes];
}

describe("o roteiro dos prints da página de Segurança do Paciente", () => {
  it("refaz todas as imagens que a página cita, e só elas", () => {
    const pagina = carregarPaginasDoManual().find((p) => p.modulo === "seguranca-do-paciente")!;
    const citadas = imagensCitadas(pagina.corpo);
    const doScript = imagensDoRoteiro(readFileSync(ROTEIRO, "utf8"));

    expect(citadas.length).toBeGreaterThan(0);
    expect([...doScript].sort()).toEqual([...citadas].sort());
  });

  it("recusa rodar contra um endereço que não é o app local", () => {
    const rodada = spawnSync("bash", [ROTEIRO], {
      env: { ...process.env, BASE: "https://app.hospitalsaomatheus.cloud", PATH: "/usr/bin:/bin" },
      encoding: "utf8",
    });

    expect(rodada.status).toBe(1);
    expect(rodada.stderr).toContain("não é o app local");
    expect(rodada.stdout).not.toContain("pronta");
  });

  it("serve a tabela no lugar do backend, recusa o que grava e não deixa pedido do módulo seguir para ele", () => {
    const texto = readFileSync(ROTEIRO, "utf8");
    expect(texto).toMatch(/page\.route\(/);
    expect(texto).toMatch(/method\(\) !== 'GET'[\s\S]{0,80}status: 403/);
    // Fora da tabela e fora do GET, a resposta é do próprio roteiro, nunca do backend.
    expect(texto).not.toMatch(/route\.(continue|fallback)\(/);
  });
});

describe("a tabela de respostas do módulo", () => {
  const T = tabela();
  const R = doRoteiro();

  it("responde cada tela que o roteiro abre", () => {
    for (const rota of [
      "nsp/membros",
      "nsp/membros/pessoas",
      "participantes/setores",
      `nsp/membros?data=${R.composicao}`,
      "nsp/documentos",
      "nsp/assinaturas-dos-documentos",
      "nsp/capacitacoes",
      "nsp/agenda",
      "nsp/reunioes",
    ]) {
      expect(T[rota], `falta a resposta de ${rota}`).toBeDefined();
    }
  });

  it("a lista de membros mostra os estados que a página explica, e cada ficha tem histórico", () => {
    const { membros } = T["nsp/membros"] as { membros: { id: string; estado: string; termo_pendente: boolean }[] };
    const estados = new Set(membros.map((m) => m.estado));
    for (const estado of ["ativo", "a_vencer", "aguardando_assinatura", "em_carencia", "encerrado"]) {
      expect(estados.has(estado), `nenhum membro em ${estado}`).toBe(true);
    }
    for (const m of membros) {
      expect(T[`nsp/membros/${m.id}/trilha`], `falta o histórico de ${m.id}`).toMatchObject({ trilha: expect.any(Array) });
      if (m.termo_pendente) expect(T[`nsp/membros/${m.id}/termo`], `falta o Termo de ${m.id}`).toBeDefined();
    }
  });

  it("a composição da data do roteiro traz alguém que já saiu do Núcleo", () => {
    const { membros } = T[`nsp/membros?data=${R.composicao}`] as { membros: { estado: string }[] };
    expect(membros.length).toBeGreaterThan(0);
    expect(membros.some((m) => m.estado === "encerrado")).toBe(true);
  });

  it("a reunião do dia está no calendário com título único, a pauta pronta e a presença aberta", () => {
    const { reunioes } = T["nsp/reunioes"] as { reunioes: { id_reuniao: string; titulo: string; status_ata: string }[] };
    const titulos = reunioes.map((r) => r.titulo);
    expect(new Set(titulos).size).toBe(titulos.length);
    const doDia = reunioes.filter((r) => r.titulo === R.reuniao_do_dia);
    expect(doDia).toHaveLength(1);
    expect(doDia[0].status_ata).toBe("PROGRAMADA");
    expect(T[`nsp/reunioes/${doDia[0].id_reuniao}/pauta`]).toMatchObject({ disponivel: true, blocos: expect.any(Array) });
    expect(T[`nsp/reunioes/${doDia[0].id_reuniao}/presenca`]).toMatchObject({ pode_registrar: true });
  });

  it("as duas atas abrem pela página da reunião: uma esperando a validação, a outra encerrada", () => {
    const { reunioes } = T["nsp/reunioes"] as { reunioes: { id_reuniao: string; status_ata: string }[] };
    for (const status of ["AGUARDANDO_VALIDACAO", "ASSINADA"]) {
      const reuniao = reunioes.find((r) => r.status_ata === status);
      expect(reuniao, `nenhuma reunião em ${status}`).toBeDefined();
      expect(T[`reunioes/${reuniao!.id_reuniao}`]).toMatchObject({
        status_ata: status,
        do_nucleo: true,
        json_ata: { modelo: "nsp_dez_blocos" },
      });
      const leitura = T[`nsp/reunioes/${reuniao!.id_reuniao}/ata`] as { status_ata: string; ata: { blocos: unknown[] } };
      expect(leitura.status_ata).toBe(status);
      expect(leitura.ata.blocos).toHaveLength(10);
    }
  });

  it("a ata só cita membro pelo nome nas presenças e nas assinaturas, como a validação da minuta exige", () => {
    const nomes = SEED.membros.map((m: { nome: string }) => m.nome);
    for (const chave of Object.keys(T).filter((k) => k.endsWith("/ata"))) {
      const { ata } = T[chave] as { ata: { blocos: { chave: string; itens: string[] }[] } };
      for (const bloco of ata.blocos.filter((b) => !["presencas_e_quorum", "assinaturas"].includes(b.chave))) {
        for (const item of bloco.itens) {
          for (const nome of nomes) expect(item, `${chave}, bloco ${bloco.chave}`).not.toContain(nome);
        }
      }
    }
  });
});

describe("o seed e as respostas da página de Segurança do Paciente", () => {
  it("as pessoas de exemplo ficam na faixa P17800 a P17809, longe das pessoas dos outros roteiros", () => {
    const ids = [SEED.presidencia.id, ...SEED.membros.map((m: { id: string }) => m.id), ...SEED.pessoas_fora_do_nucleo.map((p: { id: string }) => p.id)];
    for (const id of ids) expect(id).toMatch(/^P1780\d$/);
  });

  it("o seed só tem e-mail de exemplo, e nenhum telefone, endereço ou nome de gente de verdade", () => {
    expect((SEED_CRU.match(EMAIL) ?? []).length).toBeGreaterThan(0);
    expect(folhas(SEED).flatMap(dadoReal)).toEqual([]);
  });

  it("a tabela de respostas não traz e-mail, telefone, endereço nem nome de gente de verdade", () => {
    expect(folhas(tabela()).flatMap(dadoReal)).toEqual([]);
  });
});

describe("os detectores do roteiro e do dado real", () => {
  it("o print de um pedaço, da tela, da página, da ficha e do topo contam como imagem do roteiro", () => {
    const texto = [
      'print "$(bloco x)" "bloco.png"',
      'print_tela "tela.png"',
      'print_pagina "inteira.png"',
      'print_ficha "Fulana" "ficha.png"',
      'print_topo "getByRole(x)" 330 "topo.png"',
      '# print "velho.png"',
    ].join("\n");
    expect(imagensDoRoteiro(texto)).toEqual(["bloco.png", "tela.png", "inteira.png", "ficha.png", "topo.png"]);
  });

  it("e-mail de verdade, telefone, endereço de fora e nome real são pegos, em maiúscula ou minúscula", () => {
    for (const real of [
      "nucleo@hospitalsaomatheus.com.br",
      "Fulano@Gmail.com",
      "(21) 99876-5432",
      "123.456.789-09",
      "HTTPS://assinatura.clicksign.com/termo",
      "Presidência: PEDRO REZENDE",
      "Hospital São Matheus",
    ]) {
      expect(dadoReal(real), real).not.toEqual([]);
    }
    expect(dadoReal("MARINA.COUTO.NUCLEO@EXEMPLO.LOCAL")).toEqual([]);
    expect(dadoReal("COREN 214587/RJ")).toEqual([]);
    expect(dadoReal("2026-11-12T12:00:00-03:00")).toEqual([]);
  });
});
