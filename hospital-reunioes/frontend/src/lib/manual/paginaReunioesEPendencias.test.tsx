/**
 * @vitest-environment jsdom
 */

/**
 * A página de Reuniões e Pendências do manual (issue #1721, ADR 0094).
 *
 * Os testes leem o Markdown de verdade, do disco, e não uma cópia: a página que
 * a pessoa abre é a mesma que eles conferem. As tarefas esperadas vêm da
 * issue (marcar a reunião, anexar a transcrição, revisar a Ata, mandar para
 * assinatura e acompanhar as Pendências).
 */

import { existsSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MarkdownDoManual } from "@/components/manual/MarkdownDoManual";
import { lerFluxograma, type Fluxo } from "@/components/manual/fluxograma/fluxo";
import { itensDoMenu } from "@/components/layout/Sidebar";
import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { carregarPaginasDoManual } from "./carregar";
import { enderecoDaImagem, imagensCitadas, paginasVisiveis } from "./paginas";

afterEach(() => {
  cleanup();
});

const PAGINAS = carregarPaginasDoManual();
const PAGINA = PAGINAS.find((p) => p.pasta === "reunioes-e-pendencias")!;

function pessoa(papeis: Partial<CurrentParticipante>): CurrentParticipante {
  return { id: "p1", nome_completo: "Fulana de Tal", email: "fulana@hsm", ...papeis };
}

/** As seções `##` da página: o título e o texto até a próxima. */
function secoes(corpo: string): { titulo: string; texto: string }[] {
  return corpo
    .split(/^## /m)
    .slice(1)
    .map((parte) => {
      const [titulo, ...resto] = parte.split("\n");
      return { titulo: titulo.trim(), texto: resto.join("\n") };
    });
}

const FONTE_DO_FLUXOGRAMA = /```fluxograma\n([\s\S]*?)```/;

/** Os passos que se alcançam a partir de `de`, seguindo as ligações. */
function alcancaveis(fluxo: Fluxo, de: string): Set<string> {
  const achados = new Set([de]);
  const fila = [de];
  while (fila.length) {
    const atual = fila.shift()!;
    for (const l of fluxo.ligacoes) {
      if (l.de === atual && !achados.has(l.para)) {
        achados.add(l.para);
        fila.push(l.para);
      }
    }
  }
  return achados;
}

describe("quem vê a página de Reuniões e Pendências", () => {
  it("o Facilitador vê a página, e quem só tem POPs não vê", () => {
    const facilitador = paginasVisiveis(PAGINAS, pessoa({ access_profile: "regular" }));
    const soPops = paginasVisiveis(PAGINAS, pessoa({ access_profile: null, perfil_pop: "coordenador" }));

    expect(facilitador.map((p) => p.pasta)).toContain("reunioes-e-pendencias");
    expect(soPops.map((p) => p.pasta)).not.toContain("reunioes-e-pendencias");
  });
});

describe("as tarefas da página", () => {
  const tarefas = secoes(PAGINA.corpo).filter((s) => !FONTE_DO_FLUXOGRAMA.test(s.texto));

  it("tem as tarefas da issue, da reunião às Pendências", () => {
    const titulos = tarefas.map((t) => t.titulo);
    for (const tarefa of [
      /^Marcar uma reunião$/,
      /^Anexar a transcrição/,
      /^Revisar a Ata$/,
      /^Mandar a Ata para assinatura$/,
      /^Acompanhar as Pendências$/,
    ]) {
      expect(titulos.some((t) => tarefa.test(t)), String(tarefa)).toBe(true);
    }
  });

  it("cada tarefa tem passos numerados e pelo menos um print que existe", () => {
    const semPasso = tarefas.filter((t) => !/^1\. /m.test(t.texto) || !/^2\. /m.test(t.texto));
    const semPrint = tarefas.filter((t) => imagensCitadas(t.texto).length === 0);
    const printsQueFaltam = tarefas
      .flatMap((t) => imagensCitadas(t.texto))
      .map((src) => enderecoDaImagem(PAGINA.pasta, src))
      .filter((endereco) => !existsSync(join(process.cwd(), "public", endereco)));

    expect(tarefas.length).toBeGreaterThanOrEqual(5);
    expect(semPasso.map((t) => t.titulo)).toEqual([]);
    expect(semPrint.map((t) => t.titulo)).toEqual([]);
    expect(printsQueFaltam).toEqual([]);
  });
});

describe("as reuniões do Núcleo de Segurança do Paciente (issue #1781)", () => {
  const listaDeReunioes = secoes(PAGINA.corpo).find((s) => s.titulo === "Ver as reuniões do mês")!;

  it("a seção da lista de reuniões diz que as do Núcleo ficam no módulo Segurança do Paciente", () => {
    const linha = listaDeReunioes.texto.split("\n").find((l) => /Núcleo de Segurança do Paciente/.test(l)) ?? "";

    expect(linha).toMatch(/módulo \*\*Segurança do Paciente\*\*/);
    expect(linha).toMatch(/\*\*Reuniões\*\*/);
  });

  it("a página não tem travessão nem meia-risca", () => {
    const comTraco = PAGINA.corpo.split("\n").filter((l) => /[–—]/.test(l));

    expect(comTraco).toEqual([]);
  });
});

describe("entrar no app pelo Início (issue #1948)", () => {
  const entrar = secoes(PAGINA.corpo).find((s) => /^Entrar no app/.test(s.titulo));
  // O menu de verdade do Facilitador: a página tem de nomear os itens que ele vê.
  const menu = itensDoMenu(pessoa({ access_profile: "regular" }));
  const passo = (n: number) => entrar?.texto.match(new RegExp(`^${n}\\. .*$`, "m"))?.[0] ?? "";

  it("a tarefa de entrar no app existe, com passos numerados", () => {
    expect(entrar).toBeDefined();
    expect(passo(1)).not.toBe("");
    expect(passo(2)).not.toBe("");
  });

  it("diz que o app abre no Início, o primeiro item do menu", () => {
    expect(menu[0]).toMatchObject({ href: "/inicio", label: "Início" });
    expect(passo(1)).toMatch(new RegExp(`abre no \\*\\*${menu[0].label}\\*\\*`));
  });

  it("leva ao painel de Reuniões pelo item do menu que abre o painel", () => {
    const grupo = menu.find((i) => i.subItems?.some((s) => s.href === "/dashboard"))!;
    const painel = grupo.subItems!.find((s) => s.href === "/dashboard")!;

    expect(passo(2)).toMatch(new RegExp(`clique em \\*\\*${painel.label}\\*\\* \\(2\\)`));
    // O grupo já começa aberto (Sidebar, estado inicial): clicar nele fecha o
    // grupo e esconde o painel. A página nomeia o grupo, sem mandar clicar nele.
    expect(passo(2)).toMatch(new RegExp(`\\*\\*${grupo.label}\\*\\*[^.]*já aparece aberto`));
    expect(passo(2)).not.toMatch(new RegExp(`(abra|clique em) \\*\\*${grupo.label}\\*\\*`));
    expect(entrar?.texto).not.toMatch(/\(3\)/);
  });

  it("o print da tarefa é a tela do Início, e ele existe", () => {
    const prints = imagensCitadas(entrar?.texto ?? "");

    expect(prints).toContain("inicio.png");
    expect(existsSync(join(process.cwd(), "public", enderecoDaImagem(PAGINA.pasta, "inicio.png")))).toBe(true);
  });
});

describe("o fluxograma da página", () => {
  const fonte = FONTE_DO_FLUXOGRAMA.exec(PAGINA.corpo)?.[1] ?? "";

  it("vai da reunião até a Ata assinada e às Pendências, que nascem no envio (issue #1880)", () => {
    const leitura = lerFluxograma(fonte);
    if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
    const { fluxo } = leitura;
    const porRotulo = (rotulo: RegExp) => fluxo.passos.find((p) => rotulo.test(p.rotulo))?.id ?? "";

    const inicio = fluxo.passos.find((p) => p.forma === "inicio");
    const envio = porRotulo(/^Enviar para assinatura$/);
    const assinada = porRotulo(/^Ata assinada$/);
    const pendencias = porRotulo(/^Pendências/);

    expect(inicio?.rotulo).toMatch(/reunião/i);
    expect(alcancaveis(fluxo, inicio!.id)).toContain(assinada);
    expect(alcancaveis(fluxo, envio)).toContain(pendencias);
    // A assinatura é ciência da Ata (ADR 0098): as Pendências não esperam por ela.
    expect(alcancaveis(fluxo, assinada)).not.toContain(pendencias);
  });

  it("a página desenha o fluxograma, sem erro de bloco", () => {
    const { container } = render(<MarkdownDoManual pasta={PAGINA.pasta}>{PAGINA.corpo}</MarkdownDoManual>);

    expect(container.querySelector("[data-fluxograma]")).not.toBeNull();
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });
});

describe("o ciclo de vida, o painel e a Rotina (issue #1880)", () => {
  const todas = secoes(PAGINA.corpo);
  const secao = (titulo: RegExp) => todas.find((s) => titulo.test(s.titulo));

  it("tem uma tarefa para cada coisa que nasceu ou mudou no pedido", () => {
    const titulos = todas.map((s) => s.titulo);
    for (const tarefa of [
      /^Ver o que depende de você no Início$/,
      /^Ler o painel de Reuniões$/,
      /^Classificar as linhas da Ata em Ação, Rotina e Processo$/,
      /^Contestar um item da Ata$/,
      /^Responder a uma Contestação$/,
      /^Concluir uma Pendência e anexar a prova$/,
      /^Repactuar o prazo de uma Pendência$/,
      /^Cancelar ou reabrir uma Pendência$/,
      /^Marcar a Verificação de uma Rotina$/,
      /^Consultar as Definições de processo$/,
      /^Atualizar as Pendências pelo link do e-mail$/,
    ]) {
      expect(titulos.some((t) => tarefa.test(t)), String(tarefa)).toBe(true);
    }
  });

  it("o envio para assinatura é onde as Pendências nascem, não a assinatura", () => {
    const envio = secao(/^Mandar a Ata para assinatura$/)?.texto ?? "";

    expect(envio).toMatch(/Pendências nascem no envio/);
    expect(envio).not.toMatch(/assina já recebe as Pendências/);
  });

  it("o Calendário diz que as reuniões do dia vêm na ordem do horário", () => {
    expect(secao(/^Ver as reuniões do mês$/)?.texto).toMatch(/ordem do horário de início/);
  });
});

describe("o fluxograma do ciclo de vida da Pendência (issue #1880)", () => {
  const blocos = [...PAGINA.corpo.matchAll(/```fluxograma\n([\s\S]*?)```/g)].map((m) => m[1]);
  const ler = (fonte: string) => {
    const leitura = lerFluxograma(fonte);
    if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
    return leitura.fluxo;
  };

  it("no caminho da reunião, as Pendências saem direto do envio para assinatura", () => {
    const fluxo = ler(blocos[0] ?? "");
    const envio = fluxo.passos.find((p) => /^Enviar para assinatura$/.test(p.rotulo))!;
    const pendencias = fluxo.passos.find((p) => /^Pendências/.test(p.rotulo))!;

    expect(fluxo.ligacoes.some((l) => l.de === envio.id && l.para === pendencias.id)).toBe(true);
  });

  it("a Pendência nasce no envio e passa pelos quatro estados, com as ações nas ligações", () => {
    const fluxo = ler(blocos[1] ?? "");
    const id = (rotulo: RegExp) => fluxo.passos.find((p) => rotulo.test(p.rotulo))?.id ?? "?";
    const liga = (de: string, para: string, acao: RegExp) =>
      fluxo.ligacoes.some((l) => l.de === de && l.para === para && acao.test(l.rotulo));

    const nasce = fluxo.passos.find((p) => p.forma === "inicio");
    const [pendente, andamento, concluida, cancelada] = [/^Pendente$/, /^Em progresso$/, /^Concluída$/, /^Cancelada$/].map(
      id
    );
    const repactuacao = id(/^Repactuação$/);
    const reabertura = id(/^Reabertura$/);

    expect(nasce?.rotulo).toMatch(/^Nasce no envio da Ata$/);
    expect(fluxo.ligacoes.some((l) => l.de === nasce!.id && l.para === pendente)).toBe(true);
    expect(liga(pendente, andamento, /^Iniciar$/)).toBe(true);
    expect(liga(andamento, concluida, /^Concluir$/)).toBe(true);
    expect(liga(andamento, cancelada, /^Cancelar$/)).toBe(true);
    expect(liga(pendente, repactuacao, /^Repactuar$/)).toBe(true);
    expect(liga(concluida, reabertura, /^Reabrir$/)).toBe(true);
    expect(alcancaveis(fluxo, reabertura)).toContain(pendente);
    expect(alcancaveis(fluxo, repactuacao)).toContain(pendente);
  });
});
