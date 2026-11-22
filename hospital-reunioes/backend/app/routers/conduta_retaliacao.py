"""Canal de Conduta, a verificação de retaliação no lado do Comitê (issue
#1839, PRD #1786; especificação, 6.11 e 18).

A coordenação registra cada verificação (30, 90 e 180 dias depois do
encerramento) com um clique, houve ou não houve, e a observação se quiser.
Quando houve, abre um caso novo de retaliação. Toda rota passa pelo portão
(`app.services.conduta.portao`).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])
