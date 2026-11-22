"use client";

/**
 * O link de uso único do Núcleo ao setor (issue #1996, ADR 0107 decisão 8).
 *
 * O titular da Segurança do Trabalho, da Farmácia ou da Engenharia Clínica
 * chega pelo e-mail do encaminhamento, sem senha, e vê o resumo do caso: o
 * protocolo, onde e quando, e o motivo. O relato e quem notificou não aparecem
 * aqui. Abrir a tela não confirma nada (leitor de e-mail que abre link sozinho
 * gastaria o uso único): é o botão "Recebido" que chama o servidor, e é o
 * servidor que decide o uso único e a validade.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { Logo } from "@/components/ui/Logo";
import { TURNOS } from "@/lib/seguranca-do-paciente/notificacao";

const INSTAVEL = "Não foi possível confirmar agora. Tente novamente.";
const LINK_INVALIDO = "Este link não é válido. Confira se o endereço veio completo no e-mail do Núcleo.";

interface Resumo {
  protocolo: string;
  destino: string;
  setor_que_recebe: string;
  destinatario_nome: string | null;
  setor_do_incidente: string | null;
  data_ocorrencia: string | null;
  turno: string | null;
  motivo: string | null;
}

/** "2026-11-10" em "10/11/2026", sem passar pelo fuso do navegador. */
function dataDoBrasil(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return dia && mes && ano ? `${dia}/${mes}/${ano}` : iso;
}

function mensagem(status: number, detail: string | undefined): string {
  if (status === 404) return LINK_INVALIDO;
  return detail || "Não foi possível abrir este link agora. Tente novamente.";
}

function Bloco({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{titulo}</h2>
      <div className="text-sm text-slate-800 leading-relaxed">{children}</div>
    </section>
  );
}

export default function RecebidoDoSetorPage() {
  const params = useParams();
  const token = params.token as string;

  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [erroDaAbertura, setErroDaAbertura] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [recebido, setRecebido] = useState(false);
  // O 503 e a falha do fetch deixam o botão: o link continua valendo. O 404 e
  // o 410 dizem que não há mais o que confirmar, e o botão some.
  const [erro, setErro] = useState<{ mensagem: string; podeTentarDeNovo: boolean } | null>(null);

  useEffect(() => {
    let cancelado = false;
    fetch(`/api/nsp/recebimento/${encodeURIComponent(token)}`)
      .then(async (res) => {
        const corpo = await res.json().catch(() => ({}));
        if (cancelado) return;
        if (!res.ok) {
          setErroDaAbertura(mensagem(res.status, corpo.detail));
          return;
        }
        setResumo(corpo as Resumo);
      })
      .catch(() => {
        if (!cancelado) setErroDaAbertura("Não foi possível abrir o caso agora. Tente novamente.");
      });
    return () => {
      cancelado = true;
    };
  }, [token]);

  async function confirmar() {
    setEnviando(true);
    setErro(null);
    try {
      const res = await fetch(`/api/nsp/recebimento/${encodeURIComponent(token)}/recebido`, { method: "POST" });
      const corpo = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErro({
          mensagem: res.status >= 500 ? corpo.detail || INSTAVEL : mensagem(res.status, corpo.detail),
          podeTentarDeNovo: res.status >= 500,
        });
        return;
      }
      setRecebido(true);
    } catch {
      setErro({ mensagem: INSTAVEL, podeTentarDeNovo: true });
    } finally {
      setEnviando(false);
    }
  }

  if (erroDaAbertura) {
    return (
      <main className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="w-full max-w-lg bg-white rounded-2xl border border-slate-200 shadow-premium p-8 text-center space-y-4">
          <div className="flex justify-center">
            <Logo />
          </div>
          <p role="alert" className="text-sm text-amber-700">
            {erroDaAbertura}
          </p>
        </div>
      </main>
    );
  }

  if (!resumo) {
    return (
      <main className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <Loader2 className="w-6 h-6 animate-spin text-primary/40" aria-label="Abrindo o caso" />
      </main>
    );
  }

  const turno = TURNOS.find((t) => t.valor === resumo.turno)?.rotulo;
  const quando = [resumo.data_ocorrencia ? dataDoBrasil(resumo.data_ocorrencia) : null, turno?.toLowerCase()]
    .filter(Boolean)
    .join(", ");
  const linkAcabou = erro !== null && !erro.podeTentarDeNovo;

  return (
    <main className="min-h-screen bg-slate-50 p-4 flex justify-center">
      <div className="w-full max-w-2xl bg-white rounded-2xl border border-slate-200 shadow-premium p-6 md:p-8 space-y-5">
        <div className="flex justify-center">
          <Logo />
        </div>
        <header className="space-y-1">
          <p className="text-sm font-semibold text-rose-700">Núcleo de Segurança do Paciente</p>
          <h1 className="text-xl font-bold text-slate-900">Notificação {resumo.protocolo}</h1>
          <p className="text-sm text-slate-500">
            {`Encaminhada a ${resumo.setor_que_recebe} (${resumo.destino})`}
          </p>
        </header>

        <p className="text-sm text-slate-600">
          O relato e quem notificou não aparecem neste link, que abre sem senha. Para saber mais, fale com o
          Núcleo de Segurança do Paciente.
        </p>

        <Bloco titulo="Motivo do encaminhamento">
          <p>{resumo.motivo || "Não informado."}</p>
        </Bloco>

        <Bloco titulo="Onde aconteceu">
          <p>{resumo.setor_do_incidente || "Setor não informado."}</p>
        </Bloco>

        {quando && (
          <Bloco titulo="Quando">
            <p>{quando}</p>
          </Bloco>
        )}

        <div className="border-t border-slate-100 pt-5 space-y-3">
          {recebido ? (
            <p
              data-testid="setor-recebido"
              className="flex items-start gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2.5"
            >
              <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
              <span>Recebimento confirmado. O Núcleo já sabe que o setor recebeu o caso.</span>
            </p>
          ) : (
            <>
              {erro && (
                <p
                  role="alert"
                  className="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5"
                >
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>{erro.mensagem}</span>
                </p>
              )}
              {!linkAcabou && (
                <button
                  type="button"
                  onClick={() => void confirmar()}
                  disabled={enviando}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-60"
                >
                  {enviando && <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />}
                  Recebido
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
