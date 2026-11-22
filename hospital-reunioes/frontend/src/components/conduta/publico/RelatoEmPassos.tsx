"use client";

/**
 * O relato do Canal de Conduta em passos (issue #1843, especificação seção 4,
 * P0 a P6, no layout que a Diretoria aprovou).
 *
 * Sem login e sem nada no endereço: o passo em que a pessoa está, o que ela
 * escreveu, o protocolo e o código moram só no estado desta tela. Voltar não
 * perde nada; sair da página perde tudo, de propósito. O protocolo e o código
 * aparecem uma vez, no P6, e o rascunho é apagado da memória no mesmo
 * instante em que o servidor responde.
 */

import { useEffect, useRef, useState } from "react";
import { Check, Copy, Loader2, ShieldCheck } from "lucide-react";
import { Logo } from "@/components/ui/Logo";
import {
  ASSUNTOS,
  AVISOS_DO_PASSO_1,
  AVISOS_PADRAO,
  FalhaDoEnvio,
  LIMITE_DO_RELATO,
  LINHA_DA_IA,
  RASCUNHO_VAZIO,
  dataLegivel,
  enviarConfianca,
  enviarRelato,
  lerAvisos,
  type AvisoDoPasso1,
  type Protocolo,
  type Rascunho,
  type SimNaoNaoSei,
  type TextoVigente,
} from "@/lib/conduta/relato";

const TOTAL_DE_PASSOS = 6;

// Alvo de toque de 44 px em tudo que se aperta: a tela é feita para o celular.
const CAMPO =
  "w-full min-h-[44px] rounded-xl border border-border px-3 py-2.5 text-base text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary";
const ROTULO = "block text-sm font-semibold text-slate-700";
const BOTAO_PRINCIPAL =
  "flex w-full min-h-[44px] items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-base font-semibold text-white transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed";
const BOTAO_SECUNDARIO =
  "flex w-full min-h-[44px] items-center justify-center gap-1.5 rounded-xl border border-border bg-white px-4 py-3 text-base font-semibold text-slate-600 hover:border-primary/40";
const CARTAO = "bg-white rounded-2xl border border-border px-5 py-6 space-y-5";

const SIM_NAO_NAO_SEI: { valor: SimNaoNaoSei; rotulo: string }[] = [
  { valor: "sim", rotulo: "Sim" },
  { valor: "nao", rotulo: "Não" },
  { valor: "nao_sei", rotulo: "Não sei" },
];

const E_AQUI = [
  "Assédio moral ou sexual",
  "Discriminação",
  "Violência",
  "Furto, desvio ou fraude",
  "Comissão ou propina",
  "Registro falso",
  "Acesso indevido a dados",
  "Retaliação",
];

function opcao(escolhida: boolean): string {
  return `min-h-[44px] w-full rounded-xl border px-3 py-3 text-base font-semibold text-left transition-colors ${
    escolhida ? "border-primary bg-primary/10 text-primary" : "border-border bg-white text-slate-600 hover:border-primary/40"
  }`;
}

function Opcional() {
  return <span className="font-normal normal-case text-slate-400"> (opcional)</span>;
}

/** Um grupo de escolhas de um toque, com o rótulo lido pelo leitor de tela. */
function Escolhas<T extends string>({
  id,
  rotulo,
  opcoes,
  escolhida,
  aoEscolher,
  opcional = false,
  colunas = "grid-cols-3",
}: {
  id: string;
  rotulo: string;
  opcoes: { valor: T; rotulo: string; detalhe?: string }[];
  escolhida: T | null;
  aoEscolher: (valor: T | null) => void;
  opcional?: boolean;
  colunas?: string;
}) {
  return (
    <div className="space-y-1.5">
      <p id={id} className={`etiqueta ${ROTULO}`}>
        {rotulo}
        {opcional && <Opcional />}
      </p>
      <div role="group" aria-labelledby={id} className={`grid ${colunas} gap-2`}>
        {opcoes.map(({ valor, rotulo: texto, detalhe }) => (
          <button
            key={valor}
            type="button"
            aria-pressed={escolhida === valor}
            // Na pergunta opcional, tocar de novo desfaz a escolha.
            onClick={() => aoEscolher(opcional && escolhida === valor ? null : valor)}
            className={opcao(escolhida === valor)}
          >
            {texto}
            {detalhe && <span className="block text-sm font-normal normal-case text-slate-500">{detalhe}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

function CampoDeTexto({
  id,
  rotulo,
  valor,
  aoMudar,
  limite,
  placeholder,
}: {
  id: string;
  rotulo: string;
  valor: string;
  aoMudar: (v: string) => void;
  limite: number;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className={ROTULO}>
        {rotulo}
        <Opcional />
      </label>
      <input
        id={id}
        className={CAMPO}
        value={valor}
        maxLength={limite}
        placeholder={placeholder}
        autoComplete="off"
        onChange={(e) => aoMudar(e.target.value)}
      />
    </div>
  );
}

function Progresso({ passo }: { passo: number }) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm text-slate-500">
        Passo {passo} de {TOTAL_DE_PASSOS}
      </p>
      <div
        role="progressbar"
        aria-label="Progresso do relato"
        aria-valuemin={1}
        aria-valuemax={TOTAL_DE_PASSOS}
        aria-valuenow={passo}
        className="h-1.5 w-full rounded-full bg-slate-200 overflow-hidden"
      >
        <div className="h-full bg-primary transition-all" style={{ width: `${(passo / TOTAL_DE_PASSOS) * 100}%` }} />
      </div>
    </div>
  );
}

function Copiar({ rotulo, valor }: { rotulo: string; valor: string }) {
  const [copiado, setCopiado] = useState(false);
  async function copiar() {
    try {
      await navigator.clipboard.writeText(valor);
      setCopiado(true);
    } catch {
      setCopiado(false);
    }
  }
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-slate-50 px-4 py-3">
      <div className="min-w-0">
        <p className="text-sm text-slate-500">{rotulo}</p>
        <p className="text-xl font-bold tracking-wider text-slate-900 font-mono break-all">{valor}</p>
      </div>
      <button
        type="button"
        onClick={copiar}
        aria-label={`Copiar ${rotulo.toLowerCase()}`}
        className="flex shrink-0 min-h-[44px] items-center gap-1.5 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-600"
      >
        {copiado ? <Check className="w-4 h-4" aria-hidden /> : <Copy className="w-4 h-4" aria-hidden />}
        {copiado ? "Copiado" : "Copiar"}
      </button>
    </div>
  );
}

function Entrada({ aoComecar }: { aoComecar: () => void }) {
  return (
    <div className="space-y-6 text-center">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-slate-900">Canal de Conduta</h1>
        <p className="text-base text-slate-700">AGIR CERTO é um dos nossos propósitos. Este canal existe para isso.</p>
        <p className="text-base font-semibold text-slate-900">Você pode relatar sem dizer quem é.</p>
      </div>
      <ul aria-label="O que o canal garante" className="flex flex-wrap justify-center gap-2">
        {["Sem login", "Sem registro de IP", "Só o Comitê lê"].map((selo) => (
          <li
            key={selo}
            className="flex items-center gap-1 rounded-full border border-border bg-white px-3 py-1 text-sm text-slate-600"
          >
            <ShieldCheck className="w-4 h-4 text-primary" aria-hidden />
            {selo}
          </li>
        ))}
      </ul>
      <div className="space-y-2">
        <button type="button" onClick={aoComecar} className={BOTAO_PRINCIPAL}>
          Fazer relato
        </button>
        <a href="/conduta/acompanhar" className={BOTAO_SECUNDARIO}>
          Acompanhar relato
        </a>
      </div>
      <p className="text-sm text-slate-600 text-left">
        Este canal trata de conduta grave: assédio, discriminação, violência, fraude e desvio. Não trata de salário,
        escala, benefícios nem de atendimento a pacientes.
      </p>
      <section aria-labelledby="e-aqui" className="text-left space-y-2">
        <h2 id="e-aqui" className="text-base font-semibold text-slate-900">
          É aqui
        </h2>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-sm text-slate-700">
          {E_AQUI.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <a href="/api/conduta/codigo-de-conduta" rel="noreferrer" className="block text-sm font-semibold text-primary underline">
        Código de Conduta
      </a>
    </div>
  );
}

export function RelatoEmPassos() {
  const [passo, setPasso] = useState(0);
  const [rascunho, setRascunho] = useState<Rascunho>(RASCUNHO_VAZIO);
  const [avisos, setAvisos] = useState<Partial<Record<AvisoDoPasso1, TextoVigente>>>({});
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [protocolo, setProtocolo] = useState<Protocolo | null>(null);
  const [nota, setNota] = useState<number | null>(null);
  const titulo = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let vivo = true;
    lerAvisos().then((lidos) => vivo && setAvisos(lidos));
    return () => {
      vivo = false;
    };
  }, []);

  // A cada passo, o foco vai ao título: o leitor de tela anuncia o passo e o
  // celular volta ao topo sem depender de rolagem.
  useEffect(() => {
    titulo.current?.focus();
  }, [passo]);

  const mudar = <K extends keyof Rascunho>(campo: K, valor: Rascunho[K]) =>
    setRascunho((atual) => ({ ...atual, [campo]: valor }));

  function marcarCiencia(ciente: boolean) {
    // A versão gravada é a do texto que a tela mostrou quando a caixa foi marcada.
    const versoes = Object.fromEntries(
      AVISOS_DO_PASSO_1.map((chave) => [chave, avisos[chave]?.versao ?? null])
    ) as Rascunho["versoes"];
    setRascunho((atual) => ({ ...atual, ciente, versoes }));
  }

  async function enviar() {
    setEnviando(true);
    setErro(null);
    try {
      const recebido = await enviarRelato(rascunho);
      setRascunho(RASCUNHO_VAZIO);
      setProtocolo(recebido);
      setPasso(6);
    } catch (falha) {
      setErro(falha instanceof FalhaDoEnvio ? falha.message : "Não deu para registrar o relato agora. Tente de novo.");
    } finally {
      setEnviando(false);
    }
  }

  async function responderConfianca(valor: number) {
    if (!protocolo || nota !== null) return;
    setNota(valor);
    await enviarConfianca(protocolo, valor);
  }

  const podeSeguir: Record<number, { ok: boolean; falta: string }> = {
    1: { ok: rascunho.ciente, falta: "Marque a caixa acima para continuar." },
    2: {
      ok:
        rascunho.identificacao === "anonimo" ||
        (rascunho.identificacao === "identificado" && rascunho.nome.trim() !== ""),
      falta:
        rascunho.identificacao === "identificado"
          ? "Escreva o seu nome para continuar."
          : "Escolha como você quer relatar para continuar.",
    },
    3: { ok: rascunho.direcao !== null, falta: "Responda se o relato envolve a Direção para continuar." },
    4: { ok: rascunho.relato.trim() !== "", falta: "Conte o que aconteceu para continuar." },
  };

  const cabecalho = (
    <div className="flex items-center justify-center">
      <Logo variant="default" size="sm" />
    </div>
  );

  if (passo === 0) {
    return (
      <main className="min-h-screen bg-bg">
        <div className="max-w-lg mx-auto px-4 py-8 space-y-6">
          {cabecalho}
          <Entrada aoComecar={() => setPasso(1)} />
        </div>
      </main>
    );
  }

  const seguir = podeSeguir[passo];

  return (
    <main className="min-h-screen bg-bg">
      <div className="max-w-lg mx-auto px-4 py-6 space-y-5">
        {cabecalho}
        <Progresso passo={passo} />
        <div className={CARTAO}>
          {passo === 1 && (
            <>
              <h1 ref={titulo} tabIndex={-1} className="text-xl font-bold text-slate-900 outline-none">
                Antes de começar
              </h1>
              <ol aria-label="Avisos" className="space-y-3">
                {AVISOS_DO_PASSO_1.map((chave) => (
                  <li key={chave} className="rounded-xl bg-slate-50 px-4 py-3 text-base text-slate-800">
                    {avisos[chave]?.texto ?? AVISOS_PADRAO[chave]}
                  </li>
                ))}
              </ol>
              <p className="text-sm text-slate-600">{LINHA_DA_IA}</p>
              <label className="flex items-start gap-3 rounded-xl border border-border px-4 py-3 normal-case font-normal">
                <input
                  type="checkbox"
                  className="mt-1 h-5 w-5 shrink-0"
                  checked={rascunho.ciente}
                  onChange={(e) => marcarCiencia(e.target.checked)}
                />
                <span className="text-base text-slate-800">Li as orientações. Relato o que acredito ser verdade.</span>
              </label>
              <details className="text-sm text-slate-600">
                <summary className="cursor-pointer font-semibold text-primary">Ler o aviso de privacidade completo</summary>
                <div className="mt-2 space-y-2">
                  <p>Não guardamos IP, identificação do aparelho nem localização de quem relata ou acompanha.</p>
                  <p>Os dados de origem dos anexos são apagados antes de o arquivo ser guardado.</p>
                  <p>
                    O texto do relato passa por um serviço de inteligência artificial que ajuda a organizá-lo. Esse
                    serviço guarda o texto por até 30 dias e não o usa para treinar a IA. Nenhuma decisão é tomada por
                    IA.
                  </p>
                </div>
              </details>
            </>
          )}

          {passo === 2 && (
            <>
              <h1 ref={titulo} tabIndex={-1} className="text-xl font-bold text-slate-900 outline-none">
                Como você quer relatar?
              </h1>
              <Escolhas
                id="identificacao"
                rotulo="Identificação"
                colunas="grid-cols-1"
                escolhida={rascunho.identificacao}
                aoEscolher={(v) => v && mudar("identificacao", v)}
                opcoes={[
                  {
                    valor: "anonimo",
                    rotulo: "Anônimo",
                    detalhe: "Você acompanha pelo protocolo e pelo código. Ninguém saberá quem relatou.",
                  },
                  {
                    valor: "identificado",
                    rotulo: "Com identificação",
                    detalhe: "O Comitê pode conversar com você pessoalmente. Sua identidade fica restrita ao Comitê.",
                  },
                ]}
              />
              {rascunho.identificacao === "identificado" && (
                <div className="space-y-1.5">
                  <label htmlFor="nome" className={ROTULO}>
                    Seu nome
                  </label>
                  <input
                    id="nome"
                    className={`${CAMPO} normal-case`}
                    value={rascunho.nome}
                    maxLength={200}
                    autoComplete="off"
                    onChange={(e) => mudar("nome", e.target.value)}
                  />
                </div>
              )}
            </>
          )}

          {passo === 3 && (
            <>
              <h1 ref={titulo} tabIndex={-1} className="text-xl font-bold text-slate-900 outline-none">
                Sobre o quê
              </h1>
              <div className="space-y-1.5">
                <Escolhas
                  id="direcao"
                  rotulo="O relato envolve a Direção, a Presidência ou a família proprietária?"
                  escolhida={rascunho.direcao}
                  aoEscolher={(v) => v && mudar("direcao", v)}
                  opcoes={SIM_NAO_NAO_SEI}
                />
                <p className="text-sm text-slate-500">Se sim, seu relato não passa pelo Comitê comum.</p>
              </div>
              <Escolhas
                id="assunto"
                rotulo="Assunto"
                opcional
                colunas="grid-cols-1"
                escolhida={rascunho.assunto}
                aoEscolher={(v) => mudar("assunto", v)}
                opcoes={ASSUNTOS.map((a) => ({ valor: a.codigo, rotulo: a.nome, detalhe: a.exemplos || undefined }))}
              />
              <Escolhas
                id="posicao"
                rotulo="Você"
                opcional
                escolhida={rascunho.posicao}
                aoEscolher={(v) => mudar("posicao", v)}
                opcoes={[
                  { valor: "sofreu", rotulo: "Sofreu" },
                  { valor: "presenciou", rotulo: "Presenciou" },
                  { valor: "ficou_sabendo", rotulo: "Ficou sabendo" },
                ]}
              />
            </>
          )}

          {passo === 4 && (
            <>
              <div className="space-y-1">
                <h1 ref={titulo} tabIndex={-1} className="text-xl font-bold text-slate-900 outline-none">
                  O que aconteceu
                </h1>
                <p className="text-base text-slate-700">Conte com suas palavras. Não precisa ter provas nem certeza.</p>
              </div>
              {rascunho.identificacao === "anonimo" && (
                <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  Evite detalhes que só você saberia.
                </p>
              )}
              <div className="space-y-1.5">
                <label htmlFor="relato" className={ROTULO}>
                  O que aconteceu?
                </label>
                <p id="relato-guia" className="text-sm text-slate-500">
                  O que aconteceu? Quem estava envolvido? Quando e onde? Ainda acontece?
                </p>
                <textarea
                  id="relato"
                  aria-describedby="relato-guia"
                  className={`${CAMPO} min-h-[160px]`}
                  value={rascunho.relato}
                  maxLength={LIMITE_DO_RELATO}
                  onChange={(e) => mudar("relato", e.target.value)}
                />
                <p className="text-sm text-slate-400 text-right">
                  {rascunho.relato.length.toLocaleString("pt-BR")} de {LIMITE_DO_RELATO.toLocaleString("pt-BR")}
                </p>
              </div>
              <CampoDeTexto
                id="quando"
                rotulo="Quando"
                valor={rascunho.quando}
                aoMudar={(v) => mudar("quando", v)}
                limite={200}
                placeholder="Data ou período"
              />
              <label className="flex items-center gap-3 normal-case font-normal text-base text-slate-700">
                <input
                  type="checkbox"
                  className="h-5 w-5"
                  checked={rascunho.ainda_acontece}
                  onChange={(e) => mudar("ainda_acontece", e.target.checked)}
                />
                Ainda está acontecendo
              </label>
              <CampoDeTexto
                id="onde"
                rotulo="Onde"
                valor={rascunho.onde}
                aoMudar={(v) => mudar("onde", v)}
                limite={200}
                placeholder="Setor ou local"
              />
              <CampoDeTexto
                id="quem"
                rotulo="Quem"
                valor={rascunho.quem}
                aoMudar={(v) => mudar("quem", v)}
                limite={500}
                placeholder="Nome ou cargo, se souber"
              />
              <CampoDeTexto
                id="testemunhas"
                rotulo="Testemunhas"
                valor={rascunho.testemunhas}
                aoMudar={(v) => mudar("testemunhas", v)}
                limite={500}
              />
              <Escolhas
                id="lideranca"
                rotulo="Alguma liderança já sabe?"
                opcional
                escolhida={rascunho.lideranca_sabe}
                aoEscolher={(v) => mudar("lideranca_sabe", v)}
                opcoes={SIM_NAO_NAO_SEI}
              />
              {rascunho.lideranca_sabe === "sim" && (
                <CampoDeTexto
                  id="o-que-foi-feito"
                  rotulo="O que foi feito?"
                  valor={rascunho.o_que_foi_feito}
                  aoMudar={(v) => mudar("o_que_foi_feito", v)}
                  limite={1000}
                />
              )}
              <CampoDeTexto
                id="evidencias"
                rotulo="Evidências"
                valor={rascunho.evidencias}
                aoMudar={(v) => mudar("evidencias", v)}
                limite={1000}
                placeholder="Existe algo que comprove? Onde pode ser encontrado?"
              />
            </>
          )}

          {passo === 5 && (
            <>
              <h1 ref={titulo} tabIndex={-1} className="text-xl font-bold text-slate-900 outline-none">
                Revisão
              </h1>
              <Resumo rascunho={rascunho} />
              <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                Seu relato pode iniciar a apuração da conduta de uma pessoa. Confira se descreve o que você viu, viveu ou
                soube.
              </p>
              {erro && (
                <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">
                  {erro}
                </p>
              )}
              <button type="button" onClick={enviar} disabled={enviando} className={BOTAO_PRINCIPAL}>
                {enviando && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
                Enviar
              </button>
              <p className="text-sm text-slate-500 text-center">Seu relato será lido pelo Comitê em até 5 dias úteis.</p>
            </>
          )}

          {passo === 6 && protocolo && (
            <>
              <h1 ref={titulo} tabIndex={-1} className="text-xl font-bold text-slate-900 outline-none">
                Relato registrado
              </h1>
              <p role="alert" className="rounded-xl bg-amber-50 px-4 py-3 text-base font-semibold text-amber-900">
                Anote agora. Não há como recuperar.
              </p>
              <Copiar rotulo="Protocolo" valor={protocolo.protocolo} />
              <Copiar rotulo="Código" valor={protocolo.codigo} />
              <p className="text-base text-slate-700">
                Volte a esta página a partir de {dataLegivel(protocolo.voltar_a_partir_de)}. É por aqui que o Comitê fala
                com você.
              </p>
              <div className="space-y-1.5">
                <p id="confianca" className={`etiqueta ${ROTULO}`}>
                  De 1 a 5, quanto você confia neste canal?
                  <Opcional />
                </p>
                <div role="group" aria-labelledby="confianca" className="grid grid-cols-5 gap-2">
                  {[1, 2, 3, 4, 5].map((valor) => (
                    <button
                      key={valor}
                      type="button"
                      aria-pressed={nota === valor}
                      disabled={nota !== null}
                      onClick={() => responderConfianca(valor)}
                      className={opcao(nota === valor) + " text-center"}
                    >
                      {valor}
                    </button>
                  ))}
                </div>
                {nota !== null && <p className="text-sm text-slate-500">Obrigado pela resposta.</p>}
              </div>
              <a href="/conduta/acompanhar" className={BOTAO_SECUNDARIO}>
                Acompanhar relato
              </a>
            </>
          )}

          {passo >= 1 && passo <= 4 && (
            <div className="space-y-2">
              <button
                type="button"
                disabled={!seguir.ok}
                onClick={() => setPasso(passo + 1)}
                className={BOTAO_PRINCIPAL}
              >
                Continuar
              </button>
              {!seguir.ok && <p className="text-sm text-slate-500 text-center">{seguir.falta}</p>}
            </div>
          )}
        </div>
        {passo >= 1 && passo <= 5 && (
          <button type="button" onClick={() => setPasso(passo - 1)} disabled={enviando} className={BOTAO_SECUNDARIO}>
            Voltar
          </button>
        )}
      </div>
    </main>
  );
}

const NOMES: Record<string, string> = { anonimo: "Anônimo", identificado: "Com identificação" };
const POSICOES: Record<string, string> = { sofreu: "Sofreu", presenciou: "Presenciou", ficou_sabendo: "Ficou sabendo" };
const RESPOSTAS: Record<string, string> = { sim: "Sim", nao: "Não", nao_sei: "Não sei" };

function Resumo({ rascunho: r }: { rascunho: Rascunho }) {
  const linhas: [string, string][] = [
    ["Como relata", r.identificacao === "identificado" ? `${NOMES.identificado}: ${r.nome.trim()}` : NOMES.anonimo],
    ["Envolve a Direção", r.direcao ? RESPOSTAS[r.direcao] : ""],
    ["Assunto", ASSUNTOS.find((a) => a.codigo === r.assunto)?.nome ?? ""],
    ["Você", r.posicao ? POSICOES[r.posicao] : ""],
    ["O que aconteceu", r.relato.trim()],
    ["Quando", [r.quando.trim(), r.ainda_acontece ? "Ainda está acontecendo" : ""].filter(Boolean).join(". ")],
    ["Onde", r.onde.trim()],
    ["Quem", r.quem.trim()],
    ["Testemunhas", r.testemunhas.trim()],
    [
      "Alguma liderança já sabe",
      r.lideranca_sabe
        ? [RESPOSTAS[r.lideranca_sabe], r.lideranca_sabe === "sim" ? r.o_que_foi_feito.trim() : ""].filter(Boolean).join(". ")
        : "",
    ],
    ["Evidências", r.evidencias.trim()],
  ];
  return (
    <dl aria-label="Resumo do relato" className="space-y-3">
      {linhas
        .filter(([, valor]) => valor)
        .map(([rotulo, valor]) => (
          <div key={rotulo} className="space-y-0.5">
            <dt className="text-sm font-semibold text-slate-500">{rotulo}</dt>
            <dd className="text-base text-slate-800 whitespace-pre-line break-words">{valor}</dd>
          </div>
        ))}
    </dl>
  );
}
