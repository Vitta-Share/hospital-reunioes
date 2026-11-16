-- =====================================================
-- Migration 153: Segurança do Paciente, presença, quórum e reunião não instalada
-- (issue #1774, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra:
--   1. a situação nova da reunião, NAO_INSTALADA: a reunião do Núcleo que não
--      teve quórum. Não aceita transcrição nem ata (as rotas só aceitam
--      PROGRAMADA);
--   2. a reunião reagendada aponta para a original (`reagendada_de`);
--   3. a presença de cada pessoa na reunião: presente, ausente, ausente
--      justificado ou convidado. Uma linha por pessoa por reunião. Fica fora de
--      `reuniao_participantes`, que é a lista de quem assina a ata.
--
-- O quórum NÃO é coluna: sai de uma função pura no backend, a partir da
-- presença e das Participações vigentes no dia da reunião.
--
-- Nenhuma pessoa entra por aqui (decisão 12).
-- RLS default-deny na tabela nova: só o backend, com a service_role, lê e grava.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. A situação NAO_INSTALADA ----------
ALTER TABLE reunioes DROP CONSTRAINT IF EXISTS reunioes_status_ata_check;
ALTER TABLE reunioes ADD CONSTRAINT reunioes_status_ata_check
  CHECK (status_ata IN (
    'PROGRAMADA',
    'PROCESSANDO',
    'ERRO',
    'ERRO_UPLOAD_TRANSCRICAO',
    'ERRO_GERACAO_PDF',
    'ERRO_ENVIO_EMAIL',
    'AGUARDANDO_RESOLUCAO',
    'AGUARDANDO_VALIDACAO',
    'AGUARDANDO_ASSINATURA',
    'ASSINADA',
    'APROVADA',
    'CANCELADA',
    'MIGRADA',
    'NAO_INSTALADA'
  ));

-- ---------- 2. A reunião reagendada ----------
ALTER TABLE reunioes
  ADD COLUMN IF NOT EXISTS reagendada_de VARCHAR(20) REFERENCES reunioes(id_reuniao) ON DELETE RESTRICT;

COMMENT ON COLUMN reunioes.reagendada_de IS
  'A reunião não instalada que esta reagenda (issue #1774). Nulo = reunião original.';

CREATE INDEX IF NOT EXISTS idx_reunioes_reagendada_de
  ON reunioes(reagendada_de) WHERE reagendada_de IS NOT NULL;

-- ---------- 3. A presença ----------
CREATE TABLE IF NOT EXISTS reuniao_presencas (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  id_reuniao       VARCHAR(20) NOT NULL REFERENCES reunioes(id_reuniao) ON DELETE CASCADE,
  participante_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  situacao         TEXT NOT NULL CHECK (situacao IN ('presente', 'ausente', 'ausente_justificado', 'convidado')),
  registrada_por   VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_reuniao_presencas_pessoa UNIQUE (id_reuniao, participante_id)
);

COMMENT ON TABLE reuniao_presencas IS
  'Presença de cada pessoa numa reunião do Núcleo (issue #1774): presente, ausente, ausente justificado ou convidado. Base do quórum e do bloco de presenças da ata.';

CREATE INDEX IF NOT EXISTS idx_reuniao_presencas_participante
  ON reuniao_presencas (participante_id);
CREATE INDEX IF NOT EXISTS idx_reuniao_presencas_registrada_por
  ON reuniao_presencas (registrada_por);

ALTER TABLE reuniao_presencas ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (153) ON CONFLICT (numero) DO NOTHING;
