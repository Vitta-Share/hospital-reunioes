-- =====================================================
-- Migration 214: Canal de Conduta, a Rota Especial
-- (issue #1829, PRD #1786, ADR 0097; especificação, seção 10)
-- =====================================================
-- O que entra:
--   1. no caso, a resposta do passo 3 sobre a Direção (sim, nao, nao_sei), o
--      sinal do agente e quem confirmou o desvio da fila comum, e quando;
--   2. o desfecho `parecer_entregue`, o encerramento da Rota Especial;
--   3. o registro selado: o relato gravado na entrada da Rota Especial, com
--      data, hora e código de integridade. Nenhum perfil altera nem apaga;
--   4. a entrega do parecer, feita fora do aplicativo: a quem (cifrado) e em
--      que data. Uma por caso, e não se altera nem se apaga;
--   5. os avisos de 15, 30 e 60 dias ao grupo, como motivos novos do aviso.
--
-- O grupo da Rota Especial não ganha tabela: ele fica nas atribuições do caso
-- (`grupo_especial`, migration 175), gravadas na entrada.
--
-- RLS default-deny em toda tabela nova: só o backend, com a service_role, lê
-- e grava. Nenhuma policy de propósito. Nenhum dado de pessoa em claro.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. A Direção, o sinal e o desvio ----------
ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS direcao_envolvida  TEXT,
  ADD COLUMN IF NOT EXISTS sinal_especial     BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS desviado_por       VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS desviado_em        TIMESTAMPTZ;

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_direcao_envolvida_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_direcao_envolvida_check
  CHECK (direcao_envolvida IS NULL OR direcao_envolvida IN ('sim', 'nao', 'nao_sei'));

COMMENT ON COLUMN conduta_casos.direcao_envolvida IS
  'Passo 3: o relato envolve a Direção, a Presidência ou a família proprietária? sim = nasce na Rota Especial; nao_sei = fila comum com o aviso (issue #1829).';
COMMENT ON COLUMN conduta_casos.sinal_especial IS
  'O agente de triagem sugeriu a Rota Especial: o caso da fila comum mostra o aviso, e um membro confirma o desvio (issue #1829).';

CREATE INDEX IF NOT EXISTS idx_conduta_casos_desviado_por ON conduta_casos (desviado_por);

-- O Completo prorrogado na fila comum ainda se desvia: a prorrogação gravada
-- não muda (trigger da 185) e o rito passa a especial. Só o caso desviado leva
-- a prorrogação para a Rota Especial; o que nasce nela não prorroga.
ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_prorrogacao_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_prorrogacao_check
  CHECK (
    prorrogado_em IS NULL
    OR (
      prorrogacao_cifrada LIKE 'v1:%'
      AND (rito = 'completo' OR (rito = 'especial' AND desviado_em IS NOT NULL))
    )
  );

-- ---------- 2. O desfecho da Rota Especial ----------
ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_desfecho_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_desfecho_check
  CHECK (desfecho IS NULL OR desfecho IN ('encaminhado', 'parecer_entregue'));

-- ---------- 3. O registro selado ----------
CREATE TABLE IF NOT EXISTS conduta_selos (
  caso_id         UUID PRIMARY KEY REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  relato_cifrado  TEXT NOT NULL CHECK (relato_cifrado LIKE 'v1:%'),
  selado_em       TIMESTAMPTZ NOT NULL,
  codigo          TEXT NOT NULL CHECK (codigo ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE conduta_selos IS
  'Registro selado da Rota Especial (issue #1829): o relato na entrada, com data, hora e código de integridade. Imutável.';

ALTER TABLE conduta_selos ENABLE ROW LEVEL SECURITY;

-- ---------- 4. A entrega do parecer ----------
CREATE TABLE IF NOT EXISTS conduta_entregas_do_parecer (
  caso_id               UUID PRIMARY KEY REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  destinatario_cifrado  TEXT NOT NULL CHECK (destinatario_cifrado LIKE 'v1:%'),
  entregue_em           DATE NOT NULL,
  autor_id              VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  registrado_em         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE conduta_entregas_do_parecer IS
  'O Grupo Especial entregou o parecer fora do aplicativo: a quem (cifrado) e em que data (issue #1829). Uma por caso. Imutável.';

CREATE INDEX IF NOT EXISTS idx_conduta_entregas_do_parecer_autor ON conduta_entregas_do_parecer (autor_id);

ALTER TABLE conduta_entregas_do_parecer ENABLE ROW LEVEL SECURITY;

-- Nenhum perfil altera nem apaga o selo ou a entrega, nem a service_role.
CREATE OR REPLACE FUNCTION conduta_rota_especial_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'O registro da Rota Especial é imutável: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_selos_imutavel ON conduta_selos;
CREATE TRIGGER trg_conduta_selos_imutavel
  BEFORE UPDATE OR DELETE ON conduta_selos
  FOR EACH ROW EXECUTE FUNCTION conduta_rota_especial_imutavel();

DROP TRIGGER IF EXISTS trg_conduta_entregas_do_parecer_imutavel ON conduta_entregas_do_parecer;
CREATE TRIGGER trg_conduta_entregas_do_parecer_imutavel
  BEFORE UPDATE OR DELETE ON conduta_entregas_do_parecer
  FOR EACH ROW EXECUTE FUNCTION conduta_rota_especial_imutavel();

-- ---------- 5. Os marcos de 15, 30 e 60 dias ----------
ALTER TABLE conduta_avisos DROP CONSTRAINT IF EXISTS conduta_avisos_motivo_check;
ALTER TABLE conduta_avisos
  ADD CONSTRAINT conduta_avisos_motivo_check
  CHECK (motivo IN ('tarefa', 'lembrete_5', 'lembrete_1', 'marco_15', 'marco_30', 'marco_60'));

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (214) ON CONFLICT (numero) DO NOTHING;
