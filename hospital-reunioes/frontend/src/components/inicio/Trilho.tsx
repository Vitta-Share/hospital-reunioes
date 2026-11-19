import Link from "next/link";

/** Uma linha do trilho do Início (issue #1936): por ora, a próxima Reunião. */
export interface ItemDoTrilho {
  tipo: string;
  id: string;
  titulo: string;
  data: string;
  hora: string | null;
  papel: "facilitador" | "participante";
  destino: string;
}

const DIAS_DA_SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

/** "2026-11-20" e "14:00" viram "sex, 20/11, 14:00", sem passar por fuso. */
function quando(item: ItemDoTrilho, hoje: string): string {
  const [ano, mes, dia] = item.data.slice(0, 10).split("-").map(Number);
  const semana = item.data.slice(0, 10) === hoje ? "Hoje" : DIAS_DA_SEMANA[new Date(ano, mes - 1, dia).getDay()];
  const data = `${semana}, ${String(dia).padStart(2, "0")}/${String(mes).padStart(2, "0")}`;
  return item.hora ? `${data}, ${item.hora}` : data;
}

/**
 * O trilho, ao lado da Minha Fila: as próximas Reuniões da pessoa, com dia,
 * hora e o link para cada uma. Não conta na frase nem nos contadores.
 */
export function Trilho({ itens, hoje }: { itens: ItemDoTrilho[]; hoje: string }) {
  return (
    <aside aria-label="Próximas Reuniões" className="min-w-0">
      <p aria-hidden className="etiqueta pb-2 border-b border-border text-xs text-text-secondary">
        Próximas Reuniões
      </p>
      {itens.length === 0 ? (
        <p className="py-3.5 text-sm text-text-secondary">Nenhuma Reunião marcada.</p>
      ) : (
        <ul>
          {itens.map((item) => (
            <li key={`${item.tipo}:${item.id}`} className="border-b border-border">
              <Link href={item.destino} className="block py-3 px-1 rounded-lg hover:bg-slate-50">
                <span className="block text-xs text-text-secondary tabular-nums">{quando(item, hoje)}</span>
                <span className="block text-sm text-text mt-0.5 leading-snug">{item.titulo}</span>
                <span className="block text-xs text-text-secondary mt-0.5">
                  {item.papel === "facilitador" ? "Você conduz" : "Você participa"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
