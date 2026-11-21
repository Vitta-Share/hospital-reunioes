-- =====================================================
-- Migration 179: Canal de Conduta, triagem, ritos e prazos
-- (issue #1824, PRD #1786, ADR 0097; especificação, seções 5, 6.1, 6.2 e 18)
-- =====================================================
-- O que entra:
--   1. o segundo leitor como papel da Participação no Comitê: vê a mesma fila
--      de triagem da coordenação, confere ou contesta a triagem e vota;
--   2. no caso, a triagem manual da coordenação (dentro, fora ou misto, a
--      categoria, o rito e o destino do que é de fora), a conferência do
--      segundo leitor, a prorrogação do rito Completo (uma vez só, com a
--      justificativa cifrada) e o encerramento como "Encaminhado", com a
--      orientação enviada, cifrada;
--   3. a contestação da triagem pelo segundo leitor e a decisão dos três;
--   4. o registro do prazo vencido, que não se altera nem se apaga.
--
-- RLS default-deny em toda tabela nova: só o backend, com a service_role, lê
-- e grava. Nenhuma policy de propósito. Nenhum dado de pessoa entra aqui.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. O segundo leitor ----------
ALTER TABLE participacoes DROP CONSTRAINT IF EXISTS participacoes_papel_check;
ALTER TABLE participacoes
  ADD CONSTRAINT participacoes_papel_check
  CHECK (papel IN ('presidencia', 'suplente', 'membro', 'coordenacao', 'segundo_leitor'));

-- ---------- 2. A triagem e o rito no caso ----------
ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS escopo                    TEXT,
  ADD COLUMN IF NOT EXISTS rito                      TEXT,
  ADD COLUMN IF NOT EXISTS destino                   TEXT,
  ADD COLUMN IF NOT EXISTS triagem_por               VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS triagem_em                TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS conferida_por             VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS conferida_em              TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS prorrogado_por            VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS prorrogado_em             TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS prorrogacao_cifrada       TEXT,
  ADD COLUMN IF NOT EXISTS orientacao_cifrada        TEXT,
  ADD COLUMN IF NOT EXISTS encerrado_em              TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS desfecho                  TEXT;

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_escopo_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_escopo_check
  CHECK (escopo IS NULL OR escopo IN ('dentro', 'fora', 'misto'));

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_rito_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_rito_check
  CHECK (rito IS NULL OR rito IN ('encaminhamento', 'rapido', 'completo', 'especial'));

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_destino_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_destino_check
  CHECK (destino IS NULL OR destino IN ('dp', 'ouvidoria', 'nsp', 'gestor'));

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_desfecho_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_desfecho_check
  CHECK (desfecho IS NULL OR desfecho IN ('encaminhado'));

-- Só o rito Completo prorroga, e só com a justificativa escrita.
ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_prorrogacao_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_prorrogacao_check
  CHECK (
    prorrogado_em IS NULL
    OR (rito = 'completo' AND prorrogacao_cifrada LIKE 'v1:%')
  );

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_orientacao_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_orientacao_check
  CHECK (orientacao_cifrada IS NULL OR orientacao_cifrada LIKE 'v1:%');

COMMENT ON COLUMN conduta_casos.escopo IS
  'Triagem da coordenação (issue #1824): dentro, fora ou misto. Fora do canal vai sempre ao rito Encaminhamento.';
COMMENT ON COLUMN conduta_casos.prazo_em IS
  'Último dia do prazo do rito, contado do envio do relato (recebido_em), nunca da triagem.';
COMMENT ON COLUMN conduta_casos.prorrogado_em IS
  'A prorrogação única do rito Completo, por mais 30 dias. Uma vez gravada, não muda (trigger).';

-- A prorrogação é uma vez só: gravada, o banco não a troca nem a apaga.
CREATE OR REPLACE FUNCTION conduta_prorrogacao_unica() RETURNS TRIGGER AS $$
BEGIN
  IF OLD.prorrogado_em IS NOT NULL AND (
       NEW.prorrogado_em IS DISTINCT FROM OLD.prorrogado_em
       OR NEW.prorrogacao_cifrada IS DISTINCT FROM OLD.prorrogacao_cifrada
       OR NEW.prorrogado_por IS DISTINCT FROM OLD.prorrogado_por
     ) THEN
    RAISE EXCEPTION 'O rito Completo prorroga uma vez só: a prorrogação gravada não muda'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_prorrogacao_unica ON conduta_casos;
CREATE TRIGGER trg_conduta_prorrogacao_unica
  BEFORE UPDATE ON conduta_casos
  FOR EACH ROW EXECUTE FUNCTION conduta_prorrogacao_unica();

CREATE INDEX IF NOT EXISTS idx_conduta_casos_triagem_por ON conduta_casos (triagem_por);
CREATE INDEX IF NOT EXISTS idx_conduta_casos_conferida_por ON conduta_casos (conferida_por);
CREATE INDEX IF NOT EXISTS idx_conduta_casos_prorrogado_por ON conduta_casos (prorrogado_por);

-- ---------- 3. A contestação e a decisão dos três ----------
-- Uma contestação por caso. A proposta é a triagem que o segundo leitor
-- defende; o motivo vai cifrado, porque pode citar o relato.
CREATE TABLE IF NOT EXISTS conduta_contestacoes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id         UUID NOT NULL UNIQUE REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  autor_id        VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  motivo_cifrado  TEXT NOT NULL CHECK (motivo_cifrado LIKE 'v1:%'),
  escopo          TEXT NOT NULL CHECK (escopo IN ('dentro', 'fora', 'misto')),
  categoria       TEXT NOT NULL,
  rito            TEXT NOT NULL CHECK (rito IN ('encaminhamento', 'rapido', 'completo')),
  destino         TEXT CHECK (destino IS NULL OR destino IN ('dp', 'ouvidoria', 'nsp', 'gestor')),
  resultado       TEXT CHECK (resultado IS NULL OR resultado IN ('mantida', 'acatada')),
  decidida_em     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE conduta_contestacoes IS
  'Contestação da triagem pelo segundo leitor, decidida pelos três membros votantes (issue #1824). mantida = vale a triagem da coordenação; acatada = vale a proposta.';

CREATE INDEX IF NOT EXISTS idx_conduta_contestacoes_autor ON conduta_contestacoes (autor_id);

ALTER TABLE conduta_contestacoes ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS conduta_contestacao_votos (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contestacao_id   UUID NOT NULL REFERENCES conduta_contestacoes(id) ON DELETE RESTRICT,
  participante_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  escolha          TEXT NOT NULL CHECK (escolha IN ('manter', 'acatar')),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (contestacao_id, participante_id)
);

COMMENT ON TABLE conduta_contestacao_votos IS
  'O voto de cada membro votante na contestação da triagem (issue #1824). Um por pessoa.';

CREATE INDEX IF NOT EXISTS idx_conduta_contestacao_votos_pessoa ON conduta_contestacao_votos (participante_id);

ALTER TABLE conduta_contestacao_votos ENABLE ROW LEVEL SECURITY;

-- ---------- 4. O prazo vencido, para sempre ----------
CREATE TABLE IF NOT EXISTS conduta_prazos_vencidos (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id        UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  rito           TEXT NOT NULL,
  prazo_em       DATE NOT NULL,
  registrado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, prazo_em)
);

COMMENT ON TABLE conduta_prazos_vencidos IS
  'Prazo de rito que venceu sem o caso encerrar (issue #1824). Imutável: nenhum perfil altera ou apaga, nem a prorrogação.';

ALTER TABLE conduta_prazos_vencidos ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION conduta_prazo_vencido_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'O prazo vencido fica registrado para sempre: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_prazo_vencido_imutavel ON conduta_prazos_vencidos;
CREATE TRIGGER trg_conduta_prazo_vencido_imutavel
  BEFORE UPDATE OR DELETE ON conduta_prazos_vencidos
  FOR EACH ROW EXECUTE FUNCTION conduta_prazo_vencido_imutavel();

DROP TRIGGER IF EXISTS trg_conduta_prazo_vencido_sem_truncate ON conduta_prazos_vencidos;
CREATE TRIGGER trg_conduta_prazo_vencido_sem_truncate
  BEFORE TRUNCATE ON conduta_prazos_vencidos
  FOR EACH STATEMENT EXECUTE FUNCTION conduta_prazo_vencido_imutavel();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (179) ON CONFLICT (numero) DO NOTHING;
