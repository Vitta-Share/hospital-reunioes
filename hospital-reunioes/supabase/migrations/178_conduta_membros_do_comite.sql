-- =====================================================
-- Migration 178: Canal de Conduta, os membros do Comitê
-- (issue #1822, PRD #1786, ADR 0097, decisão 3)
-- =====================================================
-- O que entra:
--   1. a cadeira "membro e segundo leitor" (`segundo_leitor`) na Participação;
--   2. a marcação de que o membro é ou não diretor (`e_diretor`), que a Rota
--      Especial usa depois. Nasce falsa;
--   3. o registro do módulo (`conduta_registro`): inclusão e encerramento de
--      Participação e o perfil de cadastro dado ou tirado, com autor e data.
--      Não se altera nem se apaga;
--   4. o tipo `CONDUTA` no sino, para o aviso aos membros a cada mudança.
--
-- Nenhuma pessoa entra por aqui: os membros e o perfil de cadastro entram
-- pela tela. RLS default-deny na tabela nova, sem policy: só o backend, com a
-- service_role, lê e grava.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. A cadeira de segundo leitor ----------
ALTER TABLE participacoes DROP CONSTRAINT IF EXISTS participacoes_papel_check;
ALTER TABLE participacoes
  ADD CONSTRAINT participacoes_papel_check
  CHECK (papel IN ('presidencia', 'suplente', 'membro', 'coordenacao', 'segundo_leitor'));

-- ---------- 2. Diretor ou não ----------
ALTER TABLE participacoes
  ADD COLUMN IF NOT EXISTS e_diretor BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN participacoes.e_diretor IS
  'Comitê de Conduta: o membro é diretor. A Rota Especial monta o grupo sem diretor (issue #1822).';

-- ---------- 3. O registro do módulo ----------
CREATE TABLE IF NOT EXISTS conduta_registro (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  acao             TEXT NOT NULL CHECK (acao IN ('inclusao', 'encerramento', 'perfil_dado', 'perfil_tirado')),
  -- Quem entrou, saiu, ganhou ou perdeu o perfil.
  participante_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  participacao_id  UUID REFERENCES participacoes(id) ON DELETE RESTRICT,
  autor_id         VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  detalhe          TEXT NOT NULL DEFAULT '',
  registrado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE conduta_registro IS
  'Registro do Comitê de Conduta (ADR 0097, decisão 3): inclusão e saída de membro, perfil de cadastro dado ou tirado, com autor e data. Imutável. Issue #1822.';

CREATE INDEX IF NOT EXISTS idx_conduta_registro_quando
  ON conduta_registro (registrado_em DESC);
CREATE INDEX IF NOT EXISTS idx_conduta_registro_pessoa
  ON conduta_registro (participante_id);
CREATE INDEX IF NOT EXISTS idx_conduta_registro_autor
  ON conduta_registro (autor_id);
CREATE INDEX IF NOT EXISTS idx_conduta_registro_participacao
  ON conduta_registro (participacao_id);

ALTER TABLE conduta_registro ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION conduta_registro_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'O registro do Comitê é imutável: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_registro_imutavel ON conduta_registro;
CREATE TRIGGER trg_conduta_registro_imutavel
  BEFORE UPDATE OR DELETE ON conduta_registro
  FOR EACH ROW EXECUTE FUNCTION conduta_registro_imutavel();

DROP TRIGGER IF EXISTS trg_conduta_registro_sem_truncate ON conduta_registro;
CREATE TRIGGER trg_conduta_registro_sem_truncate
  BEFORE TRUNCATE ON conduta_registro
  FOR EACH STATEMENT EXECUTE FUNCTION conduta_registro_imutavel();

-- ---------- 4. O aviso no sino ----------
ALTER TABLE notificacoes DROP CONSTRAINT IF EXISTS notificacoes_tipo_check;
ALTER TABLE notificacoes ADD CONSTRAINT notificacoes_tipo_check
  CHECK (tipo IN (
    'MENCAO',
    'STATUS_ALTERADO',
    'COMENTARIO',
    'PRAZO_PROXIMO',
    'RESPONSAVEL_ATRIBUIDO',
    'ACEITE_INTERNO',
    'CONTAS_MEDICAS',
    'TECNOLOGIA',
    'CONDUTA'
  ));

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (178) ON CONFLICT (numero) DO NOTHING;
