import { redirect } from "next/navigation";
import { DESTINO_PADRAO } from "@/lib/login/destino";

/**
 * A raiz do site não tem tela (ADR 0104, decisão 1): a capa com dois botões
 * saiu. O middleware já decide antes (Início com sessão, login sem); se a
 * requisição chegar aqui, segue para o Início, que manda ao login quem não
 * tem sessão.
 */
export default function Raiz() {
  redirect(DESTINO_PADRAO);
}
