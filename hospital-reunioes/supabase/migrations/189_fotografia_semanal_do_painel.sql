-- =====================================================
-- Migration 189: Fotografia semanal do painel de Reunioes (PRD #1757; issue #1873)
-- =====================================================
-- O job de segunda grava os cards do painel de cada pessoa que ve o painel,
-- uma linha por pessoa e por semana (a segunda-feira da semana, no fuso de Sao
-- Paulo). A tabela alimenta a evolucao das atrasadas nas ultimas 8 semanas e a
-- seta dos cards, que compara com a semana anterior. Nada e recalculado do
-- historico: a semana sem fotografia nao aparece (ADR 0098, decisao 10).
--
-- A chave (participante_id, semana) garante uma fotografia so por semana: o
-- job grava com `ON CONFLICT DO NOTHING`, e rodar duas vezes nao muda nada.
--
-- So o backend (service_role) le e grava: RLS default-deny, sem policy.
-- Rodar duas vezes e inofensivo. Aplicar a mao no Studio.
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS painel_fotografias (
  participante_id      VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE CASCADE,
  semana               DATE        NOT NULL CHECK (EXTRACT(ISODOW FROM semana) = 1),
  atas_paradas         INTEGER     NOT NULL DEFAULT 0,
  aguardam_assinatura  INTEGER     NOT NULL DEFAULT 0,
  atrasadas            INTEGER     NOT NULL DEFAULT 0,
  vencem_em_3_dias     INTEGER     NOT NULL DEFAULT 0,
  conformidade         INTEGER     NOT NULL DEFAULT 100 CHECK (conformidade BETWEEN 0 AND 100),
  ativas               INTEGER     NOT NULL DEFAULT 0,
  fotografada_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (participante_id, semana)
);

-- O job procura quem ja foi fotografado na semana.
CREATE INDEX IF NOT EXISTS idx_painel_fotografias_semana ON painel_fotografias (semana);

ALTER TABLE painel_fotografias ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (189) ON CONFLICT (numero) DO NOTHING;
