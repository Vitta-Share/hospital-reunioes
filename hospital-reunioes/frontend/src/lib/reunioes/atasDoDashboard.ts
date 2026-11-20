// As atas que os cards do dashboard contam (issue #1055). O card mostra o
// tamanho da lista e o modal mostra a lista: uma fonte só, para o número e a
// lista nunca discordarem. Desde a issue #1868 as duas listas vêm prontas do
// servidor (`/api/pendencias/painel`), que lê a base inteira e aplica a regra
// da Ata parada (mais de 3 dias sem atualização) no recorte de quem pede.

export interface AtaDoDashboard {
  id_reuniao: string;
  data: string;
  tipo?: string | null;
  objetivo?: string | null;
  status_ata: string;
  updated_at?: string | null;
  // O Facilitador da Reunião (e o Super admin) vê quem falta assinar e cobra.
  pode_cobrar?: boolean;
}
