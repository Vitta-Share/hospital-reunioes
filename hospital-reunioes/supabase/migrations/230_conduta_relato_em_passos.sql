-- =====================================================
-- Migration 230: Canal de Conduta, o relato em passos
-- (issue #1843, PRD #1786, ADR 0097, decisões 1, 8 e 10)
-- =====================================================
-- O que entra no caso que chega pela página pública:
--   1. o nome de quem relata com identificação, cifrado pela aplicação, fora
--      do relato (o relato vai ao agente; o nome nunca vai, decisão 7);
--   2. a ciência do passo 1: o momento e a versão de cada aviso aceito, sem
--      identidade nenhuma;
--   3. a resposta à pergunta de confiança no canal, de 1 a 5, opcional.
--
-- Só colunas novas numa tabela que já tem RLS default-deny (migration 175):
-- quem lê e grava continua sendo só o backend, com a service_role.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS relator_nome_cifrado TEXT,
  ADD COLUMN IF NOT EXISTS ciencia_em           TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS ciencia_versoes      JSONB,
  ADD COLUMN IF NOT EXISTS confianca            SMALLINT;

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_relator_nome_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_relator_nome_check
  CHECK (relator_nome_cifrado IS NULL OR relator_nome_cifrado LIKE 'v1:%');

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_ciencia_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_ciencia_check
  CHECK ((ciencia_em IS NULL) = (ciencia_versoes IS NULL));

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_confianca_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_confianca_check
  CHECK (confianca IS NULL OR confianca BETWEEN 1 AND 5);

COMMENT ON COLUMN conduta_casos.relator_nome_cifrado IS
  'Nome de quem relatou com identificação, cifrado pela aplicação. Nulo no relato anônimo. Issue #1843.';
COMMENT ON COLUMN conduta_casos.ciencia_em IS
  'Quando a pessoa marcou a caixa de ciência do passo 1. Sem identidade. Issue #1843.';
COMMENT ON COLUMN conduta_casos.ciencia_versoes IS
  'Versão de cada aviso do passo 1 que a pessoa leu (nulo = o texto padrão da página). Issue #1843.';
COMMENT ON COLUMN conduta_casos.confianca IS
  'Resposta opcional de 1 a 5 a "quanto você confia neste canal?", dada na tela do protocolo. Issue #1843.';

COMMIT;

-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (230) ON CONFLICT (numero) DO NOTHING;
