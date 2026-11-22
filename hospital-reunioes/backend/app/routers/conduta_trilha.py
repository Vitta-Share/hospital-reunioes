"""Canal de Conduta, a trilha do caso e o Dossiê (issue #1837, PRD #1786;
especificação, seções 9.1 e 9.2; ADR 0097, decisões 2 e 9).

"BAIXAR DOSSIÊ": o pacote do caso inteiro, decifrado, só para os membros do
Comitê no caso. Toda rota passa pelo portão (`app.services.conduta.portao`), e
o download entra na trilha antes de o pacote sair.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])
