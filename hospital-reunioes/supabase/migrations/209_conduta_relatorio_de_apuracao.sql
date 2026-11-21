-- =====================================================
-- Migration 209: Canal de Conduta, o relatório de apuração e o envio para voto
-- (issue #1832, PRD #1786, ADR 0097, decisão 7; especificação, 6.3, 6.4 e 8)
-- =====================================================
-- O que entra:
--   1. o relatório de apuração e a cronologia dos fatos, em versões: o texto
--      cifrado pela aplicação, quem fez a versão e se ela veio do agente ou
--      de uma edição. A edição vira versão nova, e a anterior fica: o banco
--      recusa UPDATE e DELETE. Só entra versão em caso na etapa Apuração;
--   2. a assinatura do relatório pelos apuradores, no rito Completo, aponta
--      para a versão que foi à ClickSign (`conduta_assinaturas.relatorio_id`);
--   3. a Apuração só vai a voto com o relatório gerado.
--
-- RLS default-deny na tabela nova: só o backend, com a service_role, lê e
-- grava. Nenhuma policy de propósito. Nenhum dado de pessoa entra aqui.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. O relatório e a cronologia, em versões ----------
CREATE TABLE IF NOT EXISTS conduta_relatorios (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id        UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  tipo           TEXT NOT NULL CHECK (tipo IN ('relatorio', 'cronologia')),
  versao         INTEGER NOT NULL CHECK (versao >= 1),
  texto_cifrado  TEXT NOT NULL CHECK (texto_cifrado LIKE 'v1:%'),
  origem         TEXT NOT NULL CHECK (origem IN ('agente', 'edicao')),
  autor_id       VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, tipo, versao)
);

COMMENT ON TABLE conduta_relatorios IS
  'Relatório de apuração e cronologia dos fatos do Canal de Conduta, em versões (issue #1832). Texto cifrado pela aplicação. Imutável: a edição entra como versão nova.';

CREATE INDEX IF NOT EXISTS idx_conduta_relatorios_autor ON conduta_relatorios (autor_id);

ALTER TABLE conduta_relatorios ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_relatorios FROM anon, authenticated;

CREATE OR REPLACE FUNCTION conduta_relatorio_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'A versão do relatório fica guardada: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_relatorio_imutavel ON conduta_relatorios;
CREATE TRIGGER trg_conduta_relatorio_imutavel
  BEFORE UPDATE OR DELETE ON conduta_relatorios
  FOR EACH ROW EXECUTE FUNCTION conduta_relatorio_imutavel();

CREATE OR REPLACE FUNCTION conduta_relatorio_na_apuracao() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM conduta_casos WHERE id = NEW.caso_id AND etapa = 'apuracao') THEN
    RAISE EXCEPTION 'O relatório só muda na etapa Apuração'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_relatorio_na_apuracao ON conduta_relatorios;
CREATE TRIGGER trg_conduta_relatorio_na_apuracao
  BEFORE INSERT ON conduta_relatorios
  FOR EACH ROW EXECUTE FUNCTION conduta_relatorio_na_apuracao();

-- ---------- 2. A versão que foi à assinatura ----------
ALTER TABLE conduta_assinaturas
  ADD COLUMN IF NOT EXISTS relatorio_id UUID REFERENCES conduta_relatorios(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_conduta_assinaturas_relatorio ON conduta_assinaturas (relatorio_id);

ALTER TABLE conduta_assinaturas DROP CONSTRAINT IF EXISTS conduta_assinaturas_relatorio_da_versao;
ALTER TABLE conduta_assinaturas ADD CONSTRAINT conduta_assinaturas_relatorio_da_versao CHECK (
  tipo <> 'relatorio_de_apuracao' OR (relatorio_id IS NOT NULL AND caso_id IS NOT NULL)
);

-- ---------- 3. A Apuração só vai a voto com o relatório ----------
CREATE OR REPLACE FUNCTION conduta_voto_com_relatorio() RETURNS TRIGGER AS $$
BEGIN
  IF OLD.etapa = 'apuracao' AND NEW.etapa = 'voto' AND NOT EXISTS (
       SELECT 1 FROM conduta_relatorios WHERE caso_id = NEW.id AND tipo = 'relatorio'
     ) THEN
    RAISE EXCEPTION 'A Apuração só vai a voto com o relatório'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_voto_com_relatorio ON conduta_casos;
CREATE TRIGGER trg_conduta_voto_com_relatorio
  BEFORE UPDATE OF etapa ON conduta_casos
  FOR EACH ROW EXECUTE FUNCTION conduta_voto_com_relatorio();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (209) ON CONFLICT (numero) DO NOTHING;
