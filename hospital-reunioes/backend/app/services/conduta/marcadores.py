"""Os marcadores numerados e reversíveis do Canal de Conduta (ADR 0097,
decisão 7; issue #1831).

Nenhum nome vai à IA. O termo de declaração e a ata, porém, precisam dos
nomes de volta, exatamente como foram ditos. Então cada nome vira um marcador
numerado na ida (`[PESSOA_1]`) e volta a ser o nome dentro do app. O mesmo
nome, escrito do mesmo jeito, ganha sempre o mesmo marcador.

Duas camadas, nesta ordem:

1. os nomes que o app conhece (o declarante, quem conduziu, os citados, as
   pessoas ouvidas e os membros do caso), cada um inteiro e cada palavra dele
   sozinha, porque a transcrição chama a pessoa pelo primeiro nome;
2. o que a pseudonimização da Ouvidoria (ADR 0034) acha no resto: nomes
   desconhecidos, CPF, telefone, e-mail e os outros identificadores. O texto
   que sai é o dela, com o marcador numerado no lugar do genérico.

Para numerar o que a pseudonimização trocou, o trecho original de cada
marcador é achado entre os pedaços que ela deixou como estavam. Quando o
pedaço seguinte aparece mais de uma vez, vale o primeiro ponto em que o trecho
de antes, sozinho, também vira marcador; sem nenhum, o primeiro. Se o
alinhamento falhar, o marcador sai genérico e sem volta: o que importa é o
nome não sair.
"""

from __future__ import annotations

import re

from app.services.ouvidoria_pseudonimizacao import pseudonimizar

# Os marcadores genéricos que a pseudonimização deixa.
_GENERICO = re.compile(
    r"\[(EMAIL|REDE_SOCIAL|CPF|RG|CEP|PLACA|CNS|DATA_NASCIMENTO|PROTOCOLO|TELEFONE|NOME)\]"
)
# O nome desconhecido também vira PESSOA: o modelo lê um tipo só de pessoa.
_TIPO = {"NOME": "PESSOA"}
_NUMERADO = re.compile(r"\[(?:PESSOA|EMAIL|REDE_SOCIAL|CPF|RG|CEP|PLACA|CNS|DATA_NASCIMENTO|PROTOCOLO|TELEFONE)_\d+\]")

# O lugar guardado de um nome conhecido: um caractere do plano de uso privado,
# que não é letra, dígito nem espaço. A pseudonimização passa por ele sem
# juntá-lo a um nome nem a um número.
_BASE_DO_LUGAR = 0xF0000
_LUGARES = re.compile("[\U000f0000-\U000fffff]")
# A pseudonimização tira estes dois do texto (são os lugares guardados dela).
_TIRADOS_PELA_PSEUDONIMIZACAO = ("\x00", "\x01")

_CONECTIVOS = frozenset({"de", "da", "do", "das", "dos", "e"})
# Um nome ou um número trocado nunca passa disto. Limita a busca do trecho,
# que de outro jeito cresceria com o tamanho da transcrição.
_TRECHO_MAXIMO = 300


class Marcacao:
    """Uma ida e volta: marque todos os textos de uma chamada com a mesma
    marcação, para o mesmo nome ter o mesmo marcador em todos eles."""

    def __init__(self) -> None:
        self.originais: dict[str, str] = {}
        self._marcador_de: dict[tuple[str, str], str] = {}
        self._contagem: dict[str, int] = {}
        self._lugares: list[str] = []

    def marcador(self, tipo: str, original: str) -> str:
        chave = (tipo, original)
        if chave not in self._marcador_de:
            self._contagem[tipo] = self._contagem.get(tipo, 0) + 1
            marcador = f"[{tipo}_{self._contagem[tipo]}]"
            self._marcador_de[chave] = marcador
            self.originais[marcador] = original
        return self._marcador_de[chave]

    # ── a ida ──────────────────────────────────────────────────────────────

    def marcar(self, texto: str, conhecidos: list[str] | tuple[str, ...] = ()) -> str:
        """O texto sem nome nenhum, com os marcadores numerados."""
        if not texto:
            return ""
        for tirado in _TIRADOS_PELA_PSEUDONIMIZACAO:
            texto = texto.replace(tirado, "")
        texto = _LUGARES.sub("", texto)
        texto = self._guardar_conhecidos(texto, conhecidos)
        mascarado = pseudonimizar(texto)
        saida = self._numerar(texto, mascarado)
        return _LUGARES.sub(lambda m: self._lugares[ord(m.group(0)) - _BASE_DO_LUGAR], saida)

    def _guardar_conhecidos(self, texto: str, conhecidos) -> str:
        formas: set[str] = set()
        for nome in conhecidos:
            nome = " ".join((nome or "").split())
            if len(nome) < 2:
                continue
            formas.add(nome)
            formas |= {p for p in nome.split(" ") if len(p) >= 3 and p.lower() not in _CONECTIVOS}
        for forma in sorted(formas, key=len, reverse=True):
            padrao = re.compile(
                r"(?<!\w)" + r"\s+".join(re.escape(p) for p in forma.split(" ")) + r"(?!\w)", re.IGNORECASE
            )
            texto = padrao.sub(lambda m: self._lugar(m.group(0)), texto)
        return texto

    def _lugar(self, achado: str) -> str:
        self._lugares.append(self.marcador("PESSOA", achado))
        return chr(_BASE_DO_LUGAR + len(self._lugares) - 1)

    def _numerar(self, original: str, mascarado: str) -> str:
        pedacos = _GENERICO.split(mascarado)
        # `split` com grupo alterna: pedaço, tipo, pedaço, tipo, ..., pedaço.
        literais, tipos = pedacos[0::2], pedacos[1::2]
        if not tipos:
            return mascarado
        if not original.startswith(literais[0]):
            return mascarado
        saida = [literais[0]]
        cursor = len(literais[0])
        i = 0
        while i < len(tipos):
            # Marcadores colados (sem pedaço entre eles) viram um trecho só.
            j = i
            while j + 1 < len(tipos) and literais[j + 1] == "":
                j += 1
            seguinte = literais[j + 1]
            fim = self._fim_do_trecho(original, cursor, seguinte, tipos[i], ultimo=j + 1 == len(literais) - 1)
            if fim is None:
                return mascarado
            trecho = self._sem_lugares(original[cursor:fim])
            saida.append(self.marcador(_TIPO.get(tipos[i], tipos[i]), trecho))
            saida.append(seguinte)
            cursor = fim + len(seguinte)
            i = j + 1
        return "".join(saida) if cursor == len(original) else mascarado

    @staticmethod
    def _fim_do_trecho(original: str, cursor: int, seguinte: str, tipo: str, *, ultimo: bool) -> int | None:
        if ultimo:
            fim = len(original) - len(seguinte)
            return fim if fim > cursor and original.endswith(seguinte) else None
        candidatos = []
        inicio = cursor + 1
        while (achado := original.find(seguinte, inicio, cursor + _TRECHO_MAXIMO + len(seguinte))) != -1:
            candidatos.append(achado)
            inicio = achado + 1
        if not candidatos:
            return None
        for fim in candidatos:
            if f"[{tipo}]" in pseudonimizar(original[cursor:fim]):
                return fim
        return candidatos[0]

    def _sem_lugares(self, trecho: str) -> str:
        return _LUGARES.sub(lambda m: self.originais[self._lugares[ord(m.group(0)) - _BASE_DO_LUGAR]], trecho)

    # ── a volta ────────────────────────────────────────────────────────────

    def devolver(self, texto: str) -> str:
        """O texto do modelo com os nomes de volta."""
        return _NUMERADO.sub(lambda m: self.originais.get(m.group(0), m.group(0)), texto or "")
