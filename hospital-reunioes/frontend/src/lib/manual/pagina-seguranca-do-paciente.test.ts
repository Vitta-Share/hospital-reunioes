/**
 * A página de Segurança do Paciente do manual (issue #1780, PRD #1764, e
 * issue #2003, PRD #1979).
 *
 * Lê o Markdown de verdade, em `public/manual/seguranca-do-paciente/pagina.md`,
 * e prova o que as issues prometem dele: só quem tem o módulo no menu vê a
 * página, cada tarefa tem passos numerados e print, e os fluxogramas, o do
 * membro, o da reunião e o da notificação, desenham o processo como ele ficou.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MarkdownDoManual } from "@/components/manual/MarkdownDoManual";
import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { lerFluxograma, type Fluxo, type Passo } from "@/components/manual/fluxograma/fluxo";
import { carregarPaginasDoManual } from "./carregar";
import { fluxogramasCitados, imagensCitadas, paginasVisiveis } from "./paginas";

const PAGINAS = carregarPaginasDoManual();
const PAGINA = PAGINAS.find((p) => p.modulo === "seguranca-do-paciente");
const TAREFAS = [
  "Cadastrar um membro e acompanhar o Termo",
  "Renovar ou encerrar uma participação",
  "Publicar uma revisão do Regimento",
  "Registrar uma capacitação e confirmar presença",
  "Acompanhar a agenda regulatória",
  "Fazer a reunião do Núcleo, da pauta à ata assinada",
  // A notificação de incidente, a triagem e os prazos (issue #2003, PRD #1979).
  "Notificar um incidente pelo QR, pelo endereço ou pelo botão do módulo",
  "Acompanhar uma notificação",
  "Fazer a triagem de uma notificação",
  "Encaminhar uma notificação a outro canal",
  "Fazer um registro rápido",
  "Registrar a ausência da Presidência",
  "Ajustar a tabela de prazos",
  "Recalibrar o agente",
  // Quem assina os documentos do Núcleo (issue #2251, PRD #2247).
  "Marcar o Responsável técnico",
];

function pessoa(campos: Partial<CurrentParticipante>): CurrentParticipante {
  return {
    id: "p1",
    nome_completo: "Fulana de Tal",
    email: "fulana@hsm",
    access_profile: "regular",
    perfil_pop: null,
    perfil_ouvidoria: null,
    perfil_contas_medicas: null,
    ...campos,
  };
}

/** As seções `## ` do corpo, com o título e o texto de cada uma. */
function secoes(corpo: string): { titulo: string; texto: string }[] {
  return corpo
    .split(/^## /m)
    .slice(1)
    .map((bloco) => {
      const [titulo, ...resto] = bloco.split("\n");
      return { titulo: titulo.trim(), texto: resto.join("\n") };
    });
}

function secao(titulo: string) {
  const achada = secoes(PAGINA!.corpo).find((s) => s.titulo === titulo);
  expect(achada, `a página não tem a seção "${titulo}"`).toBeDefined();
  return achada!;
}

/** Os passos que se alcançam saindo de um, pelas ligações, sem passar pelos de `evitar`. */
function alcancaveis(fluxo: Fluxo, de: string, evitar: Set<string> = new Set()): Set<string> {
  const vistos = new Set([de]);
  const fila = [de];
  while (fila.length) {
    const atual = fila.shift()!;
    for (const l of fluxo.ligacoes) {
      if (l.de === atual && !vistos.has(l.para) && !evitar.has(l.para)) {
        vistos.add(l.para);
        fila.push(l.para);
      }
    }
  }
  return vistos;
}

function passoPorRotulo(fluxo: Fluxo, rotulo: RegExp): Passo {
  const passo = fluxo.passos.find((p) => rotulo.test(p.rotulo));
  if (!passo) throw new Error(`O fluxograma não tem um passo ${rotulo}.`);
  return passo;
}

/** O fluxograma da seção: um bloco só, lido sem erro. */
function fluxoDa(titulo: string): Fluxo {
  const blocos = fluxogramasCitados(secao(titulo).texto);
  expect(blocos, `a seção "${titulo}" deveria ter um fluxograma só`).toHaveLength(1);
  const leitura = lerFluxograma(blocos[0]);
  if (!leitura.ok) throw new Error(leitura.erros.join("\n"));
  return leitura.fluxo;
}

function inicioDe(fluxo: Fluxo): Passo {
  const inicios = fluxo.passos.filter((p) => p.forma === "inicio");
  expect(inicios).toHaveLength(1);
  return inicios[0];
}

describe("a página de Segurança do Paciente do manual", () => {
  it("existe e aparece para quem tem o módulo no menu", () => {
    expect(PAGINA?.pasta).toBe("seguranca-do-paciente");
    const membro = pessoa({ recursos_nsp: ["ver_modulo", "painel", "calendario", "agenda"] });
    expect(paginasVisiveis(PAGINAS, membro).map((p) => p.modulo)).toContain("seguranca-do-paciente");
  });

  it.each([
    ["o super admin sem Acesso pleno, que não tem o módulo no menu", pessoa({ access_profile: "super_admin" })],
    ["quem não tem nenhum recurso do Núcleo", pessoa({ recursos_nsp: [] })],
  ])("não aparece para %s", (_quem, participante) => {
    expect(paginasVisiveis(PAGINAS, participante).map((p) => p.modulo)).not.toContain("seguranca-do-paciente");
  });

  it.each(TAREFAS)("a tarefa %s tem passos numerados e pelo menos um print", (tarefa) => {
    const { texto } = secao(tarefa);
    const passos = texto.match(/^\d+\. /gm) ?? [];
    expect(passos.slice(0, 2)).toEqual(["1. ", "2. "]);
    expect(imagensCitadas(texto).length).toBeGreaterThan(0);
  });

  it.each(TAREFAS)("a tarefa %s sai na tela como uma lista só, numerada em sequência", (tarefa) => {
    const { texto } = secao(tarefa);
    const numeros = (texto.match(/^\d+(?=\. )/gm) ?? []).map(Number);
    expect(numeros).toEqual(numeros.map((_, i) => i + 1));
    // O `ol` do manual não repassa o `start`: um print fora do item fecha a
    // lista e a próxima recomeça em 1 na tela. Uma lista só, com todos os passos.
    const html = renderToStaticMarkup(MarkdownDoManual({ pasta: "seguranca-do-paciente", children: texto }));
    expect(html.match(/<ol[ >]/g) ?? []).toHaveLength(1);
    expect(html.match(/<li[ >]/g) ?? []).toHaveLength(numeros.length);
  });

  it("chama o primeiro item do submenu de Visão geral, o nome que a pessoa vê no menu (#1949)", () => {
    const menu = PAGINA!.corpo.split("\n").find((linha) => linha.startsWith("Ele fica no menu da esquerda"));
    expect(menu, "a página não diz onde o módulo fica no menu").toBeDefined();
    const itens = Array.from(menu!.split(". Dentro de")[0].matchAll(/\*\*([^*]+)\*\*/g), (m) => m[1]);
    expect(itens).toEqual(["NSP", "Visão geral", "Reuniões", "Núcleo"]);
    expect(PAGINA!.corpo).not.toMatch(/\*\*Início\*\*/);
  });

  it("o registro da capacitação pede a formação do instrutor e diz o que aparece nas antigas (#1931)", () => {
    const { texto } = secao(TAREFAS[3]);
    expect(texto).toContain("**Formação do instrutor**");
    expect(texto).toContain('"Formação não informada"');
  });

  it("leva ao menu pelo nome que a pessoa vê, NSP, e não pelo antigo (issue #1918)", () => {
    expect(PAGINA!.corpo).toMatch(/\*\*NSP\*\*/);
    expect(PAGINA!.corpo).not.toMatch(/\*\*Segurança do Paciente\*\*/);
    expect(PAGINA!.corpo).not.toMatch(/grupo \**Segurança do Paciente/);
  });

  it("não traz travessão nem meia-risca", () => {
    expect(PAGINA!.corpo).not.toMatch(/[\u2013\u2014]/);
  });

  it("a reunião diz o que a decisão do reenvio da ata fixou: todos os presentes, e o prazo recomeça", () => {
    const reenvio = secao(TAREFAS[5])
      .texto.split(/^(?=\d+\. )/m)
      .find((p) => /\*\*Reenviar para assinatura\*\*/.test(p));
    expect(reenvio, "nenhum passo da reunião fala do Reenviar para assinatura").toBeDefined();
    expect(reenvio).toMatch(/todos os presentes/);
    expect(reenvio).toMatch(/5 dias úteis recomeçam/);
  });
});

describe("quem assina os documentos do Núcleo (#2251)", () => {
  /** Os passos numerados de uma seção, cada um com o texto até o próximo. */
  function passos(titulo: string): string[] {
    return secao(titulo).texto.split(/^(?=\d+\. )/m).filter((p) => /^\d+\. /.test(p));
  }

  it("o envio do Regimento vai para o Responsável técnico e para a Presidência, e não para a Diretoria Executiva", () => {
    const envio = passos("Publicar uma revisão do Regimento").find((p) => /\*\*Enviar para assinatura\*\*/.test(p));
    expect(envio, "nenhum passo do Regimento fala do Enviar para assinatura").toBeDefined();
    expect(envio).toMatch(/Responsável técnico/);
    expect(envio).toMatch(/Presidência do Núcleo/);
    expect(envio).not.toMatch(/Diretoria Executiva/);
  });

  it("o fecho do Regimento diz que o Ato de designação é assinado só pelo Responsável técnico", () => {
    const { texto } = secao("Publicar uma revisão do Regimento");
    const fecho = texto.split("\n").filter((l) => /ato de designação/i.test(l) && !/^\d+\. /.test(l));
    expect(fecho, "o fecho não fala do Ato de designação").toHaveLength(1);
    expect(fecho[0]).toMatch(/só pelo Responsável técnico/);
    expect(fecho[0]).not.toMatch(/Diretoria Executiva/);
  });

  it("marcar o Responsável técnico passa pelo cadastro de usuários e avisa que sem ninguém marcado o envio não sai", () => {
    const { texto } = secao("Marcar o Responsável técnico");
    expect(texto).toMatch(/\*\*Admin\*\*/);
    expect(texto).toMatch(/\*\*Usuários\*\*/);
    expect(texto).toMatch(/\*\*Responsável técnico\*\*/);
    expect(texto).toMatch(/desmarca/);
    expect(texto).toContain("Não há Responsável técnico marcado no cadastro para assinar");
  });

  it("a abertura da página cita o link de voltar do alto das telas (#2249)", () => {
    const abertura = PAGINA!.corpo.split(/^## /m)[0];
    expect(abertura).toMatch(/\*\*Núcleo de Segurança do Paciente\*\*, com a seta de voltar/);
  });
});

describe("o fluxograma do ciclo do membro", () => {
  const TITULO = "O ciclo do membro";

  it("lê sem erro e começa num só lugar, o cadastro", () => {
    expect(inicioDe(fluxoDa(TITULO)).rotulo).toMatch(/Cadastrar/);
  });

  it("do cadastro só se chega a Ativo pela assinatura do Termo ou pela liberação com justificativa", () => {
    const f = fluxoDa(TITULO);
    const inicio = inicioDe(f);
    const ativo = passoPorRotulo(f, /^Ativo$/);
    expect(alcancaveis(f, inicio.id).has(ativo.id)).toBe(true);
    const semAssinaturaNemLiberacao: Fluxo = {
      ...f,
      ligacoes: f.ligacoes.filter((l) => {
        const origem = f.passos.find((p) => p.id === l.de)!;
        const pelaAssinatura = origem.forma === "decisao" && /assinou/i.test(origem.rotulo) && l.rotulo === "sim";
        const pelaLiberacao = /justificativa/.test(l.rotulo);
        return !(pelaAssinatura || pelaLiberacao);
      }),
    };
    expect(alcancaveis(semAssinaturaNemLiberacao, inicio.id).has(ativo.id)).toBe(false);
  });

  it("renovar, mudar o papel ou a revisão material do Regimento mandam um Termo novo", () => {
    const f = fluxoDa(TITULO);
    const termoNovo = passoPorRotulo(f, /^Termo novo$/);
    const voltas = f.ligacoes.filter((l) => l.para === termoNovo.id).map((l) => l.rotulo).join(" ");
    expect(voltas).toMatch(/renov/i);
    expect(voltas).toMatch(/papel/);
    expect(voltas).toMatch(/revisão material/);
  });

  it("o Termo novo de quem já assinou não leva a Aguardando assinatura nem aos avisos de 3, 7 e 14 dias", () => {
    const f = fluxoDa(TITULO);
    const ativo = passoPorRotulo(f, /^Ativo$/);
    const termo = passoPorRotulo(f, /^Termo enviado$/);
    const espera = passoPorRotulo(f, /^Aguardando assinatura$/);
    const termoNovo = passoPorRotulo(f, /^Termo novo$/);
    const depoisDeAtivo = alcancaveis(f, ativo.id);
    expect(depoisDeAtivo.has(termoNovo.id)).toBe(true);
    expect(depoisDeAtivo.has(termo.id), "quem já assinou volta ao Termo da primeira assinatura").toBe(false);
    expect(depoisDeAtivo.has(espera.id), "quem já assinou volta a Aguardando assinatura").toBe(false);
    expect(termoNovo.detalhe).toMatch(/continua no estado em que estava/);
  });

  it("Em carência ainda dá para renovar, e a renovação não leva a Vencido", () => {
    const f = fluxoDa(TITULO);
    const carencia = passoPorRotulo(f, /^Em carência$/);
    const vencido = passoPorRotulo(f, /^Vencido$/);
    const renovacoes = f.ligacoes.filter((l) => l.de === carencia.id && /renov/i.test(l.rotulo));
    expect(renovacoes.length, "Em carência não tem saída por renovação").toBeGreaterThan(0);
    for (const l of renovacoes) {
      expect(l.para, `${l.de} -> ${l.para} renova direto para Vencido`).not.toBe(vencido.id);
    }
  });

  it("sem renovação, o membro passa pela carência antes de vencer, e o Encerrado se alcança do cadastro", () => {
    const f = fluxoDa(TITULO);
    const inicio = inicioDe(f);
    const carencia = passoPorRotulo(f, /^Em carência$/);
    const vencido = passoPorRotulo(f, /^Vencido$/);
    const encerrado = passoPorRotulo(f, /^Encerrado$/);
    expect(vencido.forma).toBe("fim");
    expect(encerrado.forma).toBe("fim");
    expect(alcancaveis(f, inicio.id).has(encerrado.id)).toBe(true);
    expect(alcancaveis(f, inicio.id, new Set([carencia.id])).has(vencido.id)).toBe(false);
  });
});

describe("o fluxograma do ciclo da reunião", () => {
  const TITULO = "O ciclo da reunião";

  it("lê sem erro e começa num só lugar, o calendário", () => {
    expect(inicioDe(fluxoDa(TITULO)).rotulo).toMatch(/Calendário/);
  });

  it("termina na ata encerrada, que só se alcança passando pela validação da Presidência", () => {
    const f = fluxoDa(TITULO);
    const inicio = inicioDe(f);
    const encerrada = passoPorRotulo(f, /^Ata encerrada$/);
    const validar = passoPorRotulo(f, /Validar/);
    expect(encerrada.forma).toBe("fim");
    expect(alcancaveis(f, inicio.id).has(encerrada.id)).toBe(true);
    expect(alcancaveis(f, inicio.id, new Set([validar.id])).has(encerrada.id)).toBe(false);
  });

  it("sem quórum, a reunião fica não instalada e volta com uma nova data", () => {
    const f = fluxoDa(TITULO);
    const quorum = passoPorRotulo(f, /quórum/);
    expect(quorum.forma).toBe("decisao");
    const naoInstalada = passoPorRotulo(f, /^Não instalada$/);
    expect(f.ligacoes).toContainEqual({ de: quorum.id, para: naoInstalada.id, rotulo: "não" });
    expect(alcancaveis(f, naoInstalada.id).has(quorum.id)).toBe(true);
  });

  it("o envio cancelado volta para a assinatura pelo reenvio, sem pular para o encerramento", () => {
    const f = fluxoDa(TITULO);
    const reenvio = passoPorRotulo(f, /^Reenviar para assinatura$/);
    const assinatura = passoPorRotulo(f, /^Assinatura dos presentes$/);
    const encerrada = passoPorRotulo(f, /^Ata encerrada$/);
    expect(reenvio.detalhe).toMatch(/todos os presentes/);
    expect(f.ligacoes.filter((l) => l.de === reenvio.id).map((l) => l.para)).toEqual([assinatura.id]);
    expect(f.ligacoes.some((l) => l.de === reenvio.id && l.para === encerrada.id)).toBe(false);
  });
});

describe("o fluxograma do ciclo da notificação (#2003)", () => {
  const TITULO = "O ciclo da notificação";

  it("lê sem erro e começa num só lugar, a notificação", () => {
    expect(inicioDe(fluxoDa(TITULO)).rotulo).toMatch(/Notificação/);
  });

  it("o protocolo sai antes de qualquer triagem, e o alerta do caso grave também", () => {
    const f = fluxoDa(TITULO);
    const inicio = inicioDe(f);
    const triagem = passoPorRotulo(f, /^Triagem da Presidência$/);
    const protocolo = passoPorRotulo(f, /^Protocolo na hora$/);
    const alerta = passoPorRotulo(f, /^Alerta por e-mail$/);
    const antesDaTriagem = alcancaveis(f, inicio.id, new Set([triagem.id]));
    expect(antesDaTriagem.has(protocolo.id)).toBe(true);
    expect(antesDaTriagem.has(alerta.id)).toBe(true);
  });

  it("só se chega a Classificada passando pela triagem da Presidência", () => {
    const f = fluxoDa(TITULO);
    const inicio = inicioDe(f);
    const triagem = passoPorRotulo(f, /^Triagem da Presidência$/);
    const classificada = passoPorRotulo(f, /^Classificada$/);
    expect(alcancaveis(f, inicio.id).has(classificada.id)).toBe(true);
    expect(alcancaveis(f, inicio.id, new Set([triagem.id])).has(classificada.id)).toBe(false);
  });

  it("fora de escopo encerra o caso, e as faixas A e B levam à reunião de análise", () => {
    const f = fluxoDa(TITULO);
    const inicio = inicioDe(f);
    const fora = passoPorRotulo(f, /^Fora de escopo$/);
    const reuniao = passoPorRotulo(f, /^Reunião de análise$/);
    expect(fora.forma).toBe("fim");
    expect(alcancaveis(f, inicio.id).has(fora.id)).toBe(true);
    expect(f.ligacoes.filter((l) => l.para === reuniao.id).map((l) => l.rotulo).join(" ")).toMatch(/A ou B/);
  });
});

describe("a triagem com o agente desligado (#2003)", () => {
  it("ensina a classificar à mão, a tela que toda notificação abre enquanto o agente está desligado", () => {
    const { texto } = secao("Fazer a triagem de uma notificação");
    expect(texto).toMatch(/\*\*Classificar manualmente\*\*/);
    expect(texto).toMatch(/\*\*Confirmar a classificação\*\*/);
  });
});
