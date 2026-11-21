-- =====================================================
-- Migration 174: foto ou PDF anexado na conclusao da Pendencia (issue #1865, PRD #1757)
-- =====================================================
-- Ao concluir, o responsavel pode anexar uma imagem ou um PDF de ate 10 MB,
-- alem da anotacao, que continua obrigatoria.
--
-- 1. `pendencia_anexos`: os metadados do anexo, ligado ao evento de conclusao
--    no Historico da Pendencia. O binario fica no bucket privado.
-- 2. O bucket privado `anexos-pendencias`, com o teto de 10 MB e so imagem e
--    PDF no proprio Storage. Sem policy para `authenticated`: o unico caminho
--    ate o arquivo e o link assinado de curta duracao que o backend emite
--    depois de conferir o papel (responsavel, Facilitador ou Super admin).
-- 3. `registrar_conclusao_com_anexo`: grava a conclusao (pela
--    `registrar_acao_da_pendencia` da 169) e o anexo na mesma transacao. Se a
--    conclusao for recusada, nenhum anexo fica.
--
-- RLS default-deny: so o backend, com a service_role, le e grava. Nenhuma
-- policy de proposito. Rodar duas vezes e inofensivo. Aplicar a mao no Studio,
-- depois da 169.
-- =====================================================

BEGIN;

-- 1. Os anexos da conclusao ----------------------------------------------------

CREATE TABLE IF NOT EXISTS pendencia_anexos (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_acao        VARCHAR(10) NOT NULL REFERENCES pendencias(id_acao),
  evento_id      BIGINT NOT NULL UNIQUE REFERENCES pendencia_historico(id),
  storage_path   TEXT NOT NULL CHECK (btrim(storage_path) <> ''),
  nome_original  TEXT NOT NULL,
  content_type   TEXT NOT NULL CHECK (content_type IN (
                   'image/jpeg', 'image/png', 'image/webp', 'application/pdf'
                 )),
  tamanho_bytes  BIGINT NOT NULL CHECK (tamanho_bytes > 0 AND tamanho_bytes <= 10485760),
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE pendencia_anexos IS
  'Foto ou PDF anexado na conclusao da Pendencia, ligado ao evento de conclusao do Historico. Binario no bucket privado anexos-pendencias. Issue #1865.';
COMMENT ON COLUMN pendencia_anexos.storage_path IS
  'Caminho no bucket privado. Nome sorteado: o nome original pode carregar dado pessoal e nao entra em caminho.';

CREATE INDEX IF NOT EXISTS idx_pendencia_anexos_acao ON pendencia_anexos (id_acao);

ALTER TABLE pendencia_anexos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON pendencia_anexos FROM anon, authenticated;

-- 2. O bucket privado ----------------------------------------------------------
-- O DO UPDATE fecha o bucket e garante o teto e os tipos mesmo se ele tiver
-- nascido a mao no Studio (molde da 116).

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'anexos-pendencias', 'anexos-pendencias', false, 10485760,
  ARRAY['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
)
ON CONFLICT (id) DO UPDATE SET
  public = false,
  file_size_limit = 10485760,
  allowed_mime_types = ARRAY['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];

DROP POLICY IF EXISTS "Authenticated Access anexos-pendencias" ON storage.objects;

-- 3. A conclusao com anexo -----------------------------------------------------
-- Os mesmos parametros da `registrar_acao_da_pendencia`, mais o anexo. A regra
-- (quem pode, de qual estado) segue no Python; o PT404 e o PT409 sobem iguais.

CREATE OR REPLACE FUNCTION registrar_conclusao_com_anexo(
  p_id_acao          VARCHAR,
  p_anotacao         TEXT,
  p_autor_id         VARCHAR,
  p_autor_nome       TEXT,
  p_status_esperado  TEXT,
  p_status_novo      TEXT,
  p_concluida        BOOLEAN,
  p_conta_atraso     BOOLEAN,
  p_storage_path     TEXT,
  p_nome_original    TEXT,
  p_content_type     TEXT,
  p_tamanho_bytes    BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
  v_evento  BIGINT;
BEGIN
  v_evento := registrar_acao_da_pendencia(
    p_id_acao, 'concluir', p_anotacao, p_autor_id, p_autor_nome,
    p_status_esperado, p_status_novo, NULL, p_concluida, p_conta_atraso
  );

  INSERT INTO pendencia_anexos (
    id_acao, evento_id, storage_path, nome_original, content_type, tamanho_bytes
  ) VALUES (
    p_id_acao, v_evento, p_storage_path, p_nome_original, p_content_type, p_tamanho_bytes
  );

  RETURN v_evento;
END;
$$;

REVOKE EXECUTE ON FUNCTION registrar_conclusao_com_anexo(VARCHAR, TEXT, VARCHAR, TEXT, TEXT, TEXT, BOOLEAN, BOOLEAN, TEXT, TEXT, TEXT, BIGINT)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION registrar_conclusao_com_anexo(VARCHAR, TEXT, VARCHAR, TEXT, TEXT, TEXT, BOOLEAN, BOOLEAN, TEXT, TEXT, TEXT, BIGINT)
  TO service_role;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (174) ON CONFLICT (numero) DO NOTHING;
