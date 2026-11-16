"""A convocação das reuniões do Núcleo (issue #1773, PRD #1764).

Um clique da Presidência manda o e-mail nominal a cada membro que conta para
quórum (Ativo, A vencer e Em carência, pela função pura de `membros`), com a
data e a hora absolutas, e grava quem foi convocado. O e-mail só traz a data,
a hora, o tipo e o link: o conteúdo do Núcleo fica na tela.
"""

from __future__ import annotations

from app.services.email_service import _enviar_email  # noqa: F401
