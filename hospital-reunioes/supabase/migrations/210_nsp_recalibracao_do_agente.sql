-- =====================================================
-- Migration 210: a recalibração do agente do Núcleo
-- (issue #2001, PRD #1979, ADR 0107 decisão 10; Anexo F, seções 4, 5 e 7)
-- =====================================================
-- O que entra: uma linha por marco da recalibração (30 e 60 dias da primeira
-- notificação registrada). O job diário, sem IA, grava a linha quando o marco
-- chega, com as Pendências "Recalibrar o agente do NSP" que nasceram para quem
-- tem Acesso pleno. A chave é o marco: cada um nasce uma vez só. Concluir a
-- pendência grava a decisão (manter, ajustar ou ligar a aprovação em lote),
-- quem decidiu e quando, e a decisão não muda depois.
--
-- Nenhuma pessoa entra por aqui. RLS ligado e sem política: só o backend, com
-- a service_role, lê e grava. Rodar duas vezes é inofensivo. Aplicar à mão no
-- Studio.
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS nsp_recalibracoes (
  marco         SMALLINT PRIMARY KEY CHECK (marco IN (30, 60)),
  devida_em     DATE NOT NULL,
  pendencias    TEXT[] NOT NULL DEFAULT '{}',
  criada_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
  decisao       TEXT CHECK (decisao IN ('manter', 'ajustar', 'ligar_lote')),
  decidido_por  VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  decidido_em   TIMESTAMPTZ,
  CHECK ((decisao IS NULL) = (decidido_por IS NULL) AND (decisao IS NULL) = (decidido_em IS NULL))
);

COMMENT ON TABLE nsp_recalibracoes IS
  'A recalibração do agente de triagem do Núcleo aos 30 e aos 60 dias da primeira notificação (Anexo F, seção 7). Uma linha por marco. Issue #2001.';
COMMENT ON COLUMN nsp_recalibracoes.pendencias IS
  'Os id_acao das Pendências sem Reunião "Recalibrar o agente do NSP", uma por pessoa com Acesso pleno.';
COMMENT ON COLUMN nsp_recalibracoes.decisao IS
  'A decisão da Diretoria ao concluir: manter, ajustar ou ligar_lote (ligar a aprovação em lote).';

CREATE INDEX IF NOT EXISTS idx_nsp_recalibracoes_decidido_por ON nsp_recalibracoes (decidido_por);

ALTER TABLE nsp_recalibracoes ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (210) ON CONFLICT (numero) DO NOTHING;
