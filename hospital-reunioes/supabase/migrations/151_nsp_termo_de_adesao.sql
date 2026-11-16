-- =====================================================
-- Migration 151: Segurança do Paciente, o Termo de Adesão
-- (issue #1768, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra:
--   1. a Participação ganha os carimbos de Termo gerado e enviado (o assinado
--      já existe desde a 146). O estado do membro sai deles, numa função pura
--      do backend;
--   2. o envio do Termo (`nsp_termos_envios`): uma linha por documento gerado,
--      com o envelope da assinatura eletrônica e a chave que o retorno da
--      assinatura traz. O reenvio cancela a linha anterior e cria outra;
--   3. a trilha da Participação aceita os passos do Termo e a liberação
--      manual, com o motivo;
--   4. o Termo assinado entra nos Documentos do Núcleo, uma vez por envio;
--   5. o bucket privado dos arquivos do Núcleo.
--
-- Nenhuma pessoa entra por aqui (decisão 12): a carga é pela tela.
-- RLS default-deny na tabela nova: só o backend, com a service_role, lê e grava.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. Os carimbos do Termo na Participação ----------
ALTER TABLE participacoes
  ADD COLUMN IF NOT EXISTS termo_gerado_em TIMESTAMPTZ;
ALTER TABLE participacoes
  ADD COLUMN IF NOT EXISTS termo_enviado_em TIMESTAMPTZ;

COMMENT ON COLUMN participacoes.termo_gerado_em IS
  'Quando o documento do Termo (Termo + Regimento vigente) foi gerado. Issue #1768.';
COMMENT ON COLUMN participacoes.termo_enviado_em IS
  'Quando o Termo foi enviado para a assinatura eletrônica. Issue #1768.';

-- ---------- 2. O envio do Termo ----------
CREATE TABLE IF NOT EXISTS nsp_termos_envios (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participacao_id  UUID NOT NULL REFERENCES participacoes(id) ON DELETE RESTRICT,
  regimento_id     UUID REFERENCES nsp_documentos(id) ON DELETE RESTRICT,
  situacao         TEXT NOT NULL DEFAULT 'gerado'
                   CHECK (situacao IN ('gerado', 'enviado', 'assinado', 'cancelado')),
  envelope_id      TEXT,
  documento_key    TEXT,
  arquivo_path     TEXT,
  erro             TEXT CHECK (erro IS NULL OR char_length(erro) <= 500),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  enviado_em       TIMESTAMPTZ,
  assinado_em      TIMESTAMPTZ,
  cancelado_em     TIMESTAMPTZ
);

COMMENT ON TABLE nsp_termos_envios IS
  'Cada documento do Termo de Adesão gerado para uma Participação do Núcleo (issue #1768). O id é o identificador impresso no documento. Reenviar cancela o envio aberto e cria outro.';
COMMENT ON COLUMN nsp_termos_envios.documento_key IS
  'A chave do documento na assinatura eletrônica: o retorno da assinatura chega com ela.';
COMMENT ON COLUMN nsp_termos_envios.arquivo_path IS
  'O PDF gerado (antes da assinatura) no bucket privado nsp-documentos.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_nsp_termos_envios_documento_key
  ON nsp_termos_envios (documento_key)
  WHERE documento_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_nsp_termos_envios_aberto
  ON nsp_termos_envios (participacao_id)
  WHERE situacao IN ('gerado', 'enviado');

-- O último envio da Participação (ficha, meu-termo, reconsulta) e a FK.
CREATE INDEX IF NOT EXISTS idx_nsp_termos_envios_participacao
  ON nsp_termos_envios (participacao_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_nsp_termos_envios_regimento
  ON nsp_termos_envios (regimento_id);

ALTER TABLE nsp_termos_envios ENABLE ROW LEVEL SECURITY;

-- ---------- 3. A trilha aceita o Termo e a liberação manual ----------
ALTER TABLE participacoes_trilha
  ADD COLUMN IF NOT EXISTS motivo TEXT;

ALTER TABLE participacoes_trilha DROP CONSTRAINT IF EXISTS participacoes_trilha_motivo_check;
ALTER TABLE participacoes_trilha
  ADD CONSTRAINT participacoes_trilha_motivo_check
  CHECK (motivo IS NULL OR char_length(btrim(motivo)) BETWEEN 1 AND 1000);

ALTER TABLE participacoes_trilha DROP CONSTRAINT IF EXISTS participacoes_trilha_acao_check;
ALTER TABLE participacoes_trilha
  ADD CONSTRAINT participacoes_trilha_acao_check
  CHECK (acao IN ('cadastro', 'edicao', 'renovacao', 'mudanca_de_papel', 'encerramento', 'termo_enviado', 'termo_reenviado', 'termo_assinado', 'liberacao_manual'));

COMMENT ON COLUMN participacoes_trilha.motivo IS
  'A justificativa da liberação manual do Termo (obrigatória nela). Issue #1768.';

-- ---------- 4. O Termo assinado nos Documentos ----------
ALTER TABLE nsp_documentos
  ADD COLUMN IF NOT EXISTS termo_envio_id UUID UNIQUE REFERENCES nsp_termos_envios(id) ON DELETE RESTRICT;

COMMENT ON COLUMN nsp_documentos.termo_envio_id IS
  'No Termo de Adesão assinado: o envio de onde ele veio. Único, para o retorno repetido da assinatura não duplicar o documento. Issue #1768.';

-- ---------- 5. O bucket privado do Núcleo ----------
-- Molde do `anexos-tecnologia` (migration 115): sem policy para
-- `authenticated`. O único caminho até o arquivo é a URL assinada que o
-- backend emite depois de conferir o acesso.
INSERT INTO storage.buckets (id, name, public)
VALUES ('nsp-documentos', 'nsp-documentos', false)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Authenticated Access nsp-documentos" ON storage.objects;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (151) ON CONFLICT (numero) DO NOTHING;
