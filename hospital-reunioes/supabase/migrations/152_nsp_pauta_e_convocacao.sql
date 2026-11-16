-- =====================================================
-- Migration 152: Segurança do Paciente, a pauta e a convocação das reuniões
-- (issue #1773, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra:
--   1. a pauta de cada reunião do Núcleo (`nsp_pautas`): os blocos que o
--      sistema monta, sem IA, 5 dias úteis antes da ordinária, e o que a
--      Presidência ajusta depois (quem editou e quando). Uma pauta por reunião;
--   2. quem foi convocado (`nsp_convocados`): uma linha por pessoa convocada,
--      com o estado do membro no dia da convocação, se o e-mail saiu e quem
--      convocou. A chave (reunião, pessoa) faz o segundo clique bater na
--      guarda, em vez de mandar o e-mail duas vezes.
--
-- O calendário anual não pede coluna nova: as doze ordinárias nascem em
-- `reunioes`, com o `colegiado_id` do Núcleo (migration 148).
--
-- RLS default-deny nas tabelas novas (padrão da casa): quem lê e escreve é o
-- backend com a service_role. Nenhuma policy de propósito.
-- Nenhum dado de pessoa (ADR 0095, decisão 12).
--
-- Tudo com IF NOT EXISTS: rodar duas vezes é inofensivo.
-- Aplicar à mão no Studio: o deploy não aplica SQL.
-- =====================================================

BEGIN;

-- ---------- 1. A pauta ----------
CREATE TABLE IF NOT EXISTS nsp_pautas (
  id_reuniao  VARCHAR(20) PRIMARY KEY REFERENCES reunioes(id_reuniao) ON DELETE CASCADE,
  blocos      JSONB NOT NULL CHECK (jsonb_typeof(blocos) = 'array'),
  montada_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
  editada_em  TIMESTAMPTZ,
  editada_por VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL
);

COMMENT ON TABLE nsp_pautas IS
  'Pauta de uma reunião do Núcleo de Segurança do Paciente (issue #1773): montada pelo sistema, sem IA, e ajustada pela Presidência.';
COMMENT ON COLUMN nsp_pautas.blocos IS
  'Lista de blocos {chave, titulo, sem_dados, itens: [{texto, id_acao?}]}. A situação da pendência é lida na hora, não guardada.';

CREATE INDEX IF NOT EXISTS idx_nsp_pautas_editada_por
  ON nsp_pautas(editada_por) WHERE editada_por IS NOT NULL;

ALTER TABLE nsp_pautas ENABLE ROW LEVEL SECURITY;

-- ---------- 2. Os convocados ----------
CREATE TABLE IF NOT EXISTS nsp_convocados (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  id_reuniao      VARCHAR(20) NOT NULL REFERENCES reunioes(id_reuniao) ON DELETE CASCADE,
  participante_id VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  estado          TEXT NOT NULL CHECK (estado IN ('ativo', 'a_vencer', 'em_carencia')),
  email_enviado   BOOLEAN NOT NULL DEFAULT false,
  convocado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
  convocado_por   VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  CONSTRAINT nsp_convocados_unico UNIQUE (id_reuniao, participante_id)
);

COMMENT ON TABLE nsp_convocados IS
  'Quem foi convocado para uma reunião do Núcleo (issue #1773): só quem contava para quórum no dia (Ativo, A vencer, Em carência).';

CREATE INDEX IF NOT EXISTS idx_nsp_convocados_participante
  ON nsp_convocados(participante_id);

ALTER TABLE nsp_convocados ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (152) ON CONFLICT (numero) DO NOTHING;
