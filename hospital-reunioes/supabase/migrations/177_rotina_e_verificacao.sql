-- =====================================================
-- Migration 177: Rotina e Verificacao (ADR 0098, decisao 9; issue #1874)
-- =====================================================
-- A Rotina substitui o "fluxo continuo": nasce do envio da Ata (linha do tipo
-- Rotina no quadro), com responsavel e frequencia, e vive aqui, fora de
-- `pendencias`. A Verificacao e calculada pelo calendario (semana, quinzena
-- de 1 a 15 e de 16 ao fim do mes, ou mes): o ciclo existe pela data e a linha
-- so e gravada quando alguem marca. Nenhum job cria Verificacao.
--
-- 1. `rotinas`: uma por linha de Rotina do quadro (chave id_reuniao +
--    quadro_pos, para o nascimento ser idempotente). `comeca_em` e o primeiro
--    dia do primeiro ciclo inteiro depois do envio. `frequencia` aceita NULL
--    para o fluxo continuo antigo convertido sem frequencia (#1877).
-- 2. `rotina_verificacoes`: uma por ciclo marcado (chave rotina_id +
--    ciclo_inicio). Nao realizada exige anotacao; `atrasada` diz que foi
--    marcada depois do ultimo dia do ciclo.
--
-- RLS default-deny: so o backend, com a service_role, le e grava. Nenhuma
-- policy de proposito. Rodar duas vezes e inofensivo. Aplicar a mao no Studio.
-- =====================================================

BEGIN;

-- 1. Rotina --------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rotinas (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  id_reuniao             VARCHAR(20) NOT NULL REFERENCES reunioes(id_reuniao) ON DELETE RESTRICT,
  quadro_pos             INTEGER NOT NULL,
  descricao              TEXT NOT NULL,
  responsavel_id         VARCHAR(10) REFERENCES participantes(id),
  responsavel_nome       TEXT NOT NULL DEFAULT '',
  frequencia             TEXT CHECK (frequencia IN ('SEMANAL', 'QUINZENAL', 'MENSAL')),
  comeca_em              DATE,
  status                 TEXT NOT NULL DEFAULT 'ATIVA' CHECK (status IN ('ATIVA', 'ENCERRADA')),
  encerrada_em           DATE,
  encerrada_por_id       VARCHAR(10),
  encerrada_por_nome     TEXT,
  anotacao_encerramento  TEXT,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (id_reuniao, quadro_pos),
  -- Encerrar pede anotacao e o dia (decisao 89 da #1757).
  CHECK (
    status = 'ATIVA'
    OR (encerrada_em IS NOT NULL AND length(btrim(coalesce(anotacao_encerramento, ''))) > 0)
  )
);

COMMENT ON TABLE rotinas IS
  'Rotina (ADR 0098, decisao 9): a decisao da Ata que se repete por semana, quinzena ou mes. Issue #1874.';

CREATE INDEX IF NOT EXISTS idx_rotinas_responsavel ON rotinas (responsavel_id);

ALTER TABLE rotinas ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON rotinas FROM anon, authenticated;

-- 2. Verificacao -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rotina_verificacoes (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rotina_id        UUID NOT NULL REFERENCES rotinas(id) ON DELETE RESTRICT,
  ciclo_inicio     DATE NOT NULL,
  ciclo_fim        DATE NOT NULL CHECK (ciclo_fim >= ciclo_inicio),
  resultado        TEXT NOT NULL CHECK (resultado IN ('REALIZADA', 'NAO_REALIZADA')),
  anotacao         TEXT,
  atrasada         BOOLEAN NOT NULL DEFAULT false,
  -- Sem FK: o registro nao pode depender de um cadastro que muda.
  marcada_por_id   VARCHAR(10),
  marcada_por_nome TEXT NOT NULL,
  marcada_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rotina_id, ciclo_inicio),
  -- Realizada e um clique; Nao realizada pede anotacao (decisao 75 da #1757).
  CHECK (resultado = 'REALIZADA' OR length(btrim(coalesce(anotacao, ''))) > 0)
);

COMMENT ON TABLE rotina_verificacoes IS
  'Verificacao da Rotina (ADR 0098, decisao 9): um ciclo marcado. O ciclo vem da data; a linha so existe depois da marcacao. Issue #1874.';

ALTER TABLE rotina_verificacoes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON rotina_verificacoes FROM anon, authenticated;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (177) ON CONFLICT (numero) DO NOTHING;
