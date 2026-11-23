/**
 * Quem tem histórico no app não sai da tabela: o DELETE de usuário desliga o
 * cadastro no lugar de excluir e diz qual dos dois aconteceu (issue #2043).
 */
export async function confirmacaoDaExclusao(res: Response): Promise<string> {
  const { resultado } = (await res.json()) as { resultado?: string };
  return resultado === "desligado"
    ? "Usuário desligado; o histórico dele foi mantido"
    : "Usuário excluído";
}
