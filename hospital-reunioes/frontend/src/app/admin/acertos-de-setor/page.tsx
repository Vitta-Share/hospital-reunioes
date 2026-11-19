"use client";

// Acertos de setor (issue #1861): as Reuniões antigas e os responsáveis que
// ficaram sem setor, para o Super admin preencher. Preenchido, sai da lista.
// Cada grupo é uma seção própria; a próxima lista (as Pendências de fluxo
// contínuo que não casam com o quadro da Ata) entra como mais uma seção.

import { useCallback, useEffect, useState } from "react";
import { Loader2, MapPinned } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/ui/Toast";
import { Select } from "@/components/ui/Select";

interface ReuniaoSemSetor {
  id_reuniao: string;
  titulo: string | null;
  data: string;
  tipo: string | null;
}

interface ResponsavelSemSetor {
  id: string;
  nome_completo: string;
  cargo: string | null;
  email: string | null;
}

interface Acertos {
  reunioes: ReuniaoSemSetor[];
  responsaveis: ResponsavelSemSetor[];
}

function dataCurta(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : iso;
}

function LinhaDeAcerto({
  titulo,
  detalhe,
  setores,
  onSalvar,
}: {
  titulo: string;
  detalhe: string | null;
  setores: string[];
  onSalvar: (setor: string) => Promise<void>;
}) {
  const [setor, setSetor] = useState("");
  const [salvando, setSalvando] = useState(false);

  async function salvar() {
    if (!setor) return;
    setSalvando(true);
    try {
      await onSalvar(setor);
    } finally {
      setSalvando(false);
    }
  }

  return (
    <li className="flex flex-col md:flex-row md:items-center gap-3 px-4 py-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text truncate normal-case">{titulo}</p>
        {detalhe && <p className="text-xs text-text-secondary truncate">{detalhe}</p>}
      </div>
      <div className="flex items-center gap-2 md:w-96">
        <Select
          value={setor}
          onChange={setSetor}
          placeholder="Escolha o setor"
          options={setores.map((s) => ({ value: s, label: s }))}
          className="flex-1"
        />
        <button
          type="button"
          onClick={salvar}
          disabled={!setor || salvando}
          className="px-4 py-2.5 rounded-xl bg-primary text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {salvando ? <Loader2 className="w-4 h-4 animate-spin" /> : "Salvar"}
        </button>
      </div>
    </li>
  );
}

function SecaoDeAcertos({
  titulo,
  vazio,
  children,
  quantidade,
}: {
  titulo: string;
  vazio: string;
  children: React.ReactNode;
  quantidade: number;
}) {
  const id = `acertos-${titulo.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <section aria-labelledby={id} className="rounded-2xl border border-border bg-white">
      <h2 id={id} className="px-4 py-3 border-b border-border text-base font-semibold text-text">
        {titulo}
      </h2>
      {quantidade === 0 ? (
        <p className="px-4 py-6 text-sm text-text-secondary">{vazio}</p>
      ) : (
        <ul className="divide-y divide-border">{children}</ul>
      )}
    </section>
  );
}

export default function AcertosDeSetorPage() {
  const { token, loading: authLoading } = useAuth();
  const { toast } = useToast();
  const [acertos, setAcertos] = useState<Acertos | null>(null);
  const [setores, setSetores] = useState<string[]>([]);

  const carregar = useCallback(async () => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const [resAcertos, resSetores] = await Promise.all([
        fetch("/api/admin/acertos-de-setor", { headers, cache: "no-store" }),
        fetch("/api/participantes/setores", { headers }),
      ]);
      if (!resAcertos.ok || !resSetores.ok) throw new Error();
      setAcertos((await resAcertos.json()) as Acertos);
      setSetores((await resSetores.json()) as string[]);
    } catch {
      toast("Não foi possível carregar a lista de acertos.", "error");
    }
  }, [token, toast]);

  useEffect(() => {
    if (!authLoading && token) carregar();
  }, [authLoading, token, carregar]);

  async function gravar(endereco: string, setor: string): Promise<boolean> {
    const res = await fetch(endereco, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ setor }),
    });
    if (!res.ok) {
      const corpo = await res.json().catch(() => null);
      toast(typeof corpo?.detail === "string" ? corpo.detail : "Não foi possível salvar o setor.", "error");
      return false;
    }
    toast("Setor salvo.", "success");
    return true;
  }

  async function salvarReuniao(id: string, setor: string) {
    if (!(await gravar(`/api/admin/acertos-de-setor/reunioes/${id}`, setor))) return;
    setAcertos((a) => a && { ...a, reunioes: a.reunioes.filter((r) => r.id_reuniao !== id) });
  }

  async function salvarResponsavel(id: string, setor: string) {
    if (!(await gravar(`/api/admin/acertos-de-setor/responsaveis/${id}`, setor))) return;
    setAcertos((a) => a && { ...a, responsaveis: a.responsaveis.filter((p) => p.id !== id) });
  }

  return (
    <div className="animate-fade-in-up space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-primary/10 text-primary">
          <MapPinned className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-text">Acertos de setor</h1>
          <p className="text-sm text-text-secondary">
            Reuniões e responsáveis que ficaram sem setor. Preenchido, o item sai da lista.
          </p>
        </div>
      </div>

      {!acertos ? (
        <div className="flex items-center justify-center py-16 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : (
        <>
          <SecaoDeAcertos
            titulo="Reuniões sem setor"
            vazio="Nenhuma reunião sem setor."
            quantidade={acertos.reunioes.length}
          >
            {acertos.reunioes.map((r) => (
              <LinhaDeAcerto
                key={r.id_reuniao}
                titulo={r.titulo || r.tipo || "Reunião"}
                detalhe={[dataCurta(r.data), r.tipo].filter(Boolean).join(", ")}
                setores={setores}
                onSalvar={(setor) => salvarReuniao(r.id_reuniao, setor)}
              />
            ))}
          </SecaoDeAcertos>

          <SecaoDeAcertos
            titulo="Responsáveis sem setor"
            vazio="Nenhum responsável sem setor."
            quantidade={acertos.responsaveis.length}
          >
            {acertos.responsaveis.map((p) => (
              <LinhaDeAcerto
                key={p.id}
                titulo={p.nome_completo}
                detalhe={[p.cargo, p.email].filter(Boolean).join(", ") || null}
                setores={setores}
                onSalvar={(setor) => salvarResponsavel(p.id, setor)}
              />
            ))}
          </SecaoDeAcertos>
        </>
      )}
    </div>
  );
}
