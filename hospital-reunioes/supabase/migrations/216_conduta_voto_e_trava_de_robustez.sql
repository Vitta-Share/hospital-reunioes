-- =====================================================
-- Migration 216: Canal de Conduta, o voto e a trava de robustez
-- (issue #1833, PRD #1786, ADR 0097; especificação, 6.6 e 6.7)
-- =====================================================
-- O que entra:
--   1. o voto de cada membro, por rodada: resultado, medida e justificativa
--      num texto só, cifrado pela aplicação. Um voto por pessoa e rodada; o
--      voto registrado não se altera nem se apaga. Só entra voto em caso na
--      etapa Voto;
--   2. no caso, a rodada do voto (a reunião curta abre a seguinte), o
--      resultado da votação (em claro, como a etapa), a medida da maioria
--      (cifrada), quem concluiu e quando. A etapa `ata`, depois do Voto;
--   3. a trava de robustez: o preenchimento do agente, em versões cifradas,
--      a confirmação de cada membro em cada item e a ciência do Código que o
--      DP registrou fora e um membro anexou. Nada disso se altera nem se
--      apaga;
--   4. procedente e parcialmente procedente só com os sete itens da trava
--      confirmados, e o resultado gravado não muda;
--   5. o aviso da reunião curta, como motivo novo do aviso.
--
-- RLS default-deny em toda tabela nova: só o backend, com a service_role, lê
-- e grava. Nenhuma policy de propósito. Nenhum dado de pessoa em claro.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- A recusa de UPDATE e DELETE das tabelas guardadas desta migration.
CREATE OR REPLACE FUNCTION conduta_voto_e_trava_imutaveis() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'O registro do voto e da trava fica guardado: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

-- Voto, confirmação, preenchimento e ciência só entram com o caso no Voto.
CREATE OR REPLACE FUNCTION conduta_so_na_etapa_voto() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM conduta_casos WHERE id = NEW.caso_id AND etapa = 'voto' AND resultado IS NULL
     ) THEN
    RAISE EXCEPTION 'O voto e a trava de robustez são da etapa Voto'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------- 2. No caso: a rodada, o resultado e a etapa Ata ----------
-- Antes das tabelas: o gatilho da etapa Voto lê `resultado`.
ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS rodada_do_voto         INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS resultado              TEXT,
  ADD COLUMN IF NOT EXISTS medida_cifrada         TEXT,
  ADD COLUMN IF NOT EXISTS votacao_concluida_por  VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS votacao_concluida_em   TIMESTAMPTZ;

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_rodada_do_voto_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_rodada_do_voto_check CHECK (rodada_do_voto >= 1);

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_resultado_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_resultado_check
  CHECK (
    resultado IS NULL
    OR resultado IN ('procedente', 'parcialmente_procedente', 'improcedente', 'inconclusivo')
  );

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_medida_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_medida_check
  CHECK (medida_cifrada IS NULL OR medida_cifrada LIKE 'v1:%');

COMMENT ON COLUMN conduta_casos.resultado IS
  'Resultado da votação do Comitê, pela maioria (issue #1833). Procedente e parcialmente procedente só com a trava de robustez inteira (trigger). Gravado, não muda.';
COMMENT ON COLUMN conduta_casos.rodada_do_voto IS
  'A rodada de voto aberta. Sem maioria, a reunião curta abre a seguinte, e os votos de antes ficam (issue #1833).';

CREATE INDEX IF NOT EXISTS idx_conduta_casos_votacao_concluida_por ON conduta_casos (votacao_concluida_por);

-- ---------- 1. O voto ----------
CREATE TABLE IF NOT EXISTS conduta_votos (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id          UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  rodada           INTEGER NOT NULL CHECK (rodada >= 1),
  participante_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  voto_cifrado     TEXT NOT NULL CHECK (voto_cifrado LIKE 'v1:%'),
  votado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, rodada, participante_id)
);

COMMENT ON TABLE conduta_votos IS
  'Voto de cada membro do Comitê de Conduta, por rodada (issue #1833). Resultado, medida e justificativa cifrados juntos pela aplicação. Imutável.';

CREATE INDEX IF NOT EXISTS idx_conduta_votos_participante ON conduta_votos (participante_id);

ALTER TABLE conduta_votos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_votos FROM anon, authenticated;

DROP TRIGGER IF EXISTS trg_conduta_votos_imutaveis ON conduta_votos;
CREATE TRIGGER trg_conduta_votos_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_votos
  FOR EACH ROW EXECUTE FUNCTION conduta_voto_e_trava_imutaveis();

DROP TRIGGER IF EXISTS trg_conduta_votos_na_etapa ON conduta_votos;
CREATE TRIGGER trg_conduta_votos_na_etapa
  BEFORE INSERT ON conduta_votos
  FOR EACH ROW EXECUTE FUNCTION conduta_so_na_etapa_voto();

-- ---------- 3. A trava de robustez ----------
CREATE TABLE IF NOT EXISTS conduta_trava_preenchimentos (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id        UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  versao         INTEGER NOT NULL CHECK (versao >= 1),
  itens_cifrado  TEXT NOT NULL CHECK (itens_cifrado LIKE 'v1:%'),
  autor_id       VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, versao)
);

COMMENT ON TABLE conduta_trava_preenchimentos IS
  'Preenchimento da trava de robustez pelo agente, depois do clique de um membro (issue #1833). Cifrado. Imutável: preencher de novo é versão nova.';

CREATE INDEX IF NOT EXISTS idx_conduta_trava_preenchimentos_autor ON conduta_trava_preenchimentos (autor_id);

ALTER TABLE conduta_trava_preenchimentos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_trava_preenchimentos FROM anon, authenticated;

CREATE TABLE IF NOT EXISTS conduta_trava_confirmacoes (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id          UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  item             TEXT NOT NULL CHECK (item IN ('fato', 'prova', 'defesa', 'regra', 'ciencia', 'medida', 'votos')),
  participante_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  confirmado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, item, participante_id)
);

COMMENT ON TABLE conduta_trava_confirmacoes IS
  'Confirmação de um membro num item da trava de robustez (issue #1833). A recusa da defesa pede dois membros. Imutável: a confirmação não se desfaz.';

CREATE INDEX IF NOT EXISTS idx_conduta_trava_confirmacoes_participante ON conduta_trava_confirmacoes (participante_id);

ALTER TABLE conduta_trava_confirmacoes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_trava_confirmacoes FROM anon, authenticated;

CREATE TABLE IF NOT EXISTS conduta_ciencias_do_codigo (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id        UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  versao         INTEGER NOT NULL CHECK (versao >= 1),
  storage_path   TEXT NOT NULL CHECK (btrim(storage_path) <> ''),
  content_type   TEXT NOT NULL,
  tamanho_bytes  BIGINT NOT NULL CHECK (tamanho_bytes > 0),
  enviado_por    VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  enviado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, versao)
);

COMMENT ON TABLE conduta_ciencias_do_codigo IS
  'Ciência prévia do Código pelo acusado, registrada pelo DP fora do aplicativo e anexada por um membro (issue #1833). Arquivo cifrado no bucket do Canal. Imutável.';

CREATE INDEX IF NOT EXISTS idx_conduta_ciencias_do_codigo_enviado_por ON conduta_ciencias_do_codigo (enviado_por);

ALTER TABLE conduta_ciencias_do_codigo ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_ciencias_do_codigo FROM anon, authenticated;

DROP TRIGGER IF EXISTS trg_conduta_trava_preenchimentos_imutaveis ON conduta_trava_preenchimentos;
CREATE TRIGGER trg_conduta_trava_preenchimentos_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_trava_preenchimentos
  FOR EACH ROW EXECUTE FUNCTION conduta_voto_e_trava_imutaveis();

DROP TRIGGER IF EXISTS trg_conduta_trava_confirmacoes_imutaveis ON conduta_trava_confirmacoes;
CREATE TRIGGER trg_conduta_trava_confirmacoes_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_trava_confirmacoes
  FOR EACH ROW EXECUTE FUNCTION conduta_voto_e_trava_imutaveis();

DROP TRIGGER IF EXISTS trg_conduta_ciencias_do_codigo_imutaveis ON conduta_ciencias_do_codigo;
CREATE TRIGGER trg_conduta_ciencias_do_codigo_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_ciencias_do_codigo
  FOR EACH ROW EXECUTE FUNCTION conduta_voto_e_trava_imutaveis();

DROP TRIGGER IF EXISTS trg_conduta_trava_preenchimentos_na_etapa ON conduta_trava_preenchimentos;
CREATE TRIGGER trg_conduta_trava_preenchimentos_na_etapa
  BEFORE INSERT ON conduta_trava_preenchimentos
  FOR EACH ROW EXECUTE FUNCTION conduta_so_na_etapa_voto();

DROP TRIGGER IF EXISTS trg_conduta_trava_confirmacoes_na_etapa ON conduta_trava_confirmacoes;
CREATE TRIGGER trg_conduta_trava_confirmacoes_na_etapa
  BEFORE INSERT ON conduta_trava_confirmacoes
  FOR EACH ROW EXECUTE FUNCTION conduta_so_na_etapa_voto();

DROP TRIGGER IF EXISTS trg_conduta_ciencias_do_codigo_na_etapa ON conduta_ciencias_do_codigo;
CREATE TRIGGER trg_conduta_ciencias_do_codigo_na_etapa
  BEFORE INSERT ON conduta_ciencias_do_codigo
  FOR EACH ROW EXECUTE FUNCTION conduta_so_na_etapa_voto();

-- ---------- 4. O resultado e a trava ----------
CREATE OR REPLACE FUNCTION conduta_resultado_com_trava() RETURNS TRIGGER AS $$
BEGIN
  IF OLD.resultado IS NOT NULL AND NEW.resultado IS DISTINCT FROM OLD.resultado THEN
    RAISE EXCEPTION 'O resultado da votação gravado não muda'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.resultado IS NULL AND NEW.resultado IS NOT NULL AND OLD.etapa <> 'voto' THEN
    RAISE EXCEPTION 'O resultado sai da etapa Voto'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.resultado IS NULL
     AND NEW.resultado IN ('procedente', 'parcialmente_procedente')
     AND (SELECT count(DISTINCT item) FROM conduta_trava_confirmacoes WHERE caso_id = NEW.id) < 7 THEN
    RAISE EXCEPTION 'A trava de robustez tem item em aberto: o caso não conclui como procedente'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_resultado_com_trava ON conduta_casos;
CREATE TRIGGER trg_conduta_resultado_com_trava
  BEFORE UPDATE OF resultado ON conduta_casos
  FOR EACH ROW EXECUTE FUNCTION conduta_resultado_com_trava();

-- ---------- 5. O aviso da reunião curta ----------
ALTER TABLE conduta_avisos DROP CONSTRAINT IF EXISTS conduta_avisos_motivo_check;
ALTER TABLE conduta_avisos
  ADD CONSTRAINT conduta_avisos_motivo_check
  CHECK (motivo IN ('tarefa', 'lembrete_5', 'lembrete_1', 'marco_15', 'marco_30', 'marco_60', 'reuniao_curta'));

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (216) ON CONFLICT (numero) DO NOTHING;
