-- =====================================================
-- Migration 224: Canal de Conduta, a trilha com gavetas e o Dossiê do caso
-- (issue #1837, PRD #1786, ADR 0097, decisões 2 e 9; especificação, 9.1 e 9.2)
-- =====================================================
-- O que entra:
--   1. o código de integridade de cada arquivo do caso (SHA-256 do arquivo
--      decifrado, em hexadecimal), gravado na hora do envio: nos arquivos do
--      depoimento, na ciência do Código, na cópia do PDF assinado pela
--      ClickSign e no parecer do Jurídico do afastamento cautelar. O arquivo
--      enviado antes desta migration fica sem código;
--   2. o código gravado não muda: as duas tabelas que já recusam UPDATE
--      (arquivos do depoimento e ciência) continuam recusando, e nas outras
--      duas um gatilho recusa trocar o código depois de gravado.
--
-- As gavetas de cada rito e o Dossiê saem da aplicação, sem tabela nova: o
-- download do Dossiê é uma linha da trilha do caso (migration 175).
-- Nenhuma policy nova: RLS das tabelas segue default-deny.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. O código de integridade por arquivo ----------
ALTER TABLE conduta_depoimento_arquivos
  ADD COLUMN IF NOT EXISTS codigo_integridade TEXT;
ALTER TABLE conduta_depoimento_arquivos DROP CONSTRAINT IF EXISTS conduta_depoimento_arquivos_codigo_check;
ALTER TABLE conduta_depoimento_arquivos
  ADD CONSTRAINT conduta_depoimento_arquivos_codigo_check
  CHECK (codigo_integridade IS NULL OR codigo_integridade ~ '^[0-9a-f]{64}$');

ALTER TABLE conduta_ciencias_do_codigo
  ADD COLUMN IF NOT EXISTS codigo_integridade TEXT;
ALTER TABLE conduta_ciencias_do_codigo DROP CONSTRAINT IF EXISTS conduta_ciencias_do_codigo_codigo_check;
ALTER TABLE conduta_ciencias_do_codigo
  ADD CONSTRAINT conduta_ciencias_do_codigo_codigo_check
  CHECK (codigo_integridade IS NULL OR codigo_integridade ~ '^[0-9a-f]{64}$');

ALTER TABLE conduta_assinaturas
  ADD COLUMN IF NOT EXISTS codigo_integridade TEXT;
ALTER TABLE conduta_assinaturas DROP CONSTRAINT IF EXISTS conduta_assinaturas_codigo_check;
ALTER TABLE conduta_assinaturas
  ADD CONSTRAINT conduta_assinaturas_codigo_check
  CHECK (codigo_integridade IS NULL OR codigo_integridade ~ '^[0-9a-f]{64}$');

ALTER TABLE conduta_afastamentos
  ADD COLUMN IF NOT EXISTS parecer_codigo_integridade TEXT;
ALTER TABLE conduta_afastamentos DROP CONSTRAINT IF EXISTS conduta_afastamentos_parecer_codigo_check;
ALTER TABLE conduta_afastamentos
  ADD CONSTRAINT conduta_afastamentos_parecer_codigo_check
  CHECK (parecer_codigo_integridade IS NULL OR parecer_codigo_integridade ~ '^[0-9a-f]{64}$');

COMMENT ON COLUMN conduta_depoimento_arquivos.codigo_integridade IS
  'SHA-256 do arquivo decifrado, gravado no envio (issue #1837). Nulo no arquivo enviado antes da migration 224.';
COMMENT ON COLUMN conduta_ciencias_do_codigo.codigo_integridade IS
  'SHA-256 do arquivo decifrado, gravado no envio (issue #1837).';
COMMENT ON COLUMN conduta_assinaturas.codigo_integridade IS
  'SHA-256 da cópia do PDF assinado, gravado quando a cópia é guardada (issue #1837). Não muda.';
COMMENT ON COLUMN conduta_afastamentos.parecer_codigo_integridade IS
  'SHA-256 do parecer do Jurídico, gravado no envio (issue #1837). Não muda.';

-- ---------- 2. O código gravado não muda ----------
-- A coluna vem no argumento do gatilho, para servir às duas tabelas.
CREATE OR REPLACE FUNCTION conduta_codigo_de_integridade_guardado() RETURNS TRIGGER AS $$
BEGIN
  IF to_jsonb(OLD) ->> TG_ARGV[0] IS NOT NULL
     AND (to_jsonb(NEW) ->> TG_ARGV[0]) IS DISTINCT FROM (to_jsonb(OLD) ->> TG_ARGV[0]) THEN
    RAISE EXCEPTION 'O código de integridade do arquivo, uma vez gravado, não muda'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_assinaturas_codigo_guardado ON conduta_assinaturas;
CREATE TRIGGER trg_conduta_assinaturas_codigo_guardado
  BEFORE UPDATE ON conduta_assinaturas
  FOR EACH ROW EXECUTE FUNCTION conduta_codigo_de_integridade_guardado('codigo_integridade');

DROP TRIGGER IF EXISTS trg_conduta_afastamentos_codigo_guardado ON conduta_afastamentos;
CREATE TRIGGER trg_conduta_afastamentos_codigo_guardado
  BEFORE UPDATE ON conduta_afastamentos
  FOR EACH ROW EXECUTE FUNCTION conduta_codigo_de_integridade_guardado('parecer_codigo_integridade');

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (224) ON CONFLICT (numero) DO NOTHING;
