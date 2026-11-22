"use client";

/**
 * O gráfico de atrasos por setor e o ranking de 90 dias do painel de Reuniões
 * (issue #1871). Os números vêm prontos de `/api/pendencias/painel`, do
 * hospital inteiro. O gráfico por setor chega para o Super admin e para quem
 * facilita ao menos uma Reunião; o ranking, com nomes, só para o Super admin.
 * O que o endpoint manda como `null` não aparece.
 *
 * Atrasos são as abertas com o prazo vencido agora e, nos últimos 90 dias, as
 * Repactuações depois do vencimento e as conclusões depois do prazo. As
 * Reaberturas ficam ao lado, sem somar nos atrasos, e as Rotinas não cumpridas
 * também (issue #1879): o ciclo não realizado, marcado fora do ciclo ou
 * fechado sem marcação.
 */

export interface AtrasosDoPainel {
  atrasadas: number;
  repactuacoes_vencidas: number;
  concluidas_com_atraso: number;
  atrasos: number;
  reaberturas: number;
  rotinas_nao_cumpridas: number;
}

export interface SetorDosAtrasos extends AtrasosDoPainel {
  setor: string;
}

export interface LinhaDoRanking extends AtrasosDoPainel {
  responsavel_id: string;
  nome: string | null;
  setor: string;
}

interface Props {
  porSetor: SetorDosAtrasos[];
  ranking: LinhaDoRanking[] | null;
}

function largura(valor: number, maior: number): string {
  return `${((valor / Math.max(1, maior)) * 100).toFixed(2)}%`;
}

export default function RankingDeAtrasos({ porSetor, ranking }: Props) {
  const maior = Math.max(0, ...porSetor.map((s) => s.atrasos));
  return (
    <div className={`grid grid-cols-1 gap-6 mt-6 ${ranking ? "lg:grid-cols-2" : ""}`}>
      <section
        aria-labelledby="atrasos-por-setor"
        className="bg-surface rounded-xl p-6 border border-border shadow-premium"
      >
        <h2 id="atrasos-por-setor" className="text-lg font-bold text-text mb-1">
          Atrasos por setor
        </h2>
        <p className="text-text-secondary text-xs mb-4">
          Hospital inteiro, no setor do responsável, nos últimos 90 dias
        </p>
        {porSetor.length === 0 ? (
          <p className="text-text-secondary text-sm">Nenhum atraso nos últimos 90 dias.</p>
        ) : (
          <ul className="space-y-3">
            {porSetor.map((s) => (
              <li key={s.setor}>
                <div className="flex justify-between text-sm">
                  <span className="text-text">{s.setor}</span>
                  <span className="text-text-secondary tabular-nums">
                    {s.atrasos} {s.atrasos === 1 ? "atraso" : "atrasos"}, {s.reaberturas}{" "}
                    {s.reaberturas === 1 ? "reabertura" : "reaberturas"}, {s.rotinas_nao_cumpridas}{" "}
                    {s.rotinas_nao_cumpridas === 1 ? "rotina não cumprida" : "rotinas não cumpridas"}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-border mt-1">
                  <div
                    className="h-2 rounded-full bg-red-300"
                    style={{ width: largura(s.atrasos, maior) }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {ranking && (
        <section
          aria-labelledby="ranking-de-atrasos"
          className="bg-surface rounded-xl p-6 border border-border shadow-premium overflow-x-auto"
        >
          <h2 id="ranking-de-atrasos" className="text-lg font-bold text-text mb-1">
            Ranking de atrasos
          </h2>
          <p className="text-text-secondary text-xs mb-4">
            Responsáveis do hospital inteiro, nos últimos 90 dias
          </p>
          {ranking.length === 0 ? (
            <p className="text-text-secondary text-sm">Nenhum atraso nos últimos 90 dias.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-secondary text-xs">
                  <th className="py-1 pr-2 font-medium">Responsável</th>
                  <th className="py-1 pr-2 font-medium">Setor</th>
                  <th className="py-1 pr-2 font-medium text-right">Vencidas agora</th>
                  <th className="py-1 pr-2 font-medium text-right">Repactuadas depois do prazo</th>
                  <th className="py-1 pr-2 font-medium text-right">Concluídas com atraso</th>
                  <th className="py-1 pr-2 font-medium text-right">Atrasos</th>
                  <th className="py-1 pr-2 font-medium text-right">Reaberturas</th>
                  <th className="py-1 font-medium text-right">Rotinas não cumpridas</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((linha) => (
                  <tr key={linha.responsavel_id} className="border-t border-border">
                    <td className="py-1 pr-2 text-text">{linha.nome ?? "Sem nome"}</td>
                    <td className="py-1 pr-2 text-text-secondary">{linha.setor}</td>
                    <td className="py-1 pr-2 text-right tabular-nums">{linha.atrasadas}</td>
                    <td className="py-1 pr-2 text-right tabular-nums">{linha.repactuacoes_vencidas}</td>
                    <td className="py-1 pr-2 text-right tabular-nums">{linha.concluidas_com_atraso}</td>
                    <td className="py-1 pr-2 text-right tabular-nums font-semibold">{linha.atrasos}</td>
                    <td className="py-1 pr-2 text-right tabular-nums">{linha.reaberturas}</td>
                    <td className="py-1 text-right tabular-nums">{linha.rotinas_nao_cumpridas}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  );
}
