-- =====================================================
-- Migration 221: Canal de Conduta, a ata de deliberação e a reunião do Comitê
-- (issue #1834, PRD #1786, ADR 0097, decisão 7; especificação, 6.7, 7.3, 8
-- e Anexo D)
-- =====================================================
-- O que entra:
--   1. a ata de deliberação, em versões: o texto cifrado pela aplicação e os
--      "Pontos a confirmar" (Sugestão, fora da ata), também cifrados. A ata
--      nasce na etapa Voto, depois dos votos; a versão fica guardada, e a ata
--      assinada não ganha versão nova. A versão fica presa à rodada e aos três
--      votantes de que saiu: se um deles fica impedido ou vira Citado, ou a
--      rodada muda, a ata deixa de valer e a coordenação gera outra;
--   2. a assinatura da ata pelos três votantes aponta para a versão que foi à
--      ClickSign (`conduta_assinaturas.ata_id`). A ata que está na ClickSign,
--      e ainda vale, não ganha versão nova;
--   3. a transcrição da reunião do Comitê, no rito Completo: o arquivo fica
--      cifrado no bucket do Canal, e a linha aqui só pode ser apagada depois
--      de concluída a reunião (a eliminação da seção 7.3). Nada de áudio;
--   4. a lista de conferência da reunião: as duas declarações da coordenação,
--      com quem marcou e quando, que não se desfazem;
--   5. no caso, quem concluiu a reunião, quando, e quando a transcrição foi
--      eliminada. "CONCLUIR REUNIÃO" só com os quatro itens;
--   6. a trava de robustez: o item "Votos registrados e ata assinada" só se
--      confirma com a ata assinada, e a votação só conclui com a ata assinada
--      e, no Completo, com a reunião concluída.
--
-- RLS default-deny em toda tabela nova: só o backend, com a service_role, lê
-- e grava. Nenhuma policy de propósito. Nenhum dado de pessoa em claro.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 5. No caso: a reunião concluída e a transcrição eliminada ----------
-- Antes das tabelas: os gatilhos delas leem estas colunas.
ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS reuniao_concluida_em      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS reuniao_concluida_por     VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS transcricao_eliminada_em  TIMESTAMPTZ;

COMMENT ON COLUMN conduta_casos.reuniao_concluida_em IS
  'CONCLUIR REUNIÃO do rito Completo (issue #1834): só com a transcrição anexada, a ata assinada e as duas declarações da coordenação. Gravada, não muda.';
COMMENT ON COLUMN conduta_casos.transcricao_eliminada_em IS
  'Quando a transcrição da reunião do Comitê saiu do banco e do bucket, depois de concluída a reunião (issue #1834).';

CREATE INDEX IF NOT EXISTS idx_conduta_casos_reuniao_concluida_por ON conduta_casos (reuniao_concluida_por);

-- A recusa de UPDATE e DELETE das tabelas guardadas desta migration.
CREATE OR REPLACE FUNCTION conduta_ata_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'O registro da ata e da reunião fica guardado: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

-- ---------- 1. A ata de deliberação, em versões ----------
CREATE TABLE IF NOT EXISTS conduta_atas (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id          UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  versao           INTEGER NOT NULL CHECK (versao >= 1),
  rodada           INTEGER NOT NULL CHECK (rodada >= 1),
  votantes         VARCHAR(10)[] NOT NULL CHECK (cardinality(votantes) = 3),
  ata_cifrada      TEXT NOT NULL CHECK (ata_cifrada LIKE 'v1:%'),
  pontos_cifrados  TEXT CHECK (pontos_cifrados IS NULL OR pontos_cifrados LIKE 'v1:%'),
  autor_id         VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, versao)
);

COMMENT ON TABLE conduta_atas IS
  'Ata de deliberação do Comitê de Conduta, em versões (issue #1834). Texto e Pontos a confirmar cifrados pela aplicação. Imutável: gerar de novo é versão nova.';
COMMENT ON COLUMN conduta_atas.votantes IS
  'Os três votantes cujos votos da rodada a ata traz. Se um deles fica impedido ou vira Citado, ou a rodada muda, a versão deixa de valer (issue #1834).';

CREATE INDEX IF NOT EXISTS idx_conduta_atas_autor ON conduta_atas (autor_id);

ALTER TABLE conduta_atas ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_atas FROM anon, authenticated;

DROP TRIGGER IF EXISTS trg_conduta_atas_imutaveis ON conduta_atas;
CREATE TRIGGER trg_conduta_atas_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_atas
  FOR EACH ROW EXECUTE FUNCTION conduta_ata_imutavel();

-- ---------- 2. A versão que foi à assinatura ----------
ALTER TABLE conduta_assinaturas
  ADD COLUMN IF NOT EXISTS ata_id UUID REFERENCES conduta_atas(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_conduta_assinaturas_ata ON conduta_assinaturas (ata_id);

ALTER TABLE conduta_assinaturas DROP CONSTRAINT IF EXISTS conduta_assinaturas_ata_da_versao;
ALTER TABLE conduta_assinaturas ADD CONSTRAINT conduta_assinaturas_ata_da_versao CHECK (
  tipo <> 'ata_de_deliberacao' OR (ata_id IS NOT NULL AND caso_id IS NOT NULL)
);

-- Os votos de que a ata sai ainda valem: são da rodada aberta, os três
-- votantes votaram nela, e nenhum deles ficou impedido ou virou Citado depois.
CREATE OR REPLACE FUNCTION conduta_votos_da_ata_valem(p_caso UUID, p_rodada INTEGER, p_votantes VARCHAR[])
RETURNS BOOLEAN AS $$
  SELECT cardinality(p_votantes) = 3
     AND p_rodada = (SELECT c.rodada_do_voto FROM conduta_casos c WHERE c.id = p_caso)
     AND (SELECT count(DISTINCT v.participante_id) FROM conduta_votos v
           WHERE v.caso_id = p_caso AND v.rodada = p_rodada AND v.participante_id = ANY (p_votantes)) = 3
     AND NOT EXISTS (
       SELECT 1 FROM conduta_atribuicoes t
        WHERE t.caso_id = p_caso AND t.impedido_em IS NOT NULL AND t.participante_id = ANY (p_votantes)
     )
     AND NOT EXISTS (
       SELECT 1 FROM conduta_citados ci
        WHERE ci.caso_id = p_caso AND ci.participante_id = ANY (p_votantes)
     );
$$ LANGUAGE sql STABLE;

-- A última versão da ata do caso, se os votos dela ainda valem.
CREATE OR REPLACE FUNCTION conduta_ata_em_dia(p_caso UUID) RETURNS UUID AS $$
  SELECT a.id FROM (
    SELECT * FROM conduta_atas WHERE caso_id = p_caso ORDER BY versao DESC LIMIT 1
  ) a
   WHERE conduta_votos_da_ata_valem(a.caso_id, a.rodada, a.votantes);
$$ LANGUAGE sql STABLE;

-- A última versão da ata do caso, com os votos dela valendo, assinada pelos três.
CREATE OR REPLACE FUNCTION conduta_ata_assinada(p_caso UUID) RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM conduta_assinaturas s
     WHERE s.tipo = 'ata_de_deliberacao'
       AND s.caso_id = p_caso
       AND s.situacao = 'assinado'
       AND s.ata_id = conduta_ata_em_dia(p_caso)
  );
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION conduta_ata_na_etapa_voto() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM conduta_casos WHERE id = NEW.caso_id AND etapa = 'voto' AND resultado IS NULL
     ) THEN
    RAISE EXCEPTION 'A ata de deliberação é da etapa Voto'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NOT conduta_votos_da_ata_valem(NEW.caso_id, NEW.rodada, NEW.votantes) THEN
    RAISE EXCEPTION 'A ata sai dos três votos da rodada aberta, de quem vota no caso hoje'
      USING ERRCODE = 'check_violation';
  END IF;
  IF conduta_ata_assinada(NEW.caso_id) THEN
    RAISE EXCEPTION 'A ata assinada não ganha versão nova'
      USING ERRCODE = 'check_violation';
  END IF;
  IF EXISTS (
       SELECT 1 FROM conduta_assinaturas s
        WHERE s.tipo = 'ata_de_deliberacao' AND s.caso_id = NEW.caso_id AND s.situacao = 'enviado'
          AND s.ata_id = conduta_ata_em_dia(NEW.caso_id)
     ) THEN
    RAISE EXCEPTION 'A ata que está na ClickSign não ganha versão nova'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_atas_na_etapa ON conduta_atas;
CREATE TRIGGER trg_conduta_atas_na_etapa
  BEFORE INSERT ON conduta_atas
  FOR EACH ROW EXECUTE FUNCTION conduta_ata_na_etapa_voto();

-- Só vai à assinatura a última versão da ata, com os votos dela valendo.
CREATE OR REPLACE FUNCTION conduta_assinatura_da_ata_em_dia() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.ata_id IS DISTINCT FROM conduta_ata_em_dia(NEW.caso_id) THEN
    RAISE EXCEPTION 'Só a última versão da ata, com os votos dela valendo, vai à assinatura'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_assinaturas_ata_em_dia ON conduta_assinaturas;
CREATE TRIGGER trg_conduta_assinaturas_ata_em_dia
  BEFORE INSERT ON conduta_assinaturas
  FOR EACH ROW WHEN (NEW.tipo = 'ata_de_deliberacao')
  EXECUTE FUNCTION conduta_assinatura_da_ata_em_dia();

-- ---------- 3. A transcrição da reunião do Comitê ----------
CREATE TABLE IF NOT EXISTS conduta_reuniao_transcricoes (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id        UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  versao         INTEGER NOT NULL CHECK (versao >= 1),
  storage_path   TEXT NOT NULL CHECK (btrim(storage_path) <> ''),
  content_type   TEXT NOT NULL CHECK (content_type NOT LIKE 'audio/%'),
  tamanho_bytes  BIGINT NOT NULL CHECK (tamanho_bytes > 0),
  enviado_por    VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  enviado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, versao)
);

COMMENT ON TABLE conduta_reuniao_transcricoes IS
  'Transcrição da reunião de deliberação do Comitê de Conduta, no rito Completo (issue #1834). Arquivo cifrado no bucket do Canal. Eliminada ao concluir a reunião. O áudio da reunião não entra.';

CREATE INDEX IF NOT EXISTS idx_conduta_reuniao_transcricoes_enviado_por ON conduta_reuniao_transcricoes (enviado_por);

ALTER TABLE conduta_reuniao_transcricoes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_reuniao_transcricoes FROM anon, authenticated;

CREATE OR REPLACE FUNCTION conduta_reuniao_em_aberto() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM conduta_casos
        WHERE id = NEW.caso_id AND etapa = 'voto' AND resultado IS NULL
          AND rito = 'completo' AND reuniao_concluida_em IS NULL
     ) THEN
    RAISE EXCEPTION 'A reunião do Comitê é da etapa Voto do rito Completo, antes de concluída'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_reuniao_transcricoes_em_aberto ON conduta_reuniao_transcricoes;
CREATE TRIGGER trg_conduta_reuniao_transcricoes_em_aberto
  BEFORE INSERT ON conduta_reuniao_transcricoes
  FOR EACH ROW EXECUTE FUNCTION conduta_reuniao_em_aberto();

-- A transcrição não se altera, e só sai depois de concluída a reunião.
CREATE OR REPLACE FUNCTION conduta_transcricao_so_sai_concluida() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    RAISE EXCEPTION 'A transcrição da reunião não se altera'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM conduta_casos WHERE id = OLD.caso_id AND reuniao_concluida_em IS NOT NULL) THEN
    RAISE EXCEPTION 'A transcrição da reunião só é eliminada depois de concluída a reunião'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_reuniao_transcricoes_eliminacao ON conduta_reuniao_transcricoes;
CREATE TRIGGER trg_conduta_reuniao_transcricoes_eliminacao
  BEFORE UPDATE OR DELETE ON conduta_reuniao_transcricoes
  FOR EACH ROW EXECUTE FUNCTION conduta_transcricao_so_sai_concluida();

-- ---------- 4. A lista de conferência da reunião ----------
CREATE TABLE IF NOT EXISTS conduta_reuniao_conferencia (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id      UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  item         TEXT NOT NULL CHECK (item IN ('gravacao_apagada', 'arquivos_apagados')),
  marcado_por  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  marcado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, item)
);

COMMENT ON TABLE conduta_reuniao_conferencia IS
  'Declarações da coordenação na lista de conferência da reunião do Comitê (issue #1834), com quem marcou e quando. Imutável.';

CREATE INDEX IF NOT EXISTS idx_conduta_reuniao_conferencia_marcado_por ON conduta_reuniao_conferencia (marcado_por);

ALTER TABLE conduta_reuniao_conferencia ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_reuniao_conferencia FROM anon, authenticated;

DROP TRIGGER IF EXISTS trg_conduta_reuniao_conferencia_imutavel ON conduta_reuniao_conferencia;
CREATE TRIGGER trg_conduta_reuniao_conferencia_imutavel
  BEFORE UPDATE OR DELETE ON conduta_reuniao_conferencia
  FOR EACH ROW EXECUTE FUNCTION conduta_ata_imutavel();

DROP TRIGGER IF EXISTS trg_conduta_reuniao_conferencia_em_aberto ON conduta_reuniao_conferencia;
CREATE TRIGGER trg_conduta_reuniao_conferencia_em_aberto
  BEFORE INSERT ON conduta_reuniao_conferencia
  FOR EACH ROW EXECUTE FUNCTION conduta_reuniao_em_aberto();

-- CONCLUIR REUNIÃO: só com os quatro itens, e gravada não muda.
CREATE OR REPLACE FUNCTION conduta_reuniao_com_a_lista() RETURNS TRIGGER AS $$
BEGIN
  IF OLD.reuniao_concluida_em IS NOT NULL AND NEW.reuniao_concluida_em IS DISTINCT FROM OLD.reuniao_concluida_em THEN
    RAISE EXCEPTION 'A conclusão da reunião gravada não muda'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.reuniao_concluida_em IS NULL AND NEW.reuniao_concluida_em IS NOT NULL AND (
       NEW.rito IS DISTINCT FROM 'completo'
       OR NOT EXISTS (SELECT 1 FROM conduta_reuniao_transcricoes WHERE caso_id = NEW.id)
       OR NOT conduta_ata_assinada(NEW.id)
       OR (SELECT count(*) FROM conduta_reuniao_conferencia WHERE caso_id = NEW.id) < 2
     ) THEN
    RAISE EXCEPTION 'A reunião só conclui com a transcrição anexada, a ata assinada e as duas declarações'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_reuniao_com_a_lista ON conduta_casos;
CREATE TRIGGER trg_conduta_reuniao_com_a_lista
  BEFORE UPDATE OF reuniao_concluida_em ON conduta_casos
  FOR EACH ROW EXECUTE FUNCTION conduta_reuniao_com_a_lista();

-- ---------- 6. A trava de robustez e a ata ----------
CREATE OR REPLACE FUNCTION conduta_item_dos_votos_com_ata() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.item = 'votos' AND NOT conduta_ata_assinada(NEW.caso_id) THEN
    RAISE EXCEPTION 'O item dos votos se confirma com a ata assinada'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_item_dos_votos_com_ata ON conduta_trava_confirmacoes;
CREATE TRIGGER trg_conduta_item_dos_votos_com_ata
  BEFORE INSERT ON conduta_trava_confirmacoes
  FOR EACH ROW EXECUTE FUNCTION conduta_item_dos_votos_com_ata();

CREATE OR REPLACE FUNCTION conduta_resultado_com_ata() RETURNS TRIGGER AS $$
BEGIN
  IF OLD.resultado IS NULL AND NEW.resultado IS NOT NULL THEN
    IF NOT conduta_ata_assinada(NEW.id) THEN
      RAISE EXCEPTION 'A votação só conclui com a ata assinada pelos três'
        USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.rito = 'completo' AND NEW.reuniao_concluida_em IS NULL THEN
      RAISE EXCEPTION 'No rito Completo, a votação só conclui com a reunião concluída'
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_resultado_com_ata ON conduta_casos;
CREATE TRIGGER trg_conduta_resultado_com_ata
  BEFORE UPDATE OF resultado ON conduta_casos
  FOR EACH ROW EXECUTE FUNCTION conduta_resultado_com_ata();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (221) ON CONFLICT (numero) DO NOTHING;
