-- =====================================================
-- Migration 212: o suplente em exercício do Núcleo
-- (issue #1999, PRD #1979, ADR 0107, decisão 4)
-- =====================================================
-- O que entra:
--   1. a ausência da Presidência: o início e o fim do período em que o
--      suplente responde pela Presidência, presa à Participação do suplente,
--      com quem registrou e quando. Só cresce: o banco recusa UPDATE e
--      DELETE, como a trilha da Participação;
--   2. a trilha da Participação aceita a ação "ausencia_da_presidencia".
--
-- Dentro do período, a permissão do módulo dá ao suplente os recursos da
-- Presidência. A regra mora no backend; aqui só o registro.
--
-- Nenhuma pessoa entra por aqui. RLS ligado e sem política na tabela nova:
-- só o backend, com a service_role, lê e grava. Rodar duas vezes é
-- inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. A ausência da Presidência ----------
CREATE TABLE IF NOT EXISTS nsp_ausencias_da_presidencia (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participacao_id  UUID NOT NULL REFERENCES participacoes(id) ON DELETE RESTRICT,
  inicio           DATE NOT NULL,
  fim              DATE NOT NULL,
  autor_id         VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (fim >= inicio)
);

COMMENT ON TABLE nsp_ausencias_da_presidencia IS
  'O período em que o suplente do Núcleo responde pela Presidência (ADR 0107, decisão 4). Issue #1999. Imutável: o banco recusa UPDATE e DELETE.';
COMMENT ON COLUMN nsp_ausencias_da_presidencia.participacao_id IS
  'A Participação do suplente que fica em exercício no período.';

CREATE INDEX IF NOT EXISTS idx_nsp_ausencias_da_presidencia_participacao
  ON nsp_ausencias_da_presidencia (participacao_id, inicio, fim);
CREATE INDEX IF NOT EXISTS idx_nsp_ausencias_da_presidencia_autor
  ON nsp_ausencias_da_presidencia (autor_id);

ALTER TABLE nsp_ausencias_da_presidencia ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION nsp_ausencias_da_presidencia_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'A ausência da Presidência registrada não muda: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_ausencias_da_presidencia_imutavel ON nsp_ausencias_da_presidencia;
CREATE TRIGGER trg_nsp_ausencias_da_presidencia_imutavel
  BEFORE UPDATE OR DELETE ON nsp_ausencias_da_presidencia
  FOR EACH ROW EXECUTE FUNCTION nsp_ausencias_da_presidencia_imutavel();

-- ---------- 2. A trilha aceita a ausência ----------
ALTER TABLE participacoes_trilha DROP CONSTRAINT IF EXISTS participacoes_trilha_acao_check;
ALTER TABLE participacoes_trilha
  ADD CONSTRAINT participacoes_trilha_acao_check
  CHECK (acao IN ('cadastro', 'edicao', 'renovacao', 'mudanca_de_papel', 'encerramento', 'termo_enviado', 'termo_reenviado', 'termo_assinado', 'liberacao_manual', 'ausencia_da_presidencia'));

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (212) ON CONFLICT (numero) DO NOTHING;
