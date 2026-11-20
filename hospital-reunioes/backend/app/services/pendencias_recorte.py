"""Quem vê qual Pendência (ADR 0098, decisão 7; issue #1863).

O recorte sai do vínculo, e não da lista de participantes da Reunião: a pessoa
vê a Pendência de que é responsável ou co-responsável, todas as Pendências das
Reuniões que ela facilita, e o Super admin vê todas. Quem só participou da
Reunião deixa de ver a Pendência dos outros. Nenhum perfil novo em
`access_profile` (ADR 0007).

A Pendência de Reunião do Núcleo segue a ADR 0095: some para quem o Núcleo não
libera (as `ocultas`, inclusive o Super admin e o responsável), e quem o Núcleo
libera vê as Pendências dessas Reuniões como via a Reunião.

A função é pura: quem chama carrega os dados (`dependencies`) e pergunta aqui.
A Secretária não chega até aqui: as rotas a recusam com 403 antes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecorteDasPendencias:
    """O recorte de uma pessoa.

    `reunioes`: as Reuniões cujas Pendências ela vê todas (None = todas, a visão
    do Super admin). `participante_id`: para casar com o responsável e o
    co-responsável. `ocultas`: as Reuniões do Núcleo fora do alcance dela, que
    toda leitura tira.
    """

    reunioes: tuple[str, ...] | None
    participante_id: str | None
    ocultas: tuple[str, ...]

    def ve(self, pendencia: dict) -> bool:
        """Se a Pendência está no recorte."""
        if pendencia.get("id_reuniao") in self.ocultas:
            return False
        if self.reunioes is None:
            return True
        pid = self.participante_id
        # Token órfão: id None não casa com responsável None.
        if pid is not None and pid in (pendencia.get("responsavel_id"), pendencia.get("co_responsavel_id")):
            return True
        return pendencia.get("id_reuniao") in self.reunioes

    def filtro(self) -> str | None:
        """O `or` do PostgREST que a consulta aplica. None é sem filtro; texto
        vazio é que nada aparece. As `ocultas` são tiradas à parte
        (`sem_reunioes_ocultas`)."""
        if self.reunioes is None:
            return None
        condicoes = []
        if self.participante_id is not None:
            condicoes.append(f"responsavel_id.eq.{self.participante_id}")
            condicoes.append(f"co_responsavel_id.eq.{self.participante_id}")
        if self.reunioes:
            condicoes.append(f"id_reuniao.in.({','.join(self.reunioes)})")
        return ",".join(condicoes)


def recorte_das_pendencias(
    participante_id: str | None,
    *,
    super_admin: bool,
    facilitadas: list[str],
    do_nucleo: list[str],
    ocultas: list[str],
) -> RecorteDasPendencias:
    """O recorte de quem pede, a partir do vínculo."""
    if participante_id is None:
        return RecorteDasPendencias(reunioes=(), participante_id=None, ocultas=tuple(ocultas))
    if super_admin:
        return RecorteDasPendencias(reunioes=None, participante_id=participante_id, ocultas=tuple(ocultas))
    nucleo_liberado = [i for i in do_nucleo if i not in ocultas]
    reunioes = tuple(dict.fromkeys([*facilitadas, *nucleo_liberado]))
    return RecorteDasPendencias(reunioes=reunioes, participante_id=participante_id, ocultas=tuple(ocultas))
