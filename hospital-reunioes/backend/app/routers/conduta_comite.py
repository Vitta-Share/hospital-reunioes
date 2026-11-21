"""Canal de Conduta, o lado do Comitê (issue #1820, PRD #1786, ADR 0097).

A rota mínima da fundação: a lista dos casos que a pessoa abre e a abertura de
um caso. A área logada fica em `/comite-de-conduta`, fora de `/conduta`, que é
a rota pública. Toda rota daqui passa pelo portão (`app.services.conduta.portao`).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.services.conduta import cifra
from app.services.conduta.acesso import CAMPOS_DA_LISTA
from app.services.conduta.portao import INDISPONIVEL, portao_da_lista, portao_do_caso

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


@router.get("/casos")
async def listar_casos(casos: list[dict] = Depends(portao_da_lista)) -> dict:
    return {"casos": casos}


@router.get("/casos/{caso_id}")
async def abrir_caso(caso: dict = Depends(portao_do_caso)) -> dict:
    try:
        relato = cifra.decifrar_texto(caso["relato_cifrado"])
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro
    return {**{campo: caso.get(campo) for campo in CAMPOS_DA_LISTA}, "relato": relato}
