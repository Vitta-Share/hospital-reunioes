-- =====================================================
-- Migration 233: Canal de Conduta, os anexos do relato
-- (issue #1844, PRD #1786, ADR 0097, decisão 2; especificação, seção 4, P4)
-- =====================================================
-- Quem relata anexa imagem, PDF ou áudio. O backend apaga os dados de origem
-- do arquivo (EXIF e GPS, informações de documento e XMP, etiquetas do áudio),
-- cifra e guarda o binário no bucket privado do Canal (migration 175). Aqui
-- fica só o ponteiro: o tipo, o caminho no bucket, o tamanho e o código de
-- integridade. O nome original do arquivo não é guardado, de propósito.
--
-- O anexo guardado não muda nem se apaga: o banco recusa UPDATE e DELETE.
--
-- RLS default-deny: só o backend, com a service_role, lê e grava. Nenhuma
-- policy de propósito.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS conduta_relato_anexos (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id             UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  -- relato = passo "O que aconteceu"; complemento = tela de acompanhamento.
  origem              TEXT NOT NULL DEFAULT 'relato' CHECK (origem IN ('relato', 'complemento')),
  tipo                TEXT NOT NULL CHECK (tipo IN ('imagem', 'pdf', 'audio')),
  content_type        TEXT NOT NULL,
  tamanho_bytes       BIGINT NOT NULL CHECK (tamanho_bytes > 0),
  storage_path        TEXT NOT NULL UNIQUE,
  codigo_integridade  TEXT NOT NULL CHECK (codigo_integridade ~ '^[0-9a-f]{64}$'),
  enviado_em          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE conduta_relato_anexos IS
  'Anexo do relato do Canal de Conduta (issue #1844): o arquivo vai sem os dados de origem, cifrado, ao bucket conduta-arquivos e só sai pelo backend. Sem o nome original. Imutável.';

CREATE INDEX IF NOT EXISTS idx_conduta_relato_anexos_caso
  ON conduta_relato_anexos (caso_id, enviado_em);

ALTER TABLE conduta_relato_anexos ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION conduta_relato_anexo_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'O anexo do relato fica guardado: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_relato_anexo_imutavel ON conduta_relato_anexos;
CREATE TRIGGER trg_conduta_relato_anexo_imutavel
  BEFORE UPDATE OR DELETE ON conduta_relato_anexos
  FOR EACH ROW EXECUTE FUNCTION conduta_relato_anexo_imutavel();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (233) ON CONFLICT (numero) DO NOTHING;
