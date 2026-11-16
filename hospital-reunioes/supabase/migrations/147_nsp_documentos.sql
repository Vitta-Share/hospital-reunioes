-- =====================================================
-- Migration 147: os documentos do Núcleo de Segurança do Paciente
-- (issue #1767, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra:
--   1. a tabela `nsp_documentos`: cada linha é uma versão de um tipo de
--      documento (ato de designação, Regimento, Plano de Segurança do
--      Paciente, Termo, ata, outro), com a natureza da revisão, a marca de
--      vigente e, quando houver, o arquivo assinado;
--   2. uma única versão vigente por tipo, garantida por índice único parcial;
--   3. a função `nsp_publicar_documento`, que numa só transação tira a marca
--      da vigente anterior do tipo e grava a nova como vigente.
--
-- Nenhum documento entra por aqui: o texto do Regimento entra pela tela.
-- Nada se apaga: a correção é uma versão nova, e a anterior fica na lista.
--
-- RLS default-deny (padrão da casa): quem lê e escreve é o backend com a
-- service_role. Nenhuma policy de propósito.
--
-- Tudo com IF NOT EXISTS / DROP antes de ADD / CREATE OR REPLACE: rodar duas
-- vezes é inofensivo. Aplicar à mão no Studio: o deploy não aplica SQL.
-- =====================================================

BEGIN;

-- ---------- 1. As versões dos documentos ----------
CREATE TABLE IF NOT EXISTS nsp_documentos (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tipo                  TEXT NOT NULL,
  versao                INTEGER NOT NULL CHECK (versao >= 1),
  titulo                TEXT NOT NULL CHECK (btrim(titulo) <> '' AND char_length(titulo) <= 200),
  texto                 TEXT CHECK (texto IS NULL OR char_length(texto) <= 200000),
  natureza_revisao      TEXT,
  vigente               BOOLEAN NOT NULL DEFAULT false,
  arquivo_assinado_path TEXT,
  publicado_por         VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  publicado_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT nsp_documentos_tipo_versao_unica UNIQUE (tipo, versao)
);

ALTER TABLE nsp_documentos DROP CONSTRAINT IF EXISTS nsp_documentos_tipo_check;
ALTER TABLE nsp_documentos
  ADD CONSTRAINT nsp_documentos_tipo_check
  CHECK (tipo IN ('ato_designacao', 'regimento', 'plano_seguranca_paciente', 'termo', 'ata', 'outro'));

ALTER TABLE nsp_documentos DROP CONSTRAINT IF EXISTS nsp_documentos_natureza_revisao_check;
ALTER TABLE nsp_documentos
  ADD CONSTRAINT nsp_documentos_natureza_revisao_check
  CHECK (natureza_revisao IS NULL OR natureza_revisao IN ('material', 'redacao'));

-- O Regimento vive no banco: toda versão dele tem texto e diz se a revisão é
-- material (pede nova assinatura, nas fatias de assinatura) ou só de redação.
ALTER TABLE nsp_documentos DROP CONSTRAINT IF EXISTS nsp_documentos_regimento_check;
ALTER TABLE nsp_documentos
  ADD CONSTRAINT nsp_documentos_regimento_check
  CHECK (tipo <> 'regimento' OR (natureza_revisao IS NOT NULL AND texto IS NOT NULL AND btrim(texto) <> ''));

COMMENT ON TABLE nsp_documentos IS
  'Documentos do Núcleo de Segurança do Paciente, uma linha por versão (issue #1767). Uma única vigente por tipo; nada se apaga, a correção é versão nova.';
COMMENT ON COLUMN nsp_documentos.natureza_revisao IS
  'material = a revisão muda o conteúdo e pede nova assinatura do Termo; redacao = só de redação, sem nova assinatura. Obrigatória no Regimento.';
COMMENT ON COLUMN nsp_documentos.arquivo_assinado_path IS
  'Caminho do arquivo assinado no Storage, quando houver. Preenchido pelas fatias de assinatura.';

-- ---------- 2. Uma única vigente por tipo ----------
CREATE UNIQUE INDEX IF NOT EXISTS nsp_documentos_um_vigente_por_tipo
  ON nsp_documentos(tipo) WHERE vigente;

ALTER TABLE nsp_documentos ENABLE ROW LEVEL SECURITY;

-- ---------- 3. Publicar uma versão nova ----------
-- A trava por tipo serializa duas publicações simultâneas do mesmo tipo: sem
-- ela, as duas leriam a mesma versão máxima e a segunda bateria no UNIQUE.
CREATE OR REPLACE FUNCTION nsp_publicar_documento(
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
  PERFORM pg_advisory_xact_lock(hashtext('nsp_documentos:' || p_tipo));

  SELECT COALESCE(MAX(versao), 0) + 1 INTO v_versao
    FROM nsp_documentos WHERE tipo = p_tipo;

  UPDATE nsp_documentos SET vigente = false WHERE tipo = p_tipo AND vigente;

  INSERT INTO nsp_documentos (tipo, versao, titulo, texto, natureza_revisao, vigente, publicado_por)
  VALUES (p_tipo, v_versao, p_titulo, p_texto, p_natureza_revisao, true, p_publicado_por)
  RETURNING * INTO v_novo;

  RETURN v_novo;
END;
$$;

-- A função é do backend, nunca da anon_key do bundle. `PUBLIC` na frente
-- porque o Postgres concede EXECUTE a PUBLIC quando a função nasce.
REVOKE EXECUTE ON FUNCTION nsp_publicar_documento(TEXT, TEXT, TEXT, TEXT, VARCHAR)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION nsp_publicar_documento(TEXT, TEXT, TEXT, TEXT, VARCHAR) TO service_role;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (147) ON CONFLICT (numero) DO NOTHING;
