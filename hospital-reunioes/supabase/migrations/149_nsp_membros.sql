-- =====================================================
-- Migration 149: Segurança do Paciente, os membros do Núcleo
-- (issue #1766, PRD #1764, ADR 0095, decisões 3 e 12)
-- =====================================================
-- O que entra:
--   1. a Participação ganha a área que o membro representa e a data do
--      encerramento. Encerrar não apaga: a linha fica, e a vigência termina
--      no dia do encerramento;
--   2. uma Participação aberta (não encerrada) por pessoa no Colegiado;
--   3. a trilha da Participação: quem mudou, quando, o quê, de e para.
--      Append-only, como o Movimento da Ouvidoria;
--   4. o banco recusa apagar Participação. Não existe rota de exclusão, e
--      quem chegar pelo banco também não apaga.
--
-- O estado do membro (Cadastrado, Ativo, A vencer...) NÃO é coluna: sai de uma
-- função pura no backend, a partir das datas.
--
-- Nenhuma pessoa entra por aqui (decisão 12): a carga é pela tela.
-- RLS default-deny na tabela nova: só o backend, com a service_role, lê e grava.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. Área e encerramento ----------
ALTER TABLE participacoes
  ADD COLUMN IF NOT EXISTS area TEXT;
ALTER TABLE participacoes
  ADD COLUMN IF NOT EXISTS encerrada_em DATE;

ALTER TABLE participacoes DROP CONSTRAINT IF EXISTS participacoes_area_check;
ALTER TABLE participacoes
  ADD CONSTRAINT participacoes_area_check
  CHECK (area IS NULL OR char_length(btrim(area)) BETWEEN 1 AND 120);

COMMENT ON COLUMN participacoes.area IS
  'A área do hospital que o membro representa no Colegiado. Issue #1766.';
COMMENT ON COLUMN participacoes.encerrada_em IS
  'Dia em que a Participação foi encerrada pela tela. A vigência termina neste dia; a linha nunca é apagada. Issue #1766.';

-- ---------- 2. Uma Participação aberta por pessoa ----------
CREATE UNIQUE INDEX IF NOT EXISTS uq_participacoes_aberta_por_pessoa
  ON participacoes (colegiado_id, participante_id)
  WHERE encerrada_em IS NULL;

-- ---------- 3. A trilha ----------
CREATE TABLE IF NOT EXISTS participacoes_trilha (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participacao_id  UUID NOT NULL REFERENCES participacoes(id) ON DELETE RESTRICT,
  autor_id         VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  acao             TEXT NOT NULL CHECK (acao IN ('cadastro', 'edicao', 'renovacao', 'mudanca_de_papel', 'encerramento')),
  campo            TEXT,
  valor_anterior   TEXT,
  valor_novo       TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE participacoes_trilha IS
  'Trilha da Participação (issue #1766): autor, data, campo, valor anterior e novo. Imutável: o banco recusa UPDATE e DELETE.';

CREATE INDEX IF NOT EXISTS idx_participacoes_trilha_participacao
  ON participacoes_trilha (participacao_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_participacoes_trilha_autor
  ON participacoes_trilha (autor_id);

ALTER TABLE participacoes_trilha ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION participacoes_trilha_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'A trilha da Participação é imutável: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_participacoes_trilha_imutavel ON participacoes_trilha;
CREATE TRIGGER trg_participacoes_trilha_imutavel
  BEFORE UPDATE OR DELETE ON participacoes_trilha
  FOR EACH ROW EXECUTE FUNCTION participacoes_trilha_imutavel();

-- ---------- 4. Participação não se apaga ----------
CREATE OR REPLACE FUNCTION participacoes_sem_exclusao() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Participação não se apaga: encerre a vigência'
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_participacoes_sem_exclusao ON participacoes;
CREATE TRIGGER trg_participacoes_sem_exclusao
  BEFORE DELETE ON participacoes
  FOR EACH ROW EXECUTE FUNCTION participacoes_sem_exclusao();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (149) ON CONFLICT (numero) DO NOTHING;
