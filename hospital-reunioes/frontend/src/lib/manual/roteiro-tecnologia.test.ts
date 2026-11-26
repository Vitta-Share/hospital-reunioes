/**
 * O roteiro dos prints da página de Tecnologia e o seed dele (issue #1727,
 * ADR 0094, decisão 5; refeito na issue #2282, ADR 0113).
 *
 * O roteiro (`scripts/manual/tecnologia/roteiro.sh`) semeia o diretor de
 * exemplo, responde no lugar do backend em toda rota da aba Tecnologia com a
 * tabela do `respostas.py` e fotografa a tela pelo playwright-cli. Assim
 * nenhum card real do GitHub entra no print. Desde a issue #2279 a aba só
 * lê: o Quadro, o pedido aberto e as Entregas. Rodar o roteiro de verdade
 * pede o app no ar, o que o CI não tem; aqui se prova o contrato dele: refaz
 * todas as imagens que a página cita, recusa o que não é o app local, não
 * grava nada, só responde as rotas de leitura da aba, enche o Quadro de hoje,
 * e o seed e as respostas só têm gente e endereço de exemplo.
 */

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { colunasDoQuadro, linkDoPlano, seloDaImplantacao, type Demanda } from "@/components/tecnologia/demandas";
import { carregarPaginasDoManual } from "./carregar";
import { imagensCitadas } from "./paginas";

const PASTA = join(process.cwd(), "scripts", "manual", "tecnologia");
const ROTEIRO = join(PASTA, "roteiro.sh");
const SEED_CRU = readFileSync(join(PASTA, "seed.json"), "utf8");
const SEED = JSON.parse(SEED_CRU);

/** Os PNGs que o roteiro grava: o último argumento de cada `print`, `print_tela` e `print_pagina`. */
function imagensDoRoteiro(texto: string): string[] {
  return Array.from(texto.matchAll(/^\s*print(?:_tela|_pagina)?\s.*"([^"/]+\.png)"\s*$/gm), (m) => m[1]);
}

/** A tabela que o roteiro serve no lugar do backend: a rota (depois de `/api/admin/tecnologia/`) e o corpo. */
function tabela(): Record<string, unknown> {
  const rodada = spawnSync("python3", [join(PASTA, "respostas.py")], { encoding: "utf8" });
  if (rodada.status !== 0) throw new Error(rodada.stderr);
  return JSON.parse(rodada.stdout);
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
/** Gente de verdade que mexe nesta aba: o nome não pode ir para um print do repositório público. */
const NOMES_REAIS = ["pedro rezende", "pedro rib", "lucas sampaio", "hospitalsaomatheus", "são matheus", "sao matheus"];
/** O que o roteiro clicava nas telas que saíram da aba com a issue #2279 (ADR 0113, decisão 7). */
const CLIQUES_QUE_SAIRAM = [
  "Novo pedido",
  "Conversar",
  "Conversa da Demanda",
  "Esperando você",
  "?pergunta=",
  "Me explique",
  "Achei um problema",
  "Enviar para os desenvolvedores",
  "Pede sua resposta",
];

/** E-mails, telefones, endereços e nomes que não são de exemplo, num texto. Compara em casefold. */
function dadoReal(texto: string): string[] {
  const dobrado = texto.toLocaleLowerCase("pt-BR");
  const emails = (dobrado.match(EMAIL) ?? []).filter((e) => !e.endsWith("@exemplo.local"));
  // A página dos planos é a única que o Ver o plano abre (issue #2010): só com caminho de exemplo.
  const enderecos = (dobrado.match(ENDERECO) ?? []).filter(
    (u) => !/^https:\/\/[\w.-]*exemplo\.local(\/|$)/.test(u) && !/^https:\/\/planos-hsm\.vercel\.app\/exemplo-/.test(u),
  );
  // Data e hora (2026-11-12, 2026-11-12T12:00:00-03:00) são do calendário, não de gente.
  const semDatas = texto.replace(/\b\d{4}-\d{2}-\d{2}(?:T[\d:.]+(?:Z|[+-]\d{2}:\d{2})?)?\b/g, "");
  const numeros = NUMERO_LONGO.test(semDatas) ? [texto] : [];
  const nomes = NOMES_REAIS.filter((nome) => dobrado.includes(nome));
  return [...emails, ...enderecos, ...numeros, ...nomes];
}

describe("o roteiro dos prints da página de Tecnologia", () => {
  it("refaz todas as imagens que a página cita, e só elas", () => {
    const pagina = carregarPaginasDoManual().find((p) => p.modulo === "tecnologia")!;
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
    expect(rodada.stdout).not.toContain("pronta");
  });

  it("serve a tabela no lugar do backend e não deixa pedido nenhum seguir para ele", () => {
    const texto = readFileSync(ROTEIRO, "utf8");
    expect(texto).toMatch(/page\.route\(/);
    // Fora da tabela e fora do GET, a resposta é do próprio roteiro, nunca do backend.
    expect(texto).not.toMatch(/route\.(continue|fallback)\(/);
  });

  it("não grava nada: todo pedido que não é GET recebe a recusa do roteiro, sem exceção", () => {
    const texto = readFileSync(ROTEIRO, "utf8");
    const recusas = texto.match(/method\(\) !== 'GET'\) \{\s*return route\.fulfill\(\{ status: 403/g) ?? [];
    // Uma recusa por rota servida: a da aba e a do sino.
    expect(recusas).toHaveLength(2);
    expect(texto).not.toMatch(/postDataJSON|--envio|--depois-do-problema/);
  });

  it.each(CLIQUES_QUE_SAIRAM)("não passa mais pela tela que saiu: %s", (tela) => {
    expect(readFileSync(ROTEIRO, "utf8")).not.toContain(tela);
  });

  it("serve o sino vazio, para nenhum aviso de verdade entrar no print", () => {
    const texto = readFileSync(ROTEIRO, "utf8");
    expect(texto).toMatch(/startsWith\('\/api\/notificacoes'\)/);
    expect(texto).toMatch(/nao_lidas: 0/);
  });
});

describe("a tabela de respostas da aba Tecnologia", () => {
  const T = tabela();
  const lista = T["chat"] as Demanda[];

  it("responde só as rotas de leitura que a aba pede: quem está logado, os Desenvolvedores, os Projetos, a lista e as Entregas", () => {
    for (const chave of Object.keys(T)) {
      expect(chave, `a tabela responde ${chave}, que a aba não lê mais`).toMatch(/^(eu|desenvolvedores|projetos|entregas|chat(\?[^/]*)?)$/);
    }
    expect(T["eu"]).toEqual({ desenvolvedor: false });
    expect(Array.isArray(T["desenvolvedores"])).toBe(true);
    expect(lista.length).toBeGreaterThan(0);
    expect(T["entregas"]).toMatchObject({ topo: expect.any(Object), semanas: expect.any(Array), grupos: expect.any(Array) });
  });

  it("enche todas as colunas do Quadro de hoje, inclusive Entregue", () => {
    for (const coluna of colunasDoQuadro(lista, false, new Date())) {
      expect(coluna.cards.length, `a coluna ${coluna.rotulo} sai vazia`).toBeGreaterThan(0);
    }
  });

  it("o Quadro tem pedido das três Origens, e o bug Registrado é o Relato no app, antes do Enviar à Vitta", () => {
    expect(new Set(lista.map((d) => d.origem))).toEqual(new Set(["diretor", "relato", "vitta"]));
    const registrados = lista.filter((d) => d.etapa === "registrada" && d.classificacao === "bug");
    expect(registrados.length).toBeGreaterThan(0);
    expect(registrados.every((d) => d.origem === "relato")).toBe(true);
    // A melhoria nasce como card no Claude do diretor: nunca fica Registrada como Pedido do diretor.
    expect(lista.some((d) => d.etapa === "registrada" && d.origem === "diretor")).toBe(false);
  });

  it("o filtro Projeto em Ana traz só os pedidos da Ana, e todos eles", () => {
    const daAna = T["chat?projeto=ana"] as Demanda[];
    expect(daAna.length).toBeGreaterThan(0);
    expect(daAna.every((d) => d.projeto === "ana")).toBe(true);
    expect(daAna.map((d) => d.id).sort()).toEqual(lista.filter((d) => d.projeto === "ana").map((d) => d.id).sort());
  });

  it("o pedido do painel tem partes numeradas em mais de uma Onda, uma esperando outra do pedido e uma de outro pedido (issue #1903)", () => {
    const painel = lista.find((d) => d.id === SEED.abrir.painel)!;
    const partes = painel.partes ?? [];
    expect(painel.raiz_numero).toEqual(expect.any(Number));
    expect(partes.every((p) => typeof p.numero === "number")).toBe(true);
    expect(new Set(partes.map((p) => p.onda)).size).toBeGreaterThanOrEqual(2);
    const bloqueadoras = partes.flatMap((p) => p.bloqueadoras ?? []);
    const numeros = new Set(partes.map((p) => p.numero));
    // A do mesmo pedido é uma parte que ainda não entrou; a de outro pedido não é parte dele.
    const doPedido = bloqueadoras.filter((b) => !b.de_outro_pedido);
    expect(doPedido.length).toBeGreaterThan(0);
    for (const b of doPedido) {
      const espera = partes.find((p) => p.numero === b.numero);
      expect(espera?.situacao, `#${b.numero} trava, mas já entrou`).not.toBe("em_producao");
    }
    const deFora = bloqueadoras.filter((b) => b.de_outro_pedido);
    expect(deFora.length).toBeGreaterThan(0);
    expect(deFora.every((b) => !numeros.has(b.numero))).toBe(true);
  });

  it("o Quadro tem um card com o plano já validado e outro com o plano por validar, os dois com link que a tela desenha", () => {
    const comPlano = lista.filter((d) => linkDoPlano(d) !== null);
    expect(comPlano.some((d) => d.plano_validado === true)).toBe(true);
    expect(comPlano.some((d) => d.plano_validado === false)).toBe(true);
  });
});

describe("o pedido de projeto novo na tabela (issue #1967)", () => {
  const T = tabela();
  const lista = T["chat"] as Demanda[];
  const novo = lista.find((d) => d.id === SEED.abrir.projeto_novo);

  it("o pedido de projeto novo é da Vitta, com o nome do projeto e o link de exemplo do plano, e Registrado", () => {
    expect(novo, "a lista não tem o pedido de projeto novo").toBeDefined();
    expect(["hospital", "ana"]).not.toContain(novo!.projeto);
    expect(novo!.origem).toBe("vitta");
    expect(novo!.etapa).toBe("registrada");
    expect(novo!.projeto_nome).toEqual(expect.any(String));
    expect(novo!.raiz_url).toMatch(/^https:\/\/[\w.-]*exemplo\.local\//);
  });

  it("a rota projetos lista o Aplicativo do Hospital, a Ana e o projeto novo, com o nome", () => {
    const projetos = T["projetos"] as { valor: string; nome: string }[];
    expect(projetos.map((p) => p.valor)).toEqual(["hospital", "ana", novo!.projeto]);
    expect(projetos.at(-1)!.nome).toBe(novo!.projeto_nome);
  });
});

describe("a seção Implantação na tabela (issue #2282, ADR 0113, decisão 9)", () => {
  const T = tabela();
  const lista = T["chat"] as Demanda[];
  const entrega = () => lista.find((d) => d.id === SEED.implantacao.demanda)!;

  it("a entrega Em produção tem três cards de implantação, um fechado, e o selo Implantação 1 de 3 no Quadro", () => {
    const d = entrega();
    expect(d.etapa).toBe("em_producao");
    expect(seloDaImplantacao(d)).toBe("Implantação 1 de 3");
    const pedidos = d.implantacao!.pedidos;
    expect(pedidos.map((p) => p.situacao).sort()).toEqual(["aberto", "aberto", "feito"]);
    expect(pedidos.every((p) => p.espera === null)).toBe(true);
    const ondeCai = colunasDoQuadro(lista, false, new Date()).find((c) => c.cards.some((x) => x.id === d.id));
    expect(ondeCai, "a entrega com Implantação não cai em coluna nenhuma do Quadro de hoje").toBeDefined();
  });

  it("cada card de implantação diz com quem está, e o card que o diretor passou adiante está com outra pessoa", () => {
    const pedidos = entrega().implantacao!.pedidos;
    expect(pedidos.every((p) => typeof p.destinatario === "string" && p.destinatario.length > 0)).toBe(true);
    expect(pedidos.some((p) => p.destinatario === SEED.admin.nome)).toBe(true);
    expect(pedidos.some((p) => p.destinatario !== SEED.admin.nome)).toBe(true);
  });

  it("nenhuma outra entrega tem Implantação: a seção só aparece onde há card de implantação", () => {
    expect(lista.filter((d) => d.implantacao).map((d) => d.id)).toEqual([SEED.implantacao.demanda]);
  });
});

describe("o seed e as respostas da página de Tecnologia", () => {
  it("o diretor de exemplo fica na faixa P17280 a P17289, longe das pessoas dos outros roteiros", () => {
    expect(SEED.admin.id).toMatch(/^P1728\d$/);
    for (const dev of SEED.desenvolvedores) expect(dev.id).toMatch(/^P1728\d$/);
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
  it("o print de um pedaço, o da tela e o da página inteira contam como imagem do roteiro", () => {
    const texto = 'print "$(bloco x)" "bloco.png"\nprint_tela "tela.png"\nprint_pagina "inteira.png"\n# print "velho.png"';
    expect(imagensDoRoteiro(texto)).toEqual(["bloco.png", "tela.png", "inteira.png"]);
  });

  it("e-mail de verdade, telefone, endereço de fora e nome real são pegos, em maiúscula ou minúscula", () => {
    for (const real of [
      "diretoria@hospitalsaomatheus.com.br",
      "Fulano@Gmail.com",
      "(21) 99876-5432",
      "123.456.789-09",
      "HTTPS://github.com/exemplo/issues/1",
      "Responsável: PEDRO REZENDE",
      "Hospital São Matheus",
    ]) {
      expect(dadoReal(real), real).not.toEqual([]);
    }
    expect(dadoReal("HENRIQUE.BASTOS@EXEMPLO.LOCAL")).toEqual([]);
    expect(dadoReal("https://demonstracao.exemplo.local/selo")).toEqual([]);
    expect(dadoReal("https://planos-hsm.vercel.app/exemplo-51/")).toEqual([]);
    expect(dadoReal("https://planos-hsm.vercel.app/2007/")).not.toEqual([]);
    expect(dadoReal("2026-11-12T12:00:00-03:00")).toEqual([]);
  });
});
