-- =====================================================
-- Migration 229: Canal de Conduta, a verificação de retaliação em 30, 90 e
-- 180 dias (issue #1839, PRD #1786, ADR 0097; especificação, 6.11 e 18)
-- =====================================================
-- O que entra:
--   1. no caso, o aviso de quem relatou: a última vez que ele informou algo
--      pela página de acompanhamento (a página grava, issue #1845). Com ele,
--      o caso anônimo também ganha a verificação;
--   2. a verificação de retaliação: uma por marco (30, 90 ou 180 dias) do
--      caso concluído, só depois do dia dela, contado do encerramento no
--      fuso de São Paulo. Houve ou não houve, a observação cifrada, quem
--      registrou e quando. Registrada, não muda nem se apaga; a única
--      mudança é ligar, uma vez, o caso novo de retaliação a uma verificação
--      em que houve.
--
-- RLS default-deny na tabela nova: só o backend, com a service_role, lê e
-- grava. Nenhuma policy de propósito. Nenhum dado de pessoa em claro.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. O aviso de quem relatou ----------
ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS denunciante_informou_em TIMESTAMPTZ;

COMMENT ON COLUMN conduta_casos.denunciante_informou_em IS
  'A última vez que quem relatou informou algo pela página de acompanhamento (issue #1845). Com ele, o caso concluído anônimo também ganha a verificação de retaliação (issue #1839).';

-- ---------- 2. A verificação de retaliação ----------
CREATE TABLE IF NOT EXISTS conduta_verificacoes_de_retaliacao (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id             UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  marco               SMALLINT NOT NULL CHECK (marco IN (30, 90, 180)),
  houve               BOOLEAN NOT NULL,
  observacao_cifrada  TEXT CHECK (observacao_cifrada IS NULL OR observacao_cifrada LIKE 'v1:%'),
  verificada_por      VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  verificada_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
  caso_novo_id        UUID REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  UNIQUE (caso_id, marco),
  CONSTRAINT conduta_verificacoes_de_retaliacao_caso_novo CHECK (caso_novo_id IS NULL OR houve),
  CONSTRAINT conduta_verificacoes_de_retaliacao_outro_caso CHECK (caso_novo_id IS DISTINCT FROM caso_id)
);

COMMENT ON TABLE conduta_verificacoes_de_retaliacao IS
  'Verificação de retaliação do caso concluído do Canal de Conduta (issue #1839; especificação, 6.11): em 30, 90 e 180 dias, a coordenação registra se houve mudança desfavorável para quem relatou. Observação cifrada. Imutável, fora ligar uma vez o caso novo de retaliação.';

CREATE INDEX IF NOT EXISTS idx_conduta_verificacoes_de_retaliacao_verificada_por
  ON conduta_verificacoes_de_retaliacao (verificada_por);
CREATE INDEX IF NOT EXISTS idx_conduta_verificacoes_de_retaliacao_caso_novo
  ON conduta_verificacoes_de_retaliacao (caso_novo_id);

ALTER TABLE conduta_verificacoes_de_retaliacao ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_verificacoes_de_retaliacao FROM anon, authenticated;

-- A verificação é do caso concluído, e só a partir do dia dela.
CREATE OR REPLACE FUNCTION conduta_verificacao_no_dia() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM conduta_casos
        WHERE id = NEW.caso_id AND desfecho = 'concluido' AND encerrado_em IS NOT NULL
          AND (encerrado_em AT TIME ZONE 'America/Sao_Paulo')::date + NEW.marco
              <= (now() AT TIME ZONE 'America/Sao_Paulo')::date
     ) THEN
    RAISE EXCEPTION 'A verificação de retaliação é do caso concluído, a partir do dia dela'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_verificacoes_de_retaliacao_no_dia ON conduta_verificacoes_de_retaliacao;
CREATE TRIGGER trg_conduta_verificacoes_de_retaliacao_no_dia
  BEFORE INSERT ON conduta_verificacoes_de_retaliacao
  FOR EACH ROW EXECUTE FUNCTION conduta_verificacao_no_dia();

-- Registrada, a verificação não muda nem se apaga. A única mudança é ligar,
-- uma vez, o caso novo de retaliação.
CREATE OR REPLACE FUNCTION conduta_verificacao_guardada() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'UPDATE'
     AND OLD.caso_novo_id IS NULL AND NEW.caso_novo_id IS NOT NULL
     AND (NEW.id, NEW.caso_id, NEW.marco, NEW.houve, NEW.observacao_cifrada, NEW.verificada_por, NEW.verificada_em)
         IS NOT DISTINCT FROM
         (OLD.id, OLD.caso_id, OLD.marco, OLD.houve, OLD.observacao_cifrada, OLD.verificada_por, OLD.verificada_em)
  THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'A verificação de retaliação fica guardada: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_verificacoes_de_retaliacao_guardadas ON conduta_verificacoes_de_retaliacao;
CREATE TRIGGER trg_conduta_verificacoes_de_retaliacao_guardadas
  BEFORE UPDATE OR DELETE ON conduta_verificacoes_de_retaliacao
  FOR EACH ROW EXECUTE FUNCTION conduta_verificacao_guardada();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (229) ON CONFLICT (numero) DO NOTHING;
