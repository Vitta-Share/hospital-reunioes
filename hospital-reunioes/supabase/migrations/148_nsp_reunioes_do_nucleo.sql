-- =====================================================
-- Migration 148: as reuniões do Núcleo de Segurança do Paciente
-- (issue #1772, PRD #1764, ADR 0095, decisões 3 e 4)
-- =====================================================
-- O que entra:
--   1. a reunião ganha o vínculo com o Colegiado (`colegiado_id`). Nulo é a
--      reunião de sempre; preenchido é reunião do Colegiado, que só quem o
--      módulo libera vê (o sigilo é do backend, ADR 0095, decisão 4);
--   2. o tipo da reunião aceita os quatro tipos do Núcleo, além dos de antes;
--   3. tipo do Núcleo só existe com o Colegiado, e reunião do Colegiado só
--      existe com um tipo do Núcleo.
--
-- Nenhuma tabela nova: a RLS de `reunioes` (migration 009) continua valendo.
-- Nenhum dado de pessoa (decisão 12).
--
-- Tudo com IF NOT EXISTS / DROP antes de ADD: rodar duas vezes é inofensivo.
-- Aplicar à mão no Studio: o deploy não aplica SQL.
-- =====================================================

BEGIN;

-- ---------- 1. O vínculo com o Colegiado ----------
ALTER TABLE reunioes
  ADD COLUMN IF NOT EXISTS colegiado_id UUID REFERENCES colegiados(id) ON DELETE RESTRICT;

COMMENT ON COLUMN reunioes.colegiado_id IS
  'Colegiado dono da reunião (ADR 0095). Nulo = reunião comum. Preenchido = reunião do Colegiado, escondida de quem o módulo não libera, inclusive do super admin.';

-- O sigilo procura as reuniões do Colegiado em toda leitura de reunião.
CREATE INDEX IF NOT EXISTS idx_reunioes_colegiado
  ON reunioes(colegiado_id) WHERE colegiado_id IS NOT NULL;

-- ---------- 2. Os quatro tipos do Núcleo ----------
ALTER TABLE reunioes DROP CONSTRAINT IF EXISTS reunioes_tipo_check;
ALTER TABLE reunioes
  ADD CONSTRAINT reunioes_tipo_check
  CHECK (tipo IN (
    'Diretoria', 'Gerencial', 'Coordenação', 'Mensal', 'Extraordinária',
    'Ordinária mensal', 'Análise de evento', 'Apresentação à Diretoria', 'Reunião rápida de segurança'
  ));

-- ---------- 3. Tipo do Núcleo e Colegiado andam juntos ----------
ALTER TABLE reunioes DROP CONSTRAINT IF EXISTS reunioes_tipo_do_nucleo_check;
ALTER TABLE reunioes
  ADD CONSTRAINT reunioes_tipo_do_nucleo_check
  CHECK (
    tipo IS NULL
    OR tipo NOT IN ('Ordinária mensal', 'Análise de evento', 'Apresentação à Diretoria', 'Reunião rápida de segurança')
    OR colegiado_id IS NOT NULL
  );

ALTER TABLE reunioes DROP CONSTRAINT IF EXISTS reunioes_colegiado_com_tipo_check;
ALTER TABLE reunioes
  ADD CONSTRAINT reunioes_colegiado_com_tipo_check
  CHECK (
    colegiado_id IS NULL
    OR tipo IN ('Ordinária mensal', 'Análise de evento', 'Apresentação à Diretoria', 'Reunião rápida de segurança')
  );

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (148) ON CONFLICT (numero) DO NOTHING;
