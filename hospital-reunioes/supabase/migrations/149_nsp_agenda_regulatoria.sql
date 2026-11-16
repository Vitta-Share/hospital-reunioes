-- =====================================================
-- Migration 149: Segurança do Paciente, a Agenda regulatória
-- (issue #1779, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra:
--   1. a lista das obrigações recorrentes do Núcleo (`nsp_agenda_regulatoria`):
--      evento, periodicidade, próxima data, link e antecedência do lembrete.
--      A Presidência edita, inclui e desativa pela tela;
--   2. as ocorrências (`nsp_agenda_ocorrencias`): uma linha por data de cada
--      evento, com a Pendência de lembrete que o job diário criou e o
--      resultado que a Presidência registrou. É o histórico. A chave única
--      (item, data) garante um lembrete por ocorrência;
--   3. a carga inicial com os eventos da seção 6.4 da especificação, que são
--      obrigações do Núcleo e não dados de pessoas. Entra só com a lista
--      vazia: a lista que a Presidência já editou não volta ao que era. As
--      datas ficam em branco, para a Presidência marcar.
--
-- RLS default-deny nas tabelas novas (padrão da casa): quem lê e escreve é o
-- backend com a service_role. Nenhuma policy de propósito.
--
-- Tudo com IF NOT EXISTS / DROP antes de ADD / WHERE NOT EXISTS: rodar duas
-- vezes é inofensivo. Aplicar à mão no Studio: o deploy não aplica SQL.
-- =====================================================

BEGIN;

-- ---------- 1. A agenda ----------
CREATE TABLE IF NOT EXISTS nsp_agenda_regulatoria (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evento            TEXT NOT NULL CHECK (char_length(btrim(evento)) BETWEEN 1 AND 200),
  periodicidade     TEXT NOT NULL CHECK (periodicidade IN ('mensal', 'anual', 'bienal', 'avulsa')),
  regra             TEXT CHECK (regra IS NULL OR char_length(regra) <= 200),
  proxima_data      DATE,
  link              TEXT CHECK (link IS NULL OR (link ~ '^https?://[^[:space:]]+$' AND char_length(link) <= 500)),
  antecedencia_dias INTEGER NOT NULL DEFAULT 7 CHECK (antecedencia_dias BETWEEN 0 AND 90),
  ativo             BOOLEAN NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE nsp_agenda_regulatoria IS
  'Agenda regulatória do Núcleo de Segurança do Paciente (issue #1779): as obrigações recorrentes. A Presidência edita; o job diário cria a Pendência de lembrete.';
COMMENT ON COLUMN nsp_agenda_regulatoria.periodicidade IS
  'mensal, anual, bienal: registrar o resultado avança a próxima data. avulsa: não se repete, a próxima data fica em branco.';
COMMENT ON COLUMN nsp_agenda_regulatoria.regra IS
  'O detalhe da periodicidade, em texto (ex.: até o 15º dia útil).';
COMMENT ON COLUMN nsp_agenda_regulatoria.antecedencia_dias IS
  'Quantos dias antes da próxima data o lembrete nasce como Pendência da Presidência.';

CREATE INDEX IF NOT EXISTS idx_nsp_agenda_proxima_data
  ON nsp_agenda_regulatoria(proxima_data) WHERE ativo;

ALTER TABLE nsp_agenda_regulatoria ENABLE ROW LEVEL SECURITY;

-- ---------- 2. As ocorrências ----------
CREATE TABLE IF NOT EXISTS nsp_agenda_ocorrencias (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id        UUID NOT NULL REFERENCES nsp_agenda_regulatoria(id) ON DELETE RESTRICT,
  data_prevista  DATE NOT NULL,
  pendencia_id   VARCHAR(10) REFERENCES pendencias(id_acao) ON DELETE SET NULL,
  resultado      TEXT CHECK (resultado IS NULL OR char_length(btrim(resultado)) BETWEEN 1 AND 2000),
  realizada_em   DATE,
  registrado_por VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  registrado_em  TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT nsp_agenda_ocorrencias_unica UNIQUE (item_id, data_prevista)
);

COMMENT ON TABLE nsp_agenda_ocorrencias IS
  'Uma data de um evento da Agenda regulatória (issue #1779): a Pendência de lembrete e o resultado registrado. É o histórico.';

CREATE INDEX IF NOT EXISTS idx_nsp_agenda_ocorrencias_pendencia
  ON nsp_agenda_ocorrencias(pendencia_id) WHERE pendencia_id IS NOT NULL;

ALTER TABLE nsp_agenda_ocorrencias ENABLE ROW LEVEL SECURITY;

-- ---------- 3. A carga inicial (seção 6.4 da especificação) ----------
INSERT INTO nsp_agenda_regulatoria (evento, periodicidade, regra)
SELECT evento, periodicidade, regra
FROM (VALUES
  ('Notificação externa do mês', 'mensal', 'Até o 15º dia útil'),
  ('Fechamento mensal e relatório', 'mensal', NULL),
  ('Reunião ordinária', 'mensal', NULL),
  ('Avaliação Nacional das Práticas de Segurança do Paciente', 'anual', 'No prazo da vigilância'),
  ('Avaliação da cultura de segurança (E-Questionário da ANVISA)', 'bienal', NULL),
  ('Revisão do PSP e do Regimento', 'anual', NULL),
  ('Vencimento de vigência dos membros', 'avulsa', '60 e 30 dias antes'),
  ('Recalibração do agente', 'avulsa', '30 e 60 dias depois da entrada em operação')
) AS carga(evento, periodicidade, regra)
WHERE NOT EXISTS (SELECT 1 FROM nsp_agenda_regulatoria);

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (149) ON CONFLICT (numero) DO NOTHING;
