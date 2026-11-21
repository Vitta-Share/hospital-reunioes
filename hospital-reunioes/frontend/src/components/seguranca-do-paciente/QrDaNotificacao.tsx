"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Download } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const ROTA_DO_QR = "/api/nsp/configuracao/qr-da-notificacao.png";

/**
 * A imagem do QR, pedida com o token: um `<img src>` direto iria sem ele.
 * `falhou` liga quando a rota recusa (sessão vencida, 403, 500) ou a rede cai.
 */
function useImagemDoQr(): { url: string | null; falhou: boolean } {
  const [url, setUrl] = useState<string | null>(null);
  const [falhou, setFalhou] = useState(false);
  useEffect(() => {
    let vivo = true;
    let criada: string | null = null;
    (async () => {
      const {
        data: { session },
      } = await createClient().auth.getSession();
      const res = await fetch(ROTA_DO_QR, { headers: { Authorization: `Bearer ${session?.access_token ?? ""}` } });
      if (!res.ok) throw new Error(`QR ${res.status}`);
      const blob = await res.blob();
      if (!vivo) return;
      criada = URL.createObjectURL(blob);
      setUrl(criada);
    })().catch(() => vivo && setFalhou(true));
    return () => {
      vivo = false;
      if (criada) URL.revokeObjectURL(criada);
    };
  }, []);
  return { url, falhou };
}

/**
 * A seção "QR e endereço da notificação" da Configuração (issue #2046): o QR
 * único, que abre `/notificar/qr`, para o cartaz e o papel de parede, e o
 * endereço de `/notificar` para a TI criar o ícone nos computadores. Só
 * leitura: não há nada para editar.
 */
export function QrDaNotificacao() {
  const { url: imagem, falhou: qrFalhou } = useImagemDoQr();
  const [endereco, setEndereco] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    chamarNsp<{ endereco_da_notificacao: string }>("/api/nsp/configuracao")
      .then((corpo) => vivo && setEndereco(corpo.endereco_da_notificacao))
      .catch(() => vivo && setErro("Não foi possível carregar o endereço. Recarregue a página."));
    return () => {
      vivo = false;
    };
  }, []);

  async function copiar() {
    if (!endereco) return;
    try {
      await navigator.clipboard.writeText(endereco);
      setCopiado(true);
    } catch {
      setErro("Não foi possível copiar. Selecione o endereço e copie à mão.");
    }
  }

  return (
    <section className={`${CARTAO} px-4 py-4 space-y-4`}>
      <div>
        <h2 className="text-base font-semibold text-slate-900">QR e endereço da notificação</h2>
        <p className="text-sm text-slate-600 mt-0.5">
          Imprima o QR no cartaz ou use como papel de parede. Com o endereço, a TI cria o ícone nos computadores.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 sm:items-center">
        {imagem ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imagem}
            alt="QR da notificação de incidente"
            className="w-40 h-40 shrink-0 rounded-xl border border-border"
          />
        ) : (
          <div aria-hidden className="w-40 h-40 shrink-0 rounded-xl border border-border bg-slate-50" />
        )}
        {imagem && (
          <a
            href={imagem}
            download="qr-notificacao-nsp.png"
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90"
          >
            <Download className="w-4 h-4" aria-hidden />
            Baixar o QR
          </a>
        )}
      </div>

      <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
        <code className="min-w-0 flex-1 break-all rounded-xl bg-slate-50 border border-border px-3 py-2 text-sm text-slate-800">
          {endereco ?? "Carregando o endereço..."}
        </code>
        <button
          type="button"
          onClick={copiar}
          disabled={!endereco}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-border px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50"
        >
          {copiado ? <Check className="w-4 h-4" aria-hidden /> : <Copy className="w-4 h-4" aria-hidden />}
          {copiado ? "Copiado" : "Copiar"}
        </button>
      </div>

      {qrFalhou && <p className="text-sm text-red-700">Não foi possível carregar o QR. Recarregue a página.</p>}
      {erro && <p className="text-sm text-red-700">{erro}</p>}
    </section>
  );
}
