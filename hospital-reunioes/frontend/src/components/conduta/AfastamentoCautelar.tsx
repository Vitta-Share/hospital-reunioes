"use client";

import { useEffect, useState } from "react";

import {
  DESTINOS_DO_PEDIDO,
  RESULTADOS,
  abrirParecer,
  anexarParecer,
  caminhoDoAfastamento,
  doPedido,
  type Afastamento,
  type ItemDosPedidos,
  type PedidoDeAfastamento,
  type ResultadoDoAfastamento,
} from "@/lib/conduta/afastamento";
import { chamarComite, type Citado } from "@/lib/conduta/comite";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

export const AVISO_DO_AFASTAMENTO = "O afastamento cautelar é remunerado e não é punição.";

/** "2026-11-20" vira "20/11/2026", sem passar por fuso. */
function dataDoDia(dia: string): string {
  const [ano, mes, d] = dia.slice(0, 10).split("-");
  return `${d}/${mes}/${ano}`;
}

/** O dia, no fuso do hospital. */
function diaEmSaoPaulo(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short" }).format(new Date(iso));
}

function hojeEmSaoPaulo(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
}

function textoDoResultado(afastamento: Afastamento): string {
  if (afastamento.rota === "comum") return "Decisão do coordenador: afastar.";
  if (afastamento.resultado === null) return "Aguardando o parecer do Jurídico, que define o afastamento.";
  return `O parecer do Jurídico definiu: ${afastamento.resultado === "afastar" ? "afastar" : "não afastar"}.`;
}

interface CartaoProps {
  casoId: string;
  afastamento: Afastamento;
  /** O texto do pedido, quando já foi aberto (a lista da coordenação abre direto). */
  textoDoPedido?: string | null;
  aoMudar: () => void;
}

/**
 * Um afastamento: quem, o motivo, o resultado, a entrega do pedido ao DP e ao
 * Jurídico e o parecer do Jurídico. O servidor diz quem registra a entrega e
 * quem anexa o parecer.
 */
export function CartaoDoAfastamento({ casoId, afastamento, textoDoPedido = null, aoMudar }: CartaoProps) {
  const caminho = caminhoDoAfastamento(casoId, afastamento.id);
  const [texto, setTexto] = useState<string | null>(textoDoPedido);
  const [datas, setDatas] = useState<Record<string, string>>({});
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [resultado, setResultado] = useState<ResultadoDoAfastamento | "">("");
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const especial = afastamento.rota === "especial";

  const agir = async (acao: () => Promise<unknown>) => {
    setOcupado(true);
    setAviso(null);
    try {
      await acao();
      aoMudar();
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  const verPedido = () =>
    void chamarComite<PedidoDeAfastamento>(caminho)
      .then((corpo) => setTexto(corpo.pedido.texto))
      .catch((e: Error) => setAviso(e.message));

  const verParecer = () =>
    void abrirParecer(casoId, afastamento.id)
      .then((endereco) => window.open(endereco, "_blank", "noopener"))
      .catch((e: Error) => setAviso(e.message));

  return (
    <li aria-label={`Afastamento de ${afastamento.quem}`} className="rounded-xl border border-border px-3 py-3 space-y-2">
      <p className="text-sm font-semibold text-slate-900">{afastamento.quem}</p>
      <p className="text-sm text-slate-700">{`Motivo: ${afastamento.motivo}`}</p>
      <p className="text-sm text-slate-800">{textoDoResultado(afastamento)}</p>

      {texto ? (
        <pre aria-label="Pedido de afastamento" className="whitespace-pre-wrap rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-800">
          {texto}
        </pre>
      ) : (
        <button type="button" className={BOTAO_CLARO} onClick={verPedido}>
          VER PEDIDO AO DP E AO JURÍDICO
        </button>
      )}

      {DESTINOS_DO_PEDIDO.map(({ valor, rotulo }) => {
        const entregue = afastamento.entregas[valor];
        if (entregue) return <p key={valor} className="text-sm text-slate-700">{`Entregue ao ${rotulo} em ${dataDoDia(entregue)}.`}</p>;
        if (!afastamento.pode_registrar_entrega) {
          return <p key={valor} className="text-sm text-slate-500">{`Entrega ao ${rotulo} ainda não registrada.`}</p>;
        }
        return (
          <div key={valor} className="flex flex-col sm:flex-row gap-2 sm:items-end">
            <label className="text-sm font-semibold text-slate-700 space-y-1 block">
              <span>{`Data da entrega ao ${rotulo}`}</span>
              <input
                type="date"
                className={CAMPO}
                value={datas[valor] ?? ""}
                max={hojeEmSaoPaulo()}
                onChange={(e) => setDatas({ ...datas, [valor]: e.target.value })}
              />
            </label>
            <button
              type="button"
              className={BOTAO}
              disabled={!datas[valor] || ocupado}
              onClick={() =>
                void agir(() =>
                  chamarComite(`${caminho}/entrega`, { method: "POST", body: { destino: valor, entregue_em: datas[valor] } }),
                )
              }
            >
              {`REGISTRAR ENTREGA AO ${rotulo.toUpperCase()}`}
            </button>
          </div>
        );
      })}

      {afastamento.parecer ? (
        <div className="space-y-1">
          <p className="text-sm text-slate-700">{`Parecer do Jurídico anexado em ${diaEmSaoPaulo(afastamento.parecer.anexado_em)}.`}</p>
          {afastamento.parecer.ciencia_de && (
            <p className="text-sm text-slate-700">{`Com ciência de: ${afastamento.parecer.ciencia_de.join(", ")}.`}</p>
          )}
          <button type="button" className={BOTAO_CLARO} onClick={verParecer}>
            ABRIR PARECER DO JURÍDICO
          </button>
        </div>
      ) : afastamento.pode_anexar_parecer ? (
        <form
          aria-label="Anexar o parecer do Jurídico"
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (arquivo) void agir(() => anexarParecer(casoId, afastamento.id, arquivo, especial ? resultado || null : null));
          }}
        >
          <label className="text-sm font-semibold text-slate-700 space-y-1 block">
            <span>Parecer do Jurídico (PDF)</span>
            <input type="file" accept="application/pdf" className={CAMPO} onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
          </label>
          {especial && (
            <fieldset className="space-y-1">
              <legend className="text-sm font-semibold text-slate-700">O que o parecer definiu</legend>
              <div className="flex flex-wrap gap-3">
                {RESULTADOS.map((r) => (
                  <label key={r.valor} className="flex items-center gap-2 text-sm text-slate-800">
                    <input type="radio" name={`resultado-${afastamento.id}`} checked={resultado === r.valor} onChange={() => setResultado(r.valor)} />
                    {r.rotulo}
                  </label>
                ))}
              </div>
              <p className="text-xs text-slate-500">Os membros do grupo têm ciência do parecer anexado.</p>
            </fieldset>
          )}
          <button type="submit" className={BOTAO} disabled={!arquivo || (especial && !resultado) || ocupado}>
            ANEXAR PARECER DO JURÍDICO
          </button>
        </form>
      ) : null}

      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </li>
  );
}

interface Props {
  casoId: string;
  rota: string | null;
  citados: Citado[];
  afastamentos: Afastamento[];
  podeRegistrar: boolean;
  aoMudar: () => void;
}

/**
 * O afastamento cautelar na tela do caso (issue #1836; especificação, 6.5).
 * No caso comum, o coordenador registra a decisão; na Rota Especial, o grupo
 * pede à coordenação. Só se afasta um Citado, e nunca quem relatou.
 */
export function AfastamentoCautelar({ casoId, rota, citados, afastamentos, podeRegistrar, aoMudar }: Props) {
  const [citadoId, setCitadoId] = useState("");
  const [motivo, setMotivo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const especial = rota === "especial";
  const livres = citados.filter((c) => c.nome && !afastamentos.some((a) => a.quem === c.nome));

  if (!podeRegistrar && afastamentos.length === 0) return null;

  const registrar = async () => {
    setOcupado(true);
    setAviso(null);
    try {
      await chamarComite(`/casos/${casoId}/afastamentos`, { method: "POST", body: { citado_id: citadoId, motivo: motivo.trim() } });
      setCitadoId("");
      setMotivo("");
      aoMudar();
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section aria-label="Afastamento cautelar" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 className="text-base font-semibold text-slate-900">Afastamento cautelar</h2>
      <p className="text-sm font-semibold text-slate-800">{AVISO_DO_AFASTAMENTO}</p>
      {afastamentos.length > 0 && (
        <ul className="space-y-2">
          {afastamentos.map((a) => (
            <CartaoDoAfastamento key={a.id} casoId={casoId} afastamento={a} aoMudar={aoMudar} />
          ))}
        </ul>
      )}
      {podeRegistrar && (
        <form
          aria-label={especial ? "Pedir o afastamento à coordenação" : "Registrar o afastamento"}
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            void registrar();
          }}
        >
          <p className="text-sm text-slate-700">
            {especial
              ? "O pedido vai à coordenação, que vê só quem afastar e o motivo, pede o parecer do Jurídico e o anexa. É o parecer que define."
              : "O pedido ao DP e ao Jurídico leva só quem afastar e o motivo, sem o relato. O parecer do Jurídico é consultivo."}
          </p>
          {livres.length === 0 ? (
            <p className="text-sm text-slate-500">Marque como Citado quem deve ser afastado.</p>
          ) : (
            <>
              <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                <span>Quem afastar</span>
                <select className={CAMPO} value={citadoId} onChange={(e) => setCitadoId(e.target.value)}>
                  <option value="">Escolha um Citado</option>
                  {livres.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                <span>Motivo</span>
                <textarea className={CAMPO} rows={3} maxLength={1000} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
              </label>
              <button type="submit" className={BOTAO} disabled={!citadoId || !motivo.trim() || ocupado}>
                {especial ? "PEDIR AFASTAMENTO À COORDENAÇÃO" : "REGISTRAR AFASTAMENTO"}
              </button>
            </>
          )}
        </form>
      )}
      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </section>
  );
}

/** Um pedido da Rota Especial aberto pela coordenação: só o pedido. */
function PedidoDaRotaEspecial({ item }: { item: ItemDosPedidos }) {
  const [pedido, setPedido] = useState<PedidoDeAfastamento | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const abrir = () =>
    void chamarComite<PedidoDeAfastamento>(caminhoDoAfastamento(item.caso_id, item.id))
      .then((corpo) => {
        setPedido(corpo);
        setErro(null);
      })
      .catch((e: Error) => setErro(e.message));

  if (pedido) {
    return (
      <CartaoDoAfastamento casoId={item.caso_id} afastamento={doPedido(pedido)} textoDoPedido={pedido.pedido.texto} aoMudar={abrir} />
    );
  }
  return (
    <li className="rounded-xl border border-border px-3 py-3 space-y-2">
      <p className="text-sm text-slate-800">
        {`Pedido do Grupo Especial de ${diaEmSaoPaulo(item.registrado_em)}${item.parecer_anexado ? ", com o parecer anexado" : ", aguardando o parecer do Jurídico"}.`}
      </p>
      <button type="button" className={BOTAO_CLARO} onClick={abrir}>
        ABRIR PEDIDO
      </button>
      {erro && (
        <p role="alert" className="text-sm text-red-700">
          {erro}
        </p>
      )}
    </li>
  );
}

/**
 * Os pedidos de afastamento da Rota Especial, para a coordenação (issue
 * #1836; decisões 35 e 36 do diretor). Ela vê só o pedido, nada do caso, e
 * anexa o parecer do Jurídico. Quem não é da coordenação não vê nada aqui.
 */
export function PedidosDeAfastamento() {
  const [pedidos, setPedidos] = useState<ItemDosPedidos[] | null>(null);

  useEffect(() => {
    let vivo = true;
    chamarComite<{ pedidos: ItemDosPedidos[] }>("/afastamentos/pedidos")
      .then((corpo) => vivo && setPedidos(corpo.pedidos))
      .catch(() => vivo && setPedidos(null));
    return () => {
      vivo = false;
    };
  }, []);

  if (!pedidos || pedidos.length === 0) return null;
  return (
    <section aria-label="Pedidos de afastamento da Rota Especial" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 className="text-base font-semibold text-slate-900">Pedidos de afastamento da Rota Especial</h2>
      <p className="text-sm text-slate-700">
        {`Você vê só o pedido, sem nada do caso. Peça o parecer ao Jurídico com urgência e anexe aqui: é o parecer que define. ${AVISO_DO_AFASTAMENTO}`}
      </p>
      <ul className="space-y-2">
        {pedidos.map((item) => (
          <PedidoDaRotaEspecial key={item.id} item={item} />
        ))}
      </ul>
    </section>
  );
}
