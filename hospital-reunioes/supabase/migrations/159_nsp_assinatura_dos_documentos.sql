-- =====================================================
-- Migration 159: Segurança do Paciente, a assinatura dos documentos do Núcleo
-- (issue #1771, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra:
--   1. o envio de uma versão para a assinatura eletrônica
--      (`nsp_documentos_envios`): uma linha por envelope, com a chave que o
--      retorno da assinatura traz. O reenvio cancela a linha aberta e cria
--      outra;
--   2. quem assina cada envio (`nsp_documentos_signatarios`): a Diretoria
--      Executiva no ato de designação; a Diretoria Executiva e a Presidência
--      no Regimento e no Plano. Cada linha guarda quando a pessoa assinou;
--   3. a função `nsp_versao_para_assinatura`, que grava a versão seguinte do
--      tipo FORA da vigência: a anterior continua valendo até todas as
--      assinaturas chegarem;
--   4. a função `nsp_tornar_vigente`, que numa só transação passa a versão
--      assinada a vigente, sem passar por cima de versão mais nova já vigente.
--
-- Nenhuma pessoa entra por aqui (decisão 12): os signatários saem do cadastro
-- e da Participação vigente no momento do envio.
-- RLS default-deny nas tabelas novas: só o backend, com a service_role, lê e
-- grava. Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. O envio da versão ----------
CREATE TABLE IF NOT EXISTS nsp_documentos_envios (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  documento_id   UUID NOT NULL REFERENCES nsp_documentos(id) ON DELETE RESTRICT,
  situacao       TEXT NOT NULL DEFAULT 'gerado'
                 CHECK (situacao IN ('gerado', 'enviado', 'assinado', 'cancelado')),
  envelope_id    TEXT,
  documento_key  TEXT,
  erro           TEXT CHECK (erro IS NULL OR char_length(erro) <= 500),
  autor_id       VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  enviado_em     TIMESTAMPTZ,
  assinado_em    TIMESTAMPTZ,
  cancelado_em   TIMESTAMPTZ
);

COMMENT ON TABLE nsp_documentos_envios IS
  'Cada envio de uma versão do ato de designação, do Regimento ou do Plano de Segurança do Paciente para a assinatura eletrônica (issue #1771). Reenviar cancela o envio aberto e cria outro.';
COMMENT ON COLUMN nsp_documentos_envios.documento_key IS
  'A chave do documento na assinatura eletrônica: o retorno da assinatura chega com ela.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_nsp_documentos_envios_documento_key
  ON nsp_documentos_envios (documento_key)
  WHERE documento_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_nsp_documentos_envios_aberto
  ON nsp_documentos_envios (documento_id)
  WHERE situacao IN ('gerado', 'enviado');

-- O último envio de cada versão (a tela, a reconsulta, o reenvio) e a FK.
CREATE INDEX IF NOT EXISTS idx_nsp_documentos_envios_documento
  ON nsp_documentos_envios (documento_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_nsp_documentos_envios_autor
  ON nsp_documentos_envios (autor_id);

ALTER TABLE nsp_documentos_envios ENABLE ROW LEVEL SECURITY;

-- ---------- 2. Quem assina ----------
CREATE TABLE IF NOT EXISTS nsp_documentos_signatarios (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  envio_id         UUID NOT NULL REFERENCES nsp_documentos_envios(id) ON DELETE RESTRICT,
  participante_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  qualidade        TEXT NOT NULL CHECK (qualidade IN ('diretoria_executiva', 'presidencia')),
  signatario_id    TEXT,
  assinado_em      TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT nsp_documentos_signatarios_um_por_pessoa UNIQUE (envio_id, participante_id)
);

COMMENT ON TABLE nsp_documentos_signatarios IS
  'Quem assina cada envio de documento do Núcleo e quando assinou (issue #1771). A versão só vira vigente com todas as linhas assinadas.';
COMMENT ON COLUMN nsp_documentos_signatarios.signatario_id IS
  'O id do signatário na assinatura eletrônica: o evento de assinatura chega com ele.';

CREATE INDEX IF NOT EXISTS idx_nsp_documentos_signatarios_participante
  ON nsp_documentos_signatarios (participante_id);

ALTER TABLE nsp_documentos_signatarios ENABLE ROW LEVEL SECURITY;

-- ---------- 3. A versão que vai para assinatura ----------
-- A mesma trava por tipo da `nsp_publicar_documento` (migration 147): duas
-- versões do mesmo tipo ao mesmo tempo não disputam o número.
CREATE OR REPLACE FUNCTION nsp_versao_para_assinatura(
  p_tipo             TEXT,
  p_titulo           TEXT,
  p_texto            TEXT,
  p_natureza_revisao TEXT,
  p_publicado_por    VARCHAR(10)
) RETURNS nsp_documentos
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  v_versao INTEGER;
  v_novo   nsp_documentos;
BEGIN
  IF p_tipo NOT IN ('ato_designacao', 'regimento', 'plano_seguranca_paciente') THEN
    RAISE EXCEPTION 'tipo % não vai para assinatura', p_tipo;
  END IF;

  PERFORM pg_advisory_xact_lock(hashtext('nsp_documentos:' || p_tipo));

  SELECT COALESCE(MAX(versao), 0) + 1 INTO v_versao
    FROM nsp_documentos WHERE tipo = p_tipo;

  INSERT INTO nsp_documentos (tipo, versao, titulo, texto, natureza_revisao, vigente, publicado_por)
  VALUES (p_tipo, v_versao, p_titulo, p_texto, p_natureza_revisao, false, p_publicado_por)
  RETURNING * INTO v_novo;

  RETURN v_novo;
END;
$$;

-- ---------- 4. A versão assinada vira a vigente ----------
-- Devolve a versão vigente, ou nada quando uma versão mais nova do tipo já
-- vale (a assinatura atrasada de uma versão antiga não a derruba).
CREATE OR REPLACE FUNCTION nsp_tornar_vigente(p_documento_id UUID)
RETURNS nsp_documentos
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  v_doc nsp_documentos;
BEGIN
  SELECT * INTO v_doc FROM nsp_documentos WHERE id = p_documento_id;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  PERFORM pg_advisory_xact_lock(hashtext('nsp_documentos:' || v_doc.tipo));

  SELECT * INTO v_doc FROM nsp_documentos WHERE id = p_documento_id;
  IF v_doc.vigente THEN
    RETURN v_doc;
  END IF;

  IF EXISTS (
    SELECT 1 FROM nsp_documentos
     WHERE tipo = v_doc.tipo AND vigente AND versao > v_doc.versao
  ) THEN
    RETURN NULL;
  END IF;

  UPDATE nsp_documentos SET vigente = false WHERE tipo = v_doc.tipo AND vigente;
  UPDATE nsp_documentos SET vigente = true WHERE id = p_documento_id RETURNING * INTO v_doc;

  RETURN v_doc;
END;
$$;

-- As funções são do backend, nunca da anon_key do bundle. `PUBLIC` na frente
-- porque o Postgres concede EXECUTE a PUBLIC quando a função nasce.
REVOKE EXECUTE ON FUNCTION nsp_versao_para_assinatura(TEXT, TEXT, TEXT, TEXT, VARCHAR)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION nsp_versao_para_assinatura(TEXT, TEXT, TEXT, TEXT, VARCHAR) TO service_role;

REVOKE EXECUTE ON FUNCTION nsp_tornar_vigente(UUID)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION nsp_tornar_vigente(UUID) TO service_role;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (159) ON CONFLICT (numero) DO NOTHING;
