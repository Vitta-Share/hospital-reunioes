-- =====================================================
-- Migration 202: o caso que a Ouvidoria sinaliza ao Canal de Conduta
-- (issue #1849, PRD #1786, ADR 0097 decisão 14)
-- =====================================================
-- O que entra:
--   1. a origem do caso do Canal: `canal` (a página pública) ou `ouvidoria`
--      (a sinalização do ouvidor). Os casos que já existem são do canal;
--   2. o vínculo do caso com a manifestação da Ouvidoria. Uma manifestação
--      vira um caso só: o índice único recusa o segundo, e a nova tentativa
--      da sinalização reusa o que ficou. Só a origem `ouvidoria` leva o
--      vínculo;
--   3. na manifestação, o carimbo de quando ela foi sinalizada. A manifestação
--      não muda de estado.
--
-- Quem manifestou não entra: o caso nasce com o relato cifrado e sem nome,
-- sem contato e sem hash de nada da pessoa. Nenhuma tabela nova e nenhuma
-- política: as colunas entram em `conduta_casos` (RLS ligado e sem política,
-- migration 175) e em `ouvidoria_protocolos`. Rodar duas vezes é inofensivo.
-- Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1 e 2. A origem e o vínculo no caso do Canal ----------
ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS origem          TEXT NOT NULL DEFAULT 'canal',
  ADD COLUMN IF NOT EXISTS manifestacao_id UUID REFERENCES ouvidoria_protocolos(id) ON DELETE RESTRICT;

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_origem_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_origem_check
  CHECK (origem IN ('canal', 'ouvidoria'));

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_vinculo_so_da_ouvidoria;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_vinculo_so_da_ouvidoria
  CHECK ((origem = 'ouvidoria') = (manifestacao_id IS NOT NULL));

-- Um caso por manifestação. O índice também serve à chave estrangeira.
CREATE UNIQUE INDEX IF NOT EXISTS uq_conduta_casos_manifestacao
  ON conduta_casos (manifestacao_id)
  WHERE manifestacao_id IS NOT NULL;

COMMENT ON COLUMN conduta_casos.origem IS
  'De onde o caso veio: canal (a página pública) ou ouvidoria (a sinalização do ouvidor). Issue #1849.';
COMMENT ON COLUMN conduta_casos.manifestacao_id IS
  'Na origem ouvidoria: a manifestação que o ouvidor sinalizou. Uma por manifestação. Issue #1849.';

-- ---------- 3. O carimbo na manifestação ----------
ALTER TABLE ouvidoria_protocolos
  ADD COLUMN IF NOT EXISTS conduta_sinalizada_em TIMESTAMPTZ;

COMMENT ON COLUMN ouvidoria_protocolos.conduta_sinalizada_em IS
  'Quando o ouvidor sinalizou o caso ao Canal de Conduta (ADR 0097, decisão 14). O estado da manifestação não muda. Issue #1849.';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (202) ON CONFLICT (numero) DO NOTHING;
