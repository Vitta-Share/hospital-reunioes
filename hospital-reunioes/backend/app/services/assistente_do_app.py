"""O Assistente do app: a dúvida de uso respondida pelo robô do canto da tela
(issue #2267, ADR 0113, decisão 8).

Responde pelo Kit de conhecimento e pelas páginas do Manual dos módulos que a
pessoa acessa. Quem escolhe as páginas é a tela, pela mesma conta que o Manual
faz pelo menu (`paginasVisiveis`, no frontend): as páginas moram em
`frontend/public/manual/`, fora da imagem do backend.

Uma chamada simples, sem ferramenta: o assistente não lê o código nem o
GitHub, e a conversa não grava nada (não vira Demanda).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.services.ia_chaves import ClienteDaAnthropic
from app.services.modelo_dos_agentes import MODELO_DOS_AGENTES_DO_APP
from app.utils.text_sanitizer import sanitizar_travessao

MAX_TOKENS = 2048
TEMPO_LIMITE_S = 90.0

PROMPT = (
    "Você é o Assistente do aplicativo do Hospital São Matheus. Responde dúvidas de uso do aplicativo: "
    "como uma tela funciona, onde fica um botão, como fazer uma tarefa.\n\n"
    "Regras:\n"
    "- Responda só com o que está no material abaixo: as páginas do Manual que esta pessoa vê e o Kit de "
    "conhecimento. Se o material não responde, diga que não sabe e sugira procurar a equipe de Tecnologia.\n"
    "- Diga de onde tirou a resposta, pelo título da página do Manual ou pelo nome do arquivo do Kit.\n"
    "- Fale só dos módulos que aparecem nas páginas do Manual abaixo.\n"
    "- Você não planeja melhoria, não abre pedido e não muda nada no aplicativo.\n"
    "- Escreva em português do Brasil, em frases curtas, sem termos de programador. "
    "Nunca use travessão nem meia-risca."
)


@dataclass(frozen=True)
class PaginaDoManual:
    modulo: str
    titulo: str
    corpo: str


def _cliente() -> ClienteDaAnthropic | None:
    """O cliente da Anthropic, ou None sem chave (ambiente local e CI)."""
    if not settings.anthropic_api_key:
        return None
    return ClienteDaAnthropic(max_retries=1, timeout=TEMPO_LIMITE_S)


def material(kit: str, paginas: list[PaginaDoManual]) -> str:
    """O Kit e as páginas do Manual num texto só, com o título de cada página
    como cabeçalho, que é por onde o assistente cita a fonte."""
    manual = "\n\n".join(f"## Manual: {p.titulo}\n\n{p.corpo.strip()}" for p in paginas)
    return f"# Páginas do Manual que esta pessoa vê\n\n{manual or '(nenhuma)'}\n\n# Kit de conhecimento\n\n{kit}"


def responder_a_duvida(cliente, *, mensagens: list[dict], paginas: list[PaginaDoManual], kit: str) -> str:
    """Um turno da conversa. Sem estado: a conversa inteira chega por parâmetro."""
    resposta = cliente.messages.create(
        model=MODELO_DOS_AGENTES_DO_APP,
        max_tokens=MAX_TOKENS,
        system=[
            {"type": "text", "text": PROMPT},
            {"type": "text", "text": material(kit, paginas), "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": m["role"], "content": m["content"]} for m in mensagens],
    )
    texto = "".join(bloco.text for bloco in resposta.content if getattr(bloco, "type", "") == "text")
    return sanitizar_travessao(texto.strip())
