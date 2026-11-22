-- =====================================================
-- Migration 217: Canal de Conduta, o afastamento cautelar
-- (issue #1836, PRD #1786, ADR 0097; especificação, seção 6.5; decisões 20
-- a 23, 35 e 36 do diretor)
-- =====================================================
-- Um afastamento por Citado e por caso, em qualquer etapa:
--   - no caso comum, o coordenador do Comitê registra a decisão de afastar, e
--     o aplicativo gera o pedido ao DP e ao Jurídico só com quem afastar e o
--     motivo. O parecer do Jurídico é consultivo;
--   - na Rota Especial, o grupo pede o afastamento à coordenação, que vê só o
--     pedido. A coordenação anexa o parecer do Jurídico, com ciência dos
--     membros do grupo, e é o parecer que define o resultado.
--
-- Quem afastar e o motivo vão cifrados. A entrega do pedido ao DP e ao
-- Jurídico, feita fora do aplicativo, fica registrada com a data e quem
-- registrou. O parecer vai cifrado ao bucket conduta-arquivos e só sai pelo
-- backend; aqui fica só o caminho.
--
-- RLS default-deny: só o backend, com a service_role, lê e grava. Nenhuma
-- policy de propósito. Nenhum dado de pessoa em claro. Rodar duas vezes é
-- inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS conduta_afastamentos (
  id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id                    UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  citado_id                  UUID NOT NULL REFERENCES conduta_citados(id) ON DELETE RESTRICT,
  rota                       TEXT NOT NULL CHECK (rota IN ('comum', 'especial')),
  quem_cifrado               TEXT NOT NULL CHECK (quem_cifrado LIKE 'v1:%'),
  motivo_cifrado             TEXT NOT NULL CHECK (motivo_cifrado LIKE 'v1:%'),
  registrado_por             VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  registrado_em              TIMESTAMPTZ NOT NULL DEFAULT now(),
  entregue_ao_dp_em          DATE,
  entregue_ao_dp_por         VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  entregue_ao_juridico_em    DATE,
  entregue_ao_juridico_por   VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  parecer_storage_path       TEXT,
  parecer_tamanho_bytes      INTEGER,
  parecer_anexado_por        VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  parecer_anexado_em         TIMESTAMPTZ,
  parecer_resultado          TEXT CHECK (parecer_resultado IS NULL OR parecer_resultado IN ('afastar', 'nao_afastar')),
  ciencia_de                 TEXT[],
  CONSTRAINT conduta_afastamentos_um_por_citado UNIQUE (caso_id, citado_id),
  CONSTRAINT conduta_afastamentos_entrega_ao_dp_check
    CHECK ((entregue_ao_dp_em IS NULL) = (entregue_ao_dp_por IS NULL)),
  CONSTRAINT conduta_afastamentos_entrega_ao_juridico_check
    CHECK ((entregue_ao_juridico_em IS NULL) = (entregue_ao_juridico_por IS NULL)),
  CONSTRAINT conduta_afastamentos_parecer_check
    CHECK ((parecer_storage_path IS NULL) = (parecer_anexado_em IS NULL)
       AND (parecer_storage_path IS NULL) = (parecer_anexado_por IS NULL)),
  -- Na Rota Especial o parecer define: anexado, ele leva o resultado e a
  -- ciência do grupo. No caso comum ele é consultivo e não leva resultado.
  CONSTRAINT conduta_afastamentos_resultado_check
    CHECK (
      CASE rota
        WHEN 'especial' THEN (parecer_storage_path IS NULL) = (parecer_resultado IS NULL)
          AND (parecer_storage_path IS NULL) = (ciencia_de IS NULL)
        ELSE parecer_resultado IS NULL AND ciencia_de IS NULL
      END
    )
);

COMMENT ON TABLE conduta_afastamentos IS
  'Afastamento cautelar do Canal de Conduta (issue #1836): quem afastar e o motivo, cifrados; a entrega do pedido ao DP e ao Jurídico; o parecer do Jurídico, cifrado no bucket.';
COMMENT ON COLUMN conduta_afastamentos.ciencia_de IS
  'Rota Especial: os membros do grupo que tiveram ciência do parecer quando ele foi anexado.';

CREATE INDEX IF NOT EXISTS idx_conduta_afastamentos_caso ON conduta_afastamentos (caso_id);
CREATE INDEX IF NOT EXISTS idx_conduta_afastamentos_citado ON conduta_afastamentos (citado_id);
CREATE INDEX IF NOT EXISTS idx_conduta_afastamentos_registrado_por ON conduta_afastamentos (registrado_por);
CREATE INDEX IF NOT EXISTS idx_conduta_afastamentos_entregue_ao_dp_por ON conduta_afastamentos (entregue_ao_dp_por);
CREATE INDEX IF NOT EXISTS idx_conduta_afastamentos_entregue_ao_juridico_por ON conduta_afastamentos (entregue_ao_juridico_por);
CREATE INDEX IF NOT EXISTS idx_conduta_afastamentos_parecer_anexado_por ON conduta_afastamentos (parecer_anexado_por);
-- Os pedidos da Rota Especial que a coordenação lista.
CREATE INDEX IF NOT EXISTS idx_conduta_afastamentos_rota ON conduta_afastamentos (rota, registrado_em DESC);

ALTER TABLE conduta_afastamentos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_afastamentos FROM anon, authenticated;

-- A entrega e o parecer, uma vez gravados, não mudam; quem afastar, o motivo
-- e quem registrou nunca mudam. Linha nenhuma se apaga.
CREATE OR REPLACE FUNCTION conduta_afastamentos_guarda() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'O afastamento cautelar não se apaga' USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.caso_id IS DISTINCT FROM OLD.caso_id
     OR NEW.citado_id IS DISTINCT FROM OLD.citado_id
     OR NEW.rota IS DISTINCT FROM OLD.rota
     OR NEW.quem_cifrado IS DISTINCT FROM OLD.quem_cifrado
     OR NEW.motivo_cifrado IS DISTINCT FROM OLD.motivo_cifrado
     OR NEW.registrado_por IS DISTINCT FROM OLD.registrado_por
     OR NEW.registrado_em IS DISTINCT FROM OLD.registrado_em
     OR (OLD.entregue_ao_dp_em IS NOT NULL AND (NEW.entregue_ao_dp_em IS DISTINCT FROM OLD.entregue_ao_dp_em
         OR NEW.entregue_ao_dp_por IS DISTINCT FROM OLD.entregue_ao_dp_por))
     OR (OLD.entregue_ao_juridico_em IS NOT NULL AND (NEW.entregue_ao_juridico_em IS DISTINCT FROM OLD.entregue_ao_juridico_em
         OR NEW.entregue_ao_juridico_por IS DISTINCT FROM OLD.entregue_ao_juridico_por))
     OR (OLD.parecer_storage_path IS NOT NULL AND (NEW.parecer_storage_path IS DISTINCT FROM OLD.parecer_storage_path
         OR NEW.parecer_tamanho_bytes IS DISTINCT FROM OLD.parecer_tamanho_bytes
         OR NEW.parecer_anexado_por IS DISTINCT FROM OLD.parecer_anexado_por
         OR NEW.parecer_anexado_em IS DISTINCT FROM OLD.parecer_anexado_em
         OR NEW.parecer_resultado IS DISTINCT FROM OLD.parecer_resultado
         OR NEW.ciencia_de IS DISTINCT FROM OLD.ciencia_de))
  THEN
    RAISE EXCEPTION 'O que o afastamento cautelar já registrou não muda' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_afastamentos_guarda ON conduta_afastamentos;
CREATE TRIGGER trg_conduta_afastamentos_guarda
  BEFORE UPDATE OR DELETE ON conduta_afastamentos
  FOR EACH ROW EXECUTE FUNCTION conduta_afastamentos_guarda();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (217) ON CONFLICT (numero) DO NOTHING;
