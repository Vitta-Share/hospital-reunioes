-- =====================================================
-- Migration 208: os prazos do caso e a tabela de prazos do Núcleo
-- (issue #1993, PRD #1979, ADR 0107 decisões 1 e 2)
-- =====================================================
-- O que entra:
--   1. a tabela de prazos internos do Núcleo (faixa e marco), carregada com
--      os valores do art. 26 do Regimento. Os prazos legais (72 horas, 15º dia
--      útil do mês seguinte, 60 dias) ficam no código e não entram aqui: o
--      CHECK do marco recusa qualquer marco legal;
--   2. o histórico da tabela, que só cresce: o trigger grava quem, quando, de
--      e para a cada alteração, no mesmo update, e o banco recusa UPDATE e
--      DELETE no histórico;
--   3. os prazos do caso, congelados na confirmação da triagem, um por
--      marco, com o vencimento em data e hora. Mudar a tabela não alcança o
--      caso já classificado (art. 26, § 2º);
--   4. a linha mínima de notificação externa, uma por caso, com o sistema de
--      destino (VigiMed para medicação, NOTIVISA para o resto) e o prazo
--      legal. O texto para a vigilância e a fila são da Fase 4.
--
-- Nenhuma pessoa entra por aqui. RLS ligado e sem política nas tabelas
-- novas: só o backend, com a service_role, lê e grava. Rodar duas vezes é
-- inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. A tabela de prazos internos ----------
CREATE TABLE IF NOT EXISTS nsp_tabela_de_prazos (
  faixa           TEXT NOT NULL CHECK (faixa IN ('A', 'B', 'C', 'D', 'E')),
  marco           TEXT NOT NULL CHECK (marco IN ('confirmacao_ao_notificante', 'comunicacao_a_direcao', 'triagem', 'inicio_da_investigacao', 'conclusao_da_investigacao', 'reuniao_de_analise')),
  valor           SMALLINT CHECK (valor BETWEEN 1 AND 365),
  unidade         TEXT CHECK (unidade IN ('horas_corridas', 'horas_uteis', 'dias_corridos', 'dias_uteis')),
  atualizado_por  VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (faixa, marco),
  CHECK ((valor IS NULL) = (unidade IS NULL))
);

COMMENT ON TABLE nsp_tabela_de_prazos IS
  'Os prazos internos do Núcleo por faixa e marco (art. 26 do Regimento), editáveis pela Presidência e pelo Acesso pleno. Sem valor = sem prazo próprio. Os prazos legais ficam no código. Issue #1993.';

CREATE INDEX IF NOT EXISTS idx_nsp_tabela_de_prazos_atualizado_por ON nsp_tabela_de_prazos (atualizado_por);

ALTER TABLE nsp_tabela_de_prazos ENABLE ROW LEVEL SECURITY;

-- A carga do art. 26: as 30 células, as sem prazo próprio com valor vazio.
INSERT INTO nsp_tabela_de_prazos (faixa, marco, valor, unidade) VALUES
  ('A', 'confirmacao_ao_notificante', 24, 'horas_corridas'),
  ('B', 'confirmacao_ao_notificante', 24, 'horas_corridas'),
  ('C', 'confirmacao_ao_notificante', 24, 'horas_corridas'),
  ('D', 'confirmacao_ao_notificante', 24, 'horas_corridas'),
  ('E', 'confirmacao_ao_notificante', 24, 'horas_corridas'),
  ('A', 'comunicacao_a_direcao', 2, 'horas_corridas'),
  ('B', 'comunicacao_a_direcao', 24, 'horas_corridas'),
  ('C', 'comunicacao_a_direcao', NULL, NULL),
  ('D', 'comunicacao_a_direcao', NULL, NULL),
  ('E', 'comunicacao_a_direcao', NULL, NULL),
  ('A', 'triagem', 4, 'horas_uteis'),
  ('B', 'triagem', 1, 'dias_uteis'),
  ('C', 'triagem', 2, 'dias_uteis'),
  ('D', 'triagem', 3, 'dias_uteis'),
  ('E', 'triagem', 5, 'dias_uteis'),
  ('A', 'inicio_da_investigacao', 24, 'horas_uteis'),
  ('B', 'inicio_da_investigacao', 3, 'dias_uteis'),
  ('C', 'inicio_da_investigacao', 5, 'dias_uteis'),
  ('D', 'inicio_da_investigacao', NULL, NULL),
  ('E', 'inicio_da_investigacao', NULL, NULL),
  ('A', 'conclusao_da_investigacao', 45, 'dias_corridos'),
  ('B', 'conclusao_da_investigacao', 30, 'dias_corridos'),
  ('C', 'conclusao_da_investigacao', 20, 'dias_uteis'),
  ('D', 'conclusao_da_investigacao', 10, 'dias_uteis'),
  ('E', 'conclusao_da_investigacao', NULL, NULL),
  ('A', 'reuniao_de_analise', 7, 'dias_uteis'),
  ('B', 'reuniao_de_analise', 15, 'dias_uteis'),
  ('C', 'reuniao_de_analise', NULL, NULL),
  ('D', 'reuniao_de_analise', NULL, NULL),
  ('E', 'reuniao_de_analise', NULL, NULL)
ON CONFLICT (faixa, marco) DO NOTHING;

-- ---------- 2. O histórico da tabela, que só cresce ----------
CREATE TABLE IF NOT EXISTS nsp_tabela_de_prazos_historico (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  faixa         TEXT NOT NULL,
  marco         TEXT NOT NULL,
  de_valor      SMALLINT,
  de_unidade    TEXT,
  para_valor    SMALLINT,
  para_unidade  TEXT,
  alterado_por  VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  alterado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE nsp_tabela_de_prazos_historico IS
  'Cada alteração da tabela de prazos do Núcleo: faixa, marco, de, para, quem e quando. Gravado pelo trigger da tabela; imutável. Issue #1993.';

CREATE INDEX IF NOT EXISTS idx_nsp_tabela_de_prazos_historico_alterado_em
  ON nsp_tabela_de_prazos_historico (alterado_em DESC);
CREATE INDEX IF NOT EXISTS idx_nsp_tabela_de_prazos_historico_alterado_por
  ON nsp_tabela_de_prazos_historico (alterado_por);

ALTER TABLE nsp_tabela_de_prazos_historico ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION nsp_tabela_de_prazos_registrar() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.faixa IS DISTINCT FROM OLD.faixa OR NEW.marco IS DISTINCT FROM OLD.marco THEN
    RAISE EXCEPTION 'A faixa e o marco de uma célula da tabela de prazos não mudam'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.valor IS DISTINCT FROM OLD.valor OR NEW.unidade IS DISTINCT FROM OLD.unidade THEN
    INSERT INTO nsp_tabela_de_prazos_historico
      (faixa, marco, de_valor, de_unidade, para_valor, para_unidade, alterado_por)
      VALUES (NEW.faixa, NEW.marco, OLD.valor, OLD.unidade, NEW.valor, NEW.unidade, NEW.atualizado_por);
  END IF;
  NEW.atualizado_em := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_tabela_de_prazos_registrar ON nsp_tabela_de_prazos;
CREATE TRIGGER trg_nsp_tabela_de_prazos_registrar
  BEFORE UPDATE ON nsp_tabela_de_prazos
  FOR EACH ROW EXECUTE FUNCTION nsp_tabela_de_prazos_registrar();

CREATE OR REPLACE FUNCTION nsp_tabela_de_prazos_sem_exclusao() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Célula da tabela de prazos não se apaga: deixe sem prazo, que fica no histórico'
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_tabela_de_prazos_sem_exclusao ON nsp_tabela_de_prazos;
CREATE TRIGGER trg_nsp_tabela_de_prazos_sem_exclusao
  BEFORE DELETE ON nsp_tabela_de_prazos
  FOR EACH ROW EXECUTE FUNCTION nsp_tabela_de_prazos_sem_exclusao();

CREATE OR REPLACE FUNCTION nsp_tabela_de_prazos_historico_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'O histórico da tabela de prazos só cresce: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_tabela_de_prazos_historico_imutavel ON nsp_tabela_de_prazos_historico;
CREATE TRIGGER trg_nsp_tabela_de_prazos_historico_imutavel
  BEFORE UPDATE OR DELETE ON nsp_tabela_de_prazos_historico
  FOR EACH ROW EXECUTE FUNCTION nsp_tabela_de_prazos_historico_imutavel();

-- ---------- 3. Os prazos do caso ----------
CREATE TABLE IF NOT EXISTS nsp_prazos_do_caso (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notificacao_id  UUID NOT NULL REFERENCES nsp_notificacoes(id) ON DELETE RESTRICT,
  marco           TEXT NOT NULL CHECK (marco IN ('confirmacao_ao_notificante', 'comunicacao_a_direcao', 'triagem', 'inicio_da_investigacao', 'conclusao_da_investigacao', 'reuniao_de_analise', 'notificacao_externa', 'complementacao_da_notificacao_externa')),
  tipo            TEXT NOT NULL CHECK (tipo IN ('legal', 'interno')),
  valor           SMALLINT NOT NULL CHECK (valor > 0),
  unidade         TEXT NOT NULL CHECK (unidade IN ('horas_corridas', 'horas_uteis', 'dias_corridos', 'dias_uteis', 'dia_util_do_mes_seguinte')),
  contado_de      TIMESTAMPTZ NOT NULL,
  vence_em        TIMESTAMPTZ NOT NULL,
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (notificacao_id, marco),
  CHECK ((tipo = 'legal') = (marco IN ('notificacao_externa', 'complementacao_da_notificacao_externa')))
);

COMMENT ON TABLE nsp_prazos_do_caso IS
  'Os vencimentos do caso do Núcleo, congelados na confirmação da triagem: os internos da tabela do dia, contados da chegada; os legais do código, contados do incidente. A tabela mudada depois não alcança o caso (art. 26, § 2º). Issue #1993.';

CREATE INDEX IF NOT EXISTS idx_nsp_prazos_do_caso_vence_em ON nsp_prazos_do_caso (vence_em);

ALTER TABLE nsp_prazos_do_caso ENABLE ROW LEVEL SECURITY;

-- ---------- 4. A linha mínima de notificação externa ----------
CREATE TABLE IF NOT EXISTS nsp_notificacoes_externas (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notificacao_id  UUID NOT NULL UNIQUE REFERENCES nsp_notificacoes(id) ON DELETE RESTRICT,
  sistema         TEXT NOT NULL CHECK (sistema IN ('notivisa', 'vigimed')),
  prazo_legal     TIMESTAMPTZ NOT NULL,
  estado          TEXT NOT NULL DEFAULT 'pendente' CHECK (estado IN ('pendente', 'enviada', 'complementacao_pendente', 'concluida')),
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE nsp_notificacoes_externas IS
  'A notificação do caso à vigilância sanitária: o sistema de destino (VigiMed para medicação, NOTIVISA para o resto) e o prazo legal. Criada ao confirmar a triagem, menos na circunstância de risco, que não se notifica. Issue #1993.';

CREATE INDEX IF NOT EXISTS idx_nsp_notificacoes_externas_prazo ON nsp_notificacoes_externas (estado, prazo_legal);

ALTER TABLE nsp_notificacoes_externas ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (208) ON CONFLICT (numero) DO NOTHING;
