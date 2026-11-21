-- =====================================================
-- Migration 176: Contas medicas, arquivar por Competencia
-- (issue #1958, PRD #1933, ADR 0105 decisoes 6 a 10)
-- =====================================================
-- Arquivar e um carimbo, nao uma situacao (decisao 7): a Conta Concluida ou
-- Concluida com pendencia ganha a data e a pessoa que arquivou, e a
-- `situacao` fica como esta. Painel, Retorno e reenvio continuam lendo a
-- situacao. Desarquivar e o Retorno da Validacao limpam o carimbo.
--
-- O que entra, em `cm_conta`:
--   1. `arquivada_em`: quando a conta foi arquivada. Nula na conta que nao
--      foi arquivada;
--   2. `arquivada_por`: quem arquivou. Com a pessoa apagada, fica nula e a
--      conta segue arquivada (ON DELETE SET NULL, como o `faturista_id`);
--   3. um indice parcial das Concluidas nao arquivadas, que e o que a etapa
--      Concluidas le, na ordem de envio.
--
-- So acrescenta: colunas nulas e sem DEFAULT, o backend de antes segue
-- funcionando entre a aplicacao e a subida. Sem tabela nova, sem policy
-- nova: `cm_conta` tem RLS default-deny desde a 116 (quem le e escreve e o
-- backend com a service_role).
--
-- Tudo com IF NOT EXISTS: rodar duas vezes e inofensivo. Aplicar a mao no
-- Studio ANTES da subida: o deploy nao aplica SQL, e o backend novo le e
-- grava as colunas do carimbo.
-- =====================================================

ALTER TABLE cm_conta
  ADD COLUMN IF NOT EXISTS arquivada_em TIMESTAMPTZ;

ALTER TABLE cm_conta
  ADD COLUMN IF NOT EXISTS arquivada_por VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL;

COMMENT ON COLUMN cm_conta.arquivada_em IS
  'Quando a conta concluida foi arquivada (issue #1958, ADR 0105). Nula na nao arquivada. Nao e situacao: a situacao fica como estava.';
COMMENT ON COLUMN cm_conta.arquivada_por IS
  'Quem arquivou a conta. Nula na nao arquivada e quando a pessoa foi apagada.';

CREATE INDEX IF NOT EXISTS idx_cm_conta_concluidas_nao_arquivadas
  ON cm_conta (situacao, ordem_fila)
  WHERE arquivada_em IS NULL;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (176) ON CONFLICT (numero) DO NOTHING;
