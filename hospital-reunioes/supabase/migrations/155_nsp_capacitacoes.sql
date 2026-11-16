-- =====================================================
-- Migration 155: Segurança do Paciente, as Capacitações do Núcleo
-- (issue #1778, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra:
--   1. a lista de temas mínimos de capacitação, dado de configuração que a
--      Presidência edita pela tela. Nasce VAZIA: a Diretoria ainda vai mandar
--      os temas. Tema não se apaga, se desativa: a capacitação antiga continua
--      dizendo o que tratou;
--   2. a capacitação: título, data, carga horária, instrutor, público e os
--      temas tratados (ids da lista de temas);
--   3. quem participou, uma linha por pessoa, com a hora em que ela mesma
--      confirmou a presença. Sem confirmação, a linha fica com a hora nula e
--      não conta para a cobertura dos temas.
--
-- Nenhuma pessoa entra por aqui (ADR 0095, decisão 12): a carga é pela tela.
-- RLS default-deny nas tabelas novas: só o backend, com a service_role, lê e
-- grava. Nenhuma policy de propósito.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. Os temas mínimos ----------
CREATE TABLE IF NOT EXISTS nsp_temas_minimos (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome       TEXT NOT NULL CHECK (char_length(btrim(nome)) BETWEEN 1 AND 200),
  ativo      BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE nsp_temas_minimos IS
  'Os temas mínimos de capacitação do Núcleo (issue #1778). Configuração editada pela Presidência; nasce vazia.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_nsp_temas_minimos_nome
  ON nsp_temas_minimos (lower(btrim(nome)));

ALTER TABLE nsp_temas_minimos ENABLE ROW LEVEL SECURITY;

-- ---------- 2. As capacitações ----------
CREATE TABLE IF NOT EXISTS nsp_capacitacoes (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  titulo        TEXT NOT NULL CHECK (char_length(btrim(titulo)) BETWEEN 1 AND 200),
  data          DATE NOT NULL,
  carga_horaria NUMERIC(5, 1) NOT NULL CHECK (carga_horaria > 0),
  instrutor     TEXT NOT NULL CHECK (char_length(btrim(instrutor)) BETWEEN 1 AND 200),
  publico       TEXT NOT NULL CHECK (publico IN ('membros', 'profissionais')),
  tema_ids      UUID[] NOT NULL DEFAULT '{}',
  criado_por    VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE nsp_capacitacoes IS
  'Capacitação registrada pela Presidência do Núcleo (issue #1778). tema_ids aponta para nsp_temas_minimos.';

CREATE INDEX IF NOT EXISTS idx_nsp_capacitacoes_data
  ON nsp_capacitacoes (data DESC);
CREATE INDEX IF NOT EXISTS idx_nsp_capacitacoes_criado_por
  ON nsp_capacitacoes (criado_por);

ALTER TABLE nsp_capacitacoes ENABLE ROW LEVEL SECURITY;

-- ---------- 3. Os participantes e a presença ----------
CREATE TABLE IF NOT EXISTS nsp_capacitacao_participantes (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  capacitacao_id         UUID NOT NULL REFERENCES nsp_capacitacoes(id) ON DELETE RESTRICT,
  participante_id        VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  presenca_confirmada_em TIMESTAMPTZ,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (capacitacao_id, participante_id)
);

COMMENT ON COLUMN nsp_capacitacao_participantes.presenca_confirmada_em IS
  'Quando a própria pessoa confirmou a presença no app. Nulo = não confirmou e não conta para a cobertura dos temas.';

CREATE INDEX IF NOT EXISTS idx_nsp_capacitacao_participantes_pessoa
  ON nsp_capacitacao_participantes (participante_id);

ALTER TABLE nsp_capacitacao_participantes ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (155) ON CONFLICT (numero) DO NOTHING;
