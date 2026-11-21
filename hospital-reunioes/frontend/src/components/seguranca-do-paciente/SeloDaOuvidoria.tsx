/**
 * O selo do caso que a Ouvidoria mandou ao Núcleo (issue #1997): o estado da
 * manifestação numa palavra, que o servidor manda pronto. A manifestação
 * segue o curso dela na Ouvidoria; o Núcleo só vê em que pé ela está.
 */
export function SeloDaOuvidoria({ estado }: { estado: string | null }) {
  return (
    <span
      data-testid="selo-veio-da-ouvidoria"
      className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-xs font-semibold text-indigo-800"
    >
      {estado ? `Veio da Ouvidoria: ${estado}` : "Veio da Ouvidoria"}
    </span>
  );
}
