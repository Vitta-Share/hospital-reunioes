"""A tabela de prazos do Núcleo, na Configuração (issue #1993, PRD #1979,
ADR 0107 decisão 2).

- `GET /nsp/configuracao/prazos`: os prazos internos (faixa e marco), os
  legais (só leitura) e o histórico das alterações;
- `PUT /nsp/configuracao/prazos/{faixa}/{marco}`: muda um prazo interno. Só a
  Presidência e o Acesso pleno (o recurso `tabela_de_prazos`); o prazo legal é
  recusado.

A alteração não alcança caso já classificado: o caso guarda os vencimentos do
dia da confirmação.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])
