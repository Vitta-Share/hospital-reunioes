-- =====================================================
-- Migration 181: os anexos da Notificação de incidente
-- (issue #1988, PRD #1979, ADR 0107 decisão 6)
-- =====================================================
-- Quem notifica anexa até três fotos ou PDFs, somando menos de 9 MB.
--
--   1. `nsp_notificacao_anexos`: os metadados de cada arquivo, ligados à
--      notificação. O binário fica no bucket privado, num caminho sorteado.
--      O nome original do arquivo não tem coluna: pode identificar quem
--      notificou sem se identificar. Nada daqui entra na linha da
--      notificação, que é o que a IA lê;
--   2. o banco recusa o quarto anexo da mesma notificação;
--   3. o bucket privado `nsp-anexos`, com o teto de 9 MB e só foto e PDF no
--      próprio Storage. Sem policy para `authenticated` e sem URL assinada: o
--      backend confere o recurso de casos e entrega o arquivo.
--
-- RLS ligado e sem política: só o backend, com a service_role, lê e grava.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio, depois da 174.
-- =====================================================

BEGIN;

-- ---------- 1. Os anexos ----------
CREATE TABLE IF NOT EXISTS nsp_notificacao_anexos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notificacao_id  UUID NOT NULL REFERENCES nsp_notificacoes(id) ON DELETE RESTRICT,
  storage_path    TEXT NOT NULL UNIQUE CHECK (btrim(storage_path) <> ''),
  content_type    TEXT NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp', 'image/heic', 'application/pdf')),
  tamanho_bytes   BIGINT NOT NULL CHECK (tamanho_bytes > 0 AND tamanho_bytes < 9437184),
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE nsp_notificacao_anexos IS
  'Foto ou PDF anexado à Notificação de incidente, até três por notificação. Binário no bucket privado nsp-anexos; o nome original não é guardado; nunca vai para a IA. Issue #1988.';
COMMENT ON COLUMN nsp_notificacao_anexos.storage_path IS
  'Caminho sorteado no bucket privado. O nome original pode identificar quem notificou e não entra em caminho nem em coluna.';

CREATE INDEX IF NOT EXISTS idx_nsp_notificacao_anexos_notificacao
  ON nsp_notificacao_anexos (notificacao_id, criado_em);

ALTER TABLE nsp_notificacao_anexos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nsp_notificacao_anexos FROM anon, authenticated;

-- ---------- 2. Até três por notificação ----------
CREATE OR REPLACE FUNCTION nsp_notificacao_anexos_ate_tres() RETURNS TRIGGER AS $$
BEGIN
  IF (SELECT count(*) FROM nsp_notificacao_anexos WHERE notificacao_id = NEW.notificacao_id) >= 3 THEN
    RAISE EXCEPTION 'A notificação aceita até 3 anexos'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_notificacao_anexos_ate_tres ON nsp_notificacao_anexos;
CREATE TRIGGER trg_nsp_notificacao_anexos_ate_tres
  BEFORE INSERT ON nsp_notificacao_anexos
  FOR EACH ROW EXECUTE FUNCTION nsp_notificacao_anexos_ate_tres();

-- ---------- 3. O bucket privado ----------
-- O DO UPDATE fecha o bucket e garante o teto e os tipos mesmo se ele tiver
-- nascido à mão no Studio (molde da 174 da Pendência).
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'nsp-anexos', 'nsp-anexos', false, 9437184,
  ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'application/pdf']
)
ON CONFLICT (id) DO UPDATE SET
  public = false,
  file_size_limit = 9437184,
  allowed_mime_types = ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'application/pdf'];

DROP POLICY IF EXISTS "Authenticated Access nsp-anexos" ON storage.objects;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (181) ON CONFLICT (numero) DO NOTHING;
