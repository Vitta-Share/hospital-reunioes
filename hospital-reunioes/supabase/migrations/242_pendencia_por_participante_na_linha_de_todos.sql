-- =====================================================
-- Migration 242: uma Pendência e uma Rotina por Participante na linha do
-- quadro dirigida a "Todos os participantes" (issue #2327)
-- =====================================================
-- A chave única da Pendência (057) e da Rotina (177) era a posição no quadro:
-- uma por linha. A linha de "Todos os participantes" agora nasce uma para
-- cada Participante da Reunião, todas na mesma posição, então a chave passa a
-- ser posição + responsável. A linha sem vínculo continua uma só: o
-- COALESCE trata o responsável vazio como um valor, e o NULL não escapa da
-- unicidade.
--
-- Só troca índice; nenhuma linha muda. A chave nova nasce antes de a antiga
-- sair, na mesma transação. RLS segue como está (tabelas já existentes).
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. Pendência ----------
CREATE UNIQUE INDEX IF NOT EXISTS ux_pendencias_reuniao_quadro_pos_responsavel
  ON pendencias (id_reuniao, quadro_pos, COALESCE(responsavel_id, ''))
  WHERE quadro_pos IS NOT NULL;

DROP INDEX IF EXISTS ux_pendencias_reuniao_quadro_pos;

-- ---------- 2. Rotina ----------
CREATE UNIQUE INDEX IF NOT EXISTS ux_rotinas_reuniao_quadro_pos_responsavel
  ON rotinas (id_reuniao, quadro_pos, COALESCE(responsavel_id, ''));

ALTER TABLE rotinas DROP CONSTRAINT IF EXISTS rotinas_id_reuniao_quadro_pos_key;

COMMIT;

-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (242) ON CONFLICT (numero) DO NOTHING;
