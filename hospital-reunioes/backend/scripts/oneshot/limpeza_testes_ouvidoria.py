"""Limpeza dos testes da Ouvidoria (issue #1962, PRD #1913, ADR 0102)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

# A janela é fixa no código, de propósito (ADR 0102, decisão 3): o script não
# aceita parâmetro de data. 19/10/2026 à 0h de Brasília até 17/11/2026 às
# 18h31min43s de Brasília, o instante em que o pedido nasceu, inclusive. O
# segundo final entra inteiro, com as frações dele.
INICIO_DA_JANELA = datetime(2026, 10, 19, 3, 0, 0, tzinfo=UTC)
FIM_DA_JANELA = datetime(2026, 11, 17, 21, 31, 43, tzinfo=UTC)
_DEPOIS_DA_JANELA = FIM_DA_JANELA + timedelta(seconds=1)


def na_janela(instante: datetime) -> bool:
    return INICIO_DA_JANELA <= instante < _DEPOIS_DA_JANELA


@dataclass(frozen=True)
class Avaliacao:
    id: str
    criada_em: datetime


@dataclass(frozen=True)
class Caso:
    id: str
    protocolo: str
    canal: str
    t0: datetime
    estado: str
    anonimo: bool
    avaliacao_id: str | None = None
    # Caminhos no bucket privado: os anexos do caso e os dos e-mails ligados.
    anexos: tuple[str, ...] = ()
    anexos_de_email: tuple[str, ...] = ()
    # Ids dos e-mails recebidos ligados ao caso (virou manifestação ou juntado).
    emails: tuple[str, ...] = ()
    acionamentos: int = 0
    links_de_setor: int = 0
    # Ligações com outros módulos, que têm trilha e filhas próprias.
    no_nucleo: bool = False
    no_canal_de_conduta: bool = False


AVALIACOES_ESPERADAS = 5
CANAIS_DE_TESTE = frozenset({"qr", "site"})


def motivos_que_barram(caso: Caso) -> list[str]:
    """Ligações que esta limpeza não desfaz: o caso só pode ficar."""
    motivos = []
    if caso.no_nucleo:
        motivos.append("virou notificação do Núcleo de Segurança do Paciente, que esta limpeza não apaga")
    if caso.no_canal_de_conduta:
        motivos.append("virou caso do Canal de Conduta, que esta limpeza não apaga")
    return motivos


def motivos_fora_do_padrao(caso: Caso) -> list[str]:
    """Por que o caso pode não ser teste (ADR 0102, decisão 6). Vazio = padrão de teste."""
    motivos = []
    if caso.canal not in CANAIS_DE_TESTE:
        motivos.append(f"não veio do QR nem do site (canal {caso.canal})")
    if caso.emails:
        motivos.append("tem e-mail recebido ligado")
    if caso.acionamentos:
        motivos.append("já tem acionamento de setor")
    if caso.links_de_setor:
        motivos.append("já tem link de setor enviado")
    return motivos + motivos_que_barram(caso)


@dataclass(frozen=True)
class Pendente:
    protocolo: str
    motivos: list[str]


@dataclass
class Escolha:
    avaliacoes: list[Avaliacao] = field(default_factory=list)
    casos: list[Caso] = field(default_factory=list)
    saem: list[Caso] = field(default_factory=list)
    ficam: list[Caso] = field(default_factory=list)
    pendentes: list[Pendente] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

    @property
    def ja_feita(self) -> bool:
        """Zero Avaliações e zero casos na janela: a limpeza já rodou."""
        return not self.avaliacoes and not self.casos

    @property
    def trava_dos_cinco(self) -> bool:
        return not self.ja_feita and len(self.avaliacoes) != AVALIACOES_ESPERADAS

    @property
    def pode_seguir(self) -> bool:
        return not (self.ja_feita or self.trava_dos_cinco or self.pendentes or self.erros)


def escolher(
    avaliacoes: list[Avaliacao],
    casos: list[Caso],
    liberar: list[str] | tuple[str, ...] = (),
    manter: list[str] | tuple[str, ...] = (),
) -> Escolha:
    """O que sai e o que fica. Função pura: só a janela e as decisões do diretor."""
    liberar_, manter_ = set(liberar), set(manter)
    escolha = Escolha(
        avaliacoes=[a for a in avaliacoes if na_janela(a.criada_em)],
        casos=[c for c in casos if na_janela(c.t0)],
    )

    na_lista = {c.protocolo for c in escolha.casos}
    for protocolo in sorted(liberar_ & manter_):
        escolha.erros.append(f"{protocolo}: está em --liberar e em --manter ao mesmo tempo")
    for protocolo in sorted((liberar_ | manter_) - na_lista):
        escolha.erros.append(f"{protocolo}: não é caso da janela (erro de digitação?)")

    for caso in escolha.casos:
        if caso.protocolo in manter_:
            escolha.ficam.append(caso)
            continue
        motivos = motivos_fora_do_padrao(caso)
        if not motivos:
            escolha.saem.append(caso)
        elif caso.protocolo not in liberar_:
            escolha.pendentes.append(Pendente(caso.protocolo, motivos))
        elif barram := motivos_que_barram(caso):
            escolha.erros.append(f"{caso.protocolo}: não aceita --liberar, só --manter ({'; '.join(barram)})")
        else:
            escolha.saem.append(caso)
    return escolha
