-- =====================================================
-- Migration 183: o caso que a Ouvidoria manda ao Núcleo vira notificação
-- (issue #1997, PRD #1979, ADR 0107 decisão 7)
-- =====================================================
-- O que entra:
--   1. o vínculo da notificação com a manifestação da Ouvidoria. Um caso da
--      Ouvidoria vira uma notificação só: o índice único recusa a segunda, e
--      a nova tentativa do envio reusa a que ficou. Só a origem `ouvidoria`
--      leva o vínculo;
--   2. a justificativa técnica que a Ouvidoria escreveu para o Núcleo.
--
-- Quem manifestou não entra: a notificação de origem Ouvidoria nasce sem
-- nome, sem contato e sem hash de código. Nenhuma tabela nova e nenhuma
-- política: as colunas entram em `nsp_notificacoes`, que já tem RLS ligado e
-- sem política (migration 174). Rodar duas vezes é inofensivo. Aplicar à mão
-- no Studio.
-- =====================================================

BEGIN;

ALTER TABLE nsp_notificacoes
  ADD COLUMN IF NOT EXISTS manifestacao_id UUID REFERENCES ouvidoria_protocolos(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS justificativa_tecnica TEXT;

ALTER TABLE nsp_notificacoes DROP CONSTRAINT IF EXISTS nsp_notificacoes_justificativa_tecnica_tamanho;
ALTER TABLE nsp_notificacoes
  ADD CONSTRAINT nsp_notificacoes_justificativa_tecnica_tamanho
  CHECK (justificativa_tecnica IS NULL OR char_length(justificativa_tecnica) <= 10000);

ALTER TABLE nsp_notificacoes DROP CONSTRAINT IF EXISTS nsp_notificacoes_vinculo_so_da_ouvidoria;
ALTER TABLE nsp_notificacoes
  ADD CONSTRAINT nsp_notificacoes_vinculo_so_da_ouvidoria
  CHECK (manifestacao_id IS NULL OR origem = 'ouvidoria');

-- Uma notificação por manifestação. O índice também serve à chave estrangeira.
CREATE UNIQUE INDEX IF NOT EXISTS uq_nsp_notificacoes_manifestacao
  ON nsp_notificacoes (manifestacao_id)
  WHERE manifestacao_id IS NOT NULL;

COMMENT ON COLUMN nsp_notificacoes.manifestacao_id IS
  'A manifestação da Ouvidoria que virou esta notificação (origem ouvidoria). Uma por manifestação. Issue #1997.';
COMMENT ON COLUMN nsp_notificacoes.justificativa_tecnica IS
  'Na origem ouvidoria: o que a Ouvidoria apurou para o Núcleo, copiado no envio. Issue #1997.';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (183) ON CONFLICT (numero) DO NOTHING;
