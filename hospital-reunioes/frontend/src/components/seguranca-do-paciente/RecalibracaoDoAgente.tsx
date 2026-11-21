"use client";

import { useEffect, useState } from "react";
import { AlertCircle, AlertTriangle, Loader2 } from "lucide-react";

import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";
import {
  SEM_DADOS_NESTA_FASE,
  type ItemDoAnexoF,
  type Recalibracao,
  type TelaDaRecalibracao,
} from "@/lib/seguranca-do-paciente/recalibracao";
import { formatarData } from "./NotificacoesDoNucleo";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const ROTA = "/api/nsp/recalibracao";

function Item({ item }: { item: ItemDoAnexoF }) {
  return (
    <li className="border-t border-border py-3 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-slate-900">
          {item.numero}. {item.titulo}
        </h3>
        {item.alerta && (
          <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">
            <AlertTriangle className="w-3 h-3" aria-hidden />
            Sinal de alerta aceso
          </span>
        )}
      </div>
      {item.com_dados ? (
        <ul className="space-y-0.5">
          {item.linhas.map((linha) => (
            <li key={linha} className="text-sm text-slate-700">
              {linha}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">{SEM_DADOS_NESTA_FASE}</p>
      )}
      <p className="text-xs text-slate-500">Sinal de alerta: {item.sinal}</p>
    </li>
  );
}

function Secao({ titulo, itens }: { titulo: string; itens: ItemDoAnexoF[] }) {
  return (
    <section className={`${CARTAO} px-4 py-4`}>
      <h2 className="text-base font-semibold text-slate-900 pb-1">{titulo}</h2>
      <ul>
        {itens.map((item) => (
          <Item key={item.numero} item={item} />
        ))}
      </ul>
    </section>
  );
}

function Decisao({
  marco,
  tela,
  aoDecidir,
}: {
  marco: Recalibracao;
  tela: TelaDaRecalibracao;
  aoDecidir: (recalibracoes: Recalibracao[]) => void;
}) {
  const [escolha, setEscolha] = useState<string | null>(null);
  const [gravando, setGravando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const rotulo = (valor: string) => tela.decisoes.find((d) => d.valor === valor)?.rotulo ?? valor;

  if (marco.decisao) {
    return (
      <p className="text-sm text-slate-700">
        Decisão: {rotulo(marco.decisao)}. Registrada por {marco.decidido_por ?? "quem tem Acesso pleno"}
        {marco.decidido_em ? ` em ${formatarData(marco.decidido_em)}` : ""}.
      </p>
    );
  }
  if (!tela.pode_decidir) {
    return <p className="text-sm text-slate-600">Aguardando a decisão de quem tem Acesso pleno.</p>;
  }

  async function registrar() {
    if (!escolha) return;
    setGravando(true);
    setErro(null);
    try {
      const corpo = await chamarNsp<{ recalibracoes: Recalibracao[] }>(`${ROTA}/${marco.marco}`, {
        method: "POST",
        body: { decisao: escolha },
      });
      aoDecidir(corpo.recalibracoes);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setGravando(false);
    }
  }

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-semibold text-slate-900">Qual é a decisão?</legend>
      {tela.decisoes.map((d) => (
        <label key={d.valor} className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="radio"
            name={`decisao-${marco.marco}`}
            value={d.valor}
            checked={escolha === d.valor}
            onChange={() => setEscolha(d.valor)}
          />
          {d.rotulo}
        </label>
      ))}
      {erro && (
        <p role="alert" className="text-sm text-red-700">
          {erro}
        </p>
      )}
      <button
        type="button"
        onClick={registrar}
        disabled={!escolha || gravando}
        className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-50"
      >
        {gravando && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
        Registrar a decisão
      </button>
    </fieldset>
  );
}

/**
 * A tela da pendência "Recalibrar o agente do NSP" (issue #2001): os marcos
 * de 30 e 60 dias com a decisão, e os itens das seções 4 e 5 do Anexo F. O que
 * ainda não tem dado nesta fase aparece como "sem dados nesta fase".
 */
export function RecalibracaoDoAgente() {
  const [tela, setTela] = useState<TelaDaRecalibracao | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    chamarNsp<TelaDaRecalibracao>(ROTA)
      .then((corpo) => vivo && setTela(corpo))
      .catch((e: Error) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, []);

  if (tela === null) {
    return erro ? (
      <div role="alert" className={`${CARTAO} flex gap-2 items-start px-4 py-4`}>
        <AlertCircle className="w-5 h-5 shrink-0 text-red-500" aria-hidden />
        <p className="text-sm text-red-700">{erro}</p>
      </div>
    ) : (
      <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />
    );
  }

  return (
    <div className="space-y-4">
      <section className={`${CARTAO} px-4 py-4 space-y-3`}>
        <h2 className="text-base font-semibold text-slate-900">Recalibrações</h2>
        {tela.recalibracoes.length === 0 ? (
          <p className="text-sm text-slate-600">
            A primeira recalibração chega 30 dias depois da primeira notificação registrada.
          </p>
        ) : (
          tela.recalibracoes.map((marco) => (
            <div key={marco.marco} className="space-y-2 border-t border-border pt-3 first:border-t-0 first:pt-0">
              <p className="text-sm font-semibold text-slate-900">
                Recalibração de {marco.marco} dias, desde {formatarData(marco.devida_em)}
              </p>
              <Decisao marco={marco} tela={tela} aoDecidir={(recalibracoes) => setTela({ ...tela, recalibracoes })} />
            </div>
          ))
        )}
      </section>
      <Secao titulo="Auditoria de 30 dias" itens={tela.itens.filter((i) => i.secao === 4)} />
      <Secao titulo="Auditoria de 60 dias" itens={tela.itens.filter((i) => i.secao === 5)} />
    </div>
  );
}
