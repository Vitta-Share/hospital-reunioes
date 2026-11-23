/**
 * O roteiro dos prints da página de Tecnologia e o seed dele (issue #1727,
 * ADR 0094, decisão 5).
 *
 * O roteiro (`scripts/manual/tecnologia/roteiro.sh`) semeia o diretor de
 * exemplo, responde no lugar do backend em toda rota da aba Tecnologia com a
 * tabela do `respostas.py` e fotografa a tela pelo playwright-cli. Assim
 * nenhuma conversa chama a IA e nenhum card real do GitHub entra no print.
 * Rodar o roteiro de verdade pede o app no ar, o que o CI não tem; aqui se
 * prova o contrato dele: refaz todas as imagens que a página cita, recusa o
 * que não é o app local, a tabela cobre o que a tela pede e enche o Quadro de
 * hoje, e o seed e as respostas só têm gente e endereço de exemplo.
 */

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { perguntaValida, type PerguntaDaVitta } from "@/components/tecnologia/CartaoDaPergunta";
import { conversaValida } from "@/components/tecnologia/chat";
import type { FalaDoMeExplique } from "@/components/tecnologia/MeExplique";
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

/** O sino que o roteiro serve no lugar do backend: a rota (depois de `/api/notificacoes`) e o corpo (issue #1968). */
function sino(): Record<string, unknown> {
  const rodada = spawnSync("python3", [join(PASTA, "respostas.py"), "--sino"], { encoding: "utf8" });
  if (rodada.status !== 0) throw new Error(rodada.stderr);
  return JSON.parse(rodada.stdout);
}

/** As respostas dos dois cliques do Envio aos desenvolvedores, os únicos que não são GET (issue #2015). */
function envio(): Record<string, unknown> {
  const rodada = spawnSync("python3", [join(PASTA, "respostas.py"), "--envio"], { encoding: "utf8" });
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
});

describe("a tabela de respostas da aba Tecnologia", () => {
  const T = tabela();
  const lista = T["chat"] as Demanda[];

  it("responde quem está logado como diretor, os Desenvolvedores, a lista e as Entregas", () => {
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

  it("o filtro Projeto em Ana traz só os pedidos da Ana, e todos eles", () => {
    const daAna = T["chat?projeto=ana"] as Demanda[];
    expect(daAna.length).toBeGreaterThan(0);
    expect(daAna.every((d) => d.projeto === "ana")).toBe(true);
    expect(daAna.map((d) => d.id).sort()).toEqual(lista.filter((d) => d.projeto === "ana").map((d) => d.id).sort());
  });

  it("cada pedido do diretor abre com uma conversa que a tela aceita, e todo pedido com a Conversa da Demanda", () => {
    for (const demanda of lista) {
      if (demanda.origem !== "vitta") {
        expect(conversaValida(T[`chat/${demanda.id}`]), `a conversa de ${demanda.id} não serve`).toBe(true);
      }
      expect(T[`chat/${demanda.id}/conversa`], `falta a Conversa da Demanda de ${demanda.id}`).toMatchObject({
        mensagens: expect.any(Array),
      });
    }
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

  it("as conversas que o roteiro fotografa estão no ponto do print: a pergunta da melhoria e o resumo do bug", () => {
    const melhoria = T[`chat/${SEED.abrir.melhoria}`] as { estado: string; planejamento: boolean; mensagens: { recomendada?: string }[] };
    expect(melhoria.estado).toBe("em_andamento");
    expect(melhoria.planejamento).toBe(true);
    // A última fala é a pergunta com a recomendada: a tela não pede o turno seguinte à IA.
    expect(melhoria.mensagens.at(-1)?.recomendada).toMatch(/^[AB]$/);
    const bug = T[`chat/${SEED.abrir.bug}`] as { estado: string; resumo: unknown };
    expect(bug.estado).toBe("resumido");
    expect(bug.resumo).toBeTruthy();
  });
});

describe("a pergunta da Vitta e o pedido de projeto novo na tabela (issue #1968, PRD #1964)", () => {
  const T = tabela();
  const lista = T["chat"] as Demanda[];
  const novo = lista.find((d) => d.id === SEED.abrir.projeto_novo);

  it("o pedido de projeto novo é da Vitta, com o nome do projeto e o link de exemplo do plano, Registrado e sem Apagar", () => {
    expect(novo, "a lista não tem o pedido de projeto novo").toBeDefined();
    expect(["hospital", "ana"]).not.toContain(novo!.projeto);
    expect(novo!.origem).toBe("vitta");
    expect(novo!.etapa).toBe("registrada");
    expect(novo!.projeto_nome).toEqual(expect.any(String));
    expect(novo!.raiz_url).toMatch(/^https:\/\/[\w.-]*exemplo\.local\//);
    expect(novo!.pode_apagar).toBe(false);
  });

  it("a rota projetos lista o Aplicativo do Hospital, a Ana e o projeto novo, com o nome", () => {
    const projetos = T["projetos"] as { valor: string; nome: string }[];
    expect(projetos.map((p) => p.valor)).toEqual(["hospital", "ana", novo!.projeto]);
    expect(projetos.at(-1)!.nome).toBe(novo!.projeto_nome);
  });

  it("o sino traz o aviso Pede sua resposta com o assunto, e ele abre o pedido cuja Conversa tem a pergunta da Vitta", () => {
    const S = sino();
    expect(S["/count"]).toEqual({ nao_lidas: expect.any(Number) });
    const avisos = S["?limit=20"] as { tipo: string; titulo: string; mensagem: string; referencia_id: string; lida: boolean }[];
    const aviso = avisos.find((a) => a.titulo === "Pede sua resposta");
    expect(aviso, "o sino não tem o aviso Pede sua resposta").toBeDefined();
    expect(aviso!.tipo).toBe("TECNOLOGIA");
    expect(aviso!.lida).toBe(false);
    expect(aviso!.mensagem.length).toBeGreaterThan(0);
    // Desde a issue #2118 o aviso guarda a Pergunta e abre a aba no cartão dela.
    const esperando = T["perguntas/esperando"] as { id: string; demanda_id: string }[];
    const pergunta = esperando.find((p) => aviso!.referencia_id === `pergunta:${p.id}`);
    expect(pergunta, "o aviso não abre uma Pergunta da lista").toBeDefined();
    expect(pergunta!.demanda_id).toBe(novo!.id);
    const conversa = T[`chat/${novo!.id}/conversa`] as { mensagens: { texto: string; minha: boolean }[] };
    const ultima = conversa.mensagens.at(-1)!;
    expect(ultima.minha).toBe(false);
    expect(ultima.texto).toMatch(/\?$/);
  });

  it("o roteiro serve o sino no lugar do backend", () => {
    expect(readFileSync(ROTEIRO, "utf8")).toMatch(/respostas\.py" --sino/);
  });
});

describe("a Pergunta da Vitta, a lista Esperando sua resposta e o Me explique na tabela (issue #2123, PRD #2112)", () => {
  const T = tabela();
  type Item = PerguntaDaVitta & { demanda_id: string; demanda: string; minha: boolean };
  const lista = () => T["perguntas/esperando"] as Item[];
  // A Pergunta do diretor; o Passo a passo dele, também na lista, tem o describe próprio (issue #2184).
  const doDiretor = () => lista().find((p) => p.minha && (p.tipo ?? "pergunta") === "pergunta")!;

  it("a lista tem as Perguntas abertas no formato que a tela aceita, as do diretor primeiro, e só a dele se responde no cartão da lista", () => {
    const itens = lista();
    expect(Array.isArray(itens)).toBe(true);
    for (const p of itens) {
      expect(perguntaValida(p), `a Pergunta ${p.id} não serve`).toBe(true);
      expect(typeof p.demanda).toBe("string");
      expect(p.estado).toBe("aberta");
      // Desde a issue #2145 o cartão da lista responde: o print mostra o campo na do diretor.
      expect(p.pode_responder ?? false).toBe(p.minha);
    }
    const minhas = itens.map((p) => p.minha);
    expect(minhas).toContain(true);
    expect(minhas).toContain(false);
    expect(minhas).toEqual([...minhas].sort((a, b) => Number(b) - Number(a)));
  });

  it("a Conversa do pedido da Pergunta do diretor traz o mesmo cartão, com opções, a recomendada e o porquê, para responder", () => {
    const pergunta = doDiretor();
    const conversa = T[`chat/${pergunta.demanda_id}/conversa`] as { mensagens: { pergunta?: PerguntaDaVitta | null }[] };
    const cartao = conversa.mensagens.map((m) => m.pergunta).find((p) => p?.id === pergunta.id);
    expect(cartao, "a Conversa não tem o cartão da Pergunta").toBeDefined();
    expect(cartao!.estado).toBe("aberta");
    expect(cartao!.pode_responder).toBe(true);
    const letras = (cartao!.opcoes ?? []).map((o) => o.letra);
    expect(letras.length).toBeGreaterThanOrEqual(2);
    expect(letras).toContain(cartao!.recomendada);
    expect(cartao!.porque).toEqual(expect.any(String));
  });

  it("o Me explique da Pergunta começa pela explicação do Assistente e traz um rascunho de resposta", () => {
    const conversa = T[`perguntas/${doDiretor().id}/me-explique`] as { mensagens: FalaDoMeExplique[] };
    expect(conversa?.mensagens?.[0]?.papel).toBe("assistente");
    expect(conversa.mensagens.some((m) => m.papel === "pessoa")).toBe(true);
    expect(conversa.mensagens.some((m) => m.papel === "assistente" && typeof m.rascunho === "string")).toBe(true);
  });

  it("nenhum texto da Pergunta chama ela de Pendência (ADR 0109, decisão 2)", () => {
    const textos = [lista(), T[`perguntas/${doDiretor().id}/me-explique`]].flatMap(folhas);
    expect(textos.filter((t) => /pend[êe]ncia/i.test(t))).toEqual([]);
  });
});

describe("o Passo a passo da Vitta na lista Esperando você (issue #2184, ADR 0110)", () => {
  const T = tabela();
  type Item = PerguntaDaVitta & { demanda_id: string; demanda: string; minha: boolean };
  const lista = () => T["perguntas/esperando"] as Item[];
  const passoAPasso = () => {
    const achado = lista().find((p) => p.tipo === "passo_a_passo");
    expect(achado, "a lista não tem um Passo a passo").toBeDefined();
    return achado!;
  };

  it("a lista junta os três tipos de pedido, a pergunta, o passo a passo e o Pedido de implantação", () => {
    const tipos = new Set(lista().map((p) => p.tipo ?? "pergunta"));
    expect([...tipos].sort()).toEqual(["implantacao", "passo_a_passo", "pergunta"]);
  });

  it("o passo a passo espera o diretor, aberto, e ele marca e conclui no cartão da lista", () => {
    const passo = passoAPasso();
    expect(perguntaValida(passo)).toBe(true);
    expect(passo.estado).toBe("aberta");
    expect(passo.minha).toBe(true);
    expect(passo.pode_responder).toBe(true);
    expect(passo.destinatario).toBe(SEED.admin.nome);
    expect((T["chat"] as Demanda[]).some((d) => d.id === passo.demanda_id && d.titulo === passo.demanda)).toBe(true);
  });

  it("o print pega o cartão no meio: um passo marcado pelo diretor, com a hora, e outro ainda sem check", () => {
    const passos = passoAPasso().passos ?? [];
    const marcados = passos.filter((p) => p.marcado);
    expect(marcados.length).toBeGreaterThan(0);
    for (const p of marcados) {
      expect(p.por).toBe(SEED.admin.nome);
      expect(Number.isNaN(Date.parse(p.em ?? ""))).toBe(false);
    }
    expect(passos.some((p) => !p.marcado)).toBe(true);
  });

  it("o último passo é o Como saber que acabou", () => {
    expect(passoAPasso().passos?.at(-1)?.texto).toMatch(/^Como saber que acabou: /);
  });

  it("o roteiro abre a aba no cartão do passo a passo, pelo ?pergunta= do aviso", () => {
    const texto = readFileSync(ROTEIRO, "utf8");
    expect(texto).toMatch(/\?pergunta=\$\(seed "\['passo_a_passo'\]\['id'\]"\)/);
    expect(passoAPasso().id).toBe(SEED.passo_a_passo.id);
  });
});

describe("o Pedido de implantação, a seção Implantação e o Achei um problema na tabela (issue #2211, ADR 0111)", () => {
  const T = tabela();
  const E = envio();
  const lista = T["chat"] as Demanda[];
  type Item = PerguntaDaVitta & { demanda_id: string; demanda: string; minha: boolean };
  const implantacoes = () => (T["perguntas/esperando"] as Item[]).filter((p) => p.tipo === "implantacao");
  const entrega = () => lista.find((d) => d.id === SEED.implantacao.demanda)!;

  it("a entrega Em produção tem a Implantação do servidor e o selo Implantação 1 de 3 no Quadro", () => {
    const d = entrega();
    expect(d.etapa).toBe("em_producao");
    expect(seloDaImplantacao(d)).toBe("Implantação 1 de 3");
    // Como o servidor manda: só Feito ou Aberto, sem espera na linha.
    const pedidos = d.implantacao!.pedidos;
    expect(pedidos.map((p) => p.situacao).sort()).toEqual(["aberto", "aberto", "feito"]);
    expect(pedidos.every((p) => p.espera === null)).toBe(true);
    const ondeCai = colunasDoQuadro(lista, false, new Date()).find((c) => c.cards.some((x) => x.id === d.id));
    expect(ondeCai, "a entrega com Implantação não cai em coluna nenhuma do Quadro de hoje").toBeDefined();
  });

  it("os Pedidos de implantação abertos da entrega esperam o diretor na lista, com os passos, e um deles espera o outro", () => {
    const abertos = implantacoes();
    expect(abertos).toHaveLength(2);
    for (const p of abertos) {
      expect(perguntaValida(p)).toBe(true);
      expect(p.demanda_id).toBe(SEED.implantacao.demanda);
      expect(p.minha && p.pode_responder).toBe(true);
      expect(p.passos?.length).toBeGreaterThan(0);
    }
    const queEspera = abertos.find((p) => p.espera)!;
    expect(queEspera, "nenhum Pedido de implantação espera outro").toBeDefined();
    const esperado = abertos.find((p) => p.id === queEspera.espera!.pedido_id);
    expect(esperado?.assunto).toBe(queEspera.espera!.assunto);
    // O que espera outro ainda tem o Achei um problema: não espera bug nenhum.
    expect(queEspera.espera_demanda ?? null).toBeNull();
    expect(queEspera.passos?.every((p) => p.marcado)).toBe(true);
  });

  it("o outro Pedido espera uma Demanda de bug do Quadro, ainda não entregue", () => {
    const comBug = implantacoes().find((p) => p.espera_demanda);
    expect(comBug, "nenhum Pedido de implantação espera a Demanda do bug").toBeDefined();
    const bug = lista.find((d) => d.id === comBug!.espera_demanda!.demanda_id)!;
    expect(bug.classificacao).toBe("bug");
    expect(bug.numero).toBe(comBug!.espera_demanda!.numero);
    expect(["entregue", "em_producao"]).not.toContain(bug.etapa);
  });

  it("o Achei um problema responde a Demanda de bug nova, cuja conversa abre com o texto do Pedido e da entrega", () => {
    const queEspera = implantacoes().find((p) => p.espera)!;
    const nova = E["chat"] as { demanda_id: string };
    const bug = lista.find((d) => d.id === nova.demanda_id)!;
    expect(bug.classificacao).toBe("bug");
    expect(bug.etapa).toBe("registrada");
    const conversa = T[`chat/${bug.id}`] as { estado: string; mensagens: { autor: string; texto: string }[] };
    expect(conversaValida(conversa)).toBe(true);
    expect(conversa.estado).toBe("em_andamento");
    // O texto que o servidor monta (TEXTO_DO_PROBLEMA, issue #2210).
    expect(conversa.mensagens[0]).toMatchObject({
      autor: "diretor",
      texto: `Achei um problema no Pedido de implantação "${queEspera.assunto}", da entrega "${entrega().titulo}".`,
    });
    expect(conversa.mensagens.at(-1)?.autor).toBe("ia");
  });

  it("o roteiro abre a aba em cada Pedido de implantação e clica no Achei um problema", () => {
    const texto = readFileSync(ROTEIRO, "utf8");
    for (const p of implantacoes()) {
      const i = SEED.implantacao.pedidos.findIndex((s: { id: string }) => s.id === p.id);
      expect(texto).toContain(`?pergunta=$(seed "['implantacao']['pedidos'][${i}]['id']")`);
    }
    expect(texto).toMatch(/getByRole\('button', \{ name: 'Achei um problema' \}\)\.click\(\)/);
  });
});

describe("o Ver o plano e o Envio aos desenvolvedores na tabela (issue #2015, PRD #2007)", () => {
  const T = tabela();
  const lista = T["chat"] as Demanda[];
  const E = envio();
  const id = SEED.abrir.envio as string;
  const conversa = () => T[`chat/${id}/conversa`] as {
    mensagens: { texto: string; minha: boolean; criado_em: string }[];
    envio?: { mensagens_novas: number };
  };

  it("o Quadro tem um card com o plano já validado e outro com o plano por validar, os dois com link que a tela desenha", () => {
    const comPlano = lista.filter((d) => linkDoPlano(d) !== null);
    expect(comPlano.some((d) => d.plano_validado === true)).toBe(true);
    expect(comPlano.some((d) => d.plano_validado === false)).toBe(true);
  });

  it("a Conversa do pedido do envio termina em mensagens do diretor, e o botão conta só essas", () => {
    const { mensagens, envio: botao } = conversa();
    const finais = mensagens.length - mensagens.findLastIndex((m) => !m.minha) - 1;
    expect(finais).toBeGreaterThan(0);
    expect(botao).toEqual({ mensagens_novas: finais });
  });

  it("o interpretar responde o Entendi assim, com tópicos e o que muda em cada parte do pedido", () => {
    const entendi = E[`chat/${id}/conversa/interpretar`] as { id: string; topicos: string[]; cards: { numero: number; muda: string }[] };
    expect(entendi.id).toEqual(expect.any(String));
    expect(entendi.topicos.length).toBeGreaterThan(0);
    const partes = (lista.find((d) => d.id === id)!.partes ?? []).map((p) => p.numero);
    expect(entendi.cards.length).toBeGreaterThan(0);
    for (const card of entendi.cards) expect(partes).toContain(card.numero);
  });

  it("os tópicos não copiam a fala do diretor (ADR 0083, decisão 8)", () => {
    const entendi = E[`chat/${id}/conversa/interpretar`] as { topicos: string[] };
    const falas = conversa().mensagens.filter((m) => m.minha).map((m) => m.texto.toLocaleLowerCase("pt-BR"));
    for (const topico of entendi.topicos) {
      expect(falas.some((f) => f.includes(topico.toLocaleLowerCase("pt-BR").replace(/\.$/, "")))).toBe(false);
    }
  });

  it("o enviar responde a linha Enviado aos desenvolvedores, do sistema, com a data, a hora e os tópicos aprovados", () => {
    const entendi = E[`chat/${id}/conversa/interpretar`] as { topicos: string[] };
    const linha = E[`chat/${id}/conversa/enviar`] as { id: string; texto: string; sistema: boolean; minha: boolean };
    expect(linha.sistema).toBe(true);
    expect(linha.minha).toBe(false);
    expect(linha.texto).toMatch(/^Enviado aos desenvolvedores em \d{2}\/\d{2}\/\d{4}, às \d{2}:\d{2}:\n/);
    expect(linha.texto.split("\n").slice(1)).toEqual(entendi.topicos.map((t) => `- ${t}`));
  });

  it("a linha Enviado vem logo depois das mensagens que ela resume, a qualquer hora que o roteiro rode", () => {
    const linha = E[`chat/${id}/conversa/enviar`] as { texto: string; criado_em: string };
    const ultima = Date.parse(conversa().mensagens.at(-1)!.criado_em);
    const enviado = Date.parse(linha.criado_em);
    expect(enviado).toBeGreaterThan(ultima);
    expect(enviado - ultima).toBeLessThanOrEqual(60 * 60 * 1000);
    const [, hora, minuto] = linha.criado_em.match(/T(\d{2}):(\d{2})/)!;
    expect(linha.texto).toContain(`às ${hora}:${minuto}:`);
  });

  it("o roteiro só responde um pedido que não é GET pela tabela do envio, e o resto continua recusado", () => {
    const texto = readFileSync(ROTEIRO, "utf8");
    expect(texto).toMatch(/respostas\.py" --envio/);
    expect(Object.keys(E).sort()).toEqual(["chat", `chat/${id}/conversa/enviar`, `chat/${id}/conversa/interpretar`]);
    // O POST do chat só responde o Achei um problema, que manda o Pedido (issue #2211).
    expect(texto).toMatch(/chave !== 'chat' \|\| corpo\?\.pedido_id/);
  });

  it("as respostas do envio não trazem e-mail, telefone, endereço nem nome de gente de verdade", () => {
    expect(folhas(E).flatMap(dadoReal)).toEqual([]);
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

  it("o sino de exemplo não traz e-mail, telefone, endereço nem nome de gente de verdade", () => {
    expect(folhas(sino()).flatMap(dadoReal)).toEqual([]);
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
