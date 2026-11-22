"use client";

import { useCallback, useEffect, useState } from "react";

import { chamarComite, type Convidado } from "@/lib/conduta/comite";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";

const PAPEIS: { valor: Convidado["motivo"]; rotulo: string }[] = [
  { valor: "apurador", rotulo: "Apurador designado" },
  { valor: "cipa", rotulo: "Membro da CIPA" },
];

const TERMO: Record<Convidado["termo"], string> = {
  assinado: "Termo assinado",
  aguardando_assinatura: "Esperando a assinatura do termo",
  nao_enviado: "Termo não enviado. Convide de novo para reenviar.",
};

interface Resposta {
  pode_convidar?: boolean;
  convites?: Convidado[];
  aviso_termo?: string | null;
}

/**
 * O convite do apurador designado e do membro da CIPA, dentro do caso (issue
 * #1825; especificação, seções 3.2, 6.4 e 10). Aparece só para quem o servidor
 * diz que convida: a coordenação, nos casos da fila comum, e o Grupo Especial,
 * no caso dele.
 */
export function ConvidarAoCaso({ casoId }: { casoId: string }) {
  const [podeConvidar, setPodeConvidar] = useState(false);
  const [convidados, setConvidados] = useState<Convidado[]>([]);
  const [motivo, setMotivo] = useState<Convidado["motivo"] | "">("");
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  const carregar = useCallback(() => {
    chamarComite<Resposta>(`/casos/${casoId}/convites`)
      .then((corpo) => {
        setPodeConvidar(Boolean(corpo.pode_convidar));
        setConvidados(corpo.convites ?? []);
      })
      .catch(() => setPodeConvidar(false));
  }, [casoId]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const convidar = async () => {
    setOcupado(true);
    setAviso(null);
    try {
      const corpo = await chamarComite<Resposta>(`/casos/${casoId}/convites`, {
        method: "POST",
        body: { email: email.trim(), nome: nome.trim(), motivo },
      });
      setConvidados(corpo.convites ?? []);
      setAviso(corpo.aviso_termo ?? "Convite enviado.");
      setEmail("");
      setNome("");
      setMotivo("");
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  if (!podeConvidar) return null;

  return (
    <section aria-label="Convidar para o caso" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 className="text-base font-semibold text-slate-900">Convidar para o caso</h2>
      <p className="text-sm text-slate-700">
        Convide o apurador designado ou o membro da CIPA pelo e-mail. A pessoa recebe o termo de confidencialidade pela
        ClickSign e, depois de assinar, abre só este caso. O e-mail do convite não traz o protocolo nem nada do caso.
      </p>

      {convidados.length > 0 && (
        <ul aria-label="Convidados" className="space-y-2">
          {convidados.map((c) => (
            <li key={c.participante_id} className="rounded-xl bg-slate-50 px-3 py-2 space-y-1">
              <p className="text-sm text-slate-800">{`${c.nome ?? "Sem nome"}, ${c.papel}`}</p>
              <p className="text-xs text-slate-500">{TERMO[c.termo]}</p>
            </li>
          ))}
        </ul>
      )}

      <form
        aria-label="Convidar"
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          void convidar();
        }}
      >
        <fieldset className="space-y-1">
          <legend className="text-sm font-semibold text-slate-700">Papel no caso</legend>
          <div className="flex flex-wrap gap-3">
            {PAPEIS.map((p) => (
              <label key={p.valor} className="flex items-center gap-2 text-sm text-slate-800">
                <input
                  type="radio"
                  name="motivo-do-convite"
                  value={p.valor}
                  checked={motivo === p.valor}
                  onChange={() => setMotivo(p.valor)}
                />
                {p.rotulo}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="text-sm font-semibold text-slate-700 space-y-1 block">
          <span>E-mail</span>
          <input className={CAMPO} type="email" value={email} maxLength={320} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="text-sm font-semibold text-slate-700 space-y-1 block">
          <span>Nome completo, para quem ainda não tem cadastro</span>
          <input className={CAMPO} value={nome} maxLength={200} onChange={(e) => setNome(e.target.value)} />
        </label>
        <button type="submit" className={BOTAO} disabled={!motivo || !email.trim() || ocupado}>
          CONVIDAR
        </button>
      </form>

      {aviso && (
        <p role="status" className="text-sm text-slate-700">
          {aviso}
        </p>
      )}
    </section>
  );
}
