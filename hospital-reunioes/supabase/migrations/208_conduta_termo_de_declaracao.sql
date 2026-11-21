-- =====================================================
-- Migration 208: Canal de Conduta, o termo de declaração redigido pelo agente
-- (issue #1831, PRD #1786, ADR 0097, decisão 7; especificação, 7.1 e Anexos C
-- e E.1)
-- =====================================================
-- O que entra:
--   1. as versões do termo de declaração de cada depoimento: o termo (cifrado
--      pela aplicação, já com os nomes de volta) e as "Notas para quem apura"
--      (cifradas, nunca impressas). A primeira versão sai do agente; cada
--      correção lançada é uma versão nova, e a anterior fica. Versão guardada
--      não se altera nem se apaga, e depoimento concluído não recebe versão;
--   2. o roteiro de perguntas sugerido pelo agente, cifrado, no cartão do
--      depoimento;
--   3. a certidão de recusa de assinatura ligada ao depoimento, na tabela das
--      assinaturas do Canal (migration 192).
--
-- RLS default-deny na tabela nova: só o backend, com a service_role, lê e
-- grava. Nenhuma policy de propósito. Nenhum dado de pessoa entra aqui.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. As versões do termo ----------
CREATE TABLE IF NOT EXISTS conduta_depoimento_termos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  depoimento_id   UUID NOT NULL REFERENCES conduta_depoimentos(id) ON DELETE RESTRICT,
  versao          INTEGER NOT NULL CHECK (versao >= 1),
  -- 'agente': redigido pelo agente depois do clique; 'correcao': correção
  -- lançada por quem conduziu.
  origem          TEXT NOT NULL CHECK (origem IN ('agente', 'correcao')),
  termo_cifrado   TEXT NOT NULL CHECK (termo_cifrado LIKE 'v1:%'),
  notas_cifradas  TEXT CHECK (notas_cifradas IS NULL OR notas_cifradas LIKE 'v1:%'),
  criado_por      VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (depoimento_id, versao)
);

COMMENT ON TABLE conduta_depoimento_termos IS
  'Versões do termo de declaração do depoimento do Canal de Conduta (issue #1831): termo e Notas para quem apura cifrados pela aplicação. Imutável: a correção é uma versão nova.';

CREATE INDEX IF NOT EXISTS idx_conduta_depoimento_termos_criado_por ON conduta_depoimento_termos (criado_por);

ALTER TABLE conduta_depoimento_termos ENABLE ROW LEVEL SECURITY;

-- As funções são as da migration 193: registro guardado não muda, e
-- depoimento concluído não recebe mais nada.
DROP TRIGGER IF EXISTS trg_conduta_depoimento_termos_imutavel ON conduta_depoimento_termos;
CREATE TRIGGER trg_conduta_depoimento_termos_imutavel
  BEFORE UPDATE OR DELETE ON conduta_depoimento_termos
  FOR EACH ROW EXECUTE FUNCTION conduta_depoimento_registro_imutavel();

DROP TRIGGER IF EXISTS trg_conduta_depoimento_termos_em_aberto ON conduta_depoimento_termos;
CREATE TRIGGER trg_conduta_depoimento_termos_em_aberto
  BEFORE INSERT ON conduta_depoimento_termos
  FOR EACH ROW EXECUTE FUNCTION conduta_depoimento_em_aberto();

-- ---------- 2. O roteiro de perguntas ----------
ALTER TABLE conduta_depoimentos
  ADD COLUMN IF NOT EXISTS roteiro_cifrado TEXT,
  ADD COLUMN IF NOT EXISTS roteiro_em      TIMESTAMPTZ;

ALTER TABLE conduta_depoimentos DROP CONSTRAINT IF EXISTS conduta_depoimentos_roteiro_check;
ALTER TABLE conduta_depoimentos
  ADD CONSTRAINT conduta_depoimentos_roteiro_check CHECK (
    (roteiro_cifrado IS NULL AND roteiro_em IS NULL)
    OR (roteiro_cifrado LIKE 'v1:%' AND roteiro_em IS NOT NULL)
  );

-- ---------- 3. A certidão de recusa, ligada ao depoimento ----------
ALTER TABLE conduta_assinaturas
  ADD COLUMN IF NOT EXISTS depoimento_id UUID REFERENCES conduta_depoimentos(id) ON DELETE RESTRICT;

ALTER TABLE conduta_assinaturas DROP CONSTRAINT IF EXISTS conduta_assinaturas_certidao_do_depoimento;
ALTER TABLE conduta_assinaturas
  ADD CONSTRAINT conduta_assinaturas_certidao_do_depoimento CHECK (
    tipo <> 'certidao_de_recusa' OR (depoimento_id IS NOT NULL AND caso_id IS NOT NULL)
  );

CREATE INDEX IF NOT EXISTS idx_conduta_assinaturas_depoimento
  ON conduta_assinaturas (depoimento_id);

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (208) ON CONFLICT (numero) DO NOTHING;
