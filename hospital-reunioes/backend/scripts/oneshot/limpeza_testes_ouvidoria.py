"""Limpeza dos testes da Ouvidoria (issue #1962, PRD #1913, ADR 0102).

As cinco Avaliações de teste e os casos abertos no mesmo período saem por
inteiro: caso, protocolo, trilha, log de acesso, anexos (linha e arquivo),
links do setor, notificações, prorrogações, tentativas de contato,
acionamentos e o e-mail recebido do caso liberado. É a única exceção à ADR
0047, e roda por fora do app, pela mão de uma pessoa.

O que este script faz:

- conferência (padrão, só lê): a primeira linha diz o banco alvo. Mostra
  quantas Avaliações há na janela e os casos, só com protocolo, canal, T0,
  estado, se é anônimo e quantos anexos tem. Nunca imprime relato, nome,
  contato, Paciente do caso nem comentário de Avaliação;
- trava dos cinco: sem exatamente cinco Avaliações na janela, para com saída
  1 e não gera nada. Zero Avaliações e zero casos = limpeza já feita, saída 0;
- caso fora do padrão de teste (não veio do QR nem do site, tem e-mail
  recebido ligado, já tem acionamento ou link de setor, virou notificação do
  Núcleo ou caso do Canal de Conduta) para o script até o diretor decidir:
  `--liberar <protocolo>` (sai junto) ou `--manter <protocolo>` (fica). O caso
  ligado ao Núcleo ou ao Canal de Conduta só aceita `--manter`;
- `--aplicar`: passa pelas mesmas travas, tira do bucket privado os arquivos
  dos anexos, um a um, grava o SQL em `local/limpeza-1913.sql` (fora do git) e
  imprime a Lista da limpeza para o diretor.

A janela é fixa no código e não há parâmetro de data. O SQL mira a lista de ids
que a conferência viu, nunca a janela.

Comandos, na ordem em que a pessoa roda em produção (pasta
`hospital-reunioes/backend`, com o `.env` de produção):

1. Conferência. Confira na primeira linha que o banco alvo é o certo:
    uv run python -m scripts.oneshot.limpeza_testes_ouvidoria

2. Se houver caso fora do padrão, leve os protocolos ao diretor na Conversa
   da Demanda #1913 e rode a conferência de novo com a resposta dele:
    uv run python -m scripts.oneshot.limpeza_testes_ouvidoria --liberar 2026-0123 --manter 2026-0124

3. Com a conferência limpa, tire os arquivos do bucket e gere o SQL (repita
   os mesmos --liberar e --manter):
    uv run python -m scripts.oneshot.limpeza_testes_ouvidoria --aplicar

4. Abra `local/limpeza-1913.sql` (na raiz do repositório), cole inteiro no SQL
   Editor do Studio e rode de uma vez. Se alguma contagem não bater, nada
   muda: volte ao passo 1. A última consulta mostra os dois gatilhos ligados.

5. Rode a conferência de novo. Ela tem de dizer que a limpeza já foi feita.
   Mande ao diretor a Lista da limpeza que o passo 3 imprimiu.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

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


# ---------------------------------------------------------------------------
# O SQL avulso
# ---------------------------------------------------------------------------

# As filhas da Manifestação e do e-mail recebido, na ordem em que saem. Cada
# uma segura o pai com ON DELETE RESTRICT, então saem antes dele. `casos` e
# `emails` são os arrays de ids conferidos, declarados no topo do bloco.
TABELAS_APAGADAS: tuple[tuple[str, str], ...] = (
    ("ouvidoria_acessos", "manifestacao_id = ANY(casos) OR email_recebido_id = ANY(emails)"),
    ("ouvidoria_movimentos", "manifestacao_id = ANY(casos)"),
    ("ouvidoria_anexos", "manifestacao_id = ANY(casos)"),
    ("ouvidoria_notificacoes", "manifestacao_id = ANY(casos)"),
    ("ouvidoria_setor_tokens", "manifestacao_id = ANY(casos)"),
    ("ouvidoria_prorrogacoes", "manifestacao_id = ANY(casos)"),
    ("ouvidoria_tentativas_contato", "manifestacao_id = ANY(casos)"),
    ("ouvidoria_acionamentos", "manifestacao_id = ANY(casos)"),
    ("ouvidoria_emails_recebidos_anexos", "email_recebido_id = ANY(emails)"),
    ("ouvidoria_emails_recebidos", "manifestacao_id = ANY(casos)"),
)

# Filhas da Manifestação que são casos de outro módulo, com trilha e filhas
# próprias. A limpeza não as apaga: o SQL confere que nenhuma aponta para os
# casos da lista e, se apontar, levanta erro e nada muda.
TABELAS_QUE_BARRAM: tuple[str, ...] = ("nsp_notificacoes", "conduta_casos")

# Os dois gatilhos que recusam DELETE (migration 064): a trilha e o log de acesso.
GATILHOS_DE_DELETE: tuple[tuple[str, str], ...] = (
    ("ouvidoria_movimentos", "trg_ouvidoria_movimentos_sem_delete"),
    ("ouvidoria_acessos", "trg_ouvidoria_acessos_sem_delete"),
)


@dataclass
class Plano:
    """A lista fechada que a conferência viu, e quantas linhas cada tabela tem
    para esses ids. O SQL apaga exatamente isso ou nada."""

    casos: tuple[str, ...]
    emails: tuple[str, ...]
    avaliacoes: tuple[str, ...]
    esperado: dict[str, int]


def _array_uuid(ids: tuple[str, ...]) -> str:
    for id_ in ids:
        # Os ids vêm do banco, mas o SQL é colado à mão: só passa UUID.
        if not _UUID.fullmatch(id_):
            raise ValueError(f"id fora do formato UUID: {id_!r}")
    if not ids:
        return "ARRAY[]::uuid[]"
    itens = ",\n    ".join(f"'{id_}'" for id_ in ids)
    return f"ARRAY[\n    {itens}\n  ]::uuid[]"


def _apaga(tabela: str, onde: str, esperado: int) -> str:
    return (
        f"  DELETE FROM {tabela} WHERE {onde};\n"
        f"  GET DIAGNOSTICS n = ROW_COUNT;\n"
        f"  IF n <> {esperado} THEN\n"
        f"    RAISE EXCEPTION '{tabela}: esperava apagar {esperado} linha(s) e apagou %. Nada mudou.', n;\n"
        f"  END IF;\n"
    )


def gerar_sql(plano: Plano) -> str:
    """O SQL avulso da limpeza: uma transação, ids fechados, contagem conferida."""
    linhas = [
        "-- Limpeza dos testes da Ouvidoria (PRD #1913, issue #1962, ADR 0102).",
        "-- Gerado pelo scripts/oneshot/limpeza_testes_ouvidoria.py --aplicar.",
        "-- Fica fora do git. Rode inteiro, de uma vez. Se qualquer contagem não",
        "-- bater, a transação levanta erro e nada muda: rode a conferência de novo.",
        "",
        "BEGIN;",
        "",
        "-- Os dois gatilhos que recusam DELETE ficam desligados só dentro desta transação.",
    ]
    linhas += [f"ALTER TABLE {t} DISABLE TRIGGER {g};" for t, g in GATILHOS_DE_DELETE]
    corpo = [
        "",
        "DO $limpeza$",
        "DECLARE",
        f"  casos uuid[] := {_array_uuid(plano.casos)};",
        f"  emails uuid[] := {_array_uuid(plano.emails)};",
        f"  avaliacoes uuid[] := {_array_uuid(plano.avaliacoes)};",
        "  n bigint;",
        "BEGIN",
    ]
    linhas += corpo
    for tabela in TABELAS_QUE_BARRAM:
        linhas.append(
            f"  SELECT count(*) INTO n FROM {tabela} WHERE manifestacao_id = ANY(casos);\n"
            f"  IF n <> 0 THEN\n"
            f"    RAISE EXCEPTION '{tabela}: % linha(s) ligada(s) a caso da lista. Nada mudou.', n;\n"
            f"  END IF;"
        )
    for tabela, onde in TABELAS_APAGADAS:
        linhas.append(_apaga(tabela, onde, plano.esperado[tabela]).rstrip("\n"))
    linhas.append(
        _apaga("ouvidoria_protocolos", "id = ANY(casos)", plano.esperado["ouvidoria_protocolos"]).rstrip("\n")
    )
    linhas.append(
        _apaga("ouvidoria_avaliacoes", "id = ANY(avaliacoes)", plano.esperado["ouvidoria_avaliacoes"]).rstrip("\n")
    )
    linhas += ["END", "$limpeza$;", "", "-- Religa os gatilhos antes do fim."]
    linhas += [f"ALTER TABLE {t} ENABLE TRIGGER {g};" for t, g in GATILHOS_DE_DELETE]
    linhas += ["", "COMMIT;", "", "-- Prova de que os dois gatilhos voltaram a valer (ligado = true)."]
    nomes = ", ".join(f"'{g}'" for _, g in GATILHOS_DE_DELETE)
    linhas.append(
        "SELECT tgrelid::regclass AS tabela, tgname AS gatilho, tgenabled = 'O' AS ligado\n"
        f"  FROM pg_trigger WHERE tgname IN ({nomes}) ORDER BY tgname;"
    )
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------------------
# A leitura do banco
# ---------------------------------------------------------------------------

# Raiz do repositório: hospital-reunioes/backend/scripts/oneshot/este_arquivo.
DESTINO_SQL = Path(__file__).resolve().parents[4] / "local" / "limpeza-1913.sql"
BRASILIA = timezone(timedelta(hours=-3))
PAGINA = 500
LOTE_DE_IDS = 50


def _ler(cliente, tabela: str, colunas: str, filtro=None) -> list[dict]:
    """Todas as linhas, em páginas: o PostgREST corta a resposta num teto."""
    linhas: list[dict] = []
    inicio = 0
    while True:
        consulta = cliente.table(tabela).select(colunas)
        if filtro:
            consulta = filtro(consulta)
        recebidas = list(consulta.order("id").range(inicio, inicio + PAGINA - 1).execute().data or [])
        linhas.extend(recebidas)
        if len(recebidas) < PAGINA:
            return linhas
        inicio += PAGINA


def _ler_por(cliente, tabela: str, colunas: str, coluna: str, valores: Iterable[str]) -> list[dict]:
    """As linhas cuja `coluna` está em `valores`, em lotes que cabem na URL."""
    valores = sorted(set(valores))
    linhas: list[dict] = []
    for i in range(0, len(valores), LOTE_DE_IDS):
        lote = valores[i : i + LOTE_DE_IDS]
        linhas += _ler(cliente, tabela, colunas, lambda c, lote=lote: c.in_(coluna, lote))
    return linhas


def _na_janela_do_banco(coluna: str):
    return lambda c: c.gte(coluna, INICIO_DA_JANELA.isoformat()).lt(coluna, _DEPOIS_DA_JANELA.isoformat())


def _instante(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def ler_avaliacoes(cliente) -> list[Avaliacao]:
    # Só id e data: o comentário da Avaliação nunca é lido.
    linhas = _ler(cliente, "ouvidoria_avaliacoes", "id, criada_em", _na_janela_do_banco("criada_em"))
    return [Avaliacao(linha["id"], _instante(linha["criada_em"])) for linha in linhas]


def ler_casos(cliente) -> list[Caso]:
    """Os casos da janela, com o que a conferência precisa. Colunas escolhidas
    uma a uma: nenhuma do Dossiê sai do banco."""
    linhas = _ler(
        cliente,
        "ouvidoria_protocolos",
        "id, protocolo, canal, contato_em, status, anonimo, avaliacao_id",
        _na_janela_do_banco("contato_em"),
    )
    ids = [linha["id"] for linha in linhas]

    def por_caso(tabela: str, colunas: str = "id, manifestacao_id") -> dict[str, list[dict]]:
        agrupado: dict[str, list[dict]] = {}
        for linha in _ler_por(cliente, tabela, colunas, "manifestacao_id", ids):
            agrupado.setdefault(linha["manifestacao_id"], []).append(linha)
        return agrupado

    anexos = por_caso("ouvidoria_anexos", "id, manifestacao_id, storage_path")
    emails = por_caso("ouvidoria_emails_recebidos")
    acionamentos = por_caso("ouvidoria_acionamentos")
    links = por_caso("ouvidoria_setor_tokens")
    nucleo = por_caso("nsp_notificacoes")
    conduta = por_caso("conduta_casos")
    ids_de_email = [e["id"] for lista in emails.values() for e in lista]
    anexos_de_email: dict[str, list[str]] = {}
    for linha in _ler_por(
        cliente,
        "ouvidoria_emails_recebidos_anexos",
        "id, email_recebido_id, storage_path",
        "email_recebido_id",
        ids_de_email,
    ):
        if linha.get("storage_path"):
            anexos_de_email.setdefault(linha["email_recebido_id"], []).append(linha["storage_path"])

    casos = []
    for linha in linhas:
        id_ = linha["id"]
        emails_do_caso = tuple(sorted(e["id"] for e in emails.get(id_, [])))
        casos.append(
            Caso(
                id=id_,
                protocolo=linha["protocolo"],
                canal=linha["canal"],
                t0=_instante(linha["contato_em"]),
                estado=linha["status"],
                anonimo=bool(linha["anonimo"]),
                avaliacao_id=linha.get("avaliacao_id"),
                anexos=tuple(sorted(a["storage_path"] for a in anexos.get(id_, []))),
                anexos_de_email=tuple(sorted(p for e in emails_do_caso for p in anexos_de_email.get(e, []))),
                emails=emails_do_caso,
                acionamentos=len(acionamentos.get(id_, [])),
                links_de_setor=len(links.get(id_, [])),
                no_nucleo=bool(nucleo.get(id_)),
                no_canal_de_conduta=bool(conduta.get(id_)),
            )
        )
    return sorted(casos, key=lambda c: c.protocolo)


def montar_plano(cliente, escolha: Escolha) -> Plano:
    """Quantas linhas cada tabela tem para os ids que saem. O SQL confere essas
    contagens dentro da transação."""
    casos = tuple(sorted(c.id for c in escolha.saem))
    emails = tuple(sorted(e for c in escolha.saem for e in c.emails))
    avaliacoes = tuple(sorted(a.id for a in escolha.avaliacoes))
    esperado: dict[str, int] = {}
    for tabela, _onde in TABELAS_APAGADAS:
        if tabela == "ouvidoria_acessos":
            achadas = {linha["id"] for linha in _ler_por(cliente, tabela, "id", "manifestacao_id", casos)}
            achadas |= {linha["id"] for linha in _ler_por(cliente, tabela, "id", "email_recebido_id", emails)}
        elif tabela == "ouvidoria_emails_recebidos_anexos":
            achadas = {linha["id"] for linha in _ler_por(cliente, tabela, "id", "email_recebido_id", emails)}
        else:
            achadas = {linha["id"] for linha in _ler_por(cliente, tabela, "id", "manifestacao_id", casos)}
        esperado[tabela] = len(achadas)
    esperado["ouvidoria_protocolos"] = len(casos)
    esperado["ouvidoria_avaliacoes"] = len(avaliacoes)
    return Plano(casos=casos, emails=emails, avaliacoes=avaliacoes, esperado=esperado)


def casos_que_perdem_a_avaliacao(cliente, escolha: Escolha) -> list[str]:
    """Caso que fica e aponta para uma Avaliação que sai: o banco só tira a
    ligação (ON DELETE SET NULL). Vai na conferência para ninguém se surpreender."""
    ficam = {c.id for c in escolha.ficam}
    # Caso da janela que não ficou por decisão (sai ou ainda espera) não conta.
    sem_aviso = {c.id for c in escolha.casos} - ficam
    linhas = _ler_por(
        cliente, "ouvidoria_protocolos", "id, protocolo", "avaliacao_id", [a.id for a in escolha.avaliacoes]
    )
    return sorted(linha["protocolo"] for linha in linhas if linha["id"] not in sem_aviso)


# ---------------------------------------------------------------------------
# O bucket
# ---------------------------------------------------------------------------


class Bucket(Protocol):
    def remover(self, caminho: str) -> bool:
        """True só quando o Storage confirma que apagou este caminho."""

    def existe(self, caminho: str) -> bool: ...


class BucketDoStorage:
    def __init__(self, cliente, nome: str):
        self._bucket = cliente.storage.from_(nome)

    def remover(self, caminho: str) -> bool:
        apagados = self._bucket.remove([caminho]) or []
        return any(objeto.get("name") == caminho for objeto in apagados)

    def existe(self, caminho: str) -> bool:
        return self._bucket.exists(caminho)


@dataclass
class ResultadoDoBucket:
    removidos: list[str] = field(default_factory=list)
    ja_ausentes: list[str] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)


def limpar_bucket(bucket: Bucket, caminhos: Iterable[str]) -> ResultadoDoBucket:
    """Um arquivo por vez, conferindo a confirmação do Storage. O que já não
    está no bucket conta como removido: a segunda execução não falha."""
    resultado = ResultadoDoBucket()
    for caminho in sorted(set(caminhos)):
        if bucket.remover(caminho):
            resultado.removidos.append(caminho)
        elif not bucket.existe(caminho):
            resultado.ja_ausentes.append(caminho)
        else:
            resultado.falhas.append(caminho)
    return resultado


# ---------------------------------------------------------------------------
# A saída
# ---------------------------------------------------------------------------


def _hora_de_brasilia(instante: datetime) -> str:
    return instante.astimezone(BRASILIA).strftime("%d/%m/%Y %H:%M:%S")


def _linha_do_caso(caso: Caso) -> str:
    anexos = len(caso.anexos) + len(caso.anexos_de_email)
    return (
        f"  {caso.protocolo} | canal {caso.canal} | T0 {_hora_de_brasilia(caso.t0)} | {caso.estado}"
        f" | anônimo: {'sim' if caso.anonimo else 'não'} | anexos: {anexos}"
    )


def imprimir_conferencia(escolha: Escolha, perdem_avaliacao: list[str]) -> None:
    print(
        f"Janela (fixa no código): {_hora_de_brasilia(INICIO_DA_JANELA)} até "
        f"{_hora_de_brasilia(FIM_DA_JANELA)}, hora de Brasília, inclusive"
    )
    print(f"{len(escolha.avaliacoes)} Avaliações na janela (esperadas: {AVALIACOES_ESPERADAS})")
    print(f"{len(escolha.casos)} casos na janela:")
    for caso in escolha.casos:
        print(_linha_do_caso(caso))
    if escolha.ficam:
        print("Ficam no banco por decisão do diretor (--manter): " + ", ".join(c.protocolo for c in escolha.ficam))
    if perdem_avaliacao:
        print("Aviso: estes casos ficam e perdem só a ligação com a Avaliação que sai: " + ", ".join(perdem_avaliacao))


def imprimir_travas(escolha: Escolha) -> None:
    if escolha.trava_dos_cinco:
        print(
            f"\nPAROU: a janela tem {len(escolha.avaliacoes)} Avaliações, e o diretor falou em "
            f"{AVALIACOES_ESPERADAS}. A diferença vira pergunta a ele na Conversa da Demanda #1913."
        )
    if escolha.pendentes:
        print("\nPAROU: casos fora do padrão de teste, à espera da decisão do diretor (--liberar ou --manter):")
        for pendente in escolha.pendentes:
            print(f"  {pendente.protocolo}: {'; '.join(pendente.motivos)}")
    if escolha.erros:
        print("\nPAROU: decisões que não fecham:")
        for erro in escolha.erros:
            print(f"  {erro}")


def imprimir_lista_da_limpeza(escolha: Escolha, bucket: ResultadoDoBucket, destino: Path) -> None:
    print("\n=== Lista da limpeza (para o diretor, na Conversa da Demanda #1913) ===")
    print(f"Avaliações que saem: {len(escolha.avaliacoes)}")
    print(f"Casos que saem ({len(escolha.saem)}): " + ", ".join(c.protocolo for c in escolha.saem))
    if escolha.ficam:
        print("Casos que ficam por decisão do diretor: " + ", ".join(c.protocolo for c in escolha.ficam))
    print(f"\nArquivos tirados do bucket: {len(bucket.removidos)}; já não estavam lá: {len(bucket.ja_ausentes)}.")
    print(f"SQL gravado em {destino}. Cole inteiro no SQL Editor do Studio e rode de uma vez.")


# ---------------------------------------------------------------------------
# O script
# ---------------------------------------------------------------------------


def criar_parser() -> argparse.ArgumentParser:
    # Sem parâmetro de data, de propósito: a janela é a da ADR 0102.
    parser = argparse.ArgumentParser(description="Limpeza dos testes da Ouvidoria (ADR 0102)")
    parser.add_argument("--aplicar", action="store_true", help="tira os arquivos do bucket e grava o SQL")
    parser.add_argument(
        "--liberar", action="append", default=[], metavar="PROTOCOLO", help="caso fora do padrão que sai"
    )
    parser.add_argument("--manter", action="append", default=[], metavar="PROTOCOLO", help="caso que fica no banco")
    return parser


def executar(cliente, bucket: Bucket, url_do_banco: str, argv: list[str], destino: Path) -> int:
    args = criar_parser().parse_args(argv)
    print(f"Banco alvo: {url_do_banco}")

    escolha = escolher(ler_avaliacoes(cliente), ler_casos(cliente), args.liberar, args.manter)
    if escolha.ja_feita:
        print("Nenhuma Avaliação e nenhum caso na janela: a limpeza já foi feita. Nada a fazer.")
        return 0
    imprimir_conferencia(escolha, casos_que_perdem_a_avaliacao(cliente, escolha))
    if not escolha.pode_seguir:
        imprimir_travas(escolha)
        print("\nNada foi tocado: nenhum arquivo saiu do bucket e nenhum SQL foi gerado.")
        return 1
    if not args.aplicar:
        print("\nConferência limpa. Nada foi tocado. Rode de novo com --aplicar para valer.")
        return 0

    plano = montar_plano(cliente, escolha)
    caminhos = [p for c in escolha.saem for p in (*c.anexos, *c.anexos_de_email)]
    resultado = limpar_bucket(bucket, caminhos)
    if resultado.falhas:
        print("\nPAROU: o Storage não confirmou a remoção destes arquivos, e eles seguem no bucket:")
        for caminho in resultado.falhas:
            print(f"  {caminho}")
        print("Nenhum SQL foi gerado. Rode --aplicar de novo.")
        return 1

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(gerar_sql(plano), encoding="utf-8")
    imprimir_lista_da_limpeza(escolha, resultado, destino)
    return 0


def main() -> int:
    from supabase import create_client

    from app.config import settings

    cliente = create_client(settings.supabase_url, settings.supabase_service_role_key)
    bucket = BucketDoStorage(cliente, settings.supabase_storage_bucket_anexos_ouvidoria)
    return executar(cliente, bucket, settings.supabase_url, sys.argv[1:], DESTINO_SQL)


if __name__ == "__main__":
    sys.exit(main())
